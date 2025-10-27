import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

class Config:
    SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "dev-secret-key")
    DEBUG = os.getenv("FLASK_DEBUG", "True").lower() == "true"
    # SQLite DB in instance folder by default
    db_path = BASE_DIR / "instance" / "peer_eval.sqlite"
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", f"sqlite:///{db_path}")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Mail (optional)
    MAIL_SERVER = os.getenv("MAIL_SERVER")
    MAIL_PORT = int(os.getenv("MAIL_PORT", "587"))
    MAIL_USERNAME = os.getenv("MAIL_USERNAME")
    MAIL_PASSWORD = os.getenv("MAIL_PASSWORD")
    MAIL_USE_TLS = os.getenv("MAIL_USE_TLS", "True").lower() == "true"
    MAIL_DEFAULT_SENDER = os.getenv("MAIL_DEFAULT_SENDER", "Peer Eval <no-reply@example.com>")

    # NLP Options
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

    # Scoring options
    SCORING_METHOD = os.getenv("SCORING_METHOD", "mean")  # mean|median|trimmed_mean
    SCORING_TRIM_FRACTION = float(os.getenv("SCORING_TRIM_FRACTION", "0.0"))

    # Curve options
    CURVE_ENABLED = os.getenv("CURVE_ENABLED", "True").lower() == "true"
    CURVE_PROTECT_THRESHOLD = float(os.getenv("CURVE_PROTECT_THRESHOLD", "80.0"))
    CURVE_K = float(os.getenv("CURVE_K", "0.5"))

    # Outbox email action target: outlook|mailto|d2l
    EMAIL_LINK_TARGET = os.getenv("EMAIL_LINK_TARGET", "outlook").lower()