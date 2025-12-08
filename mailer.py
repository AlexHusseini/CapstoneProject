"""
Email sending module for the Peer Evaluation System.

This module handles email delivery via SMTP in production, or stores messages
in the DevOutbox table for development/testing when SMTP is not configured.
"""

import smtplib
from email.mime.text import MIMEText
from flask import current_app
from models import db, DevOutbox

def _has_smtp_config():
    """Check if SMTP configuration is available.
    
    Returns True if MAIL_SERVER, MAIL_USERNAME, and MAIL_PASSWORD are all set.
    """
    cfg = current_app.config
    return bool(cfg.get("MAIL_SERVER") and cfg.get("MAIL_USERNAME") and cfg.get("MAIL_PASSWORD"))

def send_email(to_addr: str, subject: str, body: str):
    """Send an email to the specified address.
    
    Args:
        to_addr: Recipient email address
        subject: Email subject line
        body: Email body text
    
    In production (SMTP configured): Sends email via SMTP server.
    In development (no SMTP): Stores email in DevOutbox table for viewing in UI.
    """
    cfg = current_app.config
    if _has_smtp_config():
        # Production mode: send via SMTP
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
        # Development mode: store in outbox table instead of sending
        out = DevOutbox(to_addr=to_addr, subject=subject, body=body)
        db.session.add(out)
        db.session.commit()
        print(f"[DevOutbox] To: {to_addr}\nSubject: {subject}\n{body}\n")
