"""
Изпраща алърти - email (Resend HTTP API) и по избор Telegram.

ВЪЗСТАНОВЕН (13.10) след случайно презаписване с notifier.py от друг
проект (GoldSignalBot), качен по грешка през GitHub "Upload files" в това
repo - старата версия на този файл НЕ беше запазена никъде извлечимо,
затова е пресъздадена от нулата, точно по сигнатурите и начина на употреба,
които main.py реално вика (send_alert(label, result), send_price_spike_
alert(symbol, price_now, price_change_pct, last_minute_volume,
avg_prior_volume, dollar_volume), send_telegram_message(text)) - виж
main.py за пълния контекст. Честно: ако оригиналният email HTML дизайн е
изглеждал различно (цветове, точен текст), това тук е РЕКОНСТРУКЦИЯ, не
byte-perfect възстановяване - но поведението (throttle, тихи часове,
кои данни влизат в писмото) би трябвало да съвпада с документираното в
config.py/main.py.
"""
import logging
import threading
from datetime import datetime, timedelta, timezone

import requests
from zoneinfo import ZoneInfo

import config

log = logging.getLogger("notifier")

RESEND_URL = "https://api.resend.com/emails"
TELEGRAM_URL_TMPL = "https://api.telegram.org/bot{token}/sendMessage"

# --- Anti-spam състояние (виж config.MIN_EMAIL_INTERVAL_SECONDS/
# MAX_EMAILS_PER_DAY/ALERT_QUIET_HOURS_TZ) - нарочно само в паметта на
# процеса (нулира се при redeploy/restart), споделено между send_alert и
# send_price_spike_alert (и двете броят към същата дневна Resend квота) -
# защитено с lock, защото fast/full/price-spike циклите тичат в отделни нишки.
_lock = threading.Lock()
_last_email_at: datetime = None
_emails_sent_today = 0
_emails_sent_date = None  # date() на последното нулиране на дневния брояч


def _in_active_window(now_utc: datetime) -> bool:
    try:
        tz = ZoneInfo(config.ALERT_QUIET_HOURS_TZ)
    except Exception:
        tz = timezone.utc
    local = now_utc.astimezone(tz)
    start = local.replace(hour=config.ALERT_ACTIVE_START_HOUR, minute=config.ALERT_ACTIVE_START_MINUTE,
                           second=0, microsecond=0)
    end = local.replace(hour=config.ALERT_ACTIVE_END_HOUR, minute=config.ALERT_ACTIVE_END_MINUTE,
                         second=0, microsecond=0)
    return start <= local <= end


def _throttle_allows_send() -> bool:
    """True, ако темпото (мин. интервал + дневен таван + тихи часове)
    позволява изпращане ТОЧНО СЕГА - и ако да, вдига брояча/timestamp-а
    веднага (под lock), за да не се "надпреварват" паралелни извиквания."""
    global _last_email_at, _emails_sent_today, _emails_sent_date
    now = datetime.now(timezone.utc)
    with _lock:
        if not _in_active_window(now):
            log.info("Email пропуснат - извън активните часове (%s, %02d:%02d-%02d:%02d %s).",
                      now.isoformat(), config.ALERT_ACTIVE_START_HOUR, config.ALERT_ACTIVE_START_MINUTE,
                      config.ALERT_ACTIVE_END_HOUR, config.ALERT_ACTIVE_END_MINUTE, config.ALERT_QUIET_HOURS_TZ)
            return False

        today = now.date()
        if _emails_sent_date != today:
            _emails_sent_date = today
            _emails_sent_today = 0

        if _emails_sent_today >= config.MAX_EMAILS_PER_DAY:
            log.info("Email пропуснат - дневният таван (%d) е достигнат.", config.MAX_EMAILS_PER_DAY)
            return False

        if _last_email_at is not None:
            elapsed = (now - _last_email_at).total_seconds()
            if elapsed < config.MIN_EMAIL_INTERVAL_SECONDS:
                log.info("Email пропуснат - минималният интервал (%ds) не е минал още (%.0fs).",
                          config.MIN_EMAIL_INTERVAL_SECONDS, elapsed)
                return False

        _last_email_at = now
        _emails_sent_today += 1
        return True


