# Farm Bridge — Backup and Recovery

The most important data is in MySQL (listings, consumers, orders, order_items, subscriptions, pools, users). Back this up regularly.

---

## Recommended backup strategy

1. **Managed automated backups** (best): Most managed MySQL providers (Aiven, DigitalOcean, AWS RDS, Railway) support automated snapshots. Enable them.
2. **Regular `mysqldump`** for portability.
3. **Before schema changes**, create a manual backup.
4. Store backups off-site (object storage, local if permitted).

---

## Manual MySQL dump

```bash
MYSQL_PWD='your-password' mysqldump \
  -h "$MYSQL_HOST" -P "$MYSQL_PORT" \
  -u "$MYSQL_USER" --single-transaction \
  --routines --triggers \
  "$MYSQL_DB" > farmbridge_backup_$(date +%F).sql
```

Example:

```bash
mysqldump -u farmbridge -p farmbridge > farmbridge_backup.sql
```

---

## Restore (conceptually)

```bash
# Create/recreate the database
mysql -u farmbridge -p -e "CREATE DATABASE IF NOT EXISTS farmbridge"

# Restore dump
mysql -u farmbridge -p farmbridge < farmbridge_backup.sql
```

> **Warning:** Restoring a dump will overwrite existing data. Test in a staging environment first.

---

## Backup frequency

| Environment | Frequency |
|---|---|
| Demo / student | Weekly (or rely on managed snapshots) |
| Production | Daily automated + weekly manual dump |

---

## What the app does on startup

- `CREATE TABLE IF NOT EXISTS` for known tables.
- Lightweight column migrations (guarded by `information_schema` / `PRAGMA`).
- Index creation (guarded by existing-index check).
- **Never drops tables or deletes data automatically.**

---

## Recovery steps

1. Stop deploys if a bad migration/change is suspected.
2. Restore from the last good backup.
3. Run `python scripts/init_db.py` to ensure schema is consistent.
4. Verify `/health` and `/api/db-info`.
5. Test a full Farmer → Consumer order flow.

---

## Do not automate destructive commands without clear warnings

Never run `DROP DATABASE`, `DROP TABLE`, or restore directly on production without:

- A fresh backup.
- A review of the command.
- A tested rollback path.
