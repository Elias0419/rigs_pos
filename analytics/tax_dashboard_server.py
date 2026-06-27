import json
import os
import sqlite3
from datetime import date, datetime
from uuid import uuid4

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from server_utils import run_dashboard_app

app = Flask(__name__)
CORS(app)

ANALYTICS_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.abspath(
    os.environ.get("RIGS_DB_PATH", os.path.join(ANALYTICS_DIR, "..", "db", "inventory.db"))
)
EXPENSES_PATH = os.environ.get(
    "RIGS_TAX_EXPENSES_PATH", os.path.join(ANALYTICS_DIR, "data", "tax_expenses.json")
)
VALID_PERIODS = {"month", "quarter", "year"}


def ensure_expenses_file():
    os.makedirs(os.path.dirname(EXPENSES_PATH), exist_ok=True)
    if not os.path.exists(EXPENSES_PATH):
        with open(EXPENSES_PATH, "w", encoding="utf-8") as handle:
            json.dump({"cash_out": []}, handle, indent=2)


def normalize_expenses_payload(payload):
    """Support the old quarter-deduction JSON shape while moving to cash-out lines."""
    if not isinstance(payload, dict):
        return {"cash_out": []}
    if isinstance(payload.get("cash_out"), list):
        payload["cash_out"] = [item for item in payload["cash_out"] if isinstance(item, dict)]
        return payload

    cash_out = []
    for quarter_key, items in payload.get("quarters", {}).items():
        if not isinstance(items, list):
            continue
        year = str(quarter_key).split("-Q", 1)[0]
        quarter = str(quarter_key).split("-Q", 1)[1] if "-Q" in str(quarter_key) else "1"
        try:
            fallback_date = quarter_start_end(int(year), int(quarter))[0].isoformat()
        except (TypeError, ValueError):
            fallback_date = date.today().isoformat()
        for item in items:
            if not isinstance(item, dict):
                continue
            cash_out.append(
                {
                    "id": item.get("id") or uuid4().hex,
                    "transaction_date": item.get("transaction_date") or fallback_date,
                    "payee": item.get("payee") or item.get("category") or "Cash Out",
                    "category": item.get("category") or "Other Expense",
                    "description": item.get("description") or "",
                    "amount": round(float(item.get("amount", 0) or 0), 2),
                    "created_at": item.get("created_at") or datetime.now().isoformat(timespec="seconds"),
                }
            )
    return {"cash_out": cash_out}


