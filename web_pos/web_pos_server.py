"""Browser-based POS prototype for the core register loop.

This intentionally lives beside the Kivy application instead of replacing it. It
reuses the existing SQLite and order/domain classes, but keeps an in-memory
prototype cart for browser experiments.
"""

from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path
from typing import Any

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from database_manager import DatabaseManager  # noqa: E402
from order_manager import LineItem, Order  # noqa: E402

STATIC_DIR = Path(__file__).resolve().parent / "static"
DEFAULT_TAX_RATE = float(os.environ.get("RIGS_WEB_POS_TAX_RATE", "0.07"))


def _default_db_path() -> str:
    explicit_db = os.environ.get("RIGS_POS_DB")
    if explicit_db:
        return explicit_db

    candidates = [
        "/home/rigs/rigs_pos/db/inventory.db",
        "/home/x/work/rigs/rigs_pos/db/inventory.db",
        str(REPO_ROOT / "db" / "inventory.db"),
    ]
    for candidate in candidates:
        if Path(candidate).exists():
            return candidate
    return candidates[-1]


class _NullPopupManager:
    def __getattr__(self, _name: str):
        def noop(*_args, **_kwargs):
            return None

        return noop


class _PrototypeAppRef:
    """Small app-like object for existing helpers that expect app.db_manager."""

    def __init__(self, db_path: str):
        self.popup_manager = _NullPopupManager()
        self.db_manager = DatabaseManager(db_path, self)
        self.receipt_printer = None


