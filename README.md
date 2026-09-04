# 🌾 FARM BRIDGE

> **Cut the Middleman. Keep the Profit.**

Farm Bridge is a direct farm-to-market AgriTech platform that connects farmers directly with consumers, reducing unnecessary middlemen, increasing farmer income, and giving consumers fresher produce.

---

## Problem

- Farmers often lose a large share of their income to middlemen and multiple market layers.
- Consumers struggle to find transparently priced, freshly harvested produce.
- There is usually no shared system that lets a farmer list a crop on one device and have a consumer see and order it from another device.

## Solution

Farm Bridge provides:

- **Farmer Portal** — voice-first crop listing, AI freshness grading, live Mandi comparison, and order/payment tracking.
- **Consumer Portal** — live marketplace, cart + checkout, order tracking, community pool-buy, and HoReCa recurring subscriptions.
- **Shared central database** — the same MySQL database backs both portals, so a farmer's listing is immediately visible to consumers.

---

## Features

- 🎙️ **Krishi Sahayak voice assistant** (Web Speech API, English/Hindi).
- 🤖 **AI quality grading** — Grade A / B / C with freshness score, shelf life and expiry.
- 📊 **Live Mandi comparison** — clearly labelled demo benchmark, easy to integrate with real eNAM/APMC data later.
- 🧑‍🌾 **Farmer Portal** — crop listing, photo upload, grade card, voice transcript, live payout timeline.
- 🛒 **Consumer Portal** — search, category & grade filters, freshness/price sort, cart, checkout.
- 🚚 **Order tracking** — controlled status flow: Order Placed → Farmer Confirmed → Harvest Packed → Out for Delivery → Delivered.
- 👥 **Community Pool-Buy** — tier discounts (25% → 4%, 50% → 8%, 75% → 12%, 100% → 18%).
- 🍽️ **HoReCa subscriptions** — recurring Daily / Alternate Days / Weekly / Monthly procurements with a delivery calendar.
- 🔐 **Phone + OTP authentication** with JWT tokens and role-aware, protected API endpoints.
- 🛡️ **Transactional stock protection** — no overselling; the backend validates inventory and computes all prices.

---

## Architecture

```
Farmer Portal (browser)
        |
        | POST /api/listings
        v
Flask API (app.py -> routes -> services)
        |
        | transaction
        v
Central MySQL database (shared)
        |
        | GET /api/market
        v
Consumer Portal (browser, another device)
```

The frontend is a single-page HTML app (`index.html`). The backend is a modular Flask app. See [`docs/BACKEND_INTEGRATION_GUIDE.md`](docs/BACKEND_INTEGRATION_GUIDE.md) and [`docs/API_DOCUMENTATION.md`](docs/API_DOCUMENTATION.md).

## Tech Stack

- **Frontend**: HTML5, Tailwind CSS CDN, Vanilla JS, Web Speech API, Google Fonts.
- **Backend**: Python 3.11, Flask, PyMySQL, Pillow, PyJWT.
- **Database**: MySQL 8 for production; SQLite for local development and tests.
- **Tests**: pytest.

---

## Project Structure

```
FarmBridge/
├── app.py                     # Flask app factory + server entrypoint
├── config.py                  # Configuration from environment
├── database/
│   ├── db.py                  # Connection layer + schema/migrations
│   └── __init__.py
├── routes/                    # API blueprints
│   ├── auth.py                # Phone + OTP auth
│   ├── consumer.py            # Consumer profile (Consumer Portal)
│   ├── farmer.py              # Farmer profile / orders
│   ├── listings.py            # Farmer listing CRUD
│   ├── orders.py              # Order placement & status
│   ├── pools.py               # Community pools
│   ├── subscriptions.py       # HoReCa subscriptions
│   ├── market.py              # GET /api/market
│   └── mandi.py               # Mandi benchmark + AI grading
├── services/                  # Business logic
│   ├── auth_service.py
│   ├── grading_service.py
│   ├── mandi_service.py
│   ├── marketplace_service.py
│   ├── order_service.py
│   ├── consumer_service.py
│   ├── pool_service.py
│   └── subscription_service.py
├── models/                    # Lightweight model helpers
├── utils/                     # validation, security, responses, uploads
├── tests/                     # pytest suite
├── docs/                      # Project analysis, API, deploy guides
├── uploads/                   # Local image storage (git-ignored)
├── Dockerfile
├── docker-compose.yml
└── run.sh
```

