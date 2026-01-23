from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
import sqlite3
import json
import os
from datetime import datetime, timedelta
from collections import defaultdict

app = Flask(__name__)
CORS(app)

DB_PATH = os.environ.get("RIGS_DB_PATH", "db/inventory.db")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def safe_float(val, default=0.0):
    if val is None:
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default

def safe_int(val, default=0):
    if val is None:
        return default
    try:
        return int(val)
    except (ValueError, TypeError):
        return default

def safe_str(val, default=""):
    if val is None:
        return default
    return str(val)

def parse_items_json(items_str):
    if not items_str:
        return []
    try:
        parsed = json.loads(items_str)
        if isinstance(parsed, list):
            return parsed
        elif isinstance(parsed, dict):
            return [{"name": k, **v} if isinstance(v, dict) else {"name": k} for k, v in parsed.items()]
        return []
    except (json.JSONDecodeError, TypeError):
        return []

def parse_timestamp(ts):
    if not ts:
        return None
    if isinstance(ts, datetime):
        return ts
    formats = [
        "%Y-%m-%d %H:%M:%S.%f",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(str(ts), fmt)
        except ValueError:
            continue
    return None

def get_inventory_lookup():
    """Build lookup dict keyed by item_id, barcode, and lowercase name for cost backfill."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT item_id, barcode, name, category, price, cost, taxable, is_rolling_papers, papers_per_pack
        FROM items
    """)
    rows = cursor.fetchall()
    conn.close()
    
    lookup = {}
    for row in rows:
        entry = {
            "item_id": row["item_id"],
            "barcode": row["barcode"],
            "name": row["name"],
            "category": row["category"],
            "price": row["price"],
            "cost": row["cost"],
            "taxable": row["taxable"],
            "is_rolling_papers": row["is_rolling_papers"],
            "papers_per_pack": row["papers_per_pack"],
        }
        # Index by all three keys for flexible matching
        for key in (row["item_id"], row["barcode"], (row["name"] or "").lower()):
            if key:
                lookup[key] = entry
    return lookup

def backfill_item_cost(item, inventory_lookup, guess_keystone=False):
    """Enrich an order item with cost data from inventory if missing."""
    if item.get("unit_cost") is not None:
        return item  # Already has cost, no backfill needed
    
    # Try to find match in inventory
    inv = None
    for key in (item.get("item_id"), item.get("barcode"), (item.get("name") or "").lower()):
        if key and key in inventory_lookup:
            inv = inventory_lookup[key]
            break
    
    if inv:
        # Check if inventory has valid cost
        inv_cost = inv.get("cost")
        if inv_cost is not None and inv_cost != "":
            try:
                cost_val = float(inv_cost)
                # Backfill from inventory
                item = dict(item)
                item["unit_cost"] = cost_val
                item["unit_cost_source"] = "inventory"
                qty = safe_float(item.get("qty"), 0)
                item["line_cost"] = qty * item["unit_cost"]
                
                unit_price = safe_float(item.get("unit_price"), 0)
                if unit_price > 0:
                    item["margin"] = unit_price - item["unit_cost"]
                    item["margin_pct"] = (item["margin"] / unit_price) * 100
                return item
            except (ValueError, TypeError):
                pass
    
    # Keystone fallback: assume cost is 50% of price
    if guess_keystone:
        unit_price = safe_float(item.get("unit_price"), 0)
        if unit_price > 0:
            item = dict(item)
            item["unit_cost"] = unit_price * 0.5
            item["unit_cost_source"] = "keystone"
            qty = safe_float(item.get("qty"), 0)
            item["line_cost"] = qty * item["unit_cost"]
            item["margin"] = unit_price - item["unit_cost"]
            item["margin_pct"] = 50.0  # Always 50% by definition
            return item
    
    return item

@app.route("/")
def index():
    return send_from_directory(".", "analytics.html")

