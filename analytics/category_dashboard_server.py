import os
import sys

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from server_utils import run_dashboard_app

ANALYTICS_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.abspath(os.path.join(ANALYTICS_DIR, "..", "src"))
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from product_categories import ProductCategoryStore

app = Flask(__name__)
CORS(app)


def get_category_store():
    return ProductCategoryStore()


def category_payload(store):
    categories = [category.to_dict() for category in store.list_category_objects()]
    return {
        "categories": categories,
        "groups": {
            "common": [category for category in categories if category["group"] == "common"],
            "uncommon": [category for category in categories if category["group"] == "uncommon"],
        },
        "data_file": str(store.data_file),
    }


@app.route("/")
def index():
    return send_from_directory(ANALYTICS_DIR, "category_dashboard.html")


@app.route("/api/categories", methods=["GET"])
def list_categories():
    return jsonify(category_payload(get_category_store()))


@app.route("/api/categories", methods=["POST"])
def create_category():
    payload = request.get_json(silent=True) or {}
    store = get_category_store()

    try:
        category = store.create(
            name=payload.get("name"),
            group=payload.get("group", "common"),
            category_id=payload.get("id") or None,
        )
        store.save()
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    return jsonify({"ok": True, "category": category.to_dict(), **category_payload(store)}), 201


@app.route("/api/categories/<category_id>", methods=["PUT"])
def update_category(category_id):
    payload = request.get_json(silent=True) or {}
    store = get_category_store()

    try:
        category = store.update(
            category_id,
            new_name=payload.get("name"),
            group=payload.get("group"),
            category_id=payload.get("id") or None,
        )
        if not category:
            return jsonify({"error": "Category not found."}), 404
        store.save()
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    return jsonify({"ok": True, "category": category.to_dict(), **category_payload(store)})


@app.route("/api/categories/<category_id>", methods=["DELETE"])
def delete_category(category_id):
    store = get_category_store()
    if not store.delete(category_id):
        return jsonify({"error": "Category not found."}), 404

    store.save()
    return jsonify({"ok": True, **category_payload(store)})


if __name__ == "__main__":
    run_dashboard_app(app, default_port=8888, host="0.0.0.0", debug=True)
