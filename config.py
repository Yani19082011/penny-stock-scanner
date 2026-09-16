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
MAX_UNIVERSE_PRICE = float(os.getenv("MAX_UNIVERSE_PRICE", "10"))
# Горен праг на пазарна капитализация - за да са РЕАЛНИ penny stocks (малки,
# спекулативни компании), не просто големи имена (MARA, NIO, F, AMC...),
# които случайно търгуват евтино. $300M е стандартна граница за "micro-cap".
#
# ВАЖНО: FMP-ският company-screener/quote endpoint (единственият, който дава
# marketCap директно) изисква ПЛАТЕН FMP план - потвърдено с реалния ключ на
# потребителя (402 Payment Required). Безплатните FMP endpoint-и (biggest-
# gainers/biggest-losers/most-actives), които вече ползваме за universe.py,
# НЕ връщат marketCap изобщо. Затова тази проверка сега минава през Finnhub
# (безплатен tier, FINNHUB_API_KEY) като best-effort вторична проверка - виж
# universe.py. Ако FINNHUB_API_KEY липсва, тази граница НЕ се прилага реално -
# разчитаме само на статичния LARGE_CAP_BLOCKLIST + цената като защита.
MAX_MARKET_CAP_USD = float(os.getenv("MAX_MARKET_CAP_USD", "300000000"))
# Колко кандидата максимум да проверяваме през Finnhub на едно пълно
# сканиране (пести безплатния rate limit на Finnhub, ~60 заявки/мин).
MAX_MOVERS_CANDIDATES = int(os.getenv("MAX_MOVERS_CANDIDATES", "60"))
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
# --- Resend (https://resend.com) - изпраща email през HTTP API, не през Gmail SMTP.
# Ползваме го вместо Gmail App Password, защото Family Link/supervised Google
# акаунти не позволяват App Passwords изобщо. Виж README.md за регистрация.
RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")
RESEND_FROM_EMAIL = os.getenv("RESEND_FROM_EMAIL", "onboarding@resend.dev")
ALERT_EMAIL_TO = os.getenv("ALERT_EMAIL_TO", "yani.kolev2011@gmail.com")

# --- Anti-spam защита за Resend дневната квота (безплатен tier = 100 имейла/ден
# за целия акаунт, споделен с другите ботове, ползващи същия RESEND_API_KEY) ---
# Не пращаме имейл по-често от веднъж на MIN_EMAIL_INTERVAL_SECONDS (300с = 5мин,
# значи максимум ~2 имейла на всеки 10 минути), плюс твърд дневен таван като
# резерва под истинския лимит на Resend. Алъртът винаги се вижда в Render Logs -
# само самото email изпращане се прескача, ако сме над темпото.
MIN_EMAIL_INTERVAL_SECONDS = int(os.getenv("MIN_EMAIL_INTERVAL_SECONDS", "300"))
# По-малка част от общата дневна квота от 100 (споделена с memecoin бота) -
# там пращаме 90/ден, тук само 10/ден (watchlist-ът е малък, не му трябва повече).
MAX_EMAILS_PER_DAY = int(os.getenv("MAX_EMAILS_PER_DAY", "10"))

# --- Render (или локален) HTTP порт за health-check ---
PORT = int(os.getenv("PORT", "10000"))

# --- Файлове ---
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
WATCHLIST_FILE = os.path.join(DATA_DIR, "watchlist.json")
