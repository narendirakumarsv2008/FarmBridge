# FARM BRIDGE — Project Analysis (Pre-Refactor)

> This document describes the **actual state of the repository before the backend
> refactor and the Buyer → Consumer terminology migration**. It is based on a
> line-by-line reading of the source code, not assumptions.
>
> Baseline commit: `6f4cb3a` ("Fix farmer crops missing from buyer portal").
> Files inspected: `app.py`, `db.py`, `index.html`, `README.md`,
> `requirements.txt`, `.env.example`, `run.sh`, `tools/mysql_test_server.py`,
> `.gitignore`, `LICENSE`.

---

## 1. Current Project Structure

```
FarmBridge/
├── app.py                     # Flask backend + ALL business logic (997 lines)
├── db.py                      # Database abstraction layer (352 lines)
├── index.html                 # Single-page frontend (1852 lines)
├── README.md                  # Project readme
├── requirements.txt           # 4 dependencies
├── .env.example               # DB env vars only
├── run.sh                     # pip install + python app.py
├── .gitignore                 # *.db, __pycache__/, .env
├── LICENSE
├── farmbridge.db              # SQLite file (auto-created at runtime, gitignored)
└── tools/
    └── mysql_test_server.py   # Dev-only MySQL wire-protocol test server
```

There is **no** `routes/`, `services/`, `models/`, `utils/`, `tests/`, or
`docs/` directory. All application code lives in two modules (`app.py` +
`db.py`) and one HTML file.

---

## 2. Current Frontend Architecture

- A **single HTML file** (`index.html`) served by Flask from the project root
  (not from a `templates/` folder).
- **No build step, no framework.** Uses:
  - Tailwind CSS via CDN (`cdn.tailwindcss.com`)
  - Google Fonts (Syne, Bricolage Grotesque, Space Grotesk, Plus Jakarta Sans)
  - Vanilla JavaScript (one giant inline `<script>` block)
  - Web Speech API (`webkitSpeechRecognition` / `SpeechRecognition`) for the
    Krishi Sahayak voice assistant
  - Browser `FileReader` + base64 for photo upload
  - Browser geolocation + OpenStreetMap Nominatim reverse geocoding (no API key)
- UI style: glassmorphism, deep farm green (`#1a4d1a`) + orange (`#ff6b00`),
  responsive/mobile-friendly, custom CSS animations.
- **Client state** (all in `localStorage`):
  - `fb_user` → `{ name, phone }` (the "session")
  - `fb_buyer` → consumer profile (email, address, type, org)
  - `fb_cart` → the cart
  - `fb_pending` → listings queued while offline (offline-first retry)
- **Portals / views** (all sections toggled with `classList`):
  1. Login (name + phone)
  2. Portal selection (Farmer / Buyer)
  3. Farmer Portal (voice assistant, crop form, AI grade card, mandi widget,
     milestone payouts, "my recent listings")
  4. Buyer onboarding (delivery address)
  5. Buyer type selection (Individual / Community / HoReCa)
  6. Individual portal (Blinkit/Zepto-style quick commerce)
  7. Community portal (pool-buy)
  8. HoReCa portal (recurring subscriptions + calendar)
- The frontend polls `/api/market` every 30 s and has a manual refresh button
  plus a "last updated" time.

---

## 3. Current Backend Architecture

- One Flask app in `app.py`. `CORS(app)` allows **all origins**.
- All route handlers, validation, AI grading, mandi pricing, order logic, pool
  logic and subscription logic live **inside `app.py`**.
- `db.py` is the only separated concern: a hand-rolled SQLite/MySQL abstraction.
  - `Cursor` wrapper rewrites `?` → `%s` for MySQL and always returns dict rows.
  - Translates SQLite `ON CONFLICT ... DO UPDATE` upserts to MySQL
    `ON DUPLICATE KEY UPDATE`.
  - `Connection` wrapper supports `with get_conn() as conn:` (commits on exit).
- `init_db()` runs **at import time** (side effect on module import).
- Server runs with `app.run(debug=True)` — the Flask dev server, even when the
  `PORT` env var is set (e.g. for a cloud platform).
- Errors are returned inconsistently: mostly `{"error": "..."}` strings with
  various HTTP codes; success shapes vary per endpoint.

---

## 4. Current Database Architecture

- Abstracted behind `db.py`. Engines: **MySQL** (PyMySQL) when reachable,
  otherwise **silent automatic fallback to SQLite** (`farmbridge.db`).
