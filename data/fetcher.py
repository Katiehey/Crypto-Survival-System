"""
Market data fetcher using CCXT.

Handles:
- Fetching OHLCV candles from Binance
- Rate limit management
- Error handling and retries
- Storage to SQLite database
"""

import time
import sqlite3
from typing import List, Optional, Tuple
from datetime import datetime, timedelta, UTC
import ccxt
import pandas as pd

from config.system_config import SYSTEM_CONFIG
from config.exchange_config import get_exchange_config


class DataFetcher:
    """
    Fetches and stores market data from exchange.
    
    This class is responsible for:
    - Connecting to exchange via CCXT
    - Fetching OHLCV candles
    - Handling rate limits and errors
    - Storing data in SQLite
    """
    
    def __init__(self, db_path: str = None):
        """
        Initialize data fetcher.
        
        Args:
            db_path: Path to SQLite database
        """
        self.db_path = db_path or SYSTEM_CONFIG.DB_PATH
        self.exchange_config = get_exchange_config()
        self.exchange: Optional[ccxt.Exchange] = None
        
    def connect(self) -> None:
        """
        Connect to exchange.
        
        Raises:
            ValueError: If credentials not configured
            ccxt.NetworkError: If connection fails
        """
        if not self.exchange_config.has_credentials():
            raise ValueError(
                "Exchange credentials not configured. "
                "This is OK for testing, but required for fetching real data."
            )
        
        self.exchange = self.exchange_config.create_exchange()
        
        # Verify connection
        try:
            self.exchange.load_markets()
            print(f"✅ Connected to {self.exchange.name}")
        except Exception as e:
            raise ccxt.NetworkError(f"Failed to connect to exchange: {e}")
    
    def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str = '1h',
        limit: int = 100,
        since: Optional[int] = None
    ) -> List[List]:
        """
        Fetch OHLCV candles from exchange.
        
        Args:
            symbol: Trading pair (e.g., 'BTC/USDT')
            timeframe: Candle timeframe ('1m', '5m', '1h', '1d')
            limit: Number of candles to fetch
            since: Timestamp (ms) to fetch from
            
        Returns:
            List of OHLCV candles: [timestamp, open, high, low, close, volume]
            
        Raises:
            ccxt.NetworkError: If fetch fails
            ValueError: If exchange not connected
        """
        if self.exchange is None:
            raise ValueError("Exchange not connected. Call connect() first.")
        
        try:
            ohlcv = self.exchange.fetch_ohlcv(
                symbol=symbol,
                timeframe=timeframe,
                limit=limit,
                since=since
            )
            
            print(f"✅ Fetched {len(ohlcv)} candles for {symbol} ({timeframe})")
            return ohlcv
            
        except ccxt.RateLimitExceeded as e:
            print(f"⚠️  Rate limit exceeded. Waiting 60s...")
            time.sleep(60)
            return self.fetch_ohlcv(symbol, timeframe, limit, since)
            
        except ccxt.NetworkError as e:
            print(f"❌ Network error: {e}")
            raise
            
        except Exception as e:
            print(f"❌ Unexpected error fetching data: {e}")
            raise
    
    def store_ohlcv(
        self,
        symbol: str,
        timeframe: str,
        ohlcv: List[List]
    ) -> int:
        """
        Store OHLCV candles in database.
        
        Uses INSERT OR REPLACE to handle duplicates.
        
        Args:
            symbol: Trading pair
            timeframe: Candle timeframe
            ohlcv: List of candles [timestamp, o, h, l, c, v]
            
        Returns:
            Number of candles stored
        """
        if not ohlcv:
            print("⚠️  No candles to store")
            return 0
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        stored_count = 0
        
        for candle in ohlcv:
            timestamp, open_price, high, low, close, volume = candle
            
            try:
                cursor.execute("""
                    INSERT OR REPLACE INTO candles 
                    (symbol, timeframe, timestamp, open, high, low, close, volume, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    symbol,
                    timeframe,
                    timestamp,
                    open_price,
                    high,
                    low,
                    close,
                    volume,
                    datetime.now(UTC).isoformat()
                ))
                stored_count += 1
                
            except sqlite3.IntegrityError as e:
                # Duplicate entry, skip
                continue
        
        conn.commit()
        conn.close()
        
        print(f"✅ Stored {stored_count} candles in database")
        return stored_count
    
    def fetch_and_store(
        self,
        symbol: str = None,
        timeframe: str = None,
        limit: int = 100
    ) -> int:
        """
        Fetch OHLCV data and store in database.
        
        Convenience method combining fetch and store operations.
        
        Args:
            symbol: Trading pair (defaults to config)
            timeframe: Candle timeframe (defaults to config)
            limit: Number of candles to fetch
            
        Returns:
            Number of candles stored
        """
        symbol = symbol or SYSTEM_CONFIG.TRADING_PAIR
        timeframe = timeframe or SYSTEM_CONFIG.PRIMARY_TIMEFRAME
        
        # Connect if not already connected
        if self.exchange is None:
            self.connect()
        
        # Fetch data
        ohlcv = self.fetch_ohlcv(symbol, timeframe, limit)
        
        # Store data
        count = self.store_ohlcv(symbol, timeframe, ohlcv)
        
        return count
    
    def get_latest_timestamp(
        self,
        symbol: str,
        timeframe: str
    ) -> Optional[int]:
        """
        Get timestamp of most recent candle in database.
        
        Args:
            symbol: Trading pair
            timeframe: Candle timeframe
            
        Returns:
            Timestamp (ms) or None if no data exists
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT MAX(timestamp) FROM candles
            WHERE symbol = ? AND timeframe = ?
        """, (symbol, timeframe))
        
        result = cursor.fetchone()
        conn.close()
        
        return result[0] if result[0] else None
    
    def update_latest(
        self,
        symbol: str = None,
        timeframe: str = None
    ) -> int:
        """
        Update database with latest candles since last fetch.
        
        Args:
            symbol: Trading pair (defaults to config)
            timeframe: Candle timeframe (defaults to config)
            
        Returns:
            Number of new candles stored
        """
        symbol = symbol or SYSTEM_CONFIG.TRADING_PAIR
        timeframe = timeframe or SYSTEM_CONFIG.PRIMARY_TIMEFRAME
        
        # Get latest timestamp from database
        latest_ts = self.get_latest_timestamp(symbol, timeframe)
        
        if latest_ts:
            # Fetch from latest timestamp
            print(f"📊 Updating from {datetime.fromtimestamp(latest_ts/1000).isoformat()}")
            since = latest_ts + 1  # Start from next candle
        else:
            # No data exists, fetch recent history
            print(f"📊 No existing data, fetching initial history")
            since = None
        
        return self.fetch_and_store(symbol, timeframe, limit=500)
    
    def get_candle_count(
        self,
        symbol: str = None,
        timeframe: str = None
    ) -> int:
        """
        Get count of candles in database.
        
        Args:
            symbol: Trading pair (defaults to config)
            timeframe: Candle timeframe (defaults to config)
            
        Returns:
            Number of candles
        """
        symbol = symbol or SYSTEM_CONFIG.TRADING_PAIR
        timeframe = timeframe or SYSTEM_CONFIG.PRIMARY_TIMEFRAME
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT COUNT(*) FROM candles
            WHERE symbol = ? AND timeframe = ?
        """, (symbol, timeframe))
        
        count = cursor.fetchone()[0]
        conn.close()
        
        return count
    
    def load_candles(
        self,
        symbol: str = None,
        timeframe: str = None,
        limit: int = None
    ) -> pd.DataFrame:
        """
        Load candles from database as pandas DataFrame.
        
        Args:
            symbol: Trading pair (defaults to config)
            timeframe: Candle timeframe (defaults to config)
            limit: Max number of candles (most recent)
            
        Returns:
            DataFrame with OHLCV data
        """
        symbol = symbol or SYSTEM_CONFIG.TRADING_PAIR
        timeframe = timeframe or SYSTEM_CONFIG.PRIMARY_TIMEFRAME
        
        conn = sqlite3.connect(self.db_path)
        
        query = """
            SELECT timestamp, open, high, low, close, volume
            FROM candles
            WHERE symbol = ? AND timeframe = ?
            ORDER BY timestamp DESC
        """
        
        if limit:
            query += f" LIMIT {limit}"
        
        df = pd.read_sql_query(query, conn, params=(symbol, timeframe))
        conn.close()
        
        # Sort chronologically (oldest first)
        df = df.sort_values('timestamp').reset_index(drop=True)
        
        # Convert timestamp to datetime
        df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')
        
        return df


def main():
    """
    Command-line interface for data fetcher.
    
    Usage:
        python data/fetcher.py
    """
    print("=" * 60)
    print("DATA FETCHER")
    print("=" * 60)
    
    fetcher = DataFetcher()
    
    # Check existing data
    count = fetcher.get_candle_count()
    print(f"\n📊 Current data: {count} candles")
    
    if count > 0:
        latest = fetcher.get_latest_timestamp(
            SYSTEM_CONFIG.TRADING_PAIR,
            SYSTEM_CONFIG.PRIMARY_TIMEFRAME
        )
        latest_dt = datetime.fromtimestamp(latest / 1000)
        print(f"📅 Latest candle: {latest_dt.isoformat()}")
    
    # Fetch new data
    print(f"\n🔄 Fetching data for {SYSTEM_CONFIG.TRADING_PAIR}...")
    
    try:
        fetcher.connect()
        new_count = fetcher.update_latest()
        
        print(f"\n✅ Update complete")
        print(f"📊 Total candles: {fetcher.get_candle_count()}")
        
    except ValueError as e:
        print(f"\n⚠️  {e}")
        print("Set BINANCE_API_KEY and BINANCE_API_SECRET in .env to fetch data")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")


if __name__ == "__main__":
    main()