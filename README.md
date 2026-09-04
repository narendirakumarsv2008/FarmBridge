# 🌾 FARM BRIDGE

**Direct Farm-to-Market AgriTech Platform**

> *Cut the Middleman. Keep the Profit.*

Farm Bridge connects farmers directly with consumers — cutting out unnecessary
middlemen, raising farmer income, and getting consumers fresher produce.

Built with a **Flask (Python)** backend, a **MySQL** central database (SQLite
fallback for local demos), and a single-page **HTML/CSS/JS** frontend featuring
a voice assistant, AI quality grading, and live order tracking.

---

## Problem Statement

Farmers sell through long chains of middlemen and lose a large share of the
final price. Consumers pay more for produce that has travelled through many
hands. Farm Bridge lets a farmer list a crop directly and lets a consumer buy
it from the same shared database — transparently, with AI-assigned quality
grades and live inventory.

## Solution

A single platform with two connected portals over **one central database**:

- **FARMER PORTAL** — list crops (by voice or form), get an AI grade, compare a
  demo market benchmark, track milestone payouts.
- **CONSUMER PORTAL** — three ways to buy: **Individual** (quick commerce),
  **Community** (pool-buy with tier discounts), and **HoReCa** (recurring
  subscriptions + delivery calendar).

The marketplace reads directly from the farmer's listings — no mock products,
no separate databases.

## Features

- 🎙️ **Krishi Sahayak voice assistant** (Web Speech API, English/Hindi) that
  extracts crop, harvest date, quantity, price and location into the listing form.
- 🤖 **AI quality grading** (Grade A/B/C) with freshness score, shelf life and expiry.
- 📊 **Live Mandi comparison** — clearly labeled demo benchmark (ready for a real eNAM source).
- 🧺 **Consumer marketplace** with search, category/grade filters, freshness/price sorting, cart, checkout.
- 🛡️ **Stock-safe ordering** — transactional, overselling is impossible, prices computed server-side.
- 🚚 **Order tracking** with a controlled status flow and a farmer order-management view.
- 🏘️ **Community pool-buy** with server-computed tier discounts (4% / 8% / 12% / 18%).
- 🍽️ **HoReCa subscriptions** with a backend-generated delivery calendar, pause/resume/cancel.
- 🔐 **Phone + OTP auth** (mock OTP in development; SMS-provider hook for production) with signed tokens and role-based authorization.
- 📱 **Mobile App — Under Development** (🚧 coming soon for Android & iOS; the site is fully mobile-friendly today).

## Architecture

```
  Farmer Portal ─┐                     ┌─ Consumer Portal
                 ├─► Flask API ◄──────┤
   (voice, grade,│   routes/ services/ │  (market, orders,
    listings)    │   models/ database/ │   pools, subscriptions)
                 └─────────┬───────────┘
                           ▼
                   Central MySQL (SQLite in dev)
```

```
Frontend (index.html) → fetch('/api/...') → Flask routes → Services → Models → Database
```

## Tech Stack

- **Frontend:** HTML5, Tailwind CSS (CDN), Vanilla JS, Web Speech API
- **Backend:** Python 3.10+, Flask, Flask-Cors
- **Database:** MySQL (PyMySQL) with a transparent SQLite dev fallback
- **Other:** Pillow (image handling), itsdangerous (signed tokens), Gunicorn (production), pytest (tests)

## Project Structure

```
FarmBridge/
├── app.py                  # thin entry point (wires the app together)
├── config.py               # environment-driven configuration
├── db.py                   # compatibility shim → database/db.py
├── index.html              # single-page frontend
├── routes/                 # HTTP endpoints (auth, farmer, consumer, listings, orders, pools, subscriptions, misc)
├── services/               # business logic (grading, mandi, marketplace, order, pool, subscription)
├── models/                 # SQL data access per entity
├── database/               # schema + engine + migrations (buyers→consumers, inventory, order_items)
├── utils/                  # validators, security (tokens/OTP), responses, image upload
├── uploads/                # uploaded crop images (git-ignored)
├── tests/                  # pytest suite (26 tests)
├── docs/                   # PROJECT_ANALYSIS, BACKEND_INTEGRATION_GUIDE, DEPLOYMENT_GUIDE, API_DOCUMENTATION
├── Dockerfile / docker-compose.yml
├── render.yaml             # Render Blueprint (one-click IaC: Flask + MySQL)
├── mysql/Dockerfile        # MySQL 8 image used by the Render private service
├── requirements.txt / .env.example / run.sh
└── tools/mysql_test_server.py   # dev-only MySQL wire-protocol test server
```

