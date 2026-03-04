# paper_trading/live_feed.py
"""
Live market data feed using CCXT for paper trading.
"""

import time
import threading
import queue
from datetime import datetime
from typing import Dict, Optional, List, Callable
import logging

logger = logging.getLogger(__name__)


class LiveDataFeed:
    """
    Live market data feed using CCXT.
    
    Features:
    - Real-time candle updates
    - Ticker data for current prices
    - Order book depth (optional)
    - Reconnection logic
    - Data buffering
    """
    
    def __init__(
        self,
        symbol: str = "BTC/USDT",
        timeframe: str = "1h",
        exchange_config=None,
        update_interval: int = 5,  # seconds between updates
        max_retries: int = 3,
        retry_delay: int = 5
    ):
        """
        Initialize live data feed.
        
        Args:
            symbol: Trading pair
            timeframe: Candle timeframe
            exchange_config: Exchange configuration
            update_interval: Seconds between updates
            max_retries: Maximum retry attempts
            retry_delay: Delay between retries in seconds
        """
        self.symbol = symbol
        self.timeframe = timeframe
        self.exchange_config = exchange_config
        self.update_interval = update_interval
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        
        # Data storage
        self.current_candle = None
        self.candle_history = []
        self.ticker_data = None
        self.order_book = None
        self._lock = threading.Lock()
        
        # State
        self.is_running = False
        self.thread = None
        self.data_queue = queue.Queue()
        self.subscribers = []
        
        # Exchange connection
        self.exchange = None
        self._initialize_exchange()
        
        logger.info(f"LiveDataFeed initialized: {symbol} {timeframe}")
    
    def _initialize_exchange(self):
        """Initialize exchange connection."""
        try:
            import ccxt
            from config.exchange_config import get_exchange_config
            
            config = self.exchange_config or get_exchange_config()
            self.exchange = config.create_exchange()
            
            # Test connection
            try:
                self.exchange.load_markets()
            except Exception as e:
                # If authentication failed (e.g., invalid API key) but we still
                # want public market data for paper trading, fall back to a
                # public-only exchange instance (no credentials).
                msg = str(e)
                logger.warning(f"⚠️  Exchange load_markets failed: {msg}. Falling back to public-only exchange.")
                try:
                    # Create a public-only exchange instance
                    self.exchange = ccxt.binance()
                    self.exchange.enableRateLimit = True
                    self.exchange.load_markets()
                except Exception as e2:
                    logger.error(f"❌ Failed to initialize public exchange fallback: {e2}")
                    raise
            
            # Set rate limit to avoid issues
            self.exchange.enableRateLimit = True
            
            logger.info(f"✅ Connected to {self.exchange.name}")
            
        except ImportError:
            logger.error("❌ CCXT not installed. Install with: pip install ccxt")
            self.exchange = None
        except Exception as e:
            logger.error(f"❌ Failed to initialize exchange: {e}")
            self.exchange = None
    
    def start(self):
        """Start live data feed."""
        if not self.exchange:
            logger.error("❌ Cannot start: Exchange not initialized")
            return False
        
        if self.is_running:
            logger.warning("⚠️  Data feed already running")
            return True
        
        self.is_running = True
        self.thread = threading.Thread(target=self._run_feed, daemon=True)
        self.thread.start()
        
        logger.info("✅ Live data feed started")
        return True
    
    def stop(self):
        """Stop live data feed."""
        self.is_running = False
        if self.thread:
            self.thread.join(timeout=5)
            self.thread = None
        
        logger.info("✅ Live data feed stopped")
    
    def _run_feed(self):
        """Main feed loop."""
        retry_count = 0
        
        while self.is_running and retry_count < self.max_retries:
            try:
                # Fetch latest candle
                self._fetch_latest_candle()
                
                # Fetch ticker data
                self._fetch_ticker()
                
                # Fetch order book (optional)
                # self._fetch_order_book()
                
                # Reset retry count on success
                retry_count = 0
                
                # Notify subscribers
                self._notify_subscribers()
                
                # Wait for next update
                time.sleep(self.update_interval)
                
            except Exception as e:
                logger.error(f"❌ Error in data feed: {e}")
                retry_count += 1
                
                if retry_count < self.max_retries:
                    logger.info(f"⚠️  Retrying in {self.retry_delay} seconds...")
                    time.sleep(self.retry_delay)
                else:
                    logger.error(f"❌ Max retries exceeded. Stopping feed.")
                    self.is_running = False
    
    def _fetch_latest_candle(self):
        """Fetch latest candle from exchange."""
        try:
            # Fetch latest candle
            candles = self.exchange.fetch_ohlcv(
                symbol=self.symbol,
                timeframe=self.timeframe,
                limit=2
            )
            
            if candles and len(candles) > 0:
                candles = self.exchange.fetch_ohlcv(self.symbol, self.timeframe, limit=2)
                if not candles: return

        # candle format: [timestamp, open, high, low, close, volume]
                c = candles[-1]
                new_candle = {
                    'timestamp': c[0],
                    'datetime': datetime.fromtimestamp(c[0] / 1000),
                    'open': c[1], 'high': c[2], 'low': c[3], 'close': c[4], 'volume': c[5]
                }

                with self._lock:
            # Only append if it's a NEW timestamp
                    if not self.candle_history or new_candle['timestamp'] > self.candle_history[-1]['timestamp']:
                        self.candle_history.append(new_candle)
                    else:
                # Update the existing "live" candle with latest data
                        self.candle_history[-1] = new_candle
            
                    self.current_candle = new_candle
            
            # Keep history size managed
                    if len(self.candle_history) > 1000:
                        self.candle_history = self.candle_history[-1000:]
                
                logger.debug(f"📊 New candle: {self.current_candle['datetime']}, "
                           f"Price: ${self.current_candle['close']:.2f}")
                
        except Exception as e:
            logger.error(f"❌ Error fetching candle: {e}")
            raise
    
    def _fetch_ticker(self):
        """Fetch ticker data from exchange."""
        try:
            ticker = self.exchange.fetch_ticker(self.symbol)
            
            self.ticker_data = {
                'timestamp': ticker.get('timestamp'),
                'datetime': datetime.fromtimestamp(ticker.get('timestamp') / 1000) 
                            if ticker.get('timestamp') else datetime.now(),
                'last': ticker.get('last'),
                'bid': ticker.get('bid'),
                'ask': ticker.get('ask'),
                'high': ticker.get('high'),
                'low': ticker.get('low'),
                'volume': ticker.get('quoteVolume'),
                'change': ticker.get('percentage'),
                'symbol': self.symbol
            }
            
        except Exception as e:
            logger.error(f"❌ Error fetching ticker: {e}")
            # Don't raise - ticker is less critical than candles
    
    def _fetch_order_book(self):
        """Fetch order book data (optional)."""
        try:
            order_book = self.exchange.fetch_order_book(self.symbol, limit=10)
            
            self.order_book = {
                'timestamp': order_book.get('timestamp'),
                'datetime': datetime.fromtimestamp(order_book.get('timestamp') / 1000) 
                           if order_book.get('timestamp') else datetime.now(),
                'bids': order_book.get('bids', [])[:5],  # Top 5 bids
                'asks': order_book.get('asks', [])[:5],  # Top 5 asks
                'bid_volume': sum(bid[1] for bid in order_book.get('bids', [])[:5]),
                'ask_volume': sum(ask[1] for ask in order_book.get('asks', [])[:5]),
                'spread': order_book.get('asks', [[0, 0]])[0][0] - order_book.get('bids', [[0, 0]])[0][0]
            }
            
        except Exception as e:
            logger.debug(f"Order book fetch failed (normal for rate limits): {e}")
    
    def subscribe(self, callback: Callable):
        """
        Subscribe to data updates.
        
        Args:
            callback: Function to call with new data
        """
        if callback not in self.subscribers:
            self.subscribers.append(callback)
            logger.debug(f"New subscriber added. Total: {len(self.subscribers)}")
    
    def unsubscribe(self, callback: Callable):
        """Unsubscribe from data updates."""
        if callback in self.subscribers:
            self.subscribers.remove(callback)
            logger.debug(f"Subscriber removed. Total: {len(self.subscribers)}")
    
    def _notify_subscribers(self):
        """Notify all subscribers of new data."""
        data = {
            'candle': self.current_candle,
            'ticker': self.ticker_data,
            'order_book': self.order_book,
            'timestamp': datetime.now()
        }
        
        for callback in self.subscribers:
            try:
                callback(data)
            except Exception as e:
                logger.error(f"❌ Error in subscriber callback: {e}")
    
    def get_latest_candle(self) -> Optional[Dict]:
        """Get latest candle."""
        return self.current_candle
    
    def get_candle_history(self, limit: int = 100) -> List[Dict]:
        """Get candle history."""
        if limit <= 0:
            return self.candle_history.copy()
        return self.candle_history[-limit:] if self.candle_history else []
    
    def get_current_price(self) -> Optional[float]:
        """Get current price from ticker."""
        if self.ticker_data:
            return self.ticker_data.get('last')
        elif self.current_candle:
            return self.current_candle.get('close')
        return None
    
    def get_bid_ask(self) -> Optional[tuple]:
        """Get current bid/ask prices."""
        if self.ticker_data:
            return (self.ticker_data.get('bid'), self.ticker_data.get('ask'))
        return None
    
    def get_status(self) -> Dict:
        """Get feed status."""
        return {
            'is_running': self.is_running,
            'symbol': self.symbol,
            'timeframe': self.timeframe,
            'exchange': self.exchange.name if self.exchange else None,
            'current_price': self.get_current_price(),
            'candle_count': len(self.candle_history),
            'last_update': self.current_candle['datetime'] if self.current_candle else None,
            'subscriber_count': len(self.subscribers)
        }


