import sqlite3
class DatabaseManager:
    def __init__(self, db_path):
        self.db_path = db_path
        self.ensure_tables_exist()

    def _get_connection(self):
        print("DEBUG DatabaseManager get_connection")
        return sqlite3.connect(self.db_path)

    def ensure_tables_exist(self):
        self.create_items_table()
        self.create_order_history_table()

    def create_items_table(self):
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute('''CREATE TABLE IF NOT EXISTS items (
                                barcode TEXT PRIMARY KEY,
                                name TEXT,
                                price REAL
                              )''')
            conn.commit()
        except sqlite3.Error as e:
            print(f"Error creating items table: {e}")
        finally:
            conn.close()


    def create_order_history_table(self):
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute('''CREATE TABLE IF NOT EXISTS order_history (
                                order_id TEXT PRIMARY KEY,
                                items TEXT,
                                total REAL,
                                total_with_tax REAL,
                                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                            )''')
            conn.commit()
        except sqlite3.Error as e:
            print(f"Error creating order history table: {e}")
        finally:
            conn.close()

    def add_order_history(self, order_id, items, total_with_tax, total):
        self.create_order_history_table()
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            # Assuming 'items' is a JSON string for simplicity
            cursor.execute('INSERT INTO order_history (order_id, items, total, total_with_tax) VALUES (?, ?, ?, ?)',
                           (order_id, items, total, total_with_tax))
            conn.commit()
        except sqlite3.Error as e:
            print(f"Error adding order history: {e}")
            return False
        finally:
            conn.close()
        return True

    def get_item_details(self, barcode):
        print("DEBUG DatabaseManager get_item_details")

        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT name, price FROM items WHERE barcode = ?', (barcode,))
        item = cursor.fetchone()
        conn.close()
        return item

    def add_item(self, barcode, name, price):
        self.create_items_table()
        print("DEBUG DatabaseManager add_item")

        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute('INSERT INTO items (barcode, name, price) VALUES (?, ?, ?)', (barcode, name, price))
            conn.commit()
        except sqlite3.IntegrityError:
            print(f"Item with barcode {barcode} already exists.")
            conn.close()
            return False
        conn.close()
        return True

    def update_item(self, barcode, updated_info):
        
        pass

    def delete_item(self, barcode):
        
        pass

    def close_connection(self):
        print("DEBUG DatabaseManager close_connection")
        conn = self._get_connection()
        if conn:
            conn.close()


if __name__ == "__main__":
    db_manager = DatabaseManager('my_items_database.db')
    try:
        
        barcode = '123456789012'
        item = db_manager.get_item_details(barcode)
        if item:
            print(f"Item: {item[0]}, Price: {item[1]}")
        else:
            print("Item not found.")
    finally:
        db_manager.close()
