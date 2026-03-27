"""Application entry point."""

import logging

from app import create_app
from config.settings import get_settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

settings = get_settings()
app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=settings.FLASK_DEBUG)
