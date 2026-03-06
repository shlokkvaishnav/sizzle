"""Seed Dragon Wok sales using raw SQL to avoid ORM column mismatch."""
import sys, random
from datetime import datetime, timedelta, timezone
sys.path.insert(0, ".")

from sqlalchemy import text
from database import engine, SessionLocal
from models import MenuItem

db = SessionLocal()
items = db.query(MenuItem).filter(MenuItem.restaurant_id == 2).all()
print(f"Dragon Wok items: {len(items)}")
db.close()

now = datetime.now(timezone.utc)
order_counter = 9000
rows = []

for day_offset in range(60):
    date = now - timedelta(days=day_offset)
    num_orders = random.randint(15, 40)
    for _ in range(num_orders):
        order_counter += 1
        oid = "DW-{}-{}".format(date.strftime("%Y%m%d"), order_counter)
        otype = random.choice(["dine_in", "dine_in", "dine_in", "takeaway", "delivery"])
        chosen = random.sample(items, k=min(random.randint(2, 5), len(items)))
        for item in chosen:
            qty = random.randint(1, 3)
            sold = date.replace(hour=random.randint(11, 22), minute=random.randint(0, 59))
            rows.append({
                "rid": 2, "iid": item.id, "oid": oid,
                "q": qty, "up": item.selling_price,
                "tp": item.selling_price * qty,
                "ot": otype, "sa": sold,
            })

print(f"Inserting {len(rows)} sale rows...")
INSERT_SQL = text(
    "INSERT INTO sale_transactions "
    "(restaurant_id, item_id, order_id, quantity, unit_price, total_price, order_type, sold_at) "
    "VALUES (:rid, :iid, :oid, :q, :up, :tp, :ot, :sa)"
)

with engine.connect() as conn:
    for i, r in enumerate(rows):
        conn.execute(INSERT_SQL, r)
        if (i + 1) % 1000 == 0:
            conn.commit()
            print(f"  {i+1}/{len(rows)} committed...")
    conn.commit()

print(f"Done! {len(rows)} Dragon Wok sales created.")
