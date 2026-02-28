import json
import os
import sqlite3
from datetime import date, datetime
from uuid import uuid4

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

ANALYTICS_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.abspath(
    os.environ.get("RIGS_DB_PATH", os.path.join(ANALYTICS_DIR, "..", "db", "inventory.db"))
)
EXPENSES_PATH = os.environ.get(
    "RIGS_TAX_EXPENSES_PATH", os.path.join(ANALYTICS_DIR, "data", "tax_expenses.json")
)


def ensure_expenses_file():
    os.makedirs(os.path.dirname(EXPENSES_PATH), exist_ok=True)
    if not os.path.exists(EXPENSES_PATH):
        with open(EXPENSES_PATH, "w", encoding="utf-8") as handle:
            json.dump({"quarters": {}}, handle, indent=2)


def load_expenses():
    ensure_expenses_file()
    with open(EXPENSES_PATH, "r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if "quarters" not in payload or not isinstance(payload["quarters"], dict):
        payload = {"quarters": {}}
    return payload


def save_expenses(payload):
    with open(EXPENSES_PATH, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)


def get_db_connection():
    os.makedirs(os.path.dirname(os.path.abspath(DB_PATH)), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def parse_date(value):
    if not value:
        return None
    for fmt in (
        "%Y-%m-%d %H:%M:%S.%f",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d",
    ):
        try:
            return datetime.strptime(str(value), fmt).date()
        except ValueError:
            continue
    return None


def parse_month(value):
    if not value:
        return None
    try:
        parsed = datetime.strptime(str(value), "%Y-%m").date()
        return date(parsed.year, parsed.month, 1)
    except ValueError:
        return None


def month_start_for_offset(start_month, offset):
    month_idx = (start_month.month - 1) + offset
    year = start_month.year + (month_idx // 12)
    month = (month_idx % 12) + 1
    return date(year, month, 1)


def month_range(start_month, end_month):
    if start_month > end_month:
        start_month, end_month = end_month, start_month

    months = []
    cursor = start_month
    while cursor <= end_month:
        months.append(cursor)
        cursor = month_start_for_offset(cursor, 1)
    return months


def quarter_start_end(year, quarter):
    quarter = int(quarter)
    if quarter < 1 or quarter > 4:
        raise ValueError("Quarter must be 1-4")

    start_month = ((quarter - 1) * 3) + 1
    end_month = start_month + 2
    start = date(int(year), start_month, 1)

    if end_month == 12:
        end = date(int(year), 12, 31)
    else:
        next_month = date(int(year), end_month + 1, 1)
        end = next_month.fromordinal(next_month.toordinal() - 1)
    return start, end


def get_quarter_key(year, quarter):
    return f"{int(year)}-Q{int(quarter)}"


def list_quarters_with_data(conn):
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT MIN(order_timestamp) AS first_ts, MAX(order_timestamp) AS last_ts FROM order_items")
        row = cursor.fetchone()
    except sqlite3.OperationalError:
        row = None

    now = date.today()
    if not row or (row["first_ts"] is None and row["last_ts"] is None):
        return [{"year": now.year, "quarter": ((now.month - 1) // 3) + 1}]

    first_date = parse_date(row["first_ts"]) or now
    last_date = parse_date(row["last_ts"]) or now

    first_quarter = ((first_date.month - 1) // 3) + 1
    last_quarter = ((last_date.month - 1) // 3) + 1

    quarters = []
    y, q = first_date.year, first_quarter
    while (y < last_date.year) or (y == last_date.year and q <= last_quarter):
        quarters.append({"year": y, "quarter": q})
        q += 1
        if q == 5:
            q = 1
            y += 1

    current_quarter = ((now.month - 1) // 3) + 1
    if not any(item["year"] == now.year and item["quarter"] == current_quarter for item in quarters):
        quarters.append({"year": now.year, "quarter": current_quarter})

    quarters.sort(key=lambda item: (item["year"], item["quarter"]), reverse=True)
    return quarters


def compute_quarter_totals(conn, year, quarter):
    start, end = quarter_start_end(year, quarter)
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            SELECT
                COALESCE(SUM(line_subtotal), 0) AS revenue,
                COALESCE(SUM(line_cost), 0) AS cogs,
                SUM(CASE WHEN line_cost IS NULL THEN 1 ELSE 0 END) AS missing_cost_lines
            FROM order_items
            WHERE order_timestamp >= ? AND order_timestamp <= ?
            """,
            (f"{start.isoformat()} 00:00:00", f"{end.isoformat()} 23:59:59"),
        )
        row = cursor.fetchone()
    except sqlite3.OperationalError:
        row = {"revenue": 0, "cogs": 0, "missing_cost_lines": 0}

    revenue = float(row["revenue"] or 0.0)
    cogs = float(row["cogs"] or 0.0)
    gross_profit = revenue - cogs

    return {
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "revenue": round(revenue, 2),
        "cogs": round(cogs, 2),
        "gross_profit": round(gross_profit, 2),
        "missing_cost_lines": int(row["missing_cost_lines"] or 0),
    }


def compute_sales_tax_monthly(conn, start_month=None, end_month=None, trailing_months=12):
    today = date.today()
    current_month = date(today.year, today.month, 1)

    try:
        trailing_months = int(trailing_months)
    except (TypeError, ValueError):
        trailing_months = 12
    trailing_months = min(max(trailing_months, 1), 60)

    if start_month and end_month:
        months = month_range(start_month, end_month)
    elif start_month:
        months = month_range(start_month, month_start_for_offset(start_month, trailing_months - 1))
    elif end_month:
        months = month_range(month_start_for_offset(end_month, -(trailing_months - 1)), end_month)
    else:
        months = month_range(month_start_for_offset(current_month, -(trailing_months - 1)), current_month)

    start_date = months[0].isoformat()
    next_after_end = month_start_for_offset(months[-1], 1).isoformat()

    cursor = conn.cursor()
    totals_by_month = {}
    try:
        cursor.execute(
            """
            SELECT
                strftime('%Y-%m', timestamp) AS year_month,
                COALESCE(SUM(COALESCE(tax, 0)), 0) AS sales_tax_total,
                COUNT(*) AS order_count
            FROM order_history
            WHERE timestamp >= ?
              AND timestamp < ?
            GROUP BY year_month
            ORDER BY year_month ASC
            """,
            (f"{start_date} 00:00:00", f"{next_after_end} 00:00:00"),
        )
        for row in cursor.fetchall():
            totals_by_month[row["year_month"]] = {
                "sales_tax_total": round(float(row["sales_tax_total"] or 0), 2),
                "order_count": int(row["order_count"] or 0),
            }
    except sqlite3.OperationalError:
        totals_by_month = {}

    rows = []
    current_month_key = current_month.strftime("%Y-%m")
    for month in months:
        month_key = month.strftime("%Y-%m")
        month_totals = totals_by_month.get(month_key, {"sales_tax_total": 0.0, "order_count": 0})
        rows.append(
            {
                "month": month_key,
                "sales_tax_total": month_totals["sales_tax_total"],
                "order_count": month_totals["order_count"],
                "is_current_month": month_key == current_month_key,
                "is_incomplete": month_key == current_month_key,
            }
        )

    return {
        "range_start": months[0].strftime("%Y-%m"),
        "range_end": months[-1].strftime("%Y-%m"),
        "trailing_months": trailing_months,
        "rows": rows,
    }


@app.route("/")
def index():
    return send_from_directory(ANALYTICS_DIR, "tax_dashboard.html")


@app.route("/api/tax/quarters")
def get_quarters():
    conn = get_db_connection()
    try:
        return jsonify(list_quarters_with_data(conn))
    finally:
        conn.close()


@app.route("/api/tax/quarter_summary")
def get_quarter_summary():
    year = int(request.args.get("year", date.today().year))
    quarter = int(request.args.get("quarter", ((date.today().month - 1) // 3) + 1))

    conn = get_db_connection()
    try:
        totals = compute_quarter_totals(conn, year, quarter)
    finally:
        conn.close()

    expenses_payload = load_expenses()
    quarter_key = get_quarter_key(year, quarter)
    itemized = expenses_payload["quarters"].get(quarter_key, [])
    total_other_expenses = round(sum(float(item.get("amount", 0) or 0) for item in itemized), 2)

    taxable_income = round(totals["gross_profit"] - total_other_expenses, 2)

    return jsonify(
        {
            "year": year,
            "quarter": quarter,
            "quarter_key": quarter_key,
            "totals": {
                **totals,
                "other_expenses": total_other_expenses,
                "taxable_income": taxable_income,
            },
            "itemized_deductions": itemized,
        }
    )


@app.route("/api/tax/expenses", methods=["POST"])
def add_expense():
    payload = request.get_json(silent=True) or {}

    year = int(payload.get("year", 0))
    quarter = int(payload.get("quarter", 0))
    category = (payload.get("category") or "Other Expense").strip()
    description = (payload.get("description") or "").strip()
    amount = float(payload.get("amount", 0) or 0)

    if not year or quarter not in (1, 2, 3, 4):
        return jsonify({"error": "Valid year and quarter are required."}), 400
    if amount <= 0:
        return jsonify({"error": "Amount must be greater than zero."}), 400

    expense = {
        "id": uuid4().hex,
        "category": category,
        "description": description,
        "amount": round(amount, 2),
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }

    expenses_payload = load_expenses()
    quarter_key = get_quarter_key(year, quarter)
    expenses_payload["quarters"].setdefault(quarter_key, []).append(expense)
    save_expenses(expenses_payload)

    return jsonify({"ok": True, "expense": expense}), 201


@app.route("/api/tax/expenses/<expense_id>", methods=["DELETE"])
def delete_expense(expense_id):
    year = int(request.args.get("year", 0))
    quarter = int(request.args.get("quarter", 0))

    if not year or quarter not in (1, 2, 3, 4):
        return jsonify({"error": "Valid year and quarter are required."}), 400

    quarter_key = get_quarter_key(year, quarter)
    expenses_payload = load_expenses()
    existing = expenses_payload["quarters"].get(quarter_key, [])
    remaining = [item for item in existing if item.get("id") != expense_id]

    if len(remaining) == len(existing):
        return jsonify({"error": "Expense not found."}), 404

    expenses_payload["quarters"][quarter_key] = remaining
    save_expenses(expenses_payload)
    return jsonify({"ok": True})


@app.route("/api/tax/sales_tax_monthly")
def get_sales_tax_monthly():
    start_month = parse_month(request.args.get("start_month"))
    end_month = parse_month(request.args.get("end_month"))
    trailing_months = request.args.get("trailing_months", 12)

    conn = get_db_connection()
    try:
        payload = compute_sales_tax_monthly(
            conn,
            start_month=start_month,
            end_month=end_month,
            trailing_months=trailing_months,
        )
    finally:
        conn.close()

    return jsonify(payload)


if __name__ == "__main__":
    ensure_expenses_file()
    app.run(host="0.0.0.0", port=5055, debug=True)
