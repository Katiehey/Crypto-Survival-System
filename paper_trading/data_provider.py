# paper_trading/data_provider.py
"""
Data providers for paper trading system.
Provides historical and simulated real-time data.
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Optional, Dict, List
import logging

logger = logging.getLogger(__name__)


class BaseDataProvider:
    """Base class for data providers."""
    
    def __init__(self, symbol: str = "BTC/USDT", timeframe: str = "1h"):
        """
        Initialize data provider.
        
        Args:
            symbol: Trading pair
            timeframe: Candle timeframe
        """
        self.symbol = symbol
        self.timeframe = timeframe
        self.data_cache = {}
    
    def get_historical_data(self, limit: int = 1000, 
                          start_date: Optional[datetime] = None,
                          end_date: Optional[datetime] = None) -> pd.DataFrame:
        """
        Get historical data.
        
        Args:
            limit: Number of candles
            start_date: Start date
            end_date: End date
            
        Returns:
            DataFrame with OHLCV data
        """
        raise NotImplementedError
    
    def get_latest_candle(self) -> Optional[Dict]:
        """
        Get latest candle for live trading.
        
        Returns:
            Latest candle as dictionary, or None if not available
        """
        raise NotImplementedError
    
    def get_current_price(self) -> Optional[float]:
        """
        Get current market price.
        
        Returns:
            Current price, or None if not available
        """
        raise NotImplementedError


class HistoricalDataProvider(BaseDataProvider):
    """
    Historical data provider using existing database.
    """
    
    def __init__(self, db_path: str = None, **kwargs):
        """
        Initialize historical data provider.
        
        Args:
            db_path: Path to SQLite database
        """
        super().__init__(**kwargs)
        self.db_path = db_path
        
        # Try to import the data fetcher
        try:
            from data.fetcher import DataFetcher
            self.fetcher = DataFetcher(db_path=db_path)
        except ImportError:
            logger.warning("DataFetcher not available. Using simulated data.")
            self.fetcher = None
    
    def get_historical_data(self, limit: int = 1000, 
                          start_date: Optional[datetime] = None,
                          end_date: Optional[datetime] = None) -> pd.DataFrame:
        """
        Get historical data from database.
        
        Args:
            limit: Number of candles
            start_date: Start date
            end_date: End date
            
        Returns:
            DataFrame with OHLCV data
        """
        cache_key = f"{self.symbol}_{self.timeframe}_{limit}_{start_date}_{end_date}"

        if cache_key in self.data_cache:
            logger.debug(f"Using cached data for {cache_key}")
            return self.data_cache[cache_key].copy()

        if self.fetcher:
            # Load real data from the DB
            try:
                df = self.fetcher.load_candles(
                    symbol=self.symbol,
                    timeframe=self.timeframe,
                    limit=limit
                )

                if df is None or df.empty:
                    logger.warning(f"No candles found for {self.symbol} {self.timeframe}, using simulated data")
                    df = self._generate_simulated_data(limit, start_date, end_date)
                    self.data_cache[cache_key] = df.copy()
                    return df

                # Ensure datetime column exists and is of type datetime
                if 'datetime' not in df.columns:
                    if 'timestamp' in df.columns:
                        df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')
                    else:
                        logger.warning("No timestamp column present; adding synthetic datetime")
                        df['datetime'] = pd.to_datetime(df.index)

                # Apply date filters if provided
                if start_date is not None:
                    df = df[df['datetime'] >= start_date].reset_index(drop=True)
                if end_date is not None:
                    df = df[df['datetime'] <= end_date].reset_index(drop=True)

                # Add features and regime classification if absent
                if 'regime' not in df.columns or 'atr' not in df.columns:
                    try:
                        from regime.features import calculate_complete_pipeline
                        logger.info(f"Calculating features for {len(df)} candles")
                        df = calculate_complete_pipeline(df)
                    except Exception as e:
                        logger.warning(f"Feature pipeline failed: {e}; filling minimal defaults")
                        if 'regime' not in df.columns:
                            df['regime'] = 'trend'
                        if 'atr' not in df.columns:
                            df['atr'] = (df['high'] - df['low']).abs().rolling(14, min_periods=1).mean()

                # Cache and return
                self.data_cache[cache_key] = df.copy()
                logger.info(f"Loaded {len(df)} candles of historical data")
                return df

            except Exception as e:
                logger.error(f"Error loading historical data via DataFetcher: {e}. Trying direct DB read.")
                # Fall through to direct DB attempt below
        # If DataFetcher unavailable or failed, attempt direct SQLite read from db_path
        try:
            import sqlite3
            db_path = self.db_path or 'trading.db'
            # If a common local data path exists, prefer it
            import os
            if not os.path.exists(db_path) and os.path.exists('data/trading.db'):
                db_path = 'data/trading.db'

            conn = sqlite3.connect(db_path)
            query = """
                SELECT timestamp, open, high, low, close, volume
                FROM candles
                WHERE symbol = ? AND timeframe = ?
                ORDER BY timestamp DESC
                LIMIT ?
            """
            df = pd.read_sql_query(query, conn, params=(self.symbol, self.timeframe, limit))
            conn.close()

            if df is None or df.empty:
                logger.warning(f"No candles found in DB at {db_path} for {self.symbol} {self.timeframe}; using simulated data")
                df = self._generate_simulated_data(limit, start_date, end_date)
                self.data_cache[cache_key] = df.copy()
                return df

            df = df.sort_values('timestamp').reset_index(drop=True)
            df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')

            # Add minimal features if missing
            if 'regime' not in df.columns or 'atr' not in df.columns:
                try:
                    from regime.features import calculate_complete_pipeline
                    logger.info(f"Calculating features for {len(df)} candles (direct DB)")
                    df = calculate_complete_pipeline(df)
                except Exception:
                    if 'regime' not in df.columns:
                        df['regime'] = 'trend'
                    if 'atr' not in df.columns:
                        df['atr'] = (df['high'] - df['low']).abs().rolling(14, min_periods=1).mean()

            self.data_cache[cache_key] = df.copy()
            logger.info(f"Loaded {len(df)} candles from DB at {db_path}")
            return df
        except Exception as e:
            logger.warning(f"Direct DB read failed: {e}; falling back to simulated data")
            df = self._generate_simulated_data(limit, start_date, end_date)
            self.data_cache[cache_key] = df.copy()
            return df
        
    
    def _generate_simulated_data(self, limit: int = 1000,
                               start_date: Optional[datetime] = None,
                               end_date: Optional[datetime] = None) -> pd.DataFrame:
        """Generate simulated market data for testing."""
        np.random.seed(42)
        
        if not start_date:
            start_date = datetime.now() - timedelta(hours=limit)
        if not end_date:
            end_date = datetime.now()
        
        # Generate time series
        time_delta = (end_date - start_date) / limit
        timestamps = [start_date + i * time_delta for i in range(limit)]
        
        # Generate price series (random walk with drift)
        returns = np.random.normal(0.0001, 0.01, limit)  # 1% daily volatility
        price = 42000 * np.exp(np.cumsum(returns))
        
        # Generate OHLCV
        data = []
        for i in range(limit):
            base_price = price[i]
            high = base_price * (1 + abs(np.random.normal(0, 0.005)))
            low = base_price * (1 - abs(np.random.normal(0, 0.005)))
            open_price = base_price * (1 + np.random.normal(0, 0.002))
            close = base_price
            volume = np.random.lognormal(10, 1)  # Log-normal volume
            
            data.append({
                'timestamp': int(timestamps[i].timestamp() * 1000),
                'datetime': timestamps[i],
                'open': open_price,
                'high': high,
                'low': low,
                'close': close,
                'volume': volume
            })
        
        df = pd.DataFrame(data)

        # Add minimal regime placeholders for compatibility
        df['regime'] = np.random.choice(['trend', 'range', 'chaos'], len(df), p=[0.4, 0.5, 0.1])
        df['regime_confidence'] = np.random.uniform(0.6, 0.9, len(df))
        df['regime_tradable'] = df['regime'].isin(['trend', 'range'])

        # Ensure simulated data provides the same feature columns as historical data
        # by running the full pipeline. This keeps `--mode simulated` behavior
        # consistent with `HistoricalDataProvider` and allows strategies to run
        # without requiring a DB.
        try:
            from regime.features import calculate_complete_pipeline
            df_processed = calculate_complete_pipeline(df)
            return df_processed
        except Exception:
            # If pipeline fails for any reason, return the minimal frame
            # (strategy validation will catch missing columns earlier).
            return df
    
    def get_latest_candle(self) -> Optional[Dict]:
        """Get latest candle (not implemented for historical)."""
        logger.warning("get_latest_candle not implemented for HistoricalDataProvider")
        return None
    
    def get_current_price(self) -> Optional[float]:
        """Get current price (not implemented for historical)."""
        return None


class LiveDataProvider(BaseDataProvider):
    """
    Live data provider using CCXT (for real paper trading).
    """
    
    def __init__(self, exchange_config=None, **kwargs):
        """
        Initialize live data provider.
        
        Args:
            exchange_config: Exchange configuration
        """
        super().__init__(**kwargs)
        self.exchange_config = exchange_config
        self.exchange = None
        self.last_candle = None
        
        self._initialize_exchange()
    
    def _initialize_exchange(self):
        """Initialize exchange connection."""
        try:
            import ccxt
            from config.exchange_config import get_exchange_config
            
            config = self.exchange_config or get_exchange_config()
            self.exchange = config.create_exchange()
            
            # Test connection
            self.exchange.load_markets()
            logger.info(f"Connected to {self.exchange.name} for live data")
            
        except Exception as e:
            logger.error(f"Failed to initialize exchange: {e}")
            self.exchange = None
    
    def get_historical_data(self, limit: int = 1000, 
                          start_date: Optional[datetime] = None,
                          end_date: Optional[datetime] = None) -> pd.DataFrame:
        """
        Get recent historical data from exchange.
        
        Args:
            limit: Number of candles
            start_date: Start date
            end_date: End date
            
        Returns:
            DataFrame with OHLCV data
        """
        if not self.exchange:
            logger.error("Exchange not initialized")
            return pd.DataFrame()
        
        try:
            # Convert dates to timestamps
            since = None
            if start_date:
                since = int(start_date.timestamp() * 1000)
            
            # Fetch OHLCV
            ohlcv = self.exchange.fetch_ohlcv(
                symbol=self.symbol,
                timeframe=self.timeframe,
                limit=limit,
                since=since
            )
            
            # Convert to DataFrame
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')
            
            logger.info(f"Fetched {len(df)} live candles from exchange")
            return df
            
        except Exception as e:
            logger.error(f"Error fetching historical data: {e}")
            return pd.DataFrame()
    
    def get_latest_candle(self) -> Optional[Dict]:
        """
        Get the latest candle from exchange.
        
        Returns:
            Latest candle as dictionary
        """
        if not self.exchange:
            return None
        
        try:
            # Fetch latest candle
            ohlcv = self.exchange.fetch_ohlcv(
                symbol=self.symbol,
                timeframe=self.timeframe,
                limit=1
            )
            
            if not ohlcv:
                return None
            
            candle = ohlcv[0]
            self.last_candle = {
                'timestamp': candle[0],
                'datetime': datetime.fromtimestamp(candle[0] / 1000),
                'open': candle[1],
                'high': candle[2],
                'low': candle[3],
                'close': candle[4],
                'volume': candle[5]
            }

            historical_context = self.get_historical_data(limit=100)
            if not historical_context.empty:
                from regime.features import calculate_complete_pipeline
                processed_df = calculate_complete_pipeline(historical_context)
                latest_row = processed_df.iloc[-1]
            
                self.last_candle['regime'] = latest_row['regime']
                self.last_candle['regime_confidence'] = latest_row.get('regime_confidence', 0.8)
            
            return self.last_candle
            
        except Exception as e:
            logger.error(f"Error fetching latest candle: {e}")
            return None
    
    def get_current_price(self) -> Optional[float]:
        """
        Get current market price.
        
        Returns:
            Current price
        """
        if not self.exchange:
            return None
        
        try:
            ticker = self.exchange.fetch_ticker(self.symbol)
            return ticker['last']
        except Exception as e:
            logger.error(f"Error fetching current price: {e}")
            
            # Fallback to last candle
            if self.last_candle:
                return self.last_candle['close']
            
            return None


class SimulatedDataProvider(BaseDataProvider):
    """
    Simulated data provider for testing without external dependencies.
    Generates realistic market data in real-time simulation.
    """
    
    def __init__(self, initial_price: float = 42000, volatility: float = 0.01, **kwargs):
        """
        Initialize simulated data provider.
        
        Args:
            initial_price: Starting price
            volatility: Price volatility (daily)
        """
        super().__init__(**kwargs)
        self.initial_price = initial_price
        self.volatility = volatility
        self.current_price = initial_price
        self.data_history = []
        self.start_time = datetime.now()
        
        # Generate initial history
        self._generate_initial_history()
    
    def _generate_initial_history(self, num_candles: int = 100):
        """Generate initial history."""
        np.random.seed(42)
        
        prices = [self.initial_price]
        for i in range(1, num_candles):
            return_val = np.random.normal(0, self.volatility / np.sqrt(24))  # Hourly volatility
            prices.append(prices[-1] * (1 + return_val))
        
        # Create candles
        for i in range(num_candles):
            base_price = prices[i]
            candle_time = self.start_time - timedelta(hours=num_candles - i)
            
            candle = {
                'timestamp': int(candle_time.timestamp() * 1000),
                'datetime': candle_time,
                'open': base_price * (1 + np.random.normal(0, 0.002)),
                'high': base_price * (1 + abs(np.random.normal(0, 0.005))),
                'low': base_price * (1 - abs(np.random.normal(0, 0.005))),
                'close': base_price,
                'volume': np.random.lognormal(10, 1)
            }
            
            self.data_history.append(candle)
    
    def get_historical_data(self, limit: int = 1000, 
                          start_date: Optional[datetime] = None,
                          end_date: Optional[datetime] = None) -> pd.DataFrame:
        """
        Get historical simulated data.
        
        Args:
            limit: Number of candles
            start_date: Start date
            end_date: End date
            
        Returns:
            DataFrame with OHLCV data
        """
        # Filter by date if provided
        filtered_history = self.data_history.copy()
        
        if start_date:
            filtered_history = [c for c in filtered_history if c['datetime'] >= start_date]
        if end_date:
            filtered_history = [c for c in filtered_history if c['datetime'] <= end_date]
        
        # Limit results
        if limit and len(filtered_history) > limit:
            filtered_history = filtered_history[-limit:]
        
        # Convert to DataFrame
        df = pd.DataFrame(filtered_history)
        
        if len(df) > 0:
            # Add regime features
            df['regime'] = np.random.choice(['trend', 'range', 'chaos'], len(df), p=[0.4, 0.5, 0.1])
            df['regime_confidence'] = np.random.uniform(0.6, 0.9, len(df))
            df['regime_tradable'] = df['regime'].isin(['trend', 'range'])

            # Try to compute full feature set so strategies can run on simulated data
            try:
                from regime.features import calculate_complete_pipeline
                df = calculate_complete_pipeline(df)
            except Exception:
                # If the pipeline fails, return the minimal frame — callers will handle validation
                pass

        return df
    
    def get_latest_candle(self) -> Optional[Dict]:
        """
        Generate and return latest simulated candle.
        
        Returns:
            Latest candle as dictionary
        """
        # Update price with random walk
        return_val = np.random.normal(0, self.volatility / np.sqrt(24))
        self.current_price *= (1 + return_val)
        
        # Create new candle
        current_time = datetime.now()
        candle = {
            'timestamp': int(current_time.timestamp() * 1000),
            'datetime': current_time,
            'open': self.current_price * (1 + np.random.normal(0, 0.002)),
            'high': self.current_price * (1 + abs(np.random.normal(0, 0.005))),
            'low': self.current_price * (1 - abs(np.random.normal(0, 0.005))),
            'close': self.current_price,
            'volume': np.random.lognormal(10, 1),
            'regime': np.random.choice(['trend', 'range', 'chaos'], p=[0.4, 0.5, 0.1]),
            'regime_confidence': np.random.uniform(0.6, 0.9),
            'regime_tradable': True
        }
        
        # Add to history
        self.data_history.append(candle)
        
        # Keep history manageable
        if len(self.data_history) > 10000:
            self.data_history = self.data_history[-5000:]
        
        return candle
    
    def get_current_price(self) -> Optional[float]:
        """
        Get current simulated price.
        
        Returns:
            Current price
        """
        return self.current_price


def create_data_provider(provider_type: str = "historical", **kwargs) -> BaseDataProvider:
    """
    Factory function to create data providers.
    
    Args:
        provider_type: Type of provider ('historical', 'live', 'simulated')
        **kwargs: Provider-specific arguments
        
    Returns:
        Data provider instance
    """
    if provider_type == "historical":
        return HistoricalDataProvider(**kwargs)
    elif provider_type == "live":
        return LiveDataProvider(**kwargs)
    elif provider_type == "simulated":
        return SimulatedDataProvider(**kwargs)
    else:
        raise ValueError(f"Unknown provider type: {provider_type}")


def main():
    """Test data providers."""
    print("=" * 70)
    print("DATA PROVIDER TEST")
    print("=" * 70)
    
    # Test historical provider
    print("\n1. Testing HistoricalDataProvider...")
    hist_provider = HistoricalDataProvider(symbol="BTC/USDT", timeframe="1h")
    
    hist_data = hist_provider.get_historical_data(limit=10)
    print(f"   Historical data shape: {hist_data.shape}")
    if not hist_data.empty:
        print(f"   Latest candle: {hist_data.iloc[-1]['datetime']}, "
              f"Price: ${hist_data.iloc[-1]['close']:.2f}")
    
    # Test simulated provider
    print("\n2. Testing SimulatedDataProvider...")
    sim_provider = SimulatedDataProvider(symbol="BTC/USDT", timeframe="1h")
    
    sim_data = sim_provider.get_historical_data(limit=5)
    print(f"   Simulated data shape: {sim_data.shape}")
    
    latest_candle = sim_provider.get_latest_candle()
    if latest_candle:
        print(f"   Latest simulated candle: {latest_candle['datetime']}, "
              f"Price: ${latest_candle['close']:.2f}")
    
    # Test factory function
    print("\n3. Testing factory function...")
    
    providers = ["historical", "simulated"]
    for provider_type in providers:
        try:
            provider = create_data_provider(provider_type, symbol="BTC/USDT")
            data = provider.get_historical_data(limit=3)
            print(f"   {provider_type}: {len(data)} candles loaded")
        except Exception as e:
            print(f"   {provider_type}: Error - {e}")
    
    print("\n✅ Data provider test complete")
    print("=" * 70)


if __name__ == "__main__":
    main()