class PaperTradingLiveDataProvider:
    """
    Data provider that uses live feed for paper trading.
    """
    
    def __init__(self, symbol: str = "BTC/USDT", timeframe: str = "1h", **kwargs):
        """
        Initialize live data provider.
        
        Args:
            symbol: Trading pair
            timeframe: Candle timeframe
            **kwargs: Additional arguments for LiveDataFeed
        """
        self.symbol = symbol
        self.timeframe = timeframe
        
        # Create live feed
        self.feed = LiveDataFeed(symbol=symbol, timeframe=timeframe, **kwargs)
        
        # Buffer for historical data requests
        self.historical_buffer = []
        
        # Start feed
        self.feed.start()
        
        # Subscribe to updates
        self.feed.subscribe(self._handle_update)
        
        logger.info(f"PaperTradingLiveDataProvider initialized")
    
    def _handle_update(self, data):
        """Handle data updates from feed."""
        if data.get('candle'):
            self.historical_buffer.append(data['candle'])
            
            # Keep buffer manageable
            if len(self.historical_buffer) > 10000:
                self.historical_buffer = self.historical_buffer[-5000:]
    
    def get_historical_data(self, limit: int = 1000, 
                          start_date: Optional[datetime] = None,
                          end_date: Optional[datetime] = None):
        """
        Get historical data from buffer.
        
        Note: Live feed only provides recent data.
        For full historical data, use HistoricalDataProvider.
        """
        import pandas as pd
        
        # Use buffer data
        data = self.historical_buffer.copy()
        
        # Filter by date if provided
        if start_date:
            data = [d for d in data if d['datetime'] >= start_date]
        if end_date:
            data = [d for d in data if d['datetime'] <= end_date]
        
        # Limit results
        if limit and len(data) > limit:
            data = data[-limit:]
        
        # Convert to DataFrame
        if data:
            df = pd.DataFrame(data)
            return df
        else:
            # Return empty DataFrame with expected columns
            return pd.DataFrame(columns=[
                'timestamp', 'datetime', 'open', 'high', 'low', 'close', 'volume',
                'symbol', 'timeframe'
            ])
    
    def get_latest_candle(self, *args, **kwargs) -> Optional[Dict]:
        """Get latest candle from feed.

        Accepts and ignores legacy/extra arguments to remain backward compatible
        with callers that pass `symbol`/`timeframe` as kwargs.
        """
        return self.feed.get_latest_candle()
    
    def get_current_price(self) -> Optional[float]:
        """Get current price from feed."""
        return self.feed.get_current_price()
    
    def stop(self):
        """Stop the data provider."""
        self.feed.stop()
    
    def get_status(self) -> Dict:
        """Get provider status."""
        return self.feed.get_status()