@app.route("/api/orders")
def get_orders():
    conn = get_db()
    cursor = conn.cursor()
    
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")
    keyword = request.args.get("keyword", "").strip().lower()
    category = request.args.get("category", "").strip()
    payment_method = request.args.get("payment_method", "").strip()
    min_total = request.args.get("min_total")
    max_total = request.args.get("max_total")
    min_qty = request.args.get("min_qty")
    max_qty = request.args.get("max_qty")
    
    query = """
        SELECT DISTINCT oh.order_id, oh.items, oh.total, oh.tax, oh.discount,
               oh.total_with_tax, oh.timestamp, oh.payment_method,
               oh.amount_tendered, oh.change_given
        FROM order_history oh
        LEFT JOIN order_items oi ON oh.order_id = oi.order_id
        WHERE 1=1
    """
    params = []
    
    if start_date:
        query += " AND oh.timestamp >= ?"
        params.append(start_date)
    if end_date:
        query += " AND oh.timestamp <= ?"
        params.append(end_date + " 23:59:59")
    if payment_method:
        query += " AND LOWER(oh.payment_method) = LOWER(?)"
        params.append(payment_method)
    if min_total:
        query += " AND oh.total_with_tax >= ?"
        params.append(float(min_total))
    if max_total:
        query += " AND oh.total_with_tax <= ?"
        params.append(float(max_total))
    if category:
        query += " AND LOWER(COALESCE(oi.product_category, oi.category)) = LOWER(?)"
        params.append(category)
    if keyword:
        query += " AND (LOWER(oi.name) LIKE ? OR LOWER(oh.items) LIKE ?)"
        params.extend([f"%{keyword}%", f"%{keyword}%"])
    
    query += " ORDER BY oh.timestamp DESC"
    
    cursor.execute(query, params)
    rows = cursor.fetchall()
    
    orders = []
    for row in rows:
        items = parse_items_json(row["items"])
        total_qty = sum(safe_float(i.get("quantity") or i.get("qty"), 0) for i in items)
        
        if min_qty and total_qty < float(min_qty):
            continue
        if max_qty and total_qty > float(max_qty):
            continue
        
        orders.append({
            "order_id": safe_str(row["order_id"]),
            "items": items,
            "items_count": len(items),
            "total_qty": total_qty,
            "total": safe_float(row["total"]),
            "tax": safe_float(row["tax"]),
            "discount": safe_float(row["discount"]),
            "total_with_tax": safe_float(row["total_with_tax"]),
            "timestamp": safe_str(row["timestamp"]),
            "payment_method": safe_str(row["payment_method"], "unknown"),
            "amount_tendered": safe_float(row["amount_tendered"]),
            "change_given": safe_float(row["change_given"]),
        })
    
    conn.close()
    return jsonify(orders)

