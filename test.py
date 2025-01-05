import sqlite3

# Connect to the database (update 'your_database.db' to your actual database file)
conn = sqlite3.connect('incidents.db')
cursor = conn.cursor()

try:
    # SQL query to delete records with id 4 and 5
    query = "DELETE FROM incidents WHERE id IN (4, 5)"
    cursor.execute(query)
    
    # Commit the transaction
    conn.commit()
    print(f"Records with id 4 and 5 deleted successfully.")
except sqlite3.Error as e:
    print(f"An error occurred: {e}")
finally:
    # Close the connection
    conn.close()
