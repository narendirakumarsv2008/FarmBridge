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
- Marketplace grid of all farmer listings
- Filters by crop, grade
- Shows AI grade, expiry, Mandi vs Platform price, farmer info
- Place Order → triggers status updates & UPI payout simulation

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

## 🔮 Future
- Integrate real eNAM API, UPI AutoPay, LLM for better voice parsing (Whisper), image disease detection.

Built for farmers, by Farm Bridge 🌾
