from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
import os
import base64
import json
from datetime import datetime, timedelta
import random
import re
from PIL import Image
import io

# Serve index.html from main root (not templates folder)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__, template_folder=BASE_DIR, static_folder=BASE_DIR)
CORS(app)

import db as database
from db import get_conn

DB_PATH = database.SQLITE_PATH

# Crop shelf life in days - for AI grading
CROP_SHELF_LIFE = {
    'tomato': 7, 'potato': 45, 'onion': 60, 'wheat': 180, 'rice': 180, 'paddy': 180,
    'mango': 10, 'banana': 6, 'apple': 30, 'orange': 21, 'cabbage': 14, 'cauliflower': 10,
    'brinjal': 7, 'eggplant': 7, 'carrot': 21, 'chilli': 10, 'chili': 10, 'capsicum': 8,
    'grapes': 7, 'watermelon': 14, 'muskmelon': 10, 'sugarcane': 30, 'cotton': 90,
    'soybean': 120, 'maize': 90, 'corn': 90, 'groundnut': 60, 'mustard': 60, 'coconut': 30,
    'turmeric': 60, 'ginger': 21, 'garlic': 30, 'peas': 7, 'ladyfinger': 7, 'okra': 7, 'spinach': 5, 'cucumber': 7
}

CROP_LIST = list(CROP_SHELF_LIFE.keys())

MANDI_PRICES = {
    'tomato': {'price': 22, 'mandi': 'Azadpur Mandi, Delhi', 'trend': '+2.3%'},
    'potato': {'price': 18, 'mandi': 'Agra Mandi, UP', 'trend': '-0.5%'},
    'onion': {'price': 28, 'mandi': 'Lasalgaon Mandi, MH', 'trend': '+5.1%'},
    'wheat': {'price': 24, 'mandi': 'Karnal Mandi, HR', 'trend': '+1.2%'},
    'rice': {'price': 35, 'mandi': 'Karnal Mandi, HR', 'trend': '+0.8%'},
    'mango': {'price': 60, 'mandi': 'Vashi Mandi, MH', 'trend': '+8.2%'},
    'banana': {'price': 25, 'mandi': 'Jalgaon Mandi, MH', 'trend': '+1.5%'},
    'cabbage': {'price': 15, 'mandi': 'Bangalore APMC', 'trend': '-1.2%'},
    'cauliflower': {'price': 20, 'mandi': 'Kolkata Mandi', 'trend': '+3.4%'},
    'brinjal': {'price': 26, 'mandi': 'Chennai Koyambedu', 'trend': '+2.1%'},
    'carrot': {'price': 30, 'mandi': 'Ooty Mandi, TN', 'trend': '+0.9%'},
    'chilli': {'price': 45, 'mandi': 'Guntur Mandi, AP', 'trend': '+6.7%'},
    'grapes': {'price': 55, 'mandi': 'Nashik Mandi, MH', 'trend': '+4.2%'},
}

def init_db():
    return database.init_db()


init_db()

def validate_name(name):
    """Validate name: only alphabets and spaces, no numbers/special symbols"""
    if not name or len(name.strip()) < 2:
        return False, "Name must be at least 2 characters"
    if len(name.strip()) > 50:
        return False, "Name too long (max 50 chars)"
    if not re.match(r'^[A-Za-z ]+$', name):
        return False, "Name should contain only alphabets and spaces, no numbers/symbols"
    if re.search(r'\s{2,}', name):
        return False, "Multiple spaces not allowed"
    if not re.match(r'^[A-Za-z]+(?: [A-Za-z]+)*$', name.strip()):
        return False, "Enter valid name (e.g. Ramesh Kumar)"
    return True, ""

def validate_phone(phone):
    """Validate phone: exactly 10 digits, Indian mobile 6-9 start"""
    digits = re.sub(r'\D', '', phone)
    if len(digits) == 0:
        return False, "Phone required", ""
    if not re.match(r'^\d+$', phone.replace(' ','').replace('-','')):
        # allow only digits check, but we already cleaned
        pass
    if len(digits) != 10:
        return False, f"Phone must be exactly 10 digits (you entered {len(digits)})", ""
    if not re.match(r'^[6-9]\d{9}$', digits):
        return False, "Invalid Indian mobile - should start with 6-9 and be 10 digits", ""
    return True, "", digits

def extract_crop_name_smart(text):
    """Extract only crop name from sentence, not whole sentence"""
    lower = text.lower()
    for crop in CROP_LIST:
        if re.search(rf'\b{re.escape(crop)}\b', lower):
            return crop.capitalize()
    # fallback: first meaningful word
    stop_words = {'i','am','growing','my','farm','is','in','the','a','an','we','are','have','has','this','that','my','crop','name','is','cultivating','grew','grown'}
    words = re.sub(r'[^a-zA-Z\s]', '', lower).split()
    meaningful = [w for w in words if len(w)>2 and w not in stop_words]
    if meaningful:
        return meaningful[0].capitalize()
    return None

