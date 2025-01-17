from flask import Flask
from extensions import db, babel, bootstrap, celery

def create_app():
    app = Flask(__name__)

    # Load configurations from config.py
    app.config.from_object('config.Config')

    # Initialize extensions with the app
    db.init_app(app)
    babel.init_app(app)
    bootstrap.init_app(app)

    # Initialize Celery
    celery.conf.update(app.config)

    # Register blueprints
    from routes import main_bp
    app.register_blueprint(main_bp)

    # Create database tables
    with app.app_context():
        db.drop_all()
        db.create_all()

    return app