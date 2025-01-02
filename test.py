import sqlite3

# Create a connection to the SQLite database (it will be created if it doesn't exist)
connection = sqlite3.connect("incidents.db")

# Create a cursor object to execute SQL commands
cursor = connection.cursor()

# SQL to create the incidents table
create_table_query = """
CREATE TABLE IF NOT EXISTS incidents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot BLOB, -- Stores image data
    gender TEXT NOT NULL, -- Can be 'Male', 'Female', or 'Other'
    geolocation TEXT NOT NULL, -- Format: "latitude,longitude"
    timestamp TEXT NOT NULL, -- Stores date and time
    date TEXT NOT NULL, -- Stores only the date
    video BLOB -- Stores video data
);
"""

# Execute the SQL query to create the table
cursor.execute(create_table_query)

# Commit the changes
connection.commit()

# Example: Insert sample data
# insert_query = """
# INSERT INTO incidents (snapshot, gender, geolocation, timestamp, date, video)
# VALUES (?, ?, ?, ?, ?, ?);
# """

# Sample data (replace with real binary data for snapshot and video)
# snapshot = None  # Replace with binary data of an image
# gender = "Male"
# geolocation = "37.7749,-122.4194"  # Example: San Francisco coordinates
# timestamp = "2025-01-02 10:00:00"
# date = "2025-01-02"
# video = None  # Replace with binary data of a video

# cursor.execute(insert_query, (snapshot, gender, geolocation, timestamp, date, video))

# Commit the changes
connection.commit()

# Close the connection
connection.close()

print("Database setup complete, and sample data inserted.")
