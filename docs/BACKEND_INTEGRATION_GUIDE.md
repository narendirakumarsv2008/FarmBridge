# Farm Bridge — Backend Integration Guide

This guide explains how the Farm Bridge frontend, Flask backend, services, and database fit together, and how to run the project locally.

---

## 1. Architecture

```
Frontend (index.html, browser)
        |
        | Fetch API (JSON)
        v
Flask routes (routes/*)
        |
        | validate + authorize
        v
Services (services/*)
        |
        | business logic / transactions
        v
Database (database/db.py -> MySQL or SQLite)
```

Every layer has one responsibility:

| Layer | Responsibility |
|---|---|
| `index.html` | UI, voice assistant, cart, portals. Calls the API. Never owns the database. |
| Flask routes | HTTP endpoints, parameter extraction, auth decorators, consistent JSON responses. |
| Services | Business rules: grading, Mandi benchmark, marketplace, orders, subscriptions, pools, auth. |
| `database/db.py` | Opens connections, creates schema, applies lightweight migrations, translates SQL for MySQL/SQLite. |
| MySQL / SQLite | Source of truth for listings, users, consumers, orders, etc. |

---

## 2. Local setup

### Python installation

Install Python 3.11+ from [python.org](https://www.python.org/) or your OS package manager.

### Virtual environment

```bash
cd FarmBridge
python -m venv venv
```

Activate it:

```bash
# Linux / macOS
source venv/bin/activate

# Windows
venv\Scripts\activate
```

### Dependencies

```bash
pip install -r requirements.txt
```

### Environment variables

```bash
cp .env.example .env
```

Example `.env`:

```bash
FLASK_ENV=development
ENVIRONMENT=development
SECRET_KEY=change-this-in-production
DB_ENGINE=mysql
MYSQL_HOST=127.0.0.1
MYSQL_PORT=3306
MYSQL_USER=farmbridge
MYSQL_PASSWORD=change-me
MYSQL_DB=farmbridge
UPLOAD_FOLDER=uploads
```

For local SQLite development:

```bash
ENVIRONMENT=development
DB_ENGINE=sqlite
SQLITE_PATH=farmbridge.db
```

### Database setup

The app creates the schema automatically on first startup. It applies lightweight in-place column migrations so older databases are upgraded.

---

## 3. Running locally

```bash
# Linux/macOS
source venv/bin/activate
python app.py
```

Open `http://localhost:5000`.

For a simpler one-command start:

```bash
./run.sh
```

---

## 4. Frontend → Backend connection

The frontend uses the browser `fetch` API against same-origin `/api/...` URLs.

**GET example:**

```javascript
const res = await fetch('/api/market');
const json = await res.json();
const body = json.data || json;
const items = body.items || [];
```

**POST example:**

```javascript
const res = await fetch('/api/listings', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ crop_name: 'Tomato', quantity: 100, price: 40 })
});
const json = await res.json();
```

For protected endpoints the frontend automatically attaches the JWT from `localStorage`:

```javascript
fetch('/api/auth/login', { ... }) // returns { data: { token, user } }
// later requests include:
// Authorization: Bearer <token>
```

The app injects this header automatically for same-origin `/api/` requests.

---

## 5. Farmer → Consumer data flow

```
Farmer
  |
  | POST /api/listings  (crop_name, harvest_date, quantity, price, location, photo)
  v
Backend validation
  |
  | AI grading + Mandi benchmark + image storage
  v
MySQL `listings` table (source of truth)
  |
  | GET /api/market
  v
Consumer Portal
  |
  | Consumer adds to cart / places order
  v
Backend transaction (stock check, order_items, stock decrement)
```

The central database is the only marketplace source of truth. There are no frontend-only or localStorage marketplace products.

---

## 6. Multi-device deployment

Local `localhost` databases are **not shared** across separate computers. To let Farmer A on one phone and Consumer B on another phone see the same data, you need:

- A deployed backend (Render, Railway, PythonAnywhere, Docker host, etc.).
- A central MySQL database reachable from the deployed backend.

Once deployed, both devices share the same hostname and database.

---

## 7. Troubleshooting

### Database connection failure

- Check `MYSQL_HOST`, `MYSQL_PORT`, `MYSQL_USER`, `MYSQL_PASSWORD`, `MYSQL_DB`.
- Verify MySQL is running: `mysql -u farmbridge -p farmbridge`.
- For production, if MySQL is unreachable the app fails explicitly (no silent SQLite fallback).

### Port already in use

```bash
lsof -i :5000
# or
sudo lsof -i :5000
```

Change the port:

```bash
PORT=5001 python app.py
```

### Module not found

```bash
pip install -r requirements.txt
```

### CORS issue

If your frontend is served from a different origin, set `CORS_ORIGINS` to the allowed origins:

```bash
CORS_ORIGINS=https://app.example.com
```

### Image upload failure

- Use JPG, PNG, WEBP or GIF.
- Keep under `MAX_UPLOAD_SIZE_MB` (default 5 MB).
- `uploads/` must be writable by the app process.

### Missing environment variables

Use `.env.example` as a template. Required for production:

- `SECRET_KEY`
- `DB_ENGINE=mysql`
- MySQL credentials.

### MySQL authentication failure

- Create the MySQL user with permissions:

```sql
CREATE USER 'farmbridge'@'%' IDENTIFIED BY 'your-password';
GRANT ALL PRIVILEGES ON farmbridge.* TO 'farmbridge'@'%';
FLUSH PRIVILEGES;
```

### Tables missing

- Check `/health` and `/api/db-info`.
- Confirm the app has permission to create tables.
- If you use an existing database, run the app once so the schema/migrations are applied.

---

## 8. Testing

```bash
pip install -r requirements.txt
pytest -q
```

The tests use a temporary SQLite database, so they do not touch MySQL.
