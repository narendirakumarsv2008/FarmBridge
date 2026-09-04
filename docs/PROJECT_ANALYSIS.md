# Farm Bridge — Repository Analysis (Before the Backend Refactor)

This document describes the **state of the repository at the start of the takeover**, before the backend refactor. It was produced by inspecting the actual source files (`app.py`, `db.py`, `index.html`, `README.md`, `requirements.txt`, `.env.example`, `run.sh`, `tools/mysql_test_server.py`).

## 1. Current project structure

At the start the repository was a small, flat Flask project:

```
FarmBridge/
├── index.html               # 1,852-line single-page HTML/JS frontend
├── app.py                   # ~997-line Flask backend (all routes + business logic)
├── db.py                    # ~352-line custom DB layer (MySQL/SQLite)
├── README.md
├── requirements.txt
├── run.sh
├── .env.example
├── .gitignore
├── LICENSE
└── tools/
    └── mysql_test_server.py # dev-only MySQL wire-protocol mock (mysql-mimic)
```

## 2. Current frontend architecture

- A single `index.html` in the repository root, served directly by Flask at `/`.
- No build step. Uses Tailwind CSS from a CDN, Google Fonts, and vanilla JavaScript.
- Single-page application with hidden `<section>` elements toggled by JavaScript:
  - `loginPage`
  - `portalPage` (Farmer / Current "Buyer" portal selection)
  - `farmerPortal` (voice assistant, crop form, Mandi widget, payout timeline)
  - `buyerOnboard`, `buyerTypePage`
  - `individualPortal`, `communityPortal`, `horecaPortal`
  - cart drawer, checkout modal, tracking modal, pool join modal, toast.
- Speech recognition uses the Web Speech API (`SpeechRecognition` / `webkitSpeechRecognition`).
- Persistence is primarily `localStorage` for the logged-in user, buyer profile, cart, and offline pending listings. Listings/orders are fetched from the backend but the original code also allowed offline listing queues in `localStorage`.
- The UI is intentionally mobile-first and visually polished (glassmorphism, green/orange identity).

## 3. Current backend architecture

- `app.py` was the whole backend: Flask app, CORS, database import, constants (`CROP_SHELF_LIFE`, `MANDI_PRICES`, `POOL_TIERS`), validation helpers, AI grading, all `/api/...` routes, and the server startup.
- `db.py` abstracted MySQL/SQLite connection differences so route code could use the same SQL placeholder syntax.
- There was **no service layer**, **no route module split**, **no app factory**, and **no tests**.
- `init_db()` ran at import time, creating tables automatically.

## 4. Current database architecture

`db.py` defined these tables:

| Table | Purpose |
|---|---|
| `listings` | Farmer crop listings (farmer_name, phone, crop_name, harvest_date, quantity as text, price, photo base64, grade, freshness, mandi info, status, sold_kg) |
| `users` | Minimal login records (name, phone, role, created_at) |
| `buyers` | "Buyer" profile data (phone, name, email, address, buyer_type, org_name, geo) |
| `orders` | Orders with JSON `items`, totals, payment, status, etc. |
| `pools` | Community pool-buy batches |
| `pool_joins` | Consumer pool participation |
| `subscriptions` | HoReCa recurring plans |

Key observations:

- `listings.quantity` was stored as a **string** like `"100 Kg"`.
- Inventory was tracked only as `sold_kg`; there was no `quantity_total` / `quantity_available`.
- Orders stored a **JSON cart** in `orders.items`; there was no `order_items` table.
- The `buyers` table was separate from `users`; there was no `farmers`, `consumers`, `order_items`, `delivery_tracking`, or `sessions` table.
- The DB would create `farmbridge.db` automatically if MySQL was unreachable, even in production scenarios.

## 5. Current API endpoints

From `app.py`:

