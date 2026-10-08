"""
Confluence score: превръща дневните сигнали от indicators.compute_daily_signals
(виж там за пълния контекст) в едно число 0-100, плюс dilution защита.

ПРОМЯНА (07.10, по изрична молба "давай искам това да е главната стратегия
махни старата"): старата версия тук сумираше точки от 7-8 intraday
индикатора (EMA/VWAP/ORB/relative volume/bullish свещ/news catalyst/RSI) с
тегла, които НИКОГА не бяха систематично backtest-вани. Сега, след 9 кръга
строг backtest (виж strategy_backtest.py), имаме само 2 дневни сигнала с
реално доказано, повтарящо се предимство: `donchian_breakout` (по-силния -
хваща самия пробив на 20-дневен връх на обем) и `fib_retracement_bounce`
(по-слабия - откат до 50-61.8% Fibonacci зона с отскок).

ПРОМЯНА (08.10, по изрична молба "айде да решим за бота оправи кода със
новите стратегии" - след 24 кръга допълнителен backtest, пълна история в
strategies.py): добавени `near_high_volume_build` и `volume_climax_
reversal_2day` - и двата 3-прозоречно (--offset-days 250/500) валидирани,
но НИТО ЕДИН с win_rate достатъчно силен/надежден, за да заслужи същото
доверие като donchian_breakout (виж strategies.py за пълните числа - никъде
win_rate > ~65%, а при near_high_volume_build третият прозорец е по-шумен).
Затова влизат на СЪЩОТО ниво като fib_retracement_bounce - watchlist, не
директен "ВИСОК ПОТЕНЦИАЛ" алърт. Новата схема:

  - donchian_breakout = True   -> score = 100  (над HIGH_POTENTIAL_THRESHOLD=70
                                                 -> "ВИСОК ПОТЕНЦИАЛ" алърт)
  - fib_retracement_bounce ИЛИ near_high_volume_build ИЛИ
    volume_climax_reversal_2day = True (и НЕ donchian)  -> score = 55
                                                 (над EXIT_THRESHOLD=40 ->
                                                 остава в watchlist, НЕ алъртва)
  - нито едното               -> score = 0     (излиза от watchlist)

`momentum_acceleration` НЕ влиза в score-а - 3-прозоречният тест показа
стабилно (3/3) по-нисък max_loss САМО когато се комбинира с
fib_retracement_bounce, но НЕ показа надеждно по-висок win_rate, затова се
добавя тук единствено като ИНФОРМАТИВНА бележка към fib алърти (по-нисък
исторически риск), не като допълнителен критерий за score.

`stealth_volume_anomaly` НЕ е добавена - 3-прозоречният тест излезе
нестабилен (win_rate обърна посока във всеки прозорец, третият с n=19 -
твърде малка извадка за доверие). Вижда се в strategies.py, но не е
закачена тук.

config.HIGH_POTENTIAL_THRESHOLD(70)/EXIT_THRESHOLD(40) НЕ са променяни -
старите им стойности случайно се map-ват чисто на новата схема.

ВАЖНО: news catalyst вече НЕ е твърдо условие за "ВИСОК ПОТЕНЦИАЛ" - нито
donchian_breakout, нито fib_retracement_bounce са backtest-вани с
news-catalyst филтър, затова добавянето му сега би било непроверено
допълнително ограничение. Catalyst статус СЕ показва информативно в
reasons (за твоя преценка в email-а), но вече не блокира алърта.

ВАЖНО (запазено от 18.09 - виж историята на тази бележка): активен
S-1/S-3/424B dilution filing ВСЕ ОЩЕ спира "ВИСОК ПОТЕНЦИАЛ" алърта твърдо,
независимо от score-а - това е НЕЗАВИСИМО от коя техническа стратегия се
ползва и защитава срещу реален документиран минал инцидент (TEAD).
"""
from dataclasses import dataclass, field

import config

DONCHIAN_SCORE = 100.0
WATCHLIST_SCORE = 55.0  # fib_retracement_bounce / near_high_volume_build / volume_climax_reversal_2day
NO_SIGNAL_SCORE = 0.0


@dataclass
class ScoreResult:
    symbol: str
    score: float
    reasons: list = field(default_factory=list)
    has_catalyst: bool = False
    has_dilution_risk: bool = False
    raw: dict = field(default_factory=dict)

    @property
    def is_high_potential(self) -> bool:
        # (07.10) news catalyst вече не е твърдо условие - виж бележката
        # по-горе. Dilution hard-gate е запазен непроменен.
        return self.score >= config.HIGH_POTENTIAL_THRESHOLD and not self.has_dilution_risk

    @property
    def should_stay_in_watchlist(self) -> bool:
        return self.score >= config.EXIT_THRESHOLD


def score_symbol(symbol: str, ind: dict, has_news_catalyst: bool, dilution_flags: dict) -> ScoreResult:
    if not ind:
        return ScoreResult(symbol=symbol, score=0, reasons=["недостатъчно данни"])

    reasons = []

    if ind.get("donchian_breakout"):
        score = DONCHIAN_SCORE
        reasons.append("Donchian breakout: пробив над 20-дневен връх на обем (виж strategies.py)")
    else:
        watchlist_hits = []
        if ind.get("fib_retracement_bounce"):
            fib_reason = "Fibonacci retracement bounce: откат в 50-61.8% зона с отскок (виж strategies.py)"
            if ind.get("momentum_acceleration"):
                fib_reason += " + момент ускорява (историческо по-нисък max loss, виж strategies.py кръг 20)"
            watchlist_hits.append(fib_reason)
        if ind.get("near_high_volume_build"):
            watchlist_hits.append(
                "Near-high volume build: цена близо до N-дневен връх, обемът се трупа ПРЕДИ пробив (виж strategies.py)"
            )
        if ind.get("volume_climax_reversal_2day"):
            watchlist_hits.append(
                "Volume climax reversal (2-дневно потвърждение): паник обем вчера, потвърден обрат днес без нов минимум (виж strategies.py)"
            )

        if watchlist_hits:
            score = WATCHLIST_SCORE
            reasons.extend(watchlist_hits)
        else:
            score = NO_SIGNAL_SCORE

    if has_news_catalyst:
        reasons.append("(информативно) скорошна новина/catalyst - вече не се изисква за алърт")

    has_dilution_risk = bool(dilution_flags.get("has_recent_dilution_filing", False))
    if has_dilution_risk:
        reasons.append("⚠️ скорошен dilution filing (S-1/S-3/424B) - твърдо спира 'ВИСОК ПОТЕНЦИАЛ' алърта (виж is_high_potential)")

    return ScoreResult(
        symbol=symbol,
        score=score,
        reasons=reasons,
        has_catalyst=has_news_catalyst,
        has_dilution_risk=has_dilution_risk,
        raw=ind,
    )
