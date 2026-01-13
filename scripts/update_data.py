"""
Convenience script for updating market data.

Usage:
    python scripts/update_data.py
"""

from data.fetcher import DataFetcher
from config.system_config import SYSTEM_CONFIG


def main():
    """Update market data for configured trading pair."""
    print("=" * 60)
    print("UPDATING MARKET DATA")
    print("=" * 60)
    print(f"Symbol: {SYSTEM_CONFIG.TRADING_PAIR}")
    print(f"Timeframe: {SYSTEM_CONFIG.PRIMARY_TIMEFRAME}")
    print()
    
    fetcher = DataFetcher()
    
    try:
        fetcher.connect()
        count = fetcher.update_latest()
        
        print(f"\n✅ Update complete: {count} new candles")
        print(f"📊 Total candles: {fetcher.get_candle_count()}")
        
    except ValueError as e:
        print(f"⚠️  {e}")
        return 1
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())