@app.route("/api/order_items")
def get_order_items():
    conn = get_db()
    cursor = conn.cursor()
    
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")
    keyword = request.args.get("keyword", "").strip().lower()
    category = request.args.get("category", "").strip()
    min_price = request.args.get("min_price")
    max_price = request.args.get("max_price")
    min_cost = request.args.get("min_cost")
    max_cost = request.args.get("max_cost")
    guess_keystone = request.args.get("guess_keystone", "").lower() == "true"
    
    query = """
        SELECT oi.*, oh.payment_method
        FROM order_items oi
        LEFT JOIN order_history oh ON oi.order_id = oh.order_id
        WHERE 1=1
    """
    params = []
    
    if start_date:
        query += " AND oi.order_timestamp >= ?"
        params.append(start_date)
    if end_date:
        query += " AND oi.order_timestamp <= ?"
        params.append(end_date + " 23:59:59")
    if keyword:
        query += " AND LOWER(oi.name) LIKE ?"
        params.append(f"%{keyword}%")
    if category:
        query += " AND LOWER(oi.category) = LOWER(?)"
        params.append(category)
    if min_price:
        query += " AND oi.unit_price >= ?"
        params.append(float(min_price))
    if max_price:
        query += " AND oi.unit_price <= ?"
        params.append(float(max_price))
    
    query += " ORDER BY oi.order_timestamp DESC"
    
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    
    # Load inventory for cost backfill
    inventory_lookup = get_inventory_lookup()
    
    items = []
    for row in rows:
        unit_price = safe_float(row["unit_price"])
        unit_cost = safe_float(row["unit_cost"]) if row["unit_cost"] else None
        qty = safe_float(row["qty"])
        line_subtotal = safe_float(row["line_subtotal"], qty * unit_price)
        line_cost = safe_float(row["line_cost"]) if row["line_cost"] else (qty * unit_cost if unit_cost else None)
        margin = None
        margin_pct = None
        if unit_cost and unit_price:
            margin = unit_price - unit_cost
            margin_pct = (margin / unit_price * 100) if unit_price else 0
        
        item = {
            "id": safe_int(row["id"]),
            "order_id": safe_str(row["order_id"]),
            "item_id": safe_str(row["item_id"]),
            "barcode": safe_str(row["barcode"]),
            "name": safe_str(row["name"], "Unknown Item"),
            "category": safe_str(row["category"], "Uncategorized"),
            "product_category": safe_str(row["product_category"], row["category"]),
            "qty": qty,
            "unit_price": unit_price,
            "line_subtotal": line_subtotal,
            "unit_cost": unit_cost,
            "line_cost": line_cost,
            "margin": margin,
            "margin_pct": margin_pct,
            "taxable": bool(row["taxable"]) if row["taxable"] is not None else None,
            "is_rolling_papers": bool(row["is_rolling_papers"]) if row["is_rolling_papers"] is not None else None,
            "papers_per_pack": safe_int(row["papers_per_pack"]) if row["papers_per_pack"] else None,
            "order_timestamp": safe_str(row["order_timestamp"]),
            "payment_method": safe_str(row["payment_method"], "unknown"),
            "unit_cost_source": "order" if unit_cost else None,
        }
        
        # Backfill cost from inventory if missing
        item = backfill_item_cost(item, inventory_lookup, guess_keystone)
        
        # Apply cost filters after backfill
        if min_cost and (item.get("unit_cost") is None or item["unit_cost"] < float(min_cost)):
            continue
        if max_cost and (item.get("unit_cost") is None or item["unit_cost"] > float(max_cost)):
            continue
        
        items.append(item)
    
    return jsonify(items)

@app.route("/api/categories")
def get_categories():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT DISTINCT COALESCE(product_category, category) as category FROM order_items WHERE COALESCE(product_category, category) IS NOT NULL AND COALESCE(product_category, category) != '' ORDER BY category"
    )
    categories = [row["category"] for row in cursor.fetchall()]
    conn.close()
    return jsonify(categories)

@app.route("/api/payment_methods")
def get_payment_methods():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT payment_method FROM order_history WHERE payment_method IS NOT NULL AND payment_method != '' ORDER BY payment_method")
    methods = [row["payment_method"] for row in cursor.fetchall()]
    conn.close()
    return jsonify(methods)

