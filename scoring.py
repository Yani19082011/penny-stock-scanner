"""
Confluence score: комбинира техническите индикатори + news catalyst +
dilution защита в едно число 0-100. Прагът за "висок потенциал" (~25%
target) идва от backtest.py - тук е само формулата и разумни начални
тегла, които backtest-ът трябва да калибрира с реални данни, преди да се
разчита на тях за живи алърти.
"""
from dataclasses import dataclass, field
from typing import Optional

WEIGHTS = {
    "trend_up": 15,           # EMA9 > EMA20
    "above_vwap": 10,
    "orb_bullish": 20,        # пробив над opening range
    "relative_volume": 20,    # скалирано според силата на обема (виж по-долу)
    "bullish_candle": 10,
    "news_catalyst": 15,      # има скорошна новина, свързана с движението
    "rsi_not_overbought": 5,  # RSI < 75 -> все още има място за движение
    "no_dilution_filing": 5,  # без скорошен S-1/S-3/424B filing
}

# Праг, над който сигналът се маркира като "потенциал за target %" (виж config.TARGET_PROFIT_PCT)
HIGH_POTENTIAL_THRESHOLD = 70
# Праг, под който тикер отпада от watchlist-а (виж watchlist.py)
EXIT_THRESHOLD = 40


@dataclass
class ScoreResult:
    symbol: str
    score: float
    reasons: list = field(default_factory=list)
    has_catalyst: bool = False
    raw: dict = field(default_factory=dict)

    @property
    def is_high_potential(self) -> bool:
        return self.score >= HIGH_POTENTIAL_THRESHOLD and self.has_catalyst

    @property
    def should_stay_in_watchlist(self) -> bool:
        return self.score >= EXIT_THRESHOLD


def _relative_volume_points(rel_vol: Optional[float]) -> float:
    if rel_vol is None or rel_vol != rel_vol:  # NaN check
        return 0
    if rel_vol >= 5:
        return WEIGHTS["relative_volume"]
    if rel_vol >= 3:
        return WEIGHTS["relative_volume"] * 0.7
    if rel_vol >= 2:
        return WEIGHTS["relative_volume"] * 0.4
    return 0


def score_symbol(symbol: str, ind: dict, has_news_catalyst: bool, dilution_flags: dict) -> ScoreResult:
    if not ind:
        return ScoreResult(symbol=symbol, score=0, reasons=["недостатъчно данни"])

    points = 0.0
    reasons = []

    if ind.get("trend_up"):
        points += WEIGHTS["trend_up"]
        reasons.append("EMA9 > EMA20 (uptrend)")

    if ind.get("above_vwap"):
        points += WEIGHTS["above_vwap"]
        reasons.append("цена над VWAP")

    if ind.get("orb_breakout") == "bullish":
        points += WEIGHTS["orb_bullish"]
        reasons.append("opening-range breakout нагоре")

    rv_points = _relative_volume_points(ind.get("relative_volume"))
    if rv_points:
        points += rv_points
        reasons.append(f"relative volume x{ind.get('relative_volume'):.1f}")

    if ind.get("bullish_candle"):
        points += WEIGHTS["bullish_candle"]
        reasons.append("силна bullish свещ")

    if has_news_catalyst:
        points += WEIGHTS["news_catalyst"]
        reasons.append("скорошна новина/catalyst")

    rsi14 = ind.get("rsi14")
    if rsi14 is not None and rsi14 < 75:
        points += WEIGHTS["rsi_not_overbought"]

    if not dilution_flags.get("has_recent_dilution_filing", False):
        points += WEIGHTS["no_dilution_filing"]
    else:
        reasons.append("⚠️ скорошен dilution filing (S-1/S-3/424B) - risk flag")

    return ScoreResult(
        symbol=symbol,
        score=round(points, 1),
        reasons=reasons,
        has_catalyst=has_news_catalyst,
        raw=ind,
    )