def _send_email(subject: str, html: str) -> bool:
    if not config.ALERT_EMAIL_ENABLED:
        log.info("Email пропуснат - ALERT_EMAIL_ENABLED=false.")
        return False
    if not config.RESEND_API_KEY:
        log.error("RESEND_API_KEY не е зададен - не мога да изпратя email.")
        return False

    payload = {
        "from": f"Penny Stock Scanner <{config.RESEND_FROM_EMAIL}>",
        "to": [config.ALERT_EMAIL_TO],
        "subject": subject,
        "html": html,
    }
    headers = {"Authorization": f"Bearer {config.RESEND_API_KEY}"}
    try:
        resp = requests.post(RESEND_URL, json=payload, headers=headers, timeout=20)
        if resp.status_code >= 300:
            log.error("Resend API грешка %s: %s", resp.status_code, resp.text)
            return False
        resend_id = None
        try:
            resend_id = resp.json().get("id")
        except Exception:  # noqa: BLE001
            pass
        log.info("Email приет от Resend: %s (id=%s, to=%s)", subject, resend_id, config.ALERT_EMAIL_TO)
        return True
    except Exception as exc:  # noqa: BLE001
        log.error("Грешка при изпращане на email през Resend: %s", exc)
        return False


def send_alert(label: str, result) -> bool:
    """Алърт за "ВИСОК ПОТЕНЦИАЛ" (или watchlist) от основния confluence
    score (виж scoring.py::ScoreResult). Връща True само ако email-ът
    РЕАЛНО е изпратен - False при throttle (тихи часове/темпо/дневен
    таван) ИЛИ при грешка - main.py пробва пак на следващия цикъл и в
    двата случая."""
    price = (result.raw or {}).get("price") if getattr(result, "raw", None) else None
    reasons_html = "".join(f"<li>{r}</li>" for r in result.reasons)
    price_part = f" @ ${price:,.4f}" if price else ""

    position_note = ""
    if price and config.POSITION_SIZE_EUR:
        shares_note = f"{config.POSITION_SIZE_EUR:.0f}€ позиция, цел {config.TARGET_PROFIT_EUR:.0f}€ (~{config.TARGET_PROFIT_PCT * 100:.0f}%)"
        position_note = f'<p style="font-size:12px; color:#888; margin:-6px 0 14px;">{shares_note} - само информативно, ботът не изпълнява поръчки.</p>'

    catalyst_line = "Да" if result.has_catalyst else "Не"
    dilution_line = "⚠️ ДА - скорошен dilution filing" if getattr(result, "has_dilution_risk", False) else "Не"

    subject = f"🚀 {label}: {result.symbol}{price_part}"
    html = f"""
    <div style="font-family: -apple-system, Arial, sans-serif; max-width: 560px; margin: 0 auto;">
      <div style="background:#e8f5e9; color:#1b5e20; padding:16px 20px; border-radius:10px 10px 0 0;">
        <h2 style="margin:0; font-size:20px;">🚀 {result.symbol}: {label}</h2>
        <p style="margin:4px 0 0; font-size:14px;">Score: {result.score:.0f}/100</p>
      </div>
      <div style="border:1px solid #eee; border-top:none; padding:20px; border-radius:0 0 10px 10px;">
        <table style="width:100%; border-collapse:collapse; font-size:14px; margin-bottom:10px;">
          <tr><td style="padding:4px 0; color:#666;">Цена</td><td style="text-align:right; font-weight:600;">{f"${price:,.4f}" if price else "-"}</td></tr>
          <tr><td style="padding:4px 0; color:#666;">Новина/catalyst</td><td style="text-align:right;">{catalyst_line}</td></tr>
          <tr><td style="padding:4px 0; color:#666;">Dilution риск</td><td style="text-align:right;">{dilution_line}</td></tr>
        </table>
        {position_note}
        <p style="font-size:14px; color:#333; margin-bottom:6px;"><strong>Защо:</strong></p>
        <ul style="font-size:13px; color:#444; margin-top:0; padding-left:18px;">{reasons_html}</ul>
        <p style="font-size:11px; color:#999; margin-top:18px; border-top:1px solid #eee; padding-top:10px;">
          Автоматичен сигнал от technical screening (виж scoring.py/strategies.py за честния backtest зад него).
          Не е финансов съвет - провери сам преди да отвориш позиция.
        </p>
      </div>
    </div>
    """
    if not _throttle_allows_send():
        return False
    return _send_email(subject, html)


