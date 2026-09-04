# FARM BRIDGE — Deployment Guide

Three ways to deploy Farm Bridge, from beginner demo to production. The most
important rule across all of them: **use one central MySQL database** so the
Farmer Portal and Consumer Portal see the same data from any device.

---

## Option 1 — Simple Student/Demo Deployment (Render)

Best for demos and coursework. A managed platform gives you a public URL and a
managed MySQL database with almost no ops.

Architecture:

```
GitHub repo ──► Render (Flask + Gunicorn) ──► Render managed MySQL
```

### Step-by-step (Render)

1. **Push to GitHub** (see the GitHub workflow section below). Make sure `.env`
   is NOT committed.
2. Create a new **Web Service** on Render, connect your GitHub repo.
   - Runtime: **Python 3**
   - Build command: `pip install -r requirements.txt`
   - Start command: `gunicorn -w 4 -b 0.0.0.0:$PORT app:app`
3. Create a **MySQL** database on Render (or any MySQL host). Note the host,
   port, user, password, database name.
4. Add environment variables to the web service:
   - `ENVIRONMENT=production`
   - `SECRET_KEY=<a long random string>`
   - `DB_ENGINE=mysql`
   - `MYSQL_HOST=<db host>` `MYSQL_PORT=<db port>`
   - `MYSQL_USER=<db user>` `MYSQL_PASSWORD=<db password>` `MYSQL_DB=farmbridge`
   - `UPLOAD_FOLDER=uploads`
   - `SMS_PROVIDER=` (empty — or wire up an SMS provider for production OTP)
5. Deploy. On first boot the app **creates the schema and runs migrations
   automatically**.
6. Open the public URL, log in (use `ENVIRONMENT=development` first if you want
   the mock-OTP demo login; switch to `production` once SMS is wired up).
7. Test multi-device sync: create a listing from one phone, open the URL from
   another device, confirm the listing appears (within the 30s auto-refresh or
   after tapping the refresh button).

> Railway and PythonAnywhere work the same way (Gunicorn start command +
> environment variables + managed MySQL).

---

## Option 2 — Docker

The repository ships a `Dockerfile` and `docker-compose.yml` (Flask + MySQL with
persistent volumes).

```bash
docker compose up --build
# Open http://localhost:5000
```

What the compose stack does:

- `db` — MySQL 8 with a persistent volume (`mysql_data`). Database
  `farmbridge`, user `farmbridge`.
- `app` — the Flask app served by Gunicorn, talking to `db`, with uploaded
  images in a persistent volume (`uploads_data`).

Development vs production differences:

| | Development | Production |
|---|---|---|
| `ENVIRONMENT` | `development` | `production` |
| Server | Gunicorn (already in the image) | Gunicorn |
| DB failure | falls back to SQLite | fails loudly |
| Login | mock OTP | SMS provider required |

Stop without losing data: `docker compose down` (volumes persist). Wipe
everything: `docker compose down -v`.

---

## Option 3 — Production Architecture (Nginx + Gunicorn + MySQL)

For a hardened, real deployment on your own server:

```
Internet ──► Nginx (HTTPS/TLS, reverse proxy, static files) ──► Gunicorn ──► Flask ──► MySQL
```

### 1. The server

- A VPS (or VM) with Ubuntu, Python 3.10+, and MySQL 8.
- Point a domain (e.g. `farmbridge.example.com`) at the server.

### 2. Application user + code

```bash
sudo useradd -m farmbridge
git clone <your-repo> /opt/farmbridge   # or scp the folder
cd /opt/farmbridge
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
```

### 3. Environment

```bash
cp .env.example .env
# set ENVIRONMENT=production, a strong SECRET_KEY, MySQL credentials
```

### 4. MySQL

Create the database and a dedicated user (see the integration guide). The app
migrates the schema on boot.

### 5. Gunicorn (systemd)

`/etc/systemd/system/farmbridge.service`:

```ini
[Unit]
Description=Farm Bridge
After=network.target mysql.service

[Service]
User=farmbridge
WorkingDirectory=/opt/farmbridge
EnvironmentFile=/opt/farmbridge/.env
ExecStart=/opt/farmbridge/venv/bin/gunicorn -w 4 -b 127.0.0.1:8000 app:app
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable --now farmbridge
```

### 6. Nginx + HTTPS

Install Nginx, obtain a TLS certificate (Let's Encrypt `certbot`), and proxy to
Gunicorn:

```nginx
server {
    listen 443 ssl;
    server_name farmbridge.example.com;

    ssl_certificate     /etc/letsencrypt/live/farmbridge.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/farmbridge.example.com/privkey.pem;

    client_max_body_size 8m;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
server { listen 80; server_name farmbridge.example.com; return 301 https://$host$request_uri; }
```

### 7. Production security checklist

- `ENVIRONMENT=production` (no SQLite fallback, no debug, no mock OTP).
- Strong `SECRET_KEY`; DB password in `.env` (root-only, not committed).
- HTTPS everywhere (Nginx terminates TLS).
- Regular MySQL backups: `mysqldump farmbridge > backup.sql` (cron it, store off-server).
- Logs: Gunicorn/systemd + app logs. Rotate with `logrotate`.
- Keep `uploads/` on a disk with room; consider S3/Cloudinary later.

---

## GitHub Deployment Workflow

1. **Initialize Git** — `git init`, add the files, commit.
2. **Ensure `.env` is ignored** — `.gitignore` already lists `.env`; verify
   `git status` never shows it.
3. **Push to GitHub** — create a repo, `git remote add origin ...`,
   `git push -u origin main`.
4. **Configure deployment environment variables** — set `ENVIRONMENT`,
   `SECRET_KEY`, `DB_ENGINE`, MySQL credentials, `UPLOAD_FOLDER` on the platform.
5. **Deploy backend** — via the platform's build/start commands (Gunicorn).
6. **Deploy database** — provision MySQL (managed or self-hosted).
7. **Run migrations/schema** — automatic on app startup (no manual step).
8. **Test the website** — log in, create a listing, place an order.
9. **Test multi-device synchronization** — two devices/browsers against the
   public URL must see the same listing, and stock must drop after an order.
