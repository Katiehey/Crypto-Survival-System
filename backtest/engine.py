"""
Backtest Engine - Historical strategy testing.

Core backtesting engine that:
- Replays historical data chronologically
- Generates strategy signals
- Simulates trade execution
- Tracks positions and capital
- Records all trades
"""

from datetime import datetime
from typing import Optional, List
import pandas as pd
import logging
import uuid

from strategies.base import Strategy, SignalType
from risk.engine import RiskEngine
from backtest.trade import Trade, create_trade
from backtest.result import BacktestResult
from backtest.data_loader import BacktestDataLoader

logger = logging.getLogger(__name__)


class Position:
    """
    Represents an open position during backtest.
    
    Attributes:
        entry_time: When position was opened
        entry_price: Entry price
        entry_regime: Regime at entry
        size: Position size
        side: 'long' or 'short'
        stop_loss: Stop loss price
    """
    
    def __init__(
        self,
        entry_time: datetime,
        entry_price: float,
        entry_regime: str,
        size: float,
        stop_loss: float,
        side: str = 'long'
    ):
        self.entry_time = entry_time
        self.entry_price = entry_price
        self.entry_regime = entry_regime
        self.size = size
        self.stop_loss = stop_loss
        self.side = side
        
        # Track excursions
        self.best_price = entry_price
        self.worst_price = entry_price
    
    def update_excursions(self, high: float, low: float) -> None:
        """Update MFE and MAE tracking."""
        if self.side == 'long':
            self.best_price = max(self.best_price, high)
            self.worst_price = min(self.worst_price, low)
        else:
            # Short positions (not implemented yet)
            raise NotImplementedError("Short positions not supported")
    
    def check_stop_loss(self, candle_low: float) -> bool:
        """
        Check if stop loss was hit.
        
        Args:
            candle_low: Low price of current candle
            
        Returns:
            True if stop loss hit
        """
        if self.side == 'long':
            return candle_low <= self.stop_loss
        else:
            raise NotImplementedError("Short positions not supported")
    
    def get_mfe(self) -> float:
        """Get Maximum Favorable Excursion."""
        if self.side == 'long':
            return self.best_price - self.entry_price
        else:
            raise NotImplementedError("Short positions not supported")
    
    def get_mae(self) -> float:
        """Get Maximum Adverse Excursion."""
        if self.side == 'long':
            return self.entry_price - self.worst_price
        else:
            raise NotImplementedError("Short positions not supported")


