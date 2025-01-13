import os
import time
import math
import cv2
import cvzone
from flask import Flask, render_template, Response, jsonify, send_from_directory
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
import geocoder
import requests
import sqlite3
from datetime import datetime
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

# OpenCage API Key
geolocation_api_key = ''  # Replace with your actual OpenCage API key


# YOLO model initialization
model = YOLO("best.pt")
classNames = ['wearing', 'not_wearing', 'helmet', 'no-helmet', 'phone']

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
            alert TEXT NOT NULL,
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

# Function to get geolocation based on IP (for demonstration)
def get_geolocation():
    try:
        g = geocoder.ip('me')  # Gets the geolocation of the current IP
        return g.latlng  # Returns [latitude, longitude]
    except Exception as e:
        logging.error(f"Error fetching geolocation: {e}")
        return None
    
# Function to get address using OpenCage Data API
def get_address_from_latlng(lat, lng):
    try:
        url = f"https://api.opencagedata.com/geocode/v1/json?q={lat}+{lng}&key={geolocation_api_key}"
        response = requests.get(url)
        result = response.json()
        if result and result['results']:
            # Extract the formatted address from the results
            address = result['results'][0]['formatted']
            return address
        else:
            return "Address not found"
    except Exception as e:
        logging.error(f"Error fetching address from OpenCage API: {e}")
        return "Geolocation error"

# Function to insert incident and geolocation into the database
def insert_incident(snapshot, gender, video, alert):
    try:
        # Fetch geolocation using OpenCage API
        lat_lng = get_geolocation()  # Replace with actual GPS data if available
        if lat_lng:
            latitude, longitude = lat_lng
            location = get_address_from_latlng(latitude, longitude)
        else:
            location = "Unknown"
            
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
        INSERT INTO incidents (snapshot, gender, geolocation, timestamp, date, video, alert)
        VALUES (?, ?, ?, ?, ?, ?,?);
        """
        cursor.execute(insert_query, (snapshot_data, gender, location, timestamp, date, video_data, alert))
        connection.commit()
        connection.close()
        logging.info(f"Incident recorded with geolocation: {location}.")
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

                    if classNames[cls] == 'not_wearing':
                        alert = 'Glasses not worn'
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
                            insert_incident(snapshot_path, "Unknown", video_path, alert)

                            # Send SMS alert
                            alert_message = f"Glasses Alert: A person without Glasses detected. 'Not wearing' class detected!"
                            send_sms(alert_message)

                            last_alert_time = current_time
                    
                    elif classNames[cls] == 'no-helmet':
                        alert = 'Helmet Not Worn'
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
                            insert_incident(snapshot_path, "Unknown", video_path, alert)

                            # Send SMS alert
                            alert_message = "Helmet Alert: A person without Helmet detected. 'No-helmet' class detected!"
                            send_sms(alert_message)

                            last_alert_time = current_time
                            
                    elif classNames[cls] == 'phone':
                        alert = 'Phone detected'
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
                            insert_incident(snapshot_path, "Unknown", video_path, alert)

                            # Send SMS alert
                            alert_message = "Phone Alert: A person with Phone detected. 'Phone' class detected!"
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

@app.route('/get_incident_records', methods=['GET'])
def get_incident_records():
    try:
        connection = sqlite3.connect("incidents.db")
        cursor = connection.cursor()
        fetch_query = "SELECT id, timestamp, date FROM incidents;"
        cursor.execute(fetch_query)
        records = cursor.fetchall()
        connection.close()

        # Structure the records as a list of dictionaries
        incident_list = []
        for record in records:
            incident_list.append({
                'id': record[0],
                'timestamp': record[1],
                'date': record[2]
            })

        return jsonify({'status': 'success', 'data': incident_list}), 200
    except Exception as e:
        app.logger.error(f"Error fetching incident records: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500
    






# Base directory for static files
STATIC_DIR = os.path.join(os.getcwd(),"static")

@app.route("/")
def video_storage():
    """Render the main UI with the table."""
    return render_template("video-record.html")

@app.route("/files")
def get_files():
    """Retrieve files dynamically from static folders."""
    screenshots_dir = os.path.join(STATIC_DIR, "screenshots")
    videos_dir = os.path.join(STATIC_DIR, "videos")

    files = []

    # Process screenshots (images)
    if os.path.exists(screenshots_dir):
        for filename in os.listdir(screenshots_dir):
            file_path = os.path.join(screenshots_dir, filename)
            if os.path.isfile(file_path):
                files.append({
                    "name": filename,
                    "type": "img",
                    "last_modified": os.path.getmtime(file_path),
                    "size": os.path.getsize(file_path),
                    "download_url": f"/download/screenshots/{filename}"
                })

    # Process videos
    if os.path.exists(videos_dir):
        for filename in os.listdir(videos_dir):
            file_path = os.path.join(videos_dir, filename)
            if os.path.isfile(file_path):
                files.append({
                    "name": filename,
                    "type": "vid",
                    "last_modified": os.path.getmtime(file_path),
                    "size": os.path.getsize(file_path),
                    "download_url": f"/download/videos/{filename}"
                })

    # Return file data as JSON
    return jsonify(files)

@app.route("/download/<folder>/<filename>")
def download_file(folder, filename):
    """Download a file from the specified folder."""
    folder_path = os.path.join(STATIC_DIR, folder)
    try:
         if os.path.isfile(os.path.join(folder_path, filename)):
             return send_from_directory(folder_path, filename, as_attachment=True)
         else:
             return jsonify({"error": "File not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(filename='app.log', level=logging.INFO)

    app.run(debug=DEBUG)
