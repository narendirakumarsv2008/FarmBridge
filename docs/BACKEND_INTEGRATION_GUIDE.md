# FARM BRIDGE — Backend Integration Guide

A beginner-friendly guide to how the Farm Bridge backend is structured, how the
frontend talks to it, and how to run it locally.

---

## 1. Architecture

Every request flows through the same layered pipeline:

```
        Frontend (index.html, Vanilla JS)
                    │
                    │  fetch('/api/...')
                    ▼
            Flask routes (routes/*.py)
                    │  (validate input, enforce auth/ownership)
                    ▼
            Services (services/*.py)   ← business logic lives here
                    │
                    ▼
            Models (models/*.py)       ← SQL data access
                    │
                    ▼
            Database layer (database/db.py)
                    │
                    ▼
        ┌───────────┴────────────┐
        ▼                        ▼
      MySQL                   SQLite
   (shared, production)    (local dev fallback)
```

| Layer | Directory | Responsibility |
|---|---|---|
| Routes | `routes/` | HTTP endpoints. Thin — validate input, call a service, return JSON. |
| Services | `services/` | Business logic: grading, mandi benchmark, marketplace, orders, pools, subscriptions. |
| Models | `models/` | One module per table/entity. All SQL lives here. |
| Database | `database/` | Engine selection, schema, migrations, connection helpers. |
| Utils | `utils/` | Validation, auth tokens, response envelopes, image uploads. |
| Config | `config.py` | All settings from environment variables. |

**Why split it?** The previous version put ~1,000 lines of logic in a single
`app.py`. Now the entry point (`app.py`) is ~60 lines and only wires things
together. You can find and change a feature without touching the rest.

---

## 2. Local Setup

### Python installation

