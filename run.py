import os
import time
import math
import cv2
import cvzone
from flask import Flask, render_template, Response, jsonify
from flask_migrate import Migrate
from flask_minify import Minify
from twilio.rest import Client
from ultralytics import YOLO
from api_generator.commands import gen_api
from apps.config import config_dict
from apps import create_app, db
from datetime import datetime
import sqlite3
import logging

# Initialize Flask app
app = Flask(__name__)

DEBUG = os.getenv('DEBUG', 'False') == 'True'

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

# Twilio Configuration
account_sid = ''  # Replace with your SID or load from environment variables
auth_token = ''   # Replace with your Auth Token or load from environment variables
twilio_phone_number = ''
recipient_phone_number = ''

# YOLO model initialization
model = YOLO("best.pt")
classNames = ['Body', 'Helmet', 'No helmet', 'Other']

# Database setup
def init_db():
    try:
        connection = sqlite3.connect("incidents.db")
        cursor = connection.cursor()
        create_table_query = """
        CREATE TABLE IF NOT EXISTS incidents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            snapshot BLOB, 
            gender TEXT NOT NULL, 
            geolocation TEXT NOT NULL, 
            timestamp TEXT NOT NULL, 
            date TEXT NOT NULL, 
            video BLOB 
        );
        """
        cursor.execute(create_table_query)
        connection.commit()
        connection.close()
        app.logger.info("SQLite database initialized successfully.")
    except Exception as e:
        app.logger.error(f"Failed to initialize SQLite database: {e}")

# Call the database initialization
init_db() 

# Function to insert incident into the database
def insert_incident(snapshot, gender, geolocation, video):
    try:
        connection = sqlite3.connect("incidents.db")
        cursor = connection.cursor()
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        date = datetime.now().strftime("%Y-%m-%d")

        # Open snapshot and video as binary data
        with open(snapshot, "rb") as snapshot_file:
            snapshot_data = snapshot_file.read()

        with open(video, "rb") as video_file:
            video_data = video_file.read()

        insert_query = """
        INSERT INTO incidents (snapshot, gender, geolocation, timestamp, date, video)
        VALUES (?, ?, ?, ?, ?, ?);
        """
        cursor.execute(insert_query, (snapshot_data, gender, geolocation, timestamp, date, video_data))
        connection.commit()
        connection.close()
        app.logger.info("Incident recorded in the database successfully.")
    except Exception as e:
        app.logger.error(f"Failed to insert incident into database: {e}")
        
# Twilio SMS function
def send_sms(alert_message):
    try:
        client = Client(account_sid, auth_token)
        message = client.messages.create(
            body=alert_message,
            from_=twilio_phone_number,
            to=recipient_phone_number
        )
        app.logger.info(f"SMS sent: {message.sid}")
    except Exception as e:
        app.logger.error(f"Failed to send SMS: {e}")

# Video streaming and object detection
def generate_frames():
    try:
        cap = cv2.VideoCapture(0)  # Webcam
        if not cap.isOpened():
            app.logger.error("Cannot access the camera.")
            return

        last_alert_time = time.time()
        screenshot_dir = os.path.join("static", "screenshots")
        video_dir = os.path.join("static", "videos")

        if not os.path.exists(screenshot_dir):
            os.makedirs(screenshot_dir)
        if not os.path.exists(video_dir):
            os.makedirs(video_dir)

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

                    if classNames[cls] == 'Other':
                        current_time = time.time()
                        if current_time - last_alert_time >= 30:
                            timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
                            snapshot_path = os.path.join(screenshot_dir, f"screenshot_{timestamp}.jpg")
                            
                            # Save snapshot
                            cv2.imwrite(snapshot_path, img)
                            app.logger.info(f"Snapshot saved: {snapshot_path}")

                            # Record 5-second video
                            video_path = os.path.join(video_dir, f"video_{timestamp}.mp4")
                            video_writer = cv2.VideoWriter(
                                video_path, cv2.VideoWriter_fourcc(*'mp4v'),
                                20, (img.shape[1], img.shape[0])
                            )
                            start_time = time.time()
                            while time.time() - start_time < 5:
                                success, frame = cap.read()
                                if success:
                                    video_writer.write(frame)
                                else:
                                    break
                            video_writer.release()
                            app.logger.info(f"Video saved: {video_path}")

                            # Save to database
                            insert_incident(snapshot_path, "Unknown", "Unknown", video_path)

                            # Send SMS alert
                            alert_message = "Helmet Detection Alert: 'Other' class detected!"
                            send_sms(alert_message)

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
    return render_template('index.html')

@app.route('/video_feed')
def video_feed():
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(filename='app.log', level=logging.INFO)

    app.run(debug=DEBUG)
