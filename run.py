# -*- encoding: utf-8 -*-
"""
Copyright (c) 2019 - present AppSeed.us
"""

import os
from   flask_migrate import Migrate
from   flask_minify  import Minify
from   sys import exit
from twilio.rest import Client
from flask import Flask, render_template, request, redirect, url_for

from api_generator.commands import gen_api

from apps.config import config_dict
from apps import create_app, db

# # Initialize Flask app
# app = Flask(__name__)

# WARNING: Don't run with debug turned on in production!
DEBUG = (os.getenv('DEBUG', 'False') == 'True')

# The configuration
get_config_mode = 'Debug' if DEBUG else 'Production'

# Your Twilio account SID and Auth Token
account_sid = 'AC498468e7877b48e9640cc7953cc2f66c'  # Replace with your actual SID
auth_token = 'c51e2af65def3b1cc9ed6097775a7dd4'    # Replace with your actual Auth Token

client = Client(account_sid, auth_token)



try:

    # Load the configuration using the default values
    app_config = config_dict[get_config_mode.capitalize()]

except KeyError:
    exit('Error: Invalid <config_mode>. Expected values [Debug, Production] ')

app = create_app(app_config)
Migrate(app, db)

if not DEBUG:
    Minify(app=app, html=True, js=False, cssless=False)
    
if DEBUG:
    app.logger.info('DEBUG            = ' + str(DEBUG)             )
    app.logger.info('Page Compression = ' + 'FALSE' if DEBUG else 'TRUE' )
    app.logger.info('DBMS             = ' + app_config.SQLALCHEMY_DATABASE_URI)
    app.logger.info('ASSETS_ROOT      = ' + app_config.ASSETS_ROOT )

for command in [gen_api, ]:
    app.cli.add_command(command)
    
# Route to handle SMS sending
@app.route('/send_sms', methods=['POST'])
def send_sms():
    # Send the SMS
    message = client.messages.create(
        body='Hello! This is a Helmet Detection Alert From SurveilX.',
        from_='+14692146189',  # Replace with your Twilio number
        to='+918261983331'      # Replace with your phone number
    )
    return f"Message sent! SID: {message.sid}"
    
if __name__ == "__main__":
    app.run()
    
    
    
    
