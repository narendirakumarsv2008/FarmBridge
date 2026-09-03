# 🌾 FARM BRIDGE - Direct Farm to Market Platform

**Stylish, Voice-First AgriTech Platform** built with **HTML + Python (Flask)**

> Cut the Middleman. Keep the Profit. 15-25% higher realization, instant UPI payouts, AI quality grading.

## ✨ Features Implemented

### 1. Stylish Header
- **FARM** → Font: `Syne` Extra Bold 32px, Color `#1a4d1a` (deep farm green)
- **BRIDGE** → Font: `Bricolage Grotesque` Light 38px, Color `#ff6b00` (vibrant orange), Italic, Larger size
- Glassmorphism, gradient logo, live indicators

### 2. Login Page
- Asks for **Name, Phone Number**
- Validation + saves to SQLite + localStorage
- Redirects to portal selection (Farmer / Buyer)

### 3. Portal Selection
- Two premium cards: Farmer & Buyer with hover animations

### 4. Farmer Portal

#### 🎙️ Voice Assistant (Krishi Sahayak)
- Uses **Web Speech API** (Chrome/Edge)
- Sequential flow asking for:
  - Crop name
  - Harvest date (supports "2 days ago", "yesterday", "15 May 2026")
  - Quantity
  - Price
  - Location
- **If any missed, voice asks again** (loop until filled)
- Extracts voice → text → auto-fills form → saves transcript to DB
- Supports Hindi/English + quick buttons for demo

#### 🤖 AI Grading (A/B/C)
- Python backend calculates:
  - Crop shelf life database (tomato 7d, potato 45d, wheat 180d, etc.)
  - `days_since_harvest` vs `shelf_life`
  - Freshness score = remaining/shelf * 100 + image quality heuristic (PIL analysis)
  - **Grade A**: >=70% freshness → Premium Export Quality (Green)
  - **Grade B**: 35-70% → Good Local Market (Yellow)
  - **Grade C**: <35% → Quick Sale Recommended (Red)
  - Expiry date = harvest + shelf_life
- Photo upload → preview → AI grade card

#### 📊 Live Mandi Benchmark vs Direct Payout
- Widget shows:
  - Nearest Mandi Price (from eNAM mock) + trend
  - Your Platform Net Realization (15-25% higher)
  - Visual bar comparison
  - Extra earning per quintal
- Updates every 30s, fetches from `/api/mandi-price`

#### 💸 Live Milestone Payment Tracking
- 4 steps: Order Placed → Produce Picked → Quality Verified at Drop → Instant UPI Payout
- Animated timeline with progress bar
- Simulate button for live demo
- Buyer order triggers auto-progression

### 5. Buyer Portal

#### Onboarding
- **Name & phone auto-filled** from the login session (read-only, marked AUTO)
- Asks for **email address** + **home/delivery address**
- **"Use my current location"** button — browser geolocation + OpenStreetMap reverse
  geocoding auto-fills address, city and pincode (no API key needed)
- Then asks for buyer type: **Individual / Community / HoReCa** → routes to that portal
- Profile saved to `buyers` table, remembered on next visit

#### 5a. Individual Portal (Blinkit/Zepto style)
- Live product grid from the **saved farmer database**
- **Daily live updates** of qty & price (`/api/market` — stable per-day drift so prices
  move once a day), photos, A/B/C grades, harvest timestamp ("Harvested yesterday")
- Stock bar + LOW STOCK badge, ▲▼ price change, mandi price strikethrough & savings
- Category chips, search, grade filter, sort by fresh/price
- **Cart** drawer with qty steppers, free delivery above ₹500
- **Checkout** with UPI / Card / Netbanking / COD
- **Live delivery tracking**: Order Placed → Farmer Confirmed → Harvest Packed →
  Out for Delivery → Delivered (auto-advances, ETA countdown)
- Stock is decremented on the farmer listing when an order is placed

#### 5b. Community Portal (Pool-Buy)
- **Pool-Buy widget** for apartments, housing societies & restaurants
- `Current Pool: 320/500 kg — 18 hrs left to unlock wholesale price` with live countdown
- **Automatic price drops as collective volume grows**:
  25% → −4%, 50% → −8%, 75% → −12%, 100% → **−18% full wholesale**
- Tier markers on the progress bar, "add X kg more to unlock −Y%" nudge
- Join modal previews your new price, total and saving *before* confirming
- Price can only go down; everyone in the pool gets the unlocked rate

#### 5c. HoReCa Portal (Recurring & Scheduled Procurement)
- **New Subscription** builder: produce from live stock, qty/delivery, contract rate
  (7% below retail), frequency (Daily / Alternate Days / Weekly / Monthly),
  weekday picker, time slot, start & end date, live monthly cost preview
- **Delivery Calendar**: month grid auto-generated from active subscriptions,
  month navigation, per-day breakdown, KPIs for deliveries / volume / est. spend
- **Active Plans**: pause, resume or cancel any subscription (calendar updates live)

## 🛠 Tech Stack
- **Frontend**: HTML5, TailwindCSS CDN, Vanilla JS, Web Speech API, Google Fonts
- **Backend**: Python Flask, SQLite, Pillow for image analysis
- **Database**: `farmbridge.db` with listings & users tables

## 🚀 Run Locally

```bash
pip install -r requirements.txt --break-system-packages
python app.py
# Open http://localhost:5000
```

## 📁 Structure (Updated - index.html in root)
```
FarmBridge/
├── index.html           # Full stylish SPA frontend (MAIN - in root, not in folder)
├── app.py               # Flask backend + AI grading logic (serves index.html from root)
├── requirements.txt
├── farmbridge.db        # SQLite (auto-created)
└── README.md
```

## 🎨 Design Highlights
- Glassmorphism cards, farm pattern background
- Gradient badges, shimmer effects
- Voice wave animation, mic pulse
- Responsive, mobile-friendly
- No build step needed

## 🔌 Buyer API Endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| GET/POST | `/api/buyer/profile` | Buyer details (email, address, geo, type) |
| GET | `/api/market` | Live crops from farmer DB (daily qty/price) |
| POST/GET | `/api/orders` | Create / list orders |
| PUT | `/api/orders/<id>/advance` | Advance delivery status |
| GET | `/api/pools` | Active community pools + live tier pricing |
| POST | `/api/pools/<id>/join` | Add volume to a pool |
| GET/POST | `/api/subscriptions` | HoReCa recurring plans |
| PUT/DELETE | `/api/subscriptions/<id>` | Pause / resume / cancel |
| GET | `/api/subscriptions/calendar` | Expanded delivery schedule |

## 🔮 Future
- Integrate real eNAM API, UPI AutoPay, LLM for better voice parsing (Whisper), image disease detection.

Built for farmers, by Farm Bridge 🌾
