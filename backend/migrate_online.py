"""
migrate_online.py — Copy all data from one Postgres DB to another (e.g. Supabase → Neon/Railway)
=================================================================================================
Run once when you want to switch to another online Postgres provider. Uses SQLAlchemy so IDs
and FKs are preserved.

Setup:
  1. Create a new Postgres database online (e.g. Neon.tech or Railway — both have free tiers).
  2. Get the connection string (URI) from the provider.
  3. In backend/.env set:
       SOURCE_DATABASE_URL=postgresql://...   # your current Supabase URI (or leave unset to use DATABASE_URL)
       TARGET_DATABASE_URL=postgresql://...   # the new provider URI
  4. From backend/ run:
       python migrate_online.py

After a successful run, point the app at the new DB by setting DATABASE_URL=TARGET_DATABASE_URL
(or replace DATABASE_URL with the new URI) and restart the backend.
"""

import os
import sys
from pathlib import Path

_backend = Path(__file__).resolve().parent
if str(_backend) not in sys.path:
    sys.path.insert(0, str(_backend))
os.chdir(_backend)

from dotenv import load_dotenv
load_dotenv(_backend / ".env")
load_dotenv(_backend.parent / ".env")

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from database import Base
from models import (
    Restaurant,
    RestaurantSettings,
    Category,
    MenuItem,
    Ingredient,
    RestaurantTable,
    Order,
    OrderItem,
    KOT,
    MenuItemIngredient,
    StockLog,
    ComboSuggestion,
    VoiceSession,
)

MODELS_IN_ORDER = [
    Restaurant,
    RestaurantSettings,
    Category,
    MenuItem,
    Ingredient,
    RestaurantTable,
    Order,
    OrderItem,
    KOT,
    MenuItemIngredient,
    StockLog,
    ComboSuggestion,
    VoiceSession,
]

V_SALES_VIEW_SQL = """
CREATE OR REPLACE VIEW v_sales AS
SELECT
    oi.id                                AS id,
    o.restaurant_id                      AS restaurant_id,
    oi.item_id                           AS item_id,
    o.order_id                           AS order_id,
    oi.quantity                          AS quantity,
    oi.unit_price                        AS unit_price,
    oi.line_total                        AS total_price,
    o.order_type                         AS order_type,
    COALESCE(o.settled_at, o.updated_at) AS sold_at
FROM order_items oi
JOIN orders o ON o.id = oi.order_pk
WHERE o.status = 'confirmed';
"""


def get_engine(url: str):
    if not url or not url.strip().lower().startswith(("postgresql://", "postgres://")):
        return None
    return create_engine(
        url,
        pool_pre_ping=True,
        connect_args={"sslmode": "require"},
    )


def copy_table(src_session, tgt_session, model) -> int:
    rows = src_session.query(model).all()
    if not rows:
        return 0
    for row in rows:
        d = {c.key: getattr(row, c.key) for c in model.__table__.columns}
        tgt_session.add(model(**d))
    tgt_session.commit()
    return len(rows)


def main():
    source_url = os.getenv("SOURCE_DATABASE_URL") or os.getenv("DATABASE_URL")
    target_url = os.getenv("TARGET_DATABASE_URL")

    if not target_url:
        print("ERROR: Set TARGET_DATABASE_URL in backend/.env (your new Postgres URI).")
        sys.exit(1)
    if not source_url:
        print("ERROR: Set SOURCE_DATABASE_URL or DATABASE_URL in backend/.env.")
        sys.exit(1)

    src_engine = get_engine(source_url)
    tgt_engine = get_engine(target_url)
    if not src_engine or not tgt_engine:
        print("ERROR: Both SOURCE and TARGET must be PostgreSQL URLs.")
        sys.exit(1)

    print("Source:", source_url.split("@")[-1].split("/")[0])
    print("Target:", target_url.split("@")[-1].split("/")[0])
    print()

    Base.metadata.create_all(bind=tgt_engine)
    print("Created tables on target.")

    src_session = sessionmaker(bind=src_engine)()
    tgt_session = sessionmaker(bind=tgt_engine)()

    try:
        for model in MODELS_IN_ORDER:
            name = model.__tablename__
            if name == "restaurant_tables":
                rows = src_session.query(model).all()
                for row in rows:
                    d = {c.key: getattr(row, c.key) for c in model.__table__.columns}
                    d["current_order_id"] = None
                    tgt_session.add(model(**d))
                tgt_session.commit()
                count = len(rows)
                print(f"  {name}: {count} rows")
            elif name == "orders":
                copy_table(src_session, tgt_session, model)
                count = src_session.query(model).count()
                src_tables = src_session.query(RestaurantTable).filter(
                    RestaurantTable.current_order_id.isnot(None)
                ).all()
                for st in src_tables:
                    tt = tgt_session.query(RestaurantTable).filter(
                        RestaurantTable.id == st.id
                    ).first()
                    if tt:
                        tt.current_order_id = st.current_order_id
                tgt_session.commit()
                print(f"  {name}: {count} rows (+ restored restaurant_tables.current_order_id)")
            else:
                count = copy_table(src_session, tgt_session, model)
                print(f"  {name}: {count} rows")
    finally:
        src_session.close()
        tgt_session.close()

    try:
        with tgt_engine.connect() as conn:
            conn.execute(text(V_SALES_VIEW_SQL))
            conn.commit()
        print("  v_sales: view created")
    except Exception as e:
        print("  v_sales: warning —", e)

    print()
    print("Done. To use the new DB, set in backend/.env:")
    print("  DATABASE_URL=" + target_url)
    print("Then restart the backend.")


if __name__ == "__main__":
    main()
