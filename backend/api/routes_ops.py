"""
routes_ops.py — Operations & Back-Office Endpoints
===================================================
/api/ops/* — Orders, tables, inventory, reports, settings
"""

import csv
import logging
from datetime import datetime, timedelta, timezone, date
from io import StringIO

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import func, desc

from database import get_db
from models import Order, OrderItem, RestaurantTable, Ingredient, StockLog, SaleTransaction, MenuItem, Category

router = APIRouter()
logger = logging.getLogger("petpooja.api.ops")


def _utcnow_fn():
    return datetime.now(timezone.utc)


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid date format: {value}. Use YYYY-MM-DD.")


class TableUpdateInput(BaseModel):
    status: str = Field(..., pattern=r"^(empty|occupied|reserved|cleaning)$")
    current_order_id: str | None = None


class TableBookInput(BaseModel):
    guest_name: str | None = None
    guest_count: int | None = None


class TableSettleInput(BaseModel):
    payment_method: str = Field("cash", pattern=r"^(cash|card|upi)$")


class StockAdjustInput(BaseModel):
    ingredient_id: int
    change_qty: float
    reason: str = Field(..., pattern=r"^(purchase|usage|waste|adjustment)$")
    note: str | None = None
    staff_id: int | None = None


class IngredientUpdateInput(BaseModel):
    reorder_level: float | None = None
    cost_per_unit: float | None = None


@router.get("/orders")
def get_orders(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    days: int = Query(30, ge=1, le=365),
    status: str | None = Query(None, pattern=r"^(building|confirmed|cancelled)$"),
    order_type: str | None = Query(None, pattern=r"^(dine_in|takeaway|delivery)$"),
    source: str | None = Query(None, pattern=r"^(voice|manual)$"),
    search: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    db: Session = Depends(get_db),
):
    """
    Orders list + summary metrics.
    """
    try:
        sd = _parse_date(start_date)
        ed = _parse_date(end_date)

        if sd or ed:
            start_dt = datetime.combine(sd or date.min, datetime.min.time(), tzinfo=timezone.utc)
            end_dt = datetime.combine(ed or date.max, datetime.max.time(), tzinfo=timezone.utc)
        else:
            cutoff = datetime.now(timezone.utc) - timedelta(days=days)
            start_dt = cutoff
            end_dt = datetime.now(timezone.utc)

        filters = [Order.created_at >= start_dt, Order.created_at <= end_dt]
        if status:
            filters.append(Order.status == status)
        if order_type:
            filters.append(Order.order_type == order_type)
        if source:
            filters.append(Order.source == source)
        if search:
            like = f"%{search.strip()}%"
            filters.append(
                (Order.order_id.ilike(like)) | (Order.order_number.ilike(like))
            )

        total_orders = db.query(func.count(Order.id)).filter(*filters).scalar() or 0
        total_revenue = (
            db.query(func.coalesce(func.sum(Order.total_amount), 0.0))
            .filter(*filters, Order.status == "confirmed")
            .scalar()
        ) or 0.0

        avg_order_value = (total_revenue / total_orders) if total_orders else 0.0

        status_counts = (
            db.query(Order.status, func.count(Order.id))
            .filter(*filters)
            .group_by(Order.status)
            .all()
        )
        status_map = {s: c for s, c in status_counts}

        orders = (
            db.query(
                Order.order_id,
                Order.order_number,
                Order.total_amount,
                Order.status,
                Order.order_type,
                Order.table_number,
                Order.source,
                Order.created_at,
            )
            .filter(*filters)
            .order_by(desc(Order.created_at))
            .offset(offset)
            .limit(limit)
            .all()
        )

        return {
            "summary": {
                "total_orders": int(total_orders),
                "total_revenue": round(float(total_revenue), 2),
                "avg_order_value": round(float(avg_order_value), 2),
                "open_orders": int(status_map.get("building", 0)),
                "confirmed_orders": int(status_map.get("confirmed", 0)),
                "cancelled_orders": int(status_map.get("cancelled", 0)),
            },
            "orders": [
                {
                    "order_id": o.order_id,
                    "order_number": o.order_number,
                    "total_amount": o.total_amount,
                    "status": o.status,
                    "order_type": o.order_type,
                    "table_number": o.table_number,
                    "source": o.source,
                    "created_at": o.created_at.isoformat() if o.created_at else None,
                }
                for o in orders
            ],
            "count": len(orders),
            "offset": offset,
            "limit": limit,
            "total": int(total_orders),
        }
    except Exception as e:
        logger.exception("Error fetching orders")
        raise HTTPException(status_code=500, detail=f"Orders fetch failed: {e}")


