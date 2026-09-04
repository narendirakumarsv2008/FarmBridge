"""
Farm Bridge — application configuration.

All runtime configuration comes from environment variables (optionally loaded
from a `.env` file). Nothing in here is a "secret by default" — secrets must be
provided via the environment, and `.env` is git-ignored.

Environment separation:
  ENVIRONMENT=development  → SQLite fallback is allowed, debug on.
  ENVIRONMENT=production   → MySQL is required (no silent SQLite fallback),
                             debug off, expects a WSGI server (Gunicorn).
"""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


def _load_dotenv():
    """Load .env if python-dotenv is available. Never fails hard."""
    try:
        from dotenv import load_dotenv
        load_dotenv(BASE_DIR / ".env")
    except Exception:
        pass


_load_dotenv()


def _env_bool(name, default=False):
    val = os.environ.get(name)
    if val is None:
        return default
    return val.strip().lower() in ("1", "true", "yes", "on")


class Config:
    """Static configuration object (reads env once at import)."""

    # ------------------------------------------------------------------
    # Runtime
    # ------------------------------------------------------------------
    ENVIRONMENT = os.environ.get(
        "ENVIRONMENT", os.environ.get("FLASK_ENV", "development")
    ).strip().lower()
    if ENVIRONMENT not in ("development", "production", "testing"):
        ENVIRONMENT = "development"

    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-insecure-secret-change-me")

    DEBUG = ENVIRONMENT != "production"
    IS_PRODUCTION = ENVIRONMENT == "production"

    # ------------------------------------------------------------------
    # Database
    # ------------------------------------------------------------------
    DB_ENGINE = os.environ.get("DB_ENGINE", "mysql").strip().lower()
    if DB_ENGINE not in ("mysql", "sqlite"):
        DB_ENGINE = "mysql"

    MYSQL_HOST = os.environ.get("MYSQL_HOST", "127.0.0.1")
    MYSQL_PORT = int(os.environ.get("MYSQL_PORT", "3306"))
    MYSQL_USER = os.environ.get("MYSQL_USER", "farmbridge")
    MYSQL_PASSWORD = os.environ.get("MYSQL_PASSWORD", "")
    MYSQL_DB = os.environ.get("MYSQL_DB", "farmbridge")

    # SQLite file location (development/testing).
    SQLITE_PATH = os.environ.get(
        "SQLITE_PATH", str(BASE_DIR / "farmbridge.db")
    )

    # Whether to fall back to SQLite if MySQL is unreachable.
    # The production rule: fail loudly instead of silently degrading.
    ALLOW_SQLITE_FALLBACK = (
        not IS_PRODUCTION and DB_ENGINE != "sqlite"
    )

    # ------------------------------------------------------------------
    # Uploads
    # ------------------------------------------------------------------
    UPLOAD_FOLDER = os.environ.get("UPLOAD_FOLDER", str(BASE_DIR / "uploads"))
    MAX_CONTENT_LENGTH = int(
        os.environ.get("MAX_CONTENT_LENGTH", str(8 * 1024 * 1024))
    )  # 8 MB total request body
    MAX_IMAGE_BYTES = int(
        os.environ.get("MAX_IMAGE_BYTES", str(5 * 1024 * 1024))
    )  # 5 MB per image
    ALLOWED_IMAGE_TYPES = {
        "jpg", "jpeg", "png", "webp", "gif",
    }

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------
    TOKEN_TTL_SECONDS = int(
        os.environ.get("TOKEN_TTL_SECONDS", str(7 * 24 * 60 * 60))
    )  # 7 days
    OTP_TTL_SECONDS = int(os.environ.get("OTP_TTL_SECONDS", "300"))
    # Fixed mock OTP used in development only.
    MOCK_OTP = os.environ.get("MOCK_OTP", "123456")

    # ------------------------------------------------------------------
    # Misc
    # ------------------------------------------------------------------
    DEFAULT_DELIVERY_FEE = 25
    FREE_DELIVERY_ABOVE = 500
    MARKET_REFRESH_SECONDS = 25
    # HoReCa contract discount (fraction of listing price, e.g. 0.93 → −7%).
    HORECA_CONTRACT_RATE = 0.93


# Convenience singletons used across the app.
UPLOAD_FOLDER = Config.UPLOAD_FOLDER
ALLOWED_IMAGE_TYPES = Config.ALLOWED_IMAGE_TYPES
MAX_IMAGE_BYTES = Config.MAX_IMAGE_BYTES
