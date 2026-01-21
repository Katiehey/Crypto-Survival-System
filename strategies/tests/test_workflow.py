"""
Tests for trading workflow integration.
"""

import pytest
import numpy as np
import pandas as pd
from strategies.workflow import TradingWorkflow, TradeDecision
from strategies.simple_trend import SimpleTrendStrategy
from risk.engine import RiskEngine
from strategies.base import SignalType


class TestTradingWorkflow:
    """Test complete trading workflow."""
    
    def create_test_data(self, regime='trend', efficiency=0.75):
        """Create test data."""
        n = 100
        prices = np.linspace(40000, 45000, n)
        
        return pd.DataFrame({
            'close': prices,
            'high': prices + 100,
            'low': prices - 100,
            'volume': 100 + np.abs(np.random.randn(n) * 20),
            'regime': [regime] * n,
            'regime_confidence': [0.8] * n,
            'efficiency_ratio': [efficiency] * n,
            'atr': [600.0] * n,
            'volume_regime': ['normal'] * n,
        })
    
    def test_workflow_initialization(self):
        """Test workflow can be initialized."""
        strategy = SimpleTrendStrategy()
        risk_engine = RiskEngine(500)
        
        workflow = TradingWorkflow(strategy, risk_engine)
        
        assert workflow.strategy == strategy
        assert workflow.risk_engine == risk_engine
        assert len(workflow.decisions) == 0
    
    def test_approved_trade_flow(self):
        """Test complete flow for approved trade."""
        strategy = SimpleTrendStrategy()
        risk_engine = RiskEngine(500)
        workflow = TradingWorkflow(strategy, risk_engine)
        
        df = self.create_test_data(regime='trend', efficiency=0.75)
        
        decision = workflow.process_market_data(df, current_position=None)
        
        # Should be approved
        assert decision.approved == True
        assert decision.signal_type == SignalType.LONG
        assert decision.position_size > 0
        assert decision.risk_amount > 0
        assert decision.stop_loss < decision.entry_price
    
    def test_rejected_wrong_regime(self):
        """Test rejection due to wrong regime."""
        strategy = SimpleTrendStrategy()
        risk_engine = RiskEngine(500)
        workflow = TradingWorkflow(strategy, risk_engine)
        
        df = self.create_test_data(regime='range')
        
        decision = workflow.process_market_data(df, current_position=None)
        
        # Should be rejected (strategy returns NO_TRADE)
        assert decision.approved == False
        assert "NO_TRADE" in decision.rejection_reason
    
    def test_rejected_by_risk_engine(self):
        """Test rejection by risk engine."""
        strategy = SimpleTrendStrategy()
        risk_engine = RiskEngine(500)
        workflow = TradingWorkflow(strategy, risk_engine)
        
        # Trigger consecutive loss limit
        risk_engine.state.consecutive_losses = 2
        
        df = self.create_test_data(regime='trend', efficiency=0.75)
        
        decision = workflow.process_market_data(df, current_position=None)
        
        # Should be rejected by risk engine
        assert decision.approved == False
        assert "consecutive" in decision.rejection_reason.lower()
    
    def test_exit_signal_approved(self):
        """Test that exit signals are approved."""
        strategy = SimpleTrendStrategy()
        risk_engine = RiskEngine(500)
        workflow = TradingWorkflow(strategy, risk_engine)
        
        # Create data that triggers exit
        df = self.create_test_data(regime='range')  # Regime change
        
        decision = workflow.process_market_data(df, current_position='long')
        
        # Exit should be approved
        assert decision.signal_type == SignalType.EXIT
        assert decision.approved == True
    
    def test_decision_logging(self):
        """Test that decisions are logged."""
        strategy = SimpleTrendStrategy()
        risk_engine = RiskEngine(500)
        workflow = TradingWorkflow(strategy, risk_engine)
        
        df = self.create_test_data()
        
        workflow.process_market_data(df)
        workflow.process_market_data(df)
        
        assert len(workflow.decisions) == 2
    
    def test_decision_statistics(self):
        """Test decision statistics calculation."""
        strategy = SimpleTrendStrategy()
        risk_engine = RiskEngine(500)
        workflow = TradingWorkflow(strategy, risk_engine)
        
        df_good = self.create_test_data(regime='trend', efficiency=0.75)
        df_bad = self.create_test_data(regime='range')
        
        workflow.process_market_data(df_good)  # Approved
        workflow.process_market_data(df_bad)   # Rejected
        
        stats = workflow.get_decision_statistics()
        
        assert stats['total_decisions'] == 2
        assert stats['approved'] == 1
        assert stats['rejected'] == 1
        assert stats['approval_rate'] == 0.5
    
    def test_position_sizing_integration(self):
        """Test position sizing is calculated correctly."""
        strategy = SimpleTrendStrategy()
        risk_engine = RiskEngine(500)
        workflow = TradingWorkflow(strategy, risk_engine)
        
        df = self.create_test_data()
        
        decision = workflow.process_market_data(df)
        
        if decision.approved:
            # FIX: Update expectation from 2.5 to 5.0
            # Because our RISK_LIMITS.MAX_RISK_PER_TRADE is now 0.01 (1%)
            assert decision.risk_amount == pytest.approx(5.0, abs=0.1)
    
    def test_complete_workflow_sequence(self):
        """Test complete sequence of decisions."""
        strategy = SimpleTrendStrategy()
        risk_engine = RiskEngine(500)
        workflow = TradingWorkflow(strategy, risk_engine)
        
        # 1. Entry signal (approved)
        df_entry = self.create_test_data(regime='trend', efficiency=0.75)
        decision1 = workflow.process_market_data(df_entry, current_position=None)
        
        assert decision1.approved == True
        assert decision1.signal_type == SignalType.LONG
        
        # 2. Hold signal (no action)
        decision2 = workflow.process_market_data(df_entry, current_position='long')
        
        # Should either hold or exit (depending on conditions)
        assert decision2.signal_type in [SignalType.NO_TRADE, SignalType.EXIT]
        
        # 3. Exit signal (approved)
        df_exit = self.create_test_data(regime='range')
        decision3 = workflow.process_market_data(df_exit, current_position='long')
        
        assert decision3.signal_type == SignalType.EXIT
        assert decision3.approved == True


if __name__ == "__main__":
    pytest.main([__file__, '-v'])