- Schema is defined once in `db.SCHEMA` and translated per engine
  (`{pk}`, `{text}`, `{longtext}` placeholders).
- Tables (7):
  - `users` — id, name, phone, role, created_at
  - `listings` — farmer listing (see weaknesses below)
  - `buyers` — phone(PK), name, email, address, landmark, city, pincode,
    latitude, longitude, **buyer_type**, org_name, created_at, updated_at
  - `orders` — id, order_code, buyer_phone, buyer_name, buyer_type,
    **items (JSON text)**, subtotal, delivery_fee, discount, total,
    payment_method, payment_status, status, address, eta_minutes, source,
    created_at
  - `pools` — community pool-buy batches
  - `pool_joins` — id, pool_id, buyer_phone, buyer_name, org_name, qty_kg, joined_at
  - `subscriptions` — HoReCa recurring plans
- `listings` columns: id, farmer_name, phone, crop_name, harvest_date,
  **quantity (VARCHAR, e.g. "100 Kg")**, price (DOUBLE), location,
  **photo (base64 data URL stored inline, LONGTEXT/TEXT)**, grade, expiry_date,
  shelf_life, freshness_score, mandi_price, platform_price, mandi_name,
  **status (VARCHAR, wrongly seeded with "Order Placed")**, created_at,
  voice_transcript, sold_kg (INTEGER, added via ad-hoc `ALTER` for older SQLite
  files).
- No foreign keys, no indexes beyond primary keys, no `order_items`, no
  `farmers`, no `consumers`, no `delivery_tracking`, no migrations framework
  (schema drift is handled by `CREATE TABLE IF NOT EXISTS` + one ad-hoc
  `ALTER TABLE ... ADD COLUMN sold_kg`).

---

## 5. Current API Endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| POST | `/api/login` | Name + phone login (INSERT into users) |
| GET | `/api/db-info` | Which engine is live + row counts |
| GET | `/api/mandi-price?crop=&location=` | Mock mandi benchmark |
| POST | `/api/grade` | AI grade from crop + harvest date + photo |
| POST | `/api/listings` | Create farmer listing |
| GET | `/api/listings` | All listings |
| PUT | `/api/listings/<id>/status` | Set listing status (milestone-style statuses) |
| GET | `/api/stats` | Dashboard stats (partly fake numbers) |
| GET | `/api/buyer/profile?phone=` | Fetch buyer profile |
| POST | `/api/buyer/profile` | Upsert buyer profile |
| GET | `/api/market` | Consumer marketplace (enriched listings) |
| POST | `/api/orders` | Create order (items JSON, decrements sold_kg) |
| GET | `/api/orders?phone=` | List orders |
| PUT | `/api/orders/<id>/advance` | Advance delivery status (no validation) |
| GET | `/api/pools` | Active pools (auto-seeds if empty) |
| POST | `/api/pools/<id>/join` | Add volume to a pool |
| POST | `/api/subscriptions` | Create HoReCa subscription |
| GET | `/api/subscriptions?phone=` | List subscriptions |
| PUT | `/api/subscriptions/<id>` | Pause/resume/change qty |
| DELETE | `/api/subscriptions/<id>` | Delete subscription |
| GET | `/api/subscriptions/calendar` | Expand subscriptions into a schedule |

---

## 6. Current Farmer Portal Data Flow

1. Farmer logs in with name + phone → `POST /api/login` inserts a row in
   `users` (no password/OTP, no token).
2. Farmer opens the Farmer Portal.
3. Krishi Sahayak voice assistant uses **browser** Web Speech API (EN-IN/HI
   optional via language); each step (crop, harvest date, quantity, price,
   location) is transcribed client-side and auto-filled into the form.
   Client-side helpers (`extractCropName`, `extractQuantityInKg`,
   `extractPricePerKg`, `parseDateFromSpeech`) do the parsing.
4. Farmer optionally uploads a photo → `FileReader` base64 → `POST /api/grade`
   → backend `calculate_grade()` returns grade/freshness/expiry.
5. Farmer submits → `POST /api/listings` (photo sent as base64 inside JSON).
   Backend re-validates name/phone, re-extracts crop/quantity/price, computes
   grade server-side, and INSERTs into `listings`. The **photo base64 is stored
   inside the row**.
6. "My Recent Listings" → `GET /api/listings` filtered client-side by phone.

