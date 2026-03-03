"""Validate exchange credentials and connectivity (Binance).

Attempts to connect to Binance using `ccxt` with provided env vars and
performs a lightweight fetch to ensure market data and optional balance
access are available. Exits non-zero on failure.
"""
import os
import sys
import logging
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv(usecwd=True), override=False)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main():
    try:
        import ccxt
    except Exception as e:
        logger.error('ccxt not installed: %s', e)
        return 2

    key = os.getenv('BINANCE_API_KEY')
    secret = os.getenv('BINANCE_API_SECRET')
    testnet = os.getenv('BINANCE_TESTNET', 'false').lower() in ('1', 'true', 'yes')
    pair = os.getenv('TRADING_PAIR', 'BTC/USDT')

    logger.info('Validating Binance connectivity (testnet=%s) for pair %s', testnet, pair)

    try:
        exchange = ccxt.binance({'apiKey': key or None, 'secret': secret or None, 'enableRateLimit': True})
        if testnet:
            try:
                exchange.set_sandbox_mode(True)
                logger.info('Sandbox mode enabled')
            except Exception:
                logger.warning('Exchange driver does not support sandbox_mode; continuing')

        # Public call: load markets
        markets = exchange.load_markets()
        logger.info('Loaded %d markets', len(markets))

        # Public market data: fetch OHLCV for the given pair
        try:
            ohlcv = exchange.fetch_ohlcv(pair, timeframe='1h', limit=3)
            logger.info('Fetched %d OHLCV candles for %s', len(ohlcv), pair)
        except Exception as e:
            logger.error('Failed to fetch OHLCV for %s: %s', pair, e)
            return 3

        # Optional: try balance if keys present
        if key and secret:
            try:
                bal = exchange.fetch_balance()
                logger.info('Balance fetch OK (keys valid) — total keys: %d', len(bal.keys()))
            except Exception as e:
                logger.warning('Balance fetch failed (keys may lack permissions): %s', e)

        logger.info('Exchange validation succeeded')
        return 0

    except Exception as e:
        # Treat location-restricted responses from Binance (HTTP 451) as a warning
        try:
            import ccxt
            from ccxt.base.errors import ExchangeNotAvailable
        except Exception:
            ExchangeNotAvailable = None

        msg = str(e)
        if ExchangeNotAvailable and isinstance(e, ExchangeNotAvailable):
            # ccxt surfaces HTTP status in the exception message; detect 451 or restricted-location
            if '451' in msg or 'restricted location' in msg.lower():
                logger.warning('Exchange appears restricted in CI environment: %s', msg)
                # Don't fail CI for geographic restrictions — treat as non-fatal
                return 0

        logger.exception('Exchange validation failed: %s', e)
        return 4


if __name__ == '__main__':
    rc = main()
    sys.exit(rc)
