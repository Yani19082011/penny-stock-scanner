"""
Вход на приложението.

РЕАЛНО-ВРЕМЕВА версия: два цикъла вместо един.
  - run_fast_check() на всеки config.FAST_INTERVAL_MINUTES (по подразбиране
    2 мин) - прескорира САМО вече наблюдаваните 5 тикера, за да хванем
    пробив възможно най-бързо, без да чакаме следващото пълно сканиране.
  - run_full_scan() на всеки config.SCAN_INTERVAL_MINUTES (по подразбиране
    10 мин) - сканира целия universe за нови кандидати и обновява watchlist-а.

Render free tier няма безплатен "background worker" - само Web Service
(който трябва да отговаря на HTTP и заспива след 15 мин без трафик). Затова
тук вдигаме мъничък Flask health-check сървър на config.PORT + пускаме
циклите във фонова нишка. За да не заспива, ползвай безплатен external
pinger (cron-job.org / UptimeRobot) към "/" на всеки 10 мин - виж README.md.

Локално: python main.py
На Render: Start Command = python main.py (виж README.md за детайли).
"""
import logging
import os
import threading
import time
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import requests
import schedule
from flask import Flask

import config
from data_sources import (
    AlpacaClient, FinnhubClient, FMPClient, get_sec_dilution_flags, get_bars_yfinance,
    get_google_news_rss, get_minute_bars_batch,
)
from halts import get_recently_resumed
from indicators import compute_daily_signals
from scoring import score_symbol
from universe import get_universe, get_volume_snapshot, rank_by_dollar_volume
from watchlist import load_watchlist, save_watchlist, update_watchlist
from notifier import send_alert, send_price_spike_alert, send_telegram_message

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("main")

# --- Стартова самопроверка ---
# Виж същата защита в MemecoinScanner/main.py - реален случай (17.09) там:
# стар/непълен config.py караше score_token() да гърми тихо за ВСЯКА
# монета, часове наред, без ботът да покаже ясна грешка (health-check-ът
# минаваше нормално). Тук прилагаме същия принцип превантивно, за да не се
# повтори същият клас бъг и в penny-stock бота.
REQUIRED_CONFIG_ATTRS = [
    "MAX_UNIVERSE_PRICE", "MAX_MARKET_CAP_USD", "MAX_MOVERS_CANDIDATES",
    "WATCHLIST_SIZE", "PREMARKET_START_HOUR", "PREMARKET_START_MINUTE",
    "SCAN_INTERVAL_MINUTES", "FAST_INTERVAL_MINUTES",
    "MIN_HIGH_POTENTIAL_CONFIRMATIONS", "PEAK_DRAWDOWN_STOP_PCT",
    "POSITION_SIZE_EUR", "TARGET_PROFIT_EUR", "TARGET_PROFIT_PCT",
    "HIGH_POTENTIAL_THRESHOLD", "EXIT_THRESHOLD",
    "ALERT_EMAIL_ENABLED", "RESEND_API_KEY", "RESEND_FROM_EMAIL", "ALERT_EMAIL_TO",
    "MIN_EMAIL_INTERVAL_SECONDS", "MAX_EMAILS_PER_DAY", "ALERT_QUIET_HOURS_TZ", "PORT",
    "KEEP_ALIVE_PING_MINUTES",
    # --- добавени 18.09 при цялостен преглед на кода - тези липсваха от
    # проверката, въпреки че се четат реално от bota (главно от клиентите,
    # инстанцирани по-долу, и от watchlist.py) - виж коментара при
    # _startup_self_check() за защо реда на изпълнение по-долу вече слага
    # тази проверка ПРЕДИ инстанцирането им. ---
    "ALPACA_API_KEY", "ALPACA_SECRET_KEY", "ALPACA_BASE_URL", "ALPACA_DATA_URL",
    "FINNHUB_API_KEY", "FMP_API_KEY", "DATA_DIR", "WATCHLIST_FILE",
    "UPSTASH_REDIS_REST_URL", "UPSTASH_REDIS_REST_TOKEN",
    "ALERT_ACTIVE_START_HOUR", "ALERT_ACTIVE_START_MINUTE",
    "ALERT_ACTIVE_END_HOUR", "ALERT_ACTIVE_END_MINUTE",
    # --- добавени 01.10 - "ЦЕНОВИ СКОК" v2 (замества старото "ОБЕМЕН СКОК"),
    # по ТОЧНА спецификация на потребителя - виж config.py за пълния контекст ---
    "PRICE_SPIKE_ENABLED", "PRICE_SPIKE_INTERVAL_MINUTES",
    "PRICE_SPIKE_UNIVERSE_REFRESH_MINUTES", "PRICE_SPIKE_TOP_N",
    "PRICE_SPIKE_MIN_DOLLAR_VOLUME", "PRICE_SPIKE_VOLUME_MULTIPLIER",
    "PRICE_SPIKE_VOLUME_LOOKBACK_MINUTES", "PRICE_SPIKE_MIN_PRICE_CHANGE_PCT",
    "PRICE_SPIKE_PRICE_LOOKBACK_MINUTES", "PRICE_SPIKE_COOLDOWN_MINUTES",
    "TELEGRAM_ENABLED", "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID",
]


