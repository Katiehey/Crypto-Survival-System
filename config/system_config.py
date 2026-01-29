"""
SYSTEM CONFIGURATION - SACRED RISK LIMITS

These parameters are the CORE SAFETY LAYER of the system.
Modifications require:
1. Written justification
2. Backtesting validation
3. Git commit with detailed explanation
4. Minimum 48-hour review period

DO NOT modify these values casually.
"""

from dataclasses import dataclass
from typing import Literal
import os
from dotenv import load_dotenv, find_dotenv

# Load environment variables
load_dotenv(find_dotenv(usecwd=True), override=True)


@dataclass(frozen=True)
class RiskLimits:
    """
    Hard risk constraints enforced at execution level.
    """
    
    # Per-Trade Limits
    MAX_RISK_PER_TRADE: float = 0.04
    MIN_RISK_PER_TRADE: float = 0.01 
    
    # Daily Limits
    MAX_DAILY_LOSS: float = 0.12
    MAX_TRADES_PER_DAY: int = 1  
    
    # Streak Protection
    MAX_CONSECUTIVE_LOSSES: int = 3
    # FIXED: Added the '=' sign missing in your snippet
    LOSS_STREAK_COOLDOWN_HOURS: int = 2
    
    # Kill Switch
    MAX_DRAWDOWN_FROM_PEAK: float = 0.85
    
    # --- THE CRITICAL FIX ---
    # Set to 40% (R200) to safely clear the ~$10 (R180) exchange minimum
    MAX_POSITION_SIZE_PERCENT: float = 0.95
    
    def validate(self) -> tuple[bool, str]:
        """Validate that risk limits are sane for a small ZAR account."""
        if self.MAX_RISK_PER_TRADE > 0.05:
            return False, "MAX_RISK_PER_TRADE is too high for survival"
        
        # Position cap must be high enough to allow R180+ trades
        if self.MAX_POSITION_SIZE_PERCENT < 0.10:
            return False, "Position cap too low for exchange minimums (R180+)"
        
        return True, "All risk limits valid"

@dataclass(frozen=True)
class SystemConfig:
    """
    Core system operational parameters.
    
    These define how the system operates but are less critical
    than RiskLimits.
    """
    DB_PATH: str = os.getenv('DB_PATH', 'trading.db') 
    
    # Exchange
    EXCHANGE: str = "binance"
    TRADING_PAIR: str = os.getenv('TRADING_PAIR', 'BTC/USDT')
    BASE_CURRENCY: str = os.getenv('BASE_CURRENCY', 'USDT')
    
    # Capital
    STARTING_CAPITAL: float = float(os.getenv('STARTING_CAPITAL', '500'))
    
    # Timeframes
    PRIMARY_TIMEFRAME: str = "1h"
    SECONDARY_TIMEFRAME: str = "5m"
    
    # Data Requirements
    MIN_CANDLES_REQUIRED: int = int(os.getenv('MIN_CANDLES_REQUIRED', '100'))
    LOOKBACK_PERIODS: int = 200
    
    # Execution
    ORDER_TYPE: Literal["market", "limit"] = "limit"
    SLIPPAGE_TOLERANCE: float = 0.001  # 0.1%
    
    # Fees (Binance spot trading with BNB discount)
    MAKER_FEE: float = 0.00075  # 0.075%
    TAKER_FEE: float = 0.00075  # 0.075%
    
    # Data Update
    DATA_UPDATE_INTERVAL_MINUTES: int = int(os.getenv('DATA_UPDATE_INTERVAL', '60'))
    
    # Mode
    TRADING_MODE: Literal["paper", "live"] = os.getenv('TRADING_MODE', 'paper')  # type: ignore
    USE_TESTNET: bool = os.getenv('BINANCE_TESTNET', 'true').lower() == 'true'
    
    def validate(self) -> tuple[bool, str]:
        """
        Validate system configuration.
        
        Returns:
            (is_valid, error_message)
        """
        if self.STARTING_CAPITAL < 100:
            return False, "STARTING_CAPITAL must be at least 100 USDT"
        
        if self.MIN_CANDLES_REQUIRED < 50:
            return False, "MIN_CANDLES_REQUIRED must be at least 50"
        
        if self.TRADING_MODE not in ['paper', 'live']:
            return False, "TRADING_MODE must be 'paper' or 'live'"
        
        if '/' not in self.TRADING_PAIR:
            return False, "TRADING_PAIR must be in format 'BASE/QUOTE'"
        
        return True, "System config valid"


# Instantiate as module-level constants
RISK_LIMITS = RiskLimits()
SYSTEM_CONFIG = SystemConfig()


def validate_all_config() -> None:
    """
    Validate all configuration on module import.
    Raises ValueError if any config is invalid.
    """
    risk_valid, risk_msg = RISK_LIMITS.validate()
    if not risk_valid:
        raise ValueError(f"Risk limits validation failed: {risk_msg}")
    
    system_valid, system_msg = SYSTEM_CONFIG.validate()
    if not system_valid:
        raise ValueError(f"System config validation failed: {system_msg}")


# Run validation on import
validate_all_config()


if __name__ == "__main__":
    # For testing config directly
    print("=" * 60)
    print("RISK LIMITS")
    print("=" * 60)
    print(f"Max risk per trade: {RISK_LIMITS.MAX_RISK_PER_TRADE * 100:.2f}%")
    print(f"Max daily loss: {RISK_LIMITS.MAX_DAILY_LOSS * 100:.2f}%")
    print(f"Max trades/day: {RISK_LIMITS.MAX_TRADES_PER_DAY}")
    print(f"Max consecutive losses: {RISK_LIMITS.MAX_CONSECUTIVE_LOSSES}")
    print(f"Kill switch drawdown: {RISK_LIMITS.MAX_DRAWDOWN_FROM_PEAK * 100:.1f}%")
    
    print("\n" + "=" * 60)
    print("SYSTEM CONFIG")
    print("=" * 60)
    print(f"Exchange: {SYSTEM_CONFIG.EXCHANGE}")
    print(f"Trading pair: {SYSTEM_CONFIG.TRADING_PAIR}")
    print(f"Starting capital: {SYSTEM_CONFIG.STARTING_CAPITAL} {SYSTEM_CONFIG.BASE_CURRENCY}")
    print(f"Trading mode: {SYSTEM_CONFIG.TRADING_MODE}")
    print(f"Testnet: {SYSTEM_CONFIG.USE_TESTNET}")
    print(f"Primary timeframe: {SYSTEM_CONFIG.PRIMARY_TIMEFRAME}")
    
    print("\n✅ All configuration valid")