| Method | Endpoint | Purpose |
|---|---|---|
| POST | `/api/login` | Name + phone login (no OTP, no token) |
| GET | `/api/db-info` | Show active engine and table counts |
| GET | `/api/mandi-price` | Hardcoded/random Mandi comparison |
| POST | `/api/grade` | AI freshness grading |
| POST | `/api/listings` | Create a farmer crop listing |
| GET | `/api/listings` | List all listings |
| PUT | `/api/listings/<id>/status` | Change a listing's status (used for payout steps) |
| GET | `/api/stats` | Aggregate dashboard stats |
| GET/POST | `/api/buyer/profile` | Get/save "Buyer" profile |
| GET | `/api/market` | Marketplace items from `listings` |
| POST | `/api/orders` | Create an order (decrements `sold_kg`) |
| GET | `/api/orders` | List orders |
| PUT | `/api/orders/<id>/advance` | Auto-advance order status |
| GET | `/api/pools` | List/open pools |
| POST | `/api/pools/<id>/join` | Join a pool |
| POST/GET | `/api/subscriptions` | Create/list subscriptions |
| PUT/DELETE | `/api/subscriptions/<id>` | Pause/resume/cancel |
| GET | `/api/subscriptions/calendar` | Expand subscriptions into a delivery calendar |

## 6. Current Farmer Portal data flow

1. Farmer logs in with **name + phone** (stored in `localStorage`, also inserted into `users`).
2. Farmer uses either the voice assistant or the manual crop form.
3. The browser sends `POST /api/listings` with `crop_name`, `harvest_date`, `quantity`, `price`, `location`, `photo` (base64), `voice_transcript`.
4. `app.py` validates fields, parses quantities/prices, runs `calculate_grade`, adds a Mandi benchmark, and inserts into `listings`.
5. The farmer dashboard (`loadMyListings()`) fetches `/api/listings` and filters by the logged-in phone/name.

## 7. Current Consumer ("Buyer") Portal data flow

1. Same name+phone login.
2. Consumer completes onboarding: name/phone, email, address (optionally geolocation), then chooses a profile type: Individual / Community / HoReCa.
3. `POST /api/buyer/profile` stores the profile in the `buyers` table.
4. The Individual portal fetches `/api/market`, which reads farmer `listings` from the DB.
5. Cart lives in `localStorage`; checkout `POST /api/orders` sends cart items, `buyer_phone`, `buyer_type`, address, payment method.

## 8. How Farmer listings reach the Consumer marketplace

- Farmer listing → `POST /api/listings` → `listings` table → `GET /api/market` → Consumer Portal grid.
- **This central-DB path already existed and worked**, which is the most important original feature.
- However, `GET /api/market` also applied **fake daily demand and price drift** on top of the stored listing (`available_kg = total - sold - random nibble`; `live_price = base × random drift`). This meant the displayed marketplace price/stock could differ from the actual farmer listing.

## 9. Authentication weaknesses

- Login was **name + phone only**, with no password requirement and no verification.
- The `/api/login` endpoint inserted the user with no role logic and returned no token.
- `localStorage` containing `fb_user` was the only "logged in" signal; anyone could set it.
- There were **no protected API endpoints** and **no role-based authorization**.
- Any caller could `POST /api/listings` or `POST /api/orders` without being authenticated.
- There was no OTP, no JWT, no server-side session, and no password storage (so no hash), but also no proof of identity.

## 10. Security concerns

- `Flask(__name__, template_folder=BASE_DIR, static_folder=BASE_DIR)` served the repository root as static, which could expose `app.py`, `db.py`, `.env`, and other files if requested directly.
- CORS was `CORS(app)` (all origins), no environment-controlled allowlist.
- Base64 photos were stored in the database (large data; hard to scale).
- File uploads had no type/size validation; filenames were not controlled (though the original code only accepted base64 from JSON).
- No input limits on request body beyond framework default; large image payloads allowed.
- Production credentials were not committed, but `.env.example` values were placeholders; `.env` was already git-ignored.
- SQL queries used parameter placeholders (good) but there was no auth layer to catch abuse.

## 11. Database weaknesses

