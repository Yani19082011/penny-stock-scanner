"""
Wrapper-и около външните API-та. Всеки метод връща pandas DataFrame или
обикновен Python обект - за да могат indicators.py / scoring.py да работят
без да знаят откъде идват данните.
"""
import time
import logging
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

import requests
import pandas as pd

import config

log = logging.getLogger("data_sources")


class AlpacaClient:
    """Тънка обвивка над Alpaca Market Data API v2 (безплатен IEX feed)."""

    def __init__(self):
        self.headers = {
            "APCA-API-KEY-ID": config.ALPACA_API_KEY,
            "APCA-API-SECRET-KEY": config.ALPACA_SECRET_KEY,
        }

    def get_bars(self, symbol: str, timeframe: str = "5Min", limit: int = 200) -> pd.DataFrame:
        """Последните `limit` свещи за symbol. timeframe напр. '1Min','5Min','1Day'."""
        url = f"{config.ALPACA_DATA_URL}/v2/stocks/{symbol}/bars"
        params = {"timeframe": timeframe, "limit": limit, "feed": "iex"}
        try:
            r = requests.get(url, headers=self.headers, params=params, timeout=10)
            r.raise_for_status()
            bars = r.json().get("bars", [])
        except Exception as e:
            log.warning(f"Alpaca bars fail за {symbol}: {e}")
            return pd.DataFrame()
        if not bars:
            return pd.DataFrame()
        df = pd.DataFrame(bars)
        df.rename(columns={"t": "time", "o": "open", "h": "high", "l": "low",
                            "c": "close", "v": "volume"}, inplace=True)
        df["time"] = pd.to_datetime(df["time"])
        return df.set_index("time")

    def get_news(self, symbol: str, limit: int = 10):
        """Alpaca News API (Benzinga-powered), безплатен с paper акаунт."""
        url = "https://data.alpaca.markets/v1beta1/news"
        params = {"symbols": symbol, "limit": limit}
        try:
            r = requests.get(url, headers=self.headers, params=params, timeout=10)
            r.raise_for_status()
            return r.json().get("news", [])
        except Exception as e:
            log.warning(f"Alpaca news fail за {symbol}: {e}")
            return []


class FinnhubClient:
    BASE = "https://finnhub.io/api/v1"

    def __init__(self):
        self.key = config.FINNHUB_API_KEY

    def _get(self, path, **params):
        if not self.key:
            return None
        params["token"] = self.key
        try:
            r = requests.get(f"{self.BASE}{path}", params=params, timeout=10)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            log.warning(f"Finnhub {path} fail: {e}")
            return None

    def company_news(self, symbol: str, days_back: int = 3):
        today = datetime.now(timezone.utc).date()
        frm = today - timedelta(days=days_back)
        return self._get("/company-news", symbol=symbol, **{"from": str(frm), "to": str(today)}) or []

    def basic_financials(self, symbol: str):
        data = self._get("/stock/metric", symbol=symbol, metric="all")
        return (data or {}).get("metric", {})

    def insider_transactions(self, symbol: str):
        data = self._get("/stock/insider-transactions", symbol=symbol)
        return (data or {}).get("data", [])


def get_bars_yfinance(symbol: str, interval: str = "5m", period: str = "5d", limit: int = 100) -> pd.DataFrame:
    """Fallback източник, когато Alpaca IEX връща твърде малко свещи -
    типично през pre-market (IEX сам по себе си покрива само ~2.5% от обема
    на пазара по документацията на Alpaca), но и през редовна сесия при
    силно неликвидни penny stocks. yfinance е напълно БЕЗПЛАТЕН, без API
    ключ, и обхваща консолидирани данни от повече борси (не само IEX),
    включително pre/post market с prepost=True. Забавянето спрямо реално
    време е типично няколко минути - не е "истински" real-time като платен
    feed, но е много по-пълен от самостоятелния безплатен IEX feed."""
    try:
        import yfinance as yf
        df = yf.Ticker(symbol).history(period=period, interval=interval, prepost=True)
        if df.empty:
            return pd.DataFrame()
        df = df.rename(columns={
            "Open": "open", "High": "high", "Low": "low", "Close": "close", "Volume": "volume",
        })
        return df[["open", "high", "low", "close", "volume"]].tail(limit)
    except Exception as e:
        log.warning("yfinance bars fail за %s: %s", symbol, e)
        return pd.DataFrame()


