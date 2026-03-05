"""
order_builder.py — Order JSON + KOT Generator
================================================
Builds a structured order from parsed items and
generates a Kitchen Order Ticket (KOT).
"""

import uuid
from datetime import datetime


def build_order(
    items: list[dict],
    session_id: str = None,
    order_type: str = "dine_in",
    table_number: str = None,
) -> dict:
    """
    Build a structured order JSON from parsed items.

    Args:
        items: Matched items with quantity and modifiers
        session_id: Session/order ID (auto-generated if None)
        order_type: dine_in | takeaway | delivery
        table_number: Table number for dine-in

    Returns:
        Complete order dict
    """
    order_id = session_id or f"ORD-{uuid.uuid4().hex[:8].upper()}"

    order_items = []
    total = 0.0

    for item in items:
        qty = item.get("quantity", 1)
        price = item.get("selling_price", 0)
        line_total = price * qty
        total += line_total

        order_items.append({
            "item_id": item["item_id"],
            "name": item["name"],
            "name_hi": item.get("name_hi", ""),
            "quantity": qty,
            "unit_price": price,
            "line_total": round(line_total, 2),
            "modifiers": item.get("modifiers", {}),
            "is_veg": item.get("is_veg", True),
        })

    return {
        "order_id": order_id,
        "items": order_items,
        "item_count": len(order_items),
        "total_quantity": sum(i["quantity"] for i in order_items),
        "subtotal": round(total, 2),
        "tax": round(total * 0.05, 2),  # 5% GST
        "total": round(total * 1.05, 2),
        "order_type": order_type,
        "table_number": table_number,
        "status": "building",
        "created_at": datetime.utcnow().isoformat(),
    }


def generate_kot(order: dict) -> dict:
    """
    Generate a Kitchen Order Ticket from a built order.

    Returns:
        KOT dict with kitchen-friendly formatting
    """
    if not order or not order.get("items"):
        return {}

    kot_items = []
    for item in order["items"]:
        kot_line = {
            "name": item["name"],
            "qty": item["quantity"],
            "modifiers": [],
            "notes": "",
        }

        mods = item.get("modifiers", {})

        # Add spice level if not default
        if mods.get("spice_level") and mods["spice_level"] != "medium":
            kot_line["modifiers"].append(f"Spice: {mods['spice_level']}")

        # Add size if not default
        if mods.get("size") and mods["size"] != "regular":
            kot_line["modifiers"].append(f"Size: {mods['size']}")

        # Add add-ons
        for addon in mods.get("add_ons", []):
            kot_line["modifiers"].append(addon.replace("_", " ").title())

        # Special instructions
        if mods.get("special_instructions"):
            kot_line["notes"] = mods["special_instructions"]

        kot_items.append(kot_line)

    return {
        "kot_id": f"KOT-{order['order_id']}",
        "order_id": order["order_id"],
        "table": order.get("table_number", "-"),
        "order_type": order.get("order_type", "dine_in"),
        "items": kot_items,
        "total_items": sum(i["qty"] for i in kot_items),
        "timestamp": datetime.utcnow().strftime("%d-%b %H:%M"),
        "priority": "normal",
    }