def extract_quantity_kg(text):
    """Extract quantity and convert to Kg only"""
    lower = text.lower()
    m = re.search(r'(\d+(\.\d+)?)', lower)
    if not m:
        return None
    num = float(m.group(1))
    if 'quintal' in lower or 'qtl' in lower:
        return int(round(num * 100))
    elif 'ton' in lower:
        return int(round(num * 1000))
    elif 'kg' in lower or 'kilo' in lower:
        return int(round(num))
    elif 'gram' in lower or 'gm' in lower:
        return int(round(num / 1000)) if num>=1000 else max(1, int(round(num/1000)))
    else:
        # assume kg
        return int(round(num))

def extract_price_per_kg(text):
    """Extract price and convert to Rs/Kg only"""
    lower = text.lower()
    m = re.search(r'(\d+(\.\d+)?)', lower)
    if not m:
        return None
    num = float(m.group(1))
    if 'quintal' in lower or 'qtl' in lower:
        return round(num / 100, 2)
    elif 'ton' in lower:
        return round(num / 1000, 2)
    else:
        return round(num, 2)

def calculate_grade(crop_name, harvest_date_str, image_data=None):
    crop_key = crop_name.lower().strip()
    shelf_life = 14
    for k, v in CROP_SHELF_LIFE.items():
        if k in crop_key or crop_key in k:
            shelf_life = v
            break
    try:
        harvest_date = None
        formats = ["%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%Y/%m/%d", "%d %b %Y", "%d %B %Y"]
        for fmt in formats:
            try:
                harvest_date = datetime.strptime(harvest_date_str.strip(), fmt)
                break
            except:
                continue
        if not harvest_date:
            if "today" in harvest_date_str.lower():
                harvest_date = datetime.now()
            elif "yesterday" in harvest_date_str.lower():
                harvest_date = datetime.now() - timedelta(days=1)
            elif "day" in harvest_date_str.lower():
                m = re.search(r'(\d+)', harvest_date_str)
                if m:
                    days = int(m.group(1))
                    harvest_date = datetime.now() - timedelta(days=days)
                else:
                    harvest_date = datetime.now() - timedelta(days=2)
            else:
                harvest_date = datetime.now() - timedelta(days=1)
    except Exception as e:
        print(f"Date parse error: {e}")
        harvest_date = datetime.now() - timedelta(days=1)

    days_since_harvest = (datetime.now() - harvest_date).days
    if days_since_harvest < 0:
        days_since_harvest = 0
    remaining_days = max(0, shelf_life - days_since_harvest)
    freshness_ratio = remaining_days / shelf_life if shelf_life > 0 else 0
    freshness_score = int(freshness_ratio * 100)

    image_quality_score = 0
    if image_data:
        try:
            if ',' in image_data:
                image_data = image_data.split(',')[1]
            img_bytes = base64.b64decode(image_data)
            img = Image.open(io.BytesIO(img_bytes))
            width, height = img.size
            if width * height > 500000:
                image_quality_score += 5
            image_quality_score += random.randint(-5, 10)
        except Exception as e:
            print(f"Image analysis error: {e}")
            image_quality_score = random.randint(-5, 5)

    final_freshness = max(0, min(100, freshness_score + image_quality_score))

    if final_freshness >= 70:
        grade = 'A'; grade_desc = 'Premium - Export Quality'; color = '#16a34a'
    elif final_freshness >= 35:
        grade = 'B'; grade_desc = 'Good - Local Market Grade'; color = '#eab308'
    else:
        grade = 'C'; grade_desc = 'Average - Quick Sale Recommended'; color = '#ef4444'

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
        'harvest_date_parsed': harvest_date.strftime('%Y-%m-%d')
    }

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    name = data.get('name', '').strip()
    phone = data.get('phone', '').strip()
    if not name or not phone:
        return jsonify({'error': 'Name and phone required'}), 400

    valid_name, msg_name = validate_name(name)
    if not valid_name:
        return jsonify({'error': f'Invalid name: {msg_name}'}), 400

    valid_phone, msg_phone, digits = validate_phone(phone)
    if not valid_phone:
        return jsonify({'error': f'Invalid phone: {msg_phone}'}), 400

    conn = get_conn()
    c = conn.cursor()
    c.execute('INSERT INTO users (name, phone, created_at) VALUES (?, ?, ?)',
              (name, digits, datetime.now().isoformat()))
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'name': name, 'phone': digits})

@app.route('/api/db-info', methods=['GET'])
def db_info():
    """Which database is actually backing the app right now."""
    info = database.engine_info()
    try:
        conn = get_conn()
        c = conn.cursor()
        counts = {}
        for t in ('listings', 'buyers', 'orders', 'pools', 'subscriptions'):
            c.execute('SELECT COUNT(*) AS n FROM ' + t)
            counts[t] = _scalar(c.fetchone())
        conn.close()
        info['counts'] = counts
        info['ok'] = True
    except Exception as e:
        info['ok'] = False
        info['error'] = str(e)[:200]
    return jsonify(info)