@app.route("/api/stats/summary")
def get_summary_stats():
    conn = get_db()
    cursor = conn.cursor()
    
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")
    keyword = request.args.get("keyword", "").strip().lower()
    category = request.args.get("category", "").strip()
    payment_method = request.args.get("payment_method", "").strip()
    guess_keystone = request.args.get("guess_keystone", "").lower() == "true"
    exclude_empty_days = request.args.get("exclude_empty_days", "").lower() == "true"
    # Primary data source: order_items (joined with order_history for payment filter and tax/discount)
    item_query = """
        SELECT oi.*, oh.payment_method, oh.tax as order_tax, oh.discount as order_discount,
               oh.total_with_tax as order_total
        FROM order_items oi
        LEFT JOIN order_history oh ON oi.order_id = oh.order_id
        WHERE 1=1
    """
    params_item = []
    
    if start_date:
        item_query += " AND oi.order_timestamp >= ?"
        params_item.append(start_date)
    if end_date:
        item_query += " AND oi.order_timestamp <= ?"
        params_item.append(end_date + " 23:59:59")
    if payment_method:
        item_query += " AND LOWER(oh.payment_method) = LOWER(?)"
        params_item.append(payment_method)
    if keyword:
        item_query += " AND LOWER(oi.name) LIKE ?"
        params_item.append(f"%{keyword}%")
    if category:
        item_query += " AND LOWER(oi.category) = LOWER(?)"
        params_item.append(category)
    
    cursor.execute(item_query, params_item)
    item_rows = cursor.fetchall()
    conn.close()
    
    # Load inventory for cost backfill
    inventory_lookup = get_inventory_lookup()
    
    # Process items with cost backfill, track per-order data
    items = []
    orders_seen = {}  # order_id -> {tax, discount, total, payment_method, timestamp}
    
    for row in item_rows:
        item = {
            "order_id": row["order_id"],
            "item_id": row["item_id"],
            "barcode": row["barcode"],
            "name": row["name"],
            "category": row["category"],
            "qty": safe_float(row["qty"]),
            "unit_price": safe_float(row["unit_price"]),
            "line_subtotal": safe_float(row["line_subtotal"]),
            "unit_cost": safe_float(row["unit_cost"]) if row["unit_cost"] else None,
            "line_cost": safe_float(row["line_cost"]) if row["line_cost"] else None,
            "order_timestamp": row["order_timestamp"],
        }
        item = backfill_item_cost(item, inventory_lookup, guess_keystone)
        items.append(item)
        
        # Track order-level data 
        oid = row["order_id"]
        if oid and oid not in orders_seen:
            orders_seen[oid] = {
                "tax": safe_float(row["order_tax"]),
                "discount": safe_float(row["order_discount"]),
                "total_with_tax": safe_float(row["order_total"]),
                "payment_method": row["payment_method"],
                "timestamp": row["order_timestamp"],
            }
    
    # Calculate from order_items 
    total_orders = len(orders_seen)
    total_subtotal = sum(i["line_subtotal"] for i in items)  # Pre-tax revenue from items
    total_units = sum(i["qty"] for i in items)
    total_cost = sum(safe_float(i.get("line_cost")) for i in items if i.get("line_cost"))
    
    # Tax and discount come from order_history 
    total_tax = sum(o["tax"] for o in orders_seen.values())
    total_discount = sum(o["discount"] for o in orders_seen.values())
    total_revenue = sum(o["total_with_tax"] for o in orders_seen.values())
    
    # Track cost data completeness (after backfill)
    items_with_cost = [i for i in items if i.get("unit_cost") is not None]
    items_with_original_cost = [i for i in items if i.get("unit_cost_source") == "order"]
    items_backfilled = [i for i in items if i.get("unit_cost_source") == "inventory"]
    items_keystone = [i for i in items if i.get("unit_cost_source") == "keystone"]
    items_still_missing = len(items) - len(items_with_cost)
    
    gross_profit = total_subtotal - total_cost if total_cost else None
    gross_margin_pct = (gross_profit / total_subtotal * 100) if gross_profit and total_subtotal else None
    
    avg_order_value = total_revenue / total_orders if total_orders else 0
    avg_items_per_order = total_units / total_orders if total_orders else 0
    
    timestamps = [parse_timestamp(o["timestamp"]) for o in orders_seen.values()]
    timestamps = [t for t in timestamps if t]
    date_range = None
    if timestamps:
        min_date = min(timestamps)
        max_date = max(timestamps)
        date_range = {"start": min_date.isoformat(), "end": max_date.isoformat()}
        if exclude_empty_days:
            days = len({t.date() for t in timestamps})
        else:
            start_dt = parse_timestamp(start_date) if start_date else min_date
            end_dt = parse_timestamp(end_date) if end_date else max_date
            if start_dt and end_dt:
                days = (end_dt.date() - start_dt.date()).days + 1
            else:
                days = 0
        daily_avg_revenue = total_revenue / days if days else 0
        daily_avg_orders = total_orders / days if days else 0
    else:
        daily_avg_revenue = 0
        daily_avg_orders = 0
    
    payment_breakdown = defaultdict(lambda: {"count": 0, "total": 0})
    for oid, o in orders_seen.items():
        pm = safe_str(o["payment_method"], "unknown").lower()
        payment_breakdown[pm]["count"] += 1
        payment_breakdown[pm]["total"] += o["total_with_tax"]
    
    category_breakdown = defaultdict(lambda: {"units": 0, "revenue": 0, "cost": 0})
    for i in items:
        cat = safe_str(i.get("category"), "uncategorized").lower()
        category_breakdown[cat]["units"] += i["qty"]
        category_breakdown[cat]["revenue"] += safe_float(i.get("line_subtotal"))
        category_breakdown[cat]["cost"] += safe_float(i.get("line_cost")) if i.get("line_cost") else 0
    
    return jsonify({
        "total_orders": total_orders,
        "total_revenue": round(total_revenue, 2),
        "total_subtotal": round(total_subtotal, 2),
        "total_tax": round(total_tax, 2),
        "total_discount": round(total_discount, 2),
        "total_units": round(total_units, 2),
        "total_cost": round(total_cost, 2) if total_cost else None,
        "gross_profit": round(gross_profit, 2) if gross_profit else None,
        "gross_margin_pct": round(gross_margin_pct, 2) if gross_margin_pct else None,
        "avg_order_value": round(avg_order_value, 2),
        "avg_items_per_order": round(avg_items_per_order, 2),
        "daily_avg_revenue": round(daily_avg_revenue, 2),
        "daily_avg_orders": round(daily_avg_orders, 2),
        "date_range": date_range,
        "payment_breakdown": dict(payment_breakdown),
        "category_breakdown": dict(category_breakdown),
        "cost_data_available": len(items_with_cost),
        "cost_data_from_orders": len(items_with_original_cost),
        "cost_data_backfilled": len(items_backfilled),
        "cost_data_keystone": len(items_keystone),
        "cost_data_missing": items_still_missing,
    })

