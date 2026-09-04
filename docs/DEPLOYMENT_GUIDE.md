# Farm Bridge — Deployment Guide

This guide covers three deployment paths:

1. Simple student/demo deployment.
2. Docker with MySQL.
3. Production architecture (Nginx → Gunicorn → Flask → MySQL).

---

## Before you deploy

- Push the repository to GitHub.
- Make sure `.env` is ignored (it is in `.gitignore`).
- Use a long random `SECRET_KEY`.
- Use a managed/central MySQL database for all real multi-device scenarios.

---

## Option 1 — Simple student / demo deployment

**Recommended platform:** Render, Railway, or PythonAnywhere.

Architecture:

```
GitHub
  |
  v
Deployment platform
  |
  v
Flask backend
  |
  v
Managed MySQL
```

### Step-by-step (Render example)

1. Create a new **Render Web Service** and connect your GitHub repo.
2. Build command:
   ```bash
   pip install -r requirements.txt
   ```
3. Start command:
   ```bash
   gunicorn --bind 0.0.0.0:10000 app:app
   ```
   (Render typically exposes port 10000; adjust if needed.)
4. Create a MySQL database (Render, Railway, PlanetScale, Aiven, or another managed provider).
5. Add environment variables in the Render dashboard:
   ```bash
   ENVIRONMENT=production
   SECRET_KEY=<long-random-secret>
   DB_ENGINE=mysql
   MYSQL_HOST=<your-mysql-host>
   MYSQL_PORT=3306
   MYSQL_USER=<mysql-user>
   MYSQL_PASSWORD=<mysql-password>
   MYSQL_DB=<database-name>
   CORS_ORIGINS=<your-frontend-domain>
   ```
6. Deploy.
7. Visit `/health` to confirm the database is connected.
8. Test the Farmer → Consumer flow from two devices.

---

## Option 2 — Docker

At the repository root:

```
├── Dockerfile
└── docker-compose.yml
```

### Start with Docker Compose

```bash
docker compose up --build
```

This starts:

- MySQL 8 on port `3306`.
- FarmBridge web app on port `5000`.

Persistent volumes:

- `mysql_data`
- `uploads_data`

### Development vs production in Docker

- The `Dockerfile` defaults to `ENVIRONMENT=production` and `DB_ENGINE=mysql`.
- For local development you can override:

```bash
docker compose -f docker-compose.yml \
  -e ENVIRONMENT=development \
  -e DB_ENGINE=sqlite \
  ...
```

Or run the Flask dev server directly outside Docker with `python app.py`.

### Environment variables

Pass secrets via `.env` or the shell:

```bash
export MYSQL_ROOT_PASSWORD=rootpw
export MYSQL_USER=farmbridge
export MYSQL_PASSWORD=change-me
export MYSQL_DB=farmbridge
export SECRET_KEY=long-random-secret
docker compose up --build
```

---

## Option 3 — Production architecture

```
Internet
  |
  v
Nginx (HTTPS/SSL, reverse proxy)
  |
  v
Gunicorn (multiple workers)
  |
  v
Flask app (app:app)
  |
  v
MySQL 8
```

### Basic Gunicorn command

```bash
gunicorn --bind 127.0.0.1:5000 --workers 3 --timeout 120 app:app
```

### Nginx reverse proxy example

```nginx
server {
  listen 80;
  server_name farmbridge.example.com;

  return 301 https://$host$request_uri;
}

server {
  listen 443 ssl http2;
  server_name farmbridge.example.com;

  ssl_certificate /etc/letsencrypt/live/farmbridge.example.com/fullchain.pem;
  ssl_certificate_key /etc/letsencrypt/live/farmbridge.example.com/privkey.pem;

  location / {
    proxy_pass http://127.0.0.1:5000;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
  }

  location /uploads/ {
    alias /path/to/FarmBridge/uploads/;
    expires 1d;
  }
}
```

### HTTPS / SSL

- Use Let's Encrypt (`certbot --nginx`) or a managed load balancer certificate.
- Do not allow HTTP in production.
- Set `SECRET_KEY`, DB credentials, and `CORS_ORIGINS` via the environment.

### Database backups

For MySQL:

```bash
mysqldump -u farmbridge -p farmbridge > farmbridge_$(date +%F).sql
```

Schedule a nightly job (cron) and store backups off-site.

### Logging

- Gunicorn access logs.
- Flask application logs to stdout/stderr (captured by the host or container runtime).
- Avoid logging passwords, OTPs, tokens, or sensitive personal data.

### Production security checklist

- `ENVIRONMENT=production`.
- `DB_ENGINE=mysql` and a real MySQL server.
- Strong `SECRET_KEY`.
- Restricted `CORS_ORIGINS`.
- HTTPS enabled.
- `.env` not committed.
- Uploads directory writable by the app.
- Database user has least privilege.
- Backups enabled.

---

## GitHub deployment workflow

1. `git init` (already a repo here).
2. Ensure `.env` is ignored.
3. Push to GitHub.
4. Configure deployment platform environment variables.
5. Deploy the backend.
6. Deploy/provision the database.
7. Run the app once so the schema/migrations are created, or apply migrations manually.
8. Test `/health` and `/api/db-info`.
9. Test multi-device synchronization: create a listing from one device and view it from another.

---

## Summary

| Option | Best for | Complexity |
|---|---|---|
| Render/Railway/PythonAnywhere | Student projects & demos | Low |
| Docker Compose | Reproducible local/deploy environments | Medium |
| Nginx + Gunicorn + MySQL | Real production | High |