@app.route('/api/mandi-price', methods=['GET'])
def mandi_price():
    crop = request.args.get('crop', '').lower().strip()
    location = request.args.get('location', '')
    # extract crop name only if sentence passed
    smart_crop = extract_crop_name_smart(crop)
    if smart_crop:
        crop = smart_crop.lower()

    mandi_info = None
    for k, v in MANDI_PRICES.items():
        if k in crop or crop in k:
            mandi_info = v
            break
    if not mandi_info:
        base = random.randint(18, 45)
        mandi_info = {
            'price': base,
            'mandi': f'Nearest APMC - {location[:20] if location else "Local Mandi"}',
            'trend': f'{"+" if random.random() > 0.3 else "-"}{random.uniform(0.5, 6.0):.1f}%'
        }
    uplift = random.uniform(0.15, 0.25)
    platform_price = round(mandi_info['price'] * (1 + uplift), 2)
    return jsonify({
        'crop': crop,
        'mandi_price': mandi_info['price'],
        'mandi_name': mandi_info['mandi'],
        'mandi_trend': mandi_info['trend'],
        'platform_price': platform_price,
        'uplift_percent': round(uplift * 100, 1),
        'extra_earning_per_kg': round(platform_price - mandi_info['price'], 2),
        'extra_earning_per_quintal': round((platform_price - mandi_info['price']) * 100, 2),
        'comparison': {'mandi': mandi_info['price'], 'platform': platform_price}
    })

@app.route('/api/grade', methods=['POST'])
def grade_api():
    data = request.json
    crop_name = data.get('crop_name', '')
    harvest_date = data.get('harvest_date', '')
    photo = data.get('photo', None)
    if not crop_name or not harvest_date:
        return jsonify({'error': 'crop_name and harvest_date required'}), 400
    # smart extract crop name
    smart = extract_crop_name_smart(crop_name)
    if smart:
        crop_name = smart
    result = calculate_grade(crop_name, harvest_date, photo)
    return jsonify(result)

