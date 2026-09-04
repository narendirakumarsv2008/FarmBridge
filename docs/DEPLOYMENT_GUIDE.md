# FARM BRIDGE — Deployment Guide

Three ways to deploy Farm Bridge, from beginner demo to production. The most
important rule across all of them: **use one central MySQL database** so the
Farmer Portal and Consumer Portal see the same data from any device.

---

## Option 1 — Render (Blueprint / one-click Infrastructure-as-Code)

The repo ships a `render.yaml` **Blueprint**, so Render can provision the whole
stack (Flask web service + MySQL private service) from the file — no manual
click-through needed.

Architecture:

```
GitHub repo ──► Render Blueprint ──► farmbridge (web, Gunicorn)
                                    farmbridge-mysql (private service + disk)
```

> ⚠️ One honest caveat: Render's *managed* databases are PostgreSQL-only, so the
> Blueprint runs MySQL as a **private service** from the official MySQL 8 image
> with a persistent disk. Persistent disks require a **paid** instance type, so
> the MySQL service is set to `0.5c-512mb` (≈$7/month). The web service itself is
> free. (A free, demo-only alternative is at the end of this section.)

### Step-by-step

1. **Push the repo to GitHub.** Make sure `render.yaml` is present at the repo
   root and `.env` is NOT committed (it's git-ignored).
2. In the Render dashboard, go to **New → Blueprint**, connect your GitHub repo,
   and select the branch that contains `render.yaml` (e.g. `arena/01a06ac4-farmbridge`).
3. Review the resources it detected (`farmbridge` web service and
   `farmbridge-mysql` private service). Click **Apply**.
4. Render provisions MySQL first, then builds the app (`pip install -r
   requirements.txt`) and starts it with Gunicorn.
5. Wait for the first deploy. On boot the app **creates the schema and runs
   migrations automatically**, and it **retries the MySQL connection** while the
   database initialises (see `MYSQL_CONNECT_RETRIES`).
6. Open the service URL (e.g. `https://farmbridge.onrender.com`) and log in.
   `ENVIRONMENT=development` is set, so the mock-OTP login works out of the box
   (OTP shown on screen is `123456`).
7. Test multi-device sync: list a crop on one phone, open the URL on another
   device, confirm the listing appears (within the ~25s auto-refresh or after
   tapping refresh) and that stock drops after a purchase.

### How the services are wired (render.yaml)

| Env var (web service) | Source |
|---|---|
| `MYSQL_HOST` / `MYSQL_PORT` | referenced from the `farmbridge-mysql` private service |
| `MYSQL_PASSWORD` | referenced from the MySQL service's generated password |
| `MYSQL_USER`, `MYSQL_DB` | `farmbridge` / `farmbridge` |
| `SECRET_KEY` | auto-generated random value (`generateValue: true`) |
| `ENVIRONMENT` | `development` (mock-OTP login works immediately) |

Because `MYSQL_HOST`/`MYSQL_PORT`/`MYSQL_PASSWORD` are wired by reference, the
web service always talks to the MySQL instance Render created — no copy-pasting
credentials.

### Going live for real (production)

1. Switch `ENVIRONMENT` to `production` in the Render dashboard (or in
   `render.yaml`).
2. Wire up an SMS provider for OTP login — set `SMS_PROVIDER` to a
   `"yourmodule:function"` hook (see `utils/security.py`). Until then,
   production login returns `503 SMS provider not configured` by design.
3. Add a custom domain (Render Dashboard → Settings → Custom Domain) to get
   HTTPS at `farmbridge.example.com`.

### Known limits on Render

- **Uploaded images** are written to the local `uploads/` folder, which is
  **ephemeral** on Render's free tier — images can disappear on redeploy.
  Listings/orders/inventory all live in MySQL (persistent). For permanent
  images, point uploads at object storage (S3/Cloudinary) later.
- **MySQL is self-managed** on Render; back it up with `mysqldump` (Render
  snapshots the disk, but Render's own docs recommend `mysqldump` for restores).

### 100% free demo alternative (no MySQL service)

For a temporary demo at zero cost: delete the `farmbridge-mysql` service from
`render.yaml` (or deploy only the web service manually) and either:

- set `DB_ENGINE=sqlite` (data is lost on each redeploy — fine for a quick demo), or
- point `MYSQL_*` at a free external MySQL host (e.g. Aiven, db4free, or a free
  tier from a cloud provider) — this keeps the shared-DB behaviour across devices.

> Railway works the same way (Gunicorn start command + environment variables);
> PythonAnywhere is a good fit too if you only need the web service.

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