@app.route("/api/stats/timeseries")
def get_timeseries():
    conn = get_db()
    cursor = conn.cursor()
    
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")
    granularity = request.args.get("granularity", "day")
    keyword = request.args.get("keyword", "").strip().lower()
    category = request.args.get("category", "").strip()
    payment_method = request.args.get("payment_method", "").strip()
    
    query = "SELECT * FROM order_history WHERE 1=1"
    params = []
    
    if start_date:
        query += " AND timestamp >= ?"
        params.append(start_date)
    if end_date:
        query += " AND timestamp <= ?"
        params.append(end_date + " 23:59:59")
    if payment_method:
        query += " AND LOWER(payment_method) = LOWER(?)"
        params.append(payment_method)
    if keyword:
        query += " AND LOWER(items) LIKE ?"
        params.append(f"%{keyword}%")
    
    query += " ORDER BY timestamp"
    cursor.execute(query, params)
    orders = cursor.fetchall()
    
    if category:
        item_query = """
            SELECT order_id FROM order_items 
            WHERE LOWER(category) = LOWER(?)
        """
        cursor.execute(item_query, [category])
        valid_order_ids = set(row["order_id"] for row in cursor.fetchall())
        orders = [o for o in orders if o["order_id"] in valid_order_ids]
    
    conn.close()
    
    buckets = defaultdict(lambda: {"revenue": 0, "orders": 0, "tax": 0, "discount": 0})
    
    for o in orders:
        ts = parse_timestamp(o["timestamp"])
        if not ts:
            continue
        
        if granularity == "hour":
            key = ts.strftime("%Y-%m-%d %H:00")
        elif granularity == "day":
            key = ts.strftime("%Y-%m-%d")
        elif granularity == "week":
            week_start = ts - timedelta(days=ts.weekday())
            key = week_start.strftime("%Y-%m-%d")
        elif granularity == "month":
            key = ts.strftime("%Y-%m")
        else:
            key = ts.strftime("%Y-%m-%d")
        
        buckets[key]["revenue"] += safe_float(o["total_with_tax"])
        buckets[key]["orders"] += 1
        buckets[key]["tax"] += safe_float(o["tax"])
        buckets[key]["discount"] += safe_float(o["discount"])
    
    sorted_keys = sorted(buckets.keys())
    result = []
    for k in sorted_keys:
        result.append({
            "period": k,
            "revenue": round(buckets[k]["revenue"], 2),
            "orders": buckets[k]["orders"],
            "tax": round(buckets[k]["tax"], 2),
            "discount": round(buckets[k]["discount"], 2),
            "avg_order": round(buckets[k]["revenue"] / buckets[k]["orders"], 2) if buckets[k]["orders"] else 0,
        })
    
    return jsonify(result)

