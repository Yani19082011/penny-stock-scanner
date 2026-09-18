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

Deep research (17.09) намери безплатна алтернатива с РЕАЛЕН marketCap+volume:
StockAnalysis.com има вътрешен __data.json endpoint (SvelteKit "devalue"
флатнат формат - виж _resolve_devalue) за същите gainers/losers/active
страници, но връща directno market cap и volume - без нужда от отделна
Finnhub заявка на всеки тикер. Използваме го като ГЛАВЕН източник за
marketCap филтъра; Finnhub best-effort проверката остава само за
кандидати, за които нямаме StockAnalysis данни (напр. чисто FMP-кандидати).

Universe-ът вече е изграден така:
  1. Обединение на трите безплатни FMP movers endpoint-а + трите
     StockAnalysis.com movers endpoint-а (gainers/losers/active) - двойно
     покритие, повече уникални тикери на обиколка ("да следи колкото може
     повече", по избор на потребителя).
  2. Филтър по цена <= MAX_UNIVERSE_PRICE.
  3. Статичен LARGE_CAP_BLOCKLIST - познати средни/големи компании, които
     понякога излизат евтино/волатилно в movers списъците, но НЕ са penny
     stocks по дух (MARA, NIO, SOFI, AMC и др.).
  4. Реална пазарна капитализация: директно от StockAnalysis.com, където я
     имаме; иначе best-effort през Finnhub (ако FINNHUB_API_KEY е зададен).
     Ако нищо от двете не даде отговор, НЕ филтрираме (по-добре false
     positive, отколкото загубен реален кандидат).
  5. Текущо спрени ("halted") тикери от NYSE-то публично API (halts.py) -
     добавят се като допълнителни кандидати НЕЗАВИСИМО от movers списъците,
     защото halt за новини често предхожда рязко движение, преди то изобщо
     да личи в цена/обем (виж halts.py за детайли).

Ако и FMP, и StockAnalysis, и halts не върнат нищо в диапазона, пада на
статичен FALLBACK_UNIVERSE (грубо, потенциално остаряло - виж бележката там).
"""
import logging
import time

import requests

import config
from data_sources import FinnhubClient
from halts import get_recently_resumed

log = logging.getLogger("universe")

_finnhub = FinnhubClient()

# Познати средни/големи компании, които понякога излизат евтино/волатилно в
# movers списъците, но НЕ са "penny stocks" по дух - изключваме твърдо,
# независимо от цена/движение (директно заради оплакването за MARA/NIO, и
# на 18.09 - SNAP: "даваш ми snapchat за пореден път... искам истински, не
# такива големи известни"). Твърдият blocklist е нарочно НЕЗАВИСИМ от
# market cap API-тата по-долу (StockAnalysis/Finnhub) - те понякога нямат
# данни за конкретен тикер в конкретен момент (виж коментара при
# _passes_market_cap_filter), а известно голямо име не бива да минава само
# защото API-то временно мълчи за него.
LARGE_CAP_BLOCKLIST = {
    "MARA", "RIOT", "NIO", "F", "AMC", "GME", "NOK", "SIRI", "SOFI",
    "PLUG", "FCEL", "BBBY", "BB", "WISH", "CLOV", "SNDL", "NNDM",
    "AAL", "UAL", "CCL", "T", "VZ", "INTC", "PLTR", "LCID", "NKLA",
    "SNAP", "SNAP.US", "PINS", "UBER", "LYFT", "PYPL", "RIVN", "COIN",
    "HOOD", "DKNG", "CHPT", "OPEN", "AFRM", "MRVL",
}

FALLBACK_UNIVERSE = [
    s for s in ["PLUG", "FCEL", "BBIG", "CLOV", "SNDL", "GSAT", "CIDM", "IDEX"]
    if s not in LARGE_CAP_BLOCKLIST
]

MOVERS_ENDPOINTS = ("biggest-gainers", "biggest-losers", "most-actives")
STOCKANALYSIS_SLUGS = ("gainers", "losers", "active")

_BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    ),
}


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


def _resolve_devalue(idx, arr, memo):
    """StockAnalysis.com (SvelteKit) кодира __data.json в "devalue" флатнат
    формат: dict/list стойностите са ИНДЕКСИ към други елементи на arr, не
    директни стойности - трябва рекурсивно да ги "разгънем". Тествано с
    unit test върху синтетичен пример преди деплой - виж коментара по-долу
    при извикването."""
    if idx in memo:
        return memo[idx]
    val = arr[idx]
    if isinstance(val, dict):
        out = {}
        memo[idx] = out
        for k, v in val.items():
            out[k] = _resolve_devalue(v, arr, memo)
        return out
    if isinstance(val, list):
        out = []
        memo[idx] = out
        for v in val:
            out.append(_resolve_devalue(v, arr, memo))
        return out
    return val


def _fetch_stockanalysis_movers(slug: str) -> list[dict]:
    """StockAnalysis.com's markets/{slug}/__data.json - безплатно, без ключ,
    дава реален marketCap+volume (за разлика от FMP-ските movers). Схемата
    НЕ е официално документирана (deep research 17.09, живо потвърдена) -
    ако StockAnalysis.com смени формата си, това ще започне тихо да връща
    [] (виж log.warning по-долу в Render Logs) - fallback-ите (FMP + halts)
    остават да работят независимо."""
    url = f"https://stockanalysis.com/markets/{slug}/__data.json"
    try:
        r = requests.get(url, headers=_BROWSER_HEADERS, timeout=15)
        r.raise_for_status()
        data = r.json()
        arr = data["nodes"][2]["data"]
        root = _resolve_devalue(0, arr, {})
        rows = root.get("data") or []
    except Exception as e:
        log.warning("StockAnalysis.com %s fail: %s", slug, e)
        return []

    results = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        symbol = row.get("s")
        if not symbol:
            continue
        results.append({
            "symbol": symbol,
            "name": row.get("n"),
            "price": row.get("price"),
            "change_pct": row.get("change"),
            "volume": row.get("volume"),
            "market_cap": row.get("marketCap"),
        })
    return results


def _passes_market_cap_filter(symbol: str) -> bool:
    """Best-effort проверка през Finnhub - само за кандидати, за които
    НЯМАМЕ директен marketCap от StockAnalysis.com (виж get_universe)."""
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
    raw_rows = []
    if config.FMP_API_KEY:
        for endpoint in MOVERS_ENDPOINTS:
            raw_rows.extend(_fetch_movers(endpoint))
    else:
        log.warning("Няма FMP_API_KEY - пропускам FMP movers (StockAnalysis.com + halts продължават да работят).")

    # {symbol: known_market_cap_usd_or_None} - StockAnalysis дава реален
    # marketCap директно, спестява ни Finnhub заявка за тези тикери.
    known_market_caps = {}
    candidates = {}

    for row in raw_rows:
        symbol = row.get("symbol")
        price = row.get("price")
        if not symbol or price is None:
            continue
        if symbol in LARGE_CAP_BLOCKLIST or price > config.MAX_UNIVERSE_PRICE:
            continue
        candidates[symbol] = row

    for slug in STOCKANALYSIS_SLUGS:
        for row in _fetch_stockanalysis_movers(slug):
            symbol = row.get("symbol")
            price = row.get("price")
            if not symbol or price is None:
                continue
            if symbol in LARGE_CAP_BLOCKLIST or price > config.MAX_UNIVERSE_PRICE:
                continue
            candidates[symbol] = row
            if row.get("market_cap"):
                known_market_caps[symbol] = row["market_cap"]

    if not candidates:
        log.warning("FMP + StockAnalysis.com не върнаха нито един кандидат в диапазона.")

    symbols = []
    checked = 0
    for symbol in candidates:
        known_cap = known_market_caps.get(symbol)
        if known_cap is not None:
            # Директен marketCap от StockAnalysis.com - без Finnhub заявка.
            if known_cap <= config.MAX_MARKET_CAP_USD:
                symbols.append(symbol)
            continue

        if checked >= config.MAX_MOVERS_CANDIDATES:
            log.info(
                "Достигнат лимит от %d Finnhub проверки за тази обиколка - "
                "останалите кандидати без известен marketCap се пропускат тази обиколка.",
                config.MAX_MOVERS_CANDIDATES,
            )
            break
        if _passes_market_cap_filter(symbol):
            symbols.append(symbol)
        checked += 1
        if config.FINNHUB_API_KEY:
            time.sleep(1.1)  # пести безплатния rate limit на Finnhub (~60/мин)

    # Наскоро ВЪЗОБНОВЕНИ след halt тикери (halts.py) - добавят се
    # НЕЗАВИСИМО от movers/marketCap филтъра по-горе, защото resume след
    # halt за новини е силен catalyst сигнал, често преди изобщо да личи в
    # цена/обем. "Все още спрян" тикер НЕ се добавя тук - не е търгуем,
    # докато не се возобнови (виж коментара в halts.py). main.py ги
    # score-ва по обичайния начин (вкл. цена <= MAX_UNIVERSE_PRICE) и ГИ
    # третира и като catalyst сами по себе си (_has_news_catalyst).
    resumed_symbols = []
    try:
        resumed_symbols = [s for s in get_recently_resumed().keys() if s not in LARGE_CAP_BLOCKLIST]
        if resumed_symbols:
            log.info("Наскоро възобновени след halt тикери (допълнителни кандидати): %s", resumed_symbols)
    except Exception as e:
        log.warning("Грешка при извличане на resumed тикери: %s", e)

    combined = sorted(set(symbols) | set(resumed_symbols))
    if not combined:
        log.warning("Всички кандидати паднаха на филтрите (и няма наскоро възобновени) - fallback списък.")
        return FALLBACK_UNIVERSE

    log.info(
        "Universe тази обиколка (%d тикера, от които %d наскоро възобновени след halt): %s",
        len(combined), len(resumed_symbols), combined,
    )
    return combined
