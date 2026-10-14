"""
Централна конфигурация - чете всичко от environment variables (.env локално,
или Render "Environment" таб в продукция). Никакви ключове не се пишат тук.

ВЪЗСТАНОВЕН (13.10) след случайно презаписване с config.py от друг проект
(GoldSignalBot), качен по грешка през GitHub "Upload files" в това repo.
Възстановен от: (1) стар запазен снимок на този файл, (2) REQUIRED_CONFIG_
ATTRS в main.py (пълният, актуален списък от всичко, което ботът РЕАЛНО
чете), (3) контекста/коментарите в main.py/universe.py за секциите,
добавени след снимката (PRICE_SPIKE_*/TELEGRAM_*, 01.10). Стойностите по
подразбиране за PRICE_SPIKE_TOP_N/MIN_DOLLAR_VOLUME/VOLUME_MULTIPLIER/
VOLUME_LOOKBACK_MINUTES/MIN_PRICE_CHANGE_PCT/PRICE_LOOKBACK_MINUTES са
МОИ РЕКОНСТРУИРАНИ ДОГАДКИ (оригиналните стойности не бяха запазени никъде
извлечимо) - провери/коригирай ги, ако помниш различни числа, или просто
остави Render Environment Variables да ги override-ват, ако вече са
зададени там. Всичко останало е възстановено с висока увереност (или от
запазения снимок, или от изрични числа в коментарите на main.py/universe.py).
"""
import os
from dotenv import load_dotenv

load_dotenv()  # локално чете .env; на Render .env не съществува, но Render
                # вкарва Environment Variables директно, така че пак работи.


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

# --- Scoring прагове (виж scoring.py::ScoreResult) ---
HIGH_POTENTIAL_THRESHOLD = float(os.getenv("HIGH_POTENTIAL_THRESHOLD", "70"))
EXIT_THRESHOLD = float(os.getenv("EXIT_THRESHOLD", "40"))

# --- Watchlist / universe ---
MAX_UNIVERSE_PRICE = float(os.getenv("MAX_UNIVERSE_PRICE", "10"))
# Горен праг на пазарна капитализация - за да са РЕАЛНИ penny stocks, не
# просто големи имена, които случайно търгуват евтино. $300M е стандартна
# граница за "micro-cap".
MAX_MARKET_CAP_USD = float(os.getenv("MAX_MARKET_CAP_USD", "300000000"))
MAX_MOVERS_CANDIDATES = int(os.getenv("MAX_MOVERS_CANDIDATES", "60"))
WATCHLIST_SIZE = int(os.getenv("WATCHLIST_SIZE", "20"))

PREMARKET_START_HOUR = int(os.getenv("PREMARKET_START_HOUR", "4"))
PREMARKET_START_MINUTE = int(os.getenv("PREMARKET_START_MINUTE", "0"))

SCAN_INTERVAL_MINUTES = int(os.getenv("SCAN_INTERVAL_MINUTES", "10"))
FAST_INTERVAL_MINUTES = int(os.getenv("FAST_INTERVAL_MINUTES", "2"))

# --- Защита срещу "купуване на върха" ---
MIN_HIGH_POTENTIAL_CONFIRMATIONS = int(os.getenv("MIN_HIGH_POTENTIAL_CONFIRMATIONS", "2"))
PEAK_DRAWDOWN_STOP_PCT = float(os.getenv("PEAK_DRAWDOWN_STOP_PCT", "5"))

# --- Позициониране (само за информативния текст в алъртите) ---
POSITION_SIZE_EUR = float(os.getenv("POSITION_SIZE_EUR", "20"))
TARGET_PROFIT_EUR = float(os.getenv("TARGET_PROFIT_EUR", "5"))
TARGET_PROFIT_PCT = (TARGET_PROFIT_EUR / POSITION_SIZE_EUR) if POSITION_SIZE_EUR else 0.0  # 0.25 по подразбиране

# --- Email алърти ---
ALERT_EMAIL_ENABLED = _bool("ALERT_EMAIL_ENABLED", False)
# Resend (https://resend.com) - изпраща email през HTTP API, не през Gmail SMTP.
RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")
RESEND_FROM_EMAIL = os.getenv("RESEND_FROM_EMAIL", "onboarding@resend.dev")
ALERT_EMAIL_TO = os.getenv("ALERT_EMAIL_TO", "yani.kolev2011@gmail.com")

# --- Anti-spam защита за Resend дневната квота (100 имейла/ден общо за
# акаунта, споделен с другите ботове) - 70/30 разпределение между memecoin
# и penny-stock бота.
MIN_EMAIL_INTERVAL_SECONDS = int(os.getenv("MIN_EMAIL_INTERVAL_SECONDS", "420"))
MAX_EMAILS_PER_DAY = int(os.getenv("MAX_EMAILS_PER_DAY", "30"))