@app.route("/api/stats/top_items")
def get_top_items():
    conn = get_db()
    cursor = conn.cursor()
    
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")
    limit = safe_int(request.args.get("limit"), 20)
    sort_by = request.args.get("sort_by", "revenue")
    category = request.args.get("category", "").strip()
    guess_keystone = request.args.get("guess_keystone", "").lower() == "true"
    
    # Get all matching items
    query = """
        SELECT item_id, barcode, name, category, qty, unit_price, line_subtotal, unit_cost, line_cost, order_id
        FROM order_items
        WHERE name IS NOT NULL AND name != ''
    """
    params = []
    
    if start_date:
        query += " AND order_timestamp >= ?"
        params.append(start_date)
    if end_date:
        query += " AND order_timestamp <= ?"
        params.append(end_date + " 23:59:59")
    if category:
        query += " AND LOWER(category) = LOWER(?)"
        params.append(category)
    
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    
    # Load inventory for cost backfill
    inventory_lookup = get_inventory_lookup()
    
    # Aggregate by item name with cost backfill
    aggregated = defaultdict(lambda: {
        "name": None,
        "category": None,
        "total_qty": 0,
        "total_revenue": 0,
        "total_cost": 0,
        "prices": [],
        "costs": [],
        "order_ids": set(),
        "has_cost": False,
    })
    
    for row in rows:
        item = {
            "item_id": row["item_id"],
            "barcode": row["barcode"],
            "name": row["name"],
            "category": row["category"],
            "qty": safe_float(row["qty"]),
            "unit_price": safe_float(row["unit_price"]),
            "line_subtotal": safe_float(row["line_subtotal"]),
            "unit_cost": safe_float(row["unit_cost"]) if row["unit_cost"] else None,
            "line_cost": safe_float(row["line_cost"]) if row["line_cost"] else None,
        }
        # Backfill cost from inventory
        item = backfill_item_cost(item, inventory_lookup, guess_keystone)
        
        key = (row["name"] or "").lower()
        agg = aggregated[key]
        agg["name"] = agg["name"] or row["name"]
        agg["category"] = agg["category"] or row["category"]
        agg["total_qty"] += item["qty"]
        agg["total_revenue"] += item.get("line_subtotal") or 0
        if item.get("line_cost"):
            agg["total_cost"] += item["line_cost"]
            agg["has_cost"] = True
        agg["prices"].append(item["unit_price"])
        if item.get("unit_cost"):
            agg["costs"].append(item["unit_cost"])
        agg["order_ids"].add(row["order_id"])
    
    # Build final list
    items = []
    for key, agg in aggregated.items():
        total_revenue = agg["total_revenue"]
        total_cost = agg["total_cost"] if agg["has_cost"] else None
        profit = total_revenue - total_cost if total_cost else None
        margin_pct = (profit / total_revenue * 100) if profit and total_revenue else None
        avg_price = sum(agg["prices"]) / len(agg["prices"]) if agg["prices"] else 0
        avg_cost = sum(agg["costs"]) / len(agg["costs"]) if agg["costs"] else None
        
        items.append({
            "name": agg["name"] or "Unknown",
            "category": agg["category"] or "Uncategorized",
            "total_qty": round(agg["total_qty"], 2),
            "total_revenue": round(total_revenue, 2),
            "total_cost": round(total_cost, 2) if total_cost else None,
            "profit": round(profit, 2) if profit else None,
            "margin_pct": round(margin_pct, 2) if margin_pct else None,
            "avg_price": round(avg_price, 2),
            "avg_cost": round(avg_cost, 2) if avg_cost else None,
            "order_count": len(agg["order_ids"]),
        })
    
    # Sort
    if sort_by == "qty":
        items.sort(key=lambda x: x["total_qty"], reverse=True)
    elif sort_by == "orders":
        items.sort(key=lambda x: x["order_count"], reverse=True)
    elif sort_by == "profit":
        items.sort(key=lambda x: x["profit"] or 0, reverse=True)
    else:
        items.sort(key=lambda x: x["total_revenue"], reverse=True)
    
    return jsonify(items[:limit])

