import sqlite3


class DatabaseManager:
    def __init__(self, db_path):
        self.db_path = db_path
        self.ensure_tables_exist()

    def _get_connection(self):
        return sqlite3.connect(self.db_path)

    def ensure_tables_exist(self):
        self.create_items_table()
        self.create_order_history_table()

    def create_items_table(self):
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """CREATE TABLE IF NOT EXISTS items (
                                barcode TEXT PRIMARY KEY,
                                name TEXT,
                                price REAL,
                                cost REAL,
                                sku TEXT
                              )"""
            )
            conn.commit()
        except sqlite3.Error as e:
            print(e)
        finally:
            conn.close()

    def create_order_history_table(self):
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """CREATE TABLE IF NOT EXISTS order_history (
                                order_id TEXT PRIMARY KEY,
                                items TEXT,
                                total REAL,
                                tax REAL,
                                discount REAL,
                                total_with_tax REAL,
                                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                            )"""
            )
            conn.commit()
        except sqlite3.Error as e:
            print(e)
        finally:
            conn.close()

    def add_item(self, barcode, name, price, cost=None, sku=None):
        self.create_items_table()

        cost = cost if cost is not None else None
        sku = sku if sku is not None else None

        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO items (barcode, name, price, cost, sku) VALUES (?, ?, ?, ?, ?)",
                (barcode, name, price, cost, sku),
            )

            conn.commit()
        except sqlite3.IntegrityError as e:
            print(e)
            conn.close()
            return False
        conn.close()
        return True

    def add_order_history(self, order_id, items, total, tax, discount, total_with_tax, timestamp):
        self.create_order_history_table()
        conn = self._get_connection()
        try:
            cursor = conn.cursor()

            cursor.execute(
                "INSERT INTO order_history (order_id, items, total, tax, discount, total_with_tax, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (order_id, items, total, tax, discount, total_with_tax, timestamp),
            )
            conn.commit()
        except sqlite3.Error as e:
            print(e)
            return False
        finally:
            conn.close()
        return True

    def get_order_history(self):
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT order_id, items, total, tax, total_with_tax, timestamp FROM order_history"
        )
        order_history = cursor.fetchall()
        conn.close()
        return order_history

    def get_item_details(self, barcode):
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT name, price FROM items WHERE barcode = ?", (barcode,))
        item = cursor.fetchone()
        conn.close()
        return item

    def get_all_items(self):
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT barcode, name, price, cost, sku FROM items")
            items = cursor.fetchall()
        except sqlite3.Error as e:
            print(e)
            items = []
        finally:
            conn.close()

        return items

    def barcode_exists(self, barcode):
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM items WHERE barcode = ?", (barcode,))
        exists = cursor.fetchone() is not None
        conn.close()
        return exists

    def update_item(self, barcode, name, price, cost=None, sku=None):
        cost = cost if cost is not None else None
        sku = sku if sku is not None else None
        print("DEBUG DatabaseManager update_item", barcode, name, price, cost, sku)
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE items SET name=?, price=?, cost=?, sku=? WHERE barcode=?",
                (name, price, cost, sku, barcode),
            )
            if cursor.rowcount == 0:
                print("rowcount1")
                cursor.execute(
                    "UPDATE items SET barcode=?, price=?, cost=?, sku=? WHERE name=?",
                    (barcode, price, cost, sku, name),
                )
                if cursor.rowcount == 0:
                    print("rowcount2")
                    return False

            conn.commit()
        except Exception as e:
            print(e)
            return False
        finally:
            conn.close()

        return True

    def delete_item(self, barcode):
        pass

    def close_connection(self):
        conn = self._get_connection()
        if conn:
            conn.close()
