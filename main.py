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
from data_sources import AlpacaClient, FinnhubClient, FMPClient, get_sec_dilution_flags, get_bars_yfinance
from halts import get_recently_resumed
from indicators import compute_all
from scoring import score_symbol
from universe import get_universe
from watchlist import load_watchlist, save_watchlist, update_watchlist
from notifier import send_alert

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

    fake_ind = {
        "price": 3.5, "ema9": 3.4, "ema20": 3.2, "vwap": 3.3, "rsi14": 60.0,
        "relative_volume": 4.0, "trend_up": True, "above_vwap": True,
        "orb_breakout": "bullish", "support": 3.0, "resistance": 3.8, "bullish_candle": True,
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


def _has_news_catalyst(symbol: str, resumed_symbols: set) -> bool:
    if symbol in resumed_symbols:
        # Наскоро възобновен след halt - почти винаги реален catalyst, дори
        # когато безплатните ни новинарски източници още не са го хванали.
        # Виж halts.py за защо не пращаме алърт директно на "спрян" статус.
        return True
    news = alpaca.get_news(symbol, limit=5) or finnhub.company_news(symbol, days_back=2) or fmp.stock_news(symbol, limit=5)
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


_MIN_BARS_FOR_INDICATORS = 25  # виж indicators.compute_all() - под това връща {}


def _score_symbols(symbols) -> list:
    scores = []
    # Веднъж на сканиране (не на тикер) - виж halts.py::get_recently_resumed.
    resumed_symbols = set(get_recently_resumed().keys())
    for symbol in symbols:
        try:
            bars = alpaca.get_bars(symbol, timeframe="5Min", limit=100)
            if len(bars) < _MIN_BARS_FOR_INDICATORS:
                # Alpaca IEX е твърде тънък тук (чест случай в pre-market, или
                # при силно неликвидни тикери дори през редовна сесия) -
                # опитваме безплатния yfinance fallback (по-пълни, консолидирани
                # данни, включително pre/post market), вместо просто да
                # пропуснем кандидата.
                fallback = get_bars_yfinance(symbol)
                if len(fallback) > len(bars):
                    bars = fallback
            ind = compute_all(bars)
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


def _scan_loop():
    log.info(
        "Penny Stock Scanner фонов loop стартира. Universe price cap: $%.2f, watchlist size: %d, "
        "fast check на всеки %d мин, пълно сканиране на всеки %d мин.",
        config.MAX_UNIVERSE_PRICE, config.WATCHLIST_SIZE, config.FAST_INTERVAL_MINUTES, config.SCAN_INTERVAL_MINUTES,
    )
    run_full_scan()  # веднага при старт, после по разписание
    schedule.every(config.SCAN_INTERVAL_MINUTES).minutes.do(run_full_scan)
    schedule.every(config.FAST_INTERVAL_MINUTES).minutes.do(run_fast_check)
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
