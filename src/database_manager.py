import sqlite3
from datetime import datetime
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
        self.create_order_history_table()
        self.create_order_items_table()
        self.create_modified_orders_table()
        # self.create_dist_table()
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

    def create_order_items_table(self):
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS order_items (
                    id               INTEGER PRIMARY KEY AUTOINCREMENT,
                    order_id         TEXT NOT NULL,
                    item_id          TEXT,
                    barcode          TEXT,
                    name             TEXT NOT NULL,
                    category         TEXT,
                    qty              REAL NOT NULL,
                    unit_price       REAL NOT NULL,
                    line_subtotal    REAL NOT NULL,
                    unit_cost        REAL,
                    line_cost        REAL,
                    taxable          INTEGER,
                    is_rolling_papers INTEGER,
                    papers_per_pack  INTEGER,
                    order_timestamp  TEXT,
                    is_custom        INTEGER NOT NULL DEFAULT 0,
                    FOREIGN KEY(order_id) REFERENCES order_history(order_id)
                )
                """
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_order_items_order_id ON order_items(order_id)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_order_items_name ON order_items(name)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_order_items_category ON order_items(category)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_order_items_timestamp ON order_items(order_timestamp)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_order_items_is_custom ON order_items(is_custom)"
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

        if not cost:
            import inspect
            stack = inspect.stack()
            self.app.popup_manager.DEBUG_empty_cost(stack)
            return False

        # replace ean barcodes with upc a
        if len(str(barcode)) == 13:
            ean_barcode = barcode
            barcode = self.app.utilities.replace_ean()

        conn = self._get_connection()
        try:
            taxable = bool(taxable)
            is_rolling_papers = bool(is_rolling_papers)
            try:
                papers_per_pack_value = (
                    int(papers_per_pack) if papers_per_pack not in (None, "") else None
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
                    int(papers_per_pack) if papers_per_pack not in (None, "") else None
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

    def get_item_details(self, *, item_id: str = "", barcode: str = ""):

        conn = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            sql = """
                SELECT
                    name,
                    price,
                    barcode,
                    cost,
                    sku,
                    category,
                    item_id,
                    parent_barcode,
                    taxable,
                    is_rolling_papers,
                    papers_per_pack
                FROM items
                WHERE {where_clause}
                LIMIT 1
            """

            if item_id and str(item_id).strip():
                cursor.execute(sql.format(where_clause="item_id = ?"), (str(item_id).strip(),))
            elif barcode and str(barcode).strip():
                cursor.execute(sql.format(where_clause="barcode = ?"), (str(barcode).strip(),))
            else:
                return None

            row = cursor.fetchone()
            if not row:
                return None

            return {
                "name": row[0],
                "price": row[1],
                "barcode": row[2],
                "cost": row[3],
                "sku": row[4],
                "category": row[5],
                "item_id": row[6],
                "parent_barcode": row[7],
                "taxable": int(row[8]) if row[8] is not None else 1,
                "is_rolling_papers": int(row[9]) if row[9] is not None else 0,
                "papers_per_pack": row[10],
            }

        except Exception as e:
            logger.warning(f"[DatabaseManager]: get_item_details\n{e}")
            return None
        finally:
            if conn:
                conn.close()


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
        total,
        tax,
        discount,
        total_with_tax,
        timestamp,
        payment_method,
        amount_tendered,
        change_given,
    ):
        conn = self._get_connection()

        try:
            cursor = conn.cursor()

            cursor.execute(
                "INSERT INTO order_history (order_id, items, total, tax, discount, total_with_tax, timestamp, payment_method, amount_tendered, change_given) VALUES (?, NULL, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    order_id,
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
            logger.warn(f"[DatabaseManager]:add_order_history\n{e}")
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

    def _normalize_items_object_to_list(self, items_obj):
        if isinstance(items_obj, list):
            return items_obj
        if isinstance(items_obj, dict):
            items_list = []
            for item_name, item_details in items_obj.items():
                if isinstance(item_details, dict):
                    item = {"name": item_name}
                    item.update(item_details)
                    items_list.append(item)
                else:
                    raise TypeError(
                        f"Expected dict for item details in items dict, got {type(item_details)}"
                    )
            return items_list
        raise TypeError(
            f"Expected list or dict for items object, got {type(items_obj)}"
        )

    def _insert_order_items_from_list(self, order_id, items_list, order_timestamp):
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            insert_sql = """
                INSERT INTO order_items (
                    order_id,
                    item_id,
                    barcode,
                    name,
                    category,
                    qty,
                    unit_price,
                    line_subtotal,
                    unit_cost,
                    line_cost,
                    taxable,
                    is_rolling_papers,
                    papers_per_pack,
                    order_timestamp
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
            for item in items_list:
                if not isinstance(item, dict):
                    raise TypeError(
                        f"Expected dict item when inserting order_items, got {type(item)}"
                    )

                name = item.get("name")
                if not name:
                    raise ValueError(
                        f"Missing name in item when inserting order_items: {item}"
                    )

                if "quantity" in item:
                    qty = float(item["quantity"])
                elif "qty" in item:
                    qty = float(item["qty"])
                else:
                    raise KeyError(
                        f"Missing quantity/qty in item when inserting order_items: {item}"
                    )

                if "price" in item:
                    unit_price = float(item["price"])
                elif "unit_price" in item:
                    unit_price = float(item["unit_price"])
                else:
                    raise KeyError(
                        f"Missing price/unit_price in item when inserting order_items: {item}"
                    )

                line_subtotal = qty * unit_price

                unit_cost = item.get("cost")
                line_cost = None
                if unit_cost is not None:
                    unit_cost = float(unit_cost)
                    line_cost = qty * unit_cost

                taxable = item.get("taxable")
                if taxable is not None:
                    taxable = int(bool(taxable))

                is_rolling = item.get("is_rolling_papers")
                if is_rolling is not None:
                    is_rolling = int(bool(is_rolling))

                papers_per_pack = item.get("papers_per_pack")

                cursor.execute(
                    insert_sql,
                    (
                        order_id,
                        item.get("item_id"),
                        item.get("barcode"),
                        name,
                        item.get("category"),
                        qty,
                        unit_price,
                        line_subtotal,
                        unit_cost,
                        line_cost,
                        taxable,
                        is_rolling,
                        papers_per_pack,
                        order_timestamp,
                    ),
                )

            conn.commit()
        finally:
            conn.close()

    def _rewrite_order_items_for_order(self, order_id, items_obj):
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM order_items WHERE order_id = ?", (order_id,))
            conn.commit()
        finally:
            conn.close()

        items_list = self._normalize_items_object_to_list(items_obj)

        conn2 = self._get_connection()
        try:
            cursor2 = conn2.cursor()
            cursor2.execute(
                "SELECT timestamp FROM order_history WHERE order_id = ?", (order_id,)
            )
            row = cursor2.fetchone()
            if row is None:
                raise ValueError(
                    f"Order {order_id} not found in order_history when rewriting order_items"
                )
            order_timestamp = row[0]
        finally:
            conn2.close()

        self._insert_order_items_from_list(order_id, items_list, order_timestamp)

    def update_order_items(self, order_id, items_obj):
        self._rewrite_order_items_for_order(order_id, items_obj)
        return True

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
            """
            SELECT
                oh.order_id,
                COALESCE(item_summary.item_names, '') AS item_names,
                oh.total,
                oh.tax,
                oh.discount,
                oh.total_with_tax,
                oh.timestamp,
                oh.payment_method,
                oh.amount_tendered,
                oh.change_given
            FROM order_history oh
            LEFT JOIN (
                SELECT order_id, GROUP_CONCAT(name, ', ') AS item_names
                FROM order_items
                GROUP BY order_id
            ) AS item_summary ON oh.order_id = item_summary.order_id
            """
        )
        order_history = cursor.fetchall()
        conn.close()
        return order_history

    def get_order_items(self, order_id):
        conn = self._get_connection()
        conn.row_factory = sqlite3.Row
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT
                    id,
                    order_id,
                    item_id,
                    barcode,
                    name,
                    category,
                    qty,
                    unit_price,
                    line_subtotal,
                    unit_cost,
                    line_cost,
                    taxable,
                    is_rolling_papers,
                    papers_per_pack,
                    order_timestamp
                FROM order_items
                WHERE order_id = ?
                ORDER BY id
                """,
                (order_id,),
            )

            rows = cursor.fetchall()
            return [
                {
                    "id": row["id"],
                    "order_id": row["order_id"],
                    "item_id": row["item_id"],
                    "barcode": row["barcode"],
                    "name": row["name"],
                    "category": row["category"],
                    "qty": row["qty"],
                    "unit_price": row["unit_price"],
                    "line_subtotal": row["line_subtotal"],
                    "unit_cost": row["unit_cost"],
                    "line_cost": row["line_cost"],
                    "taxable": row["taxable"],
                    "is_rolling_papers": row["is_rolling_papers"],
                    "papers_per_pack": row["papers_per_pack"],
                    "order_timestamp": row["order_timestamp"],
                }
                for row in rows
            ]
        finally:
            conn.close()


    def _maybe_bool(self, value):
        if value is None:
            return None
        return bool(value)



    def send_order_to_history_database(self, order_details):
        tax = order_details.total_with_tax - order_details.total
        timestamp = datetime.now()

        items_for_db = [
            item_details.to_dict()
            for item_details in order_details.items.values()
        ]

        success = self.add_order_history(
            order_details.order_id,
            order_details.total,
            tax,
            order_details.total_discount,
            order_details.total_with_tax,
            timestamp,
            order_details.payment_method,
            order_details.amount_tendered,
            order_details.change_given,
        )

        if not success:
            logger.error(
                f"[DatabaseManager] send_order_to_history_database failed to insert order_history for order_id={order_details['order_id']}"
            )
            return

        self._insert_order_items_from_list(
            order_details.order_id, items_for_db, timestamp
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


## Deprecated

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