def _startup_self_check():
    missing = [name for name in REQUIRED_CONFIG_ATTRS if not hasattr(config, name)]
    if missing:
        log.critical(
            "СТАРТОВА ПРОВЕРКА ПРОВАЛЕНА: config.py липсват настройки: %s. "
            "Най-вероятно файлът (локално или на Render) е стара/непълна версия - "
            "провери git push/pull и redeploy-ни. Спирам стартирането, вместо да "
            "оставя бота да сканира тихо счупен.",
            ", ".join(missing),
        )
        raise SystemExit(1)

    # (07.10) обновено за новата схема с 2 дневни сигнала (donchian_breakout /
    # fib_retracement_bounce) - виж indicators.py/scoring.py за пълния контекст.
    fake_ind = {
        "price": 3.5, "donchian_breakout": True, "fib_retracement_bounce": False,
    }
    try:
        score_symbol("SELFTEST", fake_ind, True, {"has_recent_dilution_filing": False})
    except Exception as e:
        log.critical(
            "СТАРТОВА ПРОВЕРКА ПРОВАЛЕНА: score_symbol() гърми на синтетичен тест "
            "(%s) - има бъг/несъответствие между config.py и scoring.py. Спирам "
            "стартирането, вместо да оставя бота да сканира тихо счупен.",
            e,
        )
        raise SystemExit(1)

    log.info("Стартова самопроверка: config.py и scoring.py изглеждат съвместими.")


# ВАЖНО (18.09, намерено при цялостен преглед на кода): _startup_self_check()
# трябва да се извика ТУК, ПРЕДИ инстанцирането на клиентите по-долу - иначе
# AlpacaClient()/FinnhubClient()/FMPClient() (ако четат config стойности при
# конструиране) могат да гръмнат с гол, неясен AttributeError при стар/непълен
# config.py, преди самата самопроверка изобщо да успее да покаже ясната
# CRITICAL диагностика по-горе. main() по-долу вече НЕ вика проверката пак -
# извикана е веднъж, тук, при импортиране на модула.
_startup_self_check()

alpaca = AlpacaClient()
finnhub = FinnhubClient()
fmp = FMPClient()

app = Flask(__name__)
_status = {"last_full_scan_at": None, "last_fast_check_at": None, "last_watchlist": {}}


@app.route("/")
def health():
    """Health-check endpoint - и за Render, и за external keep-alive pinger-а."""
    return {"status": "ok", **_status}


@app.route("/test-email")
def test_email():
    """Изпраща тестов email алърт през Resend, за да провериш дали
    ALERT_EMAIL_ENABLED/RESEND_API_KEY/ALERT_EMAIL_TO са настроени правилно.
    Просто отвори този URL в браузъра веднъж."""
    from scoring import ScoreResult
    fake = ScoreResult(
        symbol="TEST",
        score=99,
        reasons=["Това е тестов алърт за проверка на Resend интеграцията."],
        has_catalyst=True,
        raw={"price": 1.23},
    )
    send_alert("ТЕСТ", fake)
    if not config.ALERT_EMAIL_ENABLED:
        return {"sent": False, "reason": "ALERT_EMAIL_ENABLED е false - провери Render Environment Variables."}
    if not config.RESEND_API_KEY:
        return {"sent": False, "reason": "RESEND_API_KEY липсва - провери Render Environment Variables."}
    return {"sent": True, "to": config.ALERT_EMAIL_TO, "note": "Провери логовете (Logs таб) и пощата си."}