def get_last_regular_session_price(symbol: str) -> float | None:
    """Sanity-check помощник (13.10, по реален инцидент - CLWT алърт показа
    "Цена: $2.15", докато потребителят твърди, че реалната цена не е
    минавала над ~$1.56 около това време - виж main.py::_price_is_sane /
    config.PRICE_SANITY_CHECK_* за пълния контекст). Разликата от
    get_bars_yfinance по-горе: тук е 1-минутна свещ и prepost=False (САМО
    редовна сесия) - умишлено, защото целта е проверка, не самия сигнал:
    "днешният" ред на ДНЕВНИЯ бар (interval='1d', prepost=True) е още
    недовършена свещ, докато пазарът е отворен, и при силно неликвиден
    penny stock единичен грешен/нереален принт (или остатъчен pre-market
    принт) може временно да изглежда като "последна цена". 1-минутната
    редовна-сесийна свещ е по-малко податлива на точно този вид артефакт,
    защото идва от отделна, по-фина агрегация.

    ПОПРАВКА (13.10, по ВТОРИ реален инцидент - LNKS алърт показа $2.27,
    докато потребителят провери графиката 2 мин по-късно и цената НИКОГА не
    е стигала $2.27 - т.е. самата sanity-check проверка не се е задействала
    навреме): yfinance 1-минутните данни често липсват точно за силно
    неликвидни/слабо следени penny stocks - именно тези, които най-много се
    нуждаят от проверка. Преди тук просто връщахме None (викащият код тогава
    "fail-open" - пропуска проверката), без резервен опит. Сега, ако
    yfinance върне празно/нищо, пробваме Alpaca IEX ('1Min' бар, виж
    AlpacaClient.get_bars) като ВТОРИ независим източник, преди да се
    откажем напълно - двата извора трудно биха имали СЪЩАТА грешка
    едновременно. Плюс явен лог и за двата провала (преди "празно" изобщо
    не се логваше - невъзможно беше да се диагностицира дали проверката
    изобщо е пробвана).

    Връща None само ако И ДВАТА извора не дадат данни - викащият код тогава
    НЕ наказва алърта заради собствена мрежова грешка, просто пропуска
    проверката (виж main.py::_price_is_sane)."""
    try:
        import yfinance as yf
        df = yf.Ticker(symbol).history(period="1d", interval="1m", prepost=False)
        if not df.empty:
            return float(df["Close"].iloc[-1])
        log.info("yfinance 1-мин sanity-check: няма данни за %s - пробвам Alpaca IEX като резерва.", symbol)
    except Exception as e:
        log.warning("yfinance 1-мин sanity-check fail за %s: %s - пробвам Alpaca IEX като резерва.", symbol, e)

    try:
        alpaca_df = AlpacaClient().get_bars(symbol, timeframe="1Min", limit=1)
        if not alpaca_df.empty:
            return float(alpaca_df["close"].iloc[-1])
        log.warning("Alpaca IEX резервна sanity-check проверка също върна празно за %s - проверката се пропуска.", symbol)
    except Exception as e:
        log.warning("Alpaca IEX резервна sanity-check проверка се провали за %s: %s - проверката се пропуска.", symbol, e)

    return None


