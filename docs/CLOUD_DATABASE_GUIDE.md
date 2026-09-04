# Farm Bridge — Cloud MySQL Database Guide

Farm Bridge uses MySQL in production. This guide explains how to connect it to any standard managed MySQL provider (Railway, Aiven, DigitalOcean Managed MySQL, AWS RDS, and others). It does **not** migrate to Supabase/PostgreSQL.

---

## Connection environment variables

The app reads these from the environment. Never hardcode them.

| Variable | Purpose | Example |
|---|---|---|
| `DB_ENGINE` | Must be `mysql` in production | `mysql` |
| `MYSQL_HOST` | Cloud database host | `db.example.com` |
| `MYSQL_PORT` | Database port | `3306` |
| `MYSQL_USER` | App database user | `farmbridge` |
| `MYSQL_PASSWORD` | App database password | `your-secret` |
| `MYSQL_DB` | Database/table schema name | `farmbridge` |
| `MYSQL_SSL_MODE` | SSL mode | `preferred`, `require`, `verify-ca`, `verify-identity`, `disabled` |
| `MYSQL_SSL_CA` | Optional CA bundle path | `/path/to/ca.pem` (for verify-ca/verify-identity) |
| `MYSQL_CREATE_DATABASE` | Whether the app user may CREATE DATABASE | `false` for managed cloud |
| `MYSQL_CONNECT_TIMEOUT` | Connect timeout seconds | `10` |

---

## SSL mode reference

| Mode | What it does |
|---|---|
| `disabled` | No SSL encryption |
| `preferred` | Use SSL if the server supports it (most managed providers) |
| `require` | Requires an SSL connection but does not verify the cert |
| `verify-ca` | Requires SSL and verifies the CA certificate (`MYSQL_SSL_CA`) |
| `verify-identity` | Requires SSL, verifies CA + hostname |

If your provider gives you a CA certificate file, use:

```bash
MYSQL_SSL_MODE=verify-ca
MYSQL_SSL_CA=/etc/ssl/certs/provider-ca.pem
```

---

## Step 1 — Create the database and user on the provider

Most managed providers let you create a MySQL database and user through their dashboard:

- Railway MySQL: create MySQL plugin, copy the `DATABASE_URL`.
- Aiven MySQL: create MySQL service, copy host/port/user/password/database.
- DigitalOcean Managed MySQL: create cluster + database, copy connection details.
- AWS RDS MySQL: create DB instance, master/user, note endpoint + port.

For a provider that exposes a single connection string, parse it into:

```
mysql://USER:PASSWORD@HOST:PORT/DBNAME
```

and set:

```bash
MYSQL_HOST=HOST
MYSQL_PORT=PORT
MYSQL_USER=USER
MYSQL_PASSWORD=PASSWORD
MYSQL_DB=DBNAME
```

---

## Step 2 — Confirm the database exists

Farm Bridge expects the database to exist. Managed cloud providers usually create it for you when you provision the database.

For local Docker MySQL, you can enable auto-create:

```bash
MYSQL_CREATE_DATABASE=true
```

For managed cloud providers, keep it `false` (the app user typically does not have `CREATE DATABASE` permission).

---

## Step 3 — Set the variables in Render

Open Render dashboard:

```
Your Web Service
  └── Environment
      └── Add Environment Variable
```

Add each `MYSQL_*` variable and `SECRET_KEY`, `ENVIRONMENT`, `DB_ENGINE`, etc.

---

## Step 4 — Redeploy service

After changing environment variables, Render redeploys the service.

---

## Step 5 — Initialize tables

Tables are created automatically at startup. You can also run:

```bash
# In a shell with the same environment variables:
python scripts/init_db.py
```

This is idempotent; it creates missing tables, applies lightweight migrations, and adds indexes. It never drops or deletes data.

---

## Step 6 — Verify connection

```bash
curl https://your-app.onrender.com/health
curl https://your-app.onrender.com/api/health
curl https://your-app.onrender.com/api/db-info
```

`/health` and `/api/health` should show database `connected: true`.

---

## Permissions (best practice)

The app user should have:

- `SELECT`, `INSERT`, `UPDATE`, `DELETE` on the `farmbridge` tables.
- `CREATE`, `ALTER`, `INDEX` on `farmbridge` only if you want the app to auto-create/migrate schema. (Most managed DBs give full rights to the database; that is fine.)
- **No** broad server-level privileges like `CREATE USER` or `GRANT` everywhere.

---

## What NOT to do

- Do not put credentials in code, HTML, JavaScript, README, or git history.
- Do not use `DB_ENGINE=sqlite` in production.
- Do not expect `MYSQL_CREATE_DATABASE=true` to work on a managed cloud DB where the user cannot create databases.
- Do not permanently disable SSL if your provider requires it.