@app.route("/test-telegram")
def test_telegram():
    """Изпраща тестово Telegram съобщение, за да провериш дали
    TELEGRAM_ENABLED/TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID са настроени
    правилно (виж README.md за стъпките през @BotFather). Просто отвори този
    URL в браузъра веднъж."""
    if not config.TELEGRAM_ENABLED:
        return {"sent": False, "reason": "TELEGRAM_ENABLED е false - провери Render Environment Variables."}
    if not (config.TELEGRAM_BOT_TOKEN and config.TELEGRAM_CHAT_ID):
        return {"sent": False, "reason": "TELEGRAM_BOT_TOKEN или TELEGRAM_CHAT_ID липсват."}
    ok = send_telegram_message("✅ Тестово съобщение от Penny Stock Scanner - Telegram връзката работи!")
    return {"sent": ok, "note": "Провери логовете (Logs таб) и Telegram чата си."}


def _has_news_catalyst(symbol: str, resumed_symbols: set) -> bool:
    if symbol in resumed_symbols:
        # Наскоро възобновен след halt - почти винаги реален catalyst, дори
        # когато безплатните ни новинарски източници още не са го хванали.
        # Виж halts.py за защо не пращаме алърт директно на "спрян" статус.
        return True
    # ВАЖНО (23.09, намерено в живи Render логове - "FMP news fail ... 402
    # Payment Required" за почти всеки тикер): текущият FMP ключ на
    # потребителя не покрива news endpoint-а (изисква платен план) - FMP
    # практически НИКОГА не връща резултат вече, само шум в логовете.
    # Добавихме get_google_news_rss() (виж data_sources.py за пълния
    # research/honest tradeoff контекст) МЕЖДУ Finnhub и FMP - безплатен,
    # без ключ - за да не разчитаме само на Alpaca+Finnhub, докато FMP
    # реално не работи с този ключ.
    news = (
        alpaca.get_news(symbol, limit=5)
        or finnhub.company_news(symbol, days_back=2)
        or get_google_news_rss(symbol, limit=5)
        or fmp.stock_news(symbol, limit=5)
    )
    return bool(news)


_NY_TZ = ZoneInfo("America/New_York")


def _is_market_hours() -> bool:
    """Редовна сесия (9:30-16:00 ET) + pre-market (4:00-9:30 ET), по избор на
    потребителя. Смятаме директно в America/New_York чрез zoneinfo, вместо
    твърд UTC офсет - това автоматично оправя и DST нюанса от старата версия
    (лятно/зимно часово време в САЩ вече не разминава прозореца).

    ВНИМАНИЕ: Alpaca безплатният IEX feed покрива само ~2.5% от обема на
    пазара (по документацията им) - през pre-market вероятно ще вижда МНОГО
    по-рядки/тънки данни, отколкото през редовната сесия. Не е гарантирано,
    че FMP-ските movers endpoint-и (biggest-gainers/losers/most-actives)
    реално отразяват pre-market движение - тяхната документация не го
    потвърждава изрично. С други думи: ботът ще ОПИТВА да сканира през
    pre-market, но количеството/качеството на кандидатите може да е по-слабо
    отколкото през 9:30-16:00 ET - провери логовете, за да видиш реално
    какво се случва.
    """
    now_et = datetime.now(_NY_TZ)
    if now_et.weekday() >= 5:
        return False
    minutes = now_et.hour * 60 + now_et.minute
    pre_market_start = config.PREMARKET_START_HOUR * 60 + config.PREMARKET_START_MINUTE
    regular_close = 16 * 60
    return pre_market_start <= minutes <= regular_close


# (07.10) обновено за новата ДНЕВНА схема (донован пробив/Fibonacci откат -
# виж indicators.py/scoring.py) - виж min_len проверките в strategies.py
# (donchian: channel_period+25=45, fib_retracement: swing_lookback+2=42);
# тук искаме малко буфер над това.
_MIN_DAILY_BARS_FOR_SIGNALS = 90


