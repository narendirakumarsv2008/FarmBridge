# Farm Bridge — Render Deployment Guide

This guide takes you from GitHub to a live Farm Bridge website on Render with a cloud MySQL database.

---

## Architecture

```
Users (Farmers + Consumers)
          |
          v
https://your-app.onrender.com
          |
          v
Render Web Service
  Flask + Gunicorn
          |
          v
Cloud MySQL Database (Railway / Aiven / DO / AWS RDS)
```

---

## STEP 1 — Push Farm Bridge to GitHub

If not already done:

```bash
cd FarmBridge
git init
git add .
git commit -m "FarmBridge production prep"
git branch -M main
git remote add origin https://github.com/<your-username>/FarmBridge.git
git push -u origin main
```

Make sure `.env` is NOT committed.

---

## STEP 2 — Create a Render account

Go to [https://render.com](https://render.com), sign up (ideally with GitHub).

---

## STEP 3 — Click New + → Web Service

In the Render dashboard:

```
New +
  └── Web Service
```

---

## STEP 4 — Connect GitHub repository

Select the `FarmBridge` repository from the list. Grant Render access to your GitHub account if prompted.

---

## STEP 5 — Configure the service

| Setting | Value |
|---|---|
| Name | `farmbridge` (or your choice) |
| Branch | `main` (or the branch you deployed) |
| Region | Choose the closest region |
| Runtime | Python 3.11+ |
| Build Command | `pip install -r requirements.txt` |
| Start Command | `gunicorn -c gunicorn.conf.py app:app` |

The app reads `PORT` from Render automatically through `gunicorn.conf.py`, so you do not hardcode port 5000.

---

## STEP 6 — Add Environment Variables

In the Render service:

```
Environment
  └── Add Environment Variable
```

Add these:

| Key | Value |
|---|---|
| `ENVIRONMENT` | `production` |
| `FLASK_ENV` | `production` |
| `FLASK_DEBUG` | `false` |
| `SECRET_KEY` | a long random string |
| `DB_ENGINE` | `mysql` |
| `MYSQL_HOST` | your cloud MySQL host |
| `MYSQL_PORT` | `3306` |
| `MYSQL_USER` | your MySQL user |
| `MYSQL_PASSWORD` | your MySQL password |
| `MYSQL_DB` | your database name |
| `MYSQL_SSL_MODE` | `preferred` (or `require` / `verify-ca`) |
| `MYSQL_CREATE_DATABASE` | `false` (managed cloud DBs already exist) |
| `STORAGE_PROVIDER` | `local` or `cloudinary` |
| `ALLOWED_ORIGINS` | `https://your-app.onrender.com` |

Do not include real secrets in the repo. They belong only in the Render dashboard.

---

## STEP 7 — Deploy

Click **Deploy** (or it auto-deploys on push).

---

## STEP 8 — Open the generated Render URL

After the build finishes, open `https://your-app.onrender.com`.

---

## STEP 9 — Run health checks

```bash
curl https://your-app.onrender.com/health
```

Expected:

```json
{
  "status": "ok",
  "app": "FarmBridge",
  "database": {"engine": "mysql", "connected": true}
}
```

Also check:

```bash
curl https://your-app.onrender.com/api/health
curl https://your-app.onrender.com/api/db-info
```

---

## STEP 10 — Test Farmer → Consumer synchronization

1. On **Device A**, open the Render URL, choose **Farmer Portal**, log in.
2. Create a listing: Tomato, 100 kg, ₹40/kg, Kochi, harvest yesterday, image.
3. On **Device B** (different browser/phone/laptop), open the Render URL, choose **Consumer Portal**.
4. Confirm the Tomato listing appears.
5. Buy 5 kg.
6. Confirm available stock becomes 95 kg in the marketplace.
7. Return to the Farmer Portal and confirm the incoming order.

---

## Optional: use render.yaml (Blueprint) instead

The repository includes `render.yaml`. You can also add it via:

```
New +
  └── Blueprint
```

Render will read the web service config, build/start command, and env var stubs. You still need to fill in the real `MYSQL_*`, `SECRET_KEY`, `ALLOWED_ORIGINS`, and Cloudinary values in the dashboard.

---

## Troubleshooting

### App builds but health check fails

- Check `MYSQL_HOST`, `MYSQL_PORT`, `MYSQL_USER`, `MYSQL_PASSWORD`, `MYSQL_DB`.
- Confirm the cloud database is accessible from the public internet.
- Confirm `MYSQL_SSL_MODE` matches your provider.

### "Production requires a reachable MySQL database"

- The MySQL credentials are wrong, the host is unreachable, or SSL is failing.
- The app deliberately does **not** fall back to SQLite in production.

### Images disappear after redeployment

- This is expected with `STORAGE_PROVIDER=local` on Render.
- Use Cloudinary or attach persistent object storage for production.

### Port issues

- Gunicorn reads `PORT` via `gunicorn.conf.py`. Do not hardcode port 5000 in the Start Command.
