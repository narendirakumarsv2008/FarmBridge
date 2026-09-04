# Farm Bridge — GitHub Setup Guide

This guide explains how to get the project into GitHub safely, without committing secrets, and then connect it to Render.

---

## 1. Create a GitHub repository

1. Go to https://github.com/new.
2. Repository name: `FarmBridge` (or your choice).
3. Set visibility: **Private** is recommended (so DB creds/secrets cannot leak), but the repo should not contain `.env`.
4. Do **not** initialize with README if you already have a local repo. Keep it empty.

---

## 2. Initialize Git locally

If this is a fresh checkout:

```bash
cd FarmBridge
git init
```

---

## 3. Add files

```bash
git add .
```

This will add all project files except those in `.gitignore`.

---

## 4. Check `.gitignore`

The project should ignore:

```gitignore
.env
.env.local
.env.production
.env.staging
__pycache__/
**/__pycache__/
*.pyc
*.pyo
venv/
.venv/
*.db
*.sqlite
*.sqlite3
instance/
uploads/
.pytest_cache/
.mypy_cache/
htmlcov/
.coverage
.DS_Store
Thumbs.db
```

Verify `.env` was not staged:

```bash
git check-ignore .env
git status
```

---

## 5. Commit

```bash
git add .
git commit -m "FarmBridge production-readiness"
```

---

## 6. Push

```bash
git branch -M main
git remote add origin https://github.com/<your-username>/FarmBridge.git
git push -u origin main
```

---

## 7. Connect GitHub to Render

1. Go to https://render.com.
2. Sign in with GitHub (grant access to the `FarmBridge` repo).
3. Create a **Web Service** (or **Blueprint** using the committed `render.yaml`).
4. Select the repository and branch.
5. Configure build/start commands and environment variables.
6. Deploy.

---

## Secrets audit before push

```bash
# Search for common secret markers (not commits; just working tree):
grep -rn "MYSQL_PASSWORD=" --include="*.py" . | grep -v ".env" || true
grep -rn "SUPER_SECRET\|api_key\|api_secret" --include="*.py" --include="*.js" --include="*.html" . | grep -v ".env" || true
```

Never commit the real `.env` file.

---

## If credentials were committed in a previous commit

**Immediately**:

1. Rotate the credentials (password, API keys) on the provider.
2. Remove the file from git:

```bash
git rm --cached .env
git commit -m "Remove accidentally committed .env"
git push
```

3. (Optional but recommended) Contact the owner if the repo is public and the history is sensitive. The password is `change-me` / placeholder in this repository now; no real credentials are present.
