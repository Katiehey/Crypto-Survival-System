"""
Historical data loader for backtesting.

Loads OHLCV data, calculates features, and classifies regimes.
Ensures no look-ahead bias.
"""

from datetime import datetime
from typing import Optional, Tuple
import pandas as pd
import logging

from data.fetcher import DataFetcher
from regime.features import calculate_complete_pipeline
from config.system_config import SYSTEM_CONFIG

logger = logging.getLogger(__name__)


class BacktestDataLoader:
    """
    Load and prepare historical data for backtesting.
    
    Responsibilities:
    - Load OHLCV candles from database
    - Calculate features chronologically
    - Classify regimes without look-ahead bias
    - Validate data quality
    """
    
    def __init__(
        self,
        symbol: str = None,
        timeframe: str = None,
        db_path: str = None
    ):
        """
        Initialize data loader.
        
        Args:
            symbol: Trading pair (defaults to config)
            timeframe: Candle timeframe (defaults to config)
            db_path: Database path (defaults to config)
        """
        self.symbol = symbol or SYSTEM_CONFIG.TRADING_PAIR
        self.timeframe = timeframe or SYSTEM_CONFIG.PRIMARY_TIMEFRAME
        self.db_path = db_path or SYSTEM_CONFIG.DB_PATH
        
        self.fetcher = DataFetcher(db_path=self.db_path)
        
        logger.info(
            f"BacktestDataLoader initialized: {self.symbol} {self.timeframe}"
        )
    
    def load_data(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: Optional[int] = None
    ) -> pd.DataFrame:
        """
        Load historical OHLCV data.
        
        Args:
            start_date: Start of backtest period
            end_date: End of backtest period
            limit: Maximum number of candles (if dates not specified)
            
        Returns:
            DataFrame with OHLCV data
            
        Raises:
            ValueError: If insufficient data available
        """
        logger.info("Loading historical data...")
        
        # Load from database
        df = self.fetcher.load_candles(
            symbol=self.symbol,
            timeframe=self.timeframe,
            limit=limit
        )
        
        if df.empty:
            raise ValueError("No data available in database")
        
        # Filter by date range if provided
        if start_date is not None:
            df = df[df['datetime'] >= start_date]
        
        if end_date is not None:
            df = df[df['datetime'] <= end_date]
        
        if df.empty:
            raise ValueError(
                f"No data available for period {start_date} to {end_date}"
            )
        
        logger.info(
            f"Loaded {len(df)} candles: "
            f"{df['datetime'].iloc[0]} to {df['datetime'].iloc[-1]}"
        )
        
        return df
    
    def prepare_data(
        self,
        df: pd.DataFrame,
        validate: bool = True
    ) -> pd.DataFrame:
        """
        Prepare data for backtesting.
        
        Calculates features and regimes chronologically to avoid look-ahead bias.
        
        Args:
            df: Raw OHLCV DataFrame
            validate: Whether to validate data quality
            
        Returns:
            DataFrame with features and regimes
            
        Raises:
            ValueError: If data validation fails
        """
        if validate:
            self._validate_data(df)
        
        logger.info("Calculating features and regimes...")
        
        # Calculate complete pipeline
        # This includes features + regime classification
        df = calculate_complete_pipeline(df)
        
        logger.info(f"Features and regimes calculated for {len(df)} candles")
        
        return df
    
    def load_and_prepare(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: Optional[int] = None
    ) -> pd.DataFrame:
        """
        Load and prepare data in one step.
        
        Convenience method combining load_data() and prepare_data().
        
        Args:
            start_date: Start of backtest period
            end_date: End of backtest period
            limit: Maximum number of candles
            
        Returns:
            Complete DataFrame ready for backtesting
        """
        # Load raw data
        df = self.load_data(start_date, end_date, limit)
        
        # Prepare (features + regimes)
        df = self.prepare_data(df)
        
        return df
    
    def _validate_data(self, df: pd.DataFrame) -> None:
        """
        Validate data quality.
        
        Checks:
        - Required columns present
        - No missing critical data
        - Prices are positive
        - Data is chronological
        - No duplicate timestamps
        
        Args:
            df: DataFrame to validate
            
        Raises:
            ValueError: If validation fails
        """
        logger.info("Validating data quality...")
        
        # Check required columns
        required = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
        missing = [col for col in required if col not in df.columns]
        
        if missing:
            raise ValueError(f"Missing required columns: {missing}")
        
        # Check for empty data
        if len(df) == 0:
            raise ValueError("DataFrame is empty")
        
        # Check for NaN in critical columns
        critical_cols = ['close', 'high', 'low', 'volume']
        for col in critical_cols:
            nan_count = df[col].isna().sum()
            if nan_count > 0:
                logger.warning(f"Found {nan_count} NaN values in {col}")
        
        # Check prices are positive
        price_cols = ['open', 'high', 'low', 'close']
        for col in price_cols:
            if (df[col] <= 0).any():
                raise ValueError(f"Found non-positive prices in {col}")
        
        # Check chronological order
        if not df['timestamp'].is_monotonic_increasing:
            raise ValueError("Data is not in chronological order")
        
        # Check for duplicates
        duplicates = df['timestamp'].duplicated().sum()
        if duplicates > 0:
            raise ValueError(f"Found {duplicates} duplicate timestamps")
        
        # Check for gaps (optional warning)
        if 'datetime' in df.columns:
            time_diffs = df['datetime'].diff()
            # Expected diff (1 hour for 1h timeframe)
            # More sophisticated gap detection could be added here
            
        logger.info("✅ Data validation passed")
    
    def get_data_summary(self, df: pd.DataFrame) -> dict:
        """
        Get summary statistics about the data.
        
        Args:
            df: DataFrame to summarize
            
        Returns:
            Dictionary with summary statistics
        """
        summary = {
            'total_candles': len(df),
            'start_date': df['datetime'].iloc[0] if 'datetime' in df.columns else None,
            'end_date': df['datetime'].iloc[-1] if 'datetime' in df.columns else None,
            'price_range': {
                'min': df['low'].min(),
                'max': df['high'].max(),
                'start': df['open'].iloc[0],
                'end': df['close'].iloc[-1],
            },
            'volume': {
                'mean': df['volume'].mean(),
                'total': df['volume'].sum(),
            }
        }
        
        # Add regime distribution if available
        if 'regime' in df.columns:
            summary['regime_distribution'] = df['regime'].value_counts().to_dict()
        
        return summary


