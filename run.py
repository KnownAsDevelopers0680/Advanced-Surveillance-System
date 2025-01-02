import os
import time
import math
import cv2
import cvzone
from flask import Flask, render_template, request, Response, jsonify
from flask_migrate import Migrate
from flask_minify import Minify
from twilio.rest import Client
from ultralytics import YOLO
from api_generator.commands import gen_api
from apps.config import config_dict
from apps import create_app, db

# Initialize Flask app
app = Flask(__name__)

# Load environment variables securely
DEBUG = (os.getenv('DEBUG', 'False') == 'True')
# TWILIO_ACCOUNT_SID = os.getenv('AC498468e7877b48e9640cc7953cc2f66c')
# TWILIO_AUTH_TOKEN = os.getenv('e0f5d97d9d7780d20059d18e145641a1')
# TWILIO_PHONE_NUMBER = os.getenv('+14692146189')
# RECIPIENT_PHONE_NUMBER = os.getenv('+918261983331')

# Configuration
get_config_mode = 'Debug' if DEBUG else 'Production'

try:
    app_config = config_dict[get_config_mode.capitalize()]
except KeyError:
    raise RuntimeError("Invalid <config_mode>. Expected values [Debug, Production]")

app = create_app(app_config)
Migrate(app, db)

if not DEBUG:
    Minify(app=app, html=True, js=False, cssless=False)
    
if DEBUG:
    app.logger.info('DEBUG            = ' + str(DEBUG))
    app.logger.info('Page Compression = ' + 'FALSE' if DEBUG else 'TRUE')
    app.logger.info('DBMS             = ' + app_config.SQLALCHEMY_DATABASE_URI)
    app.logger.info('ASSETS_ROOT      = ' + app_config.ASSETS_ROOT)

# CLI command registration
for command in [gen_api]:
    app.cli.add_command(command)

# Twilio configuration
account_sid = 'AC498468e7877b48e9640cc7953cc2f66c'  # Replace with your actual SID
auth_token = 'e0f5d97d9d7780d20059d18e145641a1'    # Replace with your actual Auth Token
twilio_phone_number = '+14692146189'
recipient_phone_number = '+918261983331'

# YOLO model initialization
model = YOLO("best.pt")
classNames = ['Body', 'Helmet', 'No helmet', 'Other']

# Twilio SMS function with error handling
def send_sms(alert_message):
    try:
        client = Client(account_sid, auth_token)
        message = client.messages.create(
            body=alert_message,
            from_=twilio_phone_number,
            to=recipient_phone_number
        )
        print(f"SMS sent: {message.sid}")
    except Exception as e:
        app.logger.error(f"Failed to send SMS: {e}")

# Video streaming and object detection
def generate_frames():
    try:
        cap = cv2.VideoCapture(0)  # Webcam
        last_alert_time = time.time()
        screenshot_dir = os.path.join("static", "screenshots")

        if not os.path.exists(screenshot_dir):
            os.makedirs(screenshot_dir)

        while cap.isOpened():
            success, img = cap.read()
            if not success:
                app.logger.error("Failed to read from webcam")
                break

            results = model(img, stream=True)
            for r in results:
                boxes = r.boxes
                for box in boxes:
                    x1, y1, x2, y2 = map(int, box.xyxy[0])
                    w, h = x2 - x1, y2 - y1
                    cvzone.cornerRect(img, (x1, y1, w, h))

                    conf = math.ceil(box.conf[0] * 100) / 100
                    cls = int(box.cls[0])
                    cvzone.putTextRect(
                        img, f'{classNames[cls]} {conf}',
                        (max(0, x1), max(35, y1)),
                        scale=1, thickness=1
                    )

                    # Alert handling for "Other" class
                    if classNames[cls] == 'Other':
                        current_time = time.time()
                        if current_time - last_alert_time >= 30:
                            alert_message = "Helmet Detection Alert: This is a Helmet Detection Alert From SurveilX."
                            send_sms(alert_message)

                            # Save screenshot
                            timestamp = time.strftime("%Y%m%d-%H%M%S")
                            screenshot_path = os.path.join(screenshot_dir, f"screenshot_{timestamp}.jpg")
                            cv2.imwrite(screenshot_path, img)
                            app.logger.info(f"Screenshot saved: {screenshot_path}")

                            last_alert_time = current_time

            ret, buffer = cv2.imencode('.jpg', img)
            frame = buffer.tobytes()
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
    except Exception as e:
        app.logger.error(f"Error during video streaming: {e}")
    finally:
        cap.release()
        cv2.destroyAllWindows()

@app.route('/')
def index():
    return render_template('index.html')  # Updated UI template

@app.route('/video_feed')
def video_feed():
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/screenshots', methods=['GET'])
def get_latest_screenshots():
    try:
        screenshot_dir = os.path.join('static', 'screenshots')
        files = sorted(
            [f for f in os.listdir(screenshot_dir) if f.endswith(('.jpg', '.jpeg', '.png'))],
            key=lambda x: os.path.getctime(os.path.join(screenshot_dir, x)),
            reverse=True
        )[:5]  # Limit to 5 latest screenshots
        return jsonify([f"/static/screenshots/{file}" for file in files])
    except Exception as e:
        app.logger.error(f"Error fetching screenshots: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=DEBUG)
