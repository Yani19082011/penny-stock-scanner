"""
"Преди да избухне" сигнални стратегии (06.10, по изрична молба на
потребителя - "искам да се опитва да намира penny stocks преди да избухнат
... намери различни стратегии дай да ги backtestваме ... да видим коя
работи"). Всяка функция тук е ЧИСТА (без мрежови повиквания) и гледа САМО
данни ДО И ВКЛЮЧИТЕЛНО последния ред на подадения DataFrame (index=time,
колони: open/high/low/close/volume) - никакъв lookahead bias - за да може
да се вика еднакво и в strategy_backtest.py (walk-forward), и по-късно на
живо в main.py, ако някоя стратегия се окаже да работи.

Всички са установени, публично документирани технически концепции (не
изобретени тук) - виж бележката във всяка функция за източника. Общата
идея, за разлика от текущия scoring.py::score_symbol (който гледа
ПОТВЪРЖДЕНИЕ на вече започнало движение - EMA uptrend, ORB пробив, bullish
свещ), е да хванат сигнали, докато цената СЕ ГОТВИ, преди явния пробив:
свиваща се волатилност, обем идващ преди цената, или обем над down-дните
(класическо "тихо натрупване").
"""
import numpy as np
import pandas as pd


def signal_pocket_pivot(df: pd.DataFrame, lookback_down_days: int = 10) -> bool:
    """Pocket Pivot (O'Neil / Gil Morales & Chris Kacher): днес е UP ден
    (close > предходен close) И днешният обем надвишава НАЙ-ВИСОКИЯ обем
    измежду последните `lookback_down_days` DOWN дни. Идеята: купувачи
    идват по-силно от всеки неотдавнашен ден на продажби, докато акцията е
    още вътре в консолидация/база - "pocket" е точно защото сигналът идва
    ПРЕДИ официалния пробив на предходен връх, не след него.
    https://traderlion.com/trading-strategies/pocket-pivot/"""
    if len(df) < lookback_down_days + 2:
        return False
    today = df.iloc[-1]
    is_up_day = today["close"] > df["close"].iloc[-2]
    if not is_up_day:
        return False
    prior = df.iloc[-(lookback_down_days + 1):-1].copy()
    prior_prior_closes = df["close"].iloc[-(lookback_down_days + 2):-2]
    down_mask = prior["close"].values < prior_prior_closes.values
    down_volumes = prior["volume"][down_mask]
    if len(down_volumes) == 0:
        # няма нито един down ден в прозореца - третираме като "няма видима съпротива" - разрешаваме сигнала
        return bool(today["volume"] > prior["volume"].max())
    return bool(today["volume"] > down_volumes.max())


def signal_nr7_volatility_squeeze(df: pd.DataFrame, window: int = 7) -> bool:
    """NR7 (Narrowest Range 7): дневният диапазон (high-low) е НАЙ-ТЕСНИЯТ от
    последните `window` дни - волатилността се свива, класически предвестник
    на рязко разширение (посоката не е гарантирана тук - чисто volatility
    сигнал).
    https://chartschool.stockcharts.com/table-of-contents/trading-strategies-and-models/trading-strategies/narrow-range-day-nr7"""
    if len(df) < window:
        return False
    ranges = (df["high"] - df["low"]).iloc[-window:]
    today_range = ranges.iloc[-1]
    return bool(today_range > 0 and today_range == ranges.min())


def signal_bollinger_squeeze(df: pd.DataFrame, bb_period: int = 20, lookback: int = 60) -> bool:
    """Bollinger Band Squeeze: ширината на лентите (4*std/sma, еквивалентно
    на (upper-lower)/middle при 2-std ленти) е на `lookback`-дневен минимум -
    ниска волатилност, класически предвестник на бъдещо разширение.
    https://chartschool.stockcharts.com/table-of-contents/trading-strategies-and-models/trading-strategies/bollinger-band-squeeze"""
    if len(df) < bb_period + lookback:
        return False
    close = df["close"]
    sma = close.rolling(bb_period).mean()
    std = close.rolling(bb_period).std()
    width = (4 * std) / sma.replace(0, np.nan)
    recent_width = width.iloc[-lookback:]
    today_width = recent_width.iloc[-1]
    if pd.isna(today_width):
        return False
    return bool(today_width == recent_width.min())


def signal_quiet_accumulation(df: pd.DataFrame, window: int = 10, price_flat_pct: float = 5.0) -> bool:
    """"Тихо натрупване": On-Balance Volume (OBV) се покачва последните
    `window` дни, ДОКАТО цената е останала почти плоска (± price_flat_pct%) -
    знак, че обемът идва вътре преди цената реално да тръгне (класическа
    OBV дивергенция/натрупване идея - обемът "знае" преди цената)."""
    if len(df) < window + 1:
        return False
    window_df = df.iloc[-(window + 1):]
    direction = np.sign(window_df["close"].diff()).fillna(0)
    obv = (direction * window_df["volume"]).cumsum()
    obv_rising = obv.iloc[-1] > obv.iloc[0]
    start_price = window_df["close"].iloc[0]
    if not start_price:
        return False
    price_change_pct = (window_df["close"].iloc[-1] - start_price) / start_price * 100
    return bool(obv_rising and abs(price_change_pct) <= price_flat_pct)


