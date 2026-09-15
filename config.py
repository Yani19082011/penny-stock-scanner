"""
Централна конфигурация - чете всичко от environment variables (.env локално,
или Railway "Variables" таб в продукция). Никакви ключове не се пишат тук.
"""
import os
from dotenv import load_dotenv

load_dotenv()  # локално чете .env; на Railway .env не съществува, но Railway
                # вкарва Variables директно в environment, така че пак работи.


def _bool(name: str, default: bool = False) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().lower() in ("1", "true", "yes", "on")


# --- Alpaca ---
ALPACA_API_KEY = os.getenv("ALPACA_API_KEY", "")
ALPACA_SECRET_KEY = os.getenv("ALPACA_SECRET_KEY", "")
ALPACA_BASE_URL = os.getenv("ALPACA_BASE_URL", "https://paper-api.alpaca.markets")
ALPACA_DATA_URL = os.getenv("ALPACA_DATA_URL", "https://data.alpaca.markets")

# --- Finnhub / FMP ---
FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY", "")
FMP_API_KEY = os.getenv("FMP_API_KEY", "")

# --- Watchlist / universe ---
MAX_UNIVERSE_PRICE = float(os.getenv("MAX_UNIVERSE_PRICE", "20"))
WATCHLIST_SIZE = int(os.getenv("WATCHLIST_SIZE", "5"))
# Пълно сканиране на целия universe (нови кандидати) - по-тежко, по-рядко.
SCAN_INTERVAL_MINUTES = int(os.getenv("SCAN_INTERVAL_MINUTES", "10"))
# Бърз цикъл - прескорира само вече наблюдаваните 5 тикера, за реално-времеви
# алърти без да чакаме следващото пълно сканиране.
FAST_INTERVAL_MINUTES = int(os.getenv("FAST_INTERVAL_MINUTES", "2"))

# --- Позициониране (само за информативния текст в алъртите - не изпълнява поръчки) ---
POSITION_SIZE_EUR = float(os.getenv("POSITION_SIZE_EUR", "20"))
TARGET_PROFIT_EUR = float(os.getenv("TARGET_PROFIT_EUR", "5"))
TARGET_PROFIT_PCT = TARGET_PROFIT_EUR / POSITION_SIZE_EUR  # 0.25 по подразбиране

# --- Email алърти ---
ALERT_EMAIL_ENABLED = _bool("ALERT_EMAIL_ENABLED", False)
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USERNAME = os.getenv("SMTP_USERNAME", "")
SMTP_APP_PASSWORD = os.getenv("SMTP_APP_PASSWORD", "")
ALERT_EMAIL_TO = os.getenv("ALERT_EMAIL_TO", "yani.kolev2011@gmail.com")

# --- Render (или локален) HTTP порт за health-check ---
PORT = int(os.getenv("PORT", "10000"))

# --- Файлове ---
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
WATCHLIST_FILE = os.path.join(DATA_DIR, "watchlist.json")