---

## 7. Current Consumer (Buyer) Portal Data Flow

1. Same login (there is no separate consumer account) → the app is
   "one name+phone opens both portals".
2. Onboarding → `POST /api/buyer/profile` upserts into `buyers`.
3. Buyer type (Individual / Community / HoReCa) routes to a portal.
4. Individual portal → `GET /api/market` → `enrich_listing()` on each listing
   (adds `live_price`, `available_kg`, `stock_pct`, etc.) → grid.
5. Cart lives in `localStorage` (`fb_cart`); quantities/prices come from the
   **frontend**.
6. Checkout → `POST /api/orders` with `{ items, buyer_phone, ... }`. Backend
   computes subtotal **from frontend-provided prices**, stores `items` as a JSON
   string, and increments `listings.sold_kg`.
7. Community portal → `GET /api/pools` (auto-seeds pools from listings),
   `POST /api/pools/<id>/join` writes `pool_joins`.
8. HoReCa portal → `POST/GET/PUT/DELETE /api/subscriptions`,
   `GET /api/subscriptions/calendar`.

---

## 8. How Farmer Listings Reach the Consumer Marketplace

The pipeline is:

```
Farmer Portal → POST /api/listings → Flask → listings table (MySQL or SQLite)
Consumer Portal → GET /api/market → Flask → SELECT * FROM listings → enrich → UI
```

So **the shared-database flow already exists in spirit** — the marketplace is
*not* hardcoded; it reads the `listings` table. **However**, the enrichment
layer mutates the data before it reaches the consumer:

- `live_price_for()` applies a random daily drift of −6% to +8% to the farmer's
  price, so the consumer sees a **different price** than the farmer set.
- `available_kg()` subtracts a random daily "demand nibble" (2–18% of stock),
  so the consumer sees **less stock than the farmer listed**.

These make the marketplace *look* live but break the "central database is the
single source of truth" guarantee (a farmer who listed 100 kg at ₹40/kg will
see the consumer portal show ~88 kg at ₹37.65 — verified in a live smoke test).

---

## 9. Authentication Weaknesses

- Login = name + phone only. Any caller can POST `/api/login` with any name.
- **No password, no OTP, no token/session.** The "session" is
  `localStorage.fb_user` — trivially forgeable and not verified by the backend.
- `role` column exists on `users` but is never populated or enforced.
- No concept of authorization: `/api/orders?phone=` returns any user's orders
  for any phone number; `/api/buyer/profile?phone=` returns any profile.
- `PUT /api/orders/<id>/advance` lets **anyone** advance any order's status.
- `PUT /api/listings/<id>/status` lets anyone change any listing's status.

---

## 10. Security Concerns

- `CORS(app)` allows **every origin** (no allowlist).
- `debug=True` always on; debugger/exceptions exposed.
- `SECRET_KEY` not configured/used at all.
- Full-resolution base64 photos stored inline in the DB (unbounded payloads,
  `photo[:100000]` truncation only, no MIME/size validation server-side, no
  filename handling — but path traversal isn't currently possible because files
  are never written to disk).
- SQL injection: low risk — parameters are bound (`?`) — but `GET /api/db-info`
  builds `SELECT COUNT(*) FROM ' + t` from a fixed list (safe today).
- Frontend prices and quantities are trusted (subtotal computed from the client
  cart).
- Fake/misleading claims in UI ("from eNAM & Agmarknet", "UPI Auto-Payout",
  "TRUSTED BY 12,000+ FARMERS") — not a security hole but a trust/integrity issue.
- No rate limiting, no input size limits beyond Flask defaults.

---

## 11. Database Weaknesses

- **Silent SQLite fallback even when MySQL is configured** — production could
  run on SQLite without anyone noticing; data would not be shared across
  devices.
- No migrations framework; schema drift handled ad-hoc.
- `quantity` stored as a **string** ("100 Kg") instead of numeric inventory.
- Inventory modeled only as `quantity` + `sold_kg`; no authoritative
  `quantity_available`, so stock cannot be safely transacted.
- `orders.items` is a JSON string (no `order_items`), so order history breaks if
  a listing is edited/deleted, and it cannot be queried relationally.
- No foreign keys, indexes, or constraints.
- Terminology: `buyers` table / `buyer_type` / `buyer_phone` throughout.
- `listings.status` is seeded with `"Order Placed"` (an order status, not a
  listing status) — semantically wrong.