@router.get("/tables")
def get_tables(
    status: str | None = Query(None, pattern=r"^(empty|occupied|reserved|cleaning)$"),
    section: str | None = None,
    search: str | None = None,
    db: Session = Depends(get_db),
):
    """
    Table status and reservation view — includes order details with items for occupied tables.
    """
    try:
        filters = []
        if status:
            filters.append(RestaurantTable.status == status)
        if section:
            filters.append(RestaurantTable.section == section)
        if search:
            like = f"%{search.strip()}%"
            filters.append(RestaurantTable.table_number.ilike(like))

        tables = db.query(RestaurantTable).filter(*filters).order_by(RestaurantTable.table_number.asc()).all()
        status_counts = (
            db.query(RestaurantTable.status, func.count(RestaurantTable.id))
            .group_by(RestaurantTable.status)
            .all()
        )
        status_map = {s: c for s, c in status_counts}

        result_tables = []
        for t in tables:
            table_data = {
                "table_id": t.id,
                "table_number": t.table_number,
                "capacity": t.capacity,
                "section": t.section,
                "status": t.status,
                "current_order_id": t.current_order_id,
                "order": None,
            }
            # If occupied and has an order, load the order details with items
            if t.current_order_id:
                order = db.query(Order).filter(Order.order_id == t.current_order_id).first()
                if order:
                    items = (
                        db.query(
                            OrderItem.quantity,
                            OrderItem.unit_price,
                            OrderItem.line_total,
                            MenuItem.name,
                        )
                        .join(MenuItem, MenuItem.id == OrderItem.item_id)
                        .filter(OrderItem.order_id == order.order_id)
                        .all()
                    )
                    table_data["order"] = {
                        "order_id": order.order_id,
                        "order_number": order.order_number,
                        "total_amount": order.total_amount,
                        "status": order.status,
                        "order_type": order.order_type,
                        "source": order.source,
                        "created_at": order.created_at.isoformat() if order.created_at else None,
                        "items": [
                            {
                                "name": item.name,
                                "quantity": item.quantity,
                                "unit_price": item.unit_price,
                                "line_total": item.line_total,
                            }
                            for item in items
                        ],
                    }
            result_tables.append(table_data)

        return {
            "summary": {
                "total_tables": len(tables),
                "occupied": int(status_map.get("occupied", 0)),
                "reserved": int(status_map.get("reserved", 0)),
                "empty": int(status_map.get("empty", 0)),
                "cleaning": int(status_map.get("cleaning", 0)),
            },
            "tables": result_tables,
        }
    except Exception as e:
        logger.exception("Error fetching tables")
        raise HTTPException(status_code=500, detail=f"Tables fetch failed: {e}")


