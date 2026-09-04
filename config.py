"""
FarmBridge configuration.

Environment variables are the source of truth for configuration. Keep secrets
out of the repository and use .env / the deployment platform's secret store in
production.
"""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


def _as_bool(value, default=False):
    if value is None:
        return default
    return str(value).strip().lower() in ('1', 'true', 'yes', 'on')


class Config:
    # Deployment mode: development | production | test
    ENVIRONMENT = os.environ.get('ENVIRONMENT', os.environ.get('FLASK_ENV', 'development')).strip().lower()
    DEBUG = _as_bool(os.environ.get('FLASK_DEBUG'), ENVIRONMENT == 'development')

    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-only-secret-change-me')
    JWT_ALGORITHM = 'HS256'
    JWT_EXPIRES_HOURS = int(os.environ.get('JWT_EXPIRES_HOURS', 72))

    # Database
    DB_ENGINE = os.environ.get('DB_ENGINE', 'mysql').strip().lower()
    MYSQL_HOST = os.environ.get('MYSQL_HOST', '127.0.0.1')
    MYSQL_PORT = int(os.environ.get('MYSQL_PORT', 3306))
    MYSQL_USER = os.environ.get('MYSQL_USER', 'farmbridge')
    MYSQL_PASSWORD = os.environ.get('MYSQL_PASSWORD', 'change-me')
    MYSQL_DB = os.environ.get('MYSQL_DB', 'farmbridge')
    SQLITE_PATH = os.environ.get('SQLITE_PATH', str(BASE_DIR / 'farmbridge.db'))

    # Uploads
    UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER', str(BASE_DIR / 'uploads'))
    MAX_UPLOAD_SIZE_MB = int(os.environ.get('MAX_UPLOAD_SIZE_MB', 5))
    MAX_UPLOAD_BYTES = MAX_UPLOAD_SIZE_MB * 1024 * 1024
    ALLOWED_IMAGE_TYPES = {
        'image/jpeg',
        'image/png',
        'image/webp',
        'image/gif',
    }

    # Auth / OTP
    OTP_EXPIRY_MINUTES = int(os.environ.get('OTP_EXPIRY_MINUTES', 5))
    SMS_PROVIDER = os.environ.get('SMS_PROVIDER', 'mock').strip().lower()
    MOCK_OTP = os.environ.get('MOCK_OTP', '123456')

    # Ordering
    DELIVERY_FEE = float(os.environ.get('DELIVERY_FEE', 25))
    FREE_DELIVERY_ABOVE = float(os.environ.get('FREE_DELIVERY_ABOVE', 500))
    MARKET_REFRESH_SECONDS = int(os.environ.get('MARKET_REFRESH_SECONDS', 30))

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


config = Config()
