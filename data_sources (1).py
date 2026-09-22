import time
import logging
from datetime import datetime, timedelta, timezone
import requests
import pandas as pd
import config

log = logging.getLogger("data_sources")

class AlpacaClient:
    def __init__(self):
        self.headers = {"APCA-API-KEY-ID": config.ALPACA_API_KEY, "APCA-API-SECRET-KEY": config.ALPACA_SECRET_KEY}
    def get_bars(self, symbol: str, timeframe: str = "5Min", limit: int = 200) -> pd.DataFrame:
        url = f"{config.ALPACA_DATA_URL}/v2/stocks/{symbol}/bars"
        try:
            r = requests.get(url, headers=self.headers, params={"timeframe": timeframe, "limit": limit, "feed": "iex"}, timeout=10)
            r.raise_for_status()
            bars = r.json().get("bars", [])
        except Exception as e:
            return pd.DataFrame()
        if not bars: return pd.DataFrame()
        df = pd.DataFrame(bars).rename(columns={"t": "time", "o": "open", "h": "high", "l": "low", "c": "close", "v": "volume"})
        df["time"] = pd.to_datetime(df["time"])
        return df.set_index("time")
    def get_news(self, symbol: str, limit: int = 10):
        try:
            r = requests.get("https://data.alpaca.markets/v1beta1/news", headers=self.headers, params={"symbols": symbol, "limit": limit}, timeout=10)
            return r.json().get("news", [])
        except: return []

class FinnhubClient:
    def __init__(self): self.key = config.FINNHUB_API_KEY
    def company_news(self, symbol: str, days_back: int = 3):
        if not self.key: return []
        today = datetime.now(timezone.utc).date()
        try:
            r = requests.get("https://finnhub.io/api/v1/company-news", params={"token": self.key, "symbol": symbol, "from": str(today - timedelta(days=days_back)), "to": str(today)}, timeout=10)
            return r.json() or []
        except: return []

def get_bars_yfinance(symbol: str, interval: str = "5m", period: str = "5d", limit: int = 100) -> pd.DataFrame:
    try:
        import yfinance as yf
        session = requests.Session()
        session.headers.update({"User-Agent": "Mozilla/5.0"})
        ticker = yf.Ticker(symbol, session=session)
        df = ticker.history(period=period, interval=interval, prepost=True)
        if df is None or df.empty: return pd.DataFrame()
        return df.rename(columns={"Open": "open", "High": "high", "Low": "low", "Close": "close", "Volume": "volume"})[["open", "high", "low", "close", "volume"]].tail(limit)
    except: return pd.DataFrame()

def get_sec_dilution_flags(symbol: str) -> dict:
    try:
        r = requests.get("https://efts.sec.gov/LATEST/search-index?q=%22{}%22&forms=S-1,S-3,424B5".format(symbol), timeout=10, headers={"User-Agent": "penny-stock-scanner contact@example.com"})
        return {"has_recent_dilution_filing": r.json().get("hits", {}).get("total", {}).get("value", 0) > 0}
    except: return {"has_recent_dilution_filing": False}
