import sqlite3


class DatabaseManager:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(DatabaseManager, cls).__new__(cls)
        return cls._instance

    def __init__(self, db_path):
        if not hasattr(self, "_init"):
            self.db_path = db_path
            self.ensure_tables_exist()
            self._init = True

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
                                barcode TEXT,
                                name TEXT,
                                price REAL,
                                cost REAL,
                                sku TEXT,
                                category TEXT,
                                parent_barcode TEXT,
                                PRIMARY KEY (barcode, sku),
                                FOREIGN KEY(parent_barcode) REFERENCES items(barcode)
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
                                payment_method TEXT,
                                amount_tendered REAL,
                                change_given REAL,
                                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                            )"""
            )
            conn.commit()
        except sqlite3.Error as e:
            print(e)
        finally:
            conn.close()

    def add_item(
        self,
        barcode,
        name,
        price,
        cost=None,
        sku=None,
        category=None,
        parent_barcode=None,
    ):
        print("db add_item", "barcode",barcode,"name",name,"price",price,"cost",cost,"sku",sku,"category",category)
        self.create_items_table()



        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO items (barcode, name, price, cost, sku, category, parent_barcode) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (barcode, name, price, cost, sku, category, parent_barcode),
            )
            conn.commit()
        except sqlite3.IntegrityError as e:
            print(e)
            conn.close()
            return False
        conn.close()
        return True

    def add_order_history(self, order_id, items, total, tax, discount, total_with_tax, timestamp, payment_method, amount_tendered, change_given):
        self.create_order_history_table()
        conn = self._get_connection()

        try:
            cursor = conn.cursor()

            cursor.execute(
            "INSERT INTO order_history (order_id, items, total, tax, discount, total_with_tax, timestamp, payment_method, amount_tendered, change_given) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (order_id, items, total, tax, discount, total_with_tax, timestamp, payment_method, amount_tendered, change_given),
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
            "SELECT order_id, items, total, tax, discount, total_with_tax, timestamp, payment_method, amount_tendered, change_given FROM order_history"
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
        print("db manager get all")
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "SELECT barcode, name, price, cost, sku, category, parent_barcode FROM items"
            )
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

    def update_item(self, barcode, name, price, cost=None, sku=None, category=None):
        conn = self._get_connection()
        try:
            cursor = conn.cursor()

            update_query = """UPDATE items
                            SET name=?, price=?, cost=?, sku=?, category=?
                            WHERE barcode=? AND (sku=? OR ? IS NULL AND sku IS NULL)"""
            cursor.execute(update_query, (name, price, cost, sku, category, barcode, sku, sku))

            if cursor.rowcount == 0:
                print("No item found with barcode and SKU:", barcode, sku)
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
