import smtplib
from email.mime.text import MIMEText
from flask import current_app
from models import db, DevOutbox

def _has_smtp_config():
    cfg = current_app.config
    return bool(cfg.get("MAIL_SERVER") and cfg.get("MAIL_USERNAME") and cfg.get("MAIL_PASSWORD"))

def send_email(to_addr: str, subject: str, body: str):
    cfg = current_app.config
    if _has_smtp_config():
        msg = MIMEText(body, "plain", "utf-8")
        msg["Subject"] = subject
        msg["From"] = cfg.get("MAIL_DEFAULT_SENDER")
        msg["To"] = to_addr
        with smtplib.SMTP(cfg["MAIL_SERVER"], cfg["MAIL_PORT"]) as server:
            if cfg.get("MAIL_USE_TLS", True):
                server.starttls()
            server.login(cfg["MAIL_USERNAME"], cfg["MAIL_PASSWORD"])
            server.send_message(msg)
    else:
        # Dev mode: store in outbox
        out = DevOutbox(to_addr=to_addr, subject=subject, body=body)
        db.session.add(out)
        db.session.commit()
        print(f"[DevOutbox] To: {to_addr}\nSubject: {subject}\n{body}\n")
