"""
Изпращане на алърти. Засега два канала:
  - лог (винаги, вижда се в Railway "Logs" таба)
  - email през Gmail SMTP (само ако ALERT_EMAIL_ENABLED=true и SMTP_* попълнени)

Забележка: Gmail изисква "App Password" (не обикновената парола) - виж
README.md за стъпките за настройка.
"""
import logging
import smtplib
from email.mime.text import MIMEText

import config
from scoring import ScoreResult

log = logging.getLogger("notifier")


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


def send_alert(kind: str, result: ScoreResult):
    message = format_alert(kind, result)
    log.info("ALERT:\n%s", message)

    if config.ALERT_EMAIL_ENABLED:
        _send_email(subject=f"[Penny Stock Scanner] {result.symbol} - {kind}", body=message)


def _send_email(subject: str, body: str):
    if not (config.SMTP_USERNAME and config.SMTP_APP_PASSWORD and config.ALERT_EMAIL_TO):
        log.warning("Email алъртите са включени, но SMTP_* или ALERT_EMAIL_TO не са попълнени.")
        return
    msg = MIMEText(body, _charset="utf-8")
    msg["Subject"] = subject
    msg["From"] = config.SMTP_USERNAME
    msg["To"] = config.ALERT_EMAIL_TO
    try:
        with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT) as server:
            server.starttls()
            server.login(config.SMTP_USERNAME, config.SMTP_APP_PASSWORD)
            server.send_message(msg)
        log.info("Email алърт изпратен до %s", config.ALERT_EMAIL_TO)
    except Exception as e:
        log.error("Изпращането на email се провали: %s", e)
