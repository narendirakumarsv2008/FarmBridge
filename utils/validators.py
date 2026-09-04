"""
Input validation helpers.

The backend never trusts the frontend: every field is re-validated here before
it is written to the database or used in a calculation.
"""

import re
from datetime import datetime, timedelta


# ---------------------------------------------------------------------------
# Identity fields
# ---------------------------------------------------------------------------

def validate_name(name):
    """Validate a person's name: alphabets and single spaces only."""
    if not name or not str(name).strip():
        return False, "Name is required"
    name = str(name).strip()
    if len(name) < 2:
        return False, "Name must be at least 2 characters"
    if len(name) > 50:
        return False, "Name too long (max 50 chars)"
    if not re.match(r"^[A-Za-z ]+$", name):
        return False, "Name should contain only alphabets and spaces, no numbers/symbols"
    if re.search(r"\s{2,}", name):
        return False, "Multiple spaces not allowed"
    if not re.match(r"^[A-Za-z]+(?: [A-Za-z]+)*$", name):
        return False, "Enter valid name (e.g. Ramesh Kumar)"
    return True, name


def validate_phone(phone):
    """Validate an Indian mobile number. Returns (ok, message, digits)."""
    raw = str(phone or "")
    digits = re.sub(r"\D", "", raw)
    if not digits:
        return False, "Phone required", ""
    if len(digits) != 10:
        return False, f"Phone must be exactly 10 digits (you entered {len(digits)})", ""
    if not re.match(r"^[6-9]\d{9}$", digits):
        return False, "Invalid Indian mobile - should start with 6-9 and be 10 digits", ""
    return True, "", digits


def validate_email(email):
    email = str(email or "").strip()
    if not email:
        return False, "Email is required"
    if not re.match(r"^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$", email):
        return False, "Enter a valid email address"
    return True, email


def validate_address(address, min_len=8):
    address = str(address or "").strip()
    if len(address) < min_len:
        return False, f"Address must be at least {min_len} characters"
    return True, address


def validate_consumer_type(consumer_type):
    consumer_type = str(consumer_type or "").strip()
    # canonical keys are lowercase; accept the legacy title-case too.
    mapping = {
        "individual": "individual",
        "community": "community",
        "horeca": "horeca",
        "individual consumer": "individual",
        "community consumer": "community",
        "horeca consumer": "horeca",
    }
    key = consumer_type.lower()
    if key in mapping:
        return True, mapping[key]
    return False, "Choose Individual, Community or HoReCa"


def validate_pincode(pincode):
    pincode = str(pincode or "").strip()
    if pincode and not re.match(r"^\d{6}$", pincode):
        return False, "Pincode must be 6 digits"
    return True, pincode


# ---------------------------------------------------------------------------
# Crop / quantity / price
# ---------------------------------------------------------------------------

def _positive_number(value, label):
    try:
        num = float(value)
    except (TypeError, ValueError):
        return None, f"{label} must be a number"
    if num <= 0:
        return None, f"{label} must be greater than zero"
    return num, ""


def validate_quantity(value):
    """Quantity must be a positive number; unit is Kg in this app."""
    return _positive_number(value, "Quantity")


def validate_price(value):
    """Price must be a positive number (₹/Kg)."""
    return _positive_number(value, "Price")


# ---------------------------------------------------------------------------
# Date helpers
# ---------------------------------------------------------------------------

def parse_harvest_date(harvest_date_str):
    """Best-effort parse of a harvest date; returns a datetime or None."""
    s = str(harvest_date_str or "").strip()
    if not s:
        return None
    formats = [
        "%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%Y/%m/%d",
        "%d %b %Y", "%d %B %Y",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    low = s.lower()
    now = datetime.now()
    if "today" in low:
        return now
    if "yesterday" in low:
        return now - timedelta(days=1)
    m = re.search(r"(\d+)\s*days?\s*ago", low)
    if m:
        return now - timedelta(days=int(m.group(1)))
    return None
