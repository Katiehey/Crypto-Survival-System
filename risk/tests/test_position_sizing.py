"""
Tests for position sizing calculations.
These tests verify mathematical correctness with known values.
"""

import pytest
from risk.engine import RiskEngine, PositionSize

class TestPositionSizing:
    """Test position sizing calculations."""
    
    def test_risk_engine_initialization(self):
        """Test risk engine can be initialized."""
        engine = RiskEngine(capital=500)
        assert engine.capital == 500
    
    def test_initialization_invalid_capital(self):
        """Test initialization rejects invalid capital."""
        with pytest.raises(ValueError):
            RiskEngine(capital=0)
        
        with pytest.raises(ValueError):
            RiskEngine(capital=-100)
    
    def test_basic_position_sizing(self):
        """Test position sizing with values above exchange minimum."""
        # Increased capital to R1000 to ensure position > R185 minimum
        engine = RiskEngine(capital=1000)
        
        result = engine.calculate_position_size(
            entry_price=42000,
            stop_loss_price=41160,  # 2% stop
            risk_percent=0.005      # 0.5% risk (R5.00)
        )
        
        # Verify risk amount (1000 * 0.005)
        assert result.risk_amount == pytest.approx(5.0, abs=0.01)
        # Verify stop distance
        assert result.stop_distance_percent == pytest.approx(0.02, abs=0.0001)
        # Verify position size (R5.00 / 0.02 = R250)
        # R250 is > R185 exchange minimum, so it should be valid
        assert result.size == pytest.approx(250.0, abs=0.1)
        assert result.is_valid == True
    
    def test_position_sizing_tight_stop(self):
        """Test position sizing with tight stop (triggers position cap)."""
        engine = RiskEngine(capital=500)
        
        result = engine.calculate_position_size(
            entry_price=42000,
            stop_loss_price=41790,  # 0.5% stop
            risk_percent=0.005
        )
        
        # R2.50 / 0.005 = R500.00
        assert result.size == pytest.approx(500.0, abs=1.0)
        assert result.is_valid == False 
        assert "exceeds cap" in result.reason.lower()
    
    def test_position_sizing_wide_stop(self):
        """Test position sizing with wide stop."""
        engine = RiskEngine(capital=500)
        
        result = engine.calculate_position_size(
            entry_price=42000,
            stop_loss_price=39900,  # 5% stop
            risk_percent=0.005
        )
        
        # R2.50 / 0.05 = R50
        assert result.size == pytest.approx(50.0, abs=1.0)
    
    def test_position_sizing_zero_stop_distance(self):
        """Test that zero stop distance is rejected."""
        engine = RiskEngine(capital=500)
        
        result = engine.calculate_position_size(
            entry_price=42000,
            stop_loss_price=42000,
            risk_percent=0.005
        )
        
        assert result.is_valid == False
        # UPDATED: Match the message "Stop loss too tight"
        assert "too tight" in result.reason.lower()
    
    def test_position_sizing_negative_price(self):
        """Test that negative prices are rejected."""
        engine = RiskEngine(capital=500)
        
        result = engine.calculate_position_size(
            entry_price=-42000,
            stop_loss_price=41000,
            risk_percent=0.005
        )
        
        assert result.is_valid == False
    
    def test_position_sizing_zero_risk(self):
        """Test that zero risk is rejected."""
        engine = RiskEngine(capital=500)
        
        result = engine.calculate_position_size(
            entry_price=42000,
            stop_loss_price=41160,
            risk_percent=0.0
        )
        
        assert result.is_valid == False
    
    def test_position_sizing_excessive_risk(self):
        """Test that excessive risk is rejected."""
        engine = RiskEngine(capital=500)
        
        result = engine.calculate_position_size(
            entry_price=42000,
            stop_loss_price=41160,
            risk_percent=0.05  # 5% risk
        )
        
        assert result.is_valid == False
        assert "exceeds" in result.reason.lower()
    
    def test_position_sizing_different_capital(self):
        """Test position sizing scales with capital."""
        engine_small = RiskEngine(capital=200) # Increased to pass min trade
        engine_large = RiskEngine(capital=2000)
        
        result_small = engine_small.calculate_position_size(42000, 41160, 0.005)
        result_large = engine_large.calculate_position_size(42000, 41160, 0.005)
        
        assert result_large.size == pytest.approx(result_small.size * 10, abs=1.0)
    
    def test_position_sizing_uses_default_risk(self):
        """Test that default risk limit is used if not specified."""
        from config.system_config import RISK_LIMITS
        
        engine = RiskEngine(capital=2000)
        result = engine.calculate_position_size(entry_price=42000, stop_loss_price=41160)
        
        assert result.risk_percent == RISK_LIMITS.MAX_RISK_PER_TRADE
    
    def test_update_capital(self):
        """Test capital can be updated."""
        engine = RiskEngine(capital=500)
        engine.update_capital(600)
        assert engine.capital == 600
        
        result = engine.calculate_position_size(42000, 41160, 0.005)
        assert result.risk_amount == pytest.approx(3.0, abs=0.01)

    def test_position_size_verification(self):
        """Test that position size calculation is correct via verification."""
        engine = RiskEngine(capital=2000)
        result = engine.calculate_position_size(42000, 41160, 0.005)
        
        loss_at_stop = result.size * result.stop_distance_percent
        assert loss_at_stop == pytest.approx(result.risk_amount, abs=0.01)


if __name__ == "__main__":
    pytest.main([__file__, '-v'])