@router.patch("/tables/{table_id}")
def update_table(
    table_id: int,
    body: TableUpdateInput,
    db: Session = Depends(get_db),
):
    """
    Update table status and current order assignment.
    """
    try:
        table = db.query(RestaurantTable).filter(RestaurantTable.id == table_id).first()
        if not table:
            raise HTTPException(status_code=404, detail="Table not found")

        table.status = body.status
        table.current_order_id = body.current_order_id
        db.commit()
        db.refresh(table)

        return {
            "table_id": table.id,
            "table_number": table.table_number,
            "status": table.status,
            "current_order_id": table.current_order_id,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error updating table")
        raise HTTPException(status_code=500, detail=f"Table update failed: {e}")


@router.post("/tables/{table_id}/book")
def book_table(
    table_id: int,
    body: TableBookInput,
    restaurant_id: int | None = Query(None),
    db: Session = Depends(get_db),
):
    """
    Book a free table — creates a new order for dine_in and marks table occupied.
    """
    try:
        table = db.query(RestaurantTable).filter(RestaurantTable.id == table_id).first()
        if not table:
            raise HTTPException(status_code=404, detail="Table not found")
        if table.status != "empty":
            raise HTTPException(status_code=400, detail=f"Table is currently {table.status}, cannot book")

        # Generate unique order_id
        import uuid
        order_id = f"ORD-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
        order_number = f"#{db.query(func.count(Order.id)).scalar() + 1}"

        new_order = Order(
            order_id=order_id,
            order_number=order_number,
            total_amount=0.0,
            status="building",
            order_type="dine_in",
            table_number=table.table_number,
            source="manual",
        )
        # Set optional FK columns only if they exist on the model
        if restaurant_id is not None:
            new_order.restaurant_id = restaurant_id
        try:
            new_order.table_id = table.id
        except Exception:
            pass
        db.add(new_order)

        table.status = "occupied"
        table.current_order_id = order_id

        db.commit()
        db.refresh(table)
        db.refresh(new_order)

        return {
            "table_id": table.id,
            "table_number": table.table_number,
            "status": table.status,
            "order_id": order_id,
            "order_number": order_number,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error booking table")
        raise HTTPException(status_code=500, detail=f"Table booking failed: {e}")


@router.post("/tables/{table_id}/settle")
def settle_table(
    table_id: int,
    body: TableSettleInput,
    db: Session = Depends(get_db),
):
    """
    Settle the bill for an occupied table:
    1. Mark the order as 'confirmed'
    2. Create sale_transactions for each order item
    3. Free the table
    """
    try:
        table = db.query(RestaurantTable).filter(RestaurantTable.id == table_id).first()
        if not table:
            raise HTTPException(status_code=404, detail="Table not found")
        if table.status != "occupied":
            raise HTTPException(status_code=400, detail="Table is not occupied")
        if not table.current_order_id:
            raise HTTPException(status_code=400, detail="No order linked to this table")

        order = db.query(Order).filter(Order.order_id == table.current_order_id).first()
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")

        # Mark order as confirmed
        order.status = "confirmed"
        order.updated_at = _utcnow_fn()

        # Recalculate total from order items
        order_items = db.query(OrderItem).filter(OrderItem.order_id == order.order_id).all()
        total = sum(oi.line_total for oi in order_items)
        order.total_amount = total

        # Create sale_transactions for each order item (so analytics / orders page picks them up)
        for oi in order_items:
            sale = SaleTransaction(
                item_id=oi.item_id,
                order_id=order.order_id,
                quantity=oi.quantity,
                unit_price=oi.unit_price,
                total_price=oi.line_total,
                order_type=order.order_type or "dine_in",
                shift_id=order.shift_id,
            )
            db.add(sale)

        # Free the table
        table.status = "empty"
        table.current_order_id = None

        db.commit()

        return {
            "table_id": table.id,
            "table_number": table.table_number,
            "status": "empty",
            "order_id": order.order_id,
            "total_amount": round(total, 2),
            "payment_method": body.payment_method,
            "settled": True,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error settling table")
        raise HTTPException(status_code=500, detail=f"Table settle failed: {e}")


@router.post("/tables/{table_id}/reserve")
def reserve_table(
    table_id: int,
    db: Session = Depends(get_db),
):
    """
    Reserve a free table.
    """
    try:
        table = db.query(RestaurantTable).filter(RestaurantTable.id == table_id).first()
        if not table:
            raise HTTPException(status_code=404, detail="Table not found")
        if table.status != "empty":
            raise HTTPException(status_code=400, detail=f"Table is currently {table.status}, cannot reserve")

        table.status = "reserved"
        db.commit()
        db.refresh(table)

        return {
            "table_id": table.id,
            "table_number": table.table_number,
            "status": "reserved",
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error reserving table")
        raise HTTPException(status_code=500, detail=f"Table reserve failed: {e}")


@router.post("/tables/{table_id}/unreserve")
def unreserve_table(
    table_id: int,
    db: Session = Depends(get_db),
):
    """
    Remove reservation — set table back to empty.
    """
    try:
        table = db.query(RestaurantTable).filter(RestaurantTable.id == table_id).first()
        if not table:
            raise HTTPException(status_code=404, detail="Table not found")
        if table.status != "reserved":
            raise HTTPException(status_code=400, detail="Table is not reserved")

        table.status = "empty"
        db.commit()
        db.refresh(table)

        return {
            "table_id": table.id,
            "table_number": table.table_number,
            "status": "empty",
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error unreserving table")
        raise HTTPException(status_code=500, detail=f"Table unreserve failed: {e}")


@router.post("/tables/{table_id}/seat")
def seat_reserved_table(
    table_id: int,
    db: Session = Depends(get_db),
):
    """
    Seat guests at a reserved table — creates order and marks occupied.
    """
    try:
        table = db.query(RestaurantTable).filter(RestaurantTable.id == table_id).first()
        if not table:
            raise HTTPException(status_code=404, detail="Table not found")
        if table.status != "reserved":
            raise HTTPException(status_code=400, detail="Table is not reserved")

        import uuid
        order_id = f"ORD-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
        order_number = f"#{db.query(func.count(Order.id)).scalar() + 1}"

        new_order = Order(
            order_id=order_id,
            order_number=order_number,
            total_amount=0.0,
            status="building",
            order_type="dine_in",
            table_number=table.table_number,
            source="manual",
        )
        try:
            new_order.table_id = table.id
        except Exception:
            pass
        db.add(new_order)

        table.status = "occupied"
        table.current_order_id = order_id

        db.commit()

        return {
            "table_id": table.id,
            "table_number": table.table_number,
            "status": "occupied",
            "order_id": order_id,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error seating at table")
        raise HTTPException(status_code=500, detail=f"Table seat failed: {e}")


@router.get("/menu-items")
def get_menu_items_list(
    search: str | None = None,
    restaurant_id: int | None = Query(None),
    db: Session = Depends(get_db),
):
    """
    Return available menu items for adding to orders.
    Filters by restaurant_id when provided so only that restaurant's items appear.
    """
    try:
        filters = [MenuItem.is_available == True]
        if restaurant_id is not None:
            filters.append(MenuItem.restaurant_id == restaurant_id)
        if search:
            like = f"%{search.strip()}%"
            filters.append(MenuItem.name.ilike(like))

        items = (
            db.query(MenuItem.id, MenuItem.name, MenuItem.selling_price, MenuItem.is_veg, Category.name.label("category"))
            .outerjoin(Category, Category.id == MenuItem.category_id)
            .filter(*filters)
            .order_by(MenuItem.name.asc())
            .limit(100)
            .all()
        )
        return {
            "items": [
                {
                    "id": i.id,
                    "name": i.name,
                    "price": i.selling_price,
                    "is_veg": i.is_veg,
                    "category": i.category or "Uncategorized",
                }
                for i in items
            ],
        }
    except Exception as e:
        logger.exception("Error fetching menu items")
        raise HTTPException(status_code=500, detail=f"Menu items fetch failed: {e}")


@router.post("/tables/{table_id}/add-item")
def add_item_to_table_order(
    table_id: int,
    item_id: int = Query(...),
    quantity: int = Query(1, ge=1),
    db: Session = Depends(get_db),
):
    """
    Add a menu item to the order on a given table. Creates order item and updates order total.
    """
    try:
        table = db.query(RestaurantTable).filter(RestaurantTable.id == table_id).first()
        if not table:
            raise HTTPException(status_code=404, detail="Table not found")
        if table.status != "occupied" or not table.current_order_id:
            raise HTTPException(status_code=400, detail="Table has no active order")

        item = db.query(MenuItem).filter(MenuItem.id == item_id).first()
        if not item:
            raise HTTPException(status_code=404, detail="Menu item not found")

        line_total = item.selling_price * quantity

        # Check if already in order — increment quantity
        existing = (
            db.query(OrderItem)
            .filter(OrderItem.order_id == table.current_order_id, OrderItem.item_id == item_id)
            .first()
        )
        if existing:
            existing.quantity += quantity
            existing.line_total = existing.quantity * existing.unit_price
        else:
            oi = OrderItem(
                order_id=table.current_order_id,
                item_id=item_id,
                quantity=quantity,
                unit_price=item.selling_price,
                line_total=line_total,
            )
            db.add(oi)

        # Update order total
        order = db.query(Order).filter(Order.order_id == table.current_order_id).first()
        if order:
            all_items = db.query(func.coalesce(func.sum(OrderItem.line_total), 0.0)).filter(
                OrderItem.order_id == order.order_id
            ).scalar()
            # Include the item we just added (if new, it's not committed yet — so add manually)
            if not existing:
                order.total_amount = float(all_items) + line_total
            else:
                # Recalculate since existing was updated
                order.total_amount = float(all_items) + (item.selling_price * quantity)

        db.commit()

        # Re-query for accurate total
        if order:
            db.refresh(order)

        return {
            "table_id": table.id,
            "order_id": table.current_order_id,
            "item_name": item.name,
            "quantity": quantity,
            "line_total": line_total,
            "order_total": order.total_amount if order else 0,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error adding item to table order")
        raise HTTPException(status_code=500, detail=f"Add item failed: {e}")


@router.get("/inventory")
def get_inventory(
    days: int = Query(30, ge=7, le=365),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    search: str | None = None,
    low_stock_only: bool = False,
    db: Session = Depends(get_db),
):
    """
    Inventory overview with low-stock and usage/waste.
    """
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)

        filters = []
        if search:
            like = f"%{search.strip()}%"
            filters.append(Ingredient.name.ilike(like))
        if low_stock_only:
            filters.append(Ingredient.current_stock <= Ingredient.reorder_level)

        ingredients_query = db.query(Ingredient).filter(*filters)
        total_ingredients = ingredients_query.count()

        total_stock_value = (
            db.query(func.coalesce(func.sum(Ingredient.current_stock * Ingredient.cost_per_unit), 0.0))
            .filter(*filters)
            .scalar()
        ) or 0.0

        low_stock = (
            db.query(Ingredient)
            .filter(*filters, Ingredient.current_stock <= Ingredient.reorder_level)
            .order_by(Ingredient.name.asc())
            .all()
        )

        ingredients = (
            ingredients_query
            .order_by(Ingredient.name.asc())
            .offset(offset)
            .limit(limit)
            .all()
        )

        usage_waste = (
            db.query(
                StockLog.reason,
                func.coalesce(func.sum(func.abs(StockLog.change_qty)), 0.0).label("qty"),
            )
            .filter(StockLog.created_at >= cutoff)
            .group_by(StockLog.reason)
            .all()
        )
        usage_map = {r: float(qty) for r, qty in usage_waste}

        return {
            "summary": {
                "total_ingredients": int(total_ingredients),
                "low_stock_count": len(low_stock),
                "total_stock_value": round(float(total_stock_value), 2),
                "usage_qty": round(usage_map.get("usage", 0.0), 2),
                "waste_qty": round(usage_map.get("waste", 0.0), 2),
            },
            "low_stock": [
                {
                    "ingredient_id": i.id,
                    "name": i.name,
                    "unit": i.unit,
                    "current_stock": i.current_stock,
                    "reorder_level": i.reorder_level,
                    "cost_per_unit": i.cost_per_unit,
                }
                for i in low_stock
            ],
            "ingredients": [
                {
                    "ingredient_id": i.id,
                    "name": i.name,
                    "unit": i.unit,
                    "current_stock": i.current_stock,
                    "reorder_level": i.reorder_level,
                    "cost_per_unit": i.cost_per_unit,
                }
                for i in ingredients
            ],
            "count": len(ingredients),
            "offset": offset,
            "limit": limit,
        }
    except Exception as e:
        logger.exception("Error fetching inventory")
        raise HTTPException(status_code=500, detail=f"Inventory fetch failed: {e}")


@router.post("/inventory/adjust")
def adjust_inventory(
    body: StockAdjustInput,
    db: Session = Depends(get_db),
):
    """
    Adjust ingredient stock and log the change.
    """
    try:
        ingredient = db.query(Ingredient).filter(Ingredient.id == body.ingredient_id).first()
        if not ingredient:
            raise HTTPException(status_code=404, detail="Ingredient not found")

        new_stock = (ingredient.current_stock or 0) + body.change_qty
        if new_stock < 0:
            raise HTTPException(status_code=400, detail="Stock cannot go below zero")

        ingredient.current_stock = new_stock
        log = StockLog(
            ingredient_id=ingredient.id,
            change_qty=body.change_qty,
            reason=body.reason,
            note=body.note,
            staff_id=body.staff_id,
        )
        db.add(log)
        db.commit()
        db.refresh(ingredient)

        return {
            "ingredient_id": ingredient.id,
            "name": ingredient.name,
            "current_stock": ingredient.current_stock,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error adjusting inventory")
        raise HTTPException(status_code=500, detail=f"Inventory adjustment failed: {e}")


@router.patch("/inventory/{ingredient_id}")
def update_ingredient(
    ingredient_id: int,
    body: IngredientUpdateInput,
    db: Session = Depends(get_db),
):
    """
    Update ingredient metadata (reorder level, cost).
    """
    try:
        ingredient = db.query(Ingredient).filter(Ingredient.id == ingredient_id).first()
        if not ingredient:
            raise HTTPException(status_code=404, detail="Ingredient not found")

        if body.reorder_level is not None:
            ingredient.reorder_level = body.reorder_level
        if body.cost_per_unit is not None:
            ingredient.cost_per_unit = body.cost_per_unit

        db.commit()
        db.refresh(ingredient)

        return {
            "ingredient_id": ingredient.id,
            "reorder_level": ingredient.reorder_level,
            "cost_per_unit": ingredient.cost_per_unit,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error updating ingredient")
        raise HTTPException(status_code=500, detail=f"Ingredient update failed: {e}")


@router.get("/reports")
def get_reports(
    days: int = Query(14, ge=7, le=90),
    top_n: int = Query(8, ge=3, le=20),
    db: Session = Depends(get_db),
):
    """
    Lightweight operational reports for charts.
    """
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)

        daily = (
            db.query(
                func.date(SaleTransaction.sold_at).label("day"),
                func.coalesce(func.sum(SaleTransaction.total_price), 0.0).label("revenue"),
                func.coalesce(func.sum(SaleTransaction.quantity), 0).label("items"),
                func.count(func.distinct(SaleTransaction.order_id)).label("orders"),
            )
            .filter(SaleTransaction.sold_at >= cutoff)
            .group_by(func.date(SaleTransaction.sold_at))
            .order_by(func.date(SaleTransaction.sold_at).asc())
            .all()
        )

        top_items = (
            db.query(
                MenuItem.id,
                MenuItem.name,
                func.coalesce(func.sum(SaleTransaction.total_price), 0.0).label("revenue"),
                func.coalesce(func.sum(SaleTransaction.quantity), 0).label("qty"),
            )
            .join(SaleTransaction, SaleTransaction.item_id == MenuItem.id)
            .filter(SaleTransaction.sold_at >= cutoff)
            .group_by(MenuItem.id, MenuItem.name)
            .order_by(desc("revenue"))
            .limit(top_n)
            .all()
        )

        top_categories = (
            db.query(
                Category.id,
                Category.name,
                func.coalesce(func.sum(SaleTransaction.total_price), 0.0).label("revenue"),
            )
            .join(MenuItem, MenuItem.category_id == Category.id)
            .join(SaleTransaction, SaleTransaction.item_id == MenuItem.id)
            .filter(SaleTransaction.sold_at >= cutoff)
            .group_by(Category.id, Category.name)
            .order_by(desc("revenue"))
            .limit(top_n)
            .all()
        )

        return {
            "daily": [
                {
                    "date": str(row.day),
                    "revenue": float(row.revenue),
                    "orders": int(row.orders),
                    "items": int(row.items),
                }
                for row in daily
            ],
            "top_items": [
                {
                    "item_id": row.id,
                    "name": row.name,
                    "revenue": float(row.revenue),
                    "qty": int(row.qty),
                }
                for row in top_items
            ],
            "top_categories": [
                {
                    "category_id": row.id,
                    "name": row.name,
                    "revenue": float(row.revenue),
                }
                for row in top_categories
            ],
        }
    except Exception as e:
        logger.exception("Error fetching reports")
        raise HTTPException(status_code=500, detail=f"Reports fetch failed: {e}")


@router.get("/reports/export")
def export_reports(
    kind: str = Query("daily", pattern=r"^(daily|top_items|top_categories)$"),
    days: int = Query(14, ge=7, le=90),
    top_n: int = Query(20, ge=3, le=50),
    db: Session = Depends(get_db),
):
    """
    CSV export for reports data.
    """
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        output = StringIO()
        writer = csv.writer(output)

        if kind == "daily":
            rows = (
                db.query(
                    func.date(SaleTransaction.sold_at).label("day"),
                    func.coalesce(func.sum(SaleTransaction.total_price), 0.0).label("revenue"),
                    func.coalesce(func.sum(SaleTransaction.quantity), 0).label("items"),
                    func.count(func.distinct(SaleTransaction.order_id)).label("orders"),
                )
                .filter(SaleTransaction.sold_at >= cutoff)
                .group_by(func.date(SaleTransaction.sold_at))
                .order_by(func.date(SaleTransaction.sold_at).asc())
                .all()
            )
            writer.writerow(["date", "revenue", "orders", "items"])
            for row in rows:
                writer.writerow([str(row.day), float(row.revenue), int(row.orders), int(row.items)])

        elif kind == "top_items":
            rows = (
                db.query(
                    MenuItem.id,
                    MenuItem.name,
                    func.coalesce(func.sum(SaleTransaction.total_price), 0.0).label("revenue"),
                    func.coalesce(func.sum(SaleTransaction.quantity), 0).label("qty"),
                )
                .join(SaleTransaction, SaleTransaction.item_id == MenuItem.id)
                .filter(SaleTransaction.sold_at >= cutoff)
                .group_by(MenuItem.id, MenuItem.name)
                .order_by(desc("revenue"))
                .limit(top_n)
                .all()
            )
            writer.writerow(["item_id", "name", "revenue", "qty"])
            for row in rows:
                writer.writerow([row.id, row.name, float(row.revenue), int(row.qty)])

        else:
            rows = (
                db.query(
                    Category.id,
                    Category.name,
                    func.coalesce(func.sum(SaleTransaction.total_price), 0.0).label("revenue"),
                )
                .join(MenuItem, MenuItem.category_id == Category.id)
                .join(SaleTransaction, SaleTransaction.item_id == MenuItem.id)
                .filter(SaleTransaction.sold_at >= cutoff)
                .group_by(Category.id, Category.name)
                .order_by(desc("revenue"))
                .limit(top_n)
                .all()
            )
            writer.writerow(["category_id", "name", "revenue"])
            for row in rows:
                writer.writerow([row.id, row.name, float(row.revenue)])

        filename = f"reports_{kind}_{days}d.csv"
        return Response(
            content=output.getvalue(),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )
    except Exception as e:
        logger.exception("Error exporting reports")
        raise HTTPException(status_code=500, detail=f"Reports export failed: {e}")


@router.get("/settings")
def get_settings():
    """
    Surface runtime settings for UI display.
    """
    try:
        import os
        from api.auth import AUTH_ENABLED
        from api.rate_limit import _VOICE_RPM, _REVENUE_RPM, _DEFAULT_RPM
        from database import DATABASE_URL

        return {
            "auth_enabled": AUTH_ENABLED,
            "rate_limits": {
                "voice_rpm": _VOICE_RPM,
                "revenue_rpm": _REVENUE_RPM,
                "default_rpm": _DEFAULT_RPM,
            },
            "cors_origins": os.getenv("CORS_ORIGINS", ""),
            "database": {
                "url": DATABASE_URL,
                "engine": "postgres" if DATABASE_URL and "postgres" in DATABASE_URL else "sqlite",
            },
        }
    except Exception as e:
        logger.exception("Error fetching settings")
        raise HTTPException(status_code=500, detail=f"Settings fetch failed: {e}")
