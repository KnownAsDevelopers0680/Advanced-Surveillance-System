import os
import time
import math
import cv2
import cvzone
from flask import Flask, render_template, request, redirect, url_for, Response, jsonify
from flask_migrate import Migrate
from flask_minify import Minify
from sys import exit
from twilio.rest import Client
from ultralytics import YOLO
from api_generator.commands import gen_api
from apps.config import config_dict
from apps import create_app, db

# Initialize Flask app
app = Flask(__name__)

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
    app.logger.info('DEBUG            = ' + str(DEBUG))
    app.logger.info('Page Compression = ' + 'FALSE' if DEBUG else 'TRUE')
    app.logger.info('DBMS             = ' + app_config.SQLALCHEMY_DATABASE_URI)
    app.logger.info('ASSETS_ROOT      = ' + app_config.ASSETS_ROOT)

for command in [gen_api, ]:
    app.cli.add_command(command)

# Twilio configuration
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

# Initialize YOLO model with custom weights
model = YOLO("best.pt")

# Define class names
classNames = ['Body', 'Helmet', 'No helmet', 'Other']

# Video stream generator with 30-second interval check for "Other" class
def generate_frames():
    cap = cv2.VideoCapture(0)  # Use webcam (0)
    last_alert_time = time.time()  # Track the time of the last alert
    screenshot_dir = os.path.join("static", "screenshots")  # Directory to save screenshots inside static

    # Create the directory if it doesn't exist
    if not os.path.exists(screenshot_dir):
        os.makedirs(screenshot_dir)

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

                # If the detected class is "Other", check the time interval
                if classNames[cls] == 'Other':
                    current_time = time.time()
                    if current_time - last_alert_time >= 30:  # Check if 30 seconds have passed
                        alert_message = "Hello! This is a Helmet Detection Alert From SurveilX."
                        
                        #Send SMS
                        send_sms(alert_message)
                        
                        # Save the screenshot
                        timestamp = time.strftime("%Y%m%d-%H%M%S")
                        screenshot_path = os.path.join(screenshot_dir, f"screenshot_{timestamp}.jpg")
                        cv2.imwrite(screenshot_path, img)
                        print(f"Screenshot saved at: {screenshot_path}")

                        last_alert_time = current_time  # Update the last alert time

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

# @app.route('/get_latest_screenshots', methods=['GET'])
# def get_latest_screenshots():
#     screenshot_dir = os.path.join('static', 'screenshots')
#     try:
#         # Get all image files sorted by creation time (newest first)
#         files = sorted(
#             [f for f in os.listdir(screenshot_dir) if f.endswith(('.jpg', '.jpeg', '.png'))],
#             key=lambda x: os.path.getctime(os.path.join(screenshot_dir, x)),
#             reverse=True
#         )
#         # Include only the latest 5 screenshots
#         latest_files = files[:1]
#         # Construct URLs relative to the static directory
#         file_paths = [f"/static/screenshots/{file}" for file in latest_files]
#         return jsonify(file_paths)
#     except Exception as e:
#         return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run()
