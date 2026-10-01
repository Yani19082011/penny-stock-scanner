"""
Изпращане на алърти. Три канала:
  - лог (винаги, вижда се в Render "Logs" таба)
  - email през Resend (https://resend.com) - HTTP API, само ако
    ALERT_EMAIL_ENABLED=true и RESEND_API_KEY е попълнен.
  - Telegram (01.10) - само за "ЦЕНОВИ СКОК" сигналите (виж
    send_price_spike_alert), само ако TELEGRAM_ENABLED=true и
    TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID са попълнени - виж README.md.

Забележка: НЕ ползваме Gmail SMTP/App Password, защото Google не позволява
App Passwords на Family Link (supervised) акаунти. Resend е безплатна услуга,
праща email през обикновен HTTP POST с API ключ - виж README.md за стъпките.
"""
import logging
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import requests

import config
from scoring import ScoreResult

log = logging.getLogger("notifier")

RESEND_API_URL = "https://api.resend.com/emails"


def _within_active_hours() -> bool:
    """Проверява дали текущият момент е в разрешения прозорец за имейли
    (config.ALERT_ACTIVE_START_* / ALERT_ACTIVE_END_* в ALERT_QUIET_HOURS_TZ).
    Ако timezone данните липсват по някаква причина - НЕ блокираме (по-добре
    да получиш имейл в грешен час, отколкото да мълчим заради bug)."""
    try:
        tz = ZoneInfo(config.ALERT_QUIET_HOURS_TZ)
    except Exception as e:
        log.warning("ALERT_QUIET_HOURS_TZ (%s) невалиден: %s - пропускам проверката за часове.", config.ALERT_QUIET_HOURS_TZ, e)
        return True
    now_local = datetime.now(tz)
    start = now_local.replace(hour=config.ALERT_ACTIVE_START_HOUR, minute=config.ALERT_ACTIVE_START_MINUTE, second=0, microsecond=0)
    end = now_local.replace(hour=config.ALERT_ACTIVE_END_HOUR, minute=config.ALERT_ACTIVE_END_MINUTE, second=0, microsecond=0)
    return start <= now_local <= end

# --- Anti-spam темпо-ограничител за Resend (виж config.MIN_EMAIL_INTERVAL_SECONDS /
# MAX_EMAILS_PER_DAY) - пази в паметта на процеса, реду се при restart на Render,
# но това е ок - целта е само да не гърмим много имейли наведнъж при серия алърти. ---
_last_sent_at = None
_daily_count = 0
_daily_reset_date = None


def _rate_limit_ok() -> bool:
    global _last_sent_at, _daily_count, _daily_reset_date
    now = datetime.now(timezone.utc)
    today = now.date()

    if _daily_reset_date != today:
        _daily_reset_date = today
        _daily_count = 0

    if _daily_count >= config.MAX_EMAILS_PER_DAY:
        log.warning(
            "Дневният лимит от %d имейла е достигнат - пропускам email-а (алъртът е в логовете).",
            config.MAX_EMAILS_PER_DAY,
        )
        return False

    if _last_sent_at is not None:
        elapsed = (now - _last_sent_at).total_seconds()
        if elapsed < config.MIN_EMAIL_INTERVAL_SECONDS:
            log.info(
                "Прескачам email (анти-спам темпо) - оставащи %.0fс до следващия разрешен имейл.",
                config.MIN_EMAIL_INTERVAL_SECONDS - elapsed,
            )
            return False

    return True


def _mark_email_sent():
    global _last_sent_at, _daily_count
    _last_sent_at = datetime.now(timezone.utc)
    _daily_count += 1


def format_alert(kind: str, result: ScoreResult) -> str:
    target_pct = round(config.TARGET_PROFIT_PCT * 100)
    lines = [
        f"[{kind}] {result.symbol} — score {result.score}/100",
        f"Цена: ${result.raw.get('price')}",
        f"Потенциал: ~{target_pct}% return "
        f"(позиция {config.POSITION_SIZE_EUR}€ -> цел {config.TARGET_PROFIT_EUR}€)",
        "Причини: " + "; ".join(result.reasons) if result.reasons else "",
    ]
    return "\n".join(l for l in lines if l)


def can_send_now() -> bool:
    """Pure "peek" - True ако email, пратен точно СЕГА, НЕ би бил пропуснат
    заради anti-spam темпото (MIN_EMAIL_INTERVAL_SECONDS/MAX_EMAILS_PER_DAY).
    main.py я ползва, за да НЕ маркира тикер като "вече алъртнат", когато
    реално email-ът е бил пропуснат заради темпото - виж коментара в
    main.py::_maybe_alert_high_potential (18.09)."""
    return _rate_limit_ok()


def send_alert(kind: str, result: ScoreResult) -> bool:
    """Връща True ако е "обработено" (пратен успешно, ИЛИ email-ите са
    изключени/не са конфигурирани, ИЛИ извън разрешените часове - retry не
    би помогнал), False САМО ако е пропуснат чисто заради anti-spam темпото."""
    message = format_alert(kind, result)
    log.info("ALERT:\n%s", message)

    if not config.ALERT_EMAIL_ENABLED:
        return True
    return _send_email(subject=f"[Penny Stock Scanner] {result.symbol} - {kind}", body=message)


