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

ПРОМЯНА (08.10, по изрична молба "айде да решим за бота оправи кода със
новите стратегии" - след общо 24 кръга допълнителен backtest, виж пълната
история в strategies.py): добавени ОЩЕ 3 сигнала, всеки 3-прозоречно (--
offset-days 250 и 500, независими периоди) валидиран преди да влезе тук:
  - `near_high_volume_build` - "преди пробива" сигнал (цена близо до
    N-дневен връх, НЕ го е пробила, обемът се трупа). 3/3 прозореца:
    max_loss драстично по-нисък от random, win_rate по-добър в 2/3.
  - `volume_climax_reversal_2day` - паник-обем ден, потвърден на СЛЕДВАЩИЯ
    ден без нов минимум. Най-стабилната находка в цялата сесия - caught_
    20pct_spike по-висок от random в 3/3 прозореца без изключение.
  - `momentum_acceleration` - ROC ускорява строго монотонно. Самостоятелно
    слаб сигнал, но в комбинация с fib_retracement_bounce max_loss пада
    значимо и стабилно 3/3 прозореца - затова се смята ТУК само като
    ДОПЪЛНИТЕЛНА информация към fib сигнала (виж scoring.py), не като
    самостоятелен критерий.
Съзнателно НЕ added: `stealth_volume_anomaly` - 3-прозоречният тест излезе
нестабилен (win_rate обърна посока 3 пъти, третият прозорец имаше само
n=19 сигнала) - недостатъчно надеждно за живо приложение (08.10).

ПРОМЯНА (10.10, по молба "има ли такава която да е като donchian но да
изпраща по-често" - кръг 26 в strategies.py, 3 варианта тествани,
3-прозоречно --offset-days 250/500): добавен `donchian_sustained_breakout`
- СЪЩИЯТ 20-дневен канал като donchian_breakout, но БЕЗ изискването "само
първия ден на пробива" (хваща и продължението на силен пробив, не само
първия ден). 3/3 прозореца ЧИСТА победа над самата donchian_breakout: ~32-
39% ПОВЕЧЕ сигнали, win_rate/median_ret/caught_20pct_spike по-добри или
равни на всички хоризонти във всичките 3 прозореца, max_loss практически
ИДЕНТИЧЕН на donchian навсякъде (никъде по-лош) - най-стабилната находка в
цялата сесия. Затова влиза на СЪЩОТО ниво като donchian_breakout в
scoring.py (score=100), не watchlist. Другите 2 варианта от кръг 26
(donchian_breakout_short, donchian_breakout_loose_volume) НЕ се добавят -
по-нестабилен/по-лош риск профил между прозорците (виж strategies.py).

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
    """Смята валидираните дневни сигнали за последния (най-пресен) ред от
    df. Изисква достатъчно история - виж min_len проверките в strategies.py
    (donchian: channel_period+25=45, fib_retracement: swing_lookback+2=42,
    momentum_acceleration: 5+3+20=28, volume_climax_reversal_2day:
    20+25+2=47, near_high_volume_build: 60+65=125 - НАЙ-строгото изискване).
    Външната проверка тук е по-рехава (45) умишлено - near_high_volume_build
    сама се пази вътрешно и просто връща False за тикери с по-къса история
    (виж main.py::_score_symbols за реалния период данни, който се тегли -
    вдигнат на "1y", за да има достатъчно бари за near_high_volume_build,
    когато тикерът реално има толкова дълга история)."""
    if df is None or df.empty or len(df) < 45:
        return {}

    last_close = df["close"].iloc[-1]
    if last_close is None or last_close != last_close:  # NaN проверка
        return {}

    return {
        "price": float(last_close),
        "donchian_breakout": bool(strategies.signal_donchian_breakout(df)),
        "donchian_sustained_breakout": bool(strategies.signal_donchian_sustained_breakout(df)),
        "fib_retracement_bounce": bool(strategies.signal_fib_retracement_bounce(df)),
        "momentum_acceleration": bool(strategies.signal_momentum_acceleration(df)),
        "near_high_volume_build": bool(strategies.signal_near_high_volume_build(df)),
        "volume_climax_reversal_2day": bool(strategies.signal_volume_climax_reversal_2day(df)),
    }