def get_minute_bars_batch(symbols: list[str], lookback_minutes: int = 15) -> dict[str, "pd.DataFrame"]:
    """Bulk 1-минутни свещи за НЯКОЛКО тикера наведнъж (yfinance) - за
    main.py::run_price_spike_scan (01.10, по изрична спецификация на
    потребителя за ценови+обемен scanner). Едно yf.download() повикване за
    целия списък е по-леко за yfinance-ския (неофициален, reverse-engineered)
    rate limit, отколкото по едно отделно повикване на тикер - но пак не е
    гарантирано (виж честите 429 предупреждения в живите Render логове) -
    при частичен провал просто връщаме каквото е успяло да се свали +
    warning в лога, НЕ гърмим целия scan заради един лош тикер.

    prepost=True включва pre/post market свещи - нужно е изрично, за да
    хванем pre-market скок (целта на цялата функция - потребителят иска да
    влиза 10-15 мин ПРЕДИ скока, обичайно точно в pre-market).

    ВАЖНО (02.10, по реален "exceeded its memory limit" инцидент на Render -
    виж config.py за пълния контекст): threads=True ПРЕМАХНАТО нарочно -
    паралелните downloads трупаха памет по-бързо от 512MB лимита на Render
    free tier, когато функцията се вика на всяка минута. Сега е
    последователно (по-бавно, но стабилно по памет) + изрично чистим
    references-ите към суровия `data` DataFrame и викаме gc.collect() в
    края, за да върнем паметта към ОС веднага, вместо да чакаме Python да го
    направи сам (pandas DataFrame-ите са известни с това, че фрагментират
    паметта при чест repeat-call в дълго-живеещ процес)."""
    result: dict = {}
    if not symbols:
        return result
    try:
        import yfinance as yf
        data = yf.download(
            tickers=" ".join(symbols), period="1d", interval="1m",
            group_by="ticker", prepost=True, progress=False, threads=False,
        )
    except Exception as e:
        log.warning("yfinance bulk 1-мин свещи се провалиха за %d тикера: %s", len(symbols), e)
        data = None

    if data is not None and not data.empty:
        for symbol in symbols:
            try:
                df = data[symbol] if len(symbols) > 1 else data
                df = df.rename(columns={
                    "Open": "open", "High": "high", "Low": "low", "Close": "close", "Volume": "volume",
                })
                df = df.dropna(subset=["close", "volume"])
                if not df.empty:
                    result[symbol] = df[["open", "high", "low", "close", "volume"]].tail(lookback_minutes).copy()
            except Exception:
                continue  # този тикер липсва/друга форма в bulk резултата - individualния fallback по-долу го хваща
    del data  # освобождаваме големия суров multi-ticker DataFrame веднага, не чакаме края на функцията

    # Fallback поотделно само за тикерите, които bulk заявката не покри.
    missing = [s for s in symbols if s not in result]
    for symbol in missing:
        df = get_bars_yfinance(symbol, interval="1m", period="1d", limit=lookback_minutes)
        if not df.empty:
            result[symbol] = df

    import gc
    gc.collect()
    return result


class FMPClient:
    BASE = "https://financialmodelingprep.com/stable"

    def __init__(self):
        self.key = config.FMP_API_KEY

    def stock_news(self, symbol: str, limit: int = 10):
        if not self.key:
            return []
        try:
            r = requests.get(
                f"{self.BASE}/news/stock",
                params={"symbols": symbol, "limit": limit, "apikey": self.key},
                timeout=10,
            )
            r.raise_for_status()
            return r.json()
        except Exception as e:
            log.warning(f"FMP news fail за {symbol}: {e}")
            return []


