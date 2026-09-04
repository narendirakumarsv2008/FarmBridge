"""
AI Quality Grading service.

Grade A : freshness >= 70%  → Premium Export Quality
Grade B : freshness 35-70%  → Good Local Market
Grade C : freshness < 35%   → Quick Sale Recommended

Inputs : crop name, harvest date, optional image (bytes or file path).
Outputs: freshness score, grade, recommendation, shelf life, expiry date.

The "AI" heuristic is deterministic: freshness is derived from the crop's
known shelf life vs. days since harvest, plus a small, honest image-quality
score computed from the actual photo dimensions (no random numbers). The
architecture lets a real ML model be swapped in later.
"""

import base64
import io
import os
import re
from datetime import datetime, timedelta

from utils.validators import parse_harvest_date

# Crop shelf life in days (rough, publicly-known estimates).
CROP_SHELF_LIFE = {
    "tomato": 7, "potato": 45, "onion": 60, "wheat": 180, "rice": 180,
    "paddy": 180, "mango": 10, "banana": 6, "apple": 30, "orange": 21,
    "cabbage": 14, "cauliflower": 10, "brinjal": 7, "eggplant": 7,
    "carrot": 21, "chilli": 10, "chili": 10, "capsicum": 8, "grapes": 7,
    "watermelon": 14, "muskmelon": 10, "sugarcane": 30, "cotton": 90,
    "soybean": 120, "maize": 90, "corn": 90, "groundnut": 60, "mustard": 60,
    "coconut": 30, "turmeric": 60, "ginger": 21, "garlic": 30, "peas": 7,
    "ladyfinger": 7, "okra": 7, "spinach": 5, "cucumber": 7,
}

CROP_LIST = list(CROP_SHELF_LIFE.keys())

_STOP_WORDS = {
    "i", "am", "growing", "my", "farm", "is", "in", "the", "a", "an", "we",
    "are", "have", "has", "this", "that", "crop", "name", "cultivating",
    "grew", "grown", "cultivate",
}


def shelf_life_for(crop_name):
    """Best-match shelf life for a crop name (substring match)."""
    key = (crop_name or "").lower().strip()
    for k, v in CROP_SHELF_LIFE.items():
        if k in key or key in k:
            return v
    return 14  # default


# ---------------------------------------------------------------------------
# Speech/typing extraction helpers (used by both grading and listings)
# ---------------------------------------------------------------------------

def extract_crop_name_smart(text):
    """Extract just the crop name from a sentence (e.g. voice input)."""
    lower = (text or "").lower()
    for crop in CROP_LIST:
        if re.search(rf"\b{re.escape(crop)}\b", lower):
            return crop.capitalize()
    words = re.sub(r"[^a-zA-Z\s]", "", lower).split()
    meaningful = [w for w in words if len(w) > 2 and w not in _STOP_WORDS]
    if meaningful:
        return meaningful[0].capitalize()
    return None


def extract_quantity_kg(text):
    """Extract a quantity and convert it to Kg."""
    lower = (text or "").lower()
    m = re.search(r"(\d+(\.\d+)?)", lower)
    if not m:
        return None
    num = float(m.group(1))
    if "quintal" in lower or "qtl" in lower:
        return int(round(num * 100))
    if "ton" in lower:
        return int(round(num * 1000))
    if "kg" in lower or "kilo" in lower:
        return int(round(num))
    if "gram" in lower or "gm" in lower:
        return max(1, int(round(num / 1000))) if num >= 1000 else max(1, int(round(num / 1000)))
    return int(round(num))


def extract_price_per_kg(text):
    """Extract a price and convert it to ₹/Kg."""
    lower = (text or "").lower()
    m = re.search(r"(\d+(\.\d+)?)", lower)
    if not m:
        return None
    num = float(m.group(1))
    if "quintal" in lower or "qtl" in lower:
        return round(num / 100, 2)
    if "ton" in lower:
        return round(num / 1000, 2)
    return round(num, 2)


def _decode_image(image_data):
    """Accept base64 (with/without data URL prefix) or a file path → bytes."""
    if not image_data:
        return None
    if isinstance(image_data, bytes):
        return image_data
    s = str(image_data)
    if s.startswith("data:") and "," in s:
        s = s.split(",", 1)[1]
    try:
        return base64.b64decode(s)
    except Exception:
        return None


def _image_quality_score(image_bytes):
    """Deterministic 0-10 score from actual image dimensions/file size."""
    if not image_bytes:
        return 0
    try:
        from PIL import Image
        img = Image.open(io.BytesIO(image_bytes))
        width, height = img.size
        pixels = width * height
        score = 0
        if pixels > 500_000:
            score += 5
        elif pixels > 100_000:
            score += 3
        if len(image_bytes) > 200_000:
            score += 3
        elif len(image_bytes) > 50_000:
            score += 1
        return min(score, 10)
    except Exception:
        return 0


def calculate_grade(crop_name, harvest_date_str, image_data=None):
    """
    Compute grade/freshness/shelf-life/expiry for a crop.

    `image_data` may be a base64 data URL or raw bytes. Returns a dict with the
    same keys the frontend expects (grade, grade_desc, grade_color, expiry_date,
    expiry_display, shelf_life, days_since_harvest, remaining_days,
    freshness_score, harvest_date_parsed).
    """
    crop_key = (crop_name or "").lower().strip()
    shelf_life = shelf_life_for(crop_key)

    harvest_date = parse_harvest_date(harvest_date_str)
    if harvest_date is None:
        harvest_date = datetime.now() - timedelta(days=1)

    days_since_harvest = max(0, (datetime.now() - harvest_date).days)
    remaining_days = max(0, shelf_life - days_since_harvest)
    freshness_ratio = remaining_days / shelf_life if shelf_life > 0 else 0
    base_freshness = int(freshness_ratio * 100)

    image_score = _image_quality_score(_decode_image(image_data))
    final_freshness = max(0, min(100, base_freshness + image_score))

    if final_freshness >= 70:
        grade = "A"
        grade_desc = "Premium - Export Quality"
        color = "#16a34a"
    elif final_freshness >= 35:
        grade = "B"
        grade_desc = "Good - Local Market Grade"
        color = "#eab308"
    else:
        grade = "C"
        grade_desc = "Average - Quick Sale Recommended"
        color = "#ef4444"

    expiry_date = harvest_date + timedelta(days=shelf_life)

    return {
        "grade": grade,
        "grade_desc": grade_desc,
        "grade_color": color,
        "expiry_date": expiry_date.strftime("%Y-%m-%d"),
        "expiry_display": expiry_date.strftime("%d %b %Y"),
        "shelf_life": shelf_life,
        "days_since_harvest": days_since_harvest,
        "remaining_days": remaining_days,
        "freshness_score": final_freshness,
        "harvest_date_parsed": harvest_date.strftime("%Y-%m-%d"),
    }
