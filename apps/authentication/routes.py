# -*- encoding: utf-8 -*-
"""
Copyright (c) 2019 - present AppSeed.us
"""

import json
from datetime import datetime
import logging

from flask_restx import Resource, Api
from flask import render_template, redirect, request, url_for
from flask_login import current_user, login_user, logout_user
from flask_dance.contrib.github import github
from sqlalchemy.exc import SQLAlchemyError

from apps import db, login_manager
from apps.authentication import blueprint
from apps.authentication.forms import LoginForm, CreateAccountForm
from apps.authentication.models import Users
from apps.authentication.util import verify_pass, generate_token

# Bind API -> Auth BP
api = Api(blueprint)

# Default Route
@blueprint.route('/')
def route_default():
    return redirect(url_for('authentication_blueprint.login'))

# GitHub OAuth Login
@blueprint.route("/github")
def login_github():
    """GitHub login using Flask-Dance."""
    if not github.authorized:
        return redirect(url_for("github.login"))

    try:
        github.get("/user")
        return redirect(url_for('home_blueprint.index'))
    except Exception as e:
        logging.error(f"GitHub login failed: {e}")
        return render_template('home/page-500.html'), 500

# Login Route
@blueprint.route('/login', methods=['GET', 'POST'])
def login():
    login_form = LoginForm(request.form)
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        # Locate user
        user = Users.query.filter_by(username=username).first()

        # Check the password
        if user and verify_pass(password, user.password):
            login_user(user)
            return redirect(url_for('home_blueprint.index'))

        # Invalid credentials
        return render_template('accounts/login.html',
                               msg='Invalid username or password',
                               form=login_form)

    if current_user.is_authenticated:
        return redirect(url_for('home_blueprint.index'))
    else:
        return render_template('accounts/login.html', form=login_form)

# Registration Route
@blueprint.route('/register', methods=['GET', 'POST'])
def register():
    create_account_form = CreateAccountForm(request.form)
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']

        # Check if username or email already exists
        if Users.query.filter_by(username=username).first():
            return render_template('accounts/register.html',
                                   msg='Username already registered',
                                   success=False,
                                   form=create_account_form)

        if Users.query.filter_by(email=email).first():
            return render_template('accounts/register.html',
                                   msg='Email already registered',
                                   success=False,
                                   form=create_account_form)

        # Create new user
        try:
            user = Users(**request.form)
            db.session.add(user)
            db.session.commit()
            logout_user()  # Ensure user session is cleared
            return render_template('accounts/register.html',
                                   msg='User created successfully.',
                                   success=True,
                                   form=create_account_form)
        except SQLAlchemyError as e:
            logging.error(f"User registration failed: {e}")
            return render_template('home/page-500.html'), 500

    return render_template('accounts/register.html', form=create_account_form)

# JWT Login Route
@api.route('/login/jwt/', methods=['POST'])
class JWTLogin(Resource):
    def post(self):
        try:
            data = request.form or request.json
            if not data:
                return {'message': 'Username or password is missing', 'success': False}, 400

            # Locate user
            user = Users.query.filter_by(username=data.get('username')).first()
            if user and verify_pass(data.get('password'), user.password):
                # Generate token if not present or expired
                if not user.api_token or user.api_token == '':
                    user.api_token = generate_token(user.id)
                    user.api_token_ts = int(datetime.utcnow().timestamp())
                    db.session.commit()

                return {
                    "message": "Successfully fetched auth token",
                    "success": True,
                    "data": user.api_token
                }
            return {'message': 'Invalid username or password', 'success': False}, 403
        except SQLAlchemyError as e:
            logging.error(f"JWT login failed: {e}")
            return {"error": "Database error occurred", "success": False, "message": str(e)}, 500
        except Exception as e:
            logging.error(f"Unexpected error: {e}")
            return {"error": "An error occurred", "success": False, "message": str(e)}, 500

# Logout Route
@blueprint.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('authentication_blueprint.login'))

# Error Handlers
@login_manager.unauthorized_handler
def unauthorized_handler():
    return render_template('home/page-403.html'), 403

@blueprint.errorhandler(403)
def access_forbidden(error):
    return render_template('home/page-403.html'), 403

@blueprint.errorhandler(404)
def not_found_error(error):
    return render_template('home/page-404.html'), 404

@blueprint.errorhandler(500)
def internal_error(error):
    return render_template('home/page-500.html'), 500
