"""
Farm Bridge Flask application.

Created as an application factory so tests and deployment can pick the right
configuration (development SQLite, test SQLite, or production MySQL).
"""

import os
from pathlib import Path

from flask import Flask, jsonify, render_template
from flask_cors import CORS
from werkzeug.exceptions import HTTPException

from config import config
from database.db import init_db as init_database, engine_info

BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = Path(config.UPLOAD_FOLDER)


def _register_blueprints(app):
    from routes.auth import bp as auth_bp
    from routes.consumer import alias_bp, bp as consumer_bp
    from routes.farmer import bp as farmer_bp
    from routes.legacy import bp as legacy_bp
    from routes.listings import bp as listings_bp
    from routes.mandi import bp as mandi_bp
    from routes.market import bp as market_bp
    from routes.misc import bp as misc_bp
    from routes.orders import bp as orders_bp
    from routes.pools import bp as pools_bp
    from routes.subscriptions import bp as subscriptions_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(consumer_bp)
    app.register_blueprint(alias_bp)
    app.register_blueprint(farmer_bp)
    app.register_blueprint(legacy_bp)
    app.register_blueprint(listings_bp)
    app.register_blueprint(mandi_bp)
    app.register_blueprint(market_bp)
    app.register_blueprint(misc_bp)
    app.register_blueprint(orders_bp)
    app.register_blueprint(pools_bp)
    app.register_blueprint(subscriptions_bp)


def create_app(test_config=None):
    global config
    app = Flask(
        __name__,
        template_folder=str(BASE_DIR),
        static_folder=str(UPLOAD_DIR),
        static_url_path='/uploads',
    )
    app.config['SECRET_KEY'] = config.SECRET_KEY
    app.config['MAX_CONTENT_LENGTH'] = config.MAX_UPLOAD_BYTES + 1024 * 1024

    # Apply test overrides before initialising the DB.
    if test_config:
        for k, v in test_config.items():
            if k == 'ENVIRONMENT':
                config.ENVIRONMENT = v
            elif k == 'DB_ENGINE':
                config.DB_ENGINE = v
            elif k == 'SQLITE_PATH':
                config.SQLITE_PATH = v
            elif k == 'SECRET_KEY':
                config.SECRET_KEY = v
            else:
                app.config[k] = v

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    init_database(config)
    _register_blueprints(app)

    # CORS. In production set CORS_ORIGINS to your frontend domain(s).
    origins = os.environ.get('CORS_ORIGINS', '*')
    CORS(app, resources={r'/api/*': {'origins': origins.split(',') if origins != '*' else '*'}})

    @app.route('/')
    def index():
        return render_template('index.html')

    @app.route('/health')
    def health():
        return jsonify({
            'status': 'ok',
            'app': 'FarmBridge',
            'database': engine_info(),
        })

    @app.errorhandler(HTTPException)
    def handle_http_error(e):
        payload = {
            'success': False,
            'error': {
                'code': e.description.upper().replace(' ', '_') if e.description else 'HTTP_ERROR',
                'message': e.description or str(e),
            }
        }
        return jsonify(payload), e.code

    @app.errorhandler(Exception)
    def handle_error(e):
        app.logger.exception('Unhandled server error: %s', e)
        return jsonify({
            'success': False,
            'error': {'code': 'INTERNAL_ERROR', 'message': 'Internal server error'}
        }), 500

    # Log startup state.
    app.logger.info('FarmBridge starting in %s mode with DB %s',
                    config.ENVIRONMENT, engine_info())

    return app


app = create_app()


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print('''
    🌾 FARM BRIDGE Server Starting...
    =================================
    → Local: http://localhost:{port}
    → Network: http://0.0.0.0:{port}
    → Database: {engine}
    → Consumer terminology enabled
    =================================
    '''.format(port=port, engine=engine_info()))
    app.run(host='0.0.0.0', port=port, debug=config.DEBUG)
