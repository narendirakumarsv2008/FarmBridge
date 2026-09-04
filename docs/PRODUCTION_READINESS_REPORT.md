# Farm Bridge — Production Readiness Report (Post-Render Preparation)

This report is based on inspecting the **current updated repository** after the backend refactor and before/while preparing Render deployment. No credentials were invented; everything here is what the project owner must configure externally.

---

## 1. What is already ready for Render

| Area | Status |
|---|---|
| Flask app factory | ✅ `create_app()` in `app.py`, exposed as `app` for Gunicorn. |
| Gunicorn config | ✅ `requirements.txt` includes `gunicorn==22.0.0`; `gunicorn.conf.py` uses `PORT` from Render. |
| Port handling | ✅ `PORT` env var used by Gunicorn config (defaults to 5000 for local/docker). |
| Python version | ✅ `python:3.11-slim` in Dockerfile; compatible with Render Python 3.11/3.12. |
| requirements.txt | ✅ Committed and includes Flask, PyMySQL, PyJWT, Pillow, Gunicorn, optional Cloudinary. |
| Production failure on DB down | ✅ `ENVIRONMENT=production` + `DB_ENGINE=mysql` raises a clear error if MySQL is unavailable; no silent SQLite fallback. |
| Health checks | ✅ `/health` and `/api/health` return database connection status with 503 when DB is down. |
| Safe diagnostics | ✅ `/api/db-info` returns only `engine`, `connected`, `environment` (and counts only outside production). No credentials/connection strings exposed. |
| CORS config | ✅ `ALLOWED_ORIGINS` / `CORS_ORIGINS` supported; production logs a warning when set to `*`. |
| Structured error envelope | ✅ APIs return `{success, data}` / `{success, error:{code,message}}`; stack traces and SQL are not returned. |
| Debug off in production | ✅ `DEBUG` is forced off when `ENVIRONMENT=production`. |
| Schema init | ✅ Idempotent, automatic; also `scripts/init_db.py` for manual/migration use. Never drops data. |
| Indexes | ✅ Useful indexes on `listings`, `orders`, `order_items`, `subscriptions`, `pool_joins`. |
| Marketplace pagination | ✅ `/api/market` and `/api/listings` support `limit` / `offset` and return `total` / `has_more`. |
| Storage abstraction | ✅ `services/storage_service.py` with `LocalStorageProvider` and optional `CloudinaryProvider`. |
| render.yaml | ✅ Created as a Render Blueprint (start/build command, env vars). |
| Tests | ✅ 26 pytest cases passing (auth, listings, market, orders, stock, oversell, consumer, pools, subscriptions, grading, DB init, production failure). |

---

## 2. What still needs configuration by the project owner

- **A real cloud MySQL database** (Railway MySQL, Aiven MySQL, DigitalOcean Managed MySQL, AWS RDS, etc.) must be created.
- **Render Web Service** must be created (or the `render.yaml` blueprint imported) and connected to GitHub.
- **Render environment variables** must be filled in with real values:
  - `SECRET_KEY`
  - `MYSQL_HOST`
  - `MYSQL_PORT`
  - `MYSQL_USER`
  - `MYSQL_PASSWORD`
  - `MYSQL_DB`
  - optionally `MYSQL_SSL_MODE` / `MYSQL_SSL_CA`
  - optionally `ALLOWED_ORIGINS`.
- **Render service name** (e.g. `farmbridge`) and the generated public URL are not set because we do not know the project owner's chosen name.
- **Real SMS OTP** is not configured; `SMS_PROVIDER=mock` is used for demo only.
- **Optional Cloudinary account** is not configured; local storage is the default.

---

## 3. Which environment variables are required

### Production required (DB + app)

```bash
ENVIRONMENT=production
FLASK_DEBUG=false
SECRET_KEY=<long-random-secret>
DB_ENGINE=mysql
MYSQL_HOST=<cloud mysql host>
MYSQL_PORT=3306
MYSQL_USER=<db user>
MYSQL_PASSWORD=<db password>
MYSQL_DB=<database name>
MYSQL_SSL_MODE=preferred   # or require / verify-ca
```

### Recommended / useful

```bash
MYSQL_SSL_CA=
MYSQL_CREATE_DATABASE=false
MYSQL_CONNECT_TIMEOUT=10
GUNICORN_WORKERS=1
GUNICORN_THREADS=4
GUNICORN_TIMEOUT=60
STORAGE_PROVIDER=local       # or cloudinary
CLOUDINARY_CLOUD_NAME=
CLOUDINARY_API_KEY=
CLOUDINARY_API_SECRET=
ALLOWED_ORIGINS=*            # set to your Render URL in production
APP_BASE_URL=https://your-app.onrender.com
```

