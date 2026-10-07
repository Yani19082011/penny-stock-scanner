"""
Дневни сигнали върху OHLCV DataFrame (index = дата, колони: open, high,
low, close, volume).

ПРОМЯНА (07.10, по изрична молба "давай искам това да е главната стратегия
махни старата"): старата версия на този файл смяташе intraday (5-мин)
индикатори (EMA9/EMA20/VWAP/RSI/ORB/bullish свещ) - това беше ОРИГИНАЛНАТА
логика на бота, НИКОГА не беше рядко backtest-вана систематично. След 9
кръга строг backtest (виж strategy_backtest.py и 26-те стратегии в
strategies.py, всяка тествана с random_baseline контрол И out-of-sample
валидация с --offset-days 250) само 2 от 26 дневни стратегии показаха
истинско, повтарящо се предимство в посоката на движението (не само
намаляване на риска): `donchian_breakout` и `fib_retracement_bounce`.
Затова сега ботът използва ДИРЕКТНО тези две (непроменени) функции от
strategies.py, вместо старите intraday индикатори.

ЧЕСТНА бележка за живо приложение: strategies.py функциите са backtest-вани
на ЗАТВОРЕНИ дневни свещи (walk-forward, без lookahead - виж strategy_
backtest.py). На живо, докато пазарът е отворен, "днешният" ред от
yfinance дневни данни е ОЩЕ недовършен (отваря се с днешния open, high/low
се обновяват, close = последна цена, volume = обемът досега за деня) - това
е разумна, но не перфектна апроксимация на "затворена дневна свещ" сигнала
от backtest-а. Сигналът може да се "размисли" (да спре да важи) преди
истинското затваряне на деня. Приемаме този компромис, защото алтернативата
(да чакаме реално затваряне) би означавала алърт чак на следващия ден.
"""
import strategies


def compute_daily_signals(df) -> dict:
    """Смята двата валидирани дневни сигнала за последния (най-пресен) ред
    от df. Изисква достатъчно история и за двете стратегии - виж min_len
    проверките в strategies.py (donchian: channel_period+25=45,
    fib_retracement: swing_lookback+2=42) - тук искаме малко повече буфер,
    за да сме сигурни, че индикаторите имат стабилна база (виж main.py
    ::_MIN_DAILY_BARS_FOR_SIGNALS)."""
    if df is None or df.empty or len(df) < 45:
        return {}

    last_close = df["close"].iloc[-1]
    if last_close is None or last_close != last_close:  # NaN проверка
        return {}

    return {
        "price": float(last_close),
        "donchian_breakout": bool(strategies.signal_donchian_breakout(df)),
        "fib_retracement_bounce": bool(strategies.signal_fib_retracement_bounce(df)),
    }
