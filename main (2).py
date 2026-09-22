"""
Вход на приложението. Премахнати проверките за FMP.
"""
import logging
import os
import threading
import time
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import requests
import schedule
from flask import Flask

import config
from data_sources import AlpacaClient, FinnhubClient, get_sec_dilution_flags, get_bars_yfinance
from halts import get_recently_resumed
from indicators import compute_all
from scoring import score_symbol
from universe import get_universe
from watchlist import load_watchlist, save_watchlist, update_watchlist
from notifier import send_alert

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("main")

REQUIRED_CONFIG_ATTRS = [
    "MAX_UNIVERSE_PRICE", "MAX_MARKET_CAP_USD", "MAX_MOVERS_CANDIDATES",
    "WATCHLIST_SIZE", "PREMARKET_START_HOUR", "PREMARKET_START_MINUTE",
    "SCAN_INTERVAL_MINUTES", "FAST_INTERVAL_MINUTES",
    "MIN_HIGH_POTENTIAL_CONFIRMATIONS", "PEAK_DRAWDOWN_STOP_PCT",
    "POSITION_SIZE_EUR", "TARGET_PROFIT_EUR", "TARGET_PROFIT_PCT",
    "HIGH_POTENTIAL_THRESHOLD", "EXIT_THRESHOLD",
    "ALERT_EMAIL_ENABLED", "RESEND_API_KEY", "RESEND_FROM_EMAIL", "ALERT_EMAIL_TO",
    "MIN_EMAIL_INTERVAL_SECONDS", "MAX_EMAILS_PER_DAY", "ALERT_QUIET_HOURS_TZ", "PORT",
    "KEEP_ALIVE_PING_MINUTES",
    "ALPACA_API_KEY", "ALPACA_SECRET_KEY", "ALPACA_BASE_URL", "ALPACA_DATA_URL",
    "FINNHUB_API_KEY", "DATA_DIR", "WATCHLIST_FILE",
    "UPSTASH_REDIS_REST_URL", "UPSTASH_REDIS_REST_TOKEN",
    "ALERT_ACTIVE_START_HOUR", "ALERT_ACTIVE_START_MINUTE",
    "ALERT_ACTIVE_END_HOUR", "ALERT_ACTIVE_END_MINUTE",
]

def _startup_self_check():
    missing = [name for name in REQUIRED_CONFIG_ATTRS if not hasattr(config, name)]
    if missing:
        log.critical("СТАРТОВА ПРОВЕРКА ПРОВАЛЕНА: config.py липсват настройки: %s.", ", ".join(missing))
        raise SystemExit(1)

    fake_ind = {
        "price": 3.5, "ema9": 3.4, "ema20": 3.2, "vwap": 3.3, "rsi14": 60.0,
        "relative_volume": 4.0, "trend_up": True, "above_vwap": True,
        "orb_breakout": "bullish", "support": 3.0, "resistance": 3.8, "bullish_candle": True,
    }
    try:
        score_symbol("SELFTEST", fake_ind, True, {"has_recent_dilution_filing": False})
    except Exception as e:
        log.critical("СТАРТОВА ПРОВЕРКА ПРОВАЛЕНА: score_symbol() гърми: %s", e)
        raise SystemExit(1)

    log.info("Стартова самопроверка: config.py и scoring.py изглеждат съвместими.")

_startup_self_check()

alpaca = AlpacaClient()
finnhub = FinnhubClient()

app = Flask(__name__)
_status = {"last_full_scan_at": None, "last_fast_check_at": None, "last_watchlist": {}}

@app.route("/")
def health():
    return {"status": "ok", **_status}

def _has_news_catalyst(symbol: str, resumed_symbols: set) -> bool:
    if symbol in resumed_symbols:
        return True
    news = alpaca.get_news(symbol, limit=5) or finnhub.company_news(symbol, days_back=2)
    return bool(news)

_NY_TZ = ZoneInfo("America/New_York")

def _is_market_hours() -> bool:
    now_et = datetime.now(_NY_TZ)
    if now_et.weekday() >= 5:
        return False
    minutes = now_et.hour * 60 + now_et.minute
    pre_market_start = config.PREMARKET_START_HOUR * 60 + config.PREMARKET_START_MINUTE
    regular_close = 16 * 60
    return pre_market_start <= minutes <= regular_close

_MIN_BARS_FOR_INDICATORS = 25

