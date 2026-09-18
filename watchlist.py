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
import logging
import os
from datetime import datetime, timezone

import requests

import config
from scoring import ScoreResult

log = logging.getLogger("watchlist")

# Ключ в Upstash Redis, под който пазим целия watchlist като един JSON blob.
_UPSTASH_KEY = "pennystockscanner:watchlist"


def _upstash_configured() -> bool:
    return bool(config.UPSTASH_REDIS_REST_URL and config.UPSTASH_REDIS_REST_TOKEN)


def _upstash_cmd(*args):
    """Едно REST повикване към Upstash Redis (https://upstash.com/docs/redis/features/restapi) -
    POST към базовия URL с JSON масив-команда, напр. ["GET","key"] / ["SET","key","value"],
    връща стойността на "result" от отговора."""
    resp = requests.post(
        config.UPSTASH_REDIS_REST_URL,
        headers={"Authorization": f"Bearer {config.UPSTASH_REDIS_REST_TOKEN}"},
        json=list(args),
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json().get("result")


def _ensure_data_dir():
    os.makedirs(config.DATA_DIR, exist_ok=True)


def load_watchlist() -> dict:
    """ВАЖНО (18.09, по оплакване на потребителя за повторни ВИСОК ПОТЕНЦИАЛ
    email-и след всеки push/redeploy на Render): безплатният Render план НЕ
    пази локалния диск между deploy-ите - watchlist.json (кой тикер вече е
    алъртнат) се изтриваше при всеки нов push, което караше вече-алъртнати
    тикери (напр. GSUN, TEAD) да изглеждат "нови" пак и да пращат втори
    email щом score-ът им отново се потвърдеше.

    Ако UPSTASH_REDIS_REST_URL/UPSTASH_REDIS_REST_TOKEN са зададени
    (безплатен Upstash Redis акаунт - виж README/.env.example), пазим
    watchlist-а ТАМ вместо на локалния Render диск - Upstash е външен на
    Render контейнера, значи паметта оцелява през ВСЕКИ redeploy/restart.
    Ако не са зададени, продължаваме по старому с локалния файл (работи си
    нормално, просто паметта не оцелява redeploy - старото поведение)."""
    if _upstash_configured():
        try:
            raw = _upstash_cmd("GET", _UPSTASH_KEY)
            return json.loads(raw) if raw else {}
        except Exception as e:
            log.error("Upstash GET се провали (%s) - тръгвам с празен watchlist тази обиколка.", e)
            return {}
    _ensure_data_dir()
    if not os.path.exists(config.WATCHLIST_FILE):
        return {}
    try:
        with open(config.WATCHLIST_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def save_watchlist(watchlist: dict):
    if _upstash_configured():
        try:
            _upstash_cmd("SET", _UPSTASH_KEY, json.dumps(watchlist, ensure_ascii=False))
            return
        except Exception as e:
            log.error("Upstash SET се провали (%s) - watchlist промените НЕ са запазени тази обиколка.", e)
            return
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
        if result is None:
            # ВАЖНО (18.09, намерено при цялостен преглед на кода): result е
            # None когато тикерът просто НЕ Е бил score-нат тази обиколка
            # (напр. временна грешка при взимане на bars/новини - виж
            # _score_symbols в main.py, което просто логва WARNING и
            # прескача символа) - това НЕ Е същото като "score-ът реално падна
            # под EXIT_THRESHOLD". Преди тук липсата на резултат директно
            # водеше до "else: dropped.append(symbol)" - т.е. една временна
            # грешка на API-то изхвърляше тикера от watchlist-а и БЪРШЕШЕ
            # meta["alerted_high_potential"] му (виж _maybe_alert_high_
            # potential/watchlist.py::update_watchlist по-горе), карайки
            # следващото истинско влизане да изглежда "ново" и да прати
            # дублиран email. Сега пазим тикера непокътнат и просто пробваме
            # пак следващия цикъл с пресни данни.
            kept[symbol] = meta
        elif result.should_stay_in_watchlist:
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
