import sqlite3
from datetime import datetime
import json
import uuid
import os
import logging

logger = logging.getLogger("rigs_pos")


class DatabaseManager:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(DatabaseManager, cls).__new__(cls)
        return cls._instance

    def __init__(self, db_path, ref):
        if not hasattr(self, "_init"):
            self.db_path = db_path
            self.created_new_database = False
            self.ensure_database_exists()
            self.ensure_tables_exist()
            self.app = ref
            self._init = True

    def _get_connection(self):
        return sqlite3.connect(self.db_path)

    def ensure_database_exists(self):
        db_directory = os.path.dirname(self.db_path)
        os.makedirs(db_directory, exist_ok=True)
        if not os.path.exists(self.db_path):
            conn = sqlite3.connect(self.db_path)
            conn.close()
            self.created_new_database = True
            logger.warning(
                "[DatabaseManager] No existing database found. Created a new empty database at %s",
                self.db_path,
            )
        else:
            logger.info("[DatabaseManager] Using existing database at %s", self.db_path)

    def ensure_tables_exist(self):
        self.create_items_table()
        self._ensure_items_schema()
        self.create_order_history_table()
        self.create_modified_orders_table()
        self.create_dist_table()
        self.create_payment_history_table()
        self.create_attendance_log_table()

    def create_payment_history_table(self):
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """CREATE TABLE IF NOT EXISTS payments (
                                timestamp TEXT,
                                session_id TEXT,
                                date TEXT,
                                name TEXT,
                                clock_in TEXT,
                                clock_out TEXT,
                                hours TEXT,
                                minutes TEXT,
                                cash BOOLEAN,
                                dd BOOLEAN,
                                notes TEXT
                            )"""
            )
            conn.commit()
        except sqlite3.Error as e:
            logger.warn(f"[DatabaseManager]:\n{e}")
        finally:
            conn.close()

    def create_attendance_log_table(self):
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """CREATE TABLE IF NOT EXISTS attendance_log (
                    session_id TEXT PRIMARY KEY,
                    name TEXT,
                    clock_in TIME,
                    clock_out TIME
                )"""
            )
            conn.commit()
        except sqlite3.Error as e:
            logger.warn(f"Error creating attendance log table: {e}")
        finally:
            conn.close()

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
                                taxable BOOLEAN DEFAULT TRUE,
                                is_rolling_papers BOOLEAN NOT NULL DEFAULT FALSE,
                                papers_per_pack INTEGER,
                                PRIMARY KEY (barcode, sku),
                                FOREIGN KEY(parent_barcode) REFERENCES items(barcode)
                            )"""
            )
            conn.commit()
        except sqlite3.Error as e:
            logger.warn(f"[DatabaseManager]:\n{e}")
        finally:
            conn.close()

    def _ensure_items_schema(self):
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(items)")
            columns = [row[1] for row in cursor.fetchall()]
            if "is_rolling_papers" not in columns:
                cursor.execute(
                    "ALTER TABLE items ADD COLUMN is_rolling_papers BOOLEAN NOT NULL DEFAULT FALSE"
                )
                conn.commit()
            if "papers_per_pack" not in columns:
                cursor.execute(
                    "ALTER TABLE items ADD COLUMN papers_per_pack INTEGER"
                )
                conn.commit()
        except sqlite3.Error as e:
            logger.warn(f"[DatabaseManager] Failed to ensure items schema:\n{e}")
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
            logger.warn(f"[DatabaseManager]:\n{e}")
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
            logger.warn(f"[DatabaseManager]:\n{e}")
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
            logger.warn(f"[DatabaseManager]:\n{e}")
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
        taxable=True,
        is_rolling_papers=False,
        papers_per_pack=None,
    ):
        item_id = uuid.uuid4()
        self.create_items_table()
        conn = self._get_connection()
        try:
            taxable = bool(taxable)
            is_rolling_papers = bool(is_rolling_papers)
            try:
                papers_per_pack_value = (
                    int(papers_per_pack)
                    if papers_per_pack not in (None, "")
                    else None
                )
            except (TypeError, ValueError):
                papers_per_pack_value = None
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO items (barcode, name, price, cost, sku, category, item_id, parent_barcode, taxable, is_rolling_papers, papers_per_pack) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    barcode,
                    name,
                    price,
                    cost,
                    sku,
                    category,
                    str(item_id),
                    parent_barcode,
                    taxable,
                    is_rolling_papers,
                    papers_per_pack_value,
                ),
            )
            conn.commit()
            item_details = {
                "barcode": barcode,
                "name": name,
                "price": price,
                "cost": cost,
                "sku": sku,
                "category": category,
                "item_id": str(item_id),
                "parent_barcode": parent_barcode,
                "taxable": taxable,
                "is_rolling_papers": is_rolling_papers,
                "papers_per_pack": papers_per_pack_value,
            }
            self.app.utilities.update_barcode_cache(item_details)
        except sqlite3.IntegrityError as e:
            logger.warn(f"[DatabaseManager]:\n{e}")
            conn.close()
            return False
        conn.close()
        return True

    def update_item(
        self,
        item_id,
        barcode,
        name,
        price,
        cost=None,
        sku=None,
        category=None,
        taxable=True,
        is_rolling_papers=False,
        papers_per_pack=None,
    ):
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            update_query = """UPDATE items
                            SET barcode=?, name=?, price=?, cost=?, sku=?, category=?, taxable=?, is_rolling_papers=?, papers_per_pack=?
                            WHERE item_id=?"""
            try:
                papers_per_pack_value = (
                    int(papers_per_pack)
                    if papers_per_pack not in (None, "")
                    else None
                )
            except (TypeError, ValueError):
                papers_per_pack_value = None
            cursor.execute(
                update_query,
                (
                    barcode,
                    name,
                    price,
                    cost,
                    sku,
                    category,
                    bool(taxable),
                    bool(is_rolling_papers),
                    papers_per_pack_value,
                    item_id,
                ),
            )
            if cursor.rowcount == 0:

                return False
            conn.commit()
            item_details = {
                "barcode": barcode,
                "item_id": item_id,
                "name": name,
                "price": price,
                "cost": cost,
                "sku": sku,
                "category": category,
                "taxable": bool(taxable),
                "is_rolling_papers": bool(is_rolling_papers),
                "papers_per_pack": papers_per_pack_value,
            }
            self.app.utilities.update_barcode_cache(item_details)
        except Exception as e:
            logger.warn(f"[DatabaseManager]:\n{e}")
            return False
        finally:
            conn.close()
        return True

    def handle_duplicate_barcodes(self, barcode):

        query = """
                SELECT barcode, name, price, cost, sku, category, item_id, parent_barcode, taxable, is_rolling_papers, papers_per_pack
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
                # print(row)
                item_details = {
                    "barcode": row[0],
                    "name": row[1],
                    "price": row[2],
                    "cost": row[3],
                    "sku": row[4],
                    "category": row[5],
                    "item_id": row[6],
                    "parent_barcode": row[7],
                    "taxable": bool(row[8]),
                    "is_rolling_papers": bool(row[9]),
                    "papers_per_pack": row[10],
                }
                items.append(item_details)

        except sqlite3.Error as e:
            logger.warn(f"Database error: {e}")
        finally:
            conn.close()

        return items

    def get_item_details(self, item_id="", name="", price=0.0, barcode="", dupe=False):
        conn = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            item_details = None
            if dupe:
                query = "SELECT name, price, barcode, cost, sku, category, item_id, parent_barcode, taxable, is_rolling_papers, papers_per_pack FROM items WHERE name = ? AND price = ?"
                cursor.execute(query, (name, price))
                if cursor.rowcount == 0:
                    query = "SELECT name, price, barcode, cost, sku, category, item_id, parent_barcode, taxable, is_rolling_papers, papers_per_pack FROM items WHERE name = ?"
                    cursor.execute(query, (name,))

            elif item_id:
                query = "SELECT name, price, barcode, cost, sku, category, item_id, parent_barcode, taxable, is_rolling_papers, papers_per_pack FROM items WHERE item_id = ?"
                cursor.execute(query, (item_id,))

            elif barcode:
                query = "SELECT name, price, barcode, cost, sku, category, item_id, parent_barcode, taxable, is_rolling_papers, papers_per_pack FROM items WHERE barcode = ?"
                cursor.execute(query, (barcode,))

            elif name and price:
                query = "SELECT name, price, barcode, cost, sku, category, item_id, parent_barcode, taxable, is_rolling_papers, papers_per_pack FROM items WHERE name = ? AND price = ?"
                cursor.execute(query, (name, price))
                if cursor.rowcount == 0:

                    query = "SELECT name, price, barcode, cost, sku, category, item_id, parent_barcode, taxable, is_rolling_papers, papers_per_pack FROM items WHERE name = ?"
                    cursor.execute(query, (name,))

            elif name:
                query = "SELECT name, price, barcode, cost, sku, category, item_id, parent_barcode, taxable, is_rolling_papers, papers_per_pack FROM items WHERE name = ?"
                cursor.execute(query, (name,))

            else:
                return None

            item = cursor.fetchone()

            if item:
                item_details = {
                    "name": item[0],
                    "price": item[1],
                    "barcode": item[2],
                    "cost": item[3],
                    "sku": item[4],
                    "category": item[5],
                    "item_id": item[6],
                    "parent_barcode": item[7],
                    "taxable": bool(item[8]),
                    "is_rolling_papers": bool(item[9]),
                    "papers_per_pack": item[10],
                }

        except Exception as e:
            logger.warn(f"[DatabaseManager]: get_item_details\n {e}")
        finally:
            if conn:
                conn.close()
        return item_details

    def delete_item(self, item_id):
        logger.warn(f"delete\n{item_id}")
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            delete_query = "DELETE FROM items WHERE item_id = ?"
            cursor.execute(delete_query, (item_id,))

            if cursor.rowcount == 0:

                return False

            conn.commit()
            return True
        except sqlite3.Error as e:
            logger.warn(f"[DatabaseManager]:\n{e}")
            return False
        finally:
            conn.close()

    def add_order_history(
        self,
        order_id,
        items,
        total,
        tax,
        discount,
        total_with_tax,
        timestamp,
        payment_method,
        amount_tendered,
        change_given,
    ):

        self.create_order_history_table()
        conn = self._get_connection()

        try:
            cursor = conn.cursor()

            cursor.execute(
                "INSERT INTO order_history (order_id, items, total, tax, discount, total_with_tax, timestamp, payment_method, amount_tendered, change_given) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    order_id,
                    items,
                    total,
                    tax,
                    discount,
                    total_with_tax,
                    timestamp,
                    payment_method,
                    amount_tendered,
                    change_given,
                ),
            )
            conn.commit()
        except sqlite3.Error as e:
            logger.warn(f"[DatabaseManager]:\n{e}")
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
            logger.warn(f"[DatabaseManager]:\n{e}")
            return False
        finally:
            conn.close()
        return True

    def delete_order(self, order_id):
        if self._save_current_order_state(order_id, "deleted"):
            conn = self._get_connection()
            try:
                cursor = conn.cursor()
                cursor.execute(
                    "DELETE FROM order_history WHERE order_id = ?", (order_id,)
                )
                conn.commit()
            except sqlite3.Error as e:
                logger.warn(f"[DatabaseManager]:\n{e}")
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

                cursor.execute(
                    f"UPDATE order_history SET {set_clause} WHERE order_id = ?", values
                )
                conn.commit()
            except sqlite3.Error as e:
                logger.warn(f"[DatabaseManager]:\n{e}")
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
        # print(order_history)
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
        self,
        barcode,
        name,
        price,
        cost=0.0,
        sku=None,
        categories=None,
        is_rolling_papers=False,
        papers_per_pack=None,
    ):
        logger.warn("add to db")
        if barcode and name and price:
            try:
                self.add_item(
                    barcode,
                    name,
                    price,
                    cost,
                    sku,
                    categories,
                    is_rolling_papers=is_rolling_papers,
                    papers_per_pack=papers_per_pack,
                )
                self.app.popup_manager.add_to_db_popup.dismiss()
            except Exception as e:
                logger.warn(f"[DatabaseManager] add_item_to_database:\n{e}")

    def get_all_items(self):
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "SELECT barcode, name, price, cost, sku, category, item_id, parent_barcode, taxable, is_rolling_papers, papers_per_pack FROM items"
            )
            items = cursor.fetchall()
        except sqlite3.Error as e:
            logger.warn(f"[DatabaseManager]:\n{e}")
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
        query = "SELECT * FROM distributor_info"
        cursor.execute(query)
        rows = cursor.fetchall()

        distributors = {
            row["id"]: {
                "name": row["name"],
                "contact_info": row["contact_info"],
                "item_name": row["item_name"],
                "item_id": row["item_id"],
                "price": row["price"],
                "notes": row["notes"],
            }
            for row in rows
        }

        conn.close()
        return distributors

    def close_connection(self):
        conn = self._get_connection()
        if conn:
            conn.close()

    def add_session_to_payment_history(
        self,
        session_id,
        date,
        name,
        clock_in,
        clock_out,
        hours,
        minutes,
        cash,
        dd,
        notes,
    ):
        conn = self._get_connection()
        timestamp = datetime.now()
        try:
            cursor = conn.cursor()

            cursor.execute(
                "INSERT INTO payments (timestamp, session_id, date, name, clock_in, clock_out, hours, minutes, cash, dd, notes) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    timestamp,
                    session_id,
                    date,
                    name,
                    clock_in,
                    clock_out,
                    hours,
                    minutes,
                    cash,
                    dd,
                    notes,
                ),
            )
            conn.commit()
        except sqlite3.Error as e:
            logger.warn(f"[DatabaseManager]:\n{e}")
            return False
        finally:
            conn.close()
        return True

    def get_sessions(self, session_id=None, name=None):
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            if session_id:
                cursor.execute(
                    "SELECT * FROM payments WHERE session_id = ?", (session_id,)
                )
            elif name:
                cursor.execute("SELECT * FROM payments WHERE name = ?", (name,))
            else:
                cursor.execute("SELECT * FROM payments")

            sessions = cursor.fetchall()
            return sessions
        except sqlite3.Error as e:
            logger.warn(f"[DatabaseManager]:\n{e}")
            return None
        finally:
            conn.close()

    def delete_attendance_log_entry(self, session_id):
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM attendance_log WHERE session_id = ?", (session_id,)
            )
            conn.commit()
        except sqlite3.Error as e:
            logger.warn(f"[DatabaseManager]:\n{e}")
        finally:
            conn.close()

    def insert_attendance_log_entry(
        self, name, session_id, clock_in_time, clock_out_time=None
    ):
        if name == "admin":
            logger.warning(
                f"Discarding admin time entry:\nSession ID: {session_id}, Clock-in: {clock_in_time}"
            )
            return
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO attendance_log (name, session_id, clock_in, clock_out)
                VALUES (?, ?, ?, ?)""",
                (name, session_id, clock_in_time, clock_out_time),
            )
            conn.commit()
        except sqlite3.Error as e:
            logger.warn(f"[DatabaseManager]:\n{e}")
        finally:
            conn.close()

    def retrieve_attendence_log_entries(self):  # debug
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM attendance_log")
            results = cursor.fetchall()

            return results
        except sqlite3.Error as e:
            logger.warn(f"[DatabaseManager]:\n{e}")
        finally:
            conn.close()

    def update_attendance_log_entry(self, session_id, clock_out_time):
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """UPDATE attendance_log
                SET clock_out = ?
                WHERE session_id = ?""",
                (clock_out_time, session_id),
            )
            conn.commit()
        except sqlite3.Error as e:
            logger.warn(f"[DatabaseManager]:\n{e}")
        finally:
            conn.close()