TELEGRAM_API_URL = "https://api.telegram.org/bot{token}/sendMessage"


def send_telegram_message(text: str) -> bool:
    """Праща съобщение през Telegram Bot API - прост HTTP POST, без
    допълнителна библиотека (01.10, виж README.md за стъпките да си
    направиш бот през @BotFather и да вземеш chat_id-то си). Връща True само
    при реално успешно изпратено съобщение - False ако Telegram не е
    конфигуриран/включен, или заявката се провали (извикващият код тогава
    решава дали да пробва email fallback - виж send_price_spike_alert)."""
    if not (config.TELEGRAM_ENABLED and config.TELEGRAM_BOT_TOKEN and config.TELEGRAM_CHAT_ID):
        return False
    try:
        resp = requests.post(
            TELEGRAM_API_URL.format(token=config.TELEGRAM_BOT_TOKEN),
            json={"chat_id": config.TELEGRAM_CHAT_ID, "text": text},
            timeout=15,
        )
        if resp.status_code >= 300:
            log.error("Telegram отказа изпращането (%s): %s", resp.status_code, resp.text)
            return False
        log.info("Telegram алърт изпратен успешно.")
        return True
    except Exception as e:
        log.error("Изпращането през Telegram се провали: %s", e)
        return False


def send_price_spike_alert(symbol: str, price, price_change_pct, last_minute_volume, avg_prior_volume, dollar_volume) -> bool:
    """"ЦЕНОВИ СКОК" сигнал (01.10, по ТОЧНА спецификация на потребителя -
    заменя старата send_volume_surge_alert). Условията (топ-N по dollar
    volume + обем последна минута >= Nx средния + цена нагоре >= X% за N мин)
    вече са проверени в main.py::run_price_spike_scan ПРЕДИ да се стигне
    дотук - тук само форматираме и пращаме.

    Канал: Telegram (config.TELEGRAM_*) - по избор на потребителя, за
    по-бързо известяване на телефона, вместо email. Ако Telegram не е
    конфигуриран/се провали, пада обратно на email (ако е включен) - по-добре
    закъснял email, отколкото напълно изгубен сигнал.

    НИКОГА не пуска поръчка - само наблюдава и известява, потребителят решава
    сам дали и как да влезе (виж README.md)."""
    message = (
        f"🚀 ЦЕНОВИ СКОК: {symbol}\n"
        f"Цена: ${price:.4f}"
        + (f" ({price_change_pct:+.1f}% за последните {config.PRICE_SPIKE_PRICE_LOOKBACK_MINUTES} мин)" if price_change_pct is not None else "")
        + "\n"
        f"Обем последна минута: {last_minute_volume:,.0f} "
        f"(средно предходни {config.PRICE_SPIKE_VOLUME_LOOKBACK_MINUTES} мин: {avg_prior_volume:,.0f})\n"
        f"Dollar volume днес: ${dollar_volume:,.0f}\n"
        "⚠️ Само наблюдение - БОТЪТ НЕ пуска поръчки - провери сам графиката/новините преди да влезеш."
    )
    log.info("ЦЕНОВИ СКОК:\n%s", message)

    if send_telegram_message(message):
        return True
    if not config.ALERT_EMAIL_ENABLED:
        return True
    return _send_email(subject=f"[Penny Stock Scanner] {symbol} - ЦЕНОВИ СКОК", body=message)


def _send_email(subject: str, body: str) -> bool:
    if not (config.RESEND_API_KEY and config.ALERT_EMAIL_TO):
        log.warning("Email алъртите са включени, но RESEND_API_KEY или ALERT_EMAIL_TO не са попълнени.")
        return True
    if not _within_active_hours():
        log.info(
            "Извън разрешените часове за имейли (%02d:%02d-%02d:%02d %s) - пропускам email-а (алъртът е в логовете).",
            config.ALERT_ACTIVE_START_HOUR, config.ALERT_ACTIVE_START_MINUTE,
            config.ALERT_ACTIVE_END_HOUR, config.ALERT_ACTIVE_END_MINUTE, config.ALERT_QUIET_HOURS_TZ,
        )
        return True
    if not _rate_limit_ok():
        return False
    try:
        resp = requests.post(
            RESEND_API_URL,
            headers={
                "Authorization": f"Bearer {config.RESEND_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "from": config.RESEND_FROM_EMAIL,
                "to": [config.ALERT_EMAIL_TO],
                "subject": subject,
                "text": body,
            },
            timeout=15,
        )
        if resp.status_code >= 300:
            log.error("Resend отказа изпращането (%s): %s", resp.status_code, resp.text)
            return True  # HTTP грешка, не anti-spam темпо - не искаме безкраен retry цикъл
        _mark_email_sent()
        log.info("Email алърт изпратен до %s през Resend", config.ALERT_EMAIL_TO)
        return True
    except Exception as e:
        log.error("Изпращането на email през Resend се провали: %s", e)
        return True  # мрежова грешка, вече е логнато - не anti-spam темпо
