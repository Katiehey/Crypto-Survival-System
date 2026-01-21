"""
Tests for trade validation and risk gates.
"""

import pytest
from datetime import datetime, date, timedelta
from risk.engine import RiskEngine


class TestTradeValidation:
    """Test trade validation logic."""
    
    def test_valid_trade_passes(self):
        """Test that valid trade passes all gates."""
        engine = RiskEngine(capital=500)
        
        is_valid, reason = engine.validate_trade(
            position_size=125,
            risk_amount=2.5,
            risk_percent=0.005
        )
        
        assert is_valid == True
        assert "approved" in reason.lower()
    
    def test_excessive_risk_rejected(self):
        """Test that excessive risk is rejected."""
        engine = RiskEngine(capital=500)
        
        is_valid, reason = engine.validate_trade(
            position_size=500,
            risk_amount=10.0,  # 2% risk (too high)
            risk_percent=0.02
        )
        
        assert is_valid == False
        assert "exceeds" in reason.lower()
    
    def test_daily_trade_limit(self):
        """Test daily trade limit enforcement."""
        from config.system_config import RISK_LIMITS
        
        engine = RiskEngine(capital=500)
        
        # Execute max trades
        for _ in range(RISK_LIMITS.MAX_TRADES_PER_DAY):
            engine.record_trade(pnl=1.0, risk_amount=2.5)
        
        # Next trade should be rejected
        is_valid, reason = engine.validate_trade(
            position_size=125,
            risk_amount=2.5,
            risk_percent=0.005
        )
        
        assert is_valid == False
        assert "trade limit" in reason.lower()
    
    def test_daily_loss_limit(self):
        """Test daily loss limit enforcement."""
        engine = RiskEngine(capital=500)
        
        # Record a loss (R3.00) -> Consecutive losses: 1
        engine.record_trade(pnl=10.0, risk_amount=5.0)
        
        # Record a WIN (R0.10) -> This resets consecutive losses to 0 
        # but keeps our daily loss at R2.90
        engine.record_trade(pnl=-20.0, risk_amount=5.0)
        
        # Next trade should be rejected by Gate 4 (Daily Loss)
        is_valid, reason = engine.validate_trade(
        position_size=100,
        risk_amount=2.5,
        risk_percent=0.005
    )
        
        assert is_valid == False
        assert "daily loss" in reason.lower()
    
    def test_consecutive_loss_limit(self):
        """Test consecutive loss limit enforcement."""
        from config.system_config import RISK_LIMITS
        
        engine = RiskEngine(capital=500)
        
        # Record consecutive losses
        for _ in range(RISK_LIMITS.MAX_CONSECUTIVE_LOSSES):
            engine.record_trade(pnl=-2.5, risk_amount=2.5)
        
        # Next trade should be rejected
        is_valid, reason = engine.validate_trade(
            position_size=125,
            risk_amount=2.5,
            risk_percent=0.005
        )
        
        assert is_valid == False
        assert any(word in reason.lower() for word in ["consecutive", "cooldown"])
    
    def test_consecutive_losses_reset_on_win(self):
        """Test that win resets consecutive losses."""
        engine = RiskEngine(capital=500)
        
        # Record losses
        engine.record_trade(pnl=-2.5, risk_amount=2.5)
        assert engine.state.consecutive_losses == 1
        
        # Record win
        engine.record_trade(pnl=3.0, risk_amount=2.5)
        assert engine.state.consecutive_losses == 0
    
    def test_kill_switch_blocks_trades(self):
        """Test that kill switch blocks all trades."""
        engine = RiskEngine(capital=500)
        
        engine.activate_kill_switch("Test")
        
        is_valid, reason = engine.validate_trade(
            position_size=125,
            risk_amount=2.5,
            risk_percent=0.005
        )
        
        assert is_valid == False
        assert "kill switch" in reason.lower()
    
    def test_kill_switch_can_be_deactivated(self):
        """Test kill switch deactivation."""
        engine = RiskEngine(capital=500)
        
        engine.activate_kill_switch("Test")
        assert engine.state.kill_switch_active == True
        
        engine.deactivate_kill_switch()
        assert engine.state.kill_switch_active == False
        
        # Trade should now be allowed
        is_valid, _ = engine.validate_trade(
            position_size=125,
            risk_amount=2.5,
            risk_percent=0.005
        )
        assert is_valid == True
    
    def test_daily_counters_reset(self):
        """Test that daily counters reset at midnight."""
        engine = RiskEngine(capital=500)
        
        # Record trades
        engine.record_trade(pnl=-2.5, risk_amount=2.5)
        engine.record_trade(pnl=-2.0, risk_amount=2.5)
        
        assert engine.state.trades_today == 2
        assert engine.state.daily_loss == 4.5
        
        # Simulate date change
        engine.state.current_date = date.today() - timedelta(days=1)
        
        # Next validation should reset counters
        engine.validate_trade(125, 2.5, 0.005)
        
        assert engine.state.trades_today == 0
        assert engine.state.daily_loss == 0.0
    
    def test_zero_position_size_rejected(self):
        """Test that zero position size is rejected."""
        engine = RiskEngine(capital=500)
        
        is_valid, reason = engine.validate_trade(
            position_size=0,
            risk_amount=0,
            risk_percent=0.005
        )
        
        assert is_valid == False
        assert "positive" in reason.lower()
    
    def test_risk_exceeds_capital_rejected(self):
        """Test that risk > capital is rejected."""
        engine = RiskEngine(capital=500)
        
        is_valid, reason = engine.validate_trade(
            position_size=1000,
            risk_amount=600,  # More than capital!
            risk_percent=1.2
        )
        
        assert is_valid == False


class TestTradeRecording:
    """Test trade recording and state updates."""
    
    def test_record_loss(self):
        """Test recording a losing trade."""
        engine = RiskEngine(capital=500)
        
        engine.record_trade(pnl=-2.5, risk_amount=2.5)
        
        assert engine.state.trades_today == 1
        assert engine.state.daily_loss == 2.5
        assert engine.state.consecutive_losses == 1
        assert engine.state.last_trade_result == 'loss'
        assert engine.capital == 497.5
    
    def test_record_win(self):
        """Test recording a winning trade."""
        engine = RiskEngine(capital=500)
        
        engine.record_trade(pnl=3.0, risk_amount=2.5)
        
        assert engine.state.trades_today == 1
        assert engine.state.daily_loss == 0.0
        assert engine.state.consecutive_losses == 0
        assert engine.state.last_trade_result == 'win'
        assert engine.capital == 503.0
    
    def test_consecutive_loss_reset(self):
        """Test manual consecutive loss reset."""
        engine = RiskEngine(capital=500)
        
        engine.record_trade(pnl=-2.5, risk_amount=2.5)
        engine.record_trade(pnl=-2.5, risk_amount=2.5)
        
        assert engine.state.consecutive_losses == 2
        
        engine.reset_consecutive_losses()
        
        assert engine.state.consecutive_losses == 0


if __name__ == "__main__":
    pytest.main([__file__, '-v'])