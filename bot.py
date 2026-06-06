"""
bot.py — Main live/paper trading loop.

Usage:
    python bot.py              # paper trading (default from .env)
    python bot.py --live       # override to live
    python bot.py --backtest   # run walk-forward backtest and exit
    python bot.py --toggle-kill-switch  # flip kill switch and exit

MacBook resilience:
- Exponential backoff reconnect on network errors
- Graceful handling of lid-close (SIGTERM / KeyboardInterrupt)
- Rate-limited polling to avoid CPU/thermal spikes
"""

from __future__ import annotations

import argparse
import gzip
import json
import logging
import os
import shutil
import signal
import smtplib
import sqlite3
import sys
import time
from datetime import datetime, timezone, timedelta
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

import ccxt
import pandas as pd
import requests

import config
from agents import ConsensusEngine
from risk import RiskEngine
from strategy import RegimeDetector, TradingStrategy

# ─── Logging setup ────────────────────────────────────────────────────────────

Path(config.LOG_DIR).mkdir(parents=True, exist_ok=True)
Path("data").mkdir(parents=True, exist_ok=True)
Path("ops").mkdir(parents=True, exist_ok=True)
Path("backtest_results").mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(
            f"{config.LOG_DIR}/bot_{datetime.now().strftime('%Y%m%d')}.log",
            encoding="utf-8",
        ),
    ],
)
logger = logging.getLogger("bot")


# ─── Database ─────────────────────────────────────────────────────────────────