@app.route("/api/stats/hourly")
def get_hourly_breakdown():
    conn = get_db()
    cursor = conn.cursor()
    
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")
    
    query = "SELECT timestamp, total_with_tax FROM order_history WHERE 1=1"
    params = []
    
    if start_date:
        query += " AND timestamp >= ?"
        params.append(start_date)
    if end_date:
        query += " AND timestamp <= ?"
        params.append(end_date + " 23:59:59")
    
    cursor.execute(query, params)
    orders = cursor.fetchall()
    conn.close()
    
    hourly = defaultdict(lambda: {"revenue": 0, "orders": 0})
    daily = defaultdict(lambda: {"revenue": 0, "orders": 0})
    
    for o in orders:
        ts = parse_timestamp(o["timestamp"])
        if not ts:
            continue
        
        hour = ts.hour
        day = ts.strftime("%A")
        
        hourly[hour]["revenue"] += safe_float(o["total_with_tax"])
        hourly[hour]["orders"] += 1
        daily[day]["revenue"] += safe_float(o["total_with_tax"])
        daily[day]["orders"] += 1
    
    hourly_result = []
    for h in range(24):
        hourly_result.append({
            "hour": h,
            "label": f"{h:02d}:00",
            "revenue": round(hourly[h]["revenue"], 2),
            "orders": hourly[h]["orders"],
        })
    
    day_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    daily_result = []
    for d in day_order:
        daily_result.append({
            "day": d,
            "revenue": round(daily[d]["revenue"], 2),
            "orders": daily[d]["orders"],
        })
    
    return jsonify({"hourly": hourly_result, "daily": daily_result})

@app.route("/api/export/csv")
def export_csv():
    import csv
    from io import StringIO
    from flask import Response
    
    data_type = request.args.get("type", "orders")
    
    conn = get_db()
    cursor = conn.cursor()
    
    if data_type == "items":
        cursor.execute("""
            SELECT oi.*, oh.payment_method
            FROM order_items oi
            LEFT JOIN order_history oh ON oi.order_id = oh.order_id
            ORDER BY oi.order_timestamp DESC
        """)
        rows = cursor.fetchall()
        headers = ["id", "order_id", "item_id", "barcode", "name", "category", 
                   "qty", "unit_price", "line_subtotal", "unit_cost", "line_cost",
                   "taxable", "is_rolling_papers", "papers_per_pack", "order_timestamp", "payment_method"]
    else:
        cursor.execute("SELECT * FROM order_history ORDER BY timestamp DESC")
        rows = cursor.fetchall()
        headers = ["order_id", "items", "total", "tax", "discount", "total_with_tax",
                   "timestamp", "payment_method", "amount_tendered", "change_given"]
    
    conn.close()
    
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(headers)
    for row in rows:
        writer.writerow([row[h] if h in row.keys() else "" for h in headers])
    
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={data_type}_export.csv"}
    )

@app.route("/shutdown", methods=["POST"])
def shutdown():
    os._exit(0)

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
