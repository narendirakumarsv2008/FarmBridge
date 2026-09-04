"""Voice-transcript and free-text crop parsing helpers."""

import re

from services.grading_service import CROP_LIST

_STOP_WORDS = {
    'i', 'am', 'growing', 'my', 'farm', 'is', 'in', 'the', 'a', 'an', 'we',
    'are', 'have', 'has', 'this', 'that', 'crop', 'name', 'cultivating',
    'grew', 'grown', 'and', 'with', 'of', 'to', 'for', 'value', 'price',
    'rupees', 'rupee', 'rs', 'kgh', 'quantity', 'kg', 'kilo', 'kilogram',
    'quintal', 'ton', 'per',
}


def extract_crop_name_smart(text):
    lower = (text or '').lower()
    for crop in CROP_LIST:
        if re.search(r'\b%s\b' % re.escape(crop), lower):
            return crop.capitalize()
    words = re.sub(r'[^a-zA-Z\s]', '', lower).split()
    meaningful = [w for w in words if len(w) > 2 and w not in _STOP_WORDS]
    if meaningful:
        return meaningful[0].capitalize()
    return None


def extract_quantity_kg(text):
    lower = (text or '').lower()
    m = re.search(r'(\d+(\.\d+)?)', lower)
    if not m:
        return None
    num = float(m.group(1))
    if 'quintal' in lower or 'qtl' in lower:
        return int(round(num * 100))
    if 'ton' in lower:
        return int(round(num * 1000))
    if 'kg' in lower or 'kilo' in lower:
        return int(round(num))
    if 'gram' in lower or 'gm' in lower:
        return int(round(num / 1000)) if num >= 1000 else 1
    return int(round(num))


def extract_price_per_kg(text):
    lower = (text or '').lower()
    m = re.search(r'(\d+(\.\d+)?)', lower)
    if not m:
        return None
    num = float(m.group(1))
    if 'quintal' in lower or 'qtl' in lower:
        return round(num / 100, 2)
    if 'ton' in lower:
        return round(num / 1000, 2)
    return round(num, 2)


def clean_crop_name(raw, smart=True):
    """Return a safe, title-cased crop name from typed or spoken input."""
    cleaned = re.sub(r'[^A-Za-z ]', '', (raw or '')).strip()
    cleaned = re.sub(r'\s+', ' ', cleaned)
    if not cleaned:
        return None
    if smart and len(cleaned.split()) > 3:
        extracted = extract_crop_name_smart(cleaned)
        cleaned = extracted or cleaned
    return cleaned.title()
