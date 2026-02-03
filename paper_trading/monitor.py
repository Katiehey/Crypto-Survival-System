# paper_trading/monitor.py
"""
Monitoring system for paper trading.
Provides real-time monitoring, alerts, and dashboard data.
"""

import time
import threading
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)

class AlertLevel(Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    ERROR = "error"

@dataclass
class Alert:
    level: AlertLevel
    message: str
    timestamp: datetime
    source: str
    data: Optional[Dict] = None
    
    def __str__(self):
        level_symbols = {
            AlertLevel.INFO: "ℹ️",
            AlertLevel.WARNING: "⚠️",
            AlertLevel.CRITICAL: "🚨",
            AlertLevel.ERROR: "❌"
        }
        symbol = level_symbols.get(self.level, "📝")
        return f"{symbol} [{self.timestamp.strftime('%H:%M:%S')}] {self.message}"

class PaperTradingMonitor:
    def __init__(self, paper_trading_system, update_interval: int = 5):
        self.system = paper_trading_system
        self.update_interval = update_interval
        self.lock = threading.Lock() # Ensures thread safety
        
        self.is_monitoring = False
        self.monitor_thread = None
        self.start_time = None
        
        self.metrics_history = []
        self.alerts = []
        self.performance_snapshots = []
        
        # Throttling to prevent alert spam (stores last alert time per message)
        self._last_alert_time = {}

        self.thresholds = {
            'drawdown_warning': 5.0,
            'drawdown_critical': 10.0,
            'position_size_warning': 0.2,
            'consecutive_losses_warning': 3,
        }
        
        logger.info("Guardian AI: Monitor initialized for Crypto-Survival-System")

    def start(self):
        if self.is_monitoring:
            return
        self.is_monitoring = True
        self.start_time = datetime.now()
        self.monitor_thread = threading.Thread(target=self._monitoring_loop, daemon=True)
        self.monitor_thread.start()
        logger.info("✅ Monitoring started")

    def stop(self):
        self.is_monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
        logger.info("✅ Monitoring stopped")

    def _monitoring_loop(self):
        while self.is_monitoring:
            try:
                metrics = self._collect_metrics()
                
                with self.lock:
                    self.metrics_history.append(metrics)
                    self._check_alerts(metrics)
                    
                    # Hourly Snapshot Logic
                    now = datetime.now()
                    if not self.performance_snapshots or \
                       (now - self.performance_snapshots[-1]['timestamp']).total_seconds() >= 3600:
                        self.performance_snapshots.append({
                            'timestamp': now,
                            'metrics': metrics
                        })

                    # Keep memory usage lean
                    if len(self.metrics_history) > 5000:
                        self.metrics_history = self.metrics_history[-2500:]

                time.sleep(self.update_interval)
            except Exception as e:
                logger.error(f"❌ Monitor Error: {e}")
                time.sleep(self.update_interval)

    def _collect_metrics(self) -> Dict:
        """Aggregates real-time data from the system."""
        sys = self.system
        
        # Safe PnL calculation
        closed = sys.closed_trades
        total_pnl = sum(t.get('pnl', 0) for t in closed)
        wins = [t for t in closed if t.get('pnl', 0) > 0]
        losses = [t for t in closed if t.get('pnl', 0) <= 0]

        metrics = {
            'timestamp': datetime.now(),
            'current_capital': sys.current_capital,
            'open_positions_count': len(sys.open_positions),
            'win_rate': (len(wins) / len(closed) * 100) if closed else 0,
            'total_pnl': total_pnl,
            'drawdown': self._calculate_drawdown(),
            'positions': [
                {
                    'symbol': p.symbol,
                    'side': p.side,
                    'unrealized_pnl': getattr(p, 'current_pnl', 0)
                } for p in sys.open_positions
            ]
        }
        return metrics

    def _calculate_drawdown(self) -> float:
        if not self.system.equity_history:
            return 0.0
        equity_values = [h['capital'] for h in self.system.equity_history]
        peak = max(equity_values)
        return ((peak - self.system.current_capital) / peak * 100) if peak > 0 else 0

    def add_alert(self, level: AlertLevel, message: str, source: str):
        # basic anti-spam: don't repeat same alert within 1 minute
        now = datetime.now()
        if message in self._last_alert_time and (now - self._last_alert_time[message]).total_seconds() < 60:
            return

        alert = Alert(level, message, now, source)
        self.alerts.append(alert)
        self._last_alert_time[message] = now
        logger.warning(str(alert))

    def _check_alerts(self, metrics: Dict):
        if metrics['drawdown'] > self.thresholds['drawdown_critical']:
            self.add_alert(AlertLevel.CRITICAL, f"Critical Drawdown: {metrics['drawdown']:.2f}%", "risk_engine")
        elif metrics['drawdown'] > self.thresholds['drawdown_warning']:
            self.add_alert(AlertLevel.WARNING, f"Significant Drawdown: {metrics['drawdown']:.2f}%", "risk_engine")