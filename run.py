import os
import time
import math
import cv2
import cvzone
from flask import Flask, render_template, Response, jsonify,url_for,send_from_directory
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





# def get_files_from_static_subfolders(base_folder="static"):
#     """
#     Retrieve files from 'screenshots' and 'videos' subfolders with their metadata.

#     Args:
#         base_folder (str): Path to the static folder containing subfolders.

#     Returns:
#         list: A list of dictionaries containing file metadata.
#     """
#     subfolders = {
#         "screenshots": "img",  # Files in 'screenshots' are images
#         "videos": "vid"        # Files in 'videos' are videos
#     }
#     files = []

#     for subfolder, file_type in subfolders.items():
#         folder_path = os.path.join(base_folder, subfolder)
#         if not os.path.exists(folder_path):
#             continue  # Skip if the subfolder doesn't exist

#         for filename in os.listdir(folder_path):
#             file_path = os.path.join(folder_path, filename)
#             if os.path.isfile(file_path):  # Ensure it's a file, not a directory
#                 file_info = {
#                     "name": filename,
#                     "type": file_type,
#                     "last_modified": datetime.fromtimestamp(os.path.getmtime(file_path)).strftime('%b %d, %Y'),
#                     "size": f"{os.path.getsize(file_path) / 1024:.2f} KB",  # File size in KB
#                     "download_url": url_for("download_file", folder=subfolder, filename=filename),
#                 }
#                 files.append(file_info)
#     return files

# @app.route("/")
# def video_storage():
#     files = get_files_from_static_subfolders("static")  # Specify the base folder
#     return render_template("video-record.html", files=files)

# @app.route("/download/<folder>/<filename>")
# def download_file(folder, filename):
#     folder_path = os.path.join("static", folder)
#     return send_from_directory(folder_path, filename, as_attachment=True)

# def get_incident_videos():
#     # Connect to the SQLite database
#     conn = sqlite3.connect('incidents.db')  # Update with the actual path to your database
#     cursor = conn.cursor()
    
#     # Fetch video URLs and gender from the `incidents` table
#     query2 = "SELECT video, gender FROM incidents"
#     cursor.execute(query2)
#     data = cursor.fetchall()
#     conn.close()
    
#     # Format the data as a list of dictionaries
#     return [{'video': row[0], 'gender': row[1]} for row in data]

# @app.route('/videos')
# def display_videos():
#     files = get_incident_videos()
#     return render_template('video-record.html', files=files)

@app.route('/video-records')
def video_records():
    try:
        connection = sqlite3.connect("incidents.db")
        cursor = connection.cursor()
        cursor.execute("SELECT id, gender, video FROM incidents")
        records = cursor.fetchall()
        connection.close()

        videos = []
        for record in records:
            video_id, gender, video_data = record
            # Assuming video is stored as binary data, create a link to the video
            # video_url = url_for('static', filename=f'videos/video_{video_id}.mp4')
            # videos.append({
            #     'gender': gender,
            #     'video_url': video_url
            # })

        return render_template('video-record.html', videos=videos)

    except Exception as e:
        app.logger.error(f"Error fetching video records: {e}")
        return render_template('video-record.html', videos=[])



if __name__ == "__main__":
    # Configure logging
    # logging.basicConfig(filename='app.log', level=logging.INFO)

    app.run(debug=True)
