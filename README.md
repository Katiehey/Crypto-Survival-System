# Crypto Survival System

A lean, intelligent BTC/USDT trading bot with a 4-agent consensus decision system, adaptive regime detection, and walk-forward backtesting. Built for a MacBook running on a small ($27–$500) account.

---

## Architecture

```
config.py     — All settings loaded from .env
agents.py     — 4-agent consensus: Technical, Sentiment, Risk, Execution
strategy.py   — ADX regime detection + ATR-based trade levels
risk.py       — Position sizing, kill switch, daily loss tracking
backtest.py   — Walk-forward backtester (no lookahead bias)
bot.py        — Main loop (paper + live), DB logging, Telegram alerts
```

### How decisions are made

A trade only executes when **all 4 agents agree**:

| Agent | Role | Blocks on |
|---|---|---|
| **Technical** | RSI, MACD, Bollinger, EMA | No clear trend/reversal signal |
| **Sentiment** | RSS news headlines (free) | Strongly opposing market mood |
| **Risk** | Drawdown, daily loss, cooldown | Any risk limit breach |
| **Execution** | Fees, slippage, min order | Balance too low, execution unfeasible |

The regime (trending vs ranging) is detected via ADX:
- **ADX > 25** → Trending → EMA crossover + RSI momentum
- **ADX ≤ 25** → Ranging → Bollinger mean reversion

---

## Setup

### 1. Clone and create virtual environment

```bash
cd "Crypto-Survival-System"
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure `.env`

Edit `.env` with your Binance API keys and Telegram bot token. Key settings:

```
TRADING_MODE=paper          # Start here — never start with live
BINANCE_TESTNET=false       # Use real market data even in paper mode
STARTING_CAPITAL=500        # Your paper balance in USDT
TELEGRAM_ENABLED=true
```

### 3. Keep MacBook awake

```bash
# Terminal 1 — keep system awake (never sleeps while this runs)
caffeinate -dimsu &

# Or use Amphetamine (GUI) from the App Store
```

### 4. Run paper trading

```bash
python bot.py
```

### 5. Run walk-forward backtest (recommended before going live)

```bash
python bot.py --backtest --backtest-days 400
```

Results saved to `backtest_results/`.

### 6. Switch to live trading

Only after:
- Paper trading is profitable over ≥ 2 weeks
- Backtest shows Sharpe ≥ 1.0 and max drawdown < 15%

```bash
# In .env:
TRADING_MODE=live

# Or one-off override:
python bot.py --live
```

---

## Risk parameters (`.env`)

| Parameter | Default | Meaning |
|---|---|---|
| `MAX_RISK_PER_TRADE` | `0.005` | 0.5% of balance per trade (ignored if balance < $100 — uses $11 minimum) |
| `MAX_DAILY_LOSS` | `0.01` | 1% daily loss stops trading for the day |
| `MAX_DRAWDOWN_KILL_SWITCH` | `0.10` | 10% total drawdown engages kill switch |
| `MAX_CONSECUTIVE_LOSSES` | `2` | Triggers 15-minute cooldown |
| `MAX_TRADES_PER_DAY` | `2` | Hard cap on daily trades |
| `ATR_STOP_MULT` | `1.5` | Stop loss = entry ± 1.5×ATR |
| `ATR_TARGET_MULT` | `3.0` | Take profit = entry ± 3.0×ATR (2:1 R:R) |

---

## Kill switch

```bash
# Toggle on/off
python bot.py --toggle-kill-switch
```

The kill switch also auto-engages when drawdown exceeds `MAX_DRAWDOWN_KILL_SWITCH`. State is written to `ops/kill_switch.json`.

---

## MacBook resilience

- **WiFi flicker**: exponential backoff reconnect (up to 10 attempts, capped at 120s wait)
- **Lid close / SIGTERM**: graceful shutdown — writes final state, closes DB, sends Telegram alert
- **Thermal management**: polling is rate-limited to exactly one tick per `DATA_UPDATE_INTERVAL` (default 60s). No busy loops.

---

## Expert critique (5 roles)

### Strategy Expert
The ADX regime switch is the most important feature — using the wrong strategy for the regime is the #1 cause of losses for rule-based systems. Weakness: ADX lags; a fast regime change (flash crash → recovery) may mis-classify for several bars. **Mitigation**: the 15-minute cooldown and 2-trade daily cap limit exposure during volatile transitions.

### Risk Expert
The 10% kill switch is conservative for a $27 account (that's $2.70 max loss). With Binance's $11 minimum order, you have very few trades before hitting that limit. Consider raising `MAX_DRAWDOWN_KILL_SWITCH` to `0.20` for micro accounts, or widening daily loss to `0.03`. The current settings are appropriate for accounts over $200.

### Execution Expert
The 0.1% taker fee on Binance is correct. With $11 orders, fee = $0.011 per side = $0.022 round-trip. The 2:1 risk-reward (3×ATR TP vs 1.5×ATR SL) means you need a ~33% win rate to break even after fees. Actual win rates on trend-following systems in BTC are typically 40–55% — this is viable.

### Backtest Expert
Walk-forward testing avoids the most common overfitting trap (training and testing on the same data). Key risk: the in-sample window (1000 bars) is used only for context, not parameter optimization — meaning there is no actual fitting happening, which is honest but means you're not extracting maximum edge from the data. If you add parameter optimization later, always use the out-of-sample fold for evaluation.

### Security Expert
- API keys are in `.env` — never commit this file (it's in `.gitignore`)
- The bot requests **spot trading permissions only** — do not enable futures/margin on the API key
- The GitHub token (`Crypto_Survival_System_Token`) should have the minimum scopes needed (repo read/write, no org admin)
- Kill switch file is local — if the MacBook loses power mid-trade in live mode, the position stays open on Binance. Set a manual stop-loss order on Binance separately as a backstop.
- Live order placement has no confirmation step — this is by design for automation, but double-check `.env` `TRADING_MODE` before running `--live`.