def create_app() -> Flask:
    app = Flask(__name__, static_folder=str(STATIC_DIR), static_url_path="/static")
    CORS(app)

    app_ref = _PrototypeAppRef(_default_db_path())
    current_order = Order(tax_rate=DEFAULT_TAX_RATE)

    def order_payload() -> dict[str, Any]:
        current_order.recalculate_totals()
        return current_order.to_dict()

    def item_payload(row: dict[str, Any]) -> dict[str, Any]:
        return {
            "item_id": row.get("item_id"),
            "barcode": row.get("barcode"),
            "ean_barcode": row.get("ean_barcode"),
            "name": row.get("name"),
            "price": float(row.get("price") or 0),
            "cost": row.get("cost"),
            "product_category": row.get("product_category"),
            "is_cigarette": row.get("is_cigarette"),
        }

    def find_item_by_any_barcode(barcode: str) -> dict[str, Any] | None:
        barcode = str(barcode or "").strip()
        if not barcode:
            return None
        item = app_ref.db_manager.get_item_details(barcode=barcode)
        if item:
            return item
        variants = []
        if len(barcode) > 1:
            variants.append(barcode[1:])
        if len(barcode) > 4:
            variants.extend([barcode[:-4], barcode[1:-4]])
        for variant in variants:
            item = app_ref.db_manager.get_item_details(barcode=variant)
            if item:
                return item
        return None

    def add_item_to_order(item: dict[str, Any]) -> None:
        item_id = str(item.get("item_id") or uuid.uuid4())
        if item_id in current_order.items:
            line_item = current_order.items[item_id]
            line_item.quantity = int(line_item.quantity) + 1
            line_item.recompute()
        else:
            line_item = LineItem(
                item_id=item_id,
                barcode=str(item.get("barcode")) if item.get("barcode") not in (None, "") else None,
                is_custom=0,
                name=str(item["name"]),
                unit_price=float(item["price"]),
                unit_cost=float(item["cost"]) if item.get("cost") not in (None, "") else None,
                is_cigarette=int(item["is_cigarette"]) if item.get("is_cigarette") not in (None, "") else None,
                product_category=item.get("product_category"),
                quantity=1,
            )
            line_item.recompute()
            current_order.items[line_item.item_id] = line_item
        current_order.recalculate_totals()

    @app.route("/")
    def index():
        return send_from_directory(STATIC_DIR, "index.html")

    @app.route("/api/health")
    def health():
        return jsonify({"ok": True, "db_path": app_ref.db_manager.db_path})

    @app.route("/api/order")
    def get_order():
        return jsonify(order_payload())

    @app.route("/api/order/clear", methods=["POST"])
    def clear_order():
        nonlocal current_order
        current_order = Order(tax_rate=DEFAULT_TAX_RATE)
        return jsonify(order_payload())

    @app.route("/api/items/search")
    def search_items():
        query = str(request.args.get("q", "")).strip().lower()
        limit = min(int(request.args.get("limit", 25)), 100)
        rows = app_ref.db_manager.get_all_items()
        matches = []
        for row in rows:
            item = {
                "barcode": row[0],
                "name": row[1],
                "price": row[2],
                "cost": row[3],
                "sku": row[4],
                "product_category": row[5],
                "item_id": row[6],
                "parent_barcode": row[7],
                "taxable": row[8],
                "is_rolling_papers": row[9],
                "is_cigarette": row[10],
                "papers_per_pack": row[11],
                "ean_barcode": row[12],
            }
            haystack = " ".join(str(item.get(key) or "") for key in ("name", "barcode", "ean_barcode", "sku")).lower()
            if not query or query in haystack:
                matches.append(item_payload(item))
            if len(matches) >= limit:
                break
        return jsonify({"items": matches})

    @app.route("/api/order/scan", methods=["POST"])
    def scan_item():
        data = request.get_json(silent=True) or {}
        barcode = data.get("barcode", "")
        item = find_item_by_any_barcode(barcode)
        if not item:
            return jsonify({"error": "Item not found", "barcode": barcode}), 404
        add_item_to_order(item)
        return jsonify({"item": item_payload(item), "order": order_payload()})

    @app.route("/api/order/items", methods=["POST"])
    def add_item():
        data = request.get_json(silent=True) or {}
        item_id = str(data.get("item_id", "")).strip()
        barcode = str(data.get("barcode", "")).strip()
        item = app_ref.db_manager.get_item_details(item_id=item_id) if item_id else None
        if not item and barcode:
            item = find_item_by_any_barcode(barcode)
        if not item:
            return jsonify({"error": "Item not found"}), 404
        add_item_to_order(item)
        return jsonify({"item": item_payload(item), "order": order_payload()})

    @app.route("/api/order/items/<item_id>", methods=["PATCH", "DELETE"])
    def update_line_item(item_id: str):
        if item_id not in current_order.items:
            return jsonify({"error": "Line item not found"}), 404
        if request.method == "DELETE":
            del current_order.items[item_id]
        else:
            data = request.get_json(silent=True) or {}
            quantity = max(int(data.get("quantity", 1)), 1)
            current_order.items[item_id].quantity = quantity
            current_order.items[item_id].recompute()
        current_order.recalculate_totals()
        return jsonify(order_payload())

    @app.route("/api/order/pay", methods=["POST"])
    def pay_order():
        data = request.get_json(silent=True) or {}
        method = str(data.get("method", "Cash")).title()
        amount_tendered = data.get("amount_tendered")
        current_order.recalculate_totals()
        current_order.payment_method = method
        if method == "Cash":
            tendered = float(amount_tendered or current_order.total_with_tax or 0)
            current_order.amount_tendered = tendered
            current_order.change_given = round(tendered - float(current_order.total_with_tax or 0), 2)
        else:
            current_order.amount_tendered = float(current_order.total_with_tax or 0)
            current_order.change_given = 0.0
        return jsonify(order_payload())

    @app.route("/api/order/finalize", methods=["POST"])
    def finalize_order():
        nonlocal current_order
        data = request.get_json(silent=True) or {}
        if not current_order.items:
            return jsonify({"error": "Cannot finalize an empty order"}), 400
        if not current_order.payment_method:
            return jsonify({"error": "Take payment before finalizing"}), 400
        current_order.recalculate_totals()
        app_ref.db_manager.send_order_to_history_database(current_order)
        if data.get("open_drawer"):
            from open_cash_drawer import open_cash_drawer

            open_cash_drawer()
        if data.get("print_receipt"):
            from receipt_printer import ReceiptPrinter

            if app_ref.receipt_printer is None:
                app_ref.receipt_printer = ReceiptPrinter(app_ref)
            app_ref.receipt_printer.print_receipt(current_order)
        completed = current_order.to_dict()
        current_order = Order(tax_rate=DEFAULT_TAX_RATE)
        return jsonify({"completed_order": completed, "order": order_payload()})

    return app


app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("RIGS_WEB_POS_PORT", "5055"))
    app.run(host="127.0.0.1", port=port, debug=True)
