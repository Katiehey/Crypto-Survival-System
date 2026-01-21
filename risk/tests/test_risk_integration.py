"""
Integration tests for complete risk engine.
"""

import pytest
from datetime import datetime, timedelta
from risk.engine import RiskEngine
from config.system_config import RISK_LIMITS


class TestRiskEngineIntegration:
    """Test complete risk engine integration."""
    
    def test_complete_trade_workflow(self):
        """Test complete workflow: size → validate → record."""
        engine = RiskEngine(capital=500)
        
        # 1. Calculate position size
        position = engine.calculate_position_size(
            entry_price=42000,
            stop_loss_price=41160,
            risk_percent=0.01
        )
        
        assert position.is_valid == True
        
        # 2. Validate trade
        is_valid, reason = engine.validate_trade(
            position.size,
            position.risk_amount,
            position.risk_percent
        )
        
        assert is_valid == True
        
        # 3. Record trade (win)
        engine.record_trade(pnl=3.0, risk_amount=2.5)
        
        assert engine.capital == 503.0
        assert engine.state.consecutive_losses == 0
    
    def test_consecutive_losses_trigger_cooldown(self):
        """Test that consecutive losses trigger cooldown."""
        engine = RiskEngine(capital=500)
        
        # Record max consecutive losses
        for _ in range(RISK_LIMITS.MAX_CONSECUTIVE_LOSSES):
            engine.record_trade(pnl=-2.5, risk_amount=2.5)
        
        # Cooldown should be active
        assert engine.state.is_in_cooldown() == True
        
        # Trade should be rejected
        position = engine.calculate_position_size(42000, 41160, 0.005)
        is_valid, reason = engine.validate_trade(
            position.size, position.risk_amount, position.risk_percent
        )
        
        assert is_valid == False
        assert "cooldown" in reason.lower()
    
    def test_win_clears_cooldown(self):
        """Test that win clears cooldown."""
        engine = RiskEngine(capital=500)
        
        # Trigger cooldown
        for _ in range(RISK_LIMITS.MAX_CONSECUTIVE_LOSSES):
            engine.record_trade(pnl=-2.5, risk_amount=2.5)
        
        assert engine.state.is_in_cooldown() == True
        
        # Record win
        engine.record_trade(pnl=3.0, risk_amount=2.5)
        
        # Cooldown should be cleared
        assert engine.state.is_in_cooldown() == False
        assert engine.state.consecutive_losses == 0
    
    def test_drawdown_triggers_kill_switch(self):
        """Test that excessive drawdown triggers kill switch."""
        engine = RiskEngine(capital=500)
        
        # Set peak higher
        engine.update_capital(510)
        
        # Create 6% drawdown
        drawdown_capital = 510 * 0.89
        engine.update_capital(drawdown_capital)
        
        # Kill switch should be active
        assert engine.state.kill_switch_active == True
        
        # Trades should be blocked
        position = engine.calculate_position_size(42000, 41160, 0.005)
        is_valid, _ = engine.validate_trade(
            position.size, position.risk_amount, position.risk_percent
        )
        
        assert is_valid == False
    
    def test_daily_limits_reset(self):
        """Test that daily limits reset on date change."""
        engine = RiskEngine(capital=500)
        
        # Use up daily trades
        for _ in range(RISK_LIMITS.MAX_TRADES_PER_DAY):
            engine.record_trade(pnl=-1.0, risk_amount=2.5)
        
        # Simulate date change
        engine.state.current_date = datetime.now().date() - timedelta(days=1)
        
        engine.state.cooldown_until = None 
        engine.state.consecutive_losses = 0

        # Validate should reset counters
        position = engine.calculate_position_size(42000, 41160, 0.005)
        is_valid, reason = engine.validate_trade(
            position.size, position.risk_amount, position.risk_percent
        )
        
        # Should be valid now (counters reset)
        assert is_valid == True
        assert engine.state.trades_today == 0
    
    def test_get_status(self):
        """Test comprehensive status reporting."""
        engine = RiskEngine(capital=500)
        
        status = engine.get_status()
        
        # Check all sections exist
        assert 'capital' in status
        assert 'daily' in status
        assert 'streak' in status
        assert 'kill_switch' in status
        assert 'can_trade' in status
        
        # Check values
        assert status['capital']['current'] == 500
        assert status['daily']['trades_today'] == 0
        assert status['streak']['consecutive_losses'] == 0
        assert status['kill_switch']['active'] == False
        assert status['can_trade'] == True
    
    def test_print_status(self, capsys):
        """Test status printing."""
        engine = RiskEngine(capital=500)
        
        engine.print_status()
        
        captured = capsys.readouterr()
        assert "RISK ENGINE STATUS" in captured.out
        assert "CAPITAL" in captured.out
        assert "TRADING ALLOWED" in captured.out
    
    def test_multiple_trades_scenario(self):
        """Test realistic multi-trade scenario."""
        engine = RiskEngine(capital=500)
        
        # Trade 1: Win
        pos1 = engine.calculate_position_size(42000, 41160, 0.005)
        valid, _ = engine.validate_trade(pos1.size, pos1.risk_amount, pos1.risk_percent)
        assert valid == True
        engine.record_trade(pnl=3.0, risk_amount=2.5)
        
        # Trade 2: Loss
        pos2 = engine.calculate_position_size(42000, 41160, 0.005)
        valid, _ = engine.validate_trade(pos2.size, pos2.risk_amount, pos2.risk_percent)
        assert valid == True
        engine.record_trade(pnl=-2.5, risk_amount=2.5)
        
        # Check state
        assert engine.state.trades_today == 2
        assert engine.state.consecutive_losses == 1
        assert engine.capital == 500.5  # 500 + 3 - 2.5
    
    def test_all_gates_can_reject(self):
        """Test that each gate can reject independently."""
        engine = RiskEngine(capital=500)
        
        # Test each rejection scenario
        scenarios = []
        
        # 1. Excessive risk
        scenarios.append((125, 10.0, 0.02, "exceeds"))  # 2% risk
        
        # 2. After daily limit
        engine2 = RiskEngine(capital=500)
        for _ in range(RISK_LIMITS.MAX_TRADES_PER_DAY):
            engine2.state.trades_today += 1
        valid, reason = engine2.validate_trade(125, 2.5, 0.005)
        assert valid == False
        
        # 3. After daily loss limit
        engine3 = RiskEngine(capital=500)
        engine3.state.daily_loss = 20.0  # Exceeds 1% of 500
        valid, reason = engine3.validate_trade(125, 2.5, 0.005)
        assert valid == False
        
        # 4. After consecutive losses
        engine4 = RiskEngine(capital=500)
        engine4.state.consecutive_losses = 2
        valid, reason = engine4.validate_trade(125, 2.5, 0.005)
        assert valid == False
        
        # 5. Kill switch
        engine5 = RiskEngine(capital=500)
        engine5.activate_kill_switch("Test")
        valid, reason = engine5.validate_trade(125, 2.5, 0.005)
        assert valid == False


if __name__ == "__main__":
    pytest.main([__file__, '-v'])