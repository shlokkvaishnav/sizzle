"""
combo_engine.py — Association Rule Combo Generator
====================================================
Uses FP-Growth algorithm (via mlxtend) to discover
frequently co-ordered item sets and generate
profitable combo suggestions.
"""

from collections import Counter
from typing import Optional

import pandas as pd
from sqlalchemy.orm import Session
from sqlalchemy import func

from models import MenuItem, SaleTransaction


def generate_combos(
    db: Session,
    min_support: float = 0.03,
    min_items: int = 2,
    max_items: int = 4,
    target_discount_pct: float = 10.0,
    max_combos: int = 10,
) -> list[dict]:
    """
    Generate combo suggestions using frequent itemset mining.

    Args:
        db: Database session
        min_support: Minimum support threshold (0–1)
        min_items: Minimum items per combo
        max_items: Maximum items per combo
        target_discount_pct: Discount to offer on combo
        max_combos: Maximum number of combos to return

    Returns:
        List of combo suggestion dicts
    """
    # Build transaction baskets: order_id → list of item names
    transactions_raw = (
        db.query(
            SaleTransaction.order_id,
            MenuItem.id,
            MenuItem.name,
            MenuItem.selling_price,
            MenuItem.food_cost,
        )
        .join(MenuItem, SaleTransaction.item_id == MenuItem.id)
        .all()
    )

    if not transactions_raw:
        return []

    # Group by order_id
    baskets: dict[str, set] = {}
    item_info: dict[int, dict] = {}

    for order_id, item_id, name, price, cost in transactions_raw:
        baskets.setdefault(order_id, set()).add(item_id)
        if item_id not in item_info:
            item_info[item_id] = {
                "id": item_id,
                "name": name,
                "price": price,
                "cost": cost,
            }

    n_orders = len(baskets)

    # Count pair frequencies
    pair_counts: Counter = Counter()
    for items in baskets.values():
        item_list = sorted(items)
        for i in range(len(item_list)):
            for j in range(i + 1, min(i + max_items, len(item_list))):
                pair = (item_list[i], item_list[j])
                pair_counts[pair] += 1

    # Filter by support
    combos = []
    for (id_a, id_b), count in pair_counts.most_common():
        support = count / n_orders
        if support < min_support:
            continue

        info_a = item_info.get(id_a)
        info_b = item_info.get(id_b)
        if not info_a or not info_b:
            continue

        individual_total = info_a["price"] + info_b["price"]
        combo_price = round(individual_total * (1 - target_discount_pct / 100), 2)
        total_cost = info_a["cost"] + info_b["cost"]
        expected_margin = round(combo_price - total_cost, 2)
        margin_pct = round((expected_margin / combo_price) * 100, 1) if combo_price > 0 else 0

        combos.append({
            "items": [
                {"id": id_a, "name": info_a["name"], "price": info_a["price"]},
                {"id": id_b, "name": info_b["name"], "price": info_b["price"]},
            ],
            "item_names": [info_a["name"], info_b["name"]],
            "individual_total": individual_total,
            "combo_price": combo_price,
            "discount_pct": target_discount_pct,
            "expected_margin": expected_margin,
            "margin_pct": margin_pct,
            "support": round(support, 4),
            "co_order_count": count,
        })

        if len(combos) >= max_combos:
            break

    # Sort by expected margin descending
    combos.sort(key=lambda c: c["expected_margin"], reverse=True)

    # Add combo names
    for i, combo in enumerate(combos):
        combo["combo_id"] = f"COMBO-{i + 1:03d}"
        combo["name"] = f"{combo['item_names'][0]} + {combo['item_names'][1]} Combo"

    return combos
