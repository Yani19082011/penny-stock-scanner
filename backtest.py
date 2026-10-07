"""
ОСТАРЯЛ (07.10) - този файл вече не се използва.

Преди ползваше indicators.compute_all() + scoring.score_symbol() (старата
intraday-базирана логика), които вече не съществуват в този вид - виж
indicators.py/scoring.py за новата дневна схема (donchian_breakout/
fib_retracement_bounce).

За истински backtest на стратегиите виж strategy_backtest.py - много по-
обстоен инструмент (26 стратегии, random_baseline контрол, out-of-sample
валидация с --offset-days), който всъщност доведе до избора на
donchian_breakout/fib_retracement_bounce като главна/вторична стратегия на
живия бот.

Файлът е оставен тук само като маркер/бележка, вместо да гърми с
ImportError, ако някой случайно го стартира.
"""

if __name__ == "__main__":
    print(
        "backtest.py е остарял и вече не работи - виж strategy_backtest.py "
        "за истинския backtest инструмент (26 стратегии, random_baseline "
        "контрол, out-of-sample валидация)."
    )
