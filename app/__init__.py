"""Flask application factory."""

from pathlib import Path

from flask import Flask, send_from_directory
from flask_cors import CORS

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


def create_app() -> Flask:
    app = Flask(__name__, static_folder=str(STATIC_DIR), static_url_path="/static")
    CORS(app)

    from app.api.routes import api_bp

    app.register_blueprint(api_bp, url_prefix="/api")

    @app.route("/")
    def index():
        return send_from_directory(str(STATIC_DIR), "index.html")

    return app