def _score_symbols(symbols) -> list:
    scores = []
    # Веднъж на сканиране (не на тикер) - виж halts.py::get_recently_resumed.
    resumed_symbols = set(get_recently_resumed().keys())
    for symbol in symbols:
        try:
            # (07.10) ВАЖНО: вече взимаме ДНЕВНИ (не 5-мин) свещи - двата
            # валидирани сигнала (donchian_breakout/fib_retracement_bounce,
            # виж strategies.py) са backtest-вани на дневни бари. yfinance е
            # безплатен и не изисква ключ (виж data_sources.get_bars_yfinance).
            # ЧЕСТНА бележка: докато пазарът е отворен, последният ("днешен")
            # ред е още недовършена свещ - виж бележката в indicators.py.
            bars = get_bars_yfinance(symbol, interval="1d", period="6mo", limit=150)
            if len(bars) < _MIN_DAILY_BARS_FOR_SIGNALS:
                continue
            ind = compute_daily_signals(bars)
            if not ind or ind["price"] > config.MAX_UNIVERSE_PRICE:
                continue
            catalyst = _has_news_catalyst(symbol, resumed_symbols)
            dilution = get_sec_dilution_flags(symbol)
            scores.append(score_symbol(symbol, ind, catalyst, dilution))
        except Exception as e:
            log.warning("Грешка при %s: %s", symbol, e)
    return scores


def _maybe_alert_high_potential(symbol: str, meta: dict, result):
    """Праща алърт само при НОВО пресичане на прага - не спамва на всеки
    бърз цикъл докато тикерът си стои над прага. Плюс защита срещу
    "купуване на върха" (виж config.MIN_HIGH_POTENTIAL_CONFIRMATIONS /
    PEAK_DRAWDOWN_STOP_PCT): изисква поне N последователни проверки над
    прага (не еднократен spike) и цената да не е вече паднала осезаемо
    от най-високата видяна цена, преди да пратим email."""
    price = (result.raw or {}).get("price") if result else None
    if price:
        meta["peak_price"] = max(meta.get("peak_price") or price, price)

    if result and result.is_high_potential:
        meta["consecutive_high_potential"] = meta.get("consecutive_high_potential", 0) + 1
        peak_price = meta.get("peak_price")
        drawdown_pct = ((peak_price - price) / peak_price * 100) if (peak_price and price) else 0.0
        already_rolling_over = drawdown_pct >= config.PEAK_DRAWDOWN_STOP_PCT
        confirmed = meta["consecutive_high_potential"] >= config.MIN_HIGH_POTENTIAL_CONFIRMATIONS

        if not meta.get("alerted_high_potential"):
            if confirmed and not already_rolling_over:
                # ВАЖНО (18.09, по изричен избор на потребителя): send_alert()
                # връща False САМО ако anti-spam темпото (MIN_EMAIL_INTERVAL_
                # SECONDS/MAX_EMAILS_PER_DAY) е блокирало email-а точно сега -
                # преди тук флагът се вдигаше БЕЗУСЛОВНО, дори когато email-ът
                # реално е бил пропуснат заради темпото, което ГУБЕШЕ тикера
                # завинаги (следващият цикъл вижда alerted_high_potential=True
                # и никога не пробва пак). Сега флагът се вдига само при
                # реално "обработен" резултат - при пропуск заради темпото,
                # следващият бърз/пълен цикъл (2/10 мин по-късно) пробва пак с
                # ПРЕСНИ данни (нов score/цена от новото сканиране).
                if send_alert(f"ВИСОК ПОТЕНЦИАЛ (~{round(config.TARGET_PROFIT_PCT*100)}%)", result):
                    meta["alerted_high_potential"] = True
                else:
                    log.info(
                        "%s: score е потвърден, НО anti-spam темпото не позволява email точно сега - "
                        "ще пробвам пак на следващия цикъл.",
                        symbol,
                    )
            elif already_rolling_over:
                log.info(
                    "%s: score е висок, НО цената вече е паднала %.1f%% от пика - "
                    "най-вероятно върхът е изпуснат, пропускам алърта.",
                    symbol, drawdown_pct,
                )
    else:
        # ВАЖНО (18.09, по оплакване на потребителя "да не ми дава едни и
        # същите"): преди тук се ресетваше и alerted_high_potential=False -
        # т.е. ВСЯКО моментно падане на score под 70 (дори с 1 точка, дори
        # временно defailure на news API-то, докато тикерът си стои спокойно
        # В watchlist-а между EXIT_THRESHOLD=40 и HIGH_POTENTIAL_THRESHOLD=70)
        # "забравяше", че вече сме алъртнали този тикер - и следващия път,
        # щом score-ът пак минеше 70, се пращаше ВТОРИ email за СЪЩИЯ тикер,
        # без той изобщо да е излизал от watchlist-а. Сега alerted_high_
        # potential се пази, докато тикерът РЕАЛНО не отпадне от watchlist-а
        # (score < EXIT_THRESHOLD - виж watchlist.py::update_watchlist, което
        # тогава изтрива целия meta речник) - само тогава ново влизане получава
        # чист старт и може да алъртне пак. consecutive_high_potential пак се
        # ресетва нормално - анти-spike защитата (N последователни проверки)
        # си остава непокътната за всеки нов опит.
        meta["consecutive_high_potential"] = 0


