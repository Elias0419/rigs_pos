import sqlite3
from datetime import datetime
import json
import uuid

class DatabaseManager:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(DatabaseManager, cls).__new__(cls)
        return cls._instance

    def __init__(self, db_path, ref):
        if not hasattr(self, "_init"):
            self.db_path = db_path
            self.ensure_tables_exist()
            self.app = ref
            self._init = True

    def _get_connection(self):
        return sqlite3.connect(self.db_path)

    def ensure_tables_exist(self):
        self.create_items_table()
        self.create_order_history_table()
        self.create_modified_orders_table()
        self.create_dist_table()


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
                                item_id TEXT,
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

    def create_modified_orders_table(self):
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """CREATE TABLE IF NOT EXISTS modified_orders (
                                order_id TEXT,
                                items TEXT,
                                total REAL,
                                tax REAL,
                                discount REAL,
                                total_with_tax REAL,
                                payment_method TEXT,
                                amount_tendered REAL,
                                change_given REAL,
                                modification_type TEXT, -- 'deleted' or 'modified'
                                timestamp TEXT
                            )"""
            )
            conn.commit()
        except sqlite3.Error as e:
            print(e)
        finally:
            conn.close()



    def create_dist_table(self):
            conn = self._get_connection()
            try:
                cursor = conn.cursor()
                cursor.execute(
                    """CREATE TABLE IF NOT EXISTS distributor_info (
                                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                                    name TEXT NOT NULL,
                                    contact_info TEXT,
                                    item_name TEXT,
                                    item_id TEXT,
                                    price REAL,
                                    notes TEXT,
                                    FOREIGN KEY(item_id) REFERENCES items(item_id)
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
        # Generate a new UUID for the item
        item_id = uuid.uuid4()

        print("db add_item", "barcode", barcode, "name", name, "price", price, "cost", cost, "sku", sku, "category", category, "item_id", item_id)
        self.create_items_table()

        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO items (barcode, name, price, cost, sku, category, item_id, parent_barcode) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (barcode, name, price, cost, sku, category, str(item_id), parent_barcode),
            )
            conn.commit()
            item_details = {
                'barcode': barcode,
                'name': name,
                'price': price,
                'cost': cost,
                'sku': sku,
                'category': category,
                'item_id': str(item_id),
                'parent_barcode': parent_barcode
            }
            self.app.utilities.update_barcode_cache(item_details)
        except sqlite3.IntegrityError as e:
            print(e)
            conn.close()
            return False
        conn.close()

        return True

    def update_item(self, item_id, barcode, name, price, cost=None, sku=None, category=None):
        print("db update_item", "barcode", barcode, "item_id", item_id, "name", name, "price", price, "cost", cost, "sku", sku, "category", category)
        conn = self._get_connection()
        try:
            cursor = conn.cursor()

            update_query = """UPDATE items
                            SET barcode=?, name=?, price=?, cost=?, sku=?, category=?
                            WHERE item_id=?"""
            cursor.execute(update_query, (barcode, name, price, cost, sku, category, item_id))

            if cursor.rowcount == 0:
                print("No item found with UUID:", item_id)
                return False

            conn.commit()
            item_details = {
                'item_id': item_id,
                'name': name,
                'price': price,
                'cost': cost,
                'sku': sku,
                'category': category,
            }
            self.app.utilities.update_barcode_cache(item_details)
        except Exception as e:
            print(e)
            return False
        finally:
            conn.close()
        return True



    def handle_duplicate_barcodes(self, barcode):

        query = """
                SELECT barcode, name, price, cost, sku, category, item_id, parent_barcode
                FROM items
                WHERE barcode = ?
               """
        items = []

        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(query, (barcode,))
            rows = cursor.fetchall()


            for row in rows:
                print(row)
                item_details = {
                    'barcode': row[0],
                    'name': row[1],
                    'price': row[2],
                    'cost': row[3],
                    'sku': row[4],
                    'category': row[5],
                    'item_id': row[6],
                    'parent_barcode': row[7]
                }
                items.append(item_details)

        except sqlite3.Error as e:
            print(f"Database error: {e}")
        finally:
            conn.close()

        return items

    def get_item_details(self, item_id="", name="", price=0.0, barcode="", dupe=False):
        print(f"called get with\nbarcode {barcode}\nname {name}\nitem_id {item_id}")
        conn = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            item_details = None
            if dupe:
                # print(f"TEST dupe\nname {name}\nprice {price}")
                query = "SELECT name, price, barcode, cost, sku, category, item_id, parent_barcode FROM items WHERE name = ? AND price = ?"
                cursor.execute(query, (name, price))
                if cursor.rowcount == 0:
                    # print(f"TEST2 dupe\nname {name}\nprice {price}")
                    query = "SELECT name, price, barcode, cost, sku, category, item_id, parent_barcode FROM items WHERE name = ?"
                    cursor.execute(query, (name,))

            elif item_id:
                # print("if item_id")
                query = "SELECT name, price, barcode, cost, sku, category, item_id, parent_barcode FROM items WHERE item_id = ?"
                cursor.execute(query, (item_id,))
            elif barcode:
                # print("elif barcode:")
                query = "SELECT name, price, barcode, cost, sku, category, item_id, parent_barcode FROM items WHERE barcode = ?"
                cursor.execute(query, (barcode,))

            elif name and price:
                # print("elif name and price:")
                # print("name and price")
                query = "SELECT name, price, barcode, cost, sku, category, item_id, parent_barcode FROM items WHERE name = ? AND price = ?"
                cursor.execute(query, (name, price))
                if cursor.rowcount == 0:

                    query = "SELECT name, price, barcode, cost, sku, category, item_id, parent_barcode FROM items WHERE name = ?"
                    cursor.execute(query, (name,))

            elif name:
                # print("elif name")
                query = "SELECT name, price, barcode, cost, sku, category, item_id, parent_barcode FROM items WHERE name = ?"
                cursor.execute(query, (name,))

            else:
                # print("else")
                # print("[DatabaseManager]: get_item_details requires either item_id, barcode, or both name and price.")
                return None

            item = cursor.fetchone()

            if item:
                item_details = {
                    'name': item[0],
                    'price': item[1],
                    'barcode': item[2],
                    'cost': item[3],
                    'sku': item[4],
                    'category': item[5],
                    'item_id': item[6],
                }

                # if item_id or barcode: # TODO
                #     item_details['parent_barcode'] = item[6]
                # else:
                #     item_details['item_id'] = item[6]
                #     item_details['parent_barcode'] = item[7]

        except Exception as e:
            print(f"[DatabaseManager]: get_item_details\n {e}")
        finally:
            if conn:
                conn.close()

        return item_details

    def delete_item(self, item_id):
        print(f"delete\n{item_id}")
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            delete_query = "DELETE FROM items WHERE item_id = ?"
            cursor.execute(delete_query, (item_id,))

            # If no rows were affected, the item_id does not exist
            if cursor.rowcount == 0:
                print(f"No item found with item_id: {item_id}")
                return False

            conn.commit()
            return True
        except sqlite3.Error as e:
            print(f"Database error during item deletion: {e}")
            return False
        finally:
            conn.close()




    # def debug_print(self, order_id, items, total, tax, discount, total_with_tax, timestamp, payment_method, amount_tendered, change_given):
    #     variables = locals()  # Captures all the local variables in the function as a dictionary
    #
    #     for var_name, value in variables.items():
    #         print(f"{var_name}: Value = {value}, Type = {type(value)}")

    def add_order_history(self, order_id, items, total, tax, discount, total_with_tax, timestamp, payment_method, amount_tendered, change_given):
        # self.debug_print(order_id, items, total, tax, discount, total_with_tax, timestamp, payment_method, amount_tendered, change_given)
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

    def _save_current_order_state(self, order_id, modification_type):
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO modified_orders (order_id, items, total, tax, discount, total_with_tax, timestamp, payment_method, amount_tendered, change_given, modification_type, timestamp) "
                "SELECT order_id, items, total, tax, discount, total_with_tax, timestamp, payment_method, amount_tendered, change_given, ?, CURRENT_TIMESTAMP "
                "FROM order_history WHERE order_id = ?",
                (modification_type, order_id),
            )
            conn.commit()
        except sqlite3.Error as e:
            print(e)
            return False
        finally:
            conn.close()
        return True

    def delete_order(self, order_id):
        print("[DatabaseManager]: Delete order", order_id)
        if self._save_current_order_state(order_id, "deleted"):
            conn = self._get_connection()
            try:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM order_history WHERE order_id = ?", (order_id,))
                conn.commit()
            except sqlite3.Error as e:
                print(e)
                return False
            finally:
                conn.close()
            return True
        else:
            return False

    def modify_order(self, order_id, **kwargs):
        if self._save_current_order_state(order_id, "modified"):
            conn = self._get_connection()
            try:
                cursor = conn.cursor()

                if "items" in kwargs and isinstance(kwargs["items"], (list, dict)):

                    kwargs["items"] = json.dumps(kwargs["items"], ensure_ascii=False)

                set_clause = ", ".join([f"{key} = ?" for key in kwargs.keys()])
                values = list(kwargs.values())
                values.append(order_id)

                cursor.execute(f"UPDATE order_history SET {set_clause} WHERE order_id = ?", values)
                conn.commit()
            except sqlite3.Error as e:
                print(e)
                return False
            finally:
                conn.close()
            return True
        else:
            return False

    def get_order_by_id(self, order_id):

        conn = self._get_connection()
        cursor = conn.cursor()


        query = """
        SELECT
            order_id,
            items,
            total,
            tax,
            discount,
            total_with_tax,
            timestamp,
            payment_method,
            amount_tendered,
            change_given
        FROM
            order_history
        WHERE
            order_id = ?
        """


        cursor.execute(query, (order_id,))


        order = cursor.fetchone()

        conn.close()


        return order


    def get_order_history(self):
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT order_id, items, total, tax, discount, total_with_tax, timestamp, payment_method, amount_tendered, change_given FROM order_history"
        )
        order_history = cursor.fetchall()
        #print(order_history)
        conn.close()
        return order_history

    def send_order_to_history_database(self, order_details, order_manager, db_manager):
        tax = order_details["total_with_tax"] - order_details["total"]
        timestamp = datetime.now()

        items_for_db = [
            {**{"name": item_name}, **item_details}
            for item_name, item_details in order_details["items"].items()
        ]

        self.add_order_history(
            order_details["order_id"],
            json.dumps(items_for_db),
            order_details["total"],
            tax,
            order_details["discount"],
            order_details["total_with_tax"],
            timestamp,
            order_details["payment_method"],
            order_details["amount_tendered"],
            order_details["change_given"],
        )

    def add_item_to_database(
        self, barcode, name, price, cost=0.0, sku=None, categories=None
    ):
        if barcode and name and price:
            try:
                self.add_item(barcode, name, price, cost, sku, categories)
                self.app.popup_manager.add_to_db_popup.dismiss()
            except Exception as e:
                print(e)



    def get_all_items(self):
       # print(f"db manager get all\n\n\n\n")
        conn = self._get_connection()
        #print(f"{conn}\n\n\n\n")
        cursor = conn.cursor()
        try:
            cursor.execute(
                "SELECT barcode, name, price, cost, sku, category, item_id, parent_barcode FROM items"
            )
            items = cursor.fetchall()
          #  print(len(items))
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

    def get_all_distrib(self):

        conn = self._get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        query = 'SELECT * FROM distributor_info'
        cursor.execute(query)
        rows = cursor.fetchall()


        distributors = {row['id']: {'name': row['name'], 'contact_info': row['contact_info'], 'item_name': row['item_name'], 'item_id': row['item_id'], 'price': row['price'], 'notes': row['notes']} for row in rows}

        conn.close()
        return distributors



    def close_connection(self):
        conn = self._get_connection()
        if conn:
            conn.close()
if __name__=="__main__":
    db=DatabaseManager("inventory.db", None)
    res=db.get_all_items()
    print(res)
