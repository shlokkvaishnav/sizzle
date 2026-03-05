"""
seed_data.py — Mock Data Generator
====================================
RUN THIS FIRST to populate the SQLite database with
sample menu items and realistic sales transactions.

Usage:
    cd backend
    python data/seed_data.py
"""

import json
import random
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add parent dir to path so we can import database/models
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from database import engine, Base, SessionLocal
from models import Category, MenuItem, SaleTransaction


def load_sample_menu() -> dict:
    """Load the base menu JSON."""
    menu_path = Path(__file__).parent / "sample_menu.json"
    with open(menu_path, "r", encoding="utf-8") as f:
        return json.load(f)


def seed_categories(db, categories_data: list) -> dict:
    """Insert categories and return name → id map."""
    cat_map = {}
    for idx, cat in enumerate(categories_data):
        obj = Category(
            name=cat["name"],
            name_hi=cat.get("name_hi", ""),
            display_order=idx,
            is_active=True,
        )
        db.add(obj)
        db.flush()
        cat_map[cat["name"]] = obj.id
    return cat_map


def seed_menu_items(db, items_data: list, cat_map: dict) -> list:
    """Insert menu items and return list of MenuItem objects."""
    items = []
    for item_data in items_data:
        obj = MenuItem(
            name=item_data["name"],
            name_hi=item_data.get("name_hi", ""),
            category_id=cat_map.get(item_data["category"]),
            selling_price=item_data["selling_price"],
            food_cost=item_data["food_cost"],
            is_veg=item_data.get("is_veg", True),
            is_available=True,
            is_bestseller="bestseller" in item_data.get("tags", []),
            tags=item_data.get("tags", []),
        )
        db.add(obj)
        db.flush()
        items.append(obj)
    return items


def seed_sales(db, items: list, num_days: int = 30, orders_per_day: int = 40):
    """
    Generate realistic sales transactions.
    Popular items (bestsellers) get higher order frequency.
    """
    order_types = ["dine_in", "takeaway", "delivery"]
    type_weights = [0.55, 0.25, 0.20]
    order_counter = 0

    # Popularity weights — bestsellers ordered 3x more
    item_weights = []
    for item in items:
        weight = 3.0 if item.is_bestseller else 1.0
        # Cheaper items ordered more frequently
        if item.selling_price < 100:
            weight *= 1.5
        elif item.selling_price > 350:
            weight *= 0.6
        item_weights.append(weight)

    total_weight = sum(item_weights)
    item_probs = [w / total_weight for w in item_weights]

    now = datetime.utcnow()

    for day_offset in range(num_days):
        date = now - timedelta(days=day_offset)
        day_orders = random.randint(
            int(orders_per_day * 0.6), int(orders_per_day * 1.4)
        )

        for _ in range(day_orders):
            order_counter += 1
            order_id = f"ORD-{order_counter:05d}"
            order_type = random.choices(order_types, weights=type_weights, k=1)[0]

            # Each order has 2–6 items
            num_items = random.randint(2, 6)
            ordered_items = random.choices(items, weights=item_probs, k=num_items)

            for item in ordered_items:
                qty = random.choices([1, 2, 3], weights=[0.7, 0.25, 0.05], k=1)[0]
                # Slight price variation (discounts, combos)
                unit_price = item.selling_price * random.uniform(0.95, 1.0)

                sale = SaleTransaction(
                    item_id=item.id,
                    order_id=order_id,
                    quantity=qty,
                    unit_price=round(unit_price, 2),
                    total_price=round(unit_price * qty, 2),
                    order_type=order_type,
                    sold_at=date.replace(
                        hour=random.randint(11, 22),
                        minute=random.randint(0, 59),
                    ),
                )
                db.add(sale)

    print(f"   Generated {order_counter} orders across {num_days} days")


def main():
    print("🌱 Seeding Petpooja database...")
    print("=" * 50)

    # Create all tables
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()

    try:
        # Clear existing data
        db.query(SaleTransaction).delete()
        db.query(MenuItem).delete()
        db.query(Category).delete()
        db.commit()

        # Load menu
        menu_data = load_sample_menu()

        # Seed categories
        print("📁 Seeding categories...")
        cat_map = seed_categories(db, menu_data["categories"])
        print(f"   {len(cat_map)} categories created")

        # Seed menu items
        print("🍽️  Seeding menu items...")
        items = seed_menu_items(db, menu_data["items"], cat_map)
        print(f"   {len(items)} menu items created")

        # Seed sales transactions
        print("📊 Generating sales data (30 days)...")
        seed_sales(db, items, num_days=30, orders_per_day=40)

        db.commit()
        print("=" * 50)
        print("✅ Database seeded successfully!")
        print(f"   Database: data/restaurant.db")

    except Exception as e:
        db.rollback()
        print(f"❌ Error: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