def create_live_data_provider(**kwargs):
    """
    Create live data provider.
    
    Args:
        **kwargs: Arguments for PaperTradingLiveDataProvider
        
    Returns:
        PaperTradingLiveDataProvider instance
    """
    return PaperTradingLiveDataProvider(**kwargs)


def main():
    """Test live data feed."""
    print("=" * 70)
    print("LIVE DATA FEED TEST")
    print("=" * 70)
    
    # Check if CCXT is available
    try:
        import ccxt
        print("✅ CCXT is available")
    except ImportError:
        print("❌ CCXT not installed. Install with: pip install ccxt")
        print("   Using simulated data instead.")
        
        # Fallback to simulated data
        from paper_trading.data_provider import SimulatedDataProvider
        provider = SimulatedDataProvider(symbol="BTC/USDT", timeframe="1h")
        
        # Test simulated data
        data = provider.get_historical_data(limit=5)
        print(f"\n📊 Simulated data shape: {data.shape}")
        
        latest = provider.get_latest_candle()
        if latest:
            print(f"📈 Latest simulated candle: {latest['datetime']}, "
                  f"Price: ${latest['close']:.2f}")
        
        print("\n✅ Simulated data feed working")
        return
    
    # Try to create live data provider
    try:
        print("\n🔌 Attempting to connect to exchange...")
        
        provider = create_live_data_provider(
            symbol="BTC/USDT",
            timeframe="1h",
            update_interval=10  # 10 seconds for testing
        )
        
        # Give it time to connect and fetch first data
        import time
        print("⏳ Waiting for connection and first data...")
        time.sleep(15)
        
        # Check status
        status = provider.get_status()
        
        print(f"\n📋 LIVE FEED STATUS:")
        print(f"   Running: {status['is_running']}")
        print(f"   Exchange: {status['exchange']}")
        print(f"   Symbol: {status['symbol']}")
        print(f"   Timeframe: {status['timeframe']}")
        
        if status['current_price']:
            print(f"   Current Price: ${status['current_price']:.2f}")
        
        if status['last_update']:
            print(f"   Last Update: {status['last_update']}")
        
        print(f"   Candles in buffer: {status['candle_count']}")
        
        # Get some historical data
        historical = provider.get_historical_data(limit=5)
        if not historical.empty:
            print(f"\n📊 Historical data (last 5):")
            for _, row in historical.iterrows():
                print(f"   {row['datetime']}: ${row['close']:.2f}")
        
        # Test subscription
        def test_callback(data):
            if data.get('candle'):
                candle = data['candle']
                print(f"   📡 New data: {candle['datetime']}, "
                      f"Price: ${candle['close']:.2f}")
        
        print(f"\n🎯 Testing subscription (5 seconds)...")
        provider.feed.subscribe(test_callback)
        time.sleep(5)
        provider.feed.unsubscribe(test_callback)
        
        # Stop provider
        provider.stop()
        
        print("\n✅ Live data feed test complete")
        
    except Exception as e:
        print(f"\n❌ Error testing live feed: {e}")
        print("   This is normal if:")
        print("   1. No internet connection")
        print("   2. Exchange API is down")
        print("   3. API keys not configured")
        print("\n   Using simulated data instead.")
    
    print("\n" + "=" * 70)


if __name__ == "__main__":
    main()