def run_fast_check():
    """Бърз цикъл - само текущия watchlist, за реално-времеви алърти."""
    if not _is_market_hours():
        return
    current_watchlist = load_watchlist()
    if not current_watchlist:
        return

    scores = _score_symbols(current_watchlist.keys())
    scores_by_symbol = {s.symbol: s for s in scores}

    for symbol, meta in current_watchlist.items():
        result = scores_by_symbol.get(symbol)
        if result:
            meta["last_score"] = result.score
        _maybe_alert_high_potential(symbol, meta, result)

    save_watchlist(current_watchlist)
    _status["last_fast_check_at"] = datetime.now(timezone.utc).isoformat()
    _status["last_watchlist"] = current_watchlist
    log.info("Бърз цикъл: %s", {s: m.get("last_score") for s, m in current_watchlist.items()})


def run_full_scan():
    """Пълно сканиране - целия universe, за нови кандидати + watchlist ротация."""
    if not _is_market_hours():
        log.info("Извън пазарни часове - пропускам пълното сканиране.")
        return

    log.info("Стартирам пълно сканиране...")
    current_watchlist = load_watchlist()
    universe = set(get_universe()) | set(current_watchlist.keys())

    all_scores = _score_symbols(universe)
    new_watchlist, added, dropped = update_watchlist(current_watchlist, all_scores)

    scores_by_symbol = {s.symbol: s for s in all_scores}
    for symbol in added:
        # ВАЖНО (18.09, намерено при цялостен преглед на кода): по-рано тук
        # директно се пращаше email при ВСЯКО влизане в watchlist - но
        # влизането изисква само score >= EXIT_THRESHOLD (40/100) на ЕДНО-
        # ЕДИНСТВЕНО сканиране, без потвърждение и без drawdown проверка -
        # точно същият клас бъг ("алърт на единичен spike"), който вече
        # оправихме за "ВИСОК ПОТЕНЦИАЛ" алъртите (виж
        # MIN_HIGH_POTENTIAL_CONFIRMATIONS/PEAK_DRAWDOWN_STOP_PCT по-долу).
        # Влизането в watchlist само по себе си вече НЕ праща email - само
        # лог за проследяване. Реален email идва единствено през
        # _maybe_alert_high_potential(), което изисква истинско потвърждение.
        log.info(
            "%s влиза в watchlist (score=%.1f) - следя го, но НЯМА да пратя email, докато не се "
            "потвърди (виж MIN_HIGH_POTENTIAL_CONFIRMATIONS/PEAK_DRAWDOWN_STOP_PCT).",
            symbol, scores_by_symbol[symbol].score,
        )
    for symbol in dropped:
        log.info("%s излиза от watchlist (score падна под прага).", symbol)

    for symbol, meta in new_watchlist.items():
        _maybe_alert_high_potential(symbol, meta, scores_by_symbol.get(symbol))

    save_watchlist(new_watchlist)
    _status["last_full_scan_at"] = datetime.now(timezone.utc).isoformat()
    _status["last_watchlist"] = new_watchlist

    log.info(
        "Пълно сканиране завършено. Watchlist (%d/%d): %s",
        len(new_watchlist), config.WATCHLIST_SIZE, list(new_watchlist.keys()),
    )


# --- "ЦЕНОВИ СКОК" v2 - виж config.PRICE_SPIKE_* и notifier.send_price_spike_alert
# за пълния контекст (01.10, по ТОЧНА спецификация на потребителя, заменя
# старото "ОБЕМЕН СКОК"). Кешът и cooldown dict-ът са нарочно само в паметта
# на процеса - нулират се при redeploy/restart (виж config.py).
_price_spike_universe: list = []       # кеширан топ-N списък (dict-ове от universe.rank_by_dollar_volume)
_price_spike_last_alert_at: dict = {}  # symbol -> datetime на последния изпратен алърт (15-мин cooldown)