def load_expenses():
    ensure_expenses_file()
    with open(EXPENSES_PATH, "r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return normalize_expenses_payload(payload)


def save_expenses(payload):
    with open(EXPENSES_PATH, "w", encoding="utf-8") as handle:
        json.dump(normalize_expenses_payload(payload), handle, indent=2)


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
    start = date(int(year), start_month, 1)
    end = month_start_for_offset(start, 3).fromordinal(month_start_for_offset(start, 3).toordinal() - 1)
    return start, end


def period_start_end(period_type, period_value):
    today = date.today()
    if period_type == "year":
        year = int(period_value or today.year)
        return date(year, 1, 1), date(year, 12, 31)
    if period_type == "quarter":
        value = period_value or f"{today.year}-Q{((today.month - 1) // 3) + 1}"
        year_part, quarter_part = str(value).split("-Q", 1)
        return quarter_start_end(int(year_part), int(quarter_part))

    value = period_value or date(today.year, today.month, 1).strftime("%Y-%m")
    start = parse_month(value)
    if not start:
        raise ValueError("Month must use YYYY-MM format")
    end = month_start_for_offset(start, 1).fromordinal(month_start_for_offset(start, 1).toordinal() - 1)
    return start, end


def get_period_key(period_type, period_value):
    start, _ = period_start_end(period_type, period_value)
    if period_type == "year":
        return str(start.year)
    if period_type == "quarter":
        return f"{start.year}-Q{((start.month - 1) // 3) + 1}"
    return start.strftime("%Y-%m")


def list_periods_with_data(conn):
    cursor = conn.cursor()
    first_date = last_date = None
    try:
        cursor.execute("SELECT MIN(timestamp) AS first_ts, MAX(timestamp) AS last_ts FROM order_history")
        row = cursor.fetchone()
        first_date = parse_date(row["first_ts"])
        last_date = parse_date(row["last_ts"])
    except sqlite3.OperationalError:
        pass

    for item in load_expenses().get("cash_out", []):
        tx_date = parse_date(item.get("transaction_date"))
        if not tx_date:
            continue
        first_date = tx_date if first_date is None or tx_date < first_date else first_date
        last_date = tx_date if last_date is None or tx_date > last_date else last_date

    today = date.today()
    first_month = date((first_date or today).year, (first_date or today).month, 1)
    last_month = date((last_date or today).year, (last_date or today).month, 1)
    current_month = date(today.year, today.month, 1)
    if current_month > last_month:
        last_month = current_month

    months = month_range(first_month, last_month)
    years = sorted({month.year for month in months}, reverse=True)
    quarters = sorted({f"{month.year}-Q{((month.month - 1) // 3) + 1}" for month in months}, reverse=True)
    return {
        "default_period": current_month.strftime("%Y-%m"),
        "months": [month.strftime("%Y-%m") for month in reversed(months)],
        "quarters": quarters,
        "years": [str(year) for year in years],
    }


def compute_cash_in_totals(conn, start, end):
    next_start = end.fromordinal(end.toordinal() + 1)
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            SELECT
                COALESCE(SUM(total), 0) AS taxable_cash_in,
                COALESCE(SUM(tax), 0) AS sales_tax_collected,
                COALESCE(SUM(total_with_tax), 0) AS gross_customer_receipts,
                COUNT(*) AS order_count
            FROM order_history
            WHERE timestamp >= ?
              AND timestamp < ?
            """,
            (f"{start.isoformat()} 00:00:00", f"{next_start.isoformat()} 00:00:00"),
        )
        row = cursor.fetchone()
    except sqlite3.OperationalError:
        row = {"taxable_cash_in": 0, "sales_tax_collected": 0, "gross_customer_receipts": 0, "order_count": 0}
    taxable_cash_in = round(float(row["taxable_cash_in"] or 0), 2)
    sales_tax = round(float(row["sales_tax_collected"] or 0), 2)
    gross = round(float(row["gross_customer_receipts"] or 0), 2)
    return {
        "taxable_cash_in": taxable_cash_in,
        "sales_tax_collected": sales_tax,
        "gross_customer_receipts": gross,
        "order_count": int(row["order_count"] or 0),
    }


def cash_out_for_period(start, end):
    rows = []
    for item in load_expenses().get("cash_out", []):
        tx_date = parse_date(item.get("transaction_date"))
        if tx_date and start <= tx_date <= end:
            rows.append(item)
    return sorted(rows, key=lambda item: (item.get("transaction_date", ""), item.get("created_at", "")), reverse=True)


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


@app.route("/api/tax/periods")
def get_periods():
    conn = get_db_connection()
    try:
        return jsonify(list_periods_with_data(conn))
    finally:
        conn.close()


@app.route("/api/tax/cash_basis_summary")
def get_cash_basis_summary():
    period_type = request.args.get("period_type", "month")
    period_value = request.args.get("period_value")
    if period_type not in VALID_PERIODS:
        return jsonify({"error": "period_type must be month, quarter, or year."}), 400
    try:
        start, end = period_start_end(period_type, period_value)
        period_key = get_period_key(period_type, period_value)
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid period value."}), 400

    conn = get_db_connection()
    try:
        cash_in = compute_cash_in_totals(conn, start, end)
    finally:
        conn.close()

    cash_out = cash_out_for_period(start, end)
    total_cash_out = round(sum(float(item.get("amount", 0) or 0) for item in cash_out), 2)
    taxable_cash_income = round(cash_in["taxable_cash_in"] - total_cash_out, 2)

    return jsonify(
        {
            "period_type": period_type,
            "period_value": period_key,
            "totals": {
                "start_date": start.isoformat(),
                "end_date": end.isoformat(),
                **cash_in,
                "cash_out": total_cash_out,
                "taxable_cash_income": taxable_cash_income,
            },
            "cash_out_lines": cash_out,
        }
    )


@app.route("/api/tax/cash_out", methods=["POST"])
def add_cash_out():
    payload = request.get_json(silent=True) or {}
    tx_date = parse_date(payload.get("transaction_date"))
    payee = (payload.get("payee") or "").strip()
    category = (payload.get("category") or "Other Cash Out").strip()
    description = (payload.get("description") or "").strip()

    try:
        amount = float(payload.get("amount", 0) or 0)
    except (TypeError, ValueError):
        amount = 0

    if not tx_date:
        return jsonify({"error": "A valid transaction date is required."}), 400
    if amount <= 0:
        return jsonify({"error": "Amount must be greater than zero."}), 400

    line = {
        "id": uuid4().hex,
        "transaction_date": tx_date.isoformat(),
        "payee": payee,
        "category": category,
        "description": description,
        "amount": round(amount, 2),
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }

    expenses_payload = load_expenses()
    expenses_payload.setdefault("cash_out", []).append(line)
    save_expenses(expenses_payload)
    return jsonify({"ok": True, "cash_out_line": line}), 201


@app.route("/api/tax/cash_out/<line_id>", methods=["DELETE"])
def delete_cash_out(line_id):
    expenses_payload = load_expenses()
    existing = expenses_payload.get("cash_out", [])
    remaining = [item for item in existing if item.get("id") != line_id]
    if len(remaining) == len(existing):
        return jsonify({"error": "Cash out line not found."}), 404
    expenses_payload["cash_out"] = remaining
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


# Backwards-compatible aliases for older bookmarks/scripts.
@app.route("/api/tax/quarters")
def get_quarters():
    return jsonify([])


if __name__ == "__main__":
    ensure_expenses_file()
    run_dashboard_app(app, default_port=5055, host="0.0.0.0", debug=True)
