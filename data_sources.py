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
    Проверка в SEC EDGAR full-text search за скорошни S-1/S-3/424B filings
    (класически dilution риск за penny stocks). Безплатно, без API ключ.
    """
    try:
        r = requests.get(
            "https://efts.sec.gov/LATEST/search-index?q=%22{}%22&forms=S-1,S-3,424B5".format(symbol),
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
