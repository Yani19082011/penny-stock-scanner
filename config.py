"""
Централна конфигурация - премахнат FMP_API_KEY за 100% безплатна работа.
"""
import os
from dotenv import load_dotenv

load_dotenv()

def _bool(name: str, default: bool = False) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().lower() in ("1", "true", "yes", "on")

# --- Alpaca ---
ALPACA_API_KEY = os.getenv("ALPACA_API_KEY", "")
ALPACA_SECRET_KEY = os.getenv("ALPACA_SECRET_KEY", "")
ALPACA_BASE_URL = os.getenv("ALPACA_BASE_URL", "https://alpaca.markets")
ALPACA_DATA_URL = os.getenv("ALPACA_DATA_URL", "https://alpaca.markets")

# --- Finnhub ---
FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY", "")

# --- Scoring прагове ---
HIGH_POTENTIAL_THRESHOLD = float(os.getenv("HIGH_POTENTIAL_THRESHOLD", "70"))
EXIT_THRESHOLD = float(os.getenv("EXIT_THRESHOLD", "40"))

# --- Watchlist / universe ---
MAX_UNIVERSE_PRICE = float(os.getenv("MAX_UNIVERSE_PRICE", "10"))
MAX_MARKET_CAP_USD = float(os.getenv("MAX_MARKET_CAP_USD", "300000000"))
MAX_MOVERS_CANDIDATES = int(os.getenv("MAX_MOVERS_CANDIDATES", "60"))
WATCHLIST_SIZE = int(os.getenv("WATCHLIST_SIZE", "20"))

PREMARKET_START_HOUR = int(os.getenv("PREMARKET_START_HOUR", "4"))
PREMARKET_START_MINUTE = int(os.getenv("PREMARKET_START_MINUTE", "0"))

SCAN_INTERVAL_MINUTES = int(os.getenv("SCAN_INTERVAL_MINUTES", "10"))
FAST_INTERVAL_MINUTES = int(os.getenv("FAST_INTERVAL_MINUTES", "2"))

MIN_HIGH_POTENTIAL_CONFIRMATIONS = int(os.getenv("MIN_HIGH_POTENTIAL_CONFIRMATIONS", "2"))
PEAK_DRAWDOWN_STOP_PCT = float(os.getenv("PEAK_DRAWDOWN_STOP_PCT", "5"))

# --- Позициониране ---
POSITION_SIZE_EUR = float(os.getenv("POSITION_SIZE_EUR", "20"))
TARGET_PROFIT_EUR = float(os.getenv("TARGET_PROFIT_EUR", "5"))
TARGET_PROFIT_PCT = (TARGET_PROFIT_EUR / POSITION_SIZE_EUR) if POSITION_SIZE_EUR else 0.0

# --- Email алърти ---
ALERT_EMAIL_ENABLED = _bool("ALERT_EMAIL_ENABLED", False)
RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")
RESEND_FROM_EMAIL = os.getenv("RESEND_FROM_EMAIL", "onboarding@resend.dev")
ALERT_EMAIL_TO = os.getenv("ALERT_EMAIL_TO", "yani.kolev2011@gmail.com")

MIN_EMAIL_INTERVAL_SECONDS = int(os.getenv("MIN_EMAIL_INTERVAL_SECONDS", "420"))
MAX_EMAILS_PER_DAY = int(os.getenv("MAX_EMAILS_PER_DAY", "30"))

ALERT_QUIET_HOURS_TZ = os.getenv("ALERT_QUIET_HOURS_TZ", "Europe/Sofia")
ALERT_ACTIVE_START_HOUR = int(os.getenv("ALERT_ACTIVE_START_HOUR", "7"))
ALERT_ACTIVE_START_MINUTE = int(os.getenv("ALERT_ACTIVE_START_MINUTE", "30"))
ALERT_ACTIVE_END_HOUR = int(os.getenv("ALERT_ACTIVE_END_HOUR", "23"))
ALERT_ACTIVE_END_MINUTE = int(os.getenv("ALERT_ACTIVE_END_MINUTE", "0"))

PORT = int(os.getenv("PORT", "10000"))
KEEP_ALIVE_PING_MINUTES = int(os.getenv("KEEP_ALIVE_PING_MINUTES", "5"))

UPSTASH_REDIS_REST_URL = os.getenv("UPSTASH_REDIS_REST_URL", "")
UPSTASH_REDIS_REST_TOKEN = os.getenv("UPSTASH_REDIS_REST_TOKEN", "")

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
WATCHLIST_FILE = os.path.join(DATA_DIR, "watchlist.json")
