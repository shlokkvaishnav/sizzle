import os
from collections import Counter
from typing import Optional

import pandas as pd
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from mlxtend.frequent_patterns import fpgrowth, association_rules

from models import MenuItem, SaleTransaction, ComboSuggestion

# Global state to track when we last trained the ML model
_last_trained_order_count = 0


def generate_combos(
    db: Session,
    min_support: float = 0.03,
    target_discount_pct: float = 10.0,
    max_combos: int = 10,
    window_size: int = 500,
    update_threshold: int = 50,
) -> list[dict]:
    """
    Generate combo suggestions using an ML pipeline (FP-Growth).
    Automatically adapts to new trends using a sliding window.

    - window_size: Analyze only the last N orders to stay relevant.
    - update_threshold: Only re-run the ML model if at least N new orders have arrived.
    """
    global _last_trained_order_count

    # 1. Determine if we need to re-train the ML model
    total_orders = db.query(func.count(func.distinct(SaleTransaction.order_id))).scalar() or 0
    
    # Check if we have existing combos in the DB
    existing_combos_count = db.query(ComboSuggestion).count()

    # Trigger ML Training if: No combos exist OR we have enough new orders Since last train
    # Note: If server restarts, _last_trained_order_count is 0, so it forces a re-train
    needs_training = (existing_combos_count == 0) or (total_orders >= _last_trained_order_count + update_threshold)

    if needs_training and total_orders > 0:
        print(f"🧠 Training Combo ML Model (Current Orders: {total_orders}, Window: Last {window_size})")
        _run_ml_pipeline(db, min_support, target_discount_pct, max_combos, window_size)
        _last_trained_order_count = total_orders

    # 2. Return cached combos from the database (instantaneous)
    return _fetch_combos_from_db(db)


def _run_ml_pipeline(
    db: Session,
    min_support: float,
    target_discount_pct: float,
    max_combos: int,
    window_size: int,
):
    """Internal function that runs the heavy mlxtend Apriori/FP-Growth algorithms."""
    # Step A: Get the most recent X distinct order IDs
    recent_order_ids_subquery = (
        db.query(SaleTransaction.order_id, func.max(SaleTransaction.sold_at).label("latest_sold_at"))
        .group_by(SaleTransaction.order_id)
        .order_by(desc("latest_sold_at"))
        .limit(window_size)
        .subquery()
    )

    # Step B: Get all transactions for these recent orders
    transactions_raw = (
        db.query(
            SaleTransaction.order_id,
            MenuItem.id,
            MenuItem.name,
            MenuItem.selling_price,
            MenuItem.food_cost,
        )
        .join(MenuItem, SaleTransaction.item_id == MenuItem.id)
        .join(recent_order_ids_subquery, SaleTransaction.order_id == recent_order_ids_subquery.c.order_id)
        .all()
    )

    if not transactions_raw:
        return

    # Group by order_id -> list of items
    baskets = {}
    item_info = {}

    for order_id, item_id, name, price, cost in transactions_raw:
        if order_id not in baskets:
            baskets[order_id] = []
        baskets[order_id].append(item_id)
        
        if item_id not in item_info:
            item_info[item_id] = {"id": item_id, "name": name, "price": price, "cost": cost}

    # Step C: Prepare data for ML (One-Hot Encoding)
    # mlxtend expects a dataframe where rows are transactions, columns are items, values are True/False
    dataset = list(baskets.values())
    
    # We use Pandas to one-hot encode
    from mlxtend.preprocessing import TransactionEncoder
    te = TransactionEncoder()
    te_ary = te.fit(dataset).transform(dataset)
    df = pd.DataFrame(te_ary, columns=te.columns_)

    # Step D: Run FP-Growth (faster than Apriori for large sparse datasets)
    frequent_itemsets = fpgrowth(df, min_support=min_support, use_colnames=True)
    
    if frequent_itemsets.empty:
        return

    # Step E: Generate Association Rules to find high confidence pairs/combos
    rules = association_rules(frequent_itemsets, metric="confidence", min_threshold=0.1, num_itemsets=len(frequent_itemsets))
    
    # Step F: Process, score, and persist the results to DB
    _process_and_save_rules(db, rules, item_info, target_discount_pct, max_combos)


