from data.fetcher import DataFetcher
from config.system_config import SYSTEM_CONFIG
from datetime import datetime, timedelta

def collect():
    fetcher = DataFetcher()
    fetcher.connect()
    
    symbol = SYSTEM_CONFIG.TRADING_PAIR
    timeframe = SYSTEM_CONFIG.PRIMARY_TIMEFRAME
    
    print("🚀 Starting pagination-aware data collection...")
    
    # Target: ~5000 candles
    # 1h timeframe * 5000 = ~208 days
    current_since = int((datetime.now() - timedelta(days=210)).timestamp() * 1000)
    
    total_stored = 0
    for i in range(10):  # Fetch in chunks of 500
        print(f"Fetching batch {i+1}, starting from {datetime.fromtimestamp(current_since/1000)}...")
        
        ohlcv = fetcher.fetch_ohlcv(
            symbol=symbol,
            timeframe=timeframe,
            limit=500,
            since=current_since
        )
        
        if not ohlcv:
            break
            
        stored = fetcher.store_ohlcv(symbol, timeframe, ohlcv)
        total_stored += stored
        
        # Update 'since' to the timestamp of the last candle fetched + 1ms
        current_since = ohlcv[-1][0] + 1
        
    print(f"✅ Finished! Total candles now in DB: {fetcher.get_candle_count()}")

if __name__ == "__main__":
    collect()