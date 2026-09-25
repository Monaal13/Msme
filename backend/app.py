import os

import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(BASE_DIR)

if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

VENV_SITE_PACKAGES = os.path.join(PROJECT_DIR, ".venv", "Lib", "site-packages")
if os.path.exists(VENV_SITE_PACKAGES) and VENV_SITE_PACKAGES not in sys.path:
    sys.path.insert(0, VENV_SITE_PACKAGES)

FRONTEND_DIR = os.path.join(PROJECT_DIR, "frontend")
PAGES_DIR = os.path.join(FRONTEND_DIR, "pages")

from flask import Flask, jsonify, request, send_from_directory

from config import Config
from routes import register_blueprints
from services.db import initialize_database


def create_app():
    app = Flask(
        __name__,
        static_folder=FRONTEND_DIR,
        static_url_path="",
    )
    app.config.from_object(Config)

    @app.after_request
    def add_cors_headers(response):
        origin = request.headers.get("Origin")
        if origin:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Credentials"] = "true"
            response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, X-Requested-With"
            response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
        else:
            response.headers["Access-Control-Allow-Origin"] = "*"
            response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, X-Requested-With"
            response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
        return response

    @app.route("/", defaults={"path": ""}, methods=["OPTIONS"])
    @app.route("/<path:path>", methods=["OPTIONS"])
    def handle_options(path):
        return "", 204

    initialize_database(app)

    register_blueprints(app)

    @app.route("/")
    def index():
        return send_from_directory(PAGES_DIR, "login.html")

    @app.route("/pages/<path:filename>")
    def pages(filename):
        return send_from_directory(PAGES_DIR, filename)

    @app.errorhandler(404)
    def not_found(error):
        if str(error).startswith("404"):
            return send_from_directory(PAGES_DIR, "404.html"), 404
        return jsonify({"error": "Not found"}), 404

    @app.errorhandler(500)
    def server_error(error):
        return send_from_directory(PAGES_DIR, "500.html"), 500

    # Start background scheduled message worker (only in long-running environments, not Vercel serverless)
    if not os.getenv("VERCEL"):
        try:
            import threading
            import time
            from services.notifications import process_due_scheduled_messages
            
            def worker():
                # Wait a few seconds for Flask to boot
                time.sleep(5)
                with app.app_context():
                    while True:
                        try:
                            process_due_scheduled_messages()
                        except Exception as e:
                            app.logger.error(f"Error in background scheduled message worker: {e}")
                        time.sleep(30)
                        
            t = threading.Thread(target=worker, daemon=True)
            t.start()
            app.logger.info("Background scheduled message worker started.")
        except Exception as e:
            app.logger.error(f"Failed to start scheduled message worker: {e}")

    return app


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    create_app().run(host="0.0.0.0", port=port, debug=True)