---

## Installation

### 1. Prerequisites

- Python 3.11+
- pip
- For production: MySQL 8+ (or use Docker)

### 2. Virtual environment

```bash
python -m venv venv
# Linux / macOS
source venv/bin/activate
# Windows
venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Environment setup

```bash
cp .env.example .env
# Edit .env
```

For local development without MySQL:

```bash
export ENVIRONMENT=development
export DB_ENGINE=sqlite
export SQLITE_PATH=farmbridge.db
```

The app creates the tables automatically on first startup.

### 5. Run locally

```bash
python app.py
# open http://localhost:5000
```

---

## Database

MySQL is the production engine. The schema and lightweight in-place migrations run automatically at startup (`database/db.py`). Key tables:

`users` · `farmers` · `consumers` · `listings` · `orders` · `order_items` · `pools` · `pool_joins` · `subscriptions` · `sessions` · `delivery_tracking`

The legacy `buyers` table is retained for backward compatibility while the app migrates to `consumers`.

**Important:** In production the app does **not** silently fall back to SQLite. If MySQL is unreachable, startup fails with a clear error.

---

## API Overview

| Area | Endpoint | Method |
|---|---|---|
| Auth | `/api/auth/request-otp`, `/api/auth/login`, `/api/auth/me`, `/api/auth/logout` | POST / POST / GET / POST |
| Farmer | `/api/farmer/profile`, `/api/farmer/listings`, `/api/farmer/orders` | GET/PUT, GET, GET |
| Listings | `/api/listings` | GET, POST |
| Listing detail | `/api/listings/<id>` | GET, PUT, DELETE |
| Marketplace | `/api/market` | GET |
| Consumer profile | `/api/consumer/profile` | GET, POST, PUT |
| Buyer alias (deprecated) | `/api/buyer/profile` | GET, POST |
| Orders | `/api/orders` | GET, POST |
| Order status | `/api/orders/<id>/status`, `/api/orders/<id>/advance` | PUT |
| Pools | `/api/pools`, `/api/pools/<id>/join` | GET, POST |
| Subscriptions | `/api/subscriptions`, `/api/subscriptions/<id>`, `/api/subscriptions/calendar` | GET/POST, PUT/DELETE, GET |
| Mandi + grading | `/api/mandi-price`, `/api/grade` | GET, POST |
| System | `/api/db-info`, `/health` | GET |

See [`docs/API_DOCUMENTATION.md`](docs/API_DOCUMENTATION.md).

---

## Testing

```bash
pip install -r requirements.txt
pytest -q
```

The test suite covers authentication, listing creation, marketplace, order placement, stock reduction, overselling prevention, consumer profile, pool join, subscriptions, AI grading, and database initialization.

---

## Deployment

We provide three deployment paths in [`docs/DEPLOYMENT_GUIDE.md`](docs/DEPLOYMENT_GUIDE.md):

1. Simple student/demo deployment (Render / Railway / PythonAnywhere + managed MySQL).
2. Docker with MySQL (`docker compose up --build`).
3. Production architecture: Nginx → Gunicorn → Flask → MySQL, with HTTPS and backups.

---

## Mobile App

🚧 **Mobile App — Under Development**

The Farm Bridge mobile application is currently under development. We are working on bringing the complete Farm Bridge experience to **Android and iOS**. **Coming Soon.**

The website remains fully responsive and mobile-friendly.

---

## Roadmap

- Real eNAM / Agmarknet market data integration.
- Real SMS OTP provider.
- Advanced vision-based image quality / disease scoring.
- Notifications and price history.
- WebSockets / Server-Sent Events for real-time marketplace updates.

## License

See [LICENSE](LICENSE).
