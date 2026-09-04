# Farm Bridge — Final Deployment Checklist

---

## PRE-DEPLOYMENT

- [ ] All tests pass (`pytest -q`).
- [ ] `requirements.txt` updated/committed.
- [ ] `.env` not committed.
- [ ] `DEBUG` disabled for production (`FLASK_DEBUG=false`).
- [ ] Production `SECRET_KEY` generated (long random string).
- [ ] MySQL database created.
- [ ] Database credentials tested from your machine / Render environment.
- [ ] GitHub repository updated and pushed.

---

## RENDER

- [ ] Web Service created.
- [ ] GitHub repository connected.
- [ ] Build command set: `pip install -r requirements.txt`.
- [ ] Start command set: `gunicorn -c gunicorn.conf.py app:app`.
- [ ] Environment variables added (`ENVIRONMENT`, `SECRET_KEY`, `MYSQL_*`, `ALLOWED_ORIGINS`, etc.).
- [ ] Deployment successful.
- [ ] Health endpoint works (`/health`, `/api/health`).
- [ ] `FLASK_DEBUG=false` confirmed.

---

## DATABASE

- [ ] MySQL reachable from Render.
- [ ] Tables initialized (`users`, `farmers`, `consumers`, `listings`, `orders`, `order_items`, `pools`, `pool_joins`, `subscriptions`, etc.).
- [ ] Data persists after Render restart.
- [ ] SSL configured if required (`MYSQL_SSL_MODE`).

---

## APPLICATION

- [ ] Farmer Portal works.
- [ ] Consumer Portal works.
- [ ] Farmer listings appear in Consumer Marketplace.
- [ ] Orders work.
- [ ] Stock updates correctly (100 kg → 95 kg after 5 kg order).
- [ ] Overselling is rejected.
- [ ] Consumer cannot modify another farmer's listing.
- [ ] Images work.
- [ ] Multi-device testing passed (see `docs/MULTI_DEVICE_TESTING.md`).

---

## SECURITY

- [ ] `SECRET_KEY` is secure.
- [ ] `.env` ignored.
- [ ] No credentials in repo.
- [ ] CORS set to real origins (not `*` for sensitive origin).
- [ ] Structured JSON errors everywhere.
- [ ] No stack traces / SQL in responses.

---

## STORAGE / IMAGES

- [ ] Decide local (demo) or Cloudinary (persistent).
- [ ] If Cloudinary, set `STORAGE_PROVIDER=cloudinary` + credentials and verify uploads.

---

## DOCS

- [ ] `docs/PRODUCTION_READINESS_REPORT.md`
- [ ] `docs/RENDER_DEPLOYMENT_GUIDE.md`
- [ ] `docs/CLOUD_DATABASE_GUIDE.md`
- [ ] `docs/GITHUB_SETUP_GUIDE.md`
- [ ] `docs/MULTI_DEVICE_TESTING.md`
- [ ] `docs/SECURITY_CHECKLIST.md`
- [ ] `docs/BACKUP_AND_RECOVERY.md`

---

## FINAL SIGN-OFF

- [ ] Farmer & Consumer share the same MySQL DB.
- [ ] Multi-device sync verified.
- [ ] Data persists after refresh and Render restart.
- [ ] Production is reliable for demo/multi-user use.
