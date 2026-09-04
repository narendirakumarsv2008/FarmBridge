"""
AI quality grading for crop listings.

The current implementation is a deterministic freshness model based on harvest
age plus a small image-quality heuristic. It is kept out of route handlers so
it can later be replaced with a real vision model without touching the API.
"""

import base64
import io
import re
from datetime import datetime, timedelta

from PIL import Image

# Crop shelf life in days - used for AI grading.
CROP_SHELF_LIFE = {
    'tomato': 7, 'potato': 45, 'onion': 60, 'wheat': 180, 'rice': 180, 'paddy': 180,
    'mango': 10, 'banana': 6, 'apple': 30, 'orange': 21, 'cabbage': 14, 'cauliflower': 10,
    'brinjal': 7, 'eggplant': 7, 'carrot': 21, 'chilli': 10, 'chili': 10, 'capsicum': 8,
    'grapes': 7, 'watermelon': 14, 'muskmelon': 10, 'sugarcane': 30, 'cotton': 90,
    'soybean': 120, 'maize': 90, 'corn': 90, 'groundnut': 60, 'mustard': 60, 'coconut': 30,
    'turmeric': 60, 'ginger': 21, 'garlic': 30, 'peas': 7, 'ladyfinger': 7, 'okra': 7,
    'spinach': 5, 'cucumber': 7,
}

CROP_LIST = list(CROP_SHELF_LIFE.keys())


def shelf_life_for(crop_name):
    crop_key = (crop_name or '').lower().strip()
    for k, v in CROP_SHELF_LIFE.items():
        if k in crop_key or crop_key in k:
            return v
    return 14


def parse_harvest_date(harvest_date_str):
    """Try common date formats and speech-style relative phrases."""
    raw = (harvest_date_str or '').strip()
    if not raw:
        return None
    formats = [
        '%Y-%m-%d', '%d-%m-%Y', '%d/%m/%Y', '%Y/%m/%d',
        '%d %b %Y', '%d %B %Y',
    ]
    for fmt in formats:
        try:
            return datetime.strptime(raw, fmt)
        except (ValueError, TypeError):
            continue
    low = raw.lower()
    now = datetime.now()
    if 'today' in low:
        return now
    if 'yesterday' in low:
        return now - timedelta(days=1)
    if re.search(r'\bdays?\s+ago\b', low):
        m = re.search(r'(\d+)', low)
        if m:
            return now - timedelta(days=int(m.group(1)))
        return now - timedelta(days=2)
    return None


def _image_quality_score(image_data):
    """Small heuristic: resolution bonus + visible-image confidence."""
    if not image_data:
        return 0
    try:
        if ',' in image_data:
            image_data = image_data.split(',', 1)[1]
        img_bytes = base64.b64decode(image_data)
        img = Image.open(io.BytesIO(img_bytes))
        width, height = img.size
        score = 0
        if width * height > 500000:
            score += 5
        # Avoid heavy fake randomness: keep the heuristic stable for the same
        # image. A future model can replace this with a real vision score.
        return min(10, score)
    except Exception:
        return 0


def calculate_grade(crop_name, harvest_date_str, image_data=None):
    shelf_life = shelf_life_for(crop_name)
    harvest_date = parse_harvest_date(harvest_date_str)
    if harvest_date is None:
        harvest_date = datetime.now() - timedelta(days=1)

    days_since_harvest = max(0, (datetime.now() - harvest_date).days)
    remaining_days = max(0, shelf_life - days_since_harvest)
    freshness_ratio = remaining_days / shelf_life if shelf_life > 0 else 0
    freshness_score = int(freshness_ratio * 100)
    image_quality_score = _image_quality_score(image_data)
    final_freshness = max(0, min(100, freshness_score + image_quality_score))

    if final_freshness >= 70:
        grade = 'A'
        grade_desc = 'Premium - Export Quality'
        color = '#16a34a'
    elif final_freshness >= 35:
        grade = 'B'
        grade_desc = 'Good - Local Market Grade'
        color = '#eab308'
    else:
        grade = 'C'
        grade_desc = 'Average - Quick Sale Recommended'
        color = '#ef4444'

    expiry_date = harvest_date + timedelta(days=shelf_life)
    return {
        'grade': grade,
        'grade_desc': grade_desc,
        'grade_color': color,
        'expiry_date': expiry_date.strftime('%Y-%m-%d'),
        'expiry_display': expiry_date.strftime('%d %b %Y'),
        'shelf_life': shelf_life,
        'days_since_harvest': days_since_harvest,
        'remaining_days': remaining_days,
        'freshness_score': final_freshness,
        'harvest_date_parsed': harvest_date.strftime('%Y-%m-%d'),
    }