- Install **Python 3.10+** from [python.org](https://python.org).
- Verify: `python --version` (on Linux/macOS: `python3 --version`).

### Virtual environment (recommended)

```bash
# from the FarmBridge folder
python -m venv venv

# Windows
venv\Scripts\activate

# Linux / macOS
source venv/bin/activate
```

### Dependencies

```bash
pip install -r requirements.txt
```

### Environment variables

```bash
cp .env.example .env      # then edit values (see section 3)
```

`.env` is loaded automatically at startup (via `python-dotenv`). You can also
export the variables directly in your shell.

### Database setup

See section 4.

---

## 3. Environment Variables

Full reference in `.env.example`. The important ones:

| Variable | Default | Purpose |
|---|---|---|
| `ENVIRONMENT` | `development` | `development` (SQLite fallback, debug, mock OTP) or `production` (MySQL required, no debug). |
| `SECRET_KEY` | *(dev default)* | Signs auth tokens. **Change in production.** |
| `DB_ENGINE` | `mysql` | `mysql` or `sqlite`. |
| `MYSQL_HOST` / `MYSQL_PORT` | `127.0.0.1` / `3306` | MySQL server address. |
| `MYSQL_USER` / `MYSQL_PASSWORD` / `MYSQL_DB` | — | MySQL credentials + database name. |
| `UPLOAD_FOLDER` | `uploads` | Where crop images are stored. |
| `MAX_CONTENT_LENGTH` | `8388608` | Max request body (8 MB). |
| `MAX_IMAGE_BYTES` | `5242880` | Max single image (5 MB). |
| `TOKEN_TTL_SECONDS` | `604800` | Auth token lifetime (7 days). |
| `MOCK_OTP` | `123456` | Development-only OTP. |
| `SMS_PROVIDER` | *(empty)* | Production OTP delivery hook. |

---

## 4. Database Setup

### Option A — Development with SQLite (simplest)

Set `DB_ENGINE=sqlite` (or just run with no MySQL reachable). The app creates
`farmbridge.db` and all tables automatically on first boot. Good for trying the
project on one machine.

> ⚠️ A local SQLite file is **not shared across devices**. Real multi-device
> synchronization (farmer on one phone, consumer on another) requires MySQL —
> see section 8.

### Option B — MySQL (recommended for real use)

Install MySQL 8 (or use the bundled `docker-compose.yml` which provisions it).

Create the database and user:

```sql
CREATE DATABASE farmbridge CHARACTER SET utf8mb4;
CREATE USER 'farmbridge'@'%' IDENTIFIED BY 'a-strong-password';
GRANT ALL PRIVILEGES ON farmbridge.* TO 'farmbridge'@'%';
FLUSH PRIVILEGES;
```

Then configure:

```bash
DB_ENGINE=mysql
MYSQL_HOST=127.0.0.1
MYSQL_PORT=3306
MYSQL_USER=farmbridge
MYSQL_PASSWORD=a-strong-password
MYSQL_DB=farmbridge
```

**Schema initialization is automatic.** On startup `db.init_db()` creates every
table (`CREATE TABLE IF NOT EXISTS`) and runs the migrations in
`database/migrations/` (including the `buyers → consumers` rename and the
numeric-inventory backfill). You do not need to run SQL by hand.

Check which engine is live at any time:

```bash
curl http://localhost:5000/api/db-info
# {"engine":"mysql","target":"127.0.0.1:3306/farmbridge","counts":{...}, ...}
```

### Development vs production behavior

| | `ENVIRONMENT=development` | `ENVIRONMENT=production` |
|---|---|---|
| MySQL unreachable | falls back to SQLite (logged) | **refuses to start** (loud error) |
| Debug mode | on | off |
| Login | mock OTP auto-accepted | requires SMS provider |

---

## 5. Running Locally

```bash
python -m venv venv            # once
source venv/bin/activate       # Windows: venv\Scripts\activate
pip install -r requirements.txt
python app.py
# Open http://localhost:5000
```

Or use the launcher: `./run.sh`.

Production-style serving (Gunicorn):

```bash
gunicorn -w 4 -b 0.0.0.0:8000 app:app
```

---

## 6. Frontend → Backend Connection

The frontend (`index.html`) is a single page that calls the API with the
browser's `fetch`. Examples:

```js
// GET — read the marketplace (no auth needed)
const res = await fetch('/api/market');
const data = await res.json();          // { items: [...], count, updated_at }

// POST — create a listing
fetch('/api/listings', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ crop_name: 'Tomato', quantity: '100', price: '40', ... })
});
```

The frontend attaches the signed token automatically (a small `fetch` wrapper in
`index.html`) so protected endpoints work in production:

```
Authorization: Bearer <token>
```

All responses are JSON. Success:

```json
{ "success": true, "data": { ... } }
```

Error:

```json
{ "success": false, "error": { "code": "VALIDATION_ERROR", "message": "..." } }
```

(Some collection endpoints — `GET /api/listings`, `GET /api/orders`,
`GET /api/pools`, `GET /api/subscriptions` — return a bare array for
compatibility with the existing frontend.)

---

## 7. Farmer → Consumer Data Flow

```
Farmer Portal
   │  POST /api/listings        (validated, graded, image saved to uploads/)
   ▼
Backend validation & grading
   │
   ▼
MySQL `listings` table          ← single source of truth
   │
   ▼
Consumer Portal  GET /api/market
```

The marketplace is **not** a separate dataset. `GET /api/market` runs a
`SELECT` on the same `listings` table the Farmer Portal writes to — no mock
products, no localStorage source of truth. The exact price and quantity a
farmer enters are exactly what consumers see.

---

## 8. Multi-Device Deployment

**Key idea:** a SQLite file lives on one computer. If Farmer A adds a crop on
their phone (running its own `farmbridge.db`) and Consumer B opens the website
on their laptop, B will *not* see A's listing — the two SQLite files are
different.

For real multi-device sync, deploy **one backend + one central MySQL database**:

```
Farmer A ─┐
Farmer B ─┤──► Shared Flask API ──► Central MySQL
Consumer C┘
```

The recommended paths are covered in
[`docs/DEPLOYMENT_GUIDE.md`](DEPLOYMENT_GUIDE.md): a managed platform (Render /
Railway / PythonAnywhere), Docker Compose, or a full Nginx + Gunicorn + MySQL
stack.

---

## 9. Troubleshooting

| Symptom | Likely cause & fix |
|---|---|
| `Connection refused` / `Can't connect to MySQL` | MySQL not running, or wrong `MYSQL_HOST/PORT`. In development it falls back to SQLite (check the startup log). In production the app refuses to start — fix the DB. |
| `Port 5000 already in use` | Another process holds the port. Use `PORT=5050 python app.py` or kill the old process. |
| `ModuleNotFoundError: No module named 'flask'` | Dependencies not installed — run `pip install -r requirements.txt` (inside your venv). |
| **CORS** error in the browser console | The API serves CORS wide open by default. If you restrict `CORS(app)`, allow the frontend origin. |
| Image upload fails (`UPLOAD_ERROR` / `Could not read image`) | Unsupported type (JPG/PNG/WEBP/GIF only) or file too big (>5 MB). Check `MAX_IMAGE_BYTES`. |
| `Missing field: ...` / `VALIDATION_ERROR` | A required field was empty or malformed (e.g. phone not 10 digits). Read the error `message`. |
| MySQL auth failure (`Access denied`) | Wrong `MYSQL_USER`/`MYSQL_PASSWORD`, or the user lacks privileges on the database. |
| `no such table` (SQLite) or `Table doesn't exist` (MySQL) | Tables are created on startup. If you changed schema by hand, delete the DB file / drop the database and restart so migrations rebuild it. |
| Login returns `503 SMS provider not configured` | You are in `production` without an SMS provider. Use `ENVIRONMENT=development` for the demo, or wire up `SMS_PROVIDER`. |
