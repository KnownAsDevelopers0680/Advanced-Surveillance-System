# -*- encoding: utf-8 -*-
"""
Copyright (c) 2019 - present AppSeed.us
"""

import os
from   flask_migrate import Migrate
from   flask_minify  import Minify
from   sys import exit
from twilio.rest import Client
from flask import Flask, render_template, request, redirect, url_for, Response
import cv2
import math
import cvzone
from ultralytics import YOLO

from api_generator.commands import gen_api

from apps.config import config_dict
from apps import create_app, db

# # Initialize Flask app
# app = Flask(__name__)

# WARNING: Don't run with debug turned on in production!
DEBUG = (os.getenv('DEBUG', 'False') == 'True')

# The configuration
get_config_mode = 'Debug' if DEBUG else 'Production'


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

# Your Twilio account SID and Auth Token
account_sid = ''  # Replace with your actual SID
auth_token = ''    # Replace with your actual Auth Token
twilio_phone_number = '+14692146189'
recipient_phone_number = '+918261983331'

# Function to send SMS
def send_sms(alert_message):
    client = Client(account_sid, auth_token)
    message = client.messages.create(
        body=alert_message,
        from_=twilio_phone_number,
        to=recipient_phone_number
    )
    print(f"SMS sent: {message.sid}")
    
# Route to handle SMS sending
# @app.route('/send_sms', methods=['POST'])
# def send_sms():
#     # Send the SMS
#     message = client.messages.create(
#         body='Hello! This is a Helmet Detection Alert From SurveilX.',
#         from_='+14692146189',  # Replace with your Twilio number
#         to='+918261983331'      # Replace with your phone number
#     )
#     return f"Message sent! SID: {message.sid}"

# Initialize YOLO model with custom weights
model = YOLO("best.pt")

# Define class names
classNames = ['Body', 'Helmet', 'No helmet', 'Other']

# Video stream generator
def generate_frames():
    cap = cv2.VideoCapture(0)  # Use webcam (0)

    while True:
        success, img = cap.read()
        if not success:
            break

        results = model(img, stream=True)
        for r in results:
            boxes = r.boxes
            for box in boxes:
                x1, y1, x2, y2 = box.xyxy[0]
                x1, y1, x2, y2 = int(x1), int(y1), int(x2), int(y2)

                w, h = x2 - x1, y2 - y1
                cvzone.cornerRect(img, (x1, y1, w, h))
                conf = math.ceil((box.conf[0] * 100)) / 100
                cls = int(box.cls[0])

                cvzone.putTextRect(img, f'{classNames[cls]} {conf}', (max(0, x1), max(35, y1)), scale=1, thickness=1)
                
                # If the detected class is "Other", send SMS
                if classNames[cls] == 'Other':
                    alert_message = "Hello! This is a Helmet Detection Alert From SurveilX."
                    send_sms(alert_message)

        # Encode the processed frame
        ret, buffer = cv2.imencode('.jpg', img)
        frame = buffer.tobytes()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

@app.route('/')
def index():
    return render_template('surveillance.html')

@app.route('/video_feed')
def video_feed():
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')
    
if __name__ == "__main__":
    app.run()
    
    
    
    
