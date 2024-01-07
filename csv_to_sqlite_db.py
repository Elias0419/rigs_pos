import csv
import sqlite3

# Step 1: Read the CSV file and extract the required data
def read_csv(file_name):
    data = []
    with open(file_name, 'r') as file:
        csv_reader = csv.DictReader(file)
        for row in csv_reader:
            data.append((row['Name'], row['Product Code'], row['Price']))
    return data

# Step 2: Create the SQLite database and table, and insert data
def create_db_and_insert_data(data):
    # Create or connect to the SQLite database
    conn = sqlite3.connect('inventory.db')
    cursor = conn.cursor()

    # Create the 'items' table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS items (
            name TEXT,
            barcode TEXT,
            price REAL
        )
    ''')

    # Insert data into the 'items' table
    cursor.executemany('INSERT INTO items (name, barcode, price) VALUES (?, ?, ?)', data)

    # Commit changes and close the connection
    conn.commit()
    conn.close()

# Main execution
file_name = 'inventory.csv'
data = read_csv(file_name)
create_db_and_insert_data(data)