def main():
    """Test data loader."""
    print("=" * 60)
    print("BACKTEST DATA LOADER TEST")
    print("=" * 60)
    
    loader = BacktestDataLoader()
    
    # Check available data
    count = loader.fetcher.get_candle_count()
    print(f"\n📊 Available data: {count} candles")
    
    if count == 0:
        print("\n⚠️  No data in database")
        print("Run 'python data/fetcher.py' first to fetch data")
        return
    
    # Load recent data
    print("\n📥 Loading data (last 1000 candles)...")
    df = loader.load_and_prepare(limit=5000)
    
    print(f"✅ Loaded and prepared {len(df)} candles")
    
    # Summary
    summary = loader.get_data_summary(df)
    
    print("\n📊 DATA SUMMARY")
    print(f"   Period: {summary['start_date']} to {summary['end_date']}")
    print(f"   Candles: {summary['total_candles']}")
    print(f"   Price range: ${summary['price_range']['min']:.0f} - ${summary['price_range']['max']:.0f}")
    
    if 'regime_distribution' in summary:
        print("\n   Regime distribution:")
        for regime, count in summary['regime_distribution'].items():
            pct = count / summary['total_candles'] * 100
            print(f"     {regime:10s}: {count:3d} ({pct:5.1f}%)")
    
    # Show sample
    print("\n📋 SAMPLE DATA (last 5 candles)")
    cols = ['datetime', 'close', 'regime', 'regime_confidence', 'regime_tradable']
    print(df[cols].tail(5).to_string(index=False))
    
    print("\n" + "=" * 60)
    print("✅ Data loader test complete")


if __name__ == "__main__":
    main()