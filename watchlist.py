"""
Персистентен watchlist от до config.WATCHLIST_SIZE тикера.

Логика (отговаря на изискването "5 акции, не различни всеки път"):
  - Всеки scan цикъл прескорираме и текущите watchlist тикери, и нови кандидати.
  - Тикер СЛИЗА от списъка само ако score-ът му падне под EXIT_THRESHOLD.
  - Свободните места (до WATCHLIST_SIZE) се пълнят с най-добре score-ваните
    нови кандидати.
  - Нищо не се разбърква на случаен принцип - затова получаваш "същата
    акция пак по-късно", а не нови 5 всеки път.
"""
import json
import os
from datetime import datetime, timezone

import config
from scoring import ScoreResult


def _ensure_data_dir():
    os.makedirs(config.DATA_DIR, exist_ok=True)


def load_watchlist() -> dict:
    _ensure_data_dir()
    if not os.path.exists(config.WATCHLIST_FILE):
        return {}
    try:
        with open(config.WATCHLIST_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def save_watchlist(watchlist: dict):
    _ensure_data_dir()
    with open(config.WATCHLIST_FILE, "w", encoding="utf-8") as f:
        json.dump(watchlist, f, indent=2, ensure_ascii=False)


def update_watchlist(current: dict, all_scores: list[ScoreResult]) -> tuple[dict, list, list]:
    """
    current: {symbol: {...meta}} - текущия персистиран watchlist
    all_scores: ScoreResult за ВСИЧКИ разгледани тикери тази обиколка
                (трябва да включва и вече присъстващите в current)

    Връща (нов_watchlist, добавени_symbols, свалени_symbols)
    """
    scores_by_symbol = {s.symbol: s for s in all_scores}
    now = datetime.now(timezone.utc).isoformat()

    kept = {}
    dropped = []
    for symbol, meta in current.items():
        result = scores_by_symbol.get(symbol)
        if result and result.should_stay_in_watchlist:
            meta["last_score"] = result.score
            meta["last_checked"] = now
            kept[symbol] = meta
        else:
            dropped.append(symbol)

    free_slots = config.WATCHLIST_SIZE - len(kept)
    added = []
    if free_slots > 0:
        candidates = [
            s for s in all_scores
            if s.symbol not in kept and s.should_stay_in_watchlist
        ]
        candidates.sort(key=lambda s: s.score, reverse=True)
        for result in candidates[:free_slots]:
            kept[result.symbol] = {
                "added_at": now,
                "last_score": result.score,
                "last_checked": now,
            }
            added.append(result.symbol)

    return kept, added, dropped