def init_db(db_path: str = config.DB_PATH):
    """Create trades and decisions tables if they don't exist yet."""
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS trades (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp    TEXT NOT NULL,
            entered_at   TEXT,
            signal       TEXT NOT NULL,
            regime       TEXT,
            entry_price  REAL,
            exit_price   REAL,
            size_usdt    REAL,
            pnl_usdt     REAL,
            pnl_pct      REAL,
            stop_loss    REAL,
            take_profit  REAL,
            confidence   REAL,
            mode         TEXT,
            notes        TEXT
        )
    """)
    try:
        conn.execute("ALTER TABLE trades ADD COLUMN entered_at TEXT")
        conn.commit()
    except sqlite3.OperationalError:
        pass  # column already exists
    conn.execute("""
        CREATE TABLE IF NOT EXISTS decisions (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp    TEXT NOT NULL,
            signal       TEXT,
            confidence   REAL,
            regime       TEXT,
            adx          REAL,
            agent_details TEXT,
            action_taken TEXT
        )
    """)
    conn.commit()
    conn.close()
    logger.info(f"Database ready: {db_path}")


def log_decision(conn, signal, confidence, regime_info, agent_signals, action):
    """Persist a consensus decision (including all agent details) to the decisions table."""
    agent_json = json.dumps([
        {"agent": a.agent, "signal": a.signal, "confidence": a.confidence, "reason": a.reason}
        for a in agent_signals
    ])
    conn.execute(
        "INSERT INTO decisions (timestamp, signal, confidence, regime, adx, agent_details, action_taken) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            datetime.now(timezone.utc).isoformat(),
            signal, confidence,
            regime_info.get("regime", ""),
            regime_info.get("adx", 0),
            agent_json,
            action,
        ),
    )
    conn.commit()


def log_trade(conn, trade_data: dict):
    """Persist a completed trade result to the trades table."""
    entered = trade_data.get("entered_at")
    entered_at_iso = entered.isoformat() if isinstance(entered, datetime) else (entered or "")
    conn.execute(
        "INSERT INTO trades (timestamp, entered_at, signal, regime, entry_price, exit_price, "
        "size_usdt, pnl_usdt, pnl_pct, stop_loss, take_profit, confidence, mode, notes) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            datetime.now(timezone.utc).isoformat(),
            entered_at_iso,
            trade_data.get("signal", ""),
            trade_data.get("regime", ""),
            trade_data.get("entry_price", 0),
            trade_data.get("exit_price", 0),
            trade_data.get("size_usdt", 0),
            trade_data.get("pnl_usdt", 0),
            trade_data.get("pnl_pct", 0),
            trade_data.get("stop_loss", 0),
            trade_data.get("take_profit", 0),
            trade_data.get("confidence", 0),
            config.TRADING_MODE,
            trade_data.get("notes", ""),
        ),
    )
    conn.commit()


# ─── Telegram notifications ───────────────────────────────────────────────────

def send_telegram(message: str):
    """Send a plain-text message to the configured Telegram chat. Silently no-ops if disabled or unconfigured."""
    if not config.TELEGRAM_ENABLED:
        return
    if not config.TELEGRAM_BOT_TOKEN or not config.TELEGRAM_CHAT_ID:
        return
    try:
        url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendMessage"
        requests.post(url, json={"chat_id": config.TELEGRAM_CHAT_ID, "text": message},
                      timeout=5)
    except Exception as e:
        logger.debug(f"Telegram send failed: {e}")


def send_telegram_file(file_path: str, caption: str = ""):
    """Send a file (e.g. compressed log) to Telegram chat as a document."""
    if not config.TELEGRAM_ENABLED or not config.TELEGRAM_BOT_TOKEN or not config.TELEGRAM_CHAT_ID:
        return False
    try:
        url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendDocument"
        with open(file_path, "rb") as f:
            resp = requests.post(
                url,
                data={"chat_id": config.TELEGRAM_CHAT_ID, "caption": caption},
                files={"document": (Path(file_path).name, f)},
                timeout=60,
            )
        return resp.ok
    except Exception as e:
        logger.warning(f"Telegram file send failed: {e}")
        return False


# ─── Log management ───────────────────────────────────────────────────────────

def compress_old_logs(log_dir: str = config.LOG_DIR) -> list[str]:
    """
    Gzip any plain .log files older than LOG_COMPRESS_AFTER_HOURS.
    Returns list of newly compressed file paths.
    """
    compressed = []
    cutoff = datetime.now() - timedelta(hours=config.LOG_COMPRESS_AFTER_HOURS)
    for log_file in Path(log_dir).glob("*.log"):
        mtime = datetime.fromtimestamp(log_file.stat().st_mtime)
        if mtime < cutoff:
            gz_path = log_file.with_suffix(".log.gz")
            with open(log_file, "rb") as f_in:
                with gzip.open(gz_path, "wb") as f_out:
                    shutil.copyfileobj(f_in, f_out)
            log_file.unlink()
            compressed.append(str(gz_path))
            logger.info(f"Compressed old log: {gz_path}")
    return compressed


def send_logs_email(subject: str = None, body: str = None) -> bool:
    """
    Email all compressed log files to EMAIL_RECIPIENT using Gmail SMTP.
    Requires EMAIL_ADDRESS and EMAIL_APP_PASSWORD in .env.
    Get a Gmail app password at: https://myaccount.google.com/apppasswords
    """
    if not config.EMAIL_ADDRESS or not config.EMAIL_APP_PASSWORD:
        logger.warning("EMAIL_ADDRESS or EMAIL_APP_PASSWORD not set — skipping email")
        return False

    log_files = (
        list(Path(config.LOG_DIR).glob("*.log.gz")) +
        list(Path(config.LOG_DIR).glob("*.log"))
    )
    if not log_files:
        logger.info("No log files to send")
        return False

    subject = subject or f"CryptoBot logs — {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    body    = body    or (
        f"Bot log bundle from AWS.\n"
        f"Files: {[f.name for f in log_files]}\n"
        f"Generated: {datetime.now(timezone.utc).isoformat()}"
    )

    msg = MIMEMultipart()
    msg["From"]    = config.EMAIL_ADDRESS
    msg["To"]      = config.EMAIL_RECIPIENT
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    for log_file in log_files:
        with open(log_file, "rb") as f:
            part = MIMEApplication(f.read(), Name=log_file.name)
        part["Content-Disposition"] = f'attachment; filename="{log_file.name}"'
        msg.attach(part)

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(config.EMAIL_ADDRESS, config.EMAIL_APP_PASSWORD)
            smtp.send_message(msg)
        logger.info(f"Logs emailed to {config.EMAIL_RECIPIENT} ({len(log_files)} files)")
        return True
    except Exception as e:
        logger.error(f"Email send failed: {e}")
        return False


def send_logs(via: str = "telegram") -> bool:
    """
    Compress old logs then send them.
    via: "telegram" | "email" | "both"
    """
    compress_old_logs()
    log_files = (
        list(Path(config.LOG_DIR).glob("*.log.gz")) +
        list(Path(config.LOG_DIR).glob("*.log"))
    )
    if not log_files:
        logger.info("No log files to send")
        return False

    success = False
    if via in ("telegram", "both"):
        for lf in log_files:
            ok = send_telegram_file(str(lf), caption=f"Bot log: {lf.name}")
            if ok:
                logger.info(f"Sent via Telegram: {lf.name}")
                success = True

    if via in ("email", "both"):
        success = send_logs_email() or success

    return success


# ─── Exchange connection with resilience ──────────────────────────────────────

def build_exchange(live: bool = False):
    """Instantiate and return the ccxt exchange object based on EXCHANGE config."""
    if config.EXCHANGE == "kucoin":
        params = {
            "apiKey":          config.KUCOIN_API_KEY,
            "secret":          config.KUCOIN_API_SECRET,
            "password":        config.KUCOIN_PASSPHRASE,
            "enableRateLimit": True,
            "options":         {"defaultType": "spot"},
        }
        logger.info("Exchange: KuCoin")
        return ccxt.kucoin(params)

    # Default: Binance
    params = {
        "apiKey":          config.BINANCE_API_KEY,
        "secret":          config.BINANCE_API_SECRET,
        "enableRateLimit": True,
        "options":         {"defaultType": "spot"},
    }
    if config.BINANCE_TESTNET:
        params["options"]["urls"] = {
            "api": {
                "public":  "https://testnet.binance.vision/api",
                "private": "https://testnet.binance.vision/api",
            }
        }
    logger.info("Exchange: Binance")
    return ccxt.binance(params)


def fetch_ohlcv_with_retry(exchange, symbol, timeframe, limit=300) -> pd.DataFrame | None:
    """Fetch OHLCV with exponential backoff on network errors."""
    attempt  = 0
    backoff  = 1.0
    max_att  = config.MAX_RECONNECT_ATTEMPTS

    while attempt < max_att:
        try:
            ohlcv = exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
            df    = pd.DataFrame(
                ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"]
            )
            df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
            df = df.set_index("timestamp")
            return df

        except (ccxt.NetworkError, ccxt.RequestTimeout, ccxt.ExchangeNotAvailable) as e:
            attempt += 1
            wait     = min(backoff * (config.RECONNECT_BACKOFF_BASE ** attempt),
                           config.RECONNECT_BACKOFF_MAX)
            logger.warning(f"Network error (attempt {attempt}/{max_att}): {e} — retry in {wait:.0f}s")
            time.sleep(wait)

        except ccxt.AuthenticationError as e:
            logger.error(f"Auth error — check API keys: {e}")
            return None

        except Exception as e:
            logger.error(f"Unexpected fetch error: {e}")
            attempt += 1
            time.sleep(min(backoff * attempt, 30))

    logger.error(f"Failed to fetch OHLCV after {max_att} attempts")
    return None


def fetch_balance_with_retry(exchange) -> float | None:
    """Fetch USDT balance with retry."""
    try:
        balance = exchange.fetch_balance()
        return balance["free"].get(config.BASE_CURRENCY, 0)
    except Exception as e:
        logger.warning(f"Balance fetch error: {e}")
        return None


# ─── Paper trading execution ──────────────────────────────────────────────────

class PaperTradingEngine:
    """Simulates order execution with realistic fees and slippage."""

    FEE      = 0.001   # 0.1% taker
    SLIPPAGE = 0.0005  # 0.05%

    def __init__(self, balance: float):
        self.balance   = balance
        self.in_trade  = False
        self.position: dict = {}

    def enter(self, signal: str, price: float, size_usdt: float, levels: dict, regime: str = "") -> dict:
        """Open a simulated position. Returns the position dict, or {} if already in a trade."""
        if self.in_trade:
            return {}

        # Apply entry slippage
        slip_factor  = (1 + self.SLIPPAGE) if signal == "BUY" else (1 - self.SLIPPAGE)
        actual_price = price * slip_factor
        fee_cost     = size_usdt * self.FEE

        self.in_trade = True
        self.position = {
            "signal":      signal,
            "regime":      regime,
            "entry_price": actual_price,
            "size_usdt":   size_usdt,
            "fee_paid":    fee_cost,
            "stop_loss":   levels["stop_loss"],
            "take_profit": levels["take_profit"],
            "entered_at":  datetime.now(timezone.utc),
        }
        self.balance -= fee_cost
        logger.info(
            f"[PAPER] ENTER {signal}: price={actual_price:.2f}, size=${size_usdt:.2f}, "
            f"SL={levels['stop_loss']:.2f}, TP={levels['take_profit']:.2f}"
        )
        return self.position

    def check_exit(self, high: float, low: float) -> dict | None:
        """Check if current candle hits SL or TP. Returns trade result or None."""
        if not self.in_trade:
            return None

        pos    = self.position
        signal = pos["signal"]
        ep     = pos["entry_price"]

        hit_tp = hit_sl = False
        exit_price = 0.0

        if signal == "BUY":
            if low <= pos["stop_loss"]:
                hit_sl     = True
                exit_price = pos["stop_loss"]
            elif high >= pos["take_profit"]:
                hit_tp     = True
                exit_price = pos["take_profit"]
        elif signal == "SELL":
            if high >= pos["stop_loss"]:
                hit_sl     = True
                exit_price = pos["stop_loss"]
            elif low <= pos["take_profit"]:
                hit_tp     = True
                exit_price = pos["take_profit"]

        if not (hit_tp or hit_sl):
            return None

        # Apply exit slippage
        slip_factor  = (1 - self.SLIPPAGE) if signal == "BUY" else (1 + self.SLIPPAGE)
        actual_exit  = exit_price * slip_factor
        exit_fee     = pos["size_usdt"] * self.FEE
        sign         = 1 if signal == "BUY" else -1
        gross_pnl    = sign * (actual_exit - ep) / ep * pos["size_usdt"]
        net_pnl      = gross_pnl - exit_fee - pos["fee_paid"]
        pnl_pct      = net_pnl / pos["size_usdt"] * 100

        self.balance += net_pnl
        self.in_trade = False

        result = {
            **pos,
            "exit_price": actual_exit,
            "exit_time":  datetime.now(timezone.utc),
            "pnl_usdt":   round(net_pnl, 4),
            "pnl_pct":    round(pnl_pct, 3),
            "exit_reason": "TP" if hit_tp else "SL",
        }
        logger.info(
            f"[PAPER] EXIT {signal}: entry={ep:.2f} exit={actual_exit:.2f} "
            f"PnL=${net_pnl:+.4f} ({pnl_pct:+.2f}%) [{result['exit_reason']}]"
        )
        return result

    def force_exit(self, price: float, reason: str = "FORCED") -> dict:
        """Exit the open position at a given price (e.g. regime flip)."""
        if not self.in_trade:
            return {}
        pos          = self.position
        signal       = pos["signal"]
        ep           = pos["entry_price"]
        slip_factor  = (1 - self.SLIPPAGE) if signal == "BUY" else (1 + self.SLIPPAGE)
        actual_exit  = price * slip_factor
        exit_fee     = pos["size_usdt"] * self.FEE
        sign         = 1 if signal == "BUY" else -1
        gross_pnl    = sign * (actual_exit - ep) / ep * pos["size_usdt"]
        net_pnl      = gross_pnl - exit_fee - pos["fee_paid"]
        pnl_pct      = net_pnl / pos["size_usdt"] * 100
        self.balance += net_pnl
        self.in_trade = False
        result = {
            **pos,
            "exit_price":  actual_exit,
            "exit_time":   datetime.now(timezone.utc),
            "pnl_usdt":    round(net_pnl, 4),
            "pnl_pct":     round(pnl_pct, 3),
            "exit_reason": reason,
        }
        logger.info(
            f"[PAPER] FORCE EXIT {signal}: entry={ep:.2f} exit={actual_exit:.2f} "
            f"PnL=${net_pnl:+.4f} ({pnl_pct:+.2f}%) [{reason}]"
        )
        return result


# ─── Main bot loop ────────────────────────────────────────────────────────────

class TradingBot:

    def __init__(self, live_override: bool = False):
        """Initialise exchange, risk engine, consensus engine, and paper trading state."""
        self.live       = live_override or (config.TRADING_MODE == "live")
        self.exchange   = build_exchange(self.live)
        self.risk       = RiskEngine()
        self.consensus  = ConsensusEngine()
        self.regime_det = RegimeDetector()
        self.strategy   = TradingStrategy()
        self.paper_eng: PaperTradingEngine | None = None
        self._running          = True
        self._last_heartbeat   = 0.0   # monotonic timestamp of last Telegram heartbeat
        self._bot_start        = time.monotonic()

        init_db()
        self.db = sqlite3.connect(config.DB_PATH, check_same_thread=False)

        if not self.live:
            self.paper_eng = PaperTradingEngine(config.STARTING_CAPITAL)

        mode_str = "LIVE" if self.live else "PAPER"
        logger.info(f"Bot initialised — mode={mode_str} pair={config.TRADING_PAIR}")
        send_telegram(
            f"Bot started [{mode_str}]\n"
            f"Pair: {config.TRADING_PAIR}\n"
            f"Capital: ${self.risk.current_balance:.2f}\n"
            f"Kill switch: {self.risk.kill_switch}"
        )

        # Graceful shutdown on SIGTERM (macOS lid-close / system events)
        signal.signal(signal.SIGTERM, self._handle_shutdown)
        signal.signal(signal.SIGINT,  self._handle_shutdown)

    def _handle_shutdown(self, signum, frame):
        logger.info(f"Shutdown signal received ({signum})")
        self._running = False

    def run(self):
        """Block and run the main trading loop until stopped or max errors reached."""
        logger.info("Starting main loop — press Ctrl+C to stop")
        consecutive_errors = 0
        last_log_compress  = datetime.now()

        while self._running:
            loop_start = time.monotonic()
            try:
                self._tick()
                consecutive_errors = 0
            except KeyboardInterrupt:
                break
            except Exception as e:
                consecutive_errors += 1
                logger.error(f"Loop error #{consecutive_errors}: {e}", exc_info=True)
                if consecutive_errors >= 5:
                    send_telegram(f"Bot error streak ({consecutive_errors}): {e}")
                if consecutive_errors >= config.MAX_RECONNECT_ATTEMPTS:
                    logger.critical("Too many consecutive errors — halting")
                    break

            # Hourly Telegram heartbeat — confirms server is still alive
            now_mono = time.monotonic()
            if now_mono - self._last_heartbeat >= 3600:
                uptime_h = int((now_mono - self._bot_start) / 3600)
                uptime_m = int((now_mono - self._bot_start) % 3600 / 60)
                send_telegram(
                    f"💓 Bot heartbeat — still running\n"
                    f"Uptime: {uptime_h}h {uptime_m}m\n"
                    f"Balance: ${self.risk.current_balance:.2f}\n"
                    f"Pair: {config.TRADING_PAIR} | Mode: {'LIVE' if self.live else 'PAPER'}"
                )
                self._last_heartbeat = now_mono

            # Daily: compress old logs to save AWS disk space
            if (datetime.now() - last_log_compress).total_seconds() > 86400:
                compress_old_logs()
                last_log_compress = datetime.now()

            # Rate-limited sleep: maintain ~60s cycle without busy-waiting
            elapsed = time.monotonic() - loop_start
            sleep   = max(0, config.DATA_UPDATE_INTERVAL - elapsed)
            if sleep > 0:
                time.sleep(sleep)

        logger.info("Bot stopped")
        send_telegram("Bot stopped")
        self.db.close()

    def _tick(self):
        """Single iteration of the trading loop."""
        symbol    = config.TRADING_PAIR
        timeframe = config.TIMEFRAME

        # 1. Fetch market data (1h primary + 4h for multi-timeframe confirmation)
        df = fetch_ohlcv_with_retry(self.exchange, symbol, timeframe, limit=300)
        if df is None or len(df) < config.MIN_CANDLES_REQUIRED:
            logger.warning(f"Insufficient data ({len(df) if df is not None else 0} bars)")
            return

        # 4h data is optional — if fetch fails we continue without MTF filter
        df_4h = fetch_ohlcv_with_retry(self.exchange, symbol, "4h", limit=100)

        close = df["close"].iloc[-1]
        high  = df["high"].iloc[-1]
        low   = df["low"].iloc[-1]

        # 2. Sync live balance
        if self.live:
            live_bal = fetch_balance_with_retry(self.exchange)
            if live_bal is not None:
                self.risk.update_balance(live_bal)
        else:
            if self.paper_eng:
                self.risk.update_balance(self.paper_eng.balance)

        balance = self.risk.current_balance

        # 3. Detect regime (needed before exit check for regime-flip logic)
        regime_info = self.regime_det.detect(df)
        regime      = regime_info["regime"]

        # 4. HMM regime — crash/bear force-exit longs; euphoria halves position size
        hmm_regime = regime_info.get("hmm_regime")
        if hmm_regime in ("crash", "bear"):
            if self.paper_eng and self.paper_eng.in_trade:
                exit_result = self.paper_eng.force_exit(close, f"HMM_{hmm_regime.upper()}")
                if exit_result:
                    self.risk.record_trade(exit_result["pnl_usdt"])
                    log_trade(self.db, exit_result)
                    send_telegram(
                        f"Position closed — HMM {hmm_regime.upper()} regime\n"
                        f"{exit_result['signal']} @ {exit_result['exit_price']:.2f}\n"
                        f"PnL: ${exit_result['pnl_usdt']:+.4f} ({exit_result['pnl_pct']:+.2f}%)\n"
                        f"{self.risk.summary()}"
                    )
            logger.info(
                f"[HMM] {hmm_regime.upper()} regime "
                f"(conf={regime_info.get('hmm_confidence', 0):.2f}) — no new entries"
            )
            return

        # 5. Check open paper trade for exit (regime flip or SL/TP)
        if self.paper_eng and self.paper_eng.in_trade:
            entry_regime = self.paper_eng.position.get("regime", "")
            if entry_regime and regime != entry_regime:
                exit_result = self.paper_eng.force_exit(close, "REGIME_FLIP")
            else:
                exit_result = self.paper_eng.check_exit(high, low)
            if exit_result:
                self.risk.record_trade(exit_result["pnl_usdt"])
                log_trade(self.db, exit_result)
                send_telegram(
                    f"Trade closed [{exit_result['exit_reason']}]\n"
                    f"{exit_result['signal']} @ {exit_result['exit_price']:.2f}\n"
                    f"PnL: ${exit_result['pnl_usdt']:+.4f} ({exit_result['pnl_pct']:+.2f}%)\n"
                    f"{self.risk.summary()}"
                )

        # 6. Skip entry if already in trade
        if (self.paper_eng and self.paper_eng.in_trade) or self.risk.kill_switch:
            return

        # 7. Run 4-agent consensus (+ MTF filter + ML filter)
        risk_state  = self.risk.state()
        signal, confidence, agent_sigs = self.consensus.decide(
            df, regime, risk_state, balance, close, df_4h=df_4h
        )

        # 8. Log decision
        hmm_label = f" HMM={hmm_regime}({regime_info.get('hmm_confidence', 0):.2f})" if hmm_regime else ""
        log_decision(self.db, signal, confidence, regime_info, agent_sigs, "enter" if signal != "HOLD" else "hold")
        logger.info(
            f"[TICK] price={close:.2f} regime={regime} ADX={regime_info['adx']}"
            f"{hmm_label} signal={signal} conf={confidence:.2f} | {self.risk.summary()}"
        )

        # 9. Execute if consensus says go and confidence is sufficient
        if signal in ("BUY", "SELL") and confidence >= 0.6:
            levels = self.strategy.compute_levels(df, signal, regime)
            # Euphoria: reduce position size by 50% — parabolic moves reverse violently
            size   = self.risk.position_size_usdt()
            if hmm_regime == "euphoria":
                size = size * 0.5
                logger.info(f"[HMM] EUPHORIA regime — position size halved to ${size:.2f}")

            if not self.live and self.paper_eng:
                self.paper_eng.enter(signal, close, size, levels, regime)
                send_telegram(
                    f"Trade entered [PAPER]\n"
                    f"{signal} @ {close:.2f}\n"
                    f"SL={levels['stop_loss']:.2f} TP={levels['take_profit']:.2f}\n"
                    f"Size=${size:.2f} | Conf={confidence:.2f}\n"
                    f"Regime={regime} ADX={regime_info['adx']}"
                )

            elif self.live:
                self._place_live_order(signal, close, size, levels)

    def _place_live_order(self, signal: str, price: float, size_usdt: float, levels: dict):
        """Place actual order on Binance. Only called when TRADING_MODE=live."""
        try:
            symbol    = config.TRADING_PAIR
            qty_coin  = size_usdt / price
            side      = "buy" if signal == "BUY" else "sell"

            order = self.exchange.create_market_order(symbol, side, qty_coin)
            logger.info(f"[LIVE] Order placed: {order}")
            send_telegram(
                f"LIVE ORDER PLACED\n"
                f"{signal} {qty_coin:.6f} BTC @ ~{price:.2f}\n"
                f"SL={levels['stop_loss']:.2f} TP={levels['take_profit']:.2f}\n"
                f"Order ID: {order.get('id', 'N/A')}"
            )
        except Exception as e:
            logger.error(f"Live order failed: {e}")
            send_telegram(f"LIVE ORDER FAILED: {e}")


# ─── CLI entry point ──────────────────────────────────────────────────────────

def main():
    """CLI entry point — parse arguments and dispatch to the appropriate mode."""
    parser = argparse.ArgumentParser(description="Crypto Survival System Trading Bot")
    parser.add_argument("--live",               action="store_true", help="Override to live trading")
    parser.add_argument("--backtest",           action="store_true", help="Run walk-forward backtest and exit")
    parser.add_argument("--backtest-days",      type=int, default=400, help="Days of history for backtest")
    parser.add_argument("--toggle-kill-switch", action="store_true", help="Toggle kill switch")
    parser.add_argument("--send-logs",          action="store_true", help="Compress and send logs, then exit")
    parser.add_argument("--send-logs-via",      default="telegram", choices=["telegram", "email", "both"],
                        help="Delivery method for --send-logs (default: telegram)")
    parser.add_argument("--train-filter",       action="store_true",
                        help="Run backtest, train ML signal filter, save to ops/signal_filter.pkl")
    parser.add_argument("--train-filter-days",  type=int, default=600,
                        help="Days of history for ML filter training (default: 600)")
    parser.add_argument("--train-hmm",          action="store_true",
                        help="Train HMM regime detector on historical data, save to ops/hmm_model.pkl")
    parser.add_argument("--train-hmm-days",     type=int, default=730,
                        help="Days of history for HMM training (default: 730)")
    args = parser.parse_args()

    if args.toggle_kill_switch:
        risk = RiskEngine()
        if risk.kill_switch:
            risk.disengage_kill_switch()
            print("Kill switch DISENGAGED")
        else:
            risk._engage_kill_switch("Manual activation via CLI")
            print("Kill switch ENGAGED")
        return

    if args.send_logs:
        ok = send_logs(via=args.send_logs_via)
        print(f"Logs sent: {ok}")
        return

    if args.train_filter:
        from backtest import WalkForwardBacktester
        from ml_filter import SignalFilter
        print(f"Training ML signal filter on {args.train_filter_days} days of data...")
        bt  = WalkForwardBacktester()
        df  = bt.fetch_historical(days=args.train_filter_days)
        res = bt.run(df)
        features_list, outcomes = bt.extract_training_data(res)
        sf = SignalFilter()
        ok = sf.train(features_list, outcomes)
        if ok:
            print(f"ML filter trained on {len(features_list)} trades — saved to ops/signal_filter.pkl")
        else:
            print("Training failed — see logs above for details")
        return

    if args.train_hmm:
        from backtest import WalkForwardBacktester
        from hmm_engine import HMMRegimeDetector
        print(f"Training HMM on {args.train_hmm_days} days of BTC/USDT 1h data …")
        bt  = WalkForwardBacktester()
        df  = bt.fetch_historical(days=args.train_hmm_days, timeframe="1h")
        hmm = HMMRegimeDetector()
        ok  = hmm.fit(df)
        if ok:
            hmm.save_model()
            print("HMM trained → ops/hmm_model.pkl")
            print("Generating regime chart …")
            hmm.plot_regimes(df, save_path="ops/hmm_regimes.png")
            print("Chart saved → ops/hmm_regimes.png")
        else:
            print("HMM training failed — see logs above")
        return

    if args.backtest:
        from backtest import WalkForwardBacktester
        bt  = WalkForwardBacktester()
        df  = bt.fetch_historical(days=args.backtest_days)
        res = bt.run(df)
        bt.save_results(res)
        return

    bot = TradingBot(live_override=args.live)
    bot.run()


if __name__ == "__main__":
    main()