# --- "Тихи часове" за имейл алъртите ---
ALERT_QUIET_HOURS_TZ = os.getenv("ALERT_QUIET_HOURS_TZ", "Europe/Sofia")
ALERT_ACTIVE_START_HOUR = int(os.getenv("ALERT_ACTIVE_START_HOUR", "7"))
ALERT_ACTIVE_START_MINUTE = int(os.getenv("ALERT_ACTIVE_START_MINUTE", "30"))
ALERT_ACTIVE_END_HOUR = int(os.getenv("ALERT_ACTIVE_END_HOUR", "23"))
ALERT_ACTIVE_END_MINUTE = int(os.getenv("ALERT_ACTIVE_END_MINUTE", "0"))

# --- Render (или локален) HTTP порт за health-check ---
PORT = int(os.getenv("PORT", "10000"))

# --- Self-ping (keep-alive) ---
KEEP_ALIVE_PING_MINUTES = int(os.getenv("KEEP_ALIVE_PING_MINUTES", "5"))

# --- Трайна памет отвъд Render локалния диск (по избор) ---
UPSTASH_REDIS_REST_URL = os.getenv("UPSTASH_REDIS_REST_URL", "")
UPSTASH_REDIS_REST_TOKEN = os.getenv("UPSTASH_REDIS_REST_TOKEN", "")

# --- Файлове ---
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
WATCHLIST_FILE = os.path.join(DATA_DIR, "watchlist.json")

# --- "ЦЕНОВИ СКОК" v2 (01.10, по точна спецификация на потребителя) -------
# ВЪЗСТАНОВЕНО (13.10): INTERVAL_MINUTES/UNIVERSE_REFRESH_MINUTES/
# COOLDOWN_MINUTES са потвърдени с висока увереност от изрични числа в
# коментарите на main.py/universe.py (1 мин / 5 мин / 15 мин). Останалите
# 6 стойности по-долу (TOP_N, MIN_DOLLAR_VOLUME, VOLUME_MULTIPLIER,
# VOLUME_LOOKBACK_MINUTES, MIN_PRICE_CHANGE_PCT, PRICE_LOOKBACK_MINUTES) са
# РЕКОНСТРУИРАНИ ДОГАДКИ - разумни по дух на спецификацията (виж main.py::
# run_price_spike_scan за точната им употреба), но НЕ потвърдени оригинални
# числа. Провери в Render Environment Variables дали вече не са зададени
# там (тогава override-ват тези по подразбиране и нищо не се чупи) - ако не
# са, и помниш различни стойности, кажи ми ги и ще ги оправя.
PRICE_SPIKE_ENABLED = _bool("PRICE_SPIKE_ENABLED", False)
PRICE_SPIKE_INTERVAL_MINUTES = int(os.getenv("PRICE_SPIKE_INTERVAL_MINUTES", "1"))
PRICE_SPIKE_UNIVERSE_REFRESH_MINUTES = int(os.getenv("PRICE_SPIKE_UNIVERSE_REFRESH_MINUTES", "5"))
PRICE_SPIKE_TOP_N = int(os.getenv("PRICE_SPIKE_TOP_N", "30"))  # РЕКОНСТРУИРАНО - виж бележката по-горе
PRICE_SPIKE_MIN_DOLLAR_VOLUME = float(os.getenv("PRICE_SPIKE_MIN_DOLLAR_VOLUME", "500000"))  # РЕКОНСТРУИРАНО
PRICE_SPIKE_VOLUME_MULTIPLIER = float(os.getenv("PRICE_SPIKE_VOLUME_MULTIPLIER", "3"))  # РЕКОНСТРУИРАНО
PRICE_SPIKE_VOLUME_LOOKBACK_MINUTES = int(os.getenv("PRICE_SPIKE_VOLUME_LOOKBACK_MINUTES", "20"))  # РЕКОНСТРУИРАНО
PRICE_SPIKE_MIN_PRICE_CHANGE_PCT = float(os.getenv("PRICE_SPIKE_MIN_PRICE_CHANGE_PCT", "5"))  # РЕКОНСТРУИРАНО
PRICE_SPIKE_PRICE_LOOKBACK_MINUTES = int(os.getenv("PRICE_SPIKE_PRICE_LOOKBACK_MINUTES", "5"))  # РЕКОНСТРУИРАНО
PRICE_SPIKE_COOLDOWN_MINUTES = int(os.getenv("PRICE_SPIKE_COOLDOWN_MINUTES", "15"))

# --- Telegram алърти (по избор, успоредно/вместо email - виж main.py::
# test_telegram и README.md за @BotFather стъпките) ---
TELEGRAM_ENABLED = _bool("TELEGRAM_ENABLED", False)
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