def signal_ttm_squeeze(df: pd.DataFrame, bb_period: int = 20, bb_mult: float = 2.0, kc_period: int = 20, kc_mult: float = 1.5) -> bool:
    """TTM Squeeze (John Carter, "Mastering the Trade"): Bollinger Bands
    (bb_period, bb_mult стандартни отклонения) са изцяло ВЪТРЕ в Keltner
    Channel-а (kc_period, kc_mult x ATR) - комбинира две различни мерки на
    волатилност (std + ATR), за разлика от signal_bollinger_squeeze по-долу,
    който гледа само БEB ширина сама по себе си. "Squeeze on" е класическият
    предвестник на предстоящо рязко разширение на диапазона.
    https://www.tradingview.com/support/solutions/43000501971-ttm-squeeze/"""
    if len(df) < max(bb_period, kc_period) + 1:
        return False
    close, high, low = df["close"], df["high"], df["low"]
    sma = close.rolling(bb_period).mean()
    std = close.rolling(bb_period).std()
    bb_upper, bb_lower = sma + bb_mult * std, sma - bb_mult * std
    prev_close = close.shift(1)
    tr = pd.concat([high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1).max(axis=1)
    atr = tr.rolling(kc_period).mean()
    kc_mid = close.rolling(kc_period).mean()
    kc_upper, kc_lower = kc_mid + kc_mult * atr, kc_mid - kc_mult * atr
    bb_u, bb_l, kc_u, kc_l = bb_upper.iloc[-1], bb_lower.iloc[-1], kc_upper.iloc[-1], kc_lower.iloc[-1]
    if pd.isna(bb_u) or pd.isna(kc_u):
        return False
    return bool(bb_u < kc_u and bb_l > kc_l)


def signal_volume_dry_up(df: pd.DataFrame, lookback: int = 50, dryup_ratio: float = 0.5, price_floor_pct: float = 0.85, range_lookback: int = 20) -> bool:
    """Volume Dry-Up / "VDU" (Mark Minervini, "Trade Like a Stock Market
    Wizard"): днешният обем е под `dryup_ratio` x средния обем за последните
    `lookback` дни (ОБРАТНО на signal_volume_before_breakout - тук
    ТИХОТО затишие е сигналът, не повишен обем), ПРИ ЦЕНА все още близо до
    скорошния връх (>= price_floor_pct x последния `range_lookback`-дневен
    max) - показва, че продавачите са изчерпани, докато купувачите не
    бягат, класически предвестник точно преди институционален обем да
    влезе."""
    if len(df) < max(lookback, range_lookback) + 1:
        return False
    avg_vol = df["volume"].iloc[-(lookback + 1):-1].mean()
    if not avg_vol:
        return False
    today_vol = df["volume"].iloc[-1]
    if today_vol >= dryup_ratio * avg_vol:
        return False
    recent_high = df["high"].iloc[-(range_lookback + 1):-1].max()
    if not recent_high:
        return False
    today_close = df["close"].iloc[-1]
    return bool(today_close >= price_floor_pct * recent_high)


def signal_three_bar_tight(df: pd.DataFrame, bars: int = 3, max_range_ratio: float = 1.3, max_close_spread_pct: float = 3.0) -> bool:
    """"Three Bars Tight" (Mark Minervini): последните `bars` дни имат
    почти еднакви дневни диапазони (макс/мин диапазон <= max_range_ratio) И
    close цените им са стиснати в тесен коридор (<= max_close_spread_pct%
    спред) - екстремно свиване на волатилността точно преди експанзия,
    популярна сред swing трейдъри на ниско-ликвидни/penny акции."""
    if len(df) < bars:
        return False
    recent = df.iloc[-bars:]
    ranges = recent["high"] - recent["low"]
    if (ranges <= 0).any():
        return False
    if ranges.max() / ranges.min() > max_range_ratio:
        return False
    closes = recent["close"]
    avg_close = closes.mean()
    if not avg_close:
        return False
    spread_pct = (closes.max() - closes.min()) / avg_close * 100
    return bool(spread_pct <= max_close_spread_pct)


def signal_ma_convergence_coil(df: pd.DataFrame, short: int = 10, long: int = 30, lookback: int = 60) -> bool:
    """Конвергенция на пълзящи средни: спредът между SMA(`short`) и
    SMA(`long`), като % от цената, е на `lookback`-дневен минимум -
    средните "се стягат" една към друга (класически признак на base/
    консолидация, различен тип сигнал от NR7/Bollinger, защото гледа
    формата на тренда, не директно диапазона на свещите)."""
    if len(df) < long + lookback:
        return False
    close = df["close"]
    sma_s, sma_l = close.rolling(short).mean(), close.rolling(long).mean()
    spread_pct = (sma_s - sma_l).abs() / sma_l.replace(0, np.nan) * 100
    recent = spread_pct.iloc[-lookback:]
    today = recent.iloc[-1]
    if pd.isna(today):
        return False
    return bool(today == recent.min())


def signal_vcp_contraction(df: pd.DataFrame, sub_window: int = 10, min_price_ratio: float = 0.9) -> bool:
    """Опростен Volatility Contraction Pattern / "VCP" (Mark Minervini):
    последните 3x`sub_window` дни се делят на три последователни подпериода
    - сигналът гръмва само ако волатилността (std на дневните % промени)
    НАМАЛЯВА строго от първия към третия подпериод (v3 < v2 < v1) - все
    по-плитки, все по-тихи "трусове", класическата форма преди голям
    пробив. Филтър `min_price_ratio`: цената не трябва да е паднала твърде
    много през целия прозорец (изключва "падащ нож", не истинска база)."""
    total = sub_window * 3
    if len(df) < total:
        return False
    seg1 = df["close"].iloc[-total:-(2 * sub_window)]
    seg2 = df["close"].iloc[-(2 * sub_window):-sub_window]
    seg3 = df["close"].iloc[-sub_window:]

    def _vol(seg):
        r = seg.pct_change().dropna()
        return r.std() if len(r) > 1 else np.nan

    v1, v2, v3 = _vol(seg1), _vol(seg2), _vol(seg3)
    if pd.isna(v1) or pd.isna(v2) or pd.isna(v3):
        return False
    if not (v3 < v2 < v1):
        return False
    start_price = seg1.iloc[0] if len(seg1) else None
    if not start_price:
        return False
    today_price = df["close"].iloc[-1]
    return bool(today_price >= min_price_ratio * start_price)


def signal_volume_before_breakout(
    df: pd.DataFrame, lookback: int = 20, min_rel_vol: float = 2.0, max_price_change_pct: float = 5.0,
) -> bool:
    """Обемът днес е >= `min_rel_vol` x средния обем за последните `lookback`
    дни, НО дневната ценова промяна е още под `max_price_change_pct`% -
    обемът идва ПРЕДИ явното ценово движение да се случи, за разлика от
    scoring.py-ския relative_volume сигнал, който е ЧАСТ от потвърждение
    СЛЕД вече видим пробив (ORB bullish + bullish свещ едновременно)."""
    if len(df) < lookback + 1:
        return False
    today = df.iloc[-1]
    avg_vol = df["volume"].iloc[-(lookback + 1):-1].mean()
    if not avg_vol:
        return False
    rel_vol = today["volume"] / avg_vol
    prior_close = df["close"].iloc[-2]
    if not prior_close:
        return False
    price_change_pct = abs((today["close"] - prior_close) / prior_close * 100)
    return bool(rel_vol >= min_rel_vol and price_change_pct <= max_price_change_pct)


def signal_relative_strength_quiet(df: pd.DataFrame, benchmark: pd.DataFrame = None, rs_window: int = 15, rs_recent: int = 5, vol_lookback: int = 20) -> bool:
    """Relative Strength "тиха сила" (Stan Weinstein "Secrets for Profiting
    in Bull and Bear Markets" RS-линия концепция, комбинирана с volatility
    contraction): акцията НАДминава пазарния бенчмарк (SPY) през последните
    `rs_window` дни, И тази относителна сила СЕ Е ПОДОБРИЛА през последните
    `rs_recent` дни (RS линията расте точно сега), ПРИ все още свита
    собствена волатилност (под медианата на последните `vol_lookback` дни)
    - "тих лидер", който расте по-бързо от пазара, без самия той вече да е
    направил експлозивното движение. Единствената от 11-те стратегии, която
    гледа контекста на ПАЗАРА, не само самата акция. Изисква подаден
    `benchmark` DataFrame (индексиран по същите дати, със "close" колона) -
    ако липсва, сигналът просто не гръмва (връща False), никога грешка."""
    if benchmark is None or benchmark.empty:
        return False
    need = max(rs_window, vol_lookback) + 1
    if len(df) < need:
        return False
    close = df["close"]
    bench_close = benchmark["close"] if "close" in benchmark.columns else benchmark.iloc[:, 0]
    ratio = (close / bench_close.reindex(close.index).ffill()).dropna()
    if len(ratio) < max(rs_window, rs_recent) + 1:
        return False
    rs_now = ratio.iloc[-1]
    rs_start = ratio.iloc[-(rs_window + 1)]
    rs_recent_ago = ratio.iloc[-(rs_recent + 1)]
    if not rs_start or not rs_recent_ago:
        return False
    outperforming = rs_now > rs_start
    improving = rs_now > rs_recent_ago
    if not (outperforming and improving):
        return False
    daily_ret = close.pct_change()
    vol = daily_ret.rolling(5).std()
    recent_vol = vol.iloc[-vol_lookback:]
    today_vol = recent_vol.iloc[-1]
    if pd.isna(today_vol) or pd.isna(recent_vol.median()):
        return False
    return bool(today_vol <= recent_vol.median())


def signal_rsi_bullish_divergence(df: pd.DataFrame, rsi_period: int = 14, lookback: int = 20, recency: int = 3) -> bool:
    """RSI "бичи" дивергенция (J. Welles Wilder, "New Concepts in Technical
    Trading Systems" - RSI концепцията; дивергенция анализ е стандартно
    разширение): цената прави ПО-НИСЪК low в скорошната половина на
    `lookback`-дневния прозорец спрямо по-ранната половина, НО RSI прави
    ПО-ВИСОК low на същите точки - класически предвестник на обрат (слабеещ
    низходящ момент, докато цената все още пада) ПРЕДИ ценовия пробив
    нагоре. Механично различно от всички останали 11 стратегии тук - те
    всички гледат ИЛИ волатилност, ИЛИ обем; тази гледа МОМЕНТУМ изоставане
    (momentum divergence), трети независим "сетивен орган"."""
    if len(df) < rsi_period + lookback + 1:
        return False
    close = df["close"]
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(rsi_period).mean()
    avg_loss = loss.rolling(rsi_period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    window_close = close.iloc[-lookback:]
    window_rsi = rsi.iloc[-lookback:]
    if window_rsi.isna().any():
        return False
    half = lookback // 2
    early_close, recent_close = window_close.iloc[:half], window_close.iloc[half:]
    early_rsi, recent_rsi = window_rsi.iloc[:half], window_rsi.iloc[half:]
    early_low_pos = int(early_close.values.argmin())
    recent_low_pos = int(recent_close.values.argmin())
    if recent_low_pos < len(recent_close) - recency:
        return False  # скорошното дъно не е достатъчно близо до "днес"
    price_lower_low = recent_close.iloc[recent_low_pos] < early_close.iloc[early_low_pos]
    rsi_higher_low = recent_rsi.iloc[recent_low_pos] > early_rsi.iloc[early_low_pos]
    return bool(price_lower_low and rsi_higher_low)


def signal_higher_low_base(df: pd.DataFrame, lookback: int = 15, resistance_tolerance_pct: float = 4.0) -> bool:
    """"Възходяща база" (higher-low structure): последните `lookback` дни се
    делят на две половини - дъното на втората половина е ПО-ВИСОКО от
    дъното на първата (купувачите влизат на все по-висока цена), докато
    върховете на двете половини тестват приблизително едно и също ниво
    съпротивление (± resistance_tolerance_pct%) - класическа структура
    преди пробив на съпротивлението (възходящ триъгълник / higher-low
    base), различна от волатилност-базираните сигнали, защото гледа
    ФОРМАТА на дъната/върховете, не самата ширина на диапазона."""
    if len(df) < lookback + 1:
        return False
    window = df.iloc[-lookback:]
    half = lookback // 2
    first_half, second_half = window.iloc[:half], window.iloc[half:]
    low1, low2 = first_half["low"].min(), second_half["low"].min()
    if not (low2 > low1):
        return False
    high1, high2 = first_half["high"].max(), second_half["high"].max()
    if not high1 or not high2:
        return False
    resistance_spread_pct = abs(high2 - high1) / ((high1 + high2) / 2) * 100
    if resistance_spread_pct > resistance_tolerance_pct:
        return False
    today_close = df["close"].iloc[-1]
    return bool(today_close <= max(high1, high2) * 1.01)  # все още ПРЕДИ ясен пробив над съпротивлението

def signal_capitulation_reversal(df: pd.DataFrame, decline_lookback: int = 10, decline_threshold_pct: float = 25.0, vol_mult: float = 3.0, close_position_min: float = 0.6) -> bool:
    """Capitulation / Climax Bottom (класическа "паническа продажба"
    концепция): цената е паднала поне `decline_threshold_pct`% през
    последните `decline_lookback` дни, днешният обем е >= `vol_mult` x
    средния за същия период (паническа вълна от продажби), НО днес
    затваря в горната `close_position_min` част на дневния си диапазон
    (знак, че купувачите поемат контрол точно в кулминацията на паниката).
    ОБРАТНО на всички останали 14 стратегии тук, които гледат ЗАТИШИЕ преди
    пробив - тази гледа ПАНИКА преди обрат. Capitulation отскоците са сред
    най-експлозивните движения при penny/micro-cap акции (07.10, добавена
    по молба "още стратегии" след наблюдение, че pocket_pivot/
    volume_before_breakout - и двете обемно-базирани - улавят 20%+ скокове
    забележимо по-често от случаен вход, виж caught_20pct_spike_% в
    strategy_backtest.py)."""
    if len(df) < decline_lookback + 1:
        return False
    window = df.iloc[-(decline_lookback + 1):]
    start_price = window["close"].iloc[0]
    today_close = window["close"].iloc[-1]
    if not start_price:
        return False
    decline_pct = (today_close - start_price) / start_price * 100
    if decline_pct > -decline_threshold_pct:
        return False
    avg_vol = window["volume"].iloc[:-1].mean()
    today_vol = window["volume"].iloc[-1]
    if not avg_vol or today_vol < vol_mult * avg_vol:
        return False
    today_high, today_low = df["high"].iloc[-1], df["low"].iloc[-1]
    day_range = today_high - today_low
    if day_range <= 0:
        return False
    close_position = (today_close - today_low) / day_range
    return bool(close_position >= close_position_min)


def signal_gap_up_hold(df: pd.DataFrame, min_gap_pct: float = 5.0, close_position_min: float = 0.5) -> bool:
    """Gap-and-Hold: отварянето ДНЕС е с >= `min_gap_pct`% над предходния
    close (истинско gap, не просто up-ден), затварянето ДНЕС е ВСЕ ОЩЕ над
    предходния close (gap-ът не е "запълнен" до края на деня) И затварянето
    е в горната `close_position_min` част от дневния диапазон. За разлика
    от всички досегашни 14 стратегии (които гледат ЗАТИШИЕ/обем/дивергенция
    ПРЕДИ движението), тази използва съвсем ново измерение данни - OPEN
    цената спрямо предходния CLOSE - и гледа ДЕНЯ, в който движението вече
    се случва, но все още не е ясно дали ще продължи (gap holds) или ще се
    "удави" (gap fill same day). Класическа идея от gap-trading литературата
    (напр. gap-and-go setups): gap, който не се запълва, статистически по-
    склонен да продължи в посоката на gap-а.
    https://www.investopedia.com/terms/g/gap.asp (07.10, по молба "давай
    други да пробваме" - ново семейство: gap/open анализ, не coiling)."""
    if len(df) < 2:
        return False
    prior_close = df["close"].iloc[-2]
    today_open = df["open"].iloc[-1]
    if not prior_close or prior_close <= 0:
        return False
    gap_pct = (today_open - prior_close) / prior_close * 100
    if gap_pct < min_gap_pct:
        return False
    today_close = df["close"].iloc[-1]
    if today_close <= prior_close:
        return False  # gap-ът е бил запълнен (или повече) до затварянето
    today_high, today_low = df["high"].iloc[-1], df["low"].iloc[-1]
    day_range = today_high - today_low
    if day_range <= 0:
        return False
    close_position = (today_close - today_low) / day_range
    return bool(close_position >= close_position_min)


def signal_adx_trend_strength(df: pd.DataFrame, period: int = 14, adx_extreme_cap: float = 55.0, lookback_rising: int = 5, min_rise: float = 4.0) -> bool:
    """ADX/DMI (J. Welles Wilder, "New Concepts in Technical Trading
    Systems", 1978): +DI > -DI (купувачите контролират посоката), ADX
    (сила на тренда, НЕ посока) се е покачил с >= `min_rise` точки през
    последните `lookback_rising` дни (трендът НАБИРА сила точно сега) И
    ADX все още не е над `adx_extreme_cap` (не е вече "презрял"/изчерпан
    силен тренд - искаме РАННА фаза на набиране на сила, не края й). Съвсем
    различно семейство от всичко досегашно - ADX гледа СИЛАТА на
    съществуващ тренд (trend-following momentum), не свиваща се
    волатилност, не обем, не дивергенция на осцилатор. (Забележка: първата
    версия изискваше точно "прекосяване" на фиксиран праг от 25, но
    синтетичните тестове показаха, че ADX може да скочи над 25 само за
    няколко дни при чист тренд - "прекосяването" почти винаги се случва
    ПРЕДИ да имаме достатъчно данни да го хванем. "Покачва се и все още не
    е презряло" е по-устойчив критерий за целта "преди да избухне".)
    https://www.investopedia.com/terms/a/adx.asp (07.10, по молба "давай
    други да пробваме")."""
    min_len = period * 3 + lookback_rising
    if len(df) < min_len:
        return False
    high, low, close = df["high"], df["low"], df["close"]
    up_move = high.diff()
    down_move = -low.diff()
    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)
    tr1 = high - low
    tr2 = (high - close.shift()).abs()
    tr3 = (low - close.shift()).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(period).mean()
    atr_safe = atr.replace(0, np.nan)
    plus_di = 100 * pd.Series(plus_dm, index=df.index).rolling(period).mean() / atr_safe
    minus_di = 100 * pd.Series(minus_dm, index=df.index).rolling(period).mean() / atr_safe
    di_sum = (plus_di + minus_di).replace(0, np.nan)
    dx = (plus_di - minus_di).abs() / di_sum * 100
    adx = dx.rolling(period).mean()
    today_adx = adx.iloc[-1]
    adx_lookback_ago = adx.iloc[-(lookback_rising + 1)]
    if pd.isna(today_adx) or pd.isna(adx_lookback_ago):
        return False
    rising_enough = (today_adx - adx_lookback_ago) >= min_rise
    not_yet_extreme = today_adx < adx_extreme_cap
    bulls_in_control = plus_di.iloc[-1] > minus_di.iloc[-1]
    return bool(rising_enough and not_yet_extreme and bulls_in_control)


def signal_macd_bullish_cross(df: pd.DataFrame, fast: int = 12, slow: int = 26, signal_span: int = 9, near_zero_pct: float = 5.0) -> bool:
    """MACD bullish crossover (Gerald Appel): MACD линията (EMA12-EMA26)
    пресича НАГОРЕ сигналната си линия (EMA9 на MACD) ТОЧНО днес, докато
    MACD е все още близо до нулевата линия (в рамките на `near_zero_pct`%
    от цената) - т.е. РАННА фаза на промяна в моментума, не акция, която
    вече е дълбоко в zрял uptrend. Моментум-кросоувър семейство - механично
    различно от волатилност (NR7/Bollinger/VCP), обем (pocket pivot/OBV),
    дивергенция (RSI) и trend-strength (ADX) по-горе.
    https://www.investopedia.com/terms/m/macd.asp (07.10, по молба "давай
    други да пробваме")."""
    min_len = slow + signal_span + 5
    if len(df) < min_len:
        return False
    close = df["close"]
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    macd = ema_fast - ema_slow
    signal_line = macd.ewm(span=signal_span, adjust=False).mean()
    today_macd, today_sig = macd.iloc[-1], signal_line.iloc[-1]
    yest_macd, yest_sig = macd.iloc[-2], signal_line.iloc[-2]
    crossed_up = (yest_macd <= yest_sig) and (today_macd > today_sig)
    if not crossed_up:
        return False
    today_close = close.iloc[-1]
    if not today_close or today_close <= 0:
        return False
    near_zero = abs(today_macd) < (today_close * near_zero_pct / 100)
    return bool(near_zero)


def signal_stochastic_oversold_turn(df: pd.DataFrame, k_period: int = 14, d_period: int = 3, oversold_level: float = 20.0) -> bool:
    """Stochastic Oscillator (George Lane): %K = позицията на днешния close
    В РАМКИТЕ на целия high-low диапазон на последните `k_period` дни (0-100),
    %D = негова 3-дневна пл. средна. Сигнал: %K е бил <= `oversold_level`
    (свръхпродаден) някъде в последните 5 дни И ДНЕС %K пресича НАГОРЕ %D,
    докато все още е под 50 (ранен обрат, не вече "презряло" рали). За
    разлика от RSI (гледа само close-to-close ПРОМЯНАТА), Stochastic гледа
    позицията на close СПРЯМО целия диапазон - различен "сетивен орган".
    https://www.investopedia.com/terms/s/stochasticoscillator.asp (07.10,
    по молба "давай още")."""
    min_len = k_period + d_period + 6
    if len(df) < min_len:
        return False
    low_k = df["low"].rolling(k_period).min()
    high_k = df["high"].rolling(k_period).max()
    denom = (high_k - low_k).replace(0, np.nan)
    pct_k = (df["close"] - low_k) / denom * 100
    pct_d = pct_k.rolling(d_period).mean()
    today_k, today_d = pct_k.iloc[-1], pct_d.iloc[-1]
    yest_k, yest_d = pct_k.iloc[-2], pct_d.iloc[-2]
    if pd.isna(today_k) or pd.isna(today_d) or pd.isna(yest_k) or pd.isna(yest_d):
        return False
    crossed_up = (yest_k <= yest_d) and (today_k > today_d)
    if not crossed_up:
        return False
    recent_k = pct_k.iloc[-6:-1]
    was_oversold_recently = bool((recent_k <= oversold_level).any())
    still_low = today_k < 50
    return bool(was_oversold_recently and still_low)


def signal_ad_line_divergence(df: pd.DataFrame, lookback: int = 20, recency: int = 3) -> bool:
    """Accumulation/Distribution Line (Marc Chaikin): CLV = ((close-low) -
    (high-close)) / (high-low) - показва КЪДЕ в дневния диапазон е
    затворила цената (+1 = на върха, -1 = на дъното); A/D = кумулативна
    сума на CLV*volume. За разлика от OBV (гледа само ЗНАКА на дневната
    промяна цяло-или-нищо), A/D тежи с ТОЧНОТО място на затварянето в
    диапазона - може да регистрира "тихо" натрупване дори в номинално
    down ден, ако затварянето е близо до дневния връх. Сигнал: бичи
    дивергенция - цената прави ПО-НИСЪК low в скорошната половина на
    прозореца спрямо по-ранната, НО A/D линията прави ПО-ВИСОК low на
    същите точки (същата "дивергенция" идея като RSI по-горе, но върху
    съвсем различен, обемно-претеглен индикатор).
    https://www.investopedia.com/terms/a/accumulationdistribution.asp
    (07.10, по молба "давай още")."""
    if len(df) < lookback + 2:
        return False
    high, low, close, volume = df["high"], df["low"], df["close"], df["volume"]
    day_range = (high - low).replace(0, np.nan)
    clv = ((close - low) - (high - close)) / day_range
    clv = clv.fillna(0.0)
    ad_line = (clv * volume).cumsum()
    window_close = close.iloc[-lookback:]
    window_ad = ad_line.iloc[-lookback:]
    half = lookback // 2
    early_close, recent_close = window_close.iloc[:half], window_close.iloc[half:]
    early_ad, recent_ad = window_ad.iloc[:half], window_ad.iloc[half:]
    early_low_pos = int(early_close.values.argmin())
    recent_low_pos = int(recent_close.values.argmin())
    if recent_low_pos < len(recent_close) - recency:
        return False  # скорошното дъно не е достатъчно близо до "днес"
    price_lower_low = recent_close.iloc[recent_low_pos] < early_close.iloc[early_low_pos]
    ad_higher_low = recent_ad.iloc[recent_low_pos] > early_ad.iloc[early_low_pos]
    return bool(price_lower_low and ad_higher_low)


def signal_pullback_to_rising_ma(df: pd.DataFrame, trend_ma: int = 50, pullback_ma: int = 20, vol_lookback: int = 20, vol_mult: float = 0.8) -> bool:
    """"Низковолумен pullback в тренд" (Minervini/O'Neil "buy the base/
    pullback in an uptrend" - МЕХАНИЧНО различно от всички 17 досегашни,
    защото изисква АКЦИЯТА ВЕЧЕ ДА Е В УСТАНОВЕН ВЪЗХОДЯЩ ТРЕНД - всички
    останали стратегии гледат акции, които още СА в основа/консолидация
    ПРЕДИ тренда): close > растящата `trend_ma`-дневна MA (установен
    тренд) И цената се е "дръпнала" близо до по-кратката `pullback_ma`
    MA (в рамките на 3%) НА ПО-НИСЪК от средния обем (<= `vol_mult` x
    `vol_lookback`-дневния среден обем - продавачите не бързат) И днес е
    първият знак на стабилизация (close >= предходен close). Класическа
    "купи дръпването, не пробива" идея - различна посока от всичко
    останало тук.
    https://www.investopedia.com/articles/trading/08/trend-trade.asp
    (07.10, по молба "давай още")."""
    min_len = max(trend_ma, vol_lookback) + 5
    if len(df) < min_len:
        return False
    close = df["close"]
    trend_sma = close.rolling(trend_ma).mean()
    pullback_sma = close.rolling(pullback_ma).mean()
    today_close = close.iloc[-1]
    today_trend_sma, prior_trend_sma = trend_sma.iloc[-1], trend_sma.iloc[-6]
    if pd.isna(today_trend_sma) or pd.isna(prior_trend_sma):
        return False
    uptrend = (today_close > today_trend_sma) and (today_trend_sma > prior_trend_sma)
    if not uptrend:
        return False
    today_pullback_sma = pullback_sma.iloc[-1]
    if pd.isna(today_pullback_sma) or today_pullback_sma <= 0:
        return False
    near_pullback_ma = abs(today_close - today_pullback_sma) / today_pullback_sma * 100 <= 3.0
    if not near_pullback_ma:
        return False
    avg_vol = df["volume"].iloc[-vol_lookback:].mean()
    today_vol = df["volume"].iloc[-1]
    if not avg_vol or today_vol > vol_mult * avg_vol:
        return False
    stabilizing = today_close >= close.iloc[-2]
    return bool(stabilizing)


def signal_ichimoku_kijun_cross(df: pd.DataFrame, tenkan_period: int = 9, kijun_period: int = 26, cloud_lookback: int = 52) -> bool:
    """Ichimoku Kinko Hyo (Goichi Hosoda): Tenkan-sen = (9-дн. max+min)/2
    (бърза линия), Kijun-sen = (26-дн. max+min)/2 (бавна линия). Сигнал:
    Tenkan-sen пресича НАГОРЕ Kijun-sen ДНЕС (класически "TK cross"),
    докато цената е ВСЕ ОЩЕ под/на нивото на "облака" (приближение на
    Senkou Span A/B тук - виж бележка), т.е. обрат, който се случва ПРЕДИ
    цената да е пробила реалната съпротива на облака. (Честна бележка:
    класическият Ichimoku "облак" се чертае 26 дни НАПРЕД (Senkou Span
    shifted forward) - тук за опростяване сравняваме с НЕИЗМЕСТЕНИ Senkou
    A/B стойности (текущо ниво на подкрепа/съпротива от средните цени), не
    с бъдещо прожектирания облак - леко опростяване на пълната система, но
    запазва основната идея: ранен TK кросоувър под ключова съпротива.)
    Напълно различна многолинейна японска чартинг система - нищо общо
    механично с нито една от предишните 20 стратегии.
    https://www.investopedia.com/terms/i/ichimoku-cloud.asp (07.10, по
    молба "давай още стратегии")."""
    min_len = cloud_lookback + 5
    if len(df) < min_len:
        return False
    high, low, close = df["high"], df["low"], df["close"]
    tenkan = (high.rolling(tenkan_period).max() + low.rolling(tenkan_period).min()) / 2
    kijun = (high.rolling(kijun_period).max() + low.rolling(kijun_period).min()) / 2
    senkou_a = (tenkan + kijun) / 2
    senkou_b = (high.rolling(cloud_lookback).max() + low.rolling(cloud_lookback).min()) / 2
    today_tenkan, today_kijun = tenkan.iloc[-1], kijun.iloc[-1]
    yest_tenkan, yest_kijun = tenkan.iloc[-2], kijun.iloc[-2]
    if pd.isna(today_tenkan) or pd.isna(today_kijun) or pd.isna(yest_tenkan) or pd.isna(yest_kijun):
        return False
    crossed_up = (yest_tenkan <= yest_kijun) and (today_tenkan > today_kijun)
    if not crossed_up:
        return False
    cloud_top = max(senkou_a.iloc[-1], senkou_b.iloc[-1])
    if pd.isna(cloud_top):
        return False
    return bool(close.iloc[-1] <= cloud_top * 1.02)  # все още под/близо облака, не вече ясно пробил


def signal_force_index_reclaim(df: pd.DataFrame, period: int = 13, decline_days: int = 10) -> bool:
    """Elder's Force Index (Alexander Elder, "Trading for a Living"): FI =
    (close - предх. close) * volume, изгладен с `period`-дневна EMA -
    претегля ПРОМЯНАТА в цената (не нивото й) с обема - различно тегло от
    OBV (само знак) и A/D линията (позиция в диапазона). Сигнал: EMA на
    Force Index е била ОТРИЦАТЕЛНА някъде през последните `decline_days`
    дни (продавашки натиск доминира) И ДНЕС пресича обратно НАД нулата
    (купувашкият натиск*обем вече надделява).
    https://www.investopedia.com/terms/f/force-index.asp (07.10, по молба
    "давай още стратегии")."""
    min_len = period * 2 + decline_days
    if len(df) < min_len:
        return False
    close, volume = df["close"], df["volume"]
    raw_fi = close.diff() * volume
    fi_ema = raw_fi.ewm(span=period, adjust=False).mean()
    today_fi, yest_fi = fi_ema.iloc[-1], fi_ema.iloc[-2]
    if pd.isna(today_fi) or pd.isna(yest_fi):
        return False
    crossed_up = (yest_fi <= 0) and (today_fi > 0)
    if not crossed_up:
        return False
    recent_fi = fi_ema.iloc[-(decline_days + 1):-1]
    was_negative_recently = bool((recent_fi < 0).any())
    return bool(was_negative_recently)


def signal_bullish_engulfing_reversal(df: pd.DataFrame, decline_lookback: int = 5, decline_threshold_pct: float = 8.0) -> bool:
    """Bullish Engulfing (класическа японска свещна формация - Steve
    Nison, "Japanese Candlestick Charting Techniques"): вчера е бил
    "мечи" ден (close < open), ДНЕС е "бичи" (close > open) И тялото на
    днешната свещ ИЗЦЯЛО ПОГЛЪЩА тялото на вчерашната (today_open <=
    yest_close И today_close >= yest_open), след кратък спад от поне
    `decline_threshold_pct`% през предходните `decline_lookback` дни
    (контекст - не е случаен обрат насред плосък пазар). За разлика от
    ВСИЧКИ 22 досегашни стратегии (които смятат rolling индикатори -
    средни, std, обеми, осцилатори), тази е ЧИСТО разпознаване на ФОРМА
    на 2 последователни свещи - съвсем различен "сетивен орган": визуална
    ценова структура, не изчислен индикатор.
    https://www.investopedia.com/terms/b/bullishengulfingpattern.asp
    (07.10, по молба "давай още стратегии")."""
    if len(df) < decline_lookback + 2:
        return False
    today_open, today_close = df["open"].iloc[-1], df["close"].iloc[-1]
    yest_open, yest_close = df["open"].iloc[-2], df["close"].iloc[-2]
    bullish_today = today_close > today_open
    bearish_yest = yest_close < yest_open
    if not (bullish_today and bearish_yest):
        return False
    engulfs = (today_open <= yest_close) and (today_close >= yest_open)
    if not engulfs:
        return False
    prior_window = df["close"].iloc[-(decline_lookback + 2):-2]
    if len(prior_window) < decline_lookback:
        return False
    start_price = prior_window.iloc[0]
    end_price = yest_close
    if not start_price:
        return False
    decline_pct = (end_price - start_price) / start_price * 100
    return bool(decline_pct <= -decline_threshold_pct)


def signal_donchian_breakout(df: pd.DataFrame, channel_period: int = 20, confirm_vol_mult: float = 1.5) -> bool:
    """Donchian Channel Breakout (Richard Donchian - в основата на
    системата на "Turtle Traders"): днешният close пробива НАД
    най-високия high на предходните `channel_period` дни (без днес) ЗА
    ПЪРВИ път (вчера все още е бил под съответното ниво към вчера) И
    днешният обем е >= `confirm_vol_mult` x средния обем (потвърждение, не
    фалшив пробив на нисък обем). ЧЕСТНА бележка: за разлика от повечето
    други стратегии тук (които гледат сигнал ПРЕДИ явния пробив), тази
    хваща самия ДЕН НА ПРОБИВА - тества дали "пробивът на N-дневен връх"
    сам по себе си има предимство, не дали може да се хване по-рано.
    Механично е чист price-channel пробив - без MA, осцилатор или
    волатилност мярка, каквито са всички останали 23.
    https://www.investopedia.com/terms/d/donchianchannels.asp (07.10, по
    молба "давай пак продължаваме")."""
    min_len = channel_period + 25
    if len(df) < min_len:
        return False
    high, low, close, volume = df["high"], df["low"], df["close"], df["volume"]
    prior_highest_today = high.iloc[-(channel_period + 1):-1].max()
    prior_highest_yest = high.iloc[-(channel_period + 2):-2].max()
    today_close, yest_close = close.iloc[-1], close.iloc[-2]
    broke_out_today = (today_close > prior_highest_today) and (yest_close <= prior_highest_yest)
    if not broke_out_today:
        return False
    avg_vol = volume.iloc[-21:-1].mean()
    today_vol = volume.iloc[-1]
    if not avg_vol:
        return False
    return bool(today_vol >= confirm_vol_mult * avg_vol)


def signal_parabolic_sar_flip(df: pd.DataFrame, af_start: float = 0.02, af_step: float = 0.02, af_max: float = 0.2, min_bars: int = 30) -> bool:
    """Parabolic SAR (J. Welles Wilder, "New Concepts in Technical Trading
    Systems"): итеративна "стоп-и-обрат" точка, която следва тренда ден по
    ден (ускорява се с acceleration factor, докато трендът продължава).
    Сигнал: SAR пресича от НАД цената (downtrend) към ПОД цената
    (uptrend) ТОЧНО днес - системата официално обявява обрат към
    възходящ тренд. Фундаментално различен механизъм от всичко друго тук
    - не rolling статистика върху прозорец, а последователен, state-ful
    алгоритъм, който носи "памет" за целия предходен път на цената.
    https://www.investopedia.com/trading/introduction-to-parabolic-sar/
    (07.10, по молба "давай пак продължаваме")."""
    if len(df) < min_bars:
        return False
    high = df["high"].values
    low = df["low"].values
    close = df["close"].values
    n = len(df)
    uptrend = close[1] >= close[0]
    sar = low[0] if uptrend else high[0]
    ep = high[0] if uptrend else low[0]
    af = af_start
    flipped_to_up_today = False
    for i in range(1, n):
        flipped_to_up_today = False
        prior_sar = sar
        sar = prior_sar + af * (ep - prior_sar)
        if uptrend:
            lookback_low = min(low[i - 1], low[i - 2]) if i >= 2 else low[i - 1]
            sar = min(sar, lookback_low)
            if low[i] < sar:
                uptrend = False
                sar = ep
                ep = low[i]
                af = af_start
            else:
                if high[i] > ep:
                    ep = high[i]
                    af = min(af + af_step, af_max)
        else:
            lookback_high = max(high[i - 1], high[i - 2]) if i >= 2 else high[i - 1]
            sar = max(sar, lookback_high)
            if high[i] > sar:
                uptrend = True
                sar = ep
                ep = high[i]
                af = af_start
                flipped_to_up_today = True
            else:
                if low[i] < ep:
                    ep = low[i]
                    af = min(af + af_step, af_max)
    return bool(flipped_to_up_today)


def signal_fib_retracement_bounce(df: pd.DataFrame, swing_lookback: int = 40, fib_deep: float = 0.618, fib_shallow: float = 0.5, tolerance_pct: float = 3.0) -> bool:
    """Fibonacci retracement bounce (класическа "swing trading" концепция
    - коефициентите 50%/61.8% от редицата на Фибоначи): намира най-ниската
    точка (swing low) и СЛЕДВАЩАТА най-висока точка (swing high) в
    последните `swing_lookback` дни (т.е. скорошно възходящо движение),
    после проверява дали ДНЕШНИЯТ low е навлязъл в зоната 50%-61.8%
    ретрейсмънт на това движение И затварянето е ОТСКОЧИЛО обратно над
    по-дълбокото ниво (61.8%) - класическо "купи отката" на геометрично
    ниво на подкрепа. Напълно различен "сетивен орган" от всичко друго
    тук - нито индикатор, нито обем, нито свещна форма - чисто измерване
    на swing-колебание и съотношение.
    https://www.investopedia.com/terms/f/fibonacciretracement.asp (07.10,
    по молба "давай пак продължаваме")."""
    if len(df) < swing_lookback + 2:
        return False
    window = df.iloc[-swing_lookback:]
    lows, highs = window["low"].values, window["high"].values
    low_pos = int(lows.argmin())
    if low_pos >= len(window) - 3:
        return False  # дъното е твърде близо до "днес" - няма движение+откат след него
    high_pos_rel = int(highs[low_pos:].argmax())
    high_pos = low_pos + high_pos_rel
    if high_pos <= low_pos or high_pos > len(window) - 3:
        return False  # върхът трябва да е ПРЕДИ дъното по време и да остава място за откат след него
    swing_low = lows[low_pos]
    swing_high = highs[high_pos]
    if swing_high <= swing_low or not swing_low:
        return False
    move = swing_high - swing_low
    fib_deep_level = swing_high - move * fib_deep
    fib_shallow_level = swing_high - move * fib_shallow
    today_low = df["low"].iloc[-1]
    today_close = df["close"].iloc[-1]
    tol = tolerance_pct / 100
    in_zone = (today_low <= fib_shallow_level * (1 + tol)) and (today_low >= fib_deep_level * (1 - tol))
    if not in_zone:
        return False
    bounce_confirmed = today_close >= fib_deep_level
    return bool(bounce_confirmed)


def signal_supertrend_flip(df: pd.DataFrame, atr_period: int = 10, multiplier: float = 3.0, min_bars: int = 30) -> bool:
    """Supertrend (ATR-базирана следваща тренда линия, широко използвана в
    algo trading платформи): МЕХАНИЧНО различна математика от Parabolic
    SAR (който ускорява по парабола) - тук лентата е с ФИКСИРАНА ширина
    (`multiplier` x ATR) около средата на деня (high+low)/2 и "прилепва"
    се към цената, обръщайки посока само когато цената ясно я пробие.
    Сигналът е денят, в който линията премине ОТ над цената (съпротива,
    downtrend) ПОД цената (подкрепа, uptrend) - "Supertrend flip".
    https://www.investopedia.com/supertrend-indicator-7976167 (07.10, по
    молба "искам да тестваме още стратегии")."""
    min_len = atr_period + min_bars
    if len(df) < min_len:
        return False
    high, low, close = df["high"].values, df["low"].values, df["close"].values
    n = len(close)
    tr = np.zeros(n)
    tr[0] = high[0] - low[0]
    for i in range(1, n):
        tr[i] = max(high[i] - low[i], abs(high[i] - close[i - 1]), abs(low[i] - close[i - 1]))
    atr = pd.Series(tr).rolling(atr_period).mean().values

    hl2 = (high + low) / 2.0
    final_upper = np.full(n, np.nan)
    final_lower = np.full(n, np.nan)
    trend = np.zeros(n, dtype=int)  # 1 = uptrend (линията е подкрепа под цената), -1 = downtrend

    start = atr_period
    if np.isnan(atr[start]):
        return False
    final_upper[start] = hl2[start] + multiplier * atr[start]
    final_lower[start] = hl2[start] - multiplier * atr[start]
    trend[start] = 1 if close[start] > final_upper[start] else -1

    for i in range(start + 1, n):
        basic_upper = hl2[i] + multiplier * atr[i]
        basic_lower = hl2[i] - multiplier * atr[i]

        final_upper[i] = basic_upper if (basic_upper < final_upper[i - 1] or close[i - 1] > final_upper[i - 1]) else final_upper[i - 1]
        final_lower[i] = basic_lower if (basic_lower > final_lower[i - 1] or close[i - 1] < final_lower[i - 1]) else final_lower[i - 1]

        if trend[i - 1] == 1:
            trend[i] = 1 if close[i] >= final_lower[i] else -1
        else:
            trend[i] = -1 if close[i] <= final_upper[i] else 1

    return bool(trend[-1] == 1 and trend[-2] == -1)


def signal_aroon_up_cross(df: pd.DataFrame, period: int = 25) -> bool:
    """Aroon (Tushar Chande): МЕХАНИЧНО различен "сетивен орган" от всичко
    друго тук - не гледа магнитуда на движение, нито обем, а ВРЕМЕТО,
    изминало от последния връх/дъно в прозорец от `period` дни. Сигналът е
    "прясно" пресичане на Aroon Up НАД Aroon Down (най-скорошният връх
    изпреварва най-скорошното дъно за първи път) - ранен знак, че инерцията
    се обръща нагоре, преди явен ценови пробив.
    https://www.investopedia.com/terms/a/aroon.asp (07.10, по молба "искам
    да тестваме още стратегии")."""
    min_len = period + 3
    if len(df) < min_len:
        return False
    high, low = df["high"], df["low"]

    def aroon_up_down(end_idx: int):
        window_high = high.iloc[end_idx - period:end_idx + 1]
        window_low = low.iloc[end_idx - period:end_idx + 1]
        days_since_high = period - int(np.argmax(window_high.values))
        days_since_low = period - int(np.argmin(window_low.values))
        up = (period - days_since_high) / period * 100
        down = (period - days_since_low) / period * 100
        return up, down

    n = len(df)
    today_up, today_down = aroon_up_down(n - 1)
    yest_up, yest_down = aroon_up_down(n - 2)
    fresh_cross = yest_up <= yest_down and today_up > today_down
    return bool(fresh_cross)


def signal_pivot_point_breakout(df: pd.DataFrame, min_bars: int = 30) -> bool:
    """Класически "floor trader" pivot points (десетилетия стандартна
    intraday/swing техника): R1 съпротивата се смята САМО от ЕДИН предходен
    ден (High/Low/Close), не от rolling прозорец от много дни като Donchian -
    много по-реактивен, краткосрочен ориентир. Сигналът е днешното close да
    пробие НАД R1 (смятан от вчерашния ден) ЗА ПЪРВИ път - вчера close е бил
    още под собствения си R1 (смятан от деня преди вчера).
    https://www.investopedia.com/terms/p/pivotpoint.asp (07.10, по молба
    "искам да тестваме още стратегии")."""
    if len(df) < min_bars + 2:
        return False
    high, low, close = df["high"], df["low"], df["close"]

    def r1_for(idx: int) -> float:
        pivot = (high.iloc[idx] + low.iloc[idx] + close.iloc[idx]) / 3.0
        return 2 * pivot - low.iloc[idx]

    n = len(df)
    today_r1 = r1_for(n - 2)   # вчерашният ден определя днешния R1
    yest_r1 = r1_for(n - 3)    # по-предишният ден определя вчерашния R1
    today_close, yest_close = close.iloc[-1], close.iloc[-2]
    return bool(today_close > today_r1 and yest_close <= yest_r1)


def signal_keltner_breakout(df: pd.DataFrame, ema_period: int = 20, atr_period: int = 10, multiplier: float = 2.0, min_bars: int = 30) -> bool:
    """Keltner Channel breakout: лентите са EMA ± `multiplier` x ATR - ATR-
    базирани (МЕХАНИЧНО различни от Bollinger, който ползва стандартно
    отклонение, и от Donchian, който ползва сурови ценови екстремуми без
    никакво изглаждане). Сигналът е днешното close да пробие НАД горната
    лента ЗА ПЪРВИ път (вчера е бил вътре/под нея).
    https://www.investopedia.com/terms/k/keltnerchannel.asp (07.10, по
    молба "давай още стратегии")."""
    min_len = max(ema_period, atr_period) + min_bars
    if len(df) < min_len:
        return False
    close, high, low = df["close"], df["high"], df["low"]
    ema = close.ewm(span=ema_period, adjust=False).mean()
    prev_close = close.shift(1)
    tr = pd.concat([high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1).max(axis=1)
    atr = tr.rolling(atr_period).mean()
    upper = ema + multiplier * atr
    today_close, yest_close = close.iloc[-1], close.iloc[-2]
    today_upper, yest_upper = upper.iloc[-1], upper.iloc[-2]
    if pd.isna(today_upper) or pd.isna(yest_upper):
        return False
    return bool(today_close > today_upper and yest_close <= yest_upper)


def signal_cci_extreme_reversal(df: pd.DataFrame, period: int = 20, oversold: float = -100.0, min_bars: int = 30) -> bool:
    """CCI (Commodity Channel Index, Donald Lambert, 1980): МЕХАНИЧНО
    различна математика от RSI/Stochastic - измерва отклонението на
    типичната цена (H+L+C)/3 от нейната пълзяща средна, нормализирано
    спрямо СРЕДНОТО АБСОЛЮТНО отклонение (не стандартно отклонение като
    Bollinger, нито close-to-close разлика като RSI). Сигналът е CCI да
    пресече обратно НАД `oversold` прага (-100, класическа "extreme"
    граница) за първи път, след като е бил под него.
    https://www.investopedia.com/terms/c/commoditychannelindex.asp (07.10,
    по молба "давай още стратегии")."""
    min_len = period + min_bars
    if len(df) < min_len:
        return False
    tp = (df["high"] + df["low"] + df["close"]) / 3.0
    sma = tp.rolling(period).mean()
    mad = tp.rolling(period).apply(lambda x: np.mean(np.abs(x - x.mean())), raw=True)
    cci = (tp - sma) / (0.015 * mad.replace(0, np.nan))
    today_cci, yest_cci = cci.iloc[-1], cci.iloc[-2]
    if pd.isna(today_cci) or pd.isna(yest_cci):
        return False
    return bool(yest_cci <= oversold and today_cci > oversold)


def signal_three_white_soldiers(df: pd.DataFrame, min_body_pct: float = 0.5, min_bars: int = 10) -> bool:
    """Three White Soldiers (класическа японска свещна фигура): ТРИ
    последователни бичи свещи, всяка затваря по-високо от предходната, с
    тяло >= `min_body_pct` от дневния диапазон, всяка отваряща вътре в
    тялото на предходната - continuation сигнал за нарастващ купувачки
    натиск. МЕХАНИЧНО различно от bullish_engulfing_reversal (която е само
    2-свещен единичен обрат) - тук трябва ТРИ поредни потвърждения, не
    една.
    https://www.investopedia.com/terms/t/three_white_soldiers.asp (07.10,
    по молба "давай още стратегии")."""
    if len(df) < min_bars + 3:
        return False
    last3 = df.iloc[-3:]
    opens, closes = last3["open"].values, last3["close"].values
    highs, lows = last3["high"].values, last3["low"].values
    for i in range(3):
        rng = highs[i] - lows[i]
        if rng <= 0:
            return False
        body = closes[i] - opens[i]
        if body <= 0 or (body / rng) < min_body_pct:
            return False
    rising_closes = closes[0] < closes[1] < closes[2]
    opens_within_prev_body = all(
        min(opens[i - 1], closes[i - 1]) <= opens[i] <= max(opens[i - 1], closes[i - 1])
        for i in [1, 2]
    )
    return bool(rising_closes and opens_within_prev_body)


def signal_darvas_box_breakout(df: pd.DataFrame, peak_lookback: int = 60, box_days: int = 3, confirm_vol_mult: float = 1.3, min_bars: int = 70) -> bool:
    """Darvas Box (Nicolas Darvas, "How I Made $2,000,000 in the Stock
    Market"): класическа "купи сила" техника, но ПО-СТРОГА от
    donchian_breakout - изисква РЕАЛНО ФОРМИРАНА консолидационна кутия, не
    просто rolling N-дневен връх. Намира последния връх (high) в последните
    `peak_lookback` дни, после проверява дали СЛЕДВАЩИТЕ `box_days` дни НЕ
    са направили нов връх над него (кутията "задържа" - box top = peak
    high). Сигналът е днешното close да пробие над box top ЗА ПЪРВИ път
    след края на кутията, на >= `confirm_vol_mult` x среден обем.
    https://www.investopedia.com/terms/d/darvas-box-theory.asp (07.10, по
    молба "потърси повече")."""
    min_len = peak_lookback + min_bars
    if len(df) < min_len:
        return False
    window = df.iloc[-peak_lookback:]
    highs = window["high"].values
    closes = window["close"].values
    volumes = window["volume"].values
    n = len(window)
    # Върхът се търси БЕЗ днешния ден - иначе денят на самия пробив (който
    # обикновено Е новият връх по дефиниция) погрешно би се "самоизбрал" за
    # "връх на кутията", вместо истинския по-ранен връх.
    peak_search = highs[:-1]
    if len(peak_search) < 10:
        return False
    peak_pos = int(np.argmax(peak_search))
    if peak_pos > n - box_days - 2:
        return False  # не остава достатъчно дни след върха за кутия + пробив
    box_top = highs[peak_pos]
    box_window_highs = highs[peak_pos + 1: peak_pos + 1 + box_days]
    if len(box_window_highs) < box_days or box_window_highs.max() >= box_top:
        return False  # кутията не е "задържала" - имало е нов връх вътре
    post_box_closes = closes[peak_pos + 1 + box_days:]
    if len(post_box_closes) < 1:
        return False
    today_close = post_box_closes[-1]
    if len(post_box_closes) > 1 and (post_box_closes[:-1] >= box_top).any():
        return False  # вече е имало пробив по-рано - не е "за първи път"
    if today_close <= box_top:
        return False
    avg_vol = volumes[peak_pos + 1:-1].mean() if len(volumes[peak_pos + 1:-1]) else 0
    today_vol = volumes[-1]
    if not avg_vol or today_vol < confirm_vol_mult * avg_vol:
        return False
    return True


def signal_resistance_flip_retest(df: pd.DataFrame, lookback: int = 60, recent_days: int = 10, min_bars: int = 70) -> bool:
    """Polarity Principle / "стара съпротива става подкрепа" (класическа
    техническа концепция): намира локален връх (по close) в по-ранната
    част на `lookback`-дневния прозорец (преди последните `recent_days`
    дни), после проверява дали цената е останала ПОД това ниво през
    последните `recent_days` дни (нивото реално е "отблъснало" цената поне
    веднъж, не е случайно докоснато) И днес затваря НАД него за ПЪРВИ път.
    За разлика от fib_retracement_bounce (който гледа ГЕОМЕТРИЧЕН % откат),
    тук нивото е РЕАЛЕН исторически връх, без никакво съотношение.
    https://www.investopedia.com/articles/technical/04/050504.asp (07.10,
    по молба "потърси повече")."""
    min_len = lookback + min_bars
    if len(df) < min_len:
        return False
    window = df.iloc[-lookback:]
    closes = window["close"].values
    older = closes[:-(recent_days + 1)]
    recent = closes[-(recent_days + 1):-1]
    today = closes[-1]
    if len(older) < 10:
        return False
    resistance = older.max()
    if resistance <= 0:
        return False
    tested_and_held = bool((recent < resistance).all())
    first_breakout = bool(today > resistance)
    return bool(tested_and_held and first_breakout)


def signal_donchian_breakout_long(df: pd.DataFrame, channel_period: int = 100, confirm_vol_mult: float = 1.5) -> bool:
    """НЕ нова концепция, а директен тест на ЕДИН параметър: същата вече
    валидирана donchian_breakout логика (виж по-горе), но с МНОГО по-дълъг
    lookback (100 дни вместо 20) - "истински" нов връх за по-дълъг период.
    Цел: да изолираме дали по-дългият хоризонт носи по-силен (но по-рядък)
    сигнал, или по-малкият брой сигнали не компенсира (07.10, по молба
    "потърси повече")."""
    return signal_donchian_breakout(df, channel_period=channel_period, confirm_vol_mult=confirm_vol_mult)


def signal_flag_breakout(df: pd.DataFrame, pole_days: int = 10, pole_min_pct: float = 15.0, flag_days: int = 6, flag_max_range_pct: float = 8.0, min_bars: int = 40) -> bool:
    """Flag (класическа continuation фигура): силно възходящо движение
    ("pole", >= `pole_min_pct`% за `pole_days` дни), последвано от ТЯСНА
    консолидация ("flag", диапазон <= `flag_max_range_pct`% за `flag_days`
    дни), после пробив над върха на флага. За разлика от vcp_contraction
    (която изисква само свиваща се волатилност без конкретно изискване за
    предходен силен ход), тук ИЗРИЧНО изискваме доказан предходен "pole".
    https://www.investopedia.com/terms/f/flag.asp (07.10, по молба "давай
    продължаваме")."""
    min_len = pole_days + flag_days + min_bars
    if len(df) < min_len:
        return False
    close, high, low = df["close"].values, df["high"].values, df["low"].values
    n = len(close)
    flag_start = n - flag_days
    pole_start = flag_start - pole_days
    if pole_start < 0:
        return False
    pole_begin_price = close[pole_start]
    pole_end_price = close[flag_start - 1]
    if not pole_begin_price:
        return False
    pole_move_pct = (pole_end_price - pole_begin_price) / pole_begin_price * 100
    if pole_move_pct < pole_min_pct:
        return False
    flag_highs = high[flag_start:-1]
    flag_lows = low[flag_start:-1]
    if len(flag_highs) < flag_days - 1:
        return False
    flag_high = flag_highs.max()
    flag_low = flag_lows.min()
    flag_range_pct = (flag_high - flag_low) / pole_end_price * 100
    if flag_range_pct > flag_max_range_pct:
        return False
    today_close = close[-1]
    return bool(today_close > flag_high)


def signal_double_bottom_breakout(df: pd.DataFrame, lookback: int = 60, tolerance_pct: float = 5.0, min_separation: int = 5, min_bars: int = 70) -> bool:
    """Double Bottom ("W" фигура, класическа обратна фигура): намира ДВЕ
    сравними дъна (в рамките на `tolerance_pct`%) в последните `lookback`
    дни, разделени от връх (neckline) между тях. Сигналът е днешното close
    да пробие НАД neckline нивото за ПЪРВИ път - потвърждение на обрат от
    РЕАЛНА геометрична фигура, не просто единично ниво като Donchian.
    https://www.investopedia.com/terms/d/doublebottom.asp (07.10, по молба
    "давай продължаваме")."""
    min_len = lookback + min_bars
    if len(df) < min_len:
        return False
    window = df.iloc[-lookback:]
    lows = window["low"].values
    closes = window["close"].values
    n = len(window)
    candidates = []
    for i in range(0, n - min_separation - 3):
        low1 = lows[i]
        if low1 <= 0:
            continue
        for j in range(i + min_separation, n - 2):
            low2 = lows[j]
            diff_pct = abs(low1 - low2) / low1 * 100
            if diff_pct > tolerance_pct:
                continue
            between_high = closes[i:j].max()
            if between_high <= max(low1, low2):
                continue
            candidates.append((j, i, between_high))
    if not candidates:
        return False
    candidates.sort()
    j, i, neckline = candidates[-1]
    post = closes[j + 1:]
    if len(post) < 1:
        return False
    today_close = post[-1]
    if len(post) > 1 and (post[:-1] >= neckline).any():
        return False  # вече е пробило по-рано - не е "за първи път"
    return bool(today_close > neckline)


def signal_obv_leads_price(df: pd.DataFrame, lookback: int = 20, min_bars: int = 30) -> bool:
    """OBV (On-Balance Volume) прави НОВ `lookback`-дневен връх ДНЕС,
    ДОКАТО самата цена (close) ОЩЕ НЕ Е направила нов `lookback`-дневен
    връх - "обемът идва преди цената". Различно от quiet_accumulation
    (която гледа OBV дивергенция по време на ПЛОСКА цена) - тук конкретно
    изискваме OBV да пробие собствения си N-дневен връх, докато цената
    изостава, независимо дали е плоска или леко расте.
    https://www.investopedia.com/terms/o/onbalancevolume.asp (07.10, по
    молба "давай продължаваме")."""
    min_len = lookback + min_bars
    if len(df) < min_len:
        return False
    close = df["close"]
    direction = np.sign(close.diff()).fillna(0)
    obv = (direction * df["volume"]).cumsum()
    obv_window = obv.iloc[-(lookback + 1):]
    close_window = close.iloc[-(lookback + 1):]
    obv_today, obv_prior_max = obv_window.iloc[-1], obv_window.iloc[:-1].max()
    close_today, close_prior_max = close_window.iloc[-1], close_window.iloc[:-1].max()
    obv_new_high = obv_today > obv_prior_max
    price_not_new_high = close_today <= close_prior_max
    return bool(obv_new_high and price_not_new_high)


def signal_hammer_reversal(df: pd.DataFrame, decline_lookback: int = 10, decline_threshold_pct: float = 10.0,
                            min_lower_wick_ratio: float = 2.0, max_upper_wick_ratio: float = 0.3) -> bool:
    """Hammer (чук) - класическа ЕДНОСВЕЩНА японска обратна формация (за
    разлика от bullish_engulfing_reversal - 2 свещи, и three_white_soldiers
    - 3 свещи, тук трябва само ЕДНА свещ): малко тяло близо до ВЪРХА на
    дневния диапазон, дълга долна сянка (>= `min_lower_wick_ratio` x
    тялото - показва, че продавачите са бутнали цената надолу, но
    купувачите са я върнали обратно до затваряне) и почти никаква горна
    сянка, след предходен спад от поне `decline_threshold_pct`% през
    `decline_lookback` дни (контекст - хамър насред рали не е обратна
    формация, а случаен шум).
    https://www.investopedia.com/terms/h/hammer.asp (07.10, по молба
    "давай продължаваме")."""
    if len(df) < decline_lookback + 2:
        return False
    o, h, l, c = df["open"].iloc[-1], df["high"].iloc[-1], df["low"].iloc[-1], df["close"].iloc[-1]
    rng = h - l
    if rng <= 0:
        return False
    body = abs(c - o)
    if body <= 0:
        return False
    lower_wick = min(o, c) - l
    upper_wick = h - max(o, c)
    is_hammer_shape = (lower_wick >= min_lower_wick_ratio * body) and (upper_wick <= max_upper_wick_ratio * body)
    if not is_hammer_shape:
        return False
    prior_window = df["close"].iloc[-(decline_lookback + 1):-1]
    if len(prior_window) < decline_lookback:
        return False
    start_price = prior_window.iloc[0]
    end_price = df["close"].iloc[-2]
    if not start_price:
        return False
    decline_pct = (end_price - start_price) / start_price * 100
    return bool(decline_pct <= -decline_threshold_pct)


def signal_cmf_turn_positive(df: pd.DataFrame, period: int = 20, confirm_days: int = 5, min_bars: int = 30) -> bool:
    """Chaikin Money Flow (CMF) - ОГРАНИЧЕН (между -1 и +1) обемно-претеглен
    осцилатор: за всеки ден Money Flow Multiplier = ((close-low)-(high-close))/(high-low)
    (позицията на затварянето В РАМКИТЕ на деня - горе=+1, долу=-1),
    умножено по обема, сумирано за `period` дни и разделено на сумарния
    обем. Различно от OBV (obv_leads_price/quiet_accumulation - кумулативна
    сума без ограничение, расте неограничено с времето) и от A/D Line
    (ad_line_divergence - също кумулативна) - CMF е ОСРЕДНЕН индекс за
    ПОСЛЕДНИТЕ `period` дни, забравя старата история. Сигнал: CMF пресича
    от отрицателно НА положително ДНЕС, след поне `confirm_days`
    последователни дни СТРОГО под нулата преди това (истински обрат в
    обемния поток, не шум около нулата).
    https://www.investopedia.com/terms/c/chaikinmoneyflow.asp (07.10, по
    молба "давай продължаваме")."""
    min_len = period + confirm_days + min_bars
    if len(df) < min_len:
        return False
    high, low, close, vol = df["high"], df["low"], df["close"], df["volume"]
    rng = high - low
    mfm = ((close - low) - (high - close)) / rng.replace(0, np.nan)
    mfm = mfm.fillna(0.0)
    mfv = mfm * vol
    cmf = mfv.rolling(period).sum() / vol.rolling(period).sum().replace(0, np.nan)
    cmf = cmf.dropna()
    if len(cmf) < confirm_days + 1:
        return False
    today, prior = cmf.iloc[-1], cmf.iloc[-(confirm_days + 1):-1]
    crossed_up = today > 0 and (prior < 0).all()
    return bool(crossed_up)


def signal_near_high_volume_build(df: pd.DataFrame, high_lookback: int = 60, proximity_pct: float = 5.0,
                                   vol_lookback: int = 5, vol_build_mult: float = 1.5, min_bars: int = 65) -> bool:
    """"Преди да избухне" в НАЙ-буквалния смисъл - за разлика от ВСИЧКИ
    breakout стратегии тук (donchian_breakout, darvas_box_breakout,
    resistance_flip_retest, double_bottom_breakout и др.), които
    сигнализират В ДЕНЯ на самия пробив, тук цената ОЩЕ НЕ Е пробила -
    просто е в рамките на `proximity_pct`% от своя `high_lookback`-дневен
    връх (не го е докоснала/пробила), ДОКАТО обемът от последните
    `vol_lookback` дни расте спрямо по-ранния `vol_lookback`-дневен период
    (купувачки интерес се трупа ПРЕДИ пробива, не след него). Умишлено НЕ
    изисква пробив - идеята е да хване setup-а няколко дни по-рано от
    donchian_breakout, точно темата от първоначалната молба на
    потребителя ("да намира penny stocks преди да избухнат").
    (07.10, по молба "давай продължаваме")."""
    min_len = high_lookback + min_bars
    if len(df) < min_len:
        return False
    window = df.iloc[-high_lookback:]
    highs = window["high"].values
    closes = window["close"].values
    vols = window["volume"].values
    today_close = closes[-1]
    period_high = highs[:-1].max() if len(highs) > 1 else highs[-1]
    if not period_high or today_close > period_high:
        return False  # вече пробила - не е "преди"
    proximity = (period_high - today_close) / period_high * 100
    if proximity > proximity_pct:
        return False
    if len(vols) < vol_lookback * 2:
        return False
    recent_vol = vols[-vol_lookback:].mean()
    prior_vol = vols[-(vol_lookback * 2):-vol_lookback].mean()
    if not prior_vol:
        return False
    vol_building = recent_vol >= vol_build_mult * prior_vol
    return bool(vol_building)


def signal_mfi_oversold_turn(df: pd.DataFrame, period: int = 14, oversold_level: float = 20.0, min_bars: int = 30) -> bool:
    """Money Flow Index (MFI) - "обемно претегленото RSI": typical_price =
    (high+low+close)/3, money_flow = typical_price*volume, разделен на
    положителен/отрицателен според посоката на typical_price спрямо вчера,
    MFI = 100 - 100/(1+сума(положителен)/сума(отрицателен)). Различна
    математика от cmf_turn_positive (което е ОГРАНИЧЕНА позиция-в-деня
    претеглена с обем, не ratio на положителен/отрицателен паричен поток)
    и от RSI/stochastic/CCI (които изобщо не ползват обем). Сигнал: MFI
    пресича НАГОРЕ прага `oversold_level` (класически обрат от
    препродаденост, същия стил сигнал като stochastic_oversold_turn/
    cci_extreme_reversal, но с различен осцилатор).
    https://www.investopedia.com/terms/m/mfi.asp (07.10, по молба "дай
    още да пробваме")."""
    min_len = period + min_bars
    if len(df) < min_len:
        return False
    typical = (df["high"] + df["low"] + df["close"]) / 3
    mf = typical * df["volume"]
    tp_diff = typical.diff()
    pos_flow = mf.where(tp_diff > 0, 0.0)
    neg_flow = mf.where(tp_diff < 0, 0.0)
    pos_sum = pos_flow.rolling(period).sum()
    neg_sum = neg_flow.rolling(period).sum()
    mfr = pos_sum / neg_sum.replace(0, np.nan)
    mfi = 100 - (100 / (1 + mfr))
    mfi = mfi.dropna()
    if len(mfi) < 2:
        return False
    today, yesterday = mfi.iloc[-1], mfi.iloc[-2]
    crossed_up = yesterday <= oversold_level and today > oversold_level
    return bool(crossed_up)


def signal_morning_star_reversal(df: pd.DataFrame, min_body1_pct: float = 3.0, max_body2_pct: float = 1.5,
                                  min_body3_pct: float = 3.0, min_bars: int = 10) -> bool:
    """Morning Star - класическа 3-свещна ОБРАТНА японска формация: ден 1
    голяма мечи свещ, ден 2 МАЛКО тяло ("звездата" - несигурност, отваря/
    затваря под затварянето на ден 1), ден 3 голяма бичи свещ, затваряща
    над средата на тялото на ден 1. МЕХАНИЧНО различно от
    three_white_soldiers (3 свещи, но CONTINUATION формация - продължение
    на вече съществуващ възходящ тренд, не обрат) - тук е класически
    ОБРАТ след спад, с "неутрален" ден по средата.
    https://www.investopedia.com/terms/m/morningstar.asp (07.10, по молба
    "дай още да пробваме")."""
    if len(df) < min_bars + 3:
        return False
    last3 = df.iloc[-3:]
    o = last3["open"].values
    c = last3["close"].values
    body1_pct = (o[0] - c[0]) / o[0] * 100 if o[0] else 0
    if not (c[0] < o[0] and body1_pct >= min_body1_pct):
        return False
    body2_pct = abs(c[1] - o[1]) / o[1] * 100 if o[1] else 999
    if body2_pct > max_body2_pct:
        return False
    if max(o[1], c[1]) > c[0]:
        return False
    bullish3 = c[2] > o[2]
    body3_pct = (c[2] - o[2]) / o[2] * 100 if o[2] else 0
    midpoint_day1 = (o[0] + c[0]) / 2
    closes_into_day1 = c[2] >= midpoint_day1
    if not (bullish3 and body3_pct >= min_body3_pct and closes_into_day1):
        return False
    return True


def signal_atr_expansion_breakout(df: pd.DataFrame, atr_period: int = 14, expansion_mult: float = 2.0,
                                   close_position_min: float = 0.7, min_bars: int = 30) -> bool:
    """ATR Expansion - обратната идея на ВСИЧКИ "свиване на волатилността"
    стратегии тук (nr7_squeeze, bollinger_squeeze, ttm_squeeze,
    vcp_contraction, three_bar_tight, keltner_breakout) - вместо да чака
    СВИВАНЕ преди пробив, тази хваща ВНЕЗАПНО РАЗШИРЕНИЕ: истинският
    дневен диапазон (True Range, Wilder) днес е >= `expansion_mult` x
    средния ATR за предходните `atr_period` дни (БЕЗ днешния ден в
    базата, за да не се самозамърсява сравнението), И затварянето е в
    горната част (`close_position_min`) на този широк диапазон - посочва
    посока, не само хаос.
    https://www.investopedia.com/terms/a/atr.asp (07.10, по молба "дай
    още да пробваме")."""
    min_len = atr_period + min_bars + 1
    if len(df) < min_len:
        return False
    high, low, close = df["high"], df["low"], df["close"]
    prev_close = close.shift(1)
    tr = pd.concat([high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1).max(axis=1)
    atr_baseline = tr.iloc[-(atr_period + 1):-1].mean()
    today_tr = tr.iloc[-1]
    if not atr_baseline or today_tr < expansion_mult * atr_baseline:
        return False
    today_high, today_low, today_close = high.iloc[-1], low.iloc[-1], close.iloc[-1]
    rng = today_high - today_low
    if rng <= 0:
        return False
    close_position = (today_close - today_low) / rng
    return bool(close_position >= close_position_min)


def signal_volume_ratio_breakout(df: pd.DataFrame, period: int = 10, ratio_threshold: float = 2.0, min_bars: int = 20) -> bool:
    """Up/Down Volume Ratio - сумира отделно обема на UP дните (close >
    предходен close) и DOWN дните за последните `period` дни, взема
    съотношението им. ПРОСТА ratio математика, различна от OBV
    (кумулативен сбор със знак), CMF/MFI (претеглени средни/money-flow
    съотношения) и A/D line (кумулативна позиция-в-деня) - тук просто
    "колко повече пари са влезли отколкото излезли, в чист обем". Сигнал:
    съотношението >= `ratio_threshold`, И днес е UP ден (моментум все още
    активен, не остатък от стар сигнал).
    https://www.investopedia.com/terms/u/up-downvolumeratio.asp (07.10,
    по молба "продължаваме")."""
    min_len = period + min_bars + 1
    if len(df) < min_len:
        return False
    close = df["close"]
    vol = df["volume"]
    direction = np.sign(close.diff())
    window_dir = direction.iloc[-period:]
    window_vol = vol.iloc[-period:]
    up_vol = window_vol[window_dir > 0].sum()
    down_vol = window_vol[window_dir < 0].sum()
    if not down_vol:
        return False
    ratio = up_vol / down_vol
    today_up = direction.iloc[-1] > 0
    return bool(ratio >= ratio_threshold and today_up)


def signal_bear_power_reclaim(df: pd.DataFrame, ema_period: int = 13, lookback: int = 10,
                               min_recovery_pct: float = 3.0, min_bars: int = 30) -> bool:
    """Elder Ray Index (Dr. Alexander Elder) - Bear Power = днешното LOW
    минус EMA(`ema_period`) - измерва колко далеч под тренда продавачите
    са успели да бутнат цената. Различно от всичко rolling/обемно тук -
    директно свързва ценовия екстремум със съществуваща тренд-линия (EMA),
    не с rolling max/min (Donchian) или ATR ленти (Keltner). Сигнал: Bear
    Power е ВСЕ ОЩЕ отрицателен (цената все още под EMA - антиципационно,
    не пълен reclaim), НО се е възстановил с поне `min_recovery_pct`% (от
    цената) спрямо най-ниската си точка през последните `lookback` дни -
    продавачкият натиск отслабва, преди да има пълно обръщане.
    https://www.investopedia.com/terms/e/elderray.asp (07.10, по молба
    "продължаваме")."""
    min_len = ema_period + lookback + min_bars
    if len(df) < min_len:
        return False
    ema = df["close"].ewm(span=ema_period, adjust=False).mean()
    bear_power = df["low"] - ema
    bp_window = bear_power.iloc[-(lookback + 1):]
    if len(bp_window) < lookback + 1:
        return False
    bp_today = bp_window.iloc[-1]
    bp_prior_min = bp_window.iloc[:-1].min()
    ema_today = ema.iloc[-1]
    if not ema_today:
        return False
    still_below = bp_today < 0
    recovered_pct = (bp_today - bp_prior_min) / ema_today * 100
    return bool(still_below and bp_prior_min < 0 and recovered_pct >= min_recovery_pct)


def signal_long_term_low_rebound(df: pd.DataFrame, low_lookback: int = 200, rebound_pct: float = 15.0,
                                  recency_days: int = 15, min_bars: int = 30) -> bool:
    """СТРУКТУРНО ОБРАТНА идея на near_high_volume_build - вместо близо до
    връх, тук цената е направила сериозен ОТСКОК (>= `rebound_pct`%) от
    своето `low_lookback`-дневно (~ 200 дни = почти 1 година) дъно,
    установено ПРЕДИ последните `recency_days` дни (реално историческо
    дъно, не вчерашния спад). Различно и от fib_retracement_bounce (която
    гледа геометричен % откат от ПОСЛЕДНОТО колебание, не позиция спрямо
    дългосрочен диапазон) и от capitulation_reversal (която е краткосрочен
    10-дневен volume-climax сигнал, не дългосрочна позиция). Днес трябва
    да е UP ден - активен отскок, не просто "някъде над дъното".
    (07.10, по молба "продължаваме")."""
    min_len = low_lookback + min_bars
    if len(df) < min_len:
        return False
    window = df.iloc[-low_lookback:]
    lows = window["low"].values
    closes = window["close"].values
    older_part = lows[:-recency_days] if len(lows) > recency_days else lows
    if len(older_part) < 10:
        return False
    period_low = older_part.min()
    today_close = closes[-1]
    if not period_low:
        return False
    rebound = (today_close - period_low) / period_low * 100
    prior_close = closes[-2] if len(closes) > 1 else today_close
    today_up = today_close > prior_close
    return bool(rebound >= rebound_pct and today_up)


def signal_golden_cross(df: pd.DataFrame, fast: int = 50, slow: int = 200, min_bars: int = 10) -> bool:
    """Golden Cross - класически ДЪЛГОСРОЧЕН trend-regime сигнал: 50-дневна
    пресича НАГОРЕ 200-дневната пълзяща средна. Напълно различен времеви
    мащаб от всичко друго тук (повечето стратегии гледат 10-60 дни) -
    това е сигнал за смяна на РЕЖИМА (bull/bear), не "setup преди
    пробив". Очаквано РЯДЪК и БАВЕН сигнал - изисква 200+ дни история,
    затова по-малко сигнали в 250-дневен backtest прозорец от повечето
    други стратегии тук.
    https://www.investopedia.com/terms/g/goldencross.asp (08.10, по
    молба "още тествания още стратегии")."""
    min_len = slow + min_bars
    if len(df) < min_len:
        return False
    ma_fast = df["close"].rolling(fast).mean()
    ma_slow = df["close"].rolling(slow).mean()
    diff = (ma_fast - ma_slow).dropna()
    if len(diff) < 2:
        return False
    today, yesterday = diff.iloc[-1], diff.iloc[-2]
    crossed_up = yesterday <= 0 and today > 0
    return bool(crossed_up)


def signal_pvt_new_high(df: pd.DataFrame, lookback: int = 20, min_bars: int = 30) -> bool:
    """Price Volume Trend (PVT) - като obv_leads_price, НО вместо двоичен
    знак (+volume/-volume), тук всеки ден се претегля с ПРОЦЕНТНАТА
    промяна на цената (pct_change * volume), кумулативно сумирано.
    Различна "сила" на претегляне от OBV (бинарен знак) - ден с голямо %
    движение тежи повече от ден с малко, независимо от обема сам по себе
    си. Сигнал: PVT прави нов `lookback`-дневен връх ДНЕС, докато самата
    цена ОЩЕ НЕ Е.
    https://www.investopedia.com/terms/p/pvt.asp (08.10, по молба "още
    тествания още стратегии")."""
    min_len = lookback + min_bars + 1
    if len(df) < min_len:
        return False
    pct_change = df["close"].pct_change()
    pvt = (pct_change * df["volume"]).cumsum()
    pvt_window = pvt.iloc[-(lookback + 1):]
    close_window = df["close"].iloc[-(lookback + 1):]
    pvt_today, pvt_prior_max = pvt_window.iloc[-1], pvt_window.iloc[:-1].max()
    close_today, close_prior_max = close_window.iloc[-1], close_window.iloc[:-1].max()
    pvt_new_high = pvt_today > pvt_prior_max
    price_not_new_high = close_today <= close_prior_max
    return bool(pvt_new_high and price_not_new_high)


def signal_three_inside_up(df: pd.DataFrame, decline_lookback: int = 5, decline_threshold_pct: float = 5.0,
                            min_bars: int = 10) -> bool:
    """Three Inside Up - класическа 3-свещна ОБРАТНА формация, различна от
    morning_star_reversal (там ден 2 е МАЛКО тяло/звезда, обикновено
    gap-ната) - тук ден 2 е HARAMI: тялото му е ИЗЦЯЛО вътре в тялото на
    ден 1 (без значение посоката), а ден 3 потвърждава със затваряне НАД
    върха (high) на ден 1 - по-строго изискване за потвърждение от
    morning_star (която иска само над средата на тялото). Контекст: спад
    от поне `decline_threshold_pct`% преди ден 1.
    https://www.investopedia.com/terms/t/three-inside-up-down.asp (08.10,
    по молба "още тествания още стратегии")."""
    if len(df) < min_bars + 3 + decline_lookback:
        return False
    last3 = df.iloc[-3:]
    o = last3["open"].values
    c = last3["close"].values
    h = last3["high"].values
    if not (c[0] < o[0]):
        return False
    day1_body_low, day1_body_high = min(o[0], c[0]), max(o[0], c[0])
    day2_inside = (o[1] >= day1_body_low) and (o[1] <= day1_body_high) and (c[1] >= day1_body_low) and (c[1] <= day1_body_high)
    if not day2_inside:
        return False
    day3_confirms = c[2] > o[2] and c[2] > h[0]
    if not day3_confirms:
        return False
    prior_window = df["close"].iloc[-(3 + decline_lookback):-3]
    if len(prior_window) < decline_lookback:
        return False
    start_price = prior_window.iloc[0]
    end_price = o[0]
    if not start_price:
        return False
    decline_pct = (end_price - start_price) / start_price * 100
    return bool(decline_pct <= -decline_threshold_pct)


def signal_williams_r_oversold_turn(df: pd.DataFrame, period: int = 14, oversold_level: float = -80.0, min_bars: int = 30) -> bool:
    """Williams %R (Larry Williams) - %R = (Highest High(N) - Close) /
    (Highest High(N) - Lowest Low(N)) x -100, диапазон -100 (на дъното) до
    0 (на върха). ПРОСТА, НЕизгладена позиция-в-диапазона - за разлика от
    stochastic_oversold_turn (изгладен %K/%D с moving average) и
    cci_extreme_reversal (средно абсолютно отклонение) - директна, по-
    "нервна" реакция без изглаждане. Сигнал: пресича НАГОРЕ прага
    `oversold_level` (= -80).
    https://www.investopedia.com/terms/w/williamsr.asp (08.10, по молба
    "продължаваме")."""
    min_len = period + min_bars
    if len(df) < min_len:
        return False
    high_n = df["high"].rolling(period).max()
    low_n = df["low"].rolling(period).min()
    denom = (high_n - low_n)
    wr = (high_n - df["close"]) / denom.replace(0, np.nan) * -100
    wr = wr.dropna()
    if len(wr) < 2:
        return False
    today, yesterday = wr.iloc[-1], wr.iloc[-2]
    crossed_up = yesterday <= oversold_level and today > oversold_level
    return bool(crossed_up)


def signal_cup_handle_breakout(df: pd.DataFrame, cup_lookback: int = 90, handle_days: int = 10,
                                min_cup_depth_pct: float = 15.0, max_handle_depth_pct: float = 12.0,
                                confirm_vol_mult: float = 1.3, min_bars: int = 100) -> bool:
    """Cup and Handle (William O'Neil) - класическа ДЪЛГА консолидационна
    формация: "U"-образен спад и възстановяване (чашата) до почти
    същото ниво като началото (rim = по-ниското от двете "устни"), после
    плитко дръпване (дръжката, макс `max_handle_depth_pct`% дълбочина),
    и пробив над ръба с обем. МЕХАНИЧНО най-сложната геометрична фигура
    тук - различна от darvas_box_breakout (правоъгълна кутия, не U-форма)
    и double_bottom_breakout (V-образни дъна с остър neckline, не плавна
    чаша).
    https://www.investopedia.com/terms/c/cupandhandle.asp (08.10, по
    молба "продължаваме")."""
    min_len = cup_lookback + min_bars
    if len(df) < min_len:
        return False
    window = df.iloc[-cup_lookback:]
    highs = window["high"].values
    closes = window["close"].values
    volumes = window["volume"].values
    cup_part = highs[:-handle_days]
    cup_closes = closes[:-handle_days]
    if len(cup_part) < 20:
        return False
    mid = len(cup_part) // 2
    left_lip = cup_part[:mid].max()
    right_lip = cup_part[mid:].max()
    rim = min(left_lip, right_lip)
    cup_bottom = cup_closes.min()
    if not rim or cup_bottom <= 0:
        return False
    cup_depth_pct = (rim - cup_bottom) / rim * 100
    if cup_depth_pct < min_cup_depth_pct:
        return False
    handle_highs = highs[-handle_days:]
    handle_closes = closes[-handle_days:]
    if (handle_highs[:-1] > rim).any():
        return False
    handle_low = handle_closes.min()
    handle_depth_pct = (rim - handle_low) / rim * 100
    if handle_depth_pct > max_handle_depth_pct:
        return False
    today_close = closes[-1]
    if today_close <= rim:
        return False
    avg_vol = volumes[-(handle_days + 1):-1].mean()
    today_vol = volumes[-1]
    if not avg_vol or today_vol < confirm_vol_mult * avg_vol:
        return False
    return True


def signal_accumulation_day_count(df: pd.DataFrame, lookback: int = 20, vol_mult: float = 1.5,
                                   min_count: int = 6, min_bars: int = 30) -> bool:
    """Accumulation Day Count (O'Neil CANSLIM концепция) - брои колко дни
    през последните `lookback` са "accumulation days" (обем >=
    `vol_mult` x средния за периода, И затварянето е в горната половина
    на дневния диапазон). За разлика от pocket_pivot (единичен ден
    спрямо max на down-дните) или volume_before_breakout (rolling
    тенденция), тук е ПРЯКО БРОЕНЕ на чести силни дни - честотен сигнал.
    Сигнал: броят >= `min_count` И днешният ден самият е accumulation
    day.
    https://www.investopedia.com/terms/a/accumulationdistribution.asp
    (концепцията за броене на "accumulation days" е от O'Neil/IBD
    методологията) (08.10, по молба "продължаваме")."""
    min_len = lookback + min_bars
    if len(df) < min_len:
        return False
    window = df.iloc[-lookback:]
    closes = window["close"].values
    highs = window["high"].values
    lows = window["low"].values
    vols = window["volume"].values
    avg_vol = vols.mean()
    if not avg_vol:
        return False
    count = 0
    for i in range(len(window)):
        rng = highs[i] - lows[i]
        if rng <= 0:
            continue
        close_pos = (closes[i] - lows[i]) / rng
        if vols[i] >= vol_mult * avg_vol and close_pos >= 0.5:
            count += 1
    today_rng = highs[-1] - lows[-1]
    if today_rng <= 0:
        return False
    today_close_pos = (closes[-1] - lows[-1]) / today_rng
    today_is_accum = vols[-1] >= vol_mult * avg_vol and today_close_pos >= 0.5
    return bool(count >= min_count and today_is_accum)


def signal_inside_bar_breakout(df: pd.DataFrame, min_bars: int = 15) -> bool:
    """Inside Bar Breakout (класическа 2-свещна консолидационна фигура):
    вчерашната свещ ("inside bar") е ИЗЦЯЛО вътре в диапазона [high, low]
    на по-предишната свещ ("mother bar") - двойно по-просто механично от
    nr7_squeeze/bollinger_squeeze/ttm_squeeze (там е rolling статистика
    за rank/ширина на диапазона, тук е директно сравнение на 2 свещи).
    Сигнал: днес затварянето излиза НАД върха на mother bar и е бичо
    (close > open).
    https://www.investopedia.com/terms/i/insidebar.asp
    (08.10, по молба "давай продължаваме")."""
    if len(df) < min_bars + 3:
        return False
    last3 = df.iloc[-3:]
    mother_high = last3["high"].iloc[0]
    mother_low = last3["low"].iloc[0]
    inside_high = last3["high"].iloc[1]
    inside_low = last3["low"].iloc[1]
    is_inside = (inside_high <= mother_high) and (inside_low >= mother_low)
    if not is_inside:
        return False
    today_close = last3["close"].iloc[2]
    today_open = last3["open"].iloc[2]
    breakout = (today_close > mother_high) and (today_close > today_open)
    return bool(breakout)


def signal_linreg_channel_breakout(df: pd.DataFrame, period: int = 20, std_mult: float = 2.0,
                                    min_bars: int = 25) -> bool:
    """Linear Regression Channel Breakout: прокарва права линия (least
    squares) през последните `period` затваряния и строи горна лента на
    `std_mult` стандартни отклонения на остатъците над нея - РАЗЛИЧНА
    математическа база от Bollinger (SMA+std), Keltner (EMA+ATR) и
    Donchian (просто max/min). Сигнал: вчера затварянето е било под
    горната лента, днес излиза над нея (свеж пробив на регресионния
    канал).
    https://www.investopedia.com/terms/l/linearregression.asp
    (08.10, по молба "давай продължаваме")."""
    min_len = period + min_bars
    if len(df) < min_len:
        return False
    window = df["close"].iloc[-period:]
    x = np.arange(period)
    y = window.values
    slope, intercept = np.polyfit(x, y, 1)
    fitted = slope * x + intercept
    resid = y - fitted
    std = resid.std()
    if not std:
        return False
    upper_today = fitted[-1] + std_mult * std
    upper_yesterday = (slope * (period - 2) + intercept) + std_mult * std
    today_close = y[-1]
    yesterday_close = y[-2]
    crossed = (yesterday_close <= upper_yesterday) and (today_close > upper_today)
    return bool(crossed)


def signal_chaikin_oscillator_cross(df: pd.DataFrame, fast: int = 3, slow: int = 10, min_bars: int = 30) -> bool:
    """Chaikin Oscillator Zero-Line Cross: разликата между бързата (3)
    и бавната (10) EMA на Accumulation/Distribution Line (A/D Line) -
    т.е. ВТОРА производна на обемно-претеглената позиция в диапазона,
    различна от cmf_turn_positive (проста ROLLING СУМА-отношение, не
    EMA-разлика) и от obv_leads_price/pvt_new_high (кумулативна линия
    без EMA-изглаждане). Сигнал: осцилаторът пресича нулата отдолу
    нагоре.
    https://www.investopedia.com/terms/c/chaikinoscillator.asp
    (08.10, по молба "давай продължаваме")."""
    min_len = slow + min_bars
    if len(df) < min_len:
        return False
    high, low, close, vol = df["high"], df["low"], df["close"], df["volume"]
    rng = (high - low).replace(0, np.nan)
    mfm = ((close - low) - (high - close)) / rng
    mfv = (mfm * vol).fillna(0.0)
    adl = mfv.cumsum()
    ema_fast = adl.ewm(span=fast, adjust=False).mean()
    ema_slow = adl.ewm(span=slow, adjust=False).mean()
    osc = (ema_fast - ema_slow).dropna()
    if len(osc) < 2:
        return False
    today, yesterday = osc.iloc[-1], osc.iloc[-2]
    crossed_up = (yesterday <= 0) and (today > 0)
    return bool(crossed_up)


def signal_up_down_volume_ratio_surge(df: pd.DataFrame, period: int = 10, ratio_threshold: float = 2.5,
                                       min_bars: int = 20) -> bool:
    """Up/Down Volume Ratio Surge: сумира обема в дните със затваряне
    НАГОРЕ срещу дните със затваряне НАДОЛУ през последните `period`
    дни - класическо "up volume / down volume" разделение, различно
    механично от OBV/PVT (единична кумулативна линия) и от CMF/Chaikin
    (intraday позиция в диапазона, не ден-за-ден знак). Сигнал: up/down
    съотношението >= `ratio_threshold` И днес е up-ден.
    https://www.investopedia.com/terms/u/upvolume.asp
    (08.10, по молба "давай продължаваме")."""
    min_len = period + min_bars + 1
    if len(df) < min_len:
        return False
    window = df.iloc[-(period + 1):]
    closes = window["close"].values
    vols = window["volume"].values
    up_vol = 0.0
    down_vol = 0.0
    for i in range(1, len(window)):
        if closes[i] > closes[i - 1]:
            up_vol += vols[i]
        elif closes[i] < closes[i - 1]:
            down_vol += vols[i]
    if down_vol <= 0:
        return False
    ratio = up_vol / down_vol
    today_up = closes[-1] > closes[-2]
    return bool(ratio >= ratio_threshold and today_up)


def signal_momentum_acceleration(df: pd.DataFrame, roc_period: int = 5, confirm_days: int = 3,
                                  min_bars: int = 20) -> bool:
    """Momentum Acceleration: проверява дали скоростта на изменение
    (Rate of Change за `roc_period` дни) САМА се увеличава строго
    `confirm_days` дни подред - т.е. ВТОРА производна (ускорение) на
    цената, не просто ниво/праг както при adx_trend_strength или
    aroon_up_cross. Сигнал: ROC расте строго монотонно последните дни
    И текущият ROC е положителен.
    https://www.investopedia.com/terms/r/rateofchange.asp
    (08.10, по молба "давай продължаваме")."""
    min_len = roc_period + confirm_days + min_bars
    if len(df) < min_len:
        return False
    roc = df["close"].pct_change(roc_period) * 100
    roc = roc.dropna()
    if len(roc) < confirm_days:
        return False
    last = roc.iloc[-confirm_days:]
    strictly_increasing = all(last.iloc[i] < last.iloc[i + 1] for i in range(len(last) - 1))
    return bool(strictly_increasing and last.iloc[-1] > 0)


def signal_vwap_reclaim(df: pd.DataFrame, period: int = 20, min_bars: int = 25) -> bool:
    """VWAP Reclaim: прокарва ROLLING обемно-претеглена средна цена
    (VWAP) за последните `period` дни - различно ПРЕТЕГЛЯНЕ от
    pullback_to_rising_ma (проста/EMA средна без обемна тежест).
    Сигнал: вчера затварянето е било под VWAP, днес се качва над него
    (reclaim на обемно-значимо ниво).
    https://www.investopedia.com/terms/v/vwap.asp
    (08.10, по молба "давай продължаваме")."""
    min_len = period + min_bars + 1
    if len(df) < min_len:
        return False
    pv = df["close"] * df["volume"]
    vwap = pv.rolling(period).sum() / df["volume"].rolling(period).sum()
    vwap = vwap.dropna()
    close = df["close"].loc[vwap.index]
    if len(vwap) < 2:
        return False
    today_close, yesterday_close = close.iloc[-1], close.iloc[-2]
    today_vwap, yesterday_vwap = vwap.iloc[-1], vwap.iloc[-2]
    crossed = (yesterday_close <= yesterday_vwap) and (today_close > today_vwap)
    return bool(crossed)


def signal_triple_confirmation_breakout(df: pd.DataFrame, breakout_lookback: int = 20, vol_mult: float = 2.0,
                                         trend_ma: int = 50, trend_lookback: int = 5, min_bars: int = 55) -> bool:
    """Triple Confirmation Breakout: КОМПОЗИТЕН сигнал (AND на 3
    условия, не едно), целящ по-висок win rate чрез по-голяма
    избирателност (по молба на потребителя - "целта ми е да намерим
    такива с win rate около 80%"): (1) пробив над `breakout_lookback`
    -дневен връх, (2) обем >= `vol_mult` x средния за периода, (3)
    цената е над 50-дневна MA И тя самата расте (дългосрочен тренд-
    филтър). Всяко условие поотделно прилича на съществуващи
    стратегии (donchian_breakout, pocket_pivot, adx_trend_strength),
    но тук се изискват ВСИЧКИТЕ ЕДНОВРЕМЕННО - много по-строго и
    рядко, с надеждата за по-качествени сигнали.
    (08.10, по молба "продължаваме да търсим", с цел по-висок win rate)."""
    min_len = max(breakout_lookback, trend_ma) + min_bars
    if len(df) < min_len:
        return False
    close = df["close"]
    vol = df["volume"]
    prior_window = close.iloc[-(breakout_lookback + 1):-1]
    if len(prior_window) < breakout_lookback:
        return False
    period_high = prior_window.max()
    today_close = close.iloc[-1]
    breakout = today_close > period_high
    if not breakout:
        return False
    prior_vol_window = vol.iloc[-(breakout_lookback + 1):-1]
    avg_vol = prior_vol_window.mean()
    if not avg_vol:
        return False
    vol_ok = vol.iloc[-1] >= vol_mult * avg_vol
    if not vol_ok:
        return False
    ma = close.rolling(trend_ma).mean()
    if len(ma.dropna()) < trend_lookback + 1:
        return False
    trend_ok = (today_close > ma.iloc[-1]) and (ma.iloc[-1] > ma.iloc[-1 - trend_lookback])
    return bool(trend_ok)


def signal_oscillator_confluence_oversold_turn(df: pd.DataFrame, rsi_period: int = 14, stoch_period: int = 14,
                                                stoch_smooth: int = 3, wr_period: int = 14,
                                                min_bars: int = 30) -> bool:
    """Oscillator Confluence Oversold Turn: друг КОМПОЗИТЕН сигнал - за
    разлика от stochastic_oversold_turn/cci_extreme_reversal/mfi_
    oversold_turn/williams_r_oversold_turn (всяка от тях е ЕДИН
    осцилатор поотделно), тук се изисква ТРИ различни осцилатора
    (RSI(14), Stochastic %K(14,3), Williams %R(14)) ЕДНОВРЕМЕННО да
    обръщат нагоре от препродадена зона в СЪЩИЯ ден - идеята е, че
    съгласие на няколко независими индикатора е по-силен сигнал от
    само един (целта е по-висок win rate чрез строгост/избирателност).
    (08.10, по молба "продължаваме да търсим", с цел по-висок win rate)."""
    min_len = max(rsi_period, stoch_period, wr_period) + min_bars + 1
    if len(df) < min_len:
        return False
    close, high, low = df["close"], df["high"], df["low"]

    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(rsi_period).mean()
    avg_loss = loss.rolling(rsi_period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = (100 - 100 / (1 + rs)).dropna()

    low_n = low.rolling(stoch_period).min()
    high_n = high.rolling(stoch_period).max()
    raw_k = (close - low_n) / (high_n - low_n).replace(0, np.nan) * 100
    stoch_k = raw_k.rolling(stoch_smooth).mean().dropna()

    high_n2 = high.rolling(wr_period).max()
    low_n2 = low.rolling(wr_period).min()
    wr = ((high_n2 - close) / (high_n2 - low_n2).replace(0, np.nan) * -100).dropna()

    if len(rsi) < 2 or len(stoch_k) < 2 or len(wr) < 2:
        return False

    rsi_turn = (rsi.iloc[-2] <= 35) and (rsi.iloc[-1] > rsi.iloc[-2])
    stoch_turn = (stoch_k.iloc[-2] <= 25) and (stoch_k.iloc[-1] > stoch_k.iloc[-2])
    wr_turn = (wr.iloc[-2] <= -80) and (wr.iloc[-1] > wr.iloc[-2])
    return bool(rsi_turn and stoch_turn and wr_turn)


def signal_quality_pullback_entry(df: pd.DataFrame, long_ma: int = 100, short_ma: int = 20, pullback_days: int = 5,
                                   vol_contraction_mult: float = 0.8, trend_lookback: int = 10,
                                   min_bars: int = 20) -> bool:
    """Quality Pullback Entry: трети КОМПОЗИТЕН сигнал - "купи плитката
    пауза в силен дългосрочен тренд": (1) цена над 100-дневна MA И тя
    расте (дългосрочен възходящ тренд), (2) цената е близо (+-3%) до
    20-дневната MA (плитка пауза, не срив), (3) обемът се СВИВА през
    паузата (тихо изчакване, не паническа продажба - като quiet_
    accumulation, но с изричен дългосрочен тренд-филтър отгоре), (4)
    днес е бичи ден (затваряне > вчера И > отваряне). Четирите условия
    заедно би трябвало да филтрират само най-чистите "купи дъното на
    паузата в тренд" сетъпи.
    (08.10, по молба "продължаваме да търсим", с цел по-висок win rate)."""
    min_len = long_ma + min_bars
    if len(df) < min_len:
        return False
    close, vol, open_ = df["close"], df["volume"], df["open"]

    ma_long = close.rolling(long_ma).mean()
    if len(ma_long.dropna()) < trend_lookback + 1:
        return False
    trend_ok = (close.iloc[-1] > ma_long.iloc[-1]) and (ma_long.iloc[-1] > ma_long.iloc[-1 - trend_lookback])
    if not trend_ok:
        return False

    ma_short = close.rolling(short_ma).mean()
    if not ma_short.iloc[-1]:
        return False
    near_short_ma = abs(close.iloc[-1] / ma_short.iloc[-1] - 1) <= 0.03
    if not near_short_ma:
        return False

    baseline_start = pullback_days + 20
    if len(vol) < baseline_start:
        return False
    recent_vol = vol.iloc[-pullback_days:].mean()
    baseline_vol = vol.iloc[-baseline_start:-pullback_days].mean()
    if not baseline_vol:
        return False
    vol_contracted = recent_vol <= vol_contraction_mult * baseline_vol
    if not vol_contracted:
        return False

    today_up = (close.iloc[-1] > close.iloc[-2]) and (close.iloc[-1] > open_.iloc[-1])
    return bool(today_up)


def signal_doji_breakout(df: pd.DataFrame, max_body_ratio: float = 0.15, min_bars: int = 15) -> bool:
    """Doji Breakout: вчерашната свещ е "doji" - тялото (|close-open|)
    е <= `max_body_ratio` от целия дневен диапазон (high-low) - пазарна
    нерешителност. Различно от inside_bar_breakout (там е КОНТЕЙНМЪНТ
    на диапазон спрямо предишен бар, тук е ФОРМА на самата свещ -
    малко тяло спрямо широк диапазон, без връзка с предишен бар).
    Сигнал: днес затварянето излиза над вчерашния връх, бичо.
    https://www.investopedia.com/terms/d/doji.asp
    (08.10, по молба "дай да тестваме още стратегии")."""
    if len(df) < min_bars + 2:
        return False
    last2 = df.iloc[-2:]
    y_open, y_close, y_high, y_low = (last2["open"].iloc[0], last2["close"].iloc[0],
                                       last2["high"].iloc[0], last2["low"].iloc[0])
    y_range = y_high - y_low
    if y_range <= 0:
        return False
    y_body = abs(y_close - y_open)
    is_doji = (y_body / y_range) <= max_body_ratio
    if not is_doji:
        return False
    t_open, t_close = last2["open"].iloc[1], last2["close"].iloc[1]
    breakout = (t_close > y_high) and (t_close > t_open)
    return bool(breakout)


def signal_vwap_extreme_deviation_reversion(df: pd.DataFrame, period: int = 50, deviation_pct: float = 15.0,
                                             min_bars: int = 30) -> bool:
    """VWAP Extreme Deviation Reversion: за разлика от vwap_reclaim
    (просто пресичане обратно над VWAP), тук изискваме цената да е
    СИЛНО под 50-дневния VWAP (>= `deviation_pct`%) - екстремно
    отклонение, mean-reversion логика, различна от простото "вчера под,
    днес над". Сигнал: отклонението е екстремно И днес е up-ден
    (начало на евентуално връщане към средата).
    https://www.investopedia.com/terms/v/vwap.asp
    (08.10, по молба "дай да тестваме още стратегии")."""
    min_len = period + min_bars
    if len(df) < min_len:
        return False
    pv = df["close"] * df["volume"]
    vwap = pv.rolling(period).sum() / df["volume"].rolling(period).sum()
    vwap = vwap.dropna()
    if len(vwap) < 1:
        return False
    close = df["close"].loc[vwap.index]
    today_vwap = vwap.iloc[-1]
    if not today_vwap:
        return False
    today_close = close.iloc[-1]
    deviation = (today_vwap - today_close) / today_vwap * 100
    far_below = deviation >= deviation_pct
    if not far_below:
        return False
    today_up = today_close > close.iloc[-2]
    return bool(today_up)


def signal_key_reversal_day(df: pd.DataFrame, lookback: int = 20, min_bars: int = 25) -> bool:
    """Key Reversal Day: класическа единично-дневна формация - днес
    дневният МИНИМУМ пробива под `lookback`-дневния минимум (паника
    надолу интрадей), НО затварянето е над вчерашното затваряне
    (пълно обръщане в рамките на деня). Различно от hammer_reversal
    (там е формата на свещта/дължина на опашките) и от
    capitulation_reversal (там вероятно е обемен критерий) - тук е
    чисто ценово "нов минимум -> обръщане", без изисквания за форма
    или обем.
    https://www.investopedia.com/terms/k/keyreversal.asp
    (08.10, по молба "дай да тестваме още стратегии")."""
    min_len = lookback + min_bars
    if len(df) < min_len:
        return False
    low = df["low"]
    close = df["close"]
    prior_low = low.iloc[-(lookback + 1):-1].min()
    today_low = low.iloc[-1]
    new_low = today_low < prior_low
    if not new_low:
        return False
    closes_above_prior = close.iloc[-1] > close.iloc[-2]
    return bool(closes_above_prior)


def signal_adx_di_crossover(df: pd.DataFrame, period: int = 14, min_bars: int = 30) -> bool:
    """ADX +DI/-DI Crossover: за разлика от adx_trend_strength (там е
    НИВО на самия ADX), тук е ПРЕСИЧАНЕ на двете насочени линии (+DI и
    -DI, по Wilder) - сигнал когато +DI пресича -DI отдолу нагоре,
    т.е. бичите ценови движения започват да доминират над мечите.
    Различен механизъм от всички останали кросоувър-сигнали (MA,
    MACD, Chaikin) - базиран на directional movement, не на цена/
    обем директно.
    https://www.investopedia.com/terms/a/adx.asp
    (08.10, по молба "продължаваме")."""
    min_len = period + min_bars + 1
    if len(df) < min_len:
        return False
    high, low, close = df["high"], df["low"], df["close"]
    up_move = high.diff()
    down_move = -low.diff()
    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)
    prev_close = close.shift(1)
    tr = pd.concat([(high - low), (high - prev_close).abs(), (low - prev_close).abs()], axis=1).max(axis=1)

    plus_dm = pd.Series(plus_dm, index=df.index)
    minus_dm = pd.Series(minus_dm, index=df.index)

    smoothed_tr = tr.rolling(period).sum()
    smoothed_plus_dm = plus_dm.rolling(period).sum()
    smoothed_minus_dm = minus_dm.rolling(period).sum()

    plus_di = (100 * smoothed_plus_dm / smoothed_tr.replace(0, np.nan)).dropna()
    minus_di = (100 * smoothed_minus_dm / smoothed_tr.replace(0, np.nan)).dropna()

    if len(plus_di) < 2 or len(minus_di) < 2:
        return False

    yesterday_below = plus_di.iloc[-2] <= minus_di.iloc[-2]
    today_above = plus_di.iloc[-1] > minus_di.iloc[-1]
    return bool(yesterday_below and today_above)


def signal_stealth_volume_anomaly(df: pd.DataFrame, period: int = 20, vol_mult: float = 3.0,
                                   max_price_change_pct: float = 1.5, min_bars: int = 25) -> bool:
    """Stealth Volume Anomaly: ЧИСТО обемна аномалия без изисквания за
    цена/ниво - огромен обемен скок (>= `vol_mult` x средния) ПРИ почти
    никаква промяна в цената (<= `max_price_change_pct`%). Идеята е
    "тихо поглъщане" - някой трупа/разпродава голяма позиция без да
    движи цената. Различно от near_high_volume_build (там трябва
    близост до връх) и pocket_pivot/volume_before_breakout (там обемът
    е контекстуален спрямо посока) - тук е ИЗОЛИРАНА обемна аномалия,
    навсякъде на графиката.
    (08.10, по молба "продължаваме")."""
    min_len = period + min_bars + 1
    if len(df) < min_len:
        return False
    close, vol = df["close"], df["volume"]
    prior_vol = vol.iloc[-(period + 1):-1]
    avg_vol = prior_vol.mean()
    if not avg_vol:
        return False
    vol_spike = vol.iloc[-1] >= vol_mult * avg_vol
    if not vol_spike:
        return False
    prior_close = close.iloc[-2]
    if not prior_close:
        return False
    price_change_pct = abs((close.iloc[-1] - prior_close) / prior_close * 100)
    quiet = price_change_pct <= max_price_change_pct
    return bool(quiet)


def signal_nvi_new_high(df: pd.DataFrame, lookback: int = 50, min_bars: int = 30) -> bool:
    """Negative Volume Index (NVI) New High: кумулативна линия, която
    се ОБНОВЯВА само в дните, когато обемът СПАДА спрямо предишния ден
    (идеята на Norman Fosback - "smart money" трупа позиции в тихите,
    нискообемни дни). Различна конструкция от OBV/PVT/ADL (те следят
    ВСЕКИ ден) - тук само "тихите" дни влияят на линията. Сигнал:
    NVI прави нов `lookback`-дневен връх.
    https://www.investopedia.com/terms/n/nvi.asp
    (08.10, по молба "продължаваме")."""
    min_len = lookback + min_bars
    if len(df) < min_len:
        return False
    close, vol = df["close"], df["volume"]
    pct_change = close.pct_change().fillna(0.0)
    vol_decreased = vol.diff() < 0

    nvi = pd.Series(index=df.index, dtype=float)
    nvi.iloc[0] = 1000.0
    for i in range(1, len(df)):
        if vol_decreased.iloc[i]:
            nvi.iloc[i] = nvi.iloc[i - 1] * (1 + pct_change.iloc[i])
        else:
            nvi.iloc[i] = nvi.iloc[i - 1]

    window = nvi.iloc[-(lookback + 1):]
    if len(window) < lookback + 1:
        return False
    prior_max = window.iloc[:-1].max()
    today_val = window.iloc[-1]
    return bool(today_val > prior_max)


def signal_closing_strength_streak(df: pd.DataFrame, lookback: int = 3, clv_threshold: float = 0.70,
                                     min_bars: int = 20) -> bool:
    """Closing Strength Streak: ОРИГИНАЛНА идея, не е стандартен учебников
    индикатор - базирана е на "Close Location Value" (CLV = (close-low)/
    (high-low), използва се вътрешно в Accumulation/Distribution Line, но
    тук се проверява НАПРАВО като самостоятелен филтър), а не на нея самата.
    Изисква `lookback` ПОСЛЕДОВАТЕЛНИ дни, във всеки от които цената
    затваря в горната част (>= clv_threshold) на дневния си диапазон -
    т.е. купувачите контролират затварянето, не само деня. Идеята: един
    силен ден може да е случайност, 3 поредни силни затваряния е по-труден
    за случайно обяснение модел на упорит натиск за покупка.
    (08.10, по молба "ще потърсим още малко не търси само известни
    стратегии" - оригинален композитен сигнал, не комбинация от познати
    индикатори)."""
    min_len = lookback + min_bars
    if len(df) < min_len:
        return False
    recent = df.iloc[-lookback:]
    rng = recent["high"] - recent["low"]
    if (rng <= 0).any():
        return False
    clv = (recent["close"] - recent["low"]) / rng
    return bool((clv >= clv_threshold).all())


def signal_volume_climax_reversal_2day(df: pd.DataFrame, period: int = 20, vol_mult: float = 2.5,
                                         min_bars: int = 25) -> bool:
    """Volume Climax Reversal (2-дневно потвърждение): ОРИГИНАЛНА идея -
    различна от capitulation_reversal (която гледа само ЕДИН ден). Тук
    ден T-1 трябва да е силен ПАДАЩ ден с "климаксен" обем (>= vol_mult *
    средния обем) - типичен признак на паник продажба/капитулация. Но
    СИГНАЛЪТ излиза едва на ден T (ВТОРИЯ ден), само ако цената ПОТВЪРДИ
    обрата: затваря >= вчерашното затваряне И не прави нов дневен минимум
    под вчерашния. Идеята: единичен "climax" ден лесно дава фалшиви
    обрати (виж capitulation_reversal по-рано тази сесия - слаб резултат);
    изискването за ВТОРИ ден без нов минимум филтрира голяма част от тях.
    (08.10, по молба "ще потърсим още малко не търси само известни
    стратегии")."""
    min_len = period + min_bars + 2
    if len(df) < min_len:
        return False
    close, low, vol = df["close"], df["low"], df["volume"]
    avg_vol = vol.iloc[-(period + 2):-2].mean()
    if not avg_vol:
        return False
    climax_day_vol = vol.iloc[-2]
    climax_day_down = close.iloc[-2] < close.iloc[-3]
    climax = climax_day_vol >= vol_mult * avg_vol
    if not (climax and climax_day_down):
        return False
    confirm = (close.iloc[-1] >= close.iloc[-2]) and (low.iloc[-1] >= low.iloc[-2])
    return bool(confirm)


def signal_range_compression_volume_asymmetry(df: pd.DataFrame, window: int = 15, min_bars: int = 25) -> bool:
    """Range Compression + Volume Asymmetry: ОРИГИНАЛНА идея - различна от
    bollinger_squeeze/ttm_squeeze/nr7_squeeze (те гледат САМО свиването на
    диапазона, без посока). Тук се изисква и второ условие: ПРЕЗ времето
    на свиването, обемът в дните на РАСТЕЖ да е забележимо по-висок
    (>30%) от обема в дните на СПАД - т.е. "тихото" свиване не е случайно,
    а има скрит насочен (бичи) натиск зад него. Идеята: чисто свиване на
    диапазона (squeeze) не казва накъде ще избие цената - добавянето на
    обемна асиметрия е опит да се познае посоката ПРЕДИ избухването.
    (08.10, по молба "ще потърсим още малко не търси само известни
    стратегии")."""
    min_len = window + min_bars
    if len(df) < min_len:
        return False
    recent = df.iloc[-window:]
    half = window // 2
    rng = recent["high"] - recent["low"]
    early_avg_range = rng.iloc[:half].mean()
    late_avg_range = rng.iloc[half:].mean()
    if not early_avg_range:
        return False
    compressing = late_avg_range < early_avg_range * 0.8
    if not compressing:
        return False
    closes = recent["close"]
    prior_closes = closes.shift(1)
    up_days = (closes > prior_closes).fillna(False)
    down_days = (closes < prior_closes).fillna(False)
    vol = recent["volume"]
    up_vol = vol[up_days].mean() if up_days.any() else 0.0
    down_vol = vol[down_days].mean() if down_days.any() else 0.0
    if not down_vol:
        return False
    asymmetric = up_vol > down_vol * 1.3
    return bool(asymmetric)


# Регистър - strategy_backtest.py (и по-късно евентуално main.py) минава
# през тях по име, за да може лесно да добавя/маха стратегии без да пипа
# извикващия код.
# (07.10, по молба "търси нови стратегии и пак backtest" - след като
# първите 5 НЕ показаха предимство пред random_baseline контролата в
# strategy_backtest.py, добавени 5 нови: TTM Squeeze, Volume Dry-Up,
# Three Bars Tight, MA Convergence Coil, VCP Contraction - различно
# семейство концепции (Minervini VCP школа + John Carter TTM Squeeze),
# за по-широко покритие на "преди пробива" идеята.)
# (07.10, по молба "искам още стратегии разтърси се" - след като и
# комбинациите от първите 11 не издържаха извън-извадковия тест, добавени
# 2 МЕХАНИЧНО различни: RSI bullish divergence (момeнтум изоставане, не
# волатилност/обем) и higher-low base (форма на дъната, не ширина на
# диапазона) - различни "сетивни органи", не просто вариации на
# съществуващите.)
# (07.10, по молба "давай други да пробваме давай продължаваме" - след
# смесен извън-извадков резултат за pocket_pivot+volume_before_breakout
# (max_loss намалението се повтори и в двата периода, но win-rate/spike
# предимството - не), добавени 3 НОВИ семейства, никое от които не прилича
# механично на предишните 15: gap_up_hold (ново измерение данни - OPEN
# спрямо предходен CLOSE, не само close/volume серии), adx_trend_strength
# (Wilder DMI/ADX - сила на съществуващ тренд, trend-following, не
# volatility-contraction/breakout-anticipation) и macd_bullish_cross
# (момeнтум-кросоувър на EMA, различно от RSI дивергенцията).)
# (07.10, по молба "давай още тогава" - след като извън-извадковият тест
# показа, че vcp_contraction/three_bar_tight намаляват max_loss надеждно,
# но НЕ предсказват посоката по-добре от random_baseline, добавени 3 ОЩЕ
# нови семейства: stochastic_oversold_turn (позиция в диапазона, не
# close-промяна като RSI), ad_line_divergence (обемно-претеглена позиция
# в диапазона - различен индикатор от OBV), и pullback_to_rising_ma -
# ПЪРВАТА стратегия тук, която изисква акцията ВЕЧЕ да е в установен
# тренд (купи дръпването), вместо да лови акция още в основа преди тренда
# като всички останали 17.)
# КРЪГ 10 (07.10, по молба "искам да тестваме още стратегии можем ли да го
# правим едновременно докато този бот работи" - докато donchian_breakout/
# fib_retracement_bounce вече работят на живо, тук продължаваме търсенето
# паралелно, напълно независимо от живия бот): добавени 3 НОВИ семейства,
# никое механично сходно с предишните 26: supertrend_flip (ATR-базирана
# следваща тренда линия - различна математика от Parabolic SAR),
# aroon_up_cross (измерва ВРЕМЕ от последен връх/дъно, не магнитуд/обем -
# съвсем нов "сетивен орган") и pivot_point_breakout (класически floor-
# trader pivot от ЕДИН предходен ден, много по-реактивен от Donchian-овия
# rolling прозорец).
# РЕЗУЛТАТ от КРЪГ 10: и трите НЕ показаха предимство пред random_baseline
# (supertrend_flip дори забележимо по-зле; pivot_point_breakout
# практически идентичен с random - сигналът е твърде хлабав/чест, 1175
# сигнала). Не си заслужаваше extra out-of-sample тест.
# КРЪГ 11 (07.10, по молба "давай още стратегии"): добавени 3 НОВИ
# семейства: keltner_breakout (ATR-базирани ленти около EMA - различно от
# Bollinger/std и от Donchian/сурови екстремуми), cci_extreme_reversal
# (Commodity Channel Index - средно АБСОЛЮТНО отклонение, различна
# математика от RSI/Stochastic) и three_white_soldiers (3-свещна
# continuation фигура, за разлика от bullish_engulfing_reversal, която е
# само 2-свещен единичен обрат).
# РЕЗУЛТАТ от КРЪГ 11: keltner_breakout по-зле от random; cci_extreme_
# reversal - лек max_loss ефект, без посочна предимство; three_white_
# soldiers - само 15 сигнала, твърде малка извадка за извод. Никое не
# мина първия бар.
# КРЪГ 12 (07.10, по молба "айде още един път ама потърси повече сега
# давай" - този път НЕ случаен избор на индикатор, а целенасочено
# изведени от ОБЩОТО между двете работещи стратегии (donchian_breakout/
# fib_retracement_bounce): и двете са ПОТВЪРДЕН пробив на РЕАЛНО
# структурно ценово ниво, не просто "затишие преди бурята"): добавени 3
# нови - darvas_box_breakout (по-СТРОГ вариант на пробив, изисква реално
# "задържала" консолидационна кутия, не просто rolling N-дневен връх),
# resistance_flip_retest (стара съпротива става подкрепа - "polarity
# principle", реално историческо ниво вместо Fibonacci % съотношение) и
# donchian_breakout_long (изолиран тест: СЪЩАТА вече валидирана
# donchian_breakout логика, само с много по-дълъг lookback - 100 дни
# вместо 20 - за да проверим дали по-дългият хоризонт помага или вреди).
# РЕЗУЛТАТ от КРЪГ 12: darvas_box_breakout леко по-добър от random на
# 3d/5d (НО само 24 сигнала, обръща се зле на 10d - твърде тънка извадка
# за доверие); resistance_flip_retest ясно по-зле; donchian_breakout_long
# по-слаб от оригиналния 20-дневен - потвърждава, че текущата настройка в
# живия бот си остава най-добрият избор.
# КРЪГ 13 (07.10, по молба "давай продължаваме"): добавени 3 нови -
# flag_breakout (continuation фигура: доказан предходен "pole" ход +
# тясна консолидация + пробив, по-строго от vcp_contraction),
# double_bottom_breakout (класическа "W" обратна фигура - neckline пробив
# от РЕАЛНА геометрия, не единично ниво) и obv_leads_price (обемният
# поток прави нов връх ПРЕДИ самата цена - различно от quiet_accumulation,
# която изисква плоска цена).
# РЕЗУЛТАТ от КРЪГ 13: всичките 3 самостоятелно по-зле или еквивалентни на
# random_baseline (obv_leads_price и double_bottom_breakout - median_ret
# по-нисък от random на всички хоризонти; flag_breakout - само 9 сигнала,
# без значение). НО: комбинацията fib_retracement_bounce+obv_leads_price
# (n=73, т.е. и двата сигнала в същия ден) показва win_rate ~48-52% на
# 3d/5d/10d (срещу 37-38% random И срещу 41-42% самия fib_retracement_
# bounce), median_ret положителен на всички 3 хоризонта (+0.65/0/+1.44%,
# докато самия fib е -0.87/-1.14/-2.46%), и доста по-малък max_loss
# (-44/-58/-68% срещу -86/-89/-93% за самия fib). Интересно, но n=73 е
# над прага за доверие (25-30), но ПОД прага "стотици-хиляди", който имаха
# donchian_breakout/fib_retracement_bounce преди да влязат на живо - за
# сега само "следи се", НЕ готово за живия бот без извън-извадков тест.
#
# ИЗВЪН-ИЗВАДКОВ ТЕСТ на fib_retracement_bounce+obv_leads_price
# (--days 250 --offset-days 250, напълно независим по-ранен прозорец):
# НЕ издържа - на 5д win_rate пада ПОД random_baseline (44.1% срещу 46.6%),
# median_ret отрицателен на 5д/10д (-0.51%/-0.74%). Класически multiple-
# testing фалшив позитив, същия модел като bollinger_squeeze+three_bar_
# tight и ichimoku_kijun_cross по-рано. ЕДИНСТВЕНОТО, което се повтори
# стабилно в двата независими прозореца: намалението на max_loss (-60/-40/
# -30% извън извадката срещу -93/-99/-99% за random там) - полезно само
# като риск филтър върху съществуваща аларма, НЕ като нов самостоятелен
# сигнал за вход. НЕ се добавя към живия бот. (Положителна новина отделно:
# самия fib_retracement_bounce потвърди стабилно предимство в win_rate и
# в двата независими прозореца, дори без sub-$0.05 тикерите - допълнително
# потвърждение на вече направения избор за живия бот.)
# КРЪГ 14 (07.10, по молба "давай продължаваме"): добавени 3 нови -
# hammer_reversal (ПЪРВАТА едносвещна формация тук - за разлика от
# bullish_engulfing_reversal 2 свещи и three_white_soldiers 3 свещи),
# cmf_turn_positive (Chaikin Money Flow - ОГРАНИЧЕН осцилатор, различен от
# кумулативните OBV/A-D Line които растат неограничено с времето) и
# near_high_volume_build (умишлено БЕЗ пробив - цената Е близо до върха,
# но ОЩЕ не го е пробила, докато обемът се трупа - буквално "преди да
# избухне", за разлика от всички breakout стратегии тук, които хващат
# деня НА пробива).
# РЕЗУЛТАТ от КРЪГ 14 (вътре в извадката): hammer_reversal по-зле от
# random на всички хоризонти - класическо "хващане на падащ нож", не
# обрат (очаквано механично за единична свещ насред спад). cmf_turn_
# positive - смесено, по-добър win_rate на 3д/10д, но по-лоша медиана на
# 5д/10д, без ясно предимство. НАЙ-ОБЕЩАВАЩО: near_high_volume_build
# (n=45, без sub-nickel n=39) - win_rate 47-59% на всички хоризонти
# (срещу 35-40% random), медианата положителна/нулева навсякъде (срещу
# -1.3/-1.5/-3.7% random), И max_loss ДРАСТИЧНО по-малък (-19/-21/-26%
# срещу -95/-93/-99% random) - и в двата сета (пълен и без sub-nickel).
# Логично обяснимо - сигналът е анти-ципационен (цената ОЩЕ не е
# пробила), значи по дефиниция по-малко "гонене на връх". Чака извън-
# извадков тест преди да се мисли за живо.
#
# ИЗВЪН-ИЗВАДКОВИ ТЕСТОВЕ на near_high_volume_build (две независими
# 250-дневни прозорци, --offset-days 250 и --offset-days 500):
# Прозорец 1 (offset 250, n=56): win_rate 48/52/64% (срещу 44/47/48%
# random), медиана положителна на 5д/10д (+0.60/+7.38% срещу 0.00/-0.24%
# random), max_loss -15/-17/-21% (срещу -93/-99/-99% random) - ЧИСТО
# предимство навсякъде.
# Прозорец 2 (offset 500, n=26 - малка извадка, внимавай): win_rate
# 54/39/50% (срещу 49/43/42% random) - по-добър на 3д/10д, НО по-слаб на
# 5д; медианата също смесена (+2.0/-1.7/-0.5% срещу 0.0/-0.75/-2.1%
# random) - по-добра на 3д/10д, по-зле на 5д. max_loss пак ясно по-малък
# (-26/-18/-29% срещу -93/-90/-90% random).
# ОБОБЩЕНИЕ (3 независими прозореца общо - оригиналният + двата offset):
# max_loss предимството издържа 3/3 пъти стабилно - най-надеждният ефект
# на цялата стратегия (сигналът е антиципационен, не "гони връх", така
# че логично носи по-малък опашен риск). Win_rate/медиана издържат ясно
# в 2/3 прозореца, по-шумно в третия (малка извадка, n=26). Чака
# решение на потребителя дали да влезе на живо (07.10).
# КРЪГ 15 (07.10, по молба "дай още да пробваме"): добавени 3 нови -
# mfi_oversold_turn (Money Flow Index - обемно претеглено RSI, различна
# математика от cmf_turn_positive/RSI/CCI/stochastic), morning_star_
# reversal (3-свещна ОБРАТНА формация - за разлика от three_white_
# soldiers, което е CONTINUATION) и atr_expansion_breakout (обратната
# идея на ВСИЧКИ "свиване на волатилността" стратегии тук - внезапно
# РАЗШИРЕНИЕ на диапазона с посока, не свиване преди пробив).
# РЕЗУЛТАТ от КРЪГ 15: трите по-зле от random на практика навсякъде.
# mfi_oversold_turn (n=186) - по-нисък win_rate и по-лоша медиана на
# всички хоризонти. morning_star_reversal (n=28, малка извадка) - също
# по-зле, особено на 5д/10д. atr_expansion_breakout (n=179) - НАЙ-зле от
# трите (win_rate 20-31% срещу 35-40% random, медиана -6 до -8% срещу
# -1 до -4% random) - логично обяснимо: купуване на деня СЛЕД внезапен
# скок обикновено е купуване близо до локален връх, не начало на нов
# тренд ("гонене на вече станалото"). Нито една комбинация с тези 3 (18
# проверени) не излезе по-добра от random. Чисто отрицателен кръг.
# КРЪГ 16 (07.10, по молба "продължаваме"): добавени 3 нови -
# volume_ratio_breakout (прост Up/Down Volume Ratio - различна математика
# от OBV/CMF/MFI/A-D line), bear_power_reclaim (Elder Ray Index - свързва
# днешното low директно с EMA тренд-линия, различно от rolling max/min
# или ATR ленти) и long_term_low_rebound (СТРУКТУРНО обратната идея на
# near_high_volume_build - отскок от дългосрочно ~200-дневно дъно, вместо
# близост до връх).
# РЕЗУЛТАТ от КРЪГ 16 (вътре в извадката): bear_power_reclaim - праг
# твърде хлабав (n=4825 сигнала - практически шум, еквивалентно на
# random). volume_ratio_breakout (n=997) - по-лоша медиана от random на
# всички хоризонти. НАЙ-ОБЕЩАВАЩО: long_term_low_rebound (n=136, без
# sub-nickel n=133 - СОЛИДНА извадка, по-голяма от near_high_volume_
# build) - win_rate по-добър на всички хоризонти (особено 10д: 43%
# срещу 34% random), медиана по-добра навсякъде, И max_loss ДРАСТИЧНО
# по-малък (-26/-40/-52% срещу -95/-93/-99% random) - същия "анти-
# ципационен" профил като near_high_volume_build. Интересна комбинация
# и с volume_ratio_breakout (n=56): win_rate 54-55%, медиана +1.9/+2.0%.
#
# ИЗВЪН-ИЗВАДКОВ ТЕСТ на long_term_low_rebound (--offset-days 250,
# независим 250-дневен прозорец, n=162, без sub-nickel n=148): издържа
# ИЗКЛЮЧИТЕЛНО чисто - win_rate 47.5/54.9/65.4% (срещу 43.8/46.3/46.8%
# random), медиана положителна на 5д/10д (+1.39/+6.48% срещу 0.00/-0.61%
# random), max_loss по-малък навсякъде (-77/-78/-50% срещу -93/-99/-99%
# random), caught_20pct_spike също по-висок навсякъде (25/33/43% срещу
# 12/19/31% random). 2 от 2 независими прозореца минаха ЧИСТО на всички
# метрики - по-силно потвърждение от near_high_volume_build (където
# третият тест беше по-колеблив)...
#
# ТРЕТИ ТЕСТ на long_term_low_rebound (--offset-days 500, трети
# независим 250-дневен прозорец, n=103, без sub-nickel n=99): ОБРЪЩА
# СЕ - win_rate 45.6/37.9/37.9% (срещу 48.7/42.7/43.0% random - ПО-ЗЛЕ
# навсякъде), медианата също по-зле навсякъде (-0.4/-1.96/-2.04% срещу
# 0.0/-0.91/-1.83% random). Дори max_loss предимството - най-стабилният
# ефект в първите два прозореца - изчезва на 10д (-92% срещу -90%
# random, практически еднакво). За разлика от near_high_volume_build
# (където третият тест беше само "по-шумен", но не чисто отрицателен),
# тук третият прозорец е ЯСНО ОБРАТЕН резултат на почти всичко.
# ОБОБЩЕНИЕ (3 прозореца): 2 силно положителни, 1 ясно отрицателен -
# по-слаб общ профил от near_high_volume_build (която имаше 3/3 стабилен
# max_loss ефект, само win_rate/медианата бяха по-шумни в третия).
# Вероятно ефектът зависи от пазарния режим през конкретния период
# (двата "добри" прозореца са съседни по време, третият е по-стар и
# различен период) - НЕ се препоръчва за живо засега. Остава само като
# изследователска бележка.
# КРЪГ 17 (08.10, по молба "още тествания още стратегии"): добавени 3
# нови - golden_cross (50/200-дневен MA кросоувър - напълно различен
# ДЪЛГОСРОЧЕН времеви мащаб от всичко друго тук), pvt_new_high (като
# obv_leads_price, но претеглено с ПРОЦЕНТНАТА промяна на цената вместо
# двоичен знак) и three_inside_up (3-свещна ОБРАТНА формация, harami-
# базирана - различна от morning_star_reversal, по-строго потвърждение).
# РЕЗУЛТАТ от КРЪГ 17: golden_cross - 0 сигнала в 250-дневния прозорец
# (очаквано - твърде рядък/бавен сигнал за този тестов хоризонт, нужни са
# по-дълги данни за честна преценка). pvt_new_high (n=342) - ясно по-зле
# от random на всички хоризонти. three_inside_up (n=25, точно на прага
# за доверие) - изглежда ОТЛИЧНО на пръв поглед (win_rate 52-56% срещу
# 35-39% random, медиана положителна навсякъде, max_loss -18/-22/-38%
# срещу -95/-93/-99% random), ПОТВЪРДЕНО и без sub-nickel тикерите
# (същите 25 сигнала). НО n=25 е твърде малка извадка за доверие сама по
# себе си (същия праг като darvas_box_breakout/three_white_soldiers,
# които също изглеждаха добре на тънка извадка) - не се пуска на живо
# без извън-извадков тест, и дори тогава извадката там вероятно пак ще
# е малка заради рядкостта на формацията.
# КРЪГ 18 (08.10, по молба "продължаваме ако има някоя която ти хареса
# правим още тестове на нея"): добавени 3 нови - williams_r_oversold_turn
# (Williams %R - ПРОСТА, НЕизгладена позиция-в-диапазона, различна от
# stochastic_oversold_turn и cci_extreme_reversal по формулата, не по
# идеята), cup_handle_breakout (чаша с дръжка - МЕХАНИЧНО най-сложната
# геометрична фигура тук, комбинира дълбочина на корекция + плитка
# дръжка + обемно потвърждение на пробива) и accumulation_day_count
# (броене на чести силни обемни дни в прозорец - ЧЕСТОТЕН сигнал,
# различен от всички единично-дневни или съотношителни сигнали досега).
# РЕЗУЛТАТ от КРЪГ 18: чисто отрицателен кръг (като КРЪГ 15).
# williams_r_oversold_turn (n=638, достатъчна извадка) - по-зле от random
# на win_rate и медианата на ВСИЧКИ хоризонти (3/5/10д); нито една от 15
# проверени комбинации с други стратегии не показа убедителен ръб (всички
# медиани отрицателни, подобни или по-зле от random). cup_handle_breakout
# - 0 сигнала в 250-дневния прозорец (очаквано - твърде рядка/строга
# геометрична фигура за този хоризонт, нужни са по-дълги данни).
# accumulation_day_count - n=1 (прагът min_count=6 при vol_mult=1.5 е
# твърде строг за тази извадка/период - практически неизползваем сигнал
# както е конфигуриран). Никоя от трите не се препоръчва по-нататък.
# КРЪГ 19 (08.10, по молба "давай продължаваме"): добавени 3 нови -
# inside_bar_breakout (класическа 2-свещна mother/inside bar фигура -
# директно сравнение на 2 диапазона, най-простото механично тук досега),
# linreg_channel_breakout (регресионен канал - различна математика от
# Bollinger/Keltner/Donchian) и chaikin_oscillator_cross (EMA-разлика
# на A/D Line, различна от CMF-ratio и от необработените OBV/PVT линии).
# РЕЗУЛТАТ от КРЪГ 19: трети пореден чисто отрицателен кръг (като 15 и
# 18). inside_bar_breakout (n=177), linreg_channel_breakout (n=406) и
# chaikin_oscillator_cross (n=282) - всичките по-зле от random на
# win_rate и медианата на ВСИЧКИ хоризонти (3/5/10д), потвърдено и без
# sub-nickel тикерите. Проверени 12-те най-големи комбинации - никоя не
# показа предимство (всички медиани отрицателни, повечето по-зле от
# самостоятелните стратегии). Никоя от трите не се препоръчва по-нататък.
# КРЪГ 20 (08.10, по молба "давай продължаваме"): добавени 3 нови -
# up_down_volume_ratio_surge (up-vol/down-vol съотношение - различно от
# OBV/PVT кумулативни линии и от CMF/Chaikin intraday-позиция),
# momentum_acceleration (ROC-то САМО се ускорява строго монотонно, а не
# просто праг/ниво - втора производна на цената) и vwap_reclaim (rolling
# обемно-претеглена средна, различна тежест от проста/EMA MA).
# РЕЗУЛТАТ от КРЪГ 20: самостоятелно всичките 3 са слаби/в рамките на
# шума спрямо random (медианите им леко по-зле на всички хоризонти).
# НО откритие при комбинациите: fib_retracement_bounce+momentum_
# acceleration (n=237) изглежда като КАЧЕСТВЕН ФИЛТЪР върху вече
# живата fib_retracement_bounce - win_rate_3d 43.0% (срещу 41.7% само
# fib), max_loss_3d само -50.69% (срещу -85.68% само fib - значимо
# по-нисък риск), win_rate_10d 40.5% (срещу 36.7% само fib), median_10d
# -2.54% (срещу -2.71% само fib). Най-интересното откритие от КРЪГ 20 -
# кандидат за извън-извадков тест (--offset-days) като ДОПЪЛНИТЕЛЕН
# филтър върху fib_retracement_bounce, не като самостоятелна стратегия.
# up_down_volume_ratio_surge и vwap_reclaim - без силни комбинации,
# не се препоръчват по-нататък.
# OFFSET-250 тест на fib_retracement_bounce+momentum_acceleration
# (n=195, независим по-стар прозорец): СМЕСЕН резултат. max_loss_3d
# ефектът СЕ ПОВТОРИ стабилно (-40.22% за комбото срещу -96.51% само
# fib - дори по-добро от първия тест!) - това изглежда реален ефект
# на двата независими прозореца. НО win_rate/медианата подобрението
# от първия тест НЕ се повтори - в този прозорец самата fib_
# retracement_bounce е по-добра от комбото на win_rate (46.8% срещу
# 43.6% на 3д, 48.2% срещу 47.2% на 10д) и медианата (почти без разлика
# но леко в полза на fib сама). Прилича на near_high_volume_build
# прецедента - max_loss ефектът стабилен, win_rate/медианата шумни.
# Нужен е 3-ти тест (--offset-days 500) преди окончателна преценка.
# OFFSET-500 (3-ти, най-стар независим прозорец, n=128): max_loss
# ефектът СЕ ПОВТОРИ и тук, 3/3 стабилно - комбото е по-добро от fib
# сама на ВСИЧКИ хоризонти (max_loss_3d -17.2% срещу -35.99% само fib,
# max_loss_5d -24.01% срещу -32.35%, max_loss_10d -29.33% срещу
# -40.63%). win_rate/медианата останаха шумни и в тоя прозорец (разни
# посоки на разни хоризонти). ОБОБЩЕНИЕ (3 прозореца): max_loss-
# намалението на fib_retracement_bounce+momentum_acceleration филтъра
# е СТАБИЛНО 3/3 - същия клас откритие като near_high_volume_build.
# win_rate/медианата - шумни, не се разчита на тях. Това е ВТОРИЯТ
# напълно тестван (3 прозореца) кандидат за живия бот - като ДОПЪЛНИТЕЛЕН
# риск-филтър върху вече живата fib_retracement_bounce, не като нова
# самостоятелна стратегия. Чака решение на потребителя.
# КРЪГ 21 (08.10, по молба "продължаваме да търсим", след разговор за
# целева win rate ~80% - обяснено на потребителя, че това е много
# висока летва, но пробваме по-СТРОГИ/КОМПОЗИТНИ сигнали вместо прост
# единичен индикатор, за по-висока избирателност): добавени 3 нови,
# всяка е AND-комбинация от НЯКОЛКО условия в ЕДНА функция (а не 2
# отделни стратегии комбинирани после, както при fib+momentum) -
# triple_confirmation_breakout (пробив + обем + дългосрочен тренд-
# филтър едновременно), oscillator_confluence_oversold_turn (RSI +
# Stochastic + Williams %R ВСИЧКИТЕ обръщат нагоре в същия ден) и
# quality_pullback_entry (дългосрочен тренд + плитка пауза близо до
# 20-дневна MA + свиващ се обем + бичи ден - четири условия).
# РЕЗУЛТАТ от КРЪГ 21: oscillator_confluence_oversold_turn - изненадващо
# МНОГО сигнали (n=598, не рядко както очаквах - явно RSI/Stochastic/
# Williams %R са силно корелирани и се "съгласяват" често) И чисто
# отрицателен резултат на всички хоризонти - НЕ се препоръчва.
# quality_pullback_entry (n=49) - по-нисък win_rate от random, НО
# значимо по-нисък max_loss (-50.7% срещу -95.2% на 3д) и почти 0%
# caught_20pct_spike - "тих/нискорисков" профил, не отговаря на целта
# за по-висок win rate. triple_confirmation_breakout (n=71) - НАЙ-
# ИНТЕРЕСНОТО тук: win_rate_3d 47.9% (срещу 36.8% random, +11пп!),
# win_rate_10d 38.0% (срещу 34.1%), caught_20pct_spike_3d 21.1% (срещу
# 14.1%) - избирателността помогна поне тук. win_rate_5d по-слаб
# (36.6% срещу 39.0%) и медианата остава отрицателна навсякъде, но
# профилът е достатъчно интересен за извън-извадков тест по
# установения протокол (--offset-days 250/500), преди да се вярва.
# OFFSET-250 резултат (n=100, независим по-стар прозорец): МНОГО силно
# потвърждение - дори по-добро от първия тест! win_rate 48.0/50.0/56.0%
# (3/5/10д) срещу random 43.8/46.3/46.8% (+4.2/+3.7/+9.2пп), медианата
# положителна на 5д и 10д (0.18%/3.60%) срещу random (0.00%/-0.61%),
# max_loss драматично по-нисък на ВСИЧКИ хоризонти (-32.4/-48.4/-77.9%
# срещу -93.3/-98.9/-98.9%), caught_20pct_spike двойно по-добър
# (25.0/54.0% срещу 12.3/30.8% на 3д/10д). Потвърдено и без sub-nickel
# тикерите (n=99, същите числа). Това е НАЙ-СИЛНАТА находка на цялата
# сесия засега - всички метрики в една посока в 2 независими прозореца.
# Нужен е 3-ти тест (--offset-days 500) за пълно потвърждение по
# установения протокол, но изгледите са много добри.
# OFFSET-500 (3-ти, най-стар прозорец, n=62): win_rate ефектът, който
# изглеждаше толкова силен в предните 2 теста, ТУК ИЗЧЕЗНА напълно -
# 48.4/41.9/40.3% срещу random 48.7/42.7/43.0% (практически еднакво,
# дори леко по-зле на 5д/10д). Медианата също еднаква/по-зле. Същата
# история като long_term_low_rebound - 2 "добри" прозореца, 3-тият
# разкрива че ефекта не е стабилен. НО max_loss ефектът СЕ ПОВТОРИ и
# тук стабилно 3/3 (-23.1/-26.9/-29.3% срещу -93.3/-90.0/-90.0% random)
# - същия клас свойство като near_high_volume_build и fib+momentum
# филтъра. ОБОБЩЕНИЕ (3 прозореца): по-високият win_rate, който е
# ИМЕННО целта на потребителя тук, НЕ Е НАДЕЖДЕН (1 от 3 прозореца
# показа силен ефект, 1 умерен, 1 нулев/обратен). max_loss-намалението
# е стабилно, но не отговаря на конкретната цел за по-висок win rate.
# НЕ се препоръчва като начин за достигане на win rate ~80% - остава
# само като евентуален трети риск-филтър (като fib+momentum), не
# като решение на самата цел.
# КРЪГ 22 (08.10, по молба "дай да тестваме още стратегии", след
# приемане че win rate ~80% е нереалистична цел - връщане към общо
# търсене): добавени 3 нови - doji_breakout (форма на свещта - малко
# тяло спрямо широк диапазон, различно от inside_bar_breakout, който е
# контеймънт на диапазон), vwap_extreme_deviation_reversion (екстремно
# отклонение от VWAP, различно от простото пресичане на vwap_reclaim)
# и key_reversal_day (нов минимум интрадей + затваряне над вчера -
# чисто ценова формация, без изисквания за форма/обем, различна от
# hammer_reversal и capitulation_reversal).
# РЕЗУЛТАТ от КРЪГ 22: всичките 3 в рамките на шума/леко по-зле от
# random. doji_breakout (n=175) - чисто отрицателен на всички метрики.
# vwap_extreme_deviation_reversion (n=1238, много сигнали) - медианата
# и max_loss по-зле от random, caught_20pct_spike_10d леко по-добър
# (34.6% срещу 30.1%), но не достатъчно за отделна препоръка. key_
# reversal_day (n=172) - win_rate близо до random, НО max_loss значимо
# по-нисък (-61.3% срещу -95.2% на 3д) - подобен "нискорисков" профил
# като quality_pullback_entry от кръг 21. Проверени и топ-12 комбинации
# с vwap_extreme_deviation_reversion - никоя не показа предимство.
# Никоя от трите не се препоръчва за извън-извадков тест.
# КРЪГ 23 (08.10, по молба "продължаваме"): добавени 3 нови -
# adx_di_crossover (+DI/-DI пресичане по Wilder - различно от adx_
# trend_strength, който е ниво на самия ADX), stealth_volume_anomaly
# (изолирана обемна аномалия без ценово изискване - огромен обем при
# почти никаква промяна в цената) и nvi_new_high (Negative Volume
# Index - кумулативна линия, обновявана само в тихите/нискообемни дни,
# различна конструкция от OBV/PVT/ADL).
# РЕЗУЛТАТ от КРЪГ 23: adx_di_crossover (n=434) - в рамките на шума,
# без предимство. nvi_new_high (n=110) - близо до random, леко по-зле.
# stealth_volume_anomaly (n=71) - ИНТЕРЕСЕН "асиметричен" профил:
# по-нисък win_rate (29.6/32.4/28.2% срещу 36.8/39.1/33.9% random), НО
# медианата е РОВНО 0.00% на всички хоризонти (не 0 сигнала - това е
# реалната медиана), max_loss значимо по-нисък (-84/-70/-85% срещу
# -95/-93/-99%), и caught_20pct_spike_10d 38.0% срещу 30.2% random -
# хваща повече големи скокове. Без sub-nickel тикерите (n=42) картината
# е ОЩЕ ПО-ДОБРА - win_rate_3d 40.5% (срещу 36.9% random), max_loss_3d
# само -34.3% (срещу -74%) - т.е. ефектът не е от junk тикерите.
# Прилича на профила, който обясних на потребителя по-рано - нисък win
# rate, но асиметрична изплата (малки загуби, по-чести големи печалби).
# Кандидат за извън-извадков тест (--offset-days), макар n да е малко.
#
# --offset-days 250 (n=46, 2-ро независимо прозорче): ефектът се ПОТВЪРЖДАВА
# и дори изглежда по-силен. win_rate_3d леко по-нисък (41.3% срещу 43.8%
# random), НО win_rate_5d/10d вече по-ВИСОК от random (50.0/50.0% срещу
# 46.0/46.7%). median_ret вече положителна и по-добра от random на 5д/10д
# (0.07/0.47% срещу -0.10/-0.61%). max_loss пак значимо по-нисък на всички
# хоризонти (-80/-83/-87% срещу -93/-99/-99%). caught_20pct_spike по-висок
# на ВСИЧКИ хоризонти (26.1/30.4/41.3% срещу 12.7/19.2/31.2% random) - това
# е най-силният и най-постоянен сигнал от двата прозорца. Без sub-nickel
# (n=37) картината е ОЩЕ ПО-ДОБРА - win_rate 48.6/56.8/59.5% (срещу 44.0/
# 46.7/46.5% random - вече по-висок на ВСИЧКИ хоризонти), median_ret
# положителна и по-добра навсякъде, max_loss пак по-нисък, spike-catching
# пак по-висок. И двата прозорца съгласни по max_loss (по-нисък) и
# caught_20pct_spike (по-висок) - двете "асиметрични" метрики, на които се
# крепи цялата теза за тази стратегия. win_rate посоката не е консистентна
# между прозорците (по-нисък в 1-то, по-висок в 2-то), но никъде катастрофа.
# Чака 3-то прозорче (--offset-days 500) преди финална преценка - по
# установения протокол тази сесия (виж triple_confirmation_breakout и
# long_term_low_rebound - и двете обърнаха посока точно на 3-тия тест).
#
# --offset-days 500 (n=19, 3-то независимо прозорче - МНОГО малка извадка,
# под прага на доверие ~25-30 сигнала): win_rate и median_ret вече ОТНОВО
# по-ЛОШИ от random (21-32% срещу 43-48%, median -3/-5/-15% срещу 0/-1/-2%) -
# т.е. при трите прозорца win_rate посоката е непостоянна (по-зле, по-добре,
# по-зле) - НЕ е надеждна, както при triple_confirmation_breakout. НО
# max_loss пак по-нисък на всички хоризонти (-20/-22/-50% срещу -93/-90/
# -90%) и caught_20pct_spike пак по-висок (26/37/37% срещу 11/19/31%) - тези
# ДВЕ метрики се потвърдиха 3 от 3 прозорца, последователно, без изключение.
#
# ФИНАЛЕН ИЗВОД (3 прозорца): stealth_volume_anomaly НЕ помага за по-висок
# win_rate (целта на потребителя за ~80%) - тази част от сигнала е шум.
# НО "асиметричната" част от тезата (по-малки максимални загуби + по-добро
# улавяне на големи скокове) се държи стабилно и в трите независими
# прозорца - засега единствената метрика в цялата сесия с толкова чиста
# 3/3 репликация. Евентуална употреба: НЕ като самостоятелен сигнал за
# вход, а като риск-ограничител (по-малък stop loss / по-внимателно
# излизане), ако потребителят реши да го добави - решението чака потребителя.
#
# РЕЗУЛТАТ от КРЪГ 24 (3 ОРИГИНАЛНИ композитни идеи, не учебникови
# индикатори, по молба "не търси само известни стратегии"):
#
# closing_strength_streak (n=201) - по-слаб от random на почти всички
# метрики (win_rate 31/28/31% срещу 37/39/34%, caught_spike 8/13/26%
# срещу 15/20/30%) - чист негативен резултат, не се препоръчва.
#
# range_compression_volume_asymmetry (n=1280, много сигнали) - леко по-зле
# от random на повечето метрики, без ясно предимство - не се препоръчва.
#
# volume_climax_reversal_2day (n=100) - ОБЕЩАВАЩ резултат: win_rate
# по-ВИСОК от random на ВСИЧКИ хоризонти (42/46/43% срещу 37/39/34%),
# median_ret по-добра, max_loss значимо по-нисък (-76/-80/-87% срещу
# -95/-93/-99%), и caught_20pct_spike забележимо по-висок (29/37/46%
# срещу 15/20/30% random). Без sub-nickel тикерите (n=83) резултатът се
# ПОТВЪРЖДАВА на всички метрики (win_rate 45/46/45% срещу 37/40/34%) -
# т.е. не идва от junk тикери. Най-силният ПЪРВИ прозорец на цялата
# сесия засега. Кандидат за извън-извадков тест (--offset-days), по
# установения 3-прозоречен протокол, преди да му се вярва.
#
# --offset-days 250 (n=48, 2-ро независимо прозорче): win_rate смесен -
# по-нисък на 3д (37.5% срещу 43.8%), почти равен на 5д (45.8% срещу
# 46.0%), по-ВИСОК на 10д (52.1% срещу 46.7%). median_ret подобно смесена,
# но по-добра на 10д (1.04% срещу -0.61%). НО двете "твърди" метрики се
# ПОТВЪРЖДАВАТ силно - max_loss ОЩЕ по-нисък от прозорец 1 (-29/-33/-57%
# срещу -93/-99/-99% random - най-голямата разлика в цялата сесия) и
# caught_20pct_spike пак по-висок на всички хоризонти (19/29/44% срещу
# 13/19/31%). Без sub-nickel (n=46) - същата картина, потвърдено. И двата
# прозорца засега съгласни по max_loss и caught_spike - чака 3-ти тест
# (--offset-days 500) преди финална преценка.
#
# --offset-days 500 (n=36, 3-то и последно независимо прозорче): win_rate
# почти равен/леко по-добър от random на всички хоризонти (47/53/47%
# срещу 48/43/43%), median_ret също сравнима/по-добра. max_loss в ПЪЛНИЯ
# сет тук е изключение - приблизително равен на random (-90/-94/-91%
# срещу -93/-90/-90%), за пръв път не по-добър - вероятно 1-2 sub-nickel
# тикера с лош outlier точно в този прозорец. Но БЕЗ sub-nickel (n=32)
# картината е ЧИСТА победа на ВСИЧКИ 4 метрики и ВСИЧКИ хоризонти:
# win_rate 50/56/50% (срещу 49/43/42%), median_ret положителна и по-добра
# навсякъде, max_loss много по-нисък (-27/-30/-29% срещу -42/-42/-56%),
# caught_20pct_spike по-висок навсякъде (19/25/31% срещу 10/16/29%).
#
# ФИНАЛЕН ИЗВОД (3 прозорца): volume_climax_reversal_2day е НАЙ-СТАБИЛНАТА
# находка в цялата сесия засега. caught_20pct_spike по-висок от random в
# ВСИЧКИ 3 прозорца, без изключение. max_loss по-нисък в 2 от 3 прозорца
# в пълния сет, и в ВСИЧКИ 3 прозорца след премахване на sub-nickel junk
# тикерите (т.е. ефектът не е от junk тикерите - дори напротив, те го
# прикриват). win_rate/median_ret, за разлика от повечето други кандидати
# тази сесия, тук НЕ се обръщат в противоположна посока между прозорците -
# остават стабилно около или над random във всичките 3. Не достига целта
# на потребителя от ~80% win rate (никъде не надвишава ~53%), но е
# реалистичен, повторяем кандидат за живия бот - или като самостоятелна
# нова стратегия, или най-малкото като риск-филтър. Решението чака
# потребителя.
STRATEGIES = {
    "pocket_pivot": signal_pocket_pivot,
    "nr7_squeeze": signal_nr7_volatility_squeeze,
    "bollinger_squeeze": signal_bollinger_squeeze,
    "quiet_accumulation": signal_quiet_accumulation,
    "volume_before_breakout": signal_volume_before_breakout,
    "ttm_squeeze": signal_ttm_squeeze,
    "volume_dry_up": signal_volume_dry_up,
    "three_bar_tight": signal_three_bar_tight,
    "ma_convergence_coil": signal_ma_convergence_coil,
    "vcp_contraction": signal_vcp_contraction,
    "relative_strength_quiet": signal_relative_strength_quiet,
    "rsi_bullish_divergence": signal_rsi_bullish_divergence,
    "higher_low_base": signal_higher_low_base,
    "capitulation_reversal": signal_capitulation_reversal,
    "gap_up_hold": signal_gap_up_hold,
    "adx_trend_strength": signal_adx_trend_strength,
    "macd_bullish_cross": signal_macd_bullish_cross,
    "stochastic_oversold_turn": signal_stochastic_oversold_turn,
    "ad_line_divergence": signal_ad_line_divergence,
    "pullback_to_rising_ma": signal_pullback_to_rising_ma,
    "ichimoku_kijun_cross": signal_ichimoku_kijun_cross,
    "force_index_reclaim": signal_force_index_reclaim,
    "bullish_engulfing_reversal": signal_bullish_engulfing_reversal,
    "donchian_breakout": signal_donchian_breakout,
    "parabolic_sar_flip": signal_parabolic_sar_flip,
    "fib_retracement_bounce": signal_fib_retracement_bounce,
    "supertrend_flip": signal_supertrend_flip,
    "aroon_up_cross": signal_aroon_up_cross,
    "pivot_point_breakout": signal_pivot_point_breakout,
    "keltner_breakout": signal_keltner_breakout,
    "cci_extreme_reversal": signal_cci_extreme_reversal,
    "three_white_soldiers": signal_three_white_soldiers,
    "darvas_box_breakout": signal_darvas_box_breakout,
    "resistance_flip_retest": signal_resistance_flip_retest,
    "donchian_breakout_long": signal_donchian_breakout_long,
    "flag_breakout": signal_flag_breakout,
    "double_bottom_breakout": signal_double_bottom_breakout,
    "obv_leads_price": signal_obv_leads_price,
    "hammer_reversal": signal_hammer_reversal,
    "cmf_turn_positive": signal_cmf_turn_positive,
    "near_high_volume_build": signal_near_high_volume_build,
    "mfi_oversold_turn": signal_mfi_oversold_turn,
    "morning_star_reversal": signal_morning_star_reversal,
    "atr_expansion_breakout": signal_atr_expansion_breakout,
    "volume_ratio_breakout": signal_volume_ratio_breakout,
    "bear_power_reclaim": signal_bear_power_reclaim,
    "long_term_low_rebound": signal_long_term_low_rebound,
    "golden_cross": signal_golden_cross,
    "pvt_new_high": signal_pvt_new_high,
    "three_inside_up": signal_three_inside_up,
    "williams_r_oversold_turn": signal_williams_r_oversold_turn,
    "cup_handle_breakout": signal_cup_handle_breakout,
    "accumulation_day_count": signal_accumulation_day_count,
    "inside_bar_breakout": signal_inside_bar_breakout,
    "linreg_channel_breakout": signal_linreg_channel_breakout,
    "chaikin_oscillator_cross": signal_chaikin_oscillator_cross,
    "up_down_volume_ratio_surge": signal_up_down_volume_ratio_surge,
    "momentum_acceleration": signal_momentum_acceleration,
    "vwap_reclaim": signal_vwap_reclaim,
    "triple_confirmation_breakout": signal_triple_confirmation_breakout,
    "oscillator_confluence_oversold_turn": signal_oscillator_confluence_oversold_turn,
    "quality_pullback_entry": signal_quality_pullback_entry,
    "doji_breakout": signal_doji_breakout,
    "vwap_extreme_deviation_reversion": signal_vwap_extreme_deviation_reversion,
    "key_reversal_day": signal_key_reversal_day,
    "adx_di_crossover": signal_adx_di_crossover,
    "stealth_volume_anomaly": signal_stealth_volume_anomaly,
    "nvi_new_high": signal_nvi_new_high,
    "closing_strength_streak": signal_closing_strength_streak,
    "volume_climax_reversal_2day": signal_volume_climax_reversal_2day,
    "range_compression_volume_asymmetry": signal_range_compression_volume_asymmetry,
}
