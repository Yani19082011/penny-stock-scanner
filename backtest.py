"""
Прост walk-forward backtest върху исторически дневни данни от yfinance
(достатъчно, за да прецениш прага HIGH_POTENTIAL_THRESHOLD и общата логика,
преди да разчиташ на живи алърти). За истински intraday backtest ще трябва
платен исторически feed - вижте README.md, секция "Ограничения на backtest-а".

Употреба:
    python backtest.py SIRI NOK SOFI PLUG --days 180
"""
import argparse
import logging

import pandas as pd
import yfinance as yf

import config
from indicators import compute_all
from scoring import score_symbol

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("backtest")


def load_history(symbol: str, days: int) -> pd.DataFrame:
    df = yf.download(symbol, period=f"{days}d", interval="1d", progress=False)
    if df.empty:
        return df
    df = df.rename(columns={
        "Open": "open", "High": "high", "Low": "low", "Close": "close", "Volume": "volume",
    })
    return df[["open", "high", "low", "close", "volume"]]


def backtest_symbol(symbol: str, days: int, forward_days: int = 5, min_bars: int = 30):
    df = load_history(symbol, days)
    if df.empty or len(df) < min_bars + forward_days:
        log.warning("%s: недостатъчно данни, пропускам.", symbol)
        return []

    trades = []
    for i in range(min_bars, len(df) - forward_days):
        window = df.iloc[: i + 1]
        ind = compute_all(window)
        if not ind:
            continue
        # backtest-ът е "no catalyst / no dilution data" по подразбиране -
        # чисто технически score, защото исторически новини за FMP/Finnhub
        # безплатния tier не покриват назад години. Смятай прага съответно
        # по-консервативно за живата версия.
        result = score_symbol(symbol, ind, has_news_catalyst=False, dilution_flags={})
        if result.score >= config.HIGH_POTENTIAL_THRESHOLD - 15:  # по-нисък праг тук, защото няма catalyst точки
            entry_price = df["close"].iloc[i]
            exit_price = df["close"].iloc[i + forward_days]
            ret_pct = (exit_price - entry_price) / entry_price * 100
            trades.append({
                "symbol": symbol,
                "date": df.index[i].date(),
                "score": result.score,
                "entry": round(entry_price, 2),
                "exit_after_%dd" % forward_days: round(exit_price, 2),
                "return_pct": round(ret_pct, 2),
            })
    return trades


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("symbols", nargs="+")
    parser.add_argument("--days", type=int, default=180)
    parser.add_argument("--forward-days", type=int, default=5)
    args = parser.parse_args()

    all_trades = []
    for symbol in args.symbols:
        all_trades.extend(backtest_symbol(symbol, args.days, args.forward_days))

    if not all_trades:
        log.info("Няма сигнали в тествания период.")
        return

    df = pd.DataFrame(all_trades)
    win_rate = (df["return_pct"] > 0).mean() * 100
    log.info("\n%s", df.to_string(index=False))
    log.info(
        "\n--- Резюме ---\nБрой сигнали: %d | Win rate: %.1f%% | Среден return: %.2f%% | Max loss: %.2f%%",
        len(df), win_rate, df["return_pct"].mean(), df["return_pct"].min(),
    )


if __name__ == "__main__":
    main()