@app.route('/api/listings', methods=['POST'])
def create_listing():
    data = request.json
    print("Received listing:", json.dumps(data)[:800])

    required = ['crop_name', 'harvest_date', 'quantity', 'price', 'location', 'farmer_name', 'phone']
    for field in required:
        if not data.get(field):
            return jsonify({'error': f'Missing field: {field}'}), 400

    # Validate farmer name and phone again
    valid_name, msg_name = validate_name(data.get('farmer_name',''))
    if not valid_name:
        return jsonify({'error': f'Invalid farmer name: {msg_name}'}), 400
    valid_phone, msg_phone, digits = validate_phone(data.get('phone',''))
    if not valid_phone:
        return jsonify({'error': f'Invalid phone: {msg_phone}'}), 400

    crop_name_raw = (data.get('crop_name') or '').strip()
    # Only use smart extraction when the farmer typed a whole sentence
    # (e.g. voice input "I am growing tomato in my farm"). For a short,
    # direct entry we keep exactly what was typed, otherwise multi-word
    # crops get truncated ("Dragon Fruit" -> "Dragon") and the farmer can
    # never find their own listing in the buyer portal.
    cleaned = re.sub(r'[^A-Za-z ]', '', crop_name_raw).strip()
    cleaned = re.sub(r'\s+', ' ', cleaned)
    word_count = len(cleaned.split())
    if word_count > 3:
        crop_name = extract_crop_name_smart(crop_name_raw) or cleaned
        crop_name = re.sub(r'[^A-Za-z ]', '', crop_name).strip()
    else:
        crop_name = cleaned
    if not crop_name:
        return jsonify({'error': 'Enter a valid crop name (letters only)'}), 400
    crop_name = crop_name.title()

    harvest_date_raw = data.get('harvest_date')
    photo = data.get('photo', '')

    # Quantity: must be in Kg only, convert if needed
    qty_raw = str(data.get('quantity'))
    qty_kg = extract_quantity_kg(qty_raw)
    if qty_kg is None:
        # try direct int
        try:
            qty_kg = int(float(qty_raw))
        except:
            return jsonify({'error': 'Quantity must be in Kg only (e.g. 500 Kg). Could not parse'}), 400
    if qty_kg <= 0:
        return jsonify({'error': 'Quantity must be positive Kg'}), 400

    # Price: must be in Rs/Kg only
    price_raw = str(data.get('price'))
    price_per_kg = extract_price_per_kg(price_raw)
    if price_per_kg is None:
        try:
            price_per_kg = round(float(price_raw),2)
        except:
            return jsonify({'error': 'Price must be in Rs/Kg only (e.g. 25 Rs/Kg)'}), 400
    if price_per_kg <= 0:
        return jsonify({'error': 'Price must be positive Rs/Kg'}), 400

    grade_info = calculate_grade(crop_name, harvest_date_raw, photo)

    mandi_resp = MANDI_PRICES.get(crop_name.lower(), None)
    if mandi_resp:
        mandi_price_val = mandi_resp['price']
        mandi_name = mandi_resp['mandi']
    else:
        # Unknown crop: derive a plausible mandi benchmark from the farmer's own
        # asking price instead of a random number, so the comparison makes sense.
        mandi_price_val = round(float(price_per_kg) * random.uniform(1.12, 1.28), 2)
        mandi_name = f"Nearest Mandi - {data.get('location','Local')[:30]}"

    # The buyer always pays exactly what the farmer asked. The mandi figure is a
    # benchmark shown alongside it, never something that overrides the ask.
    platform_price = float(price_per_kg)
    display_platform_price = platform_price

    quantity_str = f"{qty_kg} Kg"

    conn = get_conn()
    c = conn.cursor()
    c.execute('''INSERT INTO listings 
        (farmer_name, phone, crop_name, harvest_date, quantity, price, location, photo, grade, expiry_date, shelf_life, freshness_score, mandi_price, platform_price, mandi_name, status, created_at, voice_transcript)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
        (
            data.get('farmer_name'),
            digits,
            crop_name,
            grade_info['harvest_date_parsed'],
            quantity_str,
            platform_price,
            data.get('location'),
            photo[:100000] if photo else '',
            grade_info['grade'],
            grade_info['expiry_date'],
            grade_info['shelf_life'],
            grade_info['freshness_score'],
            mandi_price_val,
            display_platform_price,
            mandi_name,
            'Order Placed',
            datetime.now().isoformat(),
            data.get('voice_transcript', '')
        ))
    listing_id = c.lastrowid
    conn.commit()
    conn.close()

    return jsonify({
        'success': True,
        'id': listing_id,
        'grade_info': grade_info,
        'mandi_price': mandi_price_val,
        'platform_price': display_platform_price,
        'farmer_price_per_kg': platform_price,
        'quantity_kg': qty_kg,
        'crop_name_extracted': crop_name,
        'mandi_name': mandi_name
    })

@app.route('/api/listings', methods=['GET'])
def get_listings():
    conn = get_conn()
    c = conn.cursor()
    c.execute('SELECT * FROM listings ORDER BY created_at DESC')
    rows = c.fetchall()
    conn.close()
    listings = [dict(r) for r in rows]
    return jsonify(listings)

@app.route('/api/listings/<int:listing_id>/status', methods=['PUT'])
def update_status(listing_id):
    data = request.json
    new_status = data.get('status')
    valid_statuses = ['Order Placed', 'Produce Picked', 'Quality Verified at Drop', 'Instant UPI Payout']
    if new_status not in valid_statuses:
        return jsonify({'error': 'Invalid status'}), 400
    conn = get_conn()
    c = conn.cursor()
    c.execute('UPDATE listings SET status=? WHERE id=?', (new_status, listing_id))
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'status': new_status})

@app.route('/api/stats', methods=['GET'])
def stats():
    conn = get_conn()
    c = conn.cursor()
    c.execute('SELECT COUNT(*) FROM listings')
    total = _scalar(c.fetchone())
    c.execute('SELECT COUNT(*) FROM listings WHERE grade="A"')
    grade_a = _scalar(c.fetchone())
    c.execute('SELECT SUM(platform_price) FROM listings')
    total_value = _scalar(c.fetchone()) or 0
    conn.close()
    return jsonify({
        'total_listings': total,
        'grade_a_count': grade_a,
        'total_value': round(total_value, 2),
        'farmers_connected': total * 3 + 1247,
        'avg_uplift': '18.7%'
    })


# ==========================================================
#  BUYER PORTAL  —  profile, market, cart/orders,
#                   community pool-buy, HoReCa subscriptions
# ==========================================================

POOL_TIERS = [
    (0,   0,  'Base price'),
    (25,  4,  'Early pool bonus'),
    (50,  8,  'Half batch unlocked'),
    (75,  12, 'Bulk rate unlocked'),
    (100, 18, 'Full wholesale price'),
]

DELIVERY_FEE = 25
FREE_DELIVERY_ABOVE = 500


def _row_to_dict(r):
    if r is None:
        return None
    if isinstance(r, dict):
        return dict(r)
    return {k: r[k] for k in r.keys()}


def _scalar(row):
    """First column of a row, for both dict and tuple cursors."""
    if row is None:
        return None
    if isinstance(row, dict):
        return next(iter(row.values()))
    return row[0]


def _daily_seed(key):
    """Stable pseudo-random per (key, day) so prices move once a day."""
    today = datetime.now().strftime('%Y-%m-%d')
    return random.Random(f'{key}-{today}')


def live_price_for(listing):
    """Daily-updating live price derived from the farmer's listed price."""
    base = float(listing.get('platform_price') or listing.get('price') or 0)
    rnd = _daily_seed(f"price-{listing.get('id')}")
    drift = rnd.uniform(-0.06, 0.08)
    live = round(max(1.0, base * (1 + drift)), 2)
    return live, round((live - base) / base * 100, 1) if base else 0.0


def available_kg(listing):
    """Remaining stock = listed qty - sold, with a daily demand nibble."""
    try:
        total = int(re.sub(r'\D', '', str(listing.get('quantity') or '0')) or 0)
    except Exception:
        total = 0
    sold = int(listing.get('sold_kg') or 0)
    rnd = _daily_seed(f"demand-{listing.get('id')}")
    nibble = int(total * rnd.uniform(0.02, 0.18))
    return max(0, total - sold - nibble), total


def enrich_listing(l):
    live, change = live_price_for(l)
    avail, total = available_kg(l)
    harvest = l.get('harvest_date') or ''
    try:
        hd = datetime.strptime(harvest, '%Y-%m-%d')
        age_days = (datetime.now() - hd).days
        harvest_display = hd.strftime('%d %b %Y')
    except Exception:
        age_days = 0
        harvest_display = harvest
    if age_days <= 0:
        freshness_label = 'Harvested today'
    elif age_days == 1:
        freshness_label = 'Harvested yesterday'
    else:
        freshness_label = f'Harvested {age_days} days ago'
    mandi = float(l.get('mandi_price') or 0)
    l.update({
        'live_price': live,
        'price_change_pct': change,
        'available_kg': avail,
        'total_kg': total,
        'stock_pct': round((avail / total) * 100) if total else 0,
        'harvest_display': harvest_display,
        'harvest_age_days': age_days,
        'freshness_label': freshness_label,
        'mandi_price': mandi,
        'savings_vs_mandi': round(mandi - live, 2) if mandi else 0,
        'unit': 'Kg',
    })
    return l


@app.route('/api/buyer/profile', methods=['GET'])
def get_buyer_profile():
    phone = request.args.get('phone', '').strip()
    if not phone:
        return jsonify({'error': 'phone required'}), 400
    conn = get_conn()
    c = conn.cursor()
    c.execute('SELECT * FROM buyers WHERE phone=?', (phone,))
    row = c.fetchone()
    conn.close()
    if not row:
        return jsonify({'found': False})
    return jsonify({'found': True, 'profile': _row_to_dict(row)})


@app.route('/api/buyer/profile', methods=['POST'])
def save_buyer_profile():
    data = request.json or {}
    name = (data.get('name') or '').strip()
    phone = re.sub(r'\D', '', data.get('phone') or '')
    email = (data.get('email') or '').strip()
    address = (data.get('address') or '').strip()
    buyer_type = (data.get('buyer_type') or '').strip()

    if not name or not phone:
        return jsonify({'error': 'Name and phone come from login and are required'}), 400
    ok, msg, digits = validate_phone(phone)
    if not ok:
        return jsonify({'error': f'Invalid phone: {msg}'}), 400
    if not re.match(r'^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$', email):
        return jsonify({'error': 'Enter a valid email address'}), 400
    if len(address) < 8:
        return jsonify({'error': 'Home address must be at least 8 characters'}), 400
    if buyer_type not in ('Individual', 'Community', 'HoReCa'):
        return jsonify({'error': 'Choose Individual, Community or HoReCa'}), 400

    now = datetime.now().isoformat()
    conn = get_conn()
    c = conn.cursor()
    c.execute("""INSERT INTO buyers
        (phone,name,email,address,landmark,city,pincode,latitude,longitude,buyer_type,org_name,created_at,updated_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(phone) DO UPDATE SET
          name=excluded.name, email=excluded.email, address=excluded.address,
          landmark=excluded.landmark, city=excluded.city, pincode=excluded.pincode,
          latitude=excluded.latitude, longitude=excluded.longitude,
          buyer_type=excluded.buyer_type, org_name=excluded.org_name, updated_at=excluded.updated_at""",
        (digits, name, email, address, data.get('landmark', ''), data.get('city', ''),
         data.get('pincode', ''), data.get('latitude'), data.get('longitude'),
         buyer_type, data.get('org_name', ''), now, now))
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'profile': {
        'phone': digits, 'name': name, 'email': email, 'address': address,
        'buyer_type': buyer_type, 'org_name': data.get('org_name', '')
    }})


@app.route('/api/market', methods=['GET'])
def market():
    """All crops from the saved farmer database with live qty/price."""
    conn = get_conn()
    c = conn.cursor()
    c.execute('SELECT * FROM listings ORDER BY created_at DESC')
    rows = [_row_to_dict(r) for r in c.fetchall()]
    conn.close()
    items = [enrich_listing(l) for l in rows]
    # Every farmer's produce stays visible. Sold-out items are flagged, not
    # removed, so a farmer always sees their listing in the buyer portal.
    for i in items:
        i['sold_out'] = i['available_kg'] <= 0
    return jsonify({
        'items': items,
        'count': len(items),
        'updated_at': datetime.now().isoformat(),
        'next_price_refresh': (datetime.now().replace(hour=0, minute=0, second=0) + timedelta(days=1)).isoformat()
    })


@app.route('/api/orders', methods=['POST'])
def create_order():
    data = request.json or {}
    items = data.get('items') or []
    phone = re.sub(r'\D', '', data.get('buyer_phone') or '')
    if not items:
        return jsonify({'error': 'Cart is empty'}), 400
    if not phone:
        return jsonify({'error': 'Buyer phone required'}), 400

    subtotal = 0.0
    for it in items:
        subtotal += float(it.get('price', 0)) * float(it.get('qty', 0))
    subtotal = round(subtotal, 2)
    discount = round(float(data.get('discount') or 0), 2)
    delivery = 0 if subtotal >= FREE_DELIVERY_ABOVE else DELIVERY_FEE
    total = round(subtotal - discount + delivery, 2)

    order_code = 'FB' + datetime.now().strftime('%y%m%d') + str(random.randint(1000, 9999))
    eta = random.randint(12, 25)
    now = datetime.now().isoformat()

    conn = get_conn()
    c = conn.cursor()
    c.execute("""INSERT INTO orders
        (order_code,buyer_phone,buyer_name,buyer_type,items,subtotal,delivery_fee,discount,total,
         payment_method,payment_status,status,address,eta_minutes,source,created_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (order_code, phone, data.get('buyer_name', ''), data.get('buyer_type', 'Individual'),
         json.dumps(items), subtotal, delivery, discount, total,
         data.get('payment_method', 'UPI'),
         'Paid' if data.get('payment_method') != 'COD' else 'Pay on delivery',
         'Order Placed', data.get('address', ''), eta,
         data.get('source', 'individual'), now))
    oid = c.lastrowid
    # decrement farmer stock
    for it in items:
        if it.get('listing_id'):
            c.execute('UPDATE listings SET sold_kg = COALESCE(sold_kg,0) + ? WHERE id=?',
                      (int(it.get('qty', 0)), int(it['listing_id'])))
    conn.commit()
    conn.close()

    return jsonify({'success': True, 'id': oid, 'order_code': order_code,
                    'subtotal': subtotal, 'delivery_fee': delivery, 'discount': discount,
                    'total': total, 'eta_minutes': eta, 'status': 'Order Placed'})


ORDER_FLOW = ['Order Placed', 'Farmer Confirmed', 'Harvest Packed',
              'Out for Delivery', 'Delivered']


@app.route('/api/orders', methods=['GET'])
def list_orders():
    phone = request.args.get('phone', '').strip()
    conn = get_conn()
    c = conn.cursor()
    if phone:
        c.execute('SELECT * FROM orders WHERE buyer_phone=? ORDER BY id DESC', (phone,))
    else:
        c.execute('SELECT * FROM orders ORDER BY id DESC')
    rows = []
    for r in c.fetchall():
        d = _row_to_dict(r)
        try:
            d['items'] = json.loads(d['items'])
        except Exception:
            d['items'] = []
        d['flow'] = ORDER_FLOW
        d['step_index'] = ORDER_FLOW.index(d['status']) if d['status'] in ORDER_FLOW else 0
        rows.append(d)
    conn.close()
    return jsonify(rows)


@app.route('/api/orders/<int:order_id>/advance', methods=['PUT'])
def advance_order(order_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute('SELECT status FROM orders WHERE id=?', (order_id,))
    row = c.fetchone()
    if not row:
        conn.close()
        return jsonify({'error': 'Order not found'}), 404
    cur = _row_to_dict(row)['status']
    idx = ORDER_FLOW.index(cur) if cur in ORDER_FLOW else 0
    nxt = ORDER_FLOW[min(idx + 1, len(ORDER_FLOW) - 1)]
    c.execute('UPDATE orders SET status=? WHERE id=?', (nxt, order_id))
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'status': nxt,
                    'step_index': ORDER_FLOW.index(nxt), 'flow': ORDER_FLOW})


# ----------------------- COMMUNITY POOL-BUY -----------------------

def pool_discount(pct_filled):
    disc, label = 0, 'Base price'
    for threshold, d, lbl in POOL_TIERS:
        if pct_filled >= threshold:
            disc, label = d, lbl
    return disc, label


def next_tier(pct_filled):
    for threshold, d, lbl in POOL_TIERS:
        if pct_filled < threshold:
            return {'at_pct': threshold, 'discount': d, 'label': lbl}
    return None


def seed_pools_if_needed():
    """Create a live pool for the freshest listings so the widget always has data."""
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM pools WHERE status='open'")
    if (_scalar(c.fetchone()) or 0) >= 3:
        conn.close()
        return
    c.execute('SELECT * FROM listings ORDER BY created_at DESC LIMIT 6')
    listings = [_row_to_dict(r) for r in c.fetchall()]
    for l in listings:
        c.execute("SELECT COUNT(*) FROM pools WHERE listing_id=? AND status='open'", (l['id'],))
        if _scalar(c.fetchone()):
            continue
        rnd = _daily_seed(f"pool-{l['id']}")
        target = rnd.choice([300, 500, 750, 1000])
        seeded = int(target * rnd.uniform(0.25, 0.72))
        ends = datetime.now() + timedelta(hours=rnd.randint(6, 36))
        c.execute("""INSERT INTO pools
            (crop_name,listing_id,photo,grade,base_price,target_kg,seeded_kg,ends_at,location,farmer_name,status,created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (l['crop_name'], l['id'], l.get('photo', ''), l.get('grade', 'A'),
             float(l.get('platform_price') or l.get('price') or 20), target, seeded,
             ends.isoformat(), l.get('location', ''), l.get('farmer_name', ''),
             'open', datetime.now().isoformat()))
    conn.commit()
    conn.close()


@app.route('/api/pools', methods=['GET'])
def get_pools():
    seed_pools_if_needed()
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM pools WHERE status='open' ORDER BY id DESC")
    pools = [_row_to_dict(r) for r in c.fetchall()]
    out = []
    for p in pools:
        c.execute('SELECT COALESCE(SUM(qty_kg),0) FROM pool_joins WHERE pool_id=?', (p['id'],))
        joined = _scalar(c.fetchone()) or 0
        c.execute('SELECT COUNT(DISTINCT buyer_phone) FROM pool_joins WHERE pool_id=?', (p['id'],))
        members = _scalar(c.fetchone()) or 0
        current = int(p['seeded_kg']) + int(joined)
        pct = min(100, round(current / p['target_kg'] * 100)) if p['target_kg'] else 0
        disc, label = pool_discount(pct)
        base = float(p['base_price'])
        price_now = round(base * (1 - disc / 100), 2)
        try:
            ends = datetime.fromisoformat(p['ends_at'])
        except Exception:
            ends = datetime.now() + timedelta(hours=12)
        secs_left = max(0, int((ends - datetime.now()).total_seconds()))
        nt = next_tier(pct)
        kg_to_next = 0
        if nt:
            kg_to_next = max(0, int(p['target_kg'] * nt['at_pct'] / 100) - current)
        p.update({
            'current_kg': current, 'members': members + 3, 'pct': pct,
            'discount_pct': disc, 'tier_label': label,
            'price_now': price_now, 'base_price': base,
            'seconds_left': secs_left, 'hours_left': round(secs_left / 3600, 1),
            'unlocked': pct >= 100, 'next_tier': nt, 'kg_to_next_tier': kg_to_next,
            'tiers': [{'at_pct': t[0], 'discount': t[1], 'label': t[2],
                       'price': round(base * (1 - t[1] / 100), 2)} for t in POOL_TIERS],
        })
        out.append(p)
    conn.close()
    return jsonify(out)


@app.route('/api/pools/<int:pool_id>/join', methods=['POST'])
def join_pool(pool_id):
    data = request.json or {}
    qty = int(data.get('qty_kg') or 0)
    if qty <= 0:
        return jsonify({'error': 'Enter quantity in Kg to pool'}), 400
    conn = get_conn()
    c = conn.cursor()
    c.execute("""INSERT INTO pool_joins (pool_id,buyer_phone,buyer_name,org_name,qty_kg,joined_at)
                 VALUES (?,?,?,?,?,?)""",
              (pool_id, re.sub(r'\D', '', data.get('buyer_phone') or ''),
               data.get('buyer_name', ''), data.get('org_name', ''), qty,
               datetime.now().isoformat()))
    conn.commit()
    conn.close()
    return jsonify({'success': True})


# ----------------------- HoReCa SUBSCRIPTIONS -----------------------

@app.route('/api/subscriptions', methods=['POST'])
def create_subscription():
    data = request.json or {}
    phone = re.sub(r'\D', '', data.get('buyer_phone') or '')
    crop = (data.get('crop_name') or '').strip()
    qty = int(data.get('qty_kg') or 0)
    freq = data.get('frequency') or 'Weekly'
    weekdays = data.get('weekdays') or []
    if not phone or not crop or qty <= 0:
        return jsonify({'error': 'Crop, quantity (Kg) and buyer are required'}), 400
    if freq in ('Weekly', 'Custom') and not weekdays:
        return jsonify({'error': 'Pick at least one delivery day'}), 400

    conn = get_conn()
    c = conn.cursor()
    c.execute("""INSERT INTO subscriptions
        (buyer_phone,buyer_name,org_name,crop_name,listing_id,qty_kg,price_per_kg,frequency,
         weekdays,time_slot,start_date,end_date,active,created_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (phone, data.get('buyer_name', ''), data.get('org_name', ''), crop,
         data.get('listing_id'), qty, float(data.get('price_per_kg') or 0), freq,
         json.dumps(weekdays), data.get('time_slot', '6:00 AM - 8:00 AM'),
         data.get('start_date') or datetime.now().strftime('%Y-%m-%d'),
         data.get('end_date', ''), 1, datetime.now().isoformat()))
    sid = c.lastrowid
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'id': sid})


@app.route('/api/subscriptions', methods=['GET'])
def list_subscriptions():
    phone = request.args.get('phone', '').strip()
    conn = get_conn()
    c = conn.cursor()
    if phone:
        c.execute('SELECT * FROM subscriptions WHERE buyer_phone=? ORDER BY id DESC', (phone,))
    else:
        c.execute('SELECT * FROM subscriptions ORDER BY id DESC')
    subs = []
    for r in c.fetchall():
        d = _row_to_dict(r)
        try:
            d['weekdays'] = json.loads(d['weekdays'] or '[]')
        except Exception:
            d['weekdays'] = []
        subs.append(d)
    conn.close()
    return jsonify(subs)


@app.route('/api/subscriptions/<int:sub_id>', methods=['PUT'])
def toggle_subscription(sub_id):
    data = request.json or {}
    conn = get_conn()
    c = conn.cursor()
    if 'active' in data:
        c.execute('UPDATE subscriptions SET active=? WHERE id=?',
                  (1 if data['active'] else 0, sub_id))
    if 'qty_kg' in data:
        c.execute('UPDATE subscriptions SET qty_kg=? WHERE id=?',
                  (int(data['qty_kg']), sub_id))
    conn.commit()
    conn.close()
    return jsonify({'success': True})


@app.route('/api/subscriptions/<int:sub_id>', methods=['DELETE'])
def delete_subscription(sub_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute('DELETE FROM subscriptions WHERE id=?', (sub_id,))
    conn.commit()
    conn.close()
    return jsonify({'success': True})


WEEKDAY_NAMES = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']


@app.route('/api/subscriptions/calendar', methods=['GET'])
def subscription_calendar():
    """Expand active subscriptions into scheduled deliveries for N days."""
    phone = request.args.get('phone', '').strip()
    days = int(request.args.get('days') or 30)
    conn = get_conn()
    c = conn.cursor()
    if phone:
        c.execute('SELECT * FROM subscriptions WHERE buyer_phone=? AND active=1', (phone,))
    else:
        c.execute('SELECT * FROM subscriptions WHERE active=1')
    subs = [_row_to_dict(r) for r in c.fetchall()]
    conn.close()

    schedule = {}
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    for sub in subs:
        try:
            wd = json.loads(sub.get('weekdays') or '[]')
        except Exception:
            wd = []
        try:
            start = datetime.strptime(sub['start_date'], '%Y-%m-%d')
        except Exception:
            start = today
        for i in range(days):
            day = today + timedelta(days=i)
            if day < start:
                continue
            name = WEEKDAY_NAMES[day.weekday()]
            hit = False
            if sub['frequency'] == 'Daily':
                hit = True
            elif sub['frequency'] in ('Weekly', 'Custom'):
                hit = name in wd
            elif sub['frequency'] == 'Alternate Days':
                hit = ((day - start).days % 2) == 0
            elif sub['frequency'] == 'Monthly':
                hit = day.day == start.day
            if hit:
                key = day.strftime('%Y-%m-%d')
                schedule.setdefault(key, []).append({
                    'sub_id': sub['id'], 'crop_name': sub['crop_name'],
                    'qty_kg': sub['qty_kg'], 'price_per_kg': sub['price_per_kg'],
                    'time_slot': sub['time_slot'],
                    'amount': round(float(sub['qty_kg']) * float(sub['price_per_kg'] or 0), 2),
                })
    total_kg = sum(d['qty_kg'] for v in schedule.values() for d in v)
    total_amt = sum(d['amount'] for v in schedule.values() for d in v)
    return jsonify({'schedule': schedule, 'days': days,
                    'total_kg': total_kg, 'total_amount': round(total_amt, 2),
                    'delivery_count': sum(len(v) for v in schedule.values())})


if __name__ == '__main__':
    # index.html is now in main root, not templates
    port = int(os.environ.get('PORT', 5000))
    print(f"""
    🌾 FARM BRIDGE Server Starting...
    =================================
    → Local: http://localhost:{port}
    → Network: http://0.0.0.0:{port}
    → Database: {database.engine_info()['engine'].upper()} → {database.engine_info()['target']}
    → Validation: Name alphabets only, Phone exactly 10 digits
    → Farmer: Crop name only extraction, Qty Kg only, Price ₹/Kg only
    =================================
    """)
    app.run(host='0.0.0.0', port=port, debug=True)