def send_price_spike_alert(symbol: str, price_now: float, price_change_pct: float,
                            last_minute_volume: float, avg_prior_volume: float, dollar_volume: float) -> bool:
    """"Ценови скок" v2 алърт (виж main.py::run_price_spike_scan за точната
    спецификация - условие 2+3 вече е проверено ПРЕДИ това извикване).
    Връща True само ако email-ът РЕАЛНО е изпратен."""
    vol_ratio = (last_minute_volume / avg_prior_volume) if avg_prior_volume else 0.0
    subject = f"⚡ Ценови скок: {symbol} @ ${price_now:,.4f} ({price_change_pct:+.1f}%)"
    html = f"""
    <div style="font-family: -apple-system, Arial, sans-serif; max-width: 560px; margin: 0 auto;">
      <div style="background:#fff3e0; color:#e65100; padding:16px 20px; border-radius:10px 10px 0 0;">
        <h2 style="margin:0; font-size:20px;">⚡ {symbol}: Ценови скок</h2>
        <p style="margin:4px 0 0; font-size:14px;">Рязко движение, засечено в реално време</p>
      </div>
      <div style="border:1px solid #eee; border-top:none; padding:20px; border-radius:0 0 10px 10px;">
        <table style="width:100%; border-collapse:collapse; font-size:14px; margin-bottom:16px;">
          <tr><td style="padding:4px 0; color:#666;">Цена сега</td><td style="text-align:right; font-weight:600;">${price_now:,.4f}</td></tr>
          <tr><td style="padding:4px 0; color:#666;">Промяна в цената</td><td style="text-align:right;">{price_change_pct:+.1f}%</td></tr>
          <tr><td style="padding:4px 0; color:#666;">Обем (последна мин.)</td><td style="text-align:right;">{last_minute_volume:,.0f}</td></tr>
          <tr><td style="padding:4px 0; color:#666;">Среден обем (база)</td><td style="text-align:right;">{avg_prior_volume:,.0f} ({vol_ratio:.1f}x)</td></tr>
          <tr><td style="padding:4px 0; color:#666;">Dollar volume</td><td style="text-align:right;">${dollar_volume:,.0f}</td></tr>
        </table>
        <p style="font-size:11px; color:#999; margin-top:18px; border-top:1px solid #eee; padding-top:10px;">
          Условия (виж config.PRICE_SPIKE_*): обем >= {config.PRICE_SPIKE_VOLUME_MULTIPLIER}x средното за последните
          {config.PRICE_SPIKE_VOLUME_LOOKBACK_MINUTES} мин, цена >= {config.PRICE_SPIKE_MIN_PRICE_CHANGE_PCT}% нагоре за
          последните {config.PRICE_SPIKE_PRICE_LOOKBACK_MINUTES} мин. Не е финансов съвет - провери сам.
        </p>
      </div>
    </div>
    """
    if not _throttle_allows_send():
        return False
    return _send_email(subject, html)


def send_telegram_message(text: str) -> bool:
    if not config.TELEGRAM_ENABLED:
        log.info("Telegram пропуснато - TELEGRAM_ENABLED=false.")
        return False
    if not (config.TELEGRAM_BOT_TOKEN and config.TELEGRAM_CHAT_ID):
        log.error("TELEGRAM_BOT_TOKEN или TELEGRAM_CHAT_ID липсват - не мога да изпратя Telegram съобщение.")
        return False
    url = TELEGRAM_URL_TMPL.format(token=config.TELEGRAM_BOT_TOKEN)
    try:
        resp = requests.post(url, json={"chat_id": config.TELEGRAM_CHAT_ID, "text": text}, timeout=15)
        if resp.status_code >= 300:
            log.error("Telegram API грешка %s: %s", resp.status_code, resp.text)
            return False
        log.info("Telegram съобщение изпратено.")
        return True
    except Exception as exc:  # noqa: BLE001
        log.error("Грешка при изпращане на Telegram съобщение: %s", exc)
        return False
