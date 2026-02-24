# paper_trading/execution.py
"""
Execution simulator for paper trading.
Simulates realistic order execution with slippage, fees, and delays.
"""

import time
import random
from datetime import datetime
from turtle import delay
from typing import Dict, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


class ExecutionResult:
    """Result of an order execution."""
    
    def __init__(self, success: bool, execution_price: float, fee: float, 
                 filled_size: float = 0.0,  
                 reason: str = "", timestamp: datetime = None):
        self.success = success
        self.execution_price = execution_price
        self.fee = fee
        self.filled_size = filled_size # Track actual amount traded
        self.reason = reason
        self.timestamp = timestamp or datetime.now()
    
    def __repr__(self):
        status = "✅" if self.success else "❌"
        return (f"ExecutionResult({status} @ ${self.execution_price:.2f}, "
                f"fee: ${self.fee:.4f}, filled: {self.filled_size}, reason: {self.reason})")


class ExecutionSimulator:
    """
    Simulates realistic order execution.
    
    Features:
    - Slippage simulation
    - Fee calculation
    - Order delays
    - Partial fills
    - Market impact (for large orders)
    - Rejections (insufficient liquidity, etc.)
    """
    
    def __init__(
        self,
        base_slippage: float = 0.001,  # 0.1% base slippage
        base_fee_rate: float = 0.00075,  # 0.075% fee (Binance)
        min_execution_delay: float = 0.1,  # Minimum delay in seconds
        max_execution_delay: float = 2.0,  # Maximum delay in seconds
        fill_probability: float = 0.95,  # Probability of full fill
        liquidity_factor: float = 0.0001,  # Market impact factor
        reject_probability: float = 0.02  # Probability of rejection
    ):
        """
        Initialize execution simulator.
        
        Args:
            base_slippage: Base slippage percentage
            base_fee_rate: Base fee rate percentage
            min_execution_delay: Minimum execution delay in seconds
            max_execution_delay: Maximum execution delay in seconds
            fill_probability: Probability of getting full fill
            liquidity_factor: Market impact factor (slippage increases with order size)
            reject_probability: Probability of order rejection
        """
        self.base_slippage = base_slippage
        self.base_fee_rate = base_fee_rate
        self.min_execution_delay = min_execution_delay
        self.max_execution_delay = max_execution_delay
        self.fill_probability = fill_probability
        self.liquidity_factor = liquidity_factor
        self.reject_probability = reject_probability
        
        # Statistics tracking
        self.execution_count = 0
        self.rejection_count = 0
        self.partial_fill_count = 0
        self.total_fees = 0.0
        self.total_slippage = 0.0
        
        logger.info(f"ExecutionSimulator initialized: {base_slippage*100:.3f}% slippage, "
                   f"{base_fee_rate*100:.3f}% fees")
    
    def execute_order(
        self,
        symbol: str,
        side: str,  # 'buy' or 'sell'
        size: float,  # Size in quote currency
        price: float,  # Requested price
        order_type: str = "market",  # 'market' or 'limit'
        limit_price: Optional[float] = None
    ) -> ExecutionResult:
        """
        Simulate order execution.
        
        Args:
            symbol: Trading pair
            side: 'buy' or 'sell'
            size: Order size in quote currency
            price: Current market price
            order_type: 'market' or 'limit'
            limit_price: Limit price (for limit orders)
            
        Returns:
            ExecutionResult object
        """
        self.execution_count += 1
        
        # Simulate execution delay
        delay = random.uniform(self.min_execution_delay, self.max_execution_delay)
        if getattr(self, 'use_real_delays', True):
            time.sleep(delay)
        
        # Check for rejection
        if random.random() < self.reject_probability:
            self.rejection_count += 1
            reasons = [
                "insufficient liquidity",
                "network timeout",
                "exchange maintenance",
                "price moved too fast"
            ]
            return ExecutionResult(
                success=False,
                execution_price=price,
                fee=0.0,
                filled_size=0.0,
                reason=random.choice(reasons)
            )
        
        # Calculate market impact (larger orders cause more slippage)
        order_ratio = size / (price * 100)  # Simplified: assume $100k daily volume
        market_impact = self.liquidity_factor * order_ratio
        
        # Calculate total slippage
        total_slippage = self.base_slippage + market_impact
        
        # Apply slippage
        if side == 'buy':
            # Buying pays more (slippage increases price)
            execution_price = price * (1 + total_slippage)
        else:  # sell
            # Selling gets less (slippage decreases price)
            execution_price = price * (1 - total_slippage)
        
        # For limit orders, check if price is favorable
        if order_type == 'limit' and limit_price:
            if side == 'buy':
                # Buy limit only executes if market price <= limit price
                if price > limit_price:
                    return ExecutionResult(
                        success=False,
                        execution_price=0.0,
                        fee=0.0,
                        filled_size=0.0,
                        reason="limit price not reached"
                    )
                execution_price = min(execution_price, limit_price)
            else:  # sell
                # Sell limit only executes if market price >= limit price
                if price < limit_price:
                    return ExecutionResult(
                        success=False,
                        execution_price=0.0,
                        fee=0.0,
                        filled_size=0.0,
                        reason="limit price not reached"
                    )
                execution_price = max(execution_price, limit_price)
        
        # Check for partial fill
        filled_size = size
        if random.random() > self.fill_probability:
            self.partial_fill_count += 1
            fill_ratio = random.uniform(0.5, 0.95)  # 50-95% filled
            filled_size = size * fill_ratio
        
        # Calculate fees
        fee = filled_size * self.base_fee_rate
        
        # Update statistics
        self.total_fees += fee
        self.total_slippage += abs(execution_price - price) * (filled_size / execution_price)
        
        # Create result
        result = ExecutionResult(
            success=True,
            execution_price=execution_price,
            fee=fee,
            filled_size=filled_size,
            reason=f"filled {filled_size/size*100:.1f}%" if filled_size < size else "fully filled"
        )
        
        logger.debug(f"Order executed: {side.upper()} {symbol} {filled_size:.2f} @ "
                    f"${execution_price:.2f} (slippage: {total_slippage*100:.3f}%)")
        
        return result
    
    def get_statistics(self) -> Dict:
        """Get execution statistics."""
        return {
            'total_executions': self.execution_count,
            'rejections': self.rejection_count,
            'partial_fills': self.partial_fill_count,
            'rejection_rate': self.rejection_count / self.execution_count if self.execution_count > 0 else 0,
            'partial_fill_rate': self.partial_fill_count / self.execution_count if self.execution_count > 0 else 0,
            'total_fees': self.total_fees,
            'avg_fee_per_trade': self.total_fees / self.execution_count if self.execution_count > 0 else 0,
            'total_slippage': self.total_slippage,
            'avg_slippage_per_trade': self.total_slippage / self.execution_count if self.execution_count > 0 else 0
        }
    
    def print_statistics(self):
        """Print execution statistics."""
        stats = self.get_statistics()
        
        print("=" * 70)
        print("EXECUTION SIMULATOR STATISTICS")
        print("=" * 70)
        
        print(f"\n📊 EXECUTIONS")
        print(f"   Total: {stats['total_executions']}")
        print(f"   Rejections: {stats['rejections']} ({stats['rejection_rate']:.1%})")
        print(f"   Partial Fills: {stats['partial_fills']} ({stats['partial_fill_rate']:.1%})")
        
        print(f"\n💰 COSTS")
        print(f"   Total Fees: ${stats['total_fees']:.4f}")
        print(f"   Avg Fee/Trade: ${stats['avg_fee_per_trade']:.4f}")
        print(f"   Total Slippage: ${stats['total_slippage']:.4f}")
        print(f"   Avg Slippage/Trade: ${stats['avg_slippage_per_trade']:.4f}")
        
        print(f"\n⚙️  CONFIGURATION")
        print(f"   Base Slippage: {self.base_slippage*100:.3f}%")
        print(f"   Base Fee Rate: {self.base_fee_rate*100:.3f}%")
        print(f"   Fill Probability: {self.fill_probability:.1%}")
        
        print("\n" + "=" * 70)


