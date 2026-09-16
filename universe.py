"""
Извлича "универсума" от кандидати - US-listed акции с цена <= config.MAX_UNIVERSE_PRICE
И пазарна капитализация <= config.MAX_MARKET_CAP_USD (за да са РЕАЛНИ penny
stocks - малки, спекулативни компании - не просто големи имена като MARA,
NIO, F, AMC, които случайно търгуват евтино в момента без да са "penny").

Основен източник: FMP stock-screener endpoint (безплатен tier го поддържа с
базови филтри, включително marketCapLowerThan). Ако FMP ключ липсва/фейлва,
пада на статичен FALLBACK_UNIVERSE.

ВАЖНО: FALLBACK_UNIVERSE НЕ е надежден начин да гарантираме "истински penny
stock" - цени и пазарни капитализации се менят постоянно, а статичен списък
от даден момент бързо остарява (компания може да поскъпне, да фалира, да
направи reverse split и т.н.). Затова силно препоръчваме да вземеш безплатен
FMP API ключ (5 мин регистрация на financialmodelingprep.com/register) - само
тогава реално се филтрира и по цена, И по пазарна капитализация динамично.
Без ключ, fallback списъкът е само груба, потенциално остаряла отправна точка.
"""
import logging
import requests

import config

log = logging.getLogger("universe")

FALLBACK_UNIVERSE = [
    "PLUG", "FCEL", "BBIG", "CLOV", "SNDL", "GSAT", "CIDM", "IDEX",
]


def get_universe() -> list[str]:
    if not config.FMP_API_KEY:
        log.warning(
            "Няма FMP_API_KEY - използвам статичен fallback списък с %d тикера "
            "(НЕ гарантирано 'истински' penny stocks по market cap - виж бележката горе).",
            len(FALLBACK_UNIVERSE),
        )
        return FALLBACK_UNIVERSE

    try:
        r = requests.get(
            "https://financialmodelingprep.com/stable/company-screener",
            params={
                "priceMoreThan": 0.5,
                "priceLowerThan": config.MAX_UNIVERSE_PRICE,
                "marketCapLowerThan": config.MAX_MARKET_CAP_USD,
                "volumeMoreThan": 300000,
                "exchange": "nasdaq,nyse,amex",
                "isActivelyTrading": "true",
                "limit": 100,
                "apikey": config.FMP_API_KEY,
            },
            timeout=15,
        )
        r.raise_for_status()
        data = r.json()
        symbols = [row["symbol"] for row in data if row.get("symbol")]
        if symbols:
            return symbols
        log.warning("FMP screener върна 0 резултата - fallback списък.")
    except Exception as e:
        log.warning("FMP screener fail: %s - fallback списък.", e)

    return FALLBACK_UNIVERSE
