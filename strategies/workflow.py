"""
Trading Workflow Manager

Orchestrates the complete trading flow:
1. Get strategy signal
2. Calculate position size (risk engine)
3. Validate trade (risk engine)
4. Record decision
5. Execute trade (if approved)

This is the "brain" that connects all components.
"""

from dataclasses import dataclass
from typing import Optional, Tuple
from datetime import datetime
import logging
import pandas as pd

from strategies.base import Strategy, SignalType
from risk.engine import RiskEngine, PositionSize
from config.system_config import RISK_LIMITS

logger = logging.getLogger(__name__)


@dataclass
class TradeDecision:
    """
    Complete trade decision with all details.
    
    Attributes:
        timestamp: When decision was made
        signal_type: Strategy signal
        signal_confidence: Strategy confidence
        approved: Whether trade was approved
        rejection_reason: Why rejected (if not approved)
        position_size: Calculated position size
        risk_amount: Amount at risk
        entry_price: Entry price
        stop_loss: Stop loss price
        regime: Current market regime
        strategy_name: Which strategy generated signal
    """
    timestamp: datetime
    signal_type: SignalType
    signal_confidence: float
    approved: bool
    rejection_reason: str
    position_size: float
    risk_amount: float
    entry_price: float
    stop_loss: Optional[float]
    regime: str
    strategy_name: str


class TradingWorkflow:
    """
    Manages complete trading workflow.
    
    Connects:
    - Strategy (signal generation)
    - Risk Engine (sizing and validation)
    - Execution (paper or live - Week 4)
    """
    
    def __init__(
        self,
        strategy: Strategy,
        risk_engine: RiskEngine
    ):
        """
        Initialize trading workflow.
        
        Args:
            strategy: Trading strategy instance
            risk_engine: Risk engine instance
        """
        self.strategy = strategy
        self.risk_engine = risk_engine
        
        self.decisions: list[TradeDecision] = []
        
        logger.info(
            f"TradingWorkflow initialized: "
            f"strategy={strategy.get_name()}, "
            f"capital={risk_engine.capital}"
        )
    
    def process_market_data(
        self,
        data: pd.DataFrame,
        current_position: Optional[str] = None
    ) -> TradeDecision:
        """
        Process market data through complete workflow.
        
        This is the MAIN method that runs the entire system.
        
        Steps:
        1. Strategy generates signal
        2. If signal is actionable (LONG/SHORT):
           a. Calculate position size
           b. Validate against risk limits
           c. Approve or reject
        3. Log decision
        4. Return decision
        
        Args:
            data: DataFrame with features and regime
            current_position: Current position ('long', 'short', None)
            
        Returns:
            TradeDecision with complete details
            
        Example:
            >>> decision = workflow.process_market_data(df)
            >>> if decision.approved:
            ...     # Execute trade
        """
        timestamp = datetime.now()
        
        # Step 1: Get strategy signal
        logger.info("Step 1: Generating strategy signal...")
        signal = self.strategy.generate_signal(data, current_position)
        
        logger.info(
            f"Signal: {signal.signal_type.value}, "
            f"confidence: {signal.confidence:.2f}, "
            f"regime: {signal.regime}"
        )
        
        # Step 2: If no trade signal, we're done
        if signal.signal_type == SignalType.NO_TRADE:
            decision = TradeDecision(
                timestamp=timestamp,
                signal_type=signal.signal_type,
                signal_confidence=signal.confidence,
                approved=False,
                rejection_reason="Strategy says NO_TRADE",
                position_size=0.0,
                risk_amount=0.0,
                entry_price=signal.entry_price,
                stop_loss=signal.stop_loss,
                regime=signal.regime or 'unknown',
                strategy_name=self.strategy.get_name()
            )
            
            self.decisions.append(decision)
            return decision
        
        # Step 3: If exit signal, approve immediately
        if signal.signal_type == SignalType.EXIT:
            decision = TradeDecision(
                timestamp=timestamp,
                signal_type=signal.signal_type,
                signal_confidence=signal.confidence,
                approved=True,
                rejection_reason="",
                position_size=0.0,  # Exit doesn't need size
                risk_amount=0.0,
                entry_price=signal.entry_price,
                stop_loss=signal.stop_loss,
                regime=signal.regime or 'unknown',
                strategy_name=self.strategy.get_name()
            )
            
            self.decisions.append(decision)
            logger.info("EXIT signal approved")
            return decision
        
        # Step 4: Process entry signal (LONG or SHORT)
        logger.info("Step 2: Calculating position size...")
        
        position = self.risk_engine.calculate_position_size(
            entry_price=signal.entry_price,
            stop_loss_price=signal.stop_loss or signal.entry_price * 0.98,
            risk_percent=None  # Use default from config
        )
        
        if not position.is_valid:
            decision = TradeDecision(
                timestamp=timestamp,
                signal_type=signal.signal_type,
                signal_confidence=signal.confidence,
                approved=False,
                rejection_reason=f"Position sizing failed: {position.reason}",
                position_size=0.0,
                risk_amount=0.0,
                entry_price=signal.entry_price,
                stop_loss=signal.stop_loss,
                regime=signal.regime or 'unknown',
                strategy_name=self.strategy.get_name()
            )
            
            self.decisions.append(decision)
            logger.warning(f"Position sizing failed: {position.reason}")
            return decision
        
        logger.info(
            f"Position size: R{position.size:.2f}, "
            f"risk: R{position.risk_amount:.2f} ({position.risk_percent*100:.2f}%)"
        )
        
        # Step 5: Validate trade against risk limits
        logger.info("Step 3: Validating trade...")
        
        is_valid, reason = self.risk_engine.validate_trade(
            position_size=position.size,
            risk_amount=position.risk_amount,
            risk_percent=position.risk_percent
        )
        
        if not is_valid:
            decision = TradeDecision(
                timestamp=timestamp,
                signal_type=signal.signal_type,
                signal_confidence=signal.confidence,
                approved=False,
                rejection_reason=f"Risk validation failed: {reason}",
                position_size=position.size,
                risk_amount=position.risk_amount,
                entry_price=signal.entry_price,
                stop_loss=signal.stop_loss,
                regime=signal.regime or 'unknown',
                strategy_name=self.strategy.get_name()
            )
            
            self.decisions.append(decision)
            logger.warning(f"Trade rejected: {reason}")
            return decision
        
        # Step 6: Trade approved!
        decision = TradeDecision(
            timestamp=timestamp,
            signal_type=signal.signal_type,
            signal_confidence=signal.confidence,
            approved=True,
            rejection_reason="",
            position_size=position.size,
            risk_amount=position.risk_amount,
            entry_price=signal.entry_price,
            stop_loss=signal.stop_loss,
            regime=signal.regime or 'unknown',
            strategy_name=self.strategy.get_name()
        )
        
        self.decisions.append(decision)
        
        logger.info(
            f"✅ TRADE APPROVED: {signal.signal_type.value} "
            f"R{position.size:.2f} @ R{signal.entry_price:.2f}"
        )
        
        return decision
    
    def get_decision_statistics(self) -> dict:
        """
        Get statistics about decisions made.
        
        Returns:
            Dictionary with decision stats
        """
        if not self.decisions:
            return {
                'total_decisions': 0,
                'approved': 0,
                'rejected': 0,
            }
        
        approved = sum(1 for d in self.decisions if d.approved)
        rejected = len(self.decisions) - approved
        
        signal_types = {}
        for d in self.decisions:
            signal_type = d.signal_type.value
            signal_types[signal_type] = signal_types.get(signal_type, 0) + 1
        
        rejection_reasons = {}
        for d in self.decisions:
            if not d.approved and d.rejection_reason:
                reason = d.rejection_reason.split(':')[0]  # First part
                rejection_reasons[reason] = rejection_reasons.get(reason, 0) + 1
        
        return {
            'total_decisions': len(self.decisions),
            'approved': approved,
            'rejected': rejected,
            'approval_rate': approved / len(self.decisions) if self.decisions else 0,
            'signal_types': signal_types,
            'rejection_reasons': rejection_reasons,
        }
    
    def print_decision_summary(self) -> None:
        """Print formatted decision summary."""
        stats = self.get_decision_statistics()
        
        print("=" * 60)
        print("TRADING WORKFLOW SUMMARY")
        print("=" * 60)
        
        print(f"\n📊 Total decisions: {stats['total_decisions']}")
        print(f"   ✅ Approved: {stats['approved']}")
        print(f"   ❌ Rejected: {stats['rejected']}")
        print(f"   Approval rate: {stats['approval_rate']*100:.1f}%")
        
        if stats['signal_types']:
            print("\n📈 Signal types:")
            for signal_type, count in stats['signal_types'].items():
                print(f"   {signal_type}: {count}")
        
        if stats['rejection_reasons']:
            print("\n🚫 Rejection reasons:")
            for reason, count in stats['rejection_reasons'].items():
                print(f"   {reason}: {count}")
        
        print("=" * 60)


