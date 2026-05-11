"""
config.py — Central configuration loaded from .env
All secrets and tunable parameters live here. Never hardcode values.
"""

import os
from dotenv import load_dotenv

load_dotenv(override=True)  # .env always takes precedence over shell environment variables

# ─── Exchange ────────────────────────────────────────────────────────────────
EXCHANGE           = os.getenv("EXCHANGE", "binance")   # "binance" | "kucoin"
BINANCE_API_KEY    = os.getenv("BINANCE_API_KEY", "")
BINANCE_API_SECRET = os.getenv("BINANCE_API_SECRET", "")
BINANCE_TESTNET    = os.getenv("BINANCE_TESTNET", "false").lower() == "true"
KUCOIN_API_KEY     = os.getenv("KUCOIN_API_KEY", "")
KUCOIN_API_SECRET  = os.getenv("KUCOIN_API_SECRET", "")
KUCOIN_PASSPHRASE  = os.getenv("KUCOIN_PASSPHRASE", "")

# ─── Trading ─────────────────────────────────────────────────────────────────
TRADING_MODE      = os.getenv("TRADING_MODE", "paper")          # "paper" | "live"
TRADING_PAIR      = os.getenv("TRADING_PAIR", "BTC/USDT")
BASE_CURRENCY     = os.getenv("BASE_CURRENCY", "USDT")
STARTING_CAPITAL  = float(os.getenv("STARTING_CAPITAL", "30"))

# Binance minimum notional for BTC/USDT is ~$5 (min qty 0.00001 BTC).
# We use $11 per trade to stay safely above minimums while capital is small.
MIN_ORDER_USDT    = float(os.getenv("MIN_ORDER_USDT", "11"))

# ─── Risk ─────────────────────────────────────────────────────────────────────
MAX_RISK_PER_TRADE       = float(os.getenv("MAX_RISK_PER_TRADE", "0.005"))   # 0.5%
MAX_DAILY_LOSS           = float(os.getenv("MAX_DAILY_LOSS", "0.01"))         # 1%
MAX_CONSECUTIVE_LOSSES   = int(os.getenv("MAX_CONSECUTIVE_LOSSES", "2"))
MAX_TRADES_PER_DAY       = int(os.getenv("MAX_TRADES_PER_DAY", "2"))
MAX_DRAWDOWN_KILL_SWITCH = float(os.getenv("MAX_DRAWDOWN_KILL_SWITCH", "0.25"))  # 25% — suitable for accounts under $100; tighten to 0.10 above $200
COOLDOWN_MINUTES         = int(os.getenv("COOLDOWN_MINUTES", "15"))

# ATR multipliers for dynamic SL / TP
# 1.5× SL was too tight for 1h BTC noise — raised to 2.0× to survive normal retracements
ATR_STOP_MULT   = float(os.getenv("ATR_STOP_MULT", "2.0"))
ATR_TARGET_MULT = float(os.getenv("ATR_TARGET_MULT", "3.0"))   # maintains ~1.5:1 RR with wider SL

# Long-only mode: True for spot USDT accounts (cannot short BTC on spot)
# Set to False only if using futures/margin.
LONG_ONLY = os.getenv("LONG_ONLY", "true").lower() == "true"

# Volume spike filter: current bar volume must exceed N × 20-bar average
VOLUME_SPIKE_MIN = float(os.getenv("VOLUME_SPIKE_MIN", "1.2"))  # compared against 50-bar avg, not 20

# ─── Strategy ────────────────────────────────────────────────────────────────
DATA_UPDATE_INTERVAL  = int(os.getenv("DATA_UPDATE_INTERVAL", "60"))   # seconds
MIN_CANDLES_REQUIRED  = int(os.getenv("MIN_CANDLES_REQUIRED", "100"))
ADX_TREND_THRESHOLD   = float(os.getenv("ADX_TREND_THRESHOLD", "25"))  # ADX > 25 = trending
RSI_TREND_BUY_MIN     = float(os.getenv("RSI_TREND_BUY_MIN",  "55"))   # RSI must clear 55, not just 50
RSI_TREND_SELL_MAX    = float(os.getenv("RSI_TREND_SELL_MAX", "45"))
RSI_RANGE_BUY_MAX     = float(os.getenv("RSI_RANGE_BUY_MAX",  "30"))   # genuine oversold
RSI_RANGE_SELL_MIN    = float(os.getenv("RSI_RANGE_SELL_MIN", "70"))   # genuine overbought
TIMEFRAME             = os.getenv("TIMEFRAME", "1h")

# ─── Agent weights (must sum to 1.0) ─────────────────────────────────────────
# Consensus: all agents must agree direction; weights used for confidence score
AGENT_WEIGHTS = {
    "technical": float(os.getenv("WEIGHT_TECHNICAL", "0.45")),
    "sentiment":  float(os.getenv("WEIGHT_SENTIMENT",  "0.15")),
    "risk":       float(os.getenv("WEIGHT_RISK",       "0.25")),
    "execution":  float(os.getenv("WEIGHT_EXECUTION",  "0.15")),
}

# ─── Sentiment RSS feeds (free, no API key needed) ───────────────────────────
SENTIMENT_FEEDS = [
    "https://feeds.feedburner.com/CoinDesk",
    "https://cointelegraph.com/rss",
    "https://bitcoinmagazine.com/.rss/full/",
    "https://cryptopotato.com/feed/",
]
SENTIMENT_CACHE_SECONDS = int(os.getenv("SENTIMENT_CACHE_SECONDS", "300"))  # 5 min

# ─── Database & Logging ───────────────────────────────────────────────────────
DB_PATH            = os.getenv("DB_PATH", "data/trading.db")
LOG_LEVEL          = os.getenv("LOG_LEVEL", "INFO")
LOG_RETENTION_DAYS = int(os.getenv("LOG_RETENTION_DAYS", "90"))
LOG_DIR            = "logs"

# ─── Telegram ────────────────────────────────────────────────────────────────
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID   = os.getenv("TELEGRAM_CHAT_ID", "")
TELEGRAM_ENABLED   = os.getenv("TELEGRAM_ENABLED", "true").lower() == "true"

# ─── Resilience ──────────────────────────────────────────────────────────────
MAX_RECONNECT_ATTEMPTS = int(os.getenv("MAX_RECONNECT_ATTEMPTS", "10"))
RECONNECT_BACKOFF_BASE = float(os.getenv("RECONNECT_BACKOFF_BASE", "2.0"))   # seconds
RECONNECT_BACKOFF_MAX  = float(os.getenv("RECONNECT_BACKOFF_MAX", "120.0"))  # 2 min cap

# ─── Kill switch file (manual override) ──────────────────────────────────────
KILL_SWITCH_FILE = "ops/kill_switch.json"

# ─── Log management ───────────────────────────────────────────────────────────
# Optional email delivery for compressed logs (uses Gmail SMTP with app password)
# Generate an app password at: https://myaccount.google.com/apppasswords
EMAIL_ADDRESS      = os.getenv("EMAIL_ADDRESS", "")
EMAIL_APP_PASSWORD = os.getenv("EMAIL_APP_PASSWORD", "")
EMAIL_RECIPIENT    = os.getenv("EMAIL_RECIPIENT", EMAIL_ADDRESS)  # default: send to self
# Compress logs older than this many hours (keeps disk usage low on AWS free tier)
LOG_COMPRESS_AFTER_HOURS = int(os.getenv("LOG_COMPRESS_AFTER_HOURS", "24"))