## Installation

```bash
git clone <your-repo-url>
cd FarmBridge
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## Environment Setup

```bash
cp .env.example .env            # then edit values
```

Key variables: `ENVIRONMENT` (development/production), `SECRET_KEY`, `DB_ENGINE`,
`MYSQL_*`, `UPLOAD_FOLDER`, `MOCK_OTP`. See `.env.example` for the full list.

## Database

- **MySQL** — recommended for real multi-device use. Create the DB + user
  (see `docs/BACKEND_INTEGRATION_GUIDE.md`), set the `MYSQL_*` vars, and the app
  **creates the schema and runs migrations automatically** on startup.
- **SQLite** — automatic fallback in development (`farmbridge.db`), so demos
  never block. Production never silently falls back.

## Running Locally

```bash
python app.py        # or ./run.sh
# Open http://localhost:5000
```

Production-style: `gunicorn -w 4 -b 0.0.0.0:8000 app:app`

## API Overview

| Area | Endpoints |
|---|---|
| Auth | `POST /api/auth/login`, `POST /api/auth/verify-otp`, `GET /api/auth/me`, `POST /api/auth/logout` |
| Farmer | `GET/PUT /api/farmer/profile`, `GET /api/farmer/orders` |
| Consumer | `GET/POST/PUT /api/consumer/profile` (legacy `/api/buyer/profile` alias) |
| Listings | `POST/GET /api/listings`, `GET/PUT/DELETE /api/listings/<id>` |
| Marketplace | `GET /api/market` |
| Orders | `POST/GET /api/orders`, `GET /api/orders/<id>`, `PUT /api/orders/<id>/status` |
| Pools | `GET /api/pools`, `POST /api/pools/<id>/join` |
| Subscriptions | `POST/GET /api/subscriptions`, `PUT/DELETE /api/subscriptions/<id>`, `GET /api/subscriptions/calendar` |
| Mandi / Grade | `GET /api/mandi-price`, `POST /api/grade` |
| Status | `GET /api/health`, `GET /api/db-info`, `GET /api/stats` |

Full details + curl examples: [`docs/API_DOCUMENTATION.md`](docs/API_DOCUMENTATION.md).

## Deployment

- **Render (one-click):** `render.yaml` Blueprint provisions the Flask web
  service + MySQL together — New → Blueprint → connect repo → Apply.
- **Demo/student:** Render/Railway/PythonAnywhere + an external MySQL host.
- **Docker:** `docker compose up --build`.
- **Production:** Nginx + Gunicorn + MySQL (HTTPS, backups, logging).

See [`docs/DEPLOYMENT_GUIDE.md`](docs/DEPLOYMENT_GUIDE.md).

## Testing

```bash
python -m pytest tests/ -q
```

26 tests cover auth, listings, marketplace, orders, stock reduction,
overselling prevention, unauthorized-access prevention, consumer profile, pool
join, subscriptions, grading, and database initialization (SQLite mode; MySQL
verified via the bundled test server).

## Future Roadmap

- Integrate a real eNAM/Agmarknet mandi price provider.
- Production SMS/OTP provider integration (Twilio/MSG91/…).
- Real UPI payments + payout milestones.
- LLM-based voice parsing (e.g. Whisper) and image-based disease detection.
- Cloud image storage (S3/Cloudinary/Supabase).

## Mobile App

🚧 **Under Development** — the Farm Bridge mobile application for Android & iOS
is coming soon. The website is fully mobile-friendly in the meantime.

---

Built for farmers, by Farm Bridge 🌾
