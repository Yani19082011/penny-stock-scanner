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
}
