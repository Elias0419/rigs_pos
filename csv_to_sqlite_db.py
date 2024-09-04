import csv
import sqlite3

# test
def read_csv(file_name):
    data = []
    with open(file_name, "r") as file:
        csv_reader = csv.DictReader(file)
        for row in csv_reader:
            parent_barcode = row.get("Parent Barcode")
            category = row.get("Category")
            data.append(
                (
                    row["Name"],
                    row["Product Code"],
                    row["Price"],
                    row["Cost"],
                    row["SKU"],
                    category,
                    parent_barcode,
                )
            )
    return data


def create_db_and_insert_data(data):
    conn = sqlite3.connect("db/inventory.db")
    cursor = conn.cursor()

    cursor.execute(
        """CREATE TABLE IF NOT EXISTS items (
                            barcode TEXT,
                            name TEXT,
                            price REAL,
                            cost REAL,
                            sku TEXT,
                            category TEXT,
                            parent_barcode TEXT,
                            PRIMARY KEY (barcode, name),
                            FOREIGN KEY(parent_barcode) REFERENCES items(barcode)
                            )"""
    )

    cursor.executemany(
        "INSERT INTO items (name, barcode, price, cost, sku, category, parent_barcode) VALUES (?, ?, ?, ?, ?, ?, ?)",
        data,
    )

    conn.commit()
    conn.close()


file_name = "inventory.csv"
data = read_csv(file_name)
create_db_and_insert_data(data)