class RealisticExecutionSimulator(ExecutionSimulator):
    """
    More realistic execution simulator with:
    - Time-of-day effects (more volatile during certain hours)
    - News event simulation
    - Exchange-specific behaviors
    """
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        
        # Time-of-day multipliers (0-24 UTC)
        # Higher multiplier = more volatility/slippage
        self.time_of_day_effects = {
            0: 1.2,   # Midnight UTC (Asian markets active)
            8: 1.5,   # 8 AM UTC (London opens)
            14: 1.8,  # 2 PM UTC (London/New York overlap)
            20: 1.3,  # 8 PM UTC (New York afternoon)
        }
        
        # News event probability (per hour)
        self.news_probability = 0.05
        self.news_impact = 2.0  # Multiplier during news
        
        self.news_active = False
    
    def _get_time_of_day_multiplier(self) -> float:
        """Get time-of-day volatility multiplier."""
        current_hour = datetime.utcnow().hour
        
        # Find closest hour in our effects
        closest_hour = min(self.time_of_day_effects.keys(), 
                          key=lambda x: min(abs(x - current_hour), 
                                          24 - abs(x - current_hour)))
        
        return self.time_of_day_effects.get(closest_hour, 1.0)
    
    def _check_news_event(self):
        """Check if a news event occurs."""
        if not self.news_active and random.random() < self.news_probability:
            self.news_active = True
            logger.warning("📰 NEWS EVENT: Increased volatility and slippage")
        
        # News events last 1-3 hours
        if self.news_active and random.random() < 0.3:
            self.news_active = False
    
    def execute_order(self, **kwargs) -> ExecutionResult:
        """Execute order with realistic enhancements."""
        # Check for news events
        self._check_news_event()
        
        # Get time-of-day multiplier
        time_multiplier = self._get_time_of_day_multiplier()
        
        # Apply multipliers
        original_slippage = self.base_slippage
        
        if self.news_active:
            self.base_slippage *= self.news_impact
        
        self.base_slippage *= time_multiplier
        
        # Execute order
        result = super().execute_order(**kwargs)
        
        # Restore original slippage
        self.base_slippage = original_slippage
        
        return result