def _process_and_save_rules(db: Session, rules: pd.DataFrame, item_info: dict, discount_pct: float, max_combos: int):
    """Parses ML association rules and persists them to ComboSuggestion table."""
    # We only care about 2-item or 3-item combos currently to keep it simple
    # The itemsets in rules are frozensets
    
    # Combine antecedents and consequents to form the full combo set
    # Create a unique list of combos since A->B and B->A refer to the same physical combo
    processed_combos = {}
    
    for idx, row in rules.iterrows():
        combo_items = tuple(sorted(list(row['antecedents']) + list(row['consequents'])))
        
        # Limit bundle size
        if len(combo_items) < 2 or len(combo_items) > 3:
            continue
            
        # Keep the one with highest lift/confidence if duplicate
        if combo_items not in processed_combos or row['lift'] > processed_combos[combo_items]['lift']:
            processed_combos[combo_items] = row

    scored_combos = []
    
    for combo_ids, rule in processed_combos.items():
        # Check if all items exist in our lookup map
        if any(item_id not in item_info for item_id in combo_ids):
            continue
            
        items_data = [item_info[i] for i in combo_ids]
        item_names = [i["name"] for i in items_data]
        
        individual_total = sum(i["price"] for i in items_data)
        combo_price = round(individual_total * (1 - discount_pct / 100), 2)
        total_cost = sum(i["cost"] for i in items_data)
        
        expected_margin = round(combo_price - total_cost, 2)
        margin_pct = round((expected_margin / combo_price) * 100, 1) if combo_price > 0 else 0
        
        scored_combos.append({
            "name": " + ".join(item_names) + " Combo",
            "item_ids": list(combo_ids),
            "item_names": item_names,
            "individual_total": individual_total,
            "combo_price": combo_price,
            "discount_pct": discount_pct,
            "expected_margin": expected_margin,
            "margin_pct": margin_pct,
            "support": float(rule["support"]),
            "confidence": float(rule["confidence"]),
            "items_data": items_data  # Kept temporarily for sorting/display
        })

    # Sort by absolute expected margin descending and take top N
    scored_combos.sort(key=lambda x: x["expected_margin"], reverse=True)
    top_combos = scored_combos[:max_combos]

    # Database Persistence
    try:
        # Clear existing combos
        db.query(ComboSuggestion).delete()
        
        # Insert new ones
        for i, c in enumerate(top_combos):
            db_combo = ComboSuggestion(
                name=c["name"],
                item_ids=c["item_ids"],
                item_names=c["item_names"],
                individual_total=c["individual_total"],
                combo_price=c["combo_price"],
                discount_pct=c["discount_pct"],
                expected_margin=c["expected_margin"],
                support=c["support"],
                confidence=c["confidence"],
            )
            db.add(db_combo)
            
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"Error saving ML combos to DB: {e}")


def _fetch_combos_from_db(db: Session) -> list[dict]:
    """Retrieves standard format combos from the Database to serve to the API."""
    db_combos = db.query(ComboSuggestion).order_by(desc(ComboSuggestion.expected_margin)).all()
    
    result = []
    for i, c in enumerate(db_combos):
        # We need to format it to match the previous API contract so frontend doesn't break
        margin_pct = round((c.expected_margin / c.combo_price) * 100, 1) if c.combo_price > 0 else 0
        
        combo_dict = {
            "combo_id": f"COMBO-{i + 1:03d}",
            "name": c.name,
            "items": [{"id": item_id} for item_id in c.item_ids], # Minimal stub
            "item_names": c.item_names,
            "individual_total": c.individual_total,
            "combo_price": c.combo_price,
            "discount_pct": c.discount_pct,
            "expected_margin": c.expected_margin,
            "margin_pct": margin_pct,
            "support": round(c.support, 4),
            "confidence": round(c.confidence, 4) if getattr(c, "confidence", None) else 0.0,
            "co_order_count": int(c.support * 500) # approximate
        }
        result.append(combo_dict)
        
    return result