def run_price_spike_universe_refresh():
    """По-рядкият от двата цикъла на тази функция (на всеки config.
    PRICE_SPIKE_UNIVERSE_REFRESH_MINUTES) - опреснява топ-N списъка по
    dollar volume (условие 1 от спецификацията). run_price_spike_scan()
    по-долу (на всеки 1 мин по подразбиране) винаги чете последния кеширан
    списък тук, вместо да удря StockAnalysis.com всяка минута."""
    global _price_spike_universe
    if not config.PRICE_SPIKE_ENABLED or not _is_market_hours():
        return
    try:
        snapshot = get_volume_snapshot()
        _price_spike_universe = rank_by_dollar_volume(
            snapshot, config.PRICE_SPIKE_TOP_N, config.PRICE_SPIKE_MIN_DOLLAR_VOLUME,
        )
        log.info(
            "Ценови скок: опреснен топ списък (%d тикера над $%.0f dollar volume): %s",
            len(_price_spike_universe), config.PRICE_SPIKE_MIN_DOLLAR_VOLUME,
            [row["symbol"] for row in _price_spike_universe],
        )
    except Exception as e:
        log.warning("Ценови скок: опресняването на топ списъка се провали: %s", e)


def run_price_spike_scan():
    """Проверява условия 2 и 3 от спецификацията (виж config.PRICE_SPIKE_*)
    САМО върху последния кеширан топ-N списък (условие 1, вече филтрирано от
    run_price_spike_universe_refresh по-горе). И ДВЕТЕ трябва да са верни
    ЕДНОВРЕМЕННО:
      2. обем последна минута >= PRICE_SPIKE_VOLUME_MULTIPLIER x средния обем
         от предходните PRICE_SPIKE_VOLUME_LOOKBACK_MINUTES минути
      3. цената е нагоре >= PRICE_SPIKE_MIN_PRICE_CHANGE_PCT% за последните
         PRICE_SPIKE_PRICE_LOOKBACK_MINUTES минути
    Никога не пуска поръчка - само следи и известява."""
    if not config.PRICE_SPIKE_ENABLED or not _is_market_hours():
        return
    if not _price_spike_universe:
        return

    symbols = [row["symbol"] for row in _price_spike_universe]
    by_symbol = {row["symbol"]: row for row in _price_spike_universe}
    needed_bars = max(config.PRICE_SPIKE_VOLUME_LOOKBACK_MINUTES, config.PRICE_SPIKE_PRICE_LOOKBACK_MINUTES) + 1

    try:
        bars_by_symbol = get_minute_bars_batch(symbols, lookback_minutes=needed_bars + 5)
    except Exception as e:
        log.warning("Ценови скок сканиране: грешка при взимане на 1-мин свещи: %s", e)
        return

    now = datetime.now(timezone.utc)
    fired = []
    for symbol, bars in bars_by_symbol.items():
        if len(bars) < needed_bars:
            continue  # недостатъчно 1-мин свещи още (напр. тъкмо отворила сесията) - прескачаме тази обиколка

        volumes = bars["volume"]
        last_minute_volume = volumes.iloc[-1]
        prior_volumes = volumes.iloc[-(config.PRICE_SPIKE_VOLUME_LOOKBACK_MINUTES + 1):-1]
        avg_prior_volume = prior_volumes.mean() if len(prior_volumes) else 0
        if avg_prior_volume <= 0 or last_minute_volume < config.PRICE_SPIKE_VOLUME_MULTIPLIER * avg_prior_volume:
            continue  # условие 2 не е изпълнено

        closes = bars["close"]
        price_now = closes.iloc[-1]
        price_then = closes.iloc[-(config.PRICE_SPIKE_PRICE_LOOKBACK_MINUTES + 1)]
        if not price_then:
            continue
        price_change_pct = (price_now - price_then) / price_then * 100
        if price_change_pct < config.PRICE_SPIKE_MIN_PRICE_CHANGE_PCT:
            continue  # условие 3 не е изпълнено

        last_alert = _price_spike_last_alert_at.get(symbol)
        if last_alert and (now - last_alert).total_seconds() < config.PRICE_SPIKE_COOLDOWN_MINUTES * 60:
            continue  # вече алъртнахме за този тикер наскоро - cooldown, дори да продължава да отговаря на условията

        dollar_volume = by_symbol.get(symbol, {}).get("dollar_volume") or (price_now * volumes.sum())
        if send_price_spike_alert(symbol, price_now, price_change_pct, last_minute_volume, avg_prior_volume, dollar_volume):
            _price_spike_last_alert_at[symbol] = now
            fired.append(symbol)

    if fired:
        log.info("Ценови скок сканиране: сигнал за %s", fired)

    # ВАЖНО (02.10, след реален "exceeded its memory limit" инцидент на
    # Render - виж config.py/data_sources.py за пълния контекст): логваме
    # текущата памет на процеса на всяка обиколка, за да личи в Render Logs
    # дали расте с времето (ранен признак на memory leak), преди да стигне
    # до следващ OOM restart.
    try:
        import resource
        peak_mb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
        log.info("Ценови скок: пикова памет на процеса засега ~%.0f MB.", peak_mb)
    except Exception:
        pass


