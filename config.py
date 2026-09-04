"""
FarmBridge configuration.

Environment variables are the source of truth for configuration. Keep secrets
out of the repository and use .env / the deployment platform's secret store in
production. Never commit real credentials.
"""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


def _as_bool(value, default=False):
    if value is None:
        return default
    return str(value).strip().lower() in ('1', 'true', 'yes', 'on')


class Config:
    # ---------------------------------------------------------------
    # Application mode
    # development | test | production
    # ---------------------------------------------------------------
    ENVIRONMENT = os.environ.get(
        'ENVIRONMENT', os.environ.get('FLASK_ENV', 'development')
    ).strip().lower()
    APP_BASE_URL = os.environ.get('APP_BASE_URL', 'http://localhost:5000').rstrip('/')

    # Flask debug is disabled by default in production regardless of FLASK_ENV.
    DEBUG = (_as_bool(os.environ.get('FLASK_DEBUG'), False)
             if ENVIRONMENT == 'production'
             else _as_bool(os.environ.get('FLASK_DEBUG'), ENVIRONMENT == 'development'))

    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-only-secret-change-me')
    JWT_ALGORITHM = 'HS256'
    JWT_EXPIRES_HOURS = int(os.environ.get('JWT_EXPIRES_HOURS', 72))

    # ---------------------------------------------------------------
    # Database
    # ---------------------------------------------------------------
    DB_ENGINE = os.environ.get('DB_ENGINE', 'mysql').strip().lower()
    MYSQL_HOST = os.environ.get('MYSQL_HOST', '127.0.0.1')
    MYSQL_PORT = int(os.environ.get('MYSQL_PORT', 3306))
    MYSQL_USER = os.environ.get('MYSQL_USER', 'farmbridge')
    MYSQL_PASSWORD = os.environ.get('MYSQL_PASSWORD', 'change-me')
    MYSQL_DB = os.environ.get('MYSQL_DB', 'farmbridge')
    MYSQL_SSL_MODE = os.environ.get('MYSQL_SSL_MODE', 'preferred').strip().lower()
    MYSQL_CONNECT_TIMEOUT = int(os.environ.get('MYSQL_CONNECT_TIMEOUT', 10))
    # Managed cloud providers usually give the user the database already; many
    # do not grant CREATE DATABASE permission. Set true only if the app user is
    # allowed to create the database (e.g. local Docker MySQL).
    MYSQL_CREATE_DATABASE = _as_bool(os.environ.get('MYSQL_CREATE_DATABASE'), False)
    SQLITE_PATH = os.environ.get('SQLITE_PATH', str(BASE_DIR / 'farmbridge.db'))

    # ---------------------------------------------------------------
    # Storage
    # local | cloudinary
    # ---------------------------------------------------------------
    STORAGE_PROVIDER = os.environ.get('STORAGE_PROVIDER', 'local').strip().lower()
    UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER', str(BASE_DIR / 'uploads'))
    MAX_UPLOAD_SIZE_MB = int(os.environ.get('MAX_UPLOAD_SIZE_MB', 5))
    MAX_UPLOAD_BYTES = MAX_UPLOAD_SIZE_MB * 1024 * 1024
    ALLOWED_IMAGE_TYPES = {
        'image/jpeg',
        'image/png',
        'image/webp',
        'image/gif',
    }

    # Optional Cloudinary (only used when STORAGE_PROVIDER=cloudinary and the
    # credentials are set; absence does not break the app).
    CLOUDINARY_CLOUD_NAME = os.environ.get('CLOUDINARY_CLOUD_NAME', '')
    CLOUDINARY_API_KEY = os.environ.get('CLOUDINARY_API_KEY', '')
    CLOUDINARY_API_SECRET = os.environ.get('CLOUDINARY_API_SECRET', '')

    # ---------------------------------------------------------------
    # Auth / OTP
    # ---------------------------------------------------------------
    OTP_EXPIRY_MINUTES = int(os.environ.get('OTP_EXPIRY_MINUTES', 5))
    SMS_PROVIDER = os.environ.get('SMS_PROVIDER', 'mock').strip().lower()
    MOCK_OTP = os.environ.get('MOCK_OTP', '123456')

    # ---------------------------------------------------------------
    # Ordering / marketplace
    # ---------------------------------------------------------------
    DELIVERY_FEE = float(os.environ.get('DELIVERY_FEE', 25))
    FREE_DELIVERY_ABOVE = float(os.environ.get('FREE_DELIVERY_ABOVE', 500))
    MARKET_REFRESH_SECONDS = int(os.environ.get('MARKET_REFRESH_SECONDS', 30))
    MARKET_PAGE_SIZE = int(os.environ.get('MARKET_PAGE_SIZE', 100))

    # ---------------------------------------------------------------
    # CORS. ALLOWED_ORIGINS overrides CORS_ORIGINS. '*' is the safe default only
    # when this is explicitly set and the value is '*'.
    # ---------------------------------------------------------------
    ALLOWED_ORIGINS = os.environ.get(
        'ALLOWED_ORIGINS', os.environ.get('CORS_ORIGINS', '*')
    )

    @property
    def is_production(self):
        return self.ENVIRONMENT == 'production'

    @property
    def is_test(self):
        return self.ENVIRONMENT == 'test'

    @property
    def allow_sqlite_fallback(self):
        # No silent fallback in production. Tests and local dev may fall back.
        return not self.is_production

    @property
    def allowed_origins_list(self):
        raw = (self.ALLOWED_ORIGINS or '*').strip()
        if raw == '*':
            return ['*']
        return [o.strip() for o in raw.split(',') if o.strip()]


config = Config()
