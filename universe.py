"""
Извлича "универсума" от кандидати - US-listed акции с цена <= config.MAX_UNIVERSE_PRICE,
филтрирани да са РЕАЛНИ penny stocks (малки, спекулативни компании), не просто
големи имена като MARA, NIO, F, AMC, които случайно търгуват евтино в момента.

ВАЖНО ОТКРИТИЕ (потвърдено с реалния FMP ключ на потребителя): FMP-ският
"stable" company-screener И quote endpoint-ите връщат 402 Payment Required -
изискват платен план, безплатният ключ НЕ ги покрива. Единствените FMP
endpoint-и, които РЕАЛНО работят безплатно, са трите "market movers":
biggest-gainers, biggest-losers, most-actives - и трите връщат само
symbol/price/name/change/changesPercentage/exchange - БЕЗ marketCap, БЕЗ
volume поле.

Затова universe-ът вече е изграден така:
  1. Обединение на трите безплатни FMP movers endpoint-а - това директно
     покрива и оригиналната молба за "днешни trending/top movers penny
     stocks" (Trading212-style), защото това е буквално единствения начин
     да видим КОЙ се движи точно сега без платен план.
  2. Филтър по цена <= MAX_UNIVERSE_PRICE (единственото числово поле,
     което movers endpoint-ите реално дават).
  3. Статичен LARGE_CAP_BLOCKLIST - познати средни/големи компании, които
     понякога излизат евтино/волатилно в movers списъците, но НЕ са penny
     stocks по дух (MARA, NIO, SOFI, AMC и др. - директно от оплакването на
     потребителя).
  4. Best-effort реална пазарна капитализация през Finnhub (безплатен tier,
     ако FINNHUB_API_KEY е зададен) - виж config.MAX_MARKET_CAP_USD. Ако
     Finnhub полето/ключа липсва или заявката фейлне, НЕ филтрираме тук
     (по-добре false positive, отколкото да изгубим реален кандидат) -
     blocklist-ът + цената остават основната защита.

Ако FMP ключ липсва, или движърите не върнат нищо в диапазона, пада на
статичен FALLBACK_UNIVERSE (грубо, потенциално остаряло - виж бележката там).
"""
import logging
import time

import requests

import config
from data_sources import FinnhubClient

log = logging.getLogger("universe")

_finnhub = FinnhubClient()

# Познати средни/големи компании, които понякога излизат евтино/волатилно в
# movers списъците, но НЕ са "penny stocks" по дух - изключваме твърдо,
# независимо от цена/движение (директно заради оплакването за MARA/NIO).
LARGE_CAP_BLOCKLIST = {
    "MARA", "RIOT", "NIO", "F", "AMC", "GME", "NOK", "SIRI", "SOFI",
    "PLUG", "FCEL", "BBBY", "BB", "WISH", "CLOV", "SNDL", "NNDM",
    "AAL", "UAL", "CCL", "T", "VZ", "INTC", "PLTR", "LCID", "NKLA",
}

FALLBACK_UNIVERSE = [
    s for s in ["PLUG", "FCEL", "BBIG", "CLOV", "SNDL", "GSAT", "CIDM", "IDEX"]
    if s not in LARGE_CAP_BLOCKLIST
]

MOVERS_ENDPOINTS = ("biggest-gainers", "biggest-losers", "most-actives")


def _fetch_movers(endpoint: str) -> list[dict]:
    try:
        r = requests.get(
            f"https://financialmodelingprep.com/stable/{endpoint}",
            params={"apikey": config.FMP_API_KEY},
            timeout=15,
        )
        r.raise_for_status()
        return r.json() or []
    except Exception as e:
        log.warning("FMP %s fail: %s", endpoint, e)
        return []


def _passes_market_cap_filter(symbol: str) -> bool:
    """Best-effort проверка през Finnhub - виж бележката в config.py."""
    if not config.FINNHUB_API_KEY:
        return True
    try:
        metrics = _finnhub.basic_financials(symbol)
        market_cap_millions = metrics.get("marketCapitalization")
        if market_cap_millions is None:
            return True
        return float(market_cap_millions) * 1_000_000 <= config.MAX_MARKET_CAP_USD
    except Exception as e:
        log.warning("Finnhub market cap fail за %s: %s", symbol, e)
        return True


def get_universe() -> list[str]:
    if not config.FMP_API_KEY:
        log.warning(
            "Няма FMP_API_KEY - използвам статичен fallback списък с %d тикера "
            "(НЕ гарантирано 'истински' penny stocks - виж бележката горе).",
            len(FALLBACK_UNIVERSE),
        )
        return FALLBACK_UNIVERSE

    raw_rows = []
    for endpoint in MOVERS_ENDPOINTS:
        raw_rows.extend(_fetch_movers(endpoint))

    candidates = {}
    for row in raw_rows:
        symbol = row.get("symbol")
        price = row.get("price")
        if not symbol or price is None:
            continue
        if symbol in LARGE_CAP_BLOCKLIST:
            continue
        if price > config.MAX_UNIVERSE_PRICE:
            continue
        candidates[symbol] = row

    if not candidates:
        log.warning("FMP movers endpoint-ите върнаха 0 кандидата в диапазона - fallback списък.")
        return FALLBACK_UNIVERSE

    symbols = []
    checked = 0
    for symbol in candidates:
        if checked >= config.MAX_MOVERS_CANDIDATES:
            log.info(
                "Достигнат лимит от %d Finnhub проверки за тази обиколка - "
                "останалите %d кандидата се пропускат тази обиколка.",
                config.MAX_MOVERS_CANDIDATES, len(candidates) - checked,
            )
            break
        if _passes_market_cap_filter(symbol):
            symbols.append(symbol)
        checked += 1
        if config.FINNHUB_API_KEY:
            time.sleep(1.1)  # пести безплатния rate limit на Finnhub (~60/мин)

    if not symbols:
        log.warning("Всички кандидати паднаха на филтрите - fallback списък.")
        return FALLBACK_UNIVERSE

    log.info("Universe тази обиколка (%d тикера от %d movers): %s", len(symbols), len(raw_rows), symbols)
    return symbols
