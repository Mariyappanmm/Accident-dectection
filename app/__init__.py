from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from app.config import Config

db = SQLAlchemy()

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Initialize Flask-SQLAlchemy with the app
    db.init_app(app)

    # Register blueprints (routes)
    from app.routes import main_bp
    app.register_blueprint(main_bp)

    return app
