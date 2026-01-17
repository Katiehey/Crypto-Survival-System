"""
Exchange API Configuration

Handles connection to Binance (or other exchanges).
API keys are loaded from environment variables ONLY.
"""

import os
from typing import Optional
from dotenv import load_dotenv, find_dotenv
import ccxt

load_dotenv(find_dotenv(usecwd=True), override=True)

class ExchangeConfig:
    """
    Exchange connection configuration.
    
    This class manages API credentials and exchange-specific settings.
    """
    
    def __init__(self):
        """
        Initialize ExchangeConfig by loading credentials from environment variables.
        
        Performs basic validation to ensure keys are not the default placeholder 
        strings and sets internal state for testnet usage.
        """
        self.api_key: Optional[str] = os.getenv('BINANCE_API_KEY')
        self.api_secret: Optional[str] = os.getenv('BINANCE_API_SECRET')
        self.use_testnet: bool = os.getenv('BINANCE_TESTNET', 'true').lower() == 'true'
        
        print(f"DEBUG: API Key from env: {os.getenv('BINANCE_API_KEY')[:5]}***")
        print(f"DEBUG: Testnet setting: {os.getenv('BINANCE_TESTNET')}")
    
        self.api_key: Optional[str] = os.getenv('BINANCE_API_KEY')
        # Validate credentials exist
        if not self.api_key or self.api_key == 'your_api_key_here':
            self.api_key = None
        
        if not self.api_secret or self.api_secret == 'your_api_secret_here':
            self.api_secret = None
    
    def has_credentials(self) -> bool:
        """Check if valid API credentials are configured."""
        return self.api_key is not None and self.api_secret is not None
    
    def create_exchange(self) -> ccxt.Exchange:
        """
        Create and configure exchange instance.
        
        Returns:
            Configured CCXT exchange object
            
        Raises:
            ValueError: If credentials are missing or invalid
        """
        if not self.has_credentials():
            raise ValueError(
                "Binance API credentials not configured. "
                "Please set BINANCE_API_KEY and BINANCE_API_SECRET in .env file"
            )
        
        config = {
            'apiKey': self.api_key,
            'secret': self.api_secret,
            'enableRateLimit': True,  # Critical for avoiding bans
            'options': {
                'defaultType': 'spot',  # Only spot trading
            }
        }
        
        # Use testnet if configured
        if self.use_testnet:
            config['urls'] = {
                'api': {
                    'public': 'https://testnet.binance.vision/api/v3',
                    'private': 'https://testnet.binance.vision/api/v3',
                }
            }
        
        exchange = ccxt.binance(config)
        
        return exchange
    
    def test_connection(self) -> tuple[bool, str]:
        """
        Test exchange connection and credentials.
        
        Returns:
            (success, message)
        """
        if not self.has_credentials():
            return False, "No API credentials configured"
        
        try:
            exchange = self.create_exchange()
            
            # Try to fetch account balance (requires valid credentials)
            balance = exchange.fetch_balance()
            
            # Check for USDT balance
            usdt_balance = balance.get('USDT', {}).get('free', 0)
            
            mode = "TESTNET" if self.use_testnet else "LIVE"
            return True, f"✅ Connected to Binance {mode}. USDT balance: {usdt_balance}"
            
        except ccxt.AuthenticationError as e:
            return False, f"Authentication failed: {str(e)}"
        except ccxt.NetworkError as e:
            return False, f"Network error: {str(e)}"
        except Exception as e:
            return False, f"Connection test failed: {str(e)}"


# Module-level singleton
_exchange_config = ExchangeConfig()


def get_exchange_config() -> ExchangeConfig:
    """Get the singleton exchange configuration instance."""
    return _exchange_config


if __name__ == "__main__":
    # For testing exchange connection
    config = get_exchange_config()
    
    print("=" * 60)
    print("EXCHANGE CONFIGURATION")
    print("=" * 60)
    print(f"Has credentials: {config.has_credentials()}")
    print(f"Using testnet: {config.use_testnet}")
    
    if config.has_credentials():
        print("\nTesting connection...")
        success, message = config.test_connection()
        print(message)
    else:
        print("\n⚠️  No API credentials configured")
        print("Set BINANCE_API_KEY and BINANCE_API_SECRET in .env to test connection")