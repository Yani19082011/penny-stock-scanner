"""
Извлича "универсума" от кандидати - US-listed акции с цена <= config.MAX_UNIVERSE_PRICE.

Основен източник: FMP stock-screener endpoint (безплатен tier го поддържа с
базови филтри). Ако FMP ключ липсва/фейлва, пада на статичен fallback списък
с познати ликвидни penny stocks, за да може скенерът да работи и без ключове
докато ги настройваш (виж README.md).
"""
import logging
import requests

import config

log = logging.getLogger("universe")

FALLBACK_UNIVERSE = [
    "SIRI", "NOK", "SOFI", "PLUG", "FCEL", "BBIG", "CLOV", "SNDL",
    "NIO", "F", "AMC", "GSAT", "CIDM", "IDEX", "MARA", "RIOT",
]


def get_universe() -> list[str]:
    if not config.FMP_API_KEY:
        log.warning("Няма FMP_API_KEY - използвам fallback списък с %d тикера.", len(FALLBACK_UNIVERSE))
        return FALLBACK_UNIVERSE

    try:
        r = requests.get(
            "https://financialmodelingprep.com/stable/company-screener",
            params={
                "priceMoreThan": 0.5,
                "priceLowerThan": config.MAX_UNIVERSE_PRICE,
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
