"""
NYSE текущи търговски спирания (trading halts) - безплатен публичен API,
БЕЗ ключ, покрива halts на всички борси (не само NYSE-listed - виж
"sourceExchange" полето по-долу), не само NYSE тикери.

Защо е полезно: акция, която току-що е ВЪЗОБНОВЕНА след halt за новини, е
класически сигнал за предстоящо рязко движение - нещо, което обикновените
"movers" списъци (universe.py) пропускат, докато движението вече не се е
случило и не личи в цената/обема. Затова тук добавяме такива тикери като
допълнителни кандидати в universe-а - main.py след това ги score-ва по
обичайния начин (цена, индикатори и т.н.), но ги третира и като
"catalyst" сами по себе си (виж main.py::_has_news_catalyst) - защото
halt за новини почти винаги означава реален catalyst, дори когато
безплатните ни новинарски източници (Alpaca/Finnhub) още не са го
хванали.

ВАЖНО: "текущо спрян" тикер НЕ Е директно търгуем (не можеш да го купиш,
докато не се възобнови) - затова НЕ добавяме такива директно в universe-а.
Вместо това следим кои тикери ИЗЧЕЗВАТ от NYSE-ския "current" списък между
последователни проверки (get_recently_resumed) - това означава, че току-що
са възобновени, което Е реално търгуем момент. NYSE няма потвърден
безплатен endpoint само за "наскоро възобновени" - изведохме сигнала сами
чрез diff между поредните извиквания на /api/trade-halts/current.

Проучени, но НЕ включени тук (deep research 17.09):
  - SEC-ският RSS feed за trading suspensions (https://www.sec.gov/
    enforcement-litigation/trading-suspensions/rss) е потвърден жив, НО
    не дава тикер символ изобщо - само име на компания + линк към PDF
    заповед. За да извадим тикера, ще трябва да парсваме всеки PDF (нов
    dependency + бавно + чупливо) - пропуснато засега, кажи ако все пак
    го искаш.
  - StockTitan-ският halt tracker е HTML страница (не JSON API) - по-
    чуплив източник за scrape-ване без да сме видели живо структурата му.

Endpoint + JSON схема потвърдени чрез живо тестване (17.09):
  GET https://www.nyse.com/api/trade-halts/current
  {
    "totalCount": <int>,
    "results": {
      "tradeHalts": [
        {
          "symbol": "XYZ",
          "issuerName": "...",
          "sourceExchange": "Nasdaq" | "NYSE" | ...,
          "reason": "News Pending" | ...,
          "formatedHaltDate": "2026-09-17",
          "formatedHaltTime": "07:55:00",
          "formatedResumptionDate": null,
          "formatedResumptionTime": null,
        },
        ...
      ]
    }
  }
Забележка: "formated" (с една буква "t") е точно както идва от NYSE, не
печатна грешка тук. Историческият download endpoint НЕ е потвърден да
работи (връща 13 байта при тест) - затова тук ползмаве само "current".
Ако NYSE промени схемата, кодът е писан defensively - виж лога
"RAW NYSE halt payload" в Render Logs за диагностика.
"""
import logging
import os
import time

import requests

log = logging.getLogger("halts")

NYSE_CURRENT_HALTS_URL = "https://www.nyse.com/api/trade-halts/current"

_BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.nyse.com/trade-halts/current",
}

RESUME_SIGNAL_WINDOW_MINUTES = int(os.getenv("RESUME_SIGNAL_WINDOW_MINUTES", "90"))
HALTS_MIN_REFRESH_SECONDS = int(os.getenv("HALTS_MIN_REFRESH_SECONDS", "300"))

_previous_halts: dict = {}
_recently_resumed: dict = {}
_last_fetch_at: float = 0.0


def get_current_halts() -> dict | None:
    """{symbol: {...halt info...}} за всички текущо спрени тикери в момента.
    None (НЕ {}) при грешка/липса на данни от заявката - НИКОГА не гърми
    извикващия код, но виж get_recently_resumed() за защо разликата между
    "None = заявката падна" и "{} = реално няма спрени тикери" е важна: ако
    върнехме {} и при мрежова грешка, get_recently_resumed() би изтълкувал
    ВСЕКИ преди това спрян тикер като "току-що възобновен" (защото не се
    вижда вече в текущия списък) - фалшив catalyst сигнал само заради
    временна грешка в заявката, не заради реално възобновяване."""
    try:
        r = requests.get(NYSE_CURRENT_HALTS_URL, headers=_BROWSER_HEADERS, timeout=10)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        log.warning("NYSE halts fail: %s", e)
        return None

    rows = (
        (data.get("results") or {}).get("tradeHalts")
        or data.get("tradeHalts")
        or (data.get("results") if isinstance(data.get("results"), list) else None)
        or []
    )

    halts = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        symbol = row.get("symbol") or row.get("Symbol") or row.get("issueSymbol")
        if not symbol:
            continue
        halts[str(symbol).upper().strip()] = {
            "issuer_name": row.get("issuerName"),
            "source_exchange": row.get("sourceExchange"),
            "reason": row.get("reason"),
            "halt_date": row.get("formatedHaltDate"),
            "halt_time": row.get("formatedHaltTime"),
            "resumption_date": row.get("formatedResumptionDate"),
            "resumption_time": row.get("formatedResumptionTime"),
        }

    if halts:
        log.debug("RAW NYSE halt payload (%d спрени тикера): %s", len(halts), halts)
    return halts


def get_recently_resumed() -> dict:
    global _previous_halts, _recently_resumed, _last_fetch_at

    now = time.time()
    if _last_fetch_at and (now - _last_fetch_at) < HALTS_MIN_REFRESH_SECONDS:
        cutoff = now - RESUME_SIGNAL_WINDOW_MINUTES * 60
        _recently_resumed = {
            symbol: info for symbol, info in _recently_resumed.items()
            if info.get("resumed_at", 0) >= cutoff
        }
        return dict(_recently_resumed)

    current = get_current_halts()
    _last_fetch_at = now

    if current is None:
        log.debug("NYSE halts заявката се провали - пропускам resume-diff тази обиколка.")
        cutoff = now - RESUME_SIGNAL_WINDOW_MINUTES * 60
        _recently_resumed = {
            symbol: info for symbol, info in _recently_resumed.items()
            if info.get("resumed_at", 0) >= cutoff
        }
        return dict(_recently_resumed)

    resumed_now = [symbol for symbol in _previous_halts if symbol not in current]
    for symbol in resumed_now:
        entry = dict(_previous_halts[symbol])
        entry["resumed_at"] = now
        _recently_resumed[symbol] = entry
    if resumed_now:
        log.info("Тикери, наскоро възобновени след halt (catalyst сигнал): %s", resumed_now)

    cutoff = now - RESUME_SIGNAL_WINDOW_MINUTES * 60
    _recently_resumed = {
        symbol: info for symbol, info in _recently_resumed.items()
        if info.get("resumed_at", 0) >= cutoff
    }

    _previous_halts = current
    return dict(_recently_resumed)
