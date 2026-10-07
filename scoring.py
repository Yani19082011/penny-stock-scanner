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
(по-слабия - откат до 50-61.8% Fibonacci зона с отскок). Новата схема:

  - donchian_breakout = True   -> score = 100  (над HIGH_POTENTIAL_THRESHOLD=70
                                                 -> "ВИСОК ПОТЕНЦИАЛ" алърт)
  - fib_retracement_bounce = True (и НЕ donchian) -> score = 55
                                                 (над EXIT_THRESHOLD=40 ->
                                                 остава в watchlist, НЕ алъртва)
  - нито едното               -> score = 0     (излиза от watchlist)

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
FIB_RETRACEMENT_SCORE = 55.0
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
    elif ind.get("fib_retracement_bounce"):
        score = FIB_RETRACEMENT_SCORE
        reasons.append("Fibonacci retracement bounce: откат в 50-61.8% зона с отскок (виж strategies.py)")
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