def create_execution_simulator(simulator_type: str = "basic", **kwargs) -> ExecutionSimulator:
    """
    Factory function to create execution simulators.
    
    Args:
        simulator_type: Type of simulator ('basic', 'realistic')
        **kwargs: Simulator-specific arguments
        
    Returns:
        Execution simulator instance
    """
    if simulator_type == "basic":
        return ExecutionSimulator(**kwargs)
    elif simulator_type == "realistic":
        return RealisticExecutionSimulator(**kwargs)
    else:
        raise ValueError(f"Unknown simulator type: {simulator_type}")


def main():
    """Test execution simulator."""
    print("=" * 70)
    print("EXECUTION SIMULATOR TEST")
    print("=" * 70)
    
    # Test basic simulator
    print("\n1. Testing basic ExecutionSimulator...")
    simulator = ExecutionSimulator(
        base_slippage=0.001,
        base_fee_rate=0.00075,
        min_execution_delay=0.01,  # Fast for testing
        max_execution_delay=0.05
    )
    
    # Simulate some orders
    orders = [
        ("BTC/USDT", "buy", 1000, 42000),
        ("BTC/USDT", "sell", 500, 42500),
        ("BTC/USDT", "buy", 2000, 43000),
    ]
    
    for symbol, side, size, price in orders:
        result = simulator.execute_order(symbol, side, size, price)
        print(f"   {side.upper()} {size} @ ${price:.2f}: {result}")
    
    # Print statistics
    simulator.print_statistics()
    
    # Test realistic simulator
    print("\n2. Testing RealisticExecutionSimulator...")
    realistic = RealisticExecutionSimulator(
        base_slippage=0.001,
        base_fee_rate=0.00075,
        min_execution_delay=0.01,
        max_execution_delay=0.05
    )
    
    # Simulate a few orders
    for _ in range(3):
        result = realistic.execute_order("BTC/USDT", "buy", 1000, 42000)
        print(f"   Realistic execution: {result}")
    
    print("\n3. Testing factory function...")
    simulators = ["basic", "realistic"]
    
    for sim_type in simulators:
        try:
            sim = create_execution_simulator(sim_type, base_slippage=0.001)
            result = sim.execute_order("TEST/USDT", "buy", 100, 100)
            print(f"   {sim_type}: {result}")
        except Exception as e:
            print(f"   {sim_type}: Error - {e}")
    
    print("\n✅ Execution simulator test complete")
    print("=" * 70)


if __name__ == "__main__":
    main()