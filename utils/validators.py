"""Input validation helpers shared by all routes/services."""

import re

CONSUMER_TYPES = ('individual', 'community', 'horeca')

_ALLOWED_LISTING_STATUSES = (
    'active', 'low_stock', 'sold_out', 'expired', 'inactive',
)


def validate_name(name):
    if not name or len(name.strip()) < 2:
        return False, 'Name must be at least 2 characters'
    if len(name.strip()) > 50:
        return False, 'Name too long (max 50 chars)'
    if not re.match(r'^[A-Za-z ]+$', name):
        return False, 'Name should contain only alphabets and spaces, no numbers/symbols'
    if re.search(r'\s{2,}', name):
        return False, 'Multiple spaces not allowed'
    return True, ''


def validate_phone(phone):
    digits = re.sub(r'[\s\-]', '', str(phone or ''))
    if not digits:
        return False, 'Phone required', ''
    if not re.match(r'^\d+$', digits):
        return False, 'Phone must contain digits only', ''
    if len(digits) != 10:
        return False, 'Phone must be exactly 10 digits (you entered %d)' % len(digits), ''
    if not re.match(r'^[6-9]\d{9}$', digits):
        return False, 'Invalid Indian mobile - should start with 6-9 and be 10 digits', ''
    return True, '', digits


def validate_email(email):
    email = (email or '').strip()
    if not email:
        return False, 'Email is required'
    if len(email) > 190:
        return False, 'Email too long'
    if not re.match(r'^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$', email):
        return False, 'Enter a valid email address'
    return True, ''


def positive_float(value, field='value', allow_zero=False):
    try:
        num = float(value)
    except (TypeError, ValueError):
        return None, '%s must be a number' % field
    if allow_zero and num >= 0:
        return num, None
    if num <= 0:
        return None, '%s must be greater than zero' % field
    return num, None


def normalize_consumer_type(value):
    v = (value or '').strip().lower()
    if v in ('individual', 'community', 'horeca'):
        return v
    if v in ('individual consumer',):
        return 'individual'
    return None


def validate_consumer_type(value):
    v = normalize_consumer_type(value)
    if not v:
        return False, 'Choose Individual, Community or HoReCa'
    return True, ''


def validate_listing_status(value):
    v = (value or '').strip().lower()
    if v in _ALLOWED_LISTING_STATUSES:
        return True, v
    return False, 'Invalid listing status'
