"""
Технически индикатори върху OHLCV DataFrame (index = time, колони:
open, high, low, close, volume). Всяка функция е чист pandas/numpy код,
за да може да се вика еднакво и на живо, и в backtest.py.
"""
import numpy as np
import pandas as pd


def ema(series: pd.Series, span: int) -> pd.Series:
    return series.ewm(span=span, adjust=False).mean()


def vwap(df: pd.DataFrame) -> pd.Series:
    typical = (df["high"] + df["low"] + df["close"]) / 3
    cum_vol = df["volume"].cumsum()
    cum_vol_price = (typical * df["volume"]).cumsum()
    return cum_vol_price / cum_vol.replace(0, np.nan)


def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def relative_volume(df: pd.DataFrame, lookback: int = 20) -> float:
    """Текущ обем спрямо средния обем за последните `lookback` свещи (без текущата)."""
    if len(df) < lookback + 1:
        return np.nan
    avg = df["volume"].iloc[-(lookback + 1):-1].mean()
    if not avg:
        return np.nan
    return df["volume"].iloc[-1] / avg


def opening_range_breakout(df: pd.DataFrame, opening_bars: int = 6) -> dict:
    """
    ORB: взима High/Low на първите `opening_bars` свещи от деня (при 5Min бар
    и opening_bars=6 това е първите 30 мин) и проверява дали последната цена
    е пробила над/под този диапазон.
    """
    if df.empty or len(df) <= opening_bars:
        return {"breakout": None, "range_high": None, "range_low": None}
    today = df.index[-1].date()
    day_df = df[df.index.date == today]
    if len(day_df) <= opening_bars:
        return {"breakout": None, "range_high": None, "range_low": None}
    opening = day_df.iloc[:opening_bars]
    range_high, range_low = opening["high"].max(), opening["low"].min()
    last_close = day_df["close"].iloc[-1]
    if last_close > range_high:
        direction = "bullish"
    elif last_close < range_low:
        direction = "bearish"
    else:
        direction = None
    return {"breakout": direction, "range_high": range_high, "range_low": range_low}


def support_resistance(df: pd.DataFrame, window: int = 20) -> dict:
    """Прост S/R: rolling min/max за последните `window` свещи."""
    if len(df) < window:
        return {"support": None, "resistance": None}
    recent = df.iloc[-window:]
    return {"support": recent["low"].min(), "resistance": recent["high"].max()}


def bullish_candle_pattern(df: pd.DataFrame) -> bool:
    """Много опростено: последната свещ е силна bullish (close близо до high, тяло > 60% от range)."""
    if df.empty:
        return False
    last = df.iloc[-1]
    rng = last["high"] - last["low"]
    if rng <= 0:
        return False
    body = abs(last["close"] - last["open"])
    close_near_high = (last["high"] - last["close"]) / rng < 0.25
    return (body / rng) > 0.6 and close_near_high and last["close"] > last["open"]


def compute_all(df: pd.DataFrame) -> dict:
    """Изчислява всички индикатори наведнъж за последната свещ. Ползва се и от
    scoring.py (на живо), и от backtest.py (walk-forward)."""
    if df.empty or len(df) < 25:
        return {}

    df = df.copy()
    df["ema9"] = ema(df["close"], 9)
    df["ema20"] = ema(df["close"], 20)
    df["vwap"] = vwap(df)
    df["rsi14"] = rsi(df["close"], 14)

    last = df.iloc[-1]
    orb = opening_range_breakout(df)
    sr = support_resistance(df)

    return {
        "price": float(last["close"]),
        "ema9": float(last["ema9"]) if pd.notna(last["ema9"]) else None,
        "ema20": float(last["ema20"]) if pd.notna(last["ema20"]) else None,
        "vwap": float(last["vwap"]) if pd.notna(last["vwap"]) else None,
        "rsi14": float(last["rsi14"]) if pd.notna(last["rsi14"]) else None,
        "relative_volume": relative_volume(df),
        "trend_up": bool(pd.notna(last["ema9"]) and pd.notna(last["ema20"]) and last["ema9"] > last["ema20"]),
        "above_vwap": bool(pd.notna(last["vwap"]) and last["close"] > last["vwap"]),
        "orb_breakout": orb["breakout"],
        "support": sr["support"],
        "resistance": sr["resistance"],
        "bullish_candle": bullish_candle_pattern(df),
    }
