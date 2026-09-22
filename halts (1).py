import logging
import os
import time
import requests
import xml.etree.ElementTree as ET

log = logging.getLogger("halts")
NASDAQ_HALTS_RSS_URL = "https://www.nasdaqtrader.com/rss.aspx?feed=tradehalts"
_BROWSER_HEADERS = {"User-Agent": "Mozilla/5.0"}
RESUME_SIGNAL_WINDOW_MINUTES = int(os.getenv("RESUME_SIGNAL_WINDOW_MINUTES", "90"))
HALTS_MIN_REFRESH_SECONDS = int(os.getenv("HALTS_MIN_REFRESH_SECONDS", "300"))
_previous_halts: dict = {}
_recently_resumed: dict = {}
_last_fetch_at: float = 0.0

def get_current_halts() -> dict | None:
    try:
        r = requests.get(NASDAQ_HALTS_RSS_URL, headers=_BROWSER_HEADERS, timeout=10)
        r.raise_for_status()
        root = ET.fromstring(r.content)
        halts = {}
        for item in root.findall(".//item"):
            title = item.find("title")
            description = item.find("description")
            if title is not None and title.text:
                symbol_candidate = title.text.replace("Trading Halt", "").replace("-", "").replace("Symbol:", "").strip()
                if " " in symbol_candidate:
                    symbol_candidate = symbol_candidate.split()[0]
                symbol = symbol_candidate.upper().strip()
                if not symbol: continue
                desc_text = description.text if description is not None else ""
                halts[symbol] = {
                    "issuer_name": "Unknown via RSS", "source_exchange": "NASDAQ/NYSE", "reason": desc_text,
                    "halt_date": None, "halt_time": None, "resumption_date": None, "resumption_time": None
                }
        return halts
    except Exception as e:
        log.warning("NASDAQ halts RSS fail: %s", e)
        return None

def get_recently_resumed() -> dict:
    global _previous_halts, _recently_resumed, _last_fetch_at
    now = time.time()
    if _last_fetch_at and (now - _last_fetch_at) < HALTS_MIN_REFRESH_SECONDS:
        return dict({s: i for s, i in _recently_resumed.items() if i.get("resumed_at", 0) >= now - RESUME_SIGNAL_WINDOW_MINUTES * 60})
    current = get_current_halts()
    _last_fetch_at = now
    if current is None:
        return dict({s: i for s, i in _recently_resumed.items() if i.get("resumed_at", 0) >= now - RESUME_SIGNAL_WINDOW_MINUTES * 60})
    resumed_now = [symbol for symbol in _previous_halts if symbol not in current]
    for symbol in resumed_now:
        entry = dict(_previous_halts[symbol])
        entry["resumed_at"] = now
        _recently_resumed[symbol] = entry
    _previous_halts = current
    return dict({s: i for s, i in _recently_resumed.items() if i.get("resumed_at", 0) >= now - RESUME_SIGNAL_WINDOW_MINUTES * 60})