---

## 12. Order & Stock Management Weaknesses

- **Overselling is possible.** `create_order` increments `sold_kg` without any
  check that `sold_kg + qty <= quantity`. Two concurrent buyers can both
  succeed and drive inventory negative; there is no transaction boundary around
  the multi-step update and no conditional/atomic update.
- Subtotal/total computed from **frontend** prices and quantity.
- No `order_items`; order history stores JSON snapshots.
- Status flow is a free-for-all: `advance_order` just moves to the next index,
  no role check, no transition validation, `CANCELLED` state doesn't exist.
- No farmer-facing order view (a farmer cannot see orders on their listings).
- `eta_minutes` is random (12–25) rather than derived.

---

## 13. Mock / Demo Features (present today)

- `MANDI_PRICES` — hardcoded mock mandi prices labeled as if they were real
  ("Azadpur Mandi, Delhi", "eNAM & Agmarknet" in the UI).
- `random.randint/uniform` used for: unknown-crop mandi price, mandi trend,
  image-quality score, platform uplift, order ETA.
- `seed_pools_if_needed()` — fabricates pool batches from listings with random
  seeded volume and a fake `members + 3` count so the Community widget never
  looks empty.
- `live_price_for()` / `available_kg()` — random daily price drift and demand
  nibble (faked "live" data).
- `/api/stats` — `farmers_connected = total * 3 + 1247` and `avg_uplift: 18.7%`
  are hardcoded.
- Farmer milestone "Instant UPI Payout" timeline is client-side simulation only
  (no real payments).
- Offline listing queue (`fb_pending`) retries POST /api/listings on reconnect.

---

## 14. Production Readiness

**Not production-ready.** Highlights:

- Dev server (`app.run(debug=True)`) instead of a WSGI server (Gunicorn).
- No secret management (no SECRET_KEY, DB creds in plain env).
- No authN/authZ.
- No transactional inventory / overselling protection.
- Silent SQLite fallback can run "production" on a single-process local file.
- No logging, no structured errors, no health endpoint.
- Base64 images in MySQL (row bloat).
- No tests, no CI, no Docker, no deployment config.

---

## 15. Dead or Duplicate Code

- `GET /api/stats` and `GET /api/db-info` are not called by the frontend
  (`/api/stats` unused entirely; `/api/db-info` is diagnostic only).
- `PUT /api/listings/<id>/status` (milestone statuses) is not called by the
  frontend; the frontend's "simulate tracking" is purely client-side.
- Duplicated crop list: `CROP_LIST`/`CROP_SHELF_LIFE` in `app.py` and
  `CROP_LIST` in `index.html` (must be kept in sync manually).
- Duplicated validation/extraction logic: `validate_name`, `validate_phone`,
  `extract_crop_name_smart`, `extract_quantity_kg`, `extract_price_per_kg`
  exist in Python and are re-implemented in JS.
- `_row_to_dict`, `_scalar` helpers exist in `app.py` (and a `dict(r)` loop in
  `get_listings` does the same thing).

---

## 16. Recommended Improvements

1. **Modular backend**: split `app.py` into `routes/`, `services/`, `models/`,
   `utils/`, `database/` (business logic out of route handlers).
2. **Consumer terminology**: `buyers` → `consumers`, `/api/buyer/*` →
   `/api/consumer/*` (with a deprecated alias for compatibility), and
   Buyer → Consumer in all user-facing text.
3. **Real source of truth**: remove random price drift / demand nibble so
   `/api/market` shows the exact rows farmers wrote; clearly label mock mandi
   data as "Demo Market Benchmark".
4. **Inventory**: numeric `quantity_total` + `quantity_available` + `unit`;
   atomic conditional decrements; `order_items` table.
5. **Orders**: transactional placement, backend-computed totals, controlled
   status flow, farmer order management endpoint.
6. **Auth**: phone + OTP (mock in dev), signed tokens, role-based authorization,
   ownership checks.
7. **Images**: store files in `uploads/`, keep a path in the DB, validate type +
   size, unique filenames.
8. **Env separation**: `ENVIRONMENT=development` (SQLite fallback OK) vs
   `production` (fail fast on MySQL problems, Gunicorn, no debug).
9. **Ops**: consistent JSON responses, logging, tests, Docker, deployment docs.
10. **Documentation**: this analysis + integration/deployment/API guides.
