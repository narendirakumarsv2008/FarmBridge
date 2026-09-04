"""
Farm Bridge — application entry point.

This module is intentionally thin: it wires the Flask app together (config,
CORS, database, blueprints, static uploads) and starts the server. All business
logic lives in `routes/` and `services/`; all SQL lives in `models/` and
`database/`.

Run:
    python app.py                       # development server
    gunicorn -w 4 -b 0.0.0.0:8000 app:app   # production
"""

import logging
import os

from flask import Flask, render_template, send_from_directory
from flask_cors import CORS

import config
from database import db
from routes import register_blueprints

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
log = logging.getLogger("farmbridge")


def create_app():
    app = Flask(
        __name__,
        template_folder=str(config.BASE_DIR),
        static_folder=str(config.BASE_DIR),
    )
    app.config["SECRET_KEY"] = config.Config.SECRET_KEY
    app.config["MAX_CONTENT_LENGTH"] = config.Config.MAX_CONTENT_LENGTH
    app.config["JSON_SORT_KEYS"] = False

    CORS(app)

    os.makedirs(config.UPLOAD_FOLDER, exist_ok=True)

    log.info("Farm Bridge starting — environment=%s", config.Config.ENVIRONMENT)
    engine = db.init_db()
    log.info("Database ready — engine=%s", engine)

    register_blueprints(app)

    @app.route("/")
    def index():
        return render_template("index.html")

    @app.route("/uploads/<path:filename>")
    def uploaded_file(filename):
        return send_from_directory(config.UPLOAD_FOLDER, filename)

    return app


app = create_app()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    debug = config.Config.DEBUG
    log.info("Serving on http://0.0.0.0:%s (debug=%s)", port, debug)
    app.run(host="0.0.0.0", port=port, debug=debug)
