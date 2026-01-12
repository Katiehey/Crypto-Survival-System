"""
Configuration validation tests.
"""

import pytest
from config.system_config import RISK_LIMITS, SYSTEM_CONFIG, RiskLimits, SystemConfig


def test_risk_limits_exist():
    """Verify risk limits are instantiated."""
    assert RISK_LIMITS is not None
    assert isinstance(RISK_LIMITS, RiskLimits)


def test_risk_limits_are_sane():
    """Verify risk limits are within acceptable ranges."""
    # Max risk per trade should be very small
    assert RISK_LIMITS.MAX_RISK_PER_TRADE <= 0.01, "Risk per trade too high"
    assert RISK_LIMITS.MAX_RISK_PER_TRADE >= 0.001, "Risk per trade too low"
    
    # Daily loss should be small
    assert RISK_LIMITS.MAX_DAILY_LOSS <= 0.02, "Daily loss limit too high"
    
    # Trade limits
    assert RISK_LIMITS.MAX_TRADES_PER_DAY <= 5, "Too many trades per day"
    assert RISK_LIMITS.MAX_TRADES_PER_DAY >= 1, "Must allow at least 1 trade"
    
    # Drawdown kill switch
    assert RISK_LIMITS.MAX_DRAWDOWN_FROM_PEAK <= 0.10, "Drawdown limit too high"


def test_risk_limits_validation():
    """Test risk limits validation method."""
    is_valid, message = RISK_LIMITS.validate()
    assert is_valid, f"Risk limits validation failed: {message}"


def test_system_config_exists():
    """Verify system config is instantiated."""
    assert SYSTEM_CONFIG is not None
    assert isinstance(SYSTEM_CONFIG, SystemConfig)


def test_system_config_validation():
    """Test system config validation method."""
    is_valid, message = SYSTEM_CONFIG.validate()
    assert is_valid, f"System config validation failed: {message}"


def test_trading_pair_format():
    """Verify trading pair is in correct format."""
    assert '/' in SYSTEM_CONFIG.TRADING_PAIR, "Trading pair must contain '/'"
    base, quote = SYSTEM_CONFIG.TRADING_PAIR.split('/')
    assert len(base) >= 2, "Base currency too short"
    assert len(quote) >= 2, "Quote currency too short"


def test_capital_is_positive():
    """Verify starting capital is positive."""
    assert SYSTEM_CONFIG.STARTING_CAPITAL > 0, "Starting capital must be positive"


def test_trading_mode_is_valid():
    """Verify trading mode is either 'paper' or 'live'."""
    assert SYSTEM_CONFIG.TRADING_MODE in ['paper', 'live'], \
        f"Invalid trading mode: {SYSTEM_CONFIG.TRADING_MODE}"


def test_fee_structure():
    """Verify fee configuration is reasonable."""
    assert 0 <= SYSTEM_CONFIG.MAKER_FEE <= 0.01, "Maker fee out of range"
    assert 0 <= SYSTEM_CONFIG.TAKER_FEE <= 0.01, "Taker fee out of range"


def test_risk_limits_immutable():
    """Verify risk limits cannot be modified (frozen dataclass)."""
    with pytest.raises(Exception):  # FrozenInstanceError
        RISK_LIMITS.MAX_RISK_PER_TRADE = 0.1  # type: ignore


def test_system_config_immutable():
    """Verify system config cannot be modified (frozen dataclass)."""
    with pytest.raises(Exception):  # FrozenInstanceError
        SYSTEM_CONFIG.STARTING_CAPITAL = 10000  # type: ignore


if __name__ == "__main__":
    pytest.main([__file__, '-v'])