def _scan_loop():
    log.info(
        "Penny Stock Scanner фонов loop стартира. Universe price cap: $%.2f, watchlist size: %d, "
        "fast check на всеки %d мин, пълно сканиране на всеки %d мин, ценови скок на всеки %d мин "
        "(топ опреснен на всеки %d мин, enabled=%s).",
        config.MAX_UNIVERSE_PRICE, config.WATCHLIST_SIZE, config.FAST_INTERVAL_MINUTES, config.SCAN_INTERVAL_MINUTES,
        config.PRICE_SPIKE_INTERVAL_MINUTES, config.PRICE_SPIKE_UNIVERSE_REFRESH_MINUTES, config.PRICE_SPIKE_ENABLED,
    )
    run_full_scan()  # веднага при старт, после по разписание
    run_price_spike_universe_refresh()
    schedule.every(config.SCAN_INTERVAL_MINUTES).minutes.do(run_full_scan)
    schedule.every(config.FAST_INTERVAL_MINUTES).minutes.do(run_fast_check)
    schedule.every(config.PRICE_SPIKE_UNIVERSE_REFRESH_MINUTES).minutes.do(run_price_spike_universe_refresh)
    schedule.every(config.PRICE_SPIKE_INTERVAL_MINUTES).minutes.do(run_price_spike_scan)
    while True:
        schedule.run_pending()
        time.sleep(15)


def _self_ping_loop():
    """Праща GET заявка към собствения публичен Render URL на всеки
    config.KEEP_ALIVE_PING_MINUTES минути - виж идентичния коментар в
    MemecoinScanner/main.py::_self_ping_loop за пълния контекст (18.09,
    по оплакване "от час и нещо няма никакви сигнали"). Тук ефектът е малко
    по-различен - извън пазарни часове ботът и без друго не сканира - но
    докато е пазарно време, service-ът заспал = пропуснат fast/full цикъл,
    затова пак си струва да не разчитаме само на външен pinger."""
    external_url = os.getenv("RENDER_EXTERNAL_URL")
    if not external_url:
        log.info("RENDER_EXTERNAL_URL не е зададен (вероятно локално стартиране) - self-ping е изключен.")
        return
    log.info(
        "Self-ping активен: %s на всеки %d мин (пази Render service-а буден).",
        external_url, config.KEEP_ALIVE_PING_MINUTES,
    )
    while True:
        time.sleep(config.KEEP_ALIVE_PING_MINUTES * 60)
        try:
            requests.get(external_url, timeout=10)
            log.info("Self-ping към %s - ОК.", external_url)
        except Exception as e:
            log.warning("Self-ping към %s се провали: %s (ще пробвам пак след %d мин).", external_url, e, config.KEEP_ALIVE_PING_MINUTES)


def main():
    # _startup_self_check() вече е извикана веднъж при импортиране на модула
    # (виж по-горе, ПРЕДИ инстанцирането на alpaca/finnhub/fmp) - не се
    # налага втори път тук.
    thread = threading.Thread(target=_scan_loop, daemon=True)
    thread.start()
    ping_thread = threading.Thread(target=_self_ping_loop, daemon=True)
    ping_thread.start()
    app.run(host="0.0.0.0", port=config.PORT)


if __name__ == "__main__":
    main()
