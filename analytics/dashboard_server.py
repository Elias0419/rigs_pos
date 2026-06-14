import os
import sys

from flask import Flask, send_from_directory
from werkzeug.middleware.dispatcher import DispatcherMiddleware

ANALYTICS_DIR = os.path.dirname(os.path.abspath(__file__))
if ANALYTICS_DIR not in sys.path:
    sys.path.insert(0, ANALYTICS_DIR)

from analytics_server import app as analytics_app
from category_dashboard_server import app as category_app
from server_utils import run_dashboard_app
from tax_dashboard_server import app as tax_app, ensure_expenses_file

app = Flask(__name__)


@app.route("/")
def index():
    return send_from_directory(ANALYTICS_DIR, "dashboard.html")


app.wsgi_app = DispatcherMiddleware(
    app.wsgi_app,
    {
        "/analytics": analytics_app,
        "/taxes": tax_app,
        "/categories": category_app,
    },
)


if __name__ == "__main__":
    ensure_expenses_file()
    run_dashboard_app(app, default_port=5000, host="0.0.0.0", debug=True)
