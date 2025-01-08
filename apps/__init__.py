# -*- encoding: utf-8 -*-
"""
Copyright (c) 2019 - present AppSeed.us
"""

import os
import logging
from flask import Flask
from flask_login import LoginManager
from flask_sqlalchemy import SQLAlchemy
from importlib import import_module
from sqlalchemy.exc import SQLAlchemyError

# Initialize extensions
db = SQLAlchemy()
login_manager = LoginManager()

def register_extensions(app):
    """Register Flask extensions."""
    db.init_app(app)
    login_manager.init_app(app)

def register_blueprints(app):
    """Register Flask blueprints."""
    blueprints = ('authentication', 'home', 'api')
    for module_name in blueprints:
        module = import_module(f'apps.{module_name}.routes')
        if module.blueprint.name not in app.blueprints:
            app.register_blueprint(module.blueprint)
        else:
            logging.warning(f"Blueprint {module.blueprint.name} is already registered.")


def configure_database(app):
    """Configure the database."""
    @app.before_first_request
    def initialize_database():
        try:
            db.create_all()
        except SQLAlchemyError as e:
            logging.error(f"Database initialization failed: {e}")
            # Fallback to SQLite
            basedir = os.path.abspath(os.path.dirname(__file__))
            app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{os.path.join(basedir, 'db.sqlite3')}"
            logging.warning("Falling back to SQLite.")
            db.create_all()

    @app.teardown_request
    def shutdown_session(exception=None):
        db.session.remove()

def create_app(config):
    """Create Flask app."""
    app = Flask(__name__)
    app.config.from_object(config)
    
    # Register extensions
    register_extensions(app)
    
    # Register blueprints
    register_blueprints(app)
    
    # Configure database
    configure_database(app)

    return app