### Never set in production

- `DB_ENGINE=sqlite` as a silent fallback.
- `MOCK_OTP` as the real login mechanism (demo only).
- Real credentials in code or committed files.

---

## 4. Which services must be created externally

| Service | Who creates it | Purpose |
|---|---|---|
| Cloud MySQL database | Project owner | Central shared database |
| MySQL database name, user, password | Project owner | Connection credentials |
| Optional SSL CA file | Provider / owner | Required only for `verify-ca`/`verify-identity` |
| Render Web Service | Project owner | Hosts Flask+Gunicorn |
| (Optional) Cloudinary account | Project owner | Persistent image storage |

---

## 5. Is the database configuration production-safe?

- **Engine:** MySQL is required in production. ✅
- **No silent SQLite fallback:** `allow_sqlite_fallback` returns `False` when `ENVIRONMENT=production`. If MySQL is unreachable, startup raises `RuntimeError`. ✅
- **SSL:** `MYSQL_SSL_MODE` maps to PyMySQL SSL parameters (`disabled`, `preferred`/`require`, `verify-ca`, `verify-identity`). ✅
- **Remote hosts:** MySQL uses `MYSQL_HOST` / `MYSQL_PORT` directly, so cloud hosts work. ✅
- **CREATE DATABASE privilege:** The app first connects directly to the target DB. It only tries `CREATE DATABASE` when `MYSQL_CREATE_DATABASE=true` or in dev, so cloud DBs that already grant a database (without create privileges) work. ✅
- **Credentials in code:** ❌ None. All via env vars. ✅
- **Migrations:** Automatic and idempotent: `CREATE TABLE IF NOT EXISTS`, per-column `ALTER TABLE` guarded by `information_schema`/`PRAGMA`, and index creation guarded by existence checks. `scripts/init_db.py` is also provided. ✅

---

## 6. Do uploaded images persist after deployment?

**Current default: NO on Render's ephemeral filesystem.**

- `STORAGE_PROVIDER=local` is the default. Images are written to `UPLOAD_FOLDER` (`/tmp/farmbridge_uploads` in render.yaml, or `uploads/` locally).
- Render disk is **ephemeral and non-persistent**: files can disappear on restart/redeploy. The DB stores only the image URL/path (not base64, which is good for size), but the file itself is on the local instance.
- The app still works on a single long-lived instance, but uploaded images are NOT durable across Render redeploys.

**How to make images persistent:**

- Set `STORAGE_PROVIDER=cloudinary` and add `CLOUDINARY_CLOUD_NAME`, `CLOUDINARY_API_KEY`, `CLOUDINARY_API_SECRET`. Uploaded images then get a Cloudinary URL stored in the DB and persist independently of Render.
- Or attach a persistent volume / object storage (Linode Object Storage, S3-compatible bucket) and adapt `storage_service.py`.

---

## 7. Production risks

| Risk | Severity | Mitigation |
|---|---|---|
| Images lost on Render redeploy | High for image-heavy use | Use Cloudinary / persistent object storage, or accept demo-only limitation |
| `ALLOWED_ORIGINS=*` | Medium | Set to exact Render URL(s) |
| Mock OTP used as production auth | High for real users | Integrate a real SMS provider; keep `SMS_PROVIDER=mock` only for demos |
| Single Gunicorn worker/thread | Medium | Scale up as traffic grows; Render free tier is suitable for demos |
| Mandi prices are demo data | Medium | Clearly labelled; replace with real eNAM/APMC provider when available |
| MySQL credentials exposure | High | Never commit `.env`; only set in Render dashboard |
| Large DB response / repeated polling | Medium | Pagination added; frontend polls every 30s, acceptable for current scale |

---

## 8. Final deployment checklist

See `docs/FINAL_DEPLOYMENT_CHECKLIST.md` for the full checklist. High-level:

1. Create cloud MySQL and copy credentials.
2. Push repo to GitHub (no secrets in repo).
3. Create Render Web Service (or import `render.yaml`).
4. Set environment variables in Render.
5. Deploy.
6. Verify `/health`, `/api/health`, `/api/db-info`.
7. Run `scripts/init_db.py` (or rely on automatic startup init).
8. Test Farmer → Consumer flow from two devices.
9. Confirm data persists after Render restart.
10. Decide image storage: local (demo) or Cloudinary (persistent).
