"""
Tests for capital tracking and drawdown monitoring.
"""

import pytest
from risk.capital_tracker import CapitalTracker
from config.system_config import RISK_LIMITS


class TestCapitalTracker:
    """Test capital tracking functionality."""
    
    def test_initialization(self):
        """Test capital tracker initialization."""
        tracker = CapitalTracker(500)
        
        assert tracker.current == 500
        assert tracker.peak == 500
        assert tracker.starting == 500
        assert tracker.get_drawdown() == 0.0
    
    def test_initialization_invalid(self):
        """Test initialization with invalid capital."""
        with pytest.raises(ValueError):
            CapitalTracker(0)
        
        with pytest.raises(ValueError):
            CapitalTracker(-100)
    
    def test_update_increases_capital(self):
        """Test updating with increased capital."""
        tracker = CapitalTracker(500)
        
        kill_switch, _ = tracker.update(510)
        
        assert tracker.current == 510
        assert tracker.peak == 510
        assert kill_switch == False
    
    def test_update_decreases_capital(self):
        """Test updating with decreased capital."""
        tracker = CapitalTracker(500)
        
        kill_switch, _ = tracker.update(490)
        
        assert tracker.current == 490
        assert tracker.peak == 500  # Peak stays at 500
        assert kill_switch == False
    
    def test_drawdown_calculation(self):
        """Test drawdown calculation."""
        tracker = CapitalTracker(500)
        
        # Increase to new peak
        tracker.update(510)
        
        # Decrease (drawdown)
        tracker.update(485)
        
        # Drawdown = (510 - 485) / 510 = 0.049 = 4.9%
        assert tracker.get_drawdown() == pytest.approx(0.049, abs=0.001)
    
    def test_drawdown_amount(self):
        """Test drawdown amount calculation."""
        tracker = CapitalTracker(500)
        tracker.update(510)
        tracker.update(485)
        
        # Lost R25 from peak
        assert tracker.get_drawdown_amount() == pytest.approx(25.0, abs=0.01)
    
    def test_kill_switch_trigger(self):
        """Test kill switch triggers on excessive drawdown."""
        tracker = CapitalTracker(500)
        
        # Set peak
        tracker.update(500)
        
        # Calculate 5% drawdown threshold
        threshold = 500 * (1 - RISK_LIMITS.MAX_DRAWDOWN_FROM_PEAK)
        
        # Just below threshold (should NOT trigger)
        kill_switch, _ = tracker.update(threshold + 1)
        assert kill_switch == False
        
        # At threshold (should trigger)
        kill_switch, reason = tracker.update(threshold - 1)
        assert kill_switch == True
        assert "drawdown" in reason.lower()
    
    def test_return_from_start(self):
        """Test total return calculation."""
        tracker = CapitalTracker(500)
        
        tracker.update(550)
        
        # 10% return
        assert tracker.get_return_from_start() == pytest.approx(0.10, abs=0.001)
    
    def test_peak_return(self):
        """Test peak return calculation."""
        tracker = CapitalTracker(500)
        
        # Reach peak
        tracker.update(550)
        
        # Drop down
        tracker.update(520)
        
        # Peak return is still 10% (from starting 500 to peak 550)
        assert tracker.get_peak_return() == pytest.approx(0.10, abs=0.001)
    
    def test_is_at_peak(self):
        """Test peak detection."""
        tracker = CapitalTracker(500)
        
        assert tracker.is_at_peak() == True
        
        tracker.update(510)
        assert tracker.is_at_peak() == True
        
        tracker.update(505)
        assert tracker.is_at_peak() == False
    
    def test_recovery_from_drawdown(self):
        """Test that drawdown reduces on recovery."""
        tracker = CapitalTracker(500)
        
        # Set peak
        tracker.update(510)
        
        # Drawdown
        tracker.update(485)
        assert tracker.get_drawdown() > 0
        
        # Partial recovery
        tracker.update(500)
        assert tracker.get_drawdown() == pytest.approx(0.0196, abs=0.001)
        
        # Full recovery to peak
        tracker.update(510)
        assert tracker.get_drawdown() == 0.0
    
    def test_new_peak_resets_drawdown(self):
        """Test that new peak resets drawdown."""
        tracker = CapitalTracker(500)
        
        # Drawdown
        tracker.update(490)
        assert tracker.get_drawdown() > 0
        
        # New peak
        tracker.update(520)
        assert tracker.get_drawdown() == 0.0
        assert tracker.peak == 520
    
    def test_statistics(self):
        """Test statistics dictionary."""
        tracker = CapitalTracker(500)
        tracker.update(510)
        tracker.update(495)
        
        stats = tracker.get_statistics()
        
        assert 'current' in stats
        assert 'peak' in stats
        assert 'drawdown_pct' in stats
        assert 'total_return_pct' in stats
        
        assert stats['current'] == 495
        assert stats['peak'] == 510
    
    def test_zero_capital_triggers_kill_switch(self):
        """Test that zero capital triggers kill switch."""
        tracker = CapitalTracker(500)
        
        kill_switch, reason = tracker.update(0)
        
        assert kill_switch == True
        assert "zero" in reason.lower()


class TestCapitalTrackerIntegration:
    """Test capital tracker integration with risk engine."""
    
    def test_risk_engine_has_capital_tracker(self):
        """Test risk engine initializes capital tracker."""
        from risk.engine import RiskEngine
        
        engine = RiskEngine(500)
        
        assert hasattr(engine, 'capital_tracker')
        assert engine.capital_tracker.current == 500
    
    def test_drawdown_triggers_kill_switch_in_engine(self):
        """Test that drawdown triggers kill switch in risk engine."""
        from risk.engine import RiskEngine
        
        engine = RiskEngine(500)
        
        # Create drawdown > 5%
        new_capital = 500 * 0.94  # 6% drawdown
        engine.update_capital(new_capital)
        
        # Kill switch should be active
        assert engine.state.kill_switch_active == True
    
    def test_engine_capital_stats(self):
        """Test getting capital stats from engine."""
        from risk.engine import RiskEngine
        
        engine = RiskEngine(500)
        engine.update_capital(510)
        
        stats = engine.get_capital_stats()
        
        assert stats['peak'] == 510
        assert stats['current'] == 510


if __name__ == "__main__":
    pytest.main([__file__, '-v'])