class BacktestEngine:
    """
    Main backtesting engine.
    
    Orchestrates:
    - Historical data replay
    - Strategy signal generation
    - Trade execution simulation
    - Position tracking
    - Capital tracking
    - Trade recording
    """
    
    def __init__(
        self,
        strategy: Strategy,
        initial_capital: float,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        slippage: float = 0.001,  # 0.1%
        fee_rate: float = 0.00075,  # 0.075% (Binance)
        data_limit: Optional[int] = None
    ):
        """
        Initialize backtest engine.
        
        Args:
            strategy: Trading strategy to test
            initial_capital: Starting capital
            start_date: Backtest start date
            end_date: Backtest end date
            slippage: Slippage as decimal (0.001 = 0.1%)
            fee_rate: Fee rate as decimal
            data_limit: Limit number of candles (if dates not used)
        """
        self.strategy = strategy
        self.initial_capital = initial_capital
        self.start_date = start_date
        self.end_date = end_date
        self.slippage = slippage
        self.fee_rate = fee_rate
        self.data_limit = data_limit
        
        # State
        self.capital = initial_capital
        self.current_position: Optional[Position] = None
        self.trades: List[Trade] = []
        
        # Data
        self.data: Optional[pd.DataFrame] = None
        self.current_index: int = 0
        
        logger.info(
            f"BacktestEngine initialized: "
            f"strategy={strategy.get_name()}, "
            f"capital=${initial_capital:.2f}, "
            f"slippage={slippage*100:.2f}%, "
            f"fees={fee_rate*100:.3f}%"
        )
    
    def run(self) -> BacktestResult:
        """
        Run complete backtest.
        
        Returns:
            BacktestResult with all metrics and trades
        """
        logger.info("=" * 60)
        logger.info("STARTING BACKTEST")
        logger.info("=" * 60)
        
        # Load and prepare data
        self._load_data()
        
        # Validate sufficient data
        if len(self.data) < 50:
            raise ValueError(
                f"Insufficient data for backtest: {len(self.data)} candles. "
                f"Need at least 50."
            )
        
        logger.info(f"Data loaded: {len(self.data)} candles")
        logger.info(f"Period: {self.data['datetime'].iloc[0]} to {self.data['datetime'].iloc[-1]}")
        
        # Process each candle
        for idx in range(len(self.data)):
            self.current_index = idx
            candle = self.data.iloc[idx]
            
            self._process_candle(candle)
        
        # Close any open position at end
        if self.current_position is not None:
            self._close_position(
                self.data.iloc[-1],
                reason='end_of_data'
            )
        
        # Create result
        result = self._create_result()
        
        logger.info("=" * 60)
        logger.info("BACKTEST COMPLETE")
        logger.info("=" * 60)
        
        return result
    
    def _load_data(self) -> None:
        """Load and prepare historical data."""
        loader = BacktestDataLoader()
        
        self.data = loader.load_and_prepare(
            start_date=self.start_date,
            end_date=self.end_date,
            limit=self.data_limit
        )
    
    def _process_candle(self, candle: pd.Series) -> None:
        """
        Process single historical candle.
        
        Args:
            candle: Current candle data
        """
        # Check if we have a position
        if self.current_position is not None:
            # Update excursions
            self.current_position.update_excursions(
                candle['high'],
                candle['low']
            )
            
            # Check stop loss
            if self.current_position.check_stop_loss(candle['low']):
                self._close_position(candle, reason='stop_loss')
                return
            
            # Check for exit signal
            signal = self.strategy.generate_signal(
                self._get_data_up_to_current(),
                current_position='long'
            )
            
            if signal.signal_type == SignalType.EXIT:
                self._close_position(candle, reason='strategy_exit')
                return
        
        else:
            # No position - check for entry signal
            signal = self.strategy.generate_signal(
                self._get_data_up_to_current(),
                current_position=None
            )
            
            if signal.signal_type == SignalType.LONG:
                self._open_position(candle, signal)
    
    def _open_position(self, candle: pd.Series, signal) -> None:
        """
        Open a new position.
        
        Args:
            candle: Current candle
            signal: Strategy signal with entry details
        """
        # Apply slippage to entry
        entry_price = signal.entry_price * (1 + self.slippage)
        
        # Use risk engine to calculate position size
        # For backtest, we create a temporary risk engine
        # (In practice, might want to maintain one risk engine instance)
        risk_engine = RiskEngine(self.capital)
        
        position_calc = risk_engine.calculate_position_size(
            entry_price=entry_price,
            stop_loss_price=signal.stop_loss or (entry_price * 0.98)
        )
        
        if not position_calc.is_valid:
            logger.debug(f"Position rejected: {position_calc.reason}")
            return
        
        # Validate trade through risk engine
        is_valid, reason = risk_engine.validate_trade(
            position_calc.size,
            position_calc.risk_amount,
            position_calc.risk_percent
        )
        
        if not is_valid:
            logger.debug(f"Trade rejected: {reason}")
            return
        
        # Create position
        self.current_position = Position(
            entry_time=candle['datetime'],
            entry_price=entry_price,
            entry_regime=candle['regime'],
            size=position_calc.size,
            stop_loss=signal.stop_loss or (entry_price * 0.98),
            side='long'
        )
        
        logger.info(
            f"📈 LONG @ ${entry_price:.2f}, "
            f"size=${position_calc.size:.2f}, "
            f"stop=${self.current_position.stop_loss:.2f}"
        )
    
    def _close_position(self, candle: pd.Series, reason: str) -> None:
        """
        Close current position and record trade.
        
        Args:
            candle: Current candle
            reason: Exit reason ('stop_loss', 'strategy_exit', 'end_of_data')
        """
        if self.current_position is None:
            return
        
        # Determine exit price based on reason
        if reason == 'stop_loss':
            # Fill at stop loss with slippage
            exit_price = self.current_position.stop_loss * (1 - self.slippage)
        else:
            # Fill at close with slippage
            exit_price = candle['close'] * (1 - self.slippage)
        
        # Create trade record
        trade = create_trade(
            trade_id=f"BT_{len(self.trades):04d}",
            entry_time=self.current_position.entry_time,
            entry_price=self.current_position.entry_price,
            entry_regime=self.current_position.entry_regime,
            exit_time=candle['datetime'],
            exit_price=exit_price,
            exit_regime=candle['regime'],
            exit_reason=reason,
            size=self.current_position.size,
            side='long',
            fee_rate=self.fee_rate
        )
        
        # Update with excursions
        trade.max_favorable_excursion = self.current_position.get_mfe()
        trade.max_adverse_excursion = self.current_position.get_mae()
        
        # Update capital
        self.capital += trade.pnl
        
        # Record trade
        self.trades.append(trade)
        
        logger.info(
            f"📉 EXIT @ ${exit_price:.2f}, "
            f"PnL=${trade.pnl:+.2f} ({trade.pnl_percent:+.2f}%), "
            f"{reason}"
        )
        
        # Clear position
        self.current_position = None
    
    def _get_data_up_to_current(self) -> pd.DataFrame:
        """
        Get data available up to current candle.
        
        This ensures no look-ahead bias.
        
        Returns:
            DataFrame with data up to and including current candle
        """
        return self.data.iloc[:self.current_index + 1].copy()
    
    def _create_result(self) -> BacktestResult:
        """
        Create BacktestResult from backtest execution.
        
        Returns:
            Complete BacktestResult
        """
        result = BacktestResult(
            start_date=self.data['datetime'].iloc[0],
            end_date=self.data['datetime'].iloc[-1],
            initial_capital=self.initial_capital,
            final_capital=self.capital,
            trades=self.trades
        )
        
        return result


def main():
    """Test backtest engine."""
    print("=" * 60)
    print("BACKTEST ENGINE TEST")
    print("=" * 60)
    
    from strategies.simple_trend import SimpleTrendStrategy
    from data.fetcher import DataFetcher
    
    # Check data availability
    fetcher = DataFetcher()
    count = fetcher.get_candle_count()
    
    if count < 100:
        print("\n⚠️  Insufficient data in database")
        print(f"   Have: {count} candles")
        print(f"   Need: 100+ candles")
        print("\nRun 'python data/fetcher.py' to fetch more data")
        return
    
    print(f"\n📊 Using {min(count, 1000)} candles for backtest")
    
    # Create strategy
    strategy = SimpleTrendStrategy()
    
    # Create backtest
    engine = BacktestEngine(
        strategy=strategy,
        initial_capital=500,
        data_limit=1000,
        slippage=0.001,
        fee_rate=0.00075
    )
    
    # Run backtest
    print("\n🔄 Running backtest...")
    result = engine.run()
    
    # Print results
    print("\n")
    result.print_summary()
    
    # Show sample trades
    if result.trades:
        print("\n📋 SAMPLE TRADES (first 5)")
        for trade in result.trades[:5]:
            print(f"   {trade}")
    
    print("\n" + "=" * 60)
    print("✅ Backtest engine test complete")


if __name__ == "__main__":
    main()