def main():
    """Test trading workflow."""
    print("=" * 60)
    print("TRADING WORKFLOW TEST")
    print("=" * 60)
    
    # Setup
    from strategies.simple_trend import SimpleTrendStrategy
    from regime.features import calculate_complete_pipeline
    import numpy as np
    import pandas as pd
    
    # Create strategy and risk engine
    strategy = SimpleTrendStrategy()
    risk_engine = RiskEngine(capital=500)
    
    workflow = TradingWorkflow(strategy, risk_engine)
    
    print(f"\n📊 Strategy: {strategy.get_name()}")
    print(f"   Capital: R{risk_engine.capital:.2f}")
    
    # Create test data
    n = 100
    prices = np.linspace(40000, 45000, n) + np.random.randn(n) * 100
    
    df = pd.DataFrame({
        'close': prices,
        'high': prices + 100,
        'low': prices - 100,
        'volume': 100 + np.abs(np.random.randn(n) * 20),
    })
    
    # Calculate features (normally done by pipeline)
    df['regime'] = 'trend'
    df['regime_confidence'] = 0.8
    df['efficiency_ratio'] = 0.75
    df['atr'] = 600.0
    df['volume_regime'] = 'normal'
    
    # Process data
    print("\n🔄 Processing market data...")
    decision = workflow.process_market_data(df, current_position=None)
    
    print("\n📋 Decision:")
    print(f"   Signal: {decision.signal_type.value}")
    print(f"   Approved: {decision.approved}")
    if decision.approved:
        print(f"   Position size: R{decision.position_size:.2f}")
        print(f"   Risk amount: R{decision.risk_amount:.2f}")
        print(f"   Entry: R{decision.entry_price:.2f}")
        print(f"   Stop: R{decision.stop_loss:.2f}")
    else:
        print(f"   Rejection reason: {decision.rejection_reason}")
    
    # Test rejection scenario
    print("\n🔄 Test rejection (consecutive losses)...")
    risk_engine.state.consecutive_losses = 2  # Hit limit
    
    decision2 = workflow.process_market_data(df, current_position=None)
    print(f"   Approved: {decision2.approved}")
    print(f"   Reason: {decision2.rejection_reason}")
    
    # Summary
    print("\n")
    workflow.print_decision_summary()


if __name__ == "__main__":
    main()