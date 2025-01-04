import sqlite3

# Connect to the database
db_path = "incidents.db"  # Replace with your actual database path
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

try:
    # SQLite supports renaming columns starting from version 3.25.0
    cursor.execute("PRAGMA user_version")
    db_version = cursor.fetchone()[0]
    print(f"SQLite Version: {db_version}")

    # Rename the column 'alerts' to 'alert'
    cursor.execute("ALTER TABLE incidents RENAME COLUMN alerts TO alert")
    print("Column renamed successfully from 'alerts' to 'alert'.")
except sqlite3.OperationalError as e:
    if "syntax error" in str(e).lower():
        print("Your SQLite version does not support column renaming. "
              "Please update to version 3.25.0 or higher.")
    else:
        print(f"An error occurred: {e}")
finally:
    # Commit changes and close the connection
    conn.commit()
    conn.close()
