# Farm Bridge — Production Security Checklist

Use this before and after deploying to Render.

---

## Secrets & configuration

- [ ] `SECRET_KEY` is a long random string set in the Render environment (not default).
- [ ] `ENVIRONMENT=production`.
- [ ] `FLASK_DEBUG=false` in production.
- [ ] `.env` is ignored by git (`.gitignore`).
- [ ] No real database credentials in code, HTML, JavaScript, README, or docs.
- [ ] `ALLOWED_ORIGINS` is set to the real frontend origin(s), not `*`, if you are using authenticated cross-origin APIs.

## Database

- [ ] MySQL is used in production (`DB_ENGINE=mysql`).
- [ ] No silent SQLite fallback (`ENVIRONMENT=production` disables it).
- [ ] `MYSQL_PASSWORD` only in Render environment variables.
- [ ] MySQL user has least privilege where possible.
- [ ] SSL configured (`MYSQL_SSL_MODE=preferred` or stronger).

## Application

- [ ] Input validation enabled (`utils/validators.py` used by auth/profile/listings/orders, etc.).
- [ ] File upload validation: allowed types, max size, unique filename, no path traversal.
- [ ] Authentication: protected endpoints require JWT (`Authorization: Bearer <token>`).
- [ ] Authorization: users cannot modify another farmer's listing (403).
- [ ] SQL injection protection: parameterised queries used through the DB layer.
- [ ] CORS configured (not permissive `*` for sensitive production API if frontend is separate).
- [ ] HTTPS used (Render serves HTTPS by default).
- [ ] Sensitive API responses minimised: `/api/db-info` does not expose credentials/connection strings.

## API / error handling

- [ ] All API errors return structured JSON: `{success:false, error:{code,message}}`.
- [ ] No Python stack traces returned to the client.
- [ ] No internal SQL returned.
- [ ] No database credentials in error messages.

## Operations

- [ ] `/health` and `/api/health` return `503` when DB is down.
- [ ] Startup logs show mode + DB engine (no passwords).
- [ ] Backups scheduled (see `docs/BACKUP_AND_RECOVERY.md`).

---

## Suggested manual checks

```bash
# Confirm production doesn't silently use SQLite
ENVIRONMENT=production DB_ENGINE=mysql MYSQL_HOST=127.0.0.1 MYSQL_PORT=1 python -c "from app import create_app; create_app()"
# Should raise: "Production requires a reachable MySQL database"
```

```bash
# Try unauthenticated protected endpoint
curl -i https://your-app.onrender.com/api/auth/me
# Expect 401
```

```bash
# Health
curl https://your-app.onrender.com/health
```

---

## If you deploy a separate frontend later

- Keep frontend and backend on same origin if possible (avoid CORS entirely).
- If separated, use `ALLOWED_ORIGINS=https://frontend.example.com` only.
- Never allow `*` for authenticated write endpoints.
