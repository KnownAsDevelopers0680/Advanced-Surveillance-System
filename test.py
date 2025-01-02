import sqlite3

# Connect to the SQLite database
connection = sqlite3.connect("incidents.db")
cursor = connection.cursor()

# SQL query to delete records where id is 1, 2, or 3
delete_query = """
DELETE FROM incidents
WHERE id IN (1, 2, 3);
"""

# Execute the delete query
cursor.execute(delete_query)

# Commit the changes and close the connection
connection.commit()
connection.close()

print("Records with id 1, 2, and 3 have been deleted.")
