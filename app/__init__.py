"""Flask application factory."""

from flask import Flask
from flask_cors import CORS


def create_app() -> Flask:
    app = Flask(__name__)
    CORS(app)

    from app.api.routes import api_bp

    app.register_blueprint(api_bp, url_prefix="/api")

    return app