def get_google_news_rss(symbol: str, limit: int = 5) -> list:
    """НОВ безплатен fallback за news catalyst (23.09) - виж бележката в
    main.py::_has_news_catalyst за защо се появи: FMPClient.stock_news
    започна да връща 402 Payment Required (текущият FMP ключ на потребителя
    не покрива news endpoint-а - изисква платен план, потвърдено в живи
    Render логове), а самостоятелно Alpaca News API + Finnhub company-news
    имат доста тясно безплатно покритие точно за нискoликвидни penny
    stocks. Google News RSS е напълно безплатен, БЕЗ API ключ, без
    официален договор за стабилност (Google може да го промени/спре по
    всяко време, без предупреждение) - затова е ДОПЪЛНИТЕЛЕН fallback, не
    замяна на другите.

    ЧЕСТНА БЕЛЕЖКА за качеството: заявката е нарочно стеснена с финансови
    ключови думи (stock/shares/nasdaq/nyse/trading), за да намали шанса за
    напълно ирелевантни съвпадения при тикери, които са и обикновени думи
    (напр. "SOS") - но не е перфектно, все пак е текстово търсене, не
    директна ticker->company справка. Тъй като catalyst=True е ТВЪРДО
    условие (AND, не просто точки) за 'ВИСОК ПОТЕНЦИАЛ' алърт (виж
    scoring.py::ScoreResult.is_high_potential), фалшиво съвпадение тук може
    да допринесе за алърт, който технически не би трябвало да излезе - виж
    README.md, ако искаш да изключиш този fallback (просто не го викай в
    main.py)."""
    query = quote(f'"{symbol}" (stock OR shares OR nasdaq OR nyse OR trading)')
    url = f"https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"
    try:
        r = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        r.raise_for_status()
        root = ET.fromstring(r.content)
        items = root.findall(".//item")[:limit]
        return [
            {
                "title": (item.findtext("title") or "").strip(),
                "link": (item.findtext("link") or "").strip(),
                "published": (item.findtext("pubDate") or "").strip(),
            }
            for item in items
            if item.findtext("title")
        ]
    except Exception as e:
        log.warning(f"Google News RSS fail за {symbol}: {e}")
        return []


def get_sec_dilution_flags(symbol: str) -> dict:
    """
    Проверка в SEC EDGAR full-text search за СКОРОШНИ S-1/S-3/424B filings
    (класически dilution риск за penny stocks). Безплатно, без API ключ.

    ПОПРАВКА (19.10, по реален инцидент - потребителят докладва "3 работни
    дни без НИТО един email", а логовете показаха по 2-3 тикера на ден със
    score 100, ВСИЧКИ блокирани от dilution filing): преди заявката НЯМАШЕ
    ограничение по дата изобщо - проверяваше дали символът се среща в S-1/
    S-3/424B5 filing от ВСИКОГА (EDGAR full-text search индексът стига до
    2001 г.), въпреки че коментарът тук (и config.PRICE_SANITY_CHECK_*
    стила на документация другаде в проекта) явно казва "скорошни". Почти
    всеки penny stock има S-1 от самото си IPO или S-3 shelf registration
    в историята си някъде - т.е. старата логика на практика блокираше
    ПОЧТИ ВСИЧКО завинаги, не само реален активен dilution риск. Сега
    заявката взима startdt/enddt (единствените официално документирани
    параметри за дата на EDGAR full-text search API - виж README.md
    бележка/коментар тук) - прозорец от config.DILUTION_LOOKBACK_DAYS назад
    от днес. Филинг отпреди 90 дни е реален "скоро предстои dilution"
    сигнал; филинг отпреди 3 години не е - точно разликата, която старата
    заявка пропускаше."""
    try:
        today = datetime.now(timezone.utc).date()
        start = today - timedelta(days=config.DILUTION_LOOKBACK_DAYS)
        r = requests.get(
            "https://efts.sec.gov/LATEST/search-index?q=%22{}%22&forms=S-1,S-3,424B5&startdt={}&enddt={}".format(
                symbol, start.isoformat(), today.isoformat(),
            ),
            timeout=10,
            headers={"User-Agent": "penny-stock-scanner contact@example.com"},
        )
        if r.status_code != 200:
            return {"has_recent_dilution_filing": False}
        hits = r.json().get("hits", {}).get("total", {}).get("value", 0)
        return {"has_recent_dilution_filing": hits > 0}
    except Exception as e:
        log.warning(f"SEC EDGAR fail за {symbol}: {e}")
        return {"has_recent_dilution_filing": False}