- `quantity` was stored as a `VARCHAR` such as `"100 Kg"`, making inventory math fragile.
- No `quantity_available`; only `sold_kg`, and the marketplace injected fake daily demand into remaining stock.
- No `order_items`; order history was a JSON blob and could not be reliably joined to listings/farmers.
- No `farmer_id` / `user_id` foreign-key-style links between listings, farmers, and users.
- `buyers` was not linked to `users`; there was no `consumers` table despite the product terminology.
- No explicit `delivery_tracking` or status history.
- No versioned migrations; schema was only `CREATE TABLE IF NOT EXISTS`, with one special `ALTER TABLE ... sold_kg` for SQLite.
- Production would silently fall back to SQLite if MySQL failed.

## 12. Order and stock management weaknesses

- `POST /api/orders` trusted the **frontend price** (`price`) and **frontend quantity**.
- It computed `subtotal` from client-sent item prices, and did not re-fetch listing prices.
- It incremented `sold_kg` after inserting the order, but did **not check available stock before accepting the order**, so two consumers could oversell the same listing.
- There was no database transaction grouping the order insert + stock update, no `order_items`, and no rollback on failure.
- Order status used display strings and allowed `/advance` only; no controlled transition validation.

## 13. Mock/demo features

- **Mandi prices** were hardcoded for ~13 crops and random for unknown crops, presented in the UI as if it were live market data.
- **Marketplace price/availability** applied daily random drift and demand nibble.
- **Pools** were seeded with random fake `seeded_kg` volume, so the UI showed e.g. "320/500 kg pooled" without any real consumer participation.
- **Farmers online** stat (`total * 3 + 1247`) was fabricated.
- **UPI payout speed** and some tracking steps were simulated in the frontend.
- The README described Mandi as "eNAM mock".

## 14. Production readiness

- Not production ready:
  - No authentication or authorization.
  - No service-layer separation.
  - No tests.
  - No Docker deployment.
  - Silent SQLite fallback.
  - Static serving of the app root.
  - Mock market data presented without clear labels.
  - No structured error handling contract.
  - No logging beyond a few `print()` calls.
- The UI and the central-Farmer→Consumer listing flow were the strongest assets to preserve.

## 15. Dead or duplicate code

- `db.py` had `_ensure_users_table` style behavior? (No — that was added in the refactor. In the original `db.py` there was no unused helper, but `Cursor.lastrowid` had a probing fallback path that was rarely used.)
- `db.py` `_TO_MYSQL` upsert translation (SQLite `ON CONFLICT ... DO UPDATE` → MySQL `ON DUPLICATE KEY UPDATE`) was used only by the buyer profile upsert.
- `app.py` had many helper functions defined at module level but grouped inconsistently (validation, crop extraction, grading, pool logic, subscription logic all in one file).
- The frontend had duplicate crop-extraction logic in JS and Python (the backend re-parsed inputs anyway).
- The `buyers`/`buyer_type` naming was duplicated across `buyers` table, API, and `localStorage` keys.

## 16. Recommended improvements

1. Split the backend into `routes`, `services`, `database`, `models`, `utils`.
2. Move AI grading into `services/grading_service.py`.
3. Move Mandi comparison into `services/mandi_service.py` with a provider abstraction and clear **demo/estimated** labels.
4. Add `quantity_total` and `quantity_available` inventory, with order transactions and stock protection.
5. Add `order_items` for reliable order history and farmer order management.
6. Rename `buyers` → `consumers` with a deprecated `/api/buyer/profile` alias.
7. Add phone + OTP auth (mock OTP in dev, SMS-provider-ready in prod) with JWT tokens.
8. Add role-based / ownership authorization.
9. Store uploaded images in `uploads/` and keep only the path URL in the database; validate type/size.
10. Separate dev vs prod database behaviour; fail loudly in production instead of falling back to SQLite.
11. Keep the UI design intact while changing all user-facing terminology to **Consumer**.
12. Add consistent `{success, data}` / `{success, error}` responses.
13. Add structured logging.
14. Add a pytest suite.
15. Add Docker deployment and documentation.
