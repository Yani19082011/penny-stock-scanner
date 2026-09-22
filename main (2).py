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

log = logging.getLogger("main")
alpaca = AlpacaClient()
finnhub = FinnhubClient()
app = Flask(__name__)
_status = {"last_full_scan_at": None, "last_fast_check_at": None, "last_watchlist": {}}

@app.route("/")
def health(): return {"status": "ok", **_status}

def _has_news_catalyst(symbol: str, resumed_symbols: set) -> bool:
    return symbol in resumed_symbols or bool(alpaca.get_news(symbol, limit=5) or finnhub.company_news(symbol, days_back=2))

def _is_market_hours() -> bool:
    now_et = datetime.now(ZoneInfo("America/New_York"))
    if now_et.weekday() >= 5: return False
    return (config.PREMARKET_START_HOUR * 60 + config.PREMARKET_START_MINUTE) <= (now_et.hour * 60 + now_et.minute) <= 16 * 60

def _score_symbols(symbols) -> list:
    scores = []
    resumed_symbols = set(get_recently_resumed().keys())
    for symbol in symbols:
        try:
            bars = alpaca.get_bars(symbol, timeframe="5Min", limit=100)
            if len(bars) < 25:
                fallback = get_bars_yfinance(symbol)
                if len(fallback) > len(bars): bars = fallback
            if len(bars) < 25: continue
            ind = compute_all(bars)
            if not ind or ind["price"] > config.MAX_UNIVERSE_PRICE: continue
            scores.append(score_symbol(symbol, ind, _has_news_catalyst(symbol, resumed_symbols), get_sec_dilution_flags(symbol)))
        except: pass
    return scores

def _maybe_alert_high_potential(symbol: str, meta: dict, result):
    price = (result.raw or {}).get("price") if result else None
    if price: meta["peak_price"] = max(meta.get("peak_price") or price, price)
    if result and result.is_high_potential:
        meta["consecutive_high_potential"] = meta.get("consecutive_high_potential", 0) + 1
        if not meta.get("alerted_high_potential") and meta["consecutive_high_potential"] >= config.MIN_HIGH_POTENTIAL_CONFIRMATIONS:
            if send_alert("ВИСОК ПОТЕНЦИАЛ", result): meta["alerted_high_potential"] = True
    else: meta["consecutive_high_potential"] = 0

def run_fast_check():
    if not _is_market_hours(): return
    wl = load_watchlist()
    if not wl: return
    scores = {s.symbol: s for s in _score_symbols(wl.keys())}
    for symbol, meta in wl.items():
        res = scores.get(symbol)
        if res: meta["last_score"] = res.score
        _maybe_alert_high_potential(symbol, meta, res)
    save_watchlist(wl)

def run_full_scan():
    if not _is_market_hours(): return
    wl = load_watchlist()
    new_wl, _, _ = update_watchlist(wl, _score_symbols(set(get_universe()) | set(wl.keys())))
    save_watchlist(new_wl)

def _scan_loop():
    run_full_scan()
    schedule.every(config.SCAN_INTERVAL_MINUTES).minutes.do(run_full_scan)
    schedule.every(config.FAST_INTERVAL_MINUTES).minutes.do(run_fast_check)
    while True:
        schedule.run_pending()
        time.sleep(15)

def main():
    threading.Thread(target=_scan_loop, daemon=True).start()
    app.run(host="0.0.0.0", port=config.PORT)

if __name__ == "__main__": main()
