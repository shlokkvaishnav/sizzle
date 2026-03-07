# Switch to another online Postgres (e.g. Neon, Railway)

Use this when you want to move your data from Supabase to another **online** Postgres provider (e.g. to avoid DNS/connectivity issues).

## 1. Create a new Postgres database

Pick one (both have free tiers):

- **[Neon](https://neon.tech)** — Sign up → Create project → copy the connection string (URI).
- **[Railway](https://railway.app)** — New project → Add PostgreSQL → copy the `DATABASE_URL` from Variables.

Ensure the URI looks like:
`postgresql://user:password@host:port/dbname?sslmode=require`  
(Neon/Railway usually include `sslmode=require` in the URI; if not, add it.)

## 2. Set env and run the migration

In **backend/.env** add (or edit):

```env
# Current Supabase (source). Omit to use DATABASE_URL.
SOURCE_DATABASE_URL=postgresql://postgres:YOUR_PASSWORD@db.xxx.supabase.co:5432/postgres

# New provider (target)
TARGET_DATABASE_URL=postgresql://user:pass@ep-xxx.us-east-1.aws.neon.tech/neondb?sslmode=require
```

From the **backend** folder run:

```bash
python migrate_online.py
```

This copies all tables and the `v_sales` view from source to target.

## 3. Point the app at the new DB

In **backend/.env** set:

```env
DATABASE_URL=postgresql://user:pass@ep-xxx...neon.tech/neondb?sslmode=require
```

(Use the same value as `TARGET_DATABASE_URL`, or remove `SOURCE_DATABASE_URL` / `TARGET_DATABASE_URL` after migration.)

Restart the backend. The app will use the new online database.
