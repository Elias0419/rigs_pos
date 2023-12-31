import sqlite3
class DatabaseManager:
    def __init__(self, db_path):
        self.db_path = db_path
        #self.conn = None

    def _get_connection(self):
        print("DEBUG DatabaseManager get_conncetion")

        return sqlite3.connect(self.db_path)

    def get_item_details(self, barcode):
        print("DEBUG DatabaseManager get_item_details")

        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT name, price FROM items WHERE barcode = ?', (barcode,))
        item = cursor.fetchone()
        conn.close()
        return item

    def add_item(self, barcode, name, price):
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
