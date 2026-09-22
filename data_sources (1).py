"""
Wrapper-и около външните API-та. Премахнат изцяло FMPClient.
"""
import time
import logging
from datetime import datetime, timedelta, timezone

import requests
import pandas as pd

import config

log = logging.getLogger("data_sources")


class AlpacaClient:
    def __init__(self):
        self.headers = {
            "APCA-API-KEY-ID": config.ALPACA_API_KEY,
            "APCA-API-SECRET-KEY": config.ALPACA_SECRET_KEY,
        }

    def get_bars(self, symbol: str, timeframe: str = "5Min", limit: int = 200) -> pd.DataFrame:
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
        url = "https://alpaca.markets"
        params = {"symbols": symbol, "limit": limit}
        try:
            r = requests.get(url, headers=self.headers, params=params, timeout=10)
            r.raise_for_status()
            return r.json().get("news", [])
        except Exception as e:
            log.warning(f"Alpaca news fail за {symbol}: {e}")
            return []


class FinnhubClient:
    BASE = "https://finnhub.io"

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
    try:
        import yfinance as yf
        session = requests.Session()
        session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        })
        ticker = yf.Ticker(symbol, session=session)
        df = ticker.history(period=period, interval=interval, prepost=True)
        if df is None or df.empty:
            return pd.DataFrame()
        df = df.rename(columns={
            "Open": "open", "High": "high", "Low": "low", "Close": "close", "Volume": "volume",
        })
        return df[["open", "high", "low", "close", "volume"]].tail(limit)
    except Exception as e:
        log.warning("yfinance bars fail за %s: %s", symbol, e)
        return pd.DataFrame()


def get_sec_dilution_flags(symbol: str) -> dict:
    try:
        r = requests.get(
            "https://sec.gov{}%22&forms=S-1,S-3,424B5".format(symbol),
            timeout=10,
            headers={"User-Agent": "penny-stock-scanner-free contact@example.com"},
        )
        if r.status_code != 200:
            return {"has_recent_dilution_filing": False}
        hits = r.json().get("hits", {}).get("total", {}).get("value", 0)
        return {"has_recent_dilution_filing": hits > 0}
    except Exception as e:
        log.warning(f"SEC EDGAR fail за {symbol}: {e}")
        return {"has_recent_dilution_filing": False}
