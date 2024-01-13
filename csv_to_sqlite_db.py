import csv
import sqlite3


def read_csv(file_name):
    data = []
    with open(file_name, "r") as file:
        csv_reader = csv.DictReader(file)
        for row in csv_reader:
            data.append((row["Name"], row["Product Code"], row["Price"], row["Cost"], row["SKU"]))
    return data


def create_db_and_insert_data(data):
    conn = sqlite3.connect("inventory.db")
    cursor = conn.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS items (
            name TEXT,
            barcode TEXT,
            price REAL,
            cost REAL,
            sku TEXT

        )
    """
    )

    cursor.executemany(
        "INSERT INTO items (name, barcode, price, cost, sku) VALUES (?, ?, ?, ?, ?)", data
    )

    conn.commit()
    conn.close()


file_name = "inventory.csv"
data = read_csv(file_name)
create_db_and_insert_data(data)