def _score_symbols(symbols) -> list:
    scores = []
    resumed_symbols = set(get_recently_resumed().keys())
    for symbol in symbols:
        try:
            bars = alpaca.get_bars(symbol, timeframe="5Min", limit=100)
            if len(bars) < _MIN_BARS_FOR_INDICATORS:
                fallback = get_bars_yfinance(symbol)
                if len(fallback) > len(bars):
                    bars = fallback
            if len(bars) < _MIN_BARS_FOR_INDICATORS:
                continue
            ind = compute_all(bars)
            if not ind or ind["price"] > config.MAX_UNIVERSE_PRICE:
                continue
            catalyst = _has_news_catalyst(symbol, resumed_symbols)
            dilution = get_sec_dilution_flags(symbol)
            scores.append(score_symbol(symbol, ind, catalyst, dilution))
        except Exception as e:
            log.warning("Грешка при %s: %s", symbol, e)
    return scores

def _maybe_alert_high_potential(symbol: str, meta: dict, result):
    price = (result.raw or {}).get("price") if result else None
    if price:
        meta["peak_price"] = max(meta.get("peak_price") or price, price)

    if result and result.is_high_potential:
        meta["consecutive_high_potential"] = meta.get("consecutive_high_potential", 0) + 1
        peak_price = meta.get("peak_price")
        drawdown_pct = ((peak_price - price) / peak_price * 100) if (peak_price and price) else 0.0
        already_rolling_over = drawdown_pct >= config.PEAK_DRAWDOWN_STOP_PCT
        confirmed = meta["consecutive_high_potential"] >= config.MIN_HIGH_POTENTIAL_CONFIRMATIONS

        if not meta.get("alerted_high_potential"):
            if confirmed and not already_rolling_over:
                if send_alert(f"ВИСОК ПОТЕНЦИАЛ (~{round(config.TARGET_PROFIT_PCT*100)}%)", result):
                    meta["alerted_high_potential"] = True
            elif already_rolling_over:
                log.info("%s: цената вече е паднала, пропускам алърт.", symbol)
    else:
        meta["consecutive_high_potential"] = 0

def run_fast_check():
    if not _is_market_hours():
        return
    current_watchlist = load_watchlist()
    if not current_watchlist:
        return

    scores = _score_symbols(current_watchlist.keys())
    scores_by_symbol = {s.symbol: s for s in scores}

    for symbol, meta in current_watchlist.items():
        result = scores_by_symbol.get(symbol)
        if result:
            meta["last_score"] = result.score
        _maybe_alert_high_potential(symbol, meta, result)

    save_watchlist(current_watchlist)
    _status["last_fast_check_at"] = datetime.now(timezone.utc).isoformat()
    _status["last_watchlist"] = current_watchlist

def run_full_scan():
    if not _is_market_hours():
        return

    log.info("Стартирам пълно сканиране...")
    current_watchlist = load_watchlist()
    universe = set(get_universe()) | set(current_watchlist.keys())

    all_scores = _score_symbols(universe)
    new_watchlist, added, dropped = update_watchlist(current_watchlist, all_scores)

    scores_by_symbol = {s.symbol: s for s in all_scores}
    for symbol, meta in new_watchlist.items():
        _maybe_alert_high_potential(symbol, meta, scores_by_symbol.get(symbol))

    save_watchlist(new_watchlist)
    _status["last_full_scan_at"] = datetime.now(timezone.utc).isoformat()
    _status["last_watchlist"] = new_watchlist
    log.info("Пълно сканиране завършено.")

def _scan_loop():
    run_full_scan()
    schedule.every(config.SCAN_INTERVAL_MINUTES).minutes.do(run_full_scan)
    schedule.every(config.FAST_INTERVAL_MINUTES).minutes.do(run_fast_check)
    while True:
        schedule.run_pending()
        time.sleep(15)

def _self_ping_loop():
    external_url = os.getenv("RENDER_EXTERNAL_URL")
    if not external_url:
        return
    while True:
        time.sleep(config.KEEP_ALIVE_PING_MINUTES * 60)
        try:
            requests.get(external_url, timeout=10)
        except Exception:
            pass

def main():
    thread = threading.Thread(target=_scan_loop, daemon=True)
    thread.start()
    ping_thread = threading.Thread(target=_self_ping_loop, daemon=True)
    ping_thread.start()
    app.run(host="0.0.0.0", port=config.PORT)

if __name__ == "__main__":
    main()
