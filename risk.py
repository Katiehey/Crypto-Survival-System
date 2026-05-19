"""
risk.py — Position sizing, kill switch, and runtime risk state management.

Handles:
- Position size calculation (using Binance minimum for small accounts)
- Kill switch (file-based for manual override + drawdown-triggered)
- Daily reset logic
- Cooldown tracking
"""

import json
import logging
import os
from datetime import datetime, timezone, date
from pathlib import Path

import config

logger = logging.getLogger(__name__)


class RiskEngine:
    """
    Central risk state. Lives in memory during a session; persists to DB on trade events.
    """

    def __init__(self, starting_balance: float = None):
        bal = starting_balance or config.STARTING_CAPITAL
        self.peak_balance        = bal
        self.current_balance     = bal
        self.daily_start_balance = bal
        self._daily_date         = date.today()
        self.consecutive_losses  = 0
        self.trades_today        = 0
        self.last_loss_time: datetime | None = None
        self.kill_switch         = self._load_kill_switch()

    # ─── State snapshot for agents ───────────────────────────────────────────

    def state(self) -> dict:
        self._maybe_daily_reset()
        return {
            "peak_balance":        self.peak_balance,
            "current_balance":     self.current_balance,
            "daily_start_balance": self.daily_start_balance,
            "consecutive_losses":  self.consecutive_losses,
            "trades_today":        self.trades_today,
            "last_loss_time":      self.last_loss_time,
            "kill_switch":         self.kill_switch,
        }

    # ─── Position sizing ──────────────────────────────────────────────────────

    def position_size_usdt(self) -> float:
        """
        For small accounts (<$100): always use Binance minimum order (~$11).
        For larger accounts: use MAX_RISK_PER_TRADE % of balance.
        """
        risk_based = self.current_balance * config.MAX_RISK_PER_TRADE
        if self.current_balance < 100:
            size = config.MIN_ORDER_USDT
        else:
            size = max(risk_based, config.MIN_ORDER_USDT)
        size = round(min(size, self.current_balance * 0.95), 2)
        pct_of_balance = size / self.current_balance if self.current_balance > 0 else 0
        if pct_of_balance > 0.15:
            logger.warning(
                f"Position size ${size:.2f} is {pct_of_balance:.0%} of balance "
                f"${self.current_balance:.2f} — Binance minimum forces outsized risk "
                f"(target was {config.MAX_RISK_PER_TRADE:.1%})"
            )
        return size

    # ─── Trade result recording ───────────────────────────────────────────────

    def record_trade(self, pnl_usdt: float):
        """Call after every closed trade with the net PnL (positive = profit)."""
        self.current_balance += pnl_usdt
        self.peak_balance     = max(self.peak_balance, self.current_balance)
        self.trades_today    += 1

        if pnl_usdt < 0:
            self.consecutive_losses += 1
            self.last_loss_time      = datetime.now(timezone.utc)
            logger.info(f"Loss recorded: ${pnl_usdt:.2f} | consecutive={self.consecutive_losses}")
        else:
            self.consecutive_losses = 0
            logger.info(f"Win recorded:  ${pnl_usdt:.2f} | balance=${self.current_balance:.2f}")

        # Auto-trigger kill switch on excessive drawdown
        drawdown = (self.peak_balance - self.current_balance) / self.peak_balance
        if drawdown >= config.MAX_DRAWDOWN_KILL_SWITCH:
            self._engage_kill_switch(
                f"Drawdown {drawdown:.1%} exceeded {config.MAX_DRAWDOWN_KILL_SWITCH:.0%} threshold"
            )

    def update_balance(self, new_balance: float):
        """Sync balance from exchange (live mode)."""
        self.current_balance = new_balance
        self.peak_balance    = max(self.peak_balance, new_balance)

    # ─── Kill switch ──────────────────────────────────────────────────────────

    def _engage_kill_switch(self, reason: str):
        self.kill_switch = True
        Path(config.KILL_SWITCH_FILE).parent.mkdir(parents=True, exist_ok=True)
        with open(config.KILL_SWITCH_FILE, "w") as f:
            json.dump({
                "active":    True,
                "reason":    reason,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }, f, indent=2)
        logger.critical(f"KILL SWITCH ENGAGED: {reason}")

    def disengage_kill_switch(self):
        """Manual reset — called from ops or toggle script."""
        self.kill_switch = False
        if os.path.exists(config.KILL_SWITCH_FILE):
            with open(config.KILL_SWITCH_FILE, "w") as f:
                json.dump({"active": False, "reason": "manually reset"}, f)
        logger.warning("Kill switch disengaged manually")

    def _load_kill_switch(self) -> bool:
        try:
            if os.path.exists(config.KILL_SWITCH_FILE):
                with open(config.KILL_SWITCH_FILE) as f:
                    data = json.load(f)
                return data.get("active", False)
        except Exception:
            pass
        return False

    # ─── Daily reset ──────────────────────────────────────────────────────────

    def _maybe_daily_reset(self):
        today = date.today()
        if today != self._daily_date:
            self._daily_date         = today
            self.daily_start_balance = self.current_balance
            self.trades_today        = 0
            logger.info(f"Daily reset: start balance=${self.current_balance:.2f}")

    # ─── Diagnostics ──────────────────────────────────────────────────────────

    def summary(self) -> str:
        drawdown = (self.peak_balance - self.current_balance) / self.peak_balance
        daily_pnl = self.current_balance - self.daily_start_balance
        return (
            f"Balance=${self.current_balance:.2f} | Peak=${self.peak_balance:.2f} | "
            f"Drawdown={drawdown:.1%} | DailyPnL=${daily_pnl:+.2f} | "
            f"Trades={self.trades_today}/{config.MAX_TRADES_PER_DAY} | "
            f"ConsecLoss={self.consecutive_losses} | KillSwitch={self.kill_switch}"
        )
