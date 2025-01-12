import sqlite3

def delete_records():
    try:
        # Connect to the database
        connection = sqlite3.connect("incidents.db")
        cursor = connection.cursor()

        # Delete records with id 4 and 5
        delete_query = "DELETE FROM incidents WHERE id IN (6, 7);"
        cursor.execute(delete_query)

        # Commit the changes
        connection.commit()
        print("Records with id 6 and 7 deleted successfully.")

    except sqlite3.Error as e:
        print(f"Error while deleting records: {e}")
    finally:
        # Close the database connection
        if connection:
            connection.close()

# Call the function
delete_records()
