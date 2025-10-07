from datetime import datetime, timedelta
import csv, json

from rapidfuzz import process, fuzz

from kivy.app import App
from kivy.clock import Clock
from kivy.graphics import Color, Line
from kivy.metrics import dp
from kivy.properties import StringProperty, ObjectProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.recycleview import RecycleView
from kivy.uix.recycleboxlayout import RecycleBoxLayout
from kivy.uix.recycleview.views import RecycleDataViewBehavior
from kivy.uix.textinput import TextInput
from kivy.factory import Factory

from kivymd.uix.button import MDRaisedButton, MDFlatButton
from kivymd.uix.label import MDLabel
from kivymd.uix.card import MDCard
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.pickers import MDDatePicker


from database_manager import DatabaseManager
import logging

logger = logging.getLogger("rigs_pos")


class MarkupLabel(MDLabel):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.markup = True


def add_bottom_divider(widget, rgba=(0.5, 0.5, 0.5, 1), width=1):
    with widget.canvas.after:
        Color(*rgba)
        widget._divider = Line(
            points=[widget.x, widget.y, widget.right, widget.y], width=width
        )
    widget.bind(
        pos=lambda *_: _update_divider(widget), size=lambda *_: _update_divider(widget)
    )


def _update_divider(widget):
    if hasattr(widget, "_divider") and widget._divider is not None:
        widget._divider.points = [widget.x, widget.y, widget.right, widget.y]


def _left_label(**kw):
    lbl = Label(halign="left", **kw)
    lbl.bind(size=lambda *_: setattr(lbl, "text_size", lbl.size))
    return lbl


class HistoryRow(RecycleDataViewBehavior, BoxLayout):
    order_id = StringProperty(allownone=True)
    items = StringProperty(allownone=True)
    total = StringProperty(allownone=True)
    tax = StringProperty(allownone=True)
    total_with_tax = StringProperty(allownone=True)
    timestamp = StringProperty(allownone=True)
    payment_method = StringProperty(allownone=True)
    amount_tendered = StringProperty(allownone=True)
    change_given = StringProperty(allownone=True)
    history_view = ObjectProperty(allownone=True)

    def __init__(self, **kwargs):
        super().__init__(orientation="horizontal", spacing=5, padding=5, **kwargs)

        grid = GridLayout(cols=3, size_hint_x=0.9, spacing=5)
        self._items_lbl = _left_label(size_hint_x=0.65)
        self._total_lbl = Label(size_hint_x=0.1)
        self._time_lbl = Label(size_hint_x=0.15)
        grid.add_widget(self._items_lbl)
        grid.add_widget(self._total_lbl)
        grid.add_widget(self._time_lbl)

        btn = MDFlatButton(text="Details", size_hint_x=0.1)
        btn.bind(on_release=lambda *_: self._open_details())

        self.add_widget(grid)
        self.add_widget(btn)

        self.bind(items=self._items_lbl.setter("text"))
        self.bind(total_with_tax=self._total_lbl.setter("text"))
        self.bind(timestamp=self._time_lbl.setter("text"))

        add_bottom_divider(self)

    def refresh_view_attrs(self, rv, index, data):
        return super().refresh_view_attrs(rv, index, data)

    def _open_details(self):
        hv = self.history_view
        if hv:
            hv.display_order_details(self.order_id)


Factory.register("HistoryRow", cls=HistoryRow)


class HistoryView(BoxLayout):
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(HistoryView, cls).__new__(cls)
        return cls._instance

    def __init__(self, ref=None, **kwargs):
        if getattr(self, "_init", False):
            return
        super().__init__(orientation="vertical", **kwargs)
        self._init = True

        self.app = App.get_running_app()
        self.receipt_printer = getattr(self.app, "receipt_printer", None)
        self.db_manager = DatabaseManager("db/inventory.db", self)
        self.order_history = []
        self.current_filter = "today"
        self.rv_data = []

        self._build_totals_bar()
        self.add_widget(self.totals_layout)

        self._build_buttons()
        self.add_widget(self.button_layout)

        self._build_rv()
        self.add_widget(self.rv)

        Clock.schedule_once(lambda dt: self.filter_today(), 0.01)

    def display_order_details_from_barcode_scan(self, barcode):
        try:
            barcode_str = str(barcode)
            order_history = self.app.db_manager.get_order_history()

            order_barcodes = [str(order[0]) for order in order_history]

            best_match, score, *_ = process.extractOne(
                barcode_str, order_barcodes, scorer=fuzz.partial_ratio, score_cutoff=80
            )

            if best_match:
                specific_order = next(
                    (order for order in order_history if str(order[0]) == best_match),
                    None,
                )

                if specific_order:
                    popup = OrderDetailsPopup(specific_order, self.receipt_printer)
                    popup.open()
                else:
                    self.order_not_found_popup(barcode_str)  # needs testing
            else:
                self.order_not_found_popup(barcode_str)

        except Exception as e:
            logger.warn(
                f"[HistoryManager] display_order_details_from_barcode_scan\n{e}"
            )

    def _build_totals_bar(self):
        self.totals_layout = GridLayout(cols=6, size_hint=(1, 0.1))
        self.history_search = _left_label()  # placeholder for sizing
        self.history_search = self._make_search_input()
        blank = BoxLayout(size_hint_x=0.1)

        self.current_filter_label = MarkupLabel(
            text="Current Filter: today", size_hint_x=0.8, markup=True
        )
        self.average_label = MarkupLabel(text="", size_hint_x=0.4, markup=True)
        self.total_cash_label = MarkupLabel(text="Total Cash: $0.00", markup=True)
        self.total_amount_label = MarkupLabel(text="Total: $0.00", markup=True)

        for w in (
            self.history_search,
            blank,
            self.current_filter_label,
            self.average_label,
            self.total_cash_label,
            self.total_amount_label,
        ):
            self.totals_layout.add_widget(w)

    def _make_search_input(self):
        from kivy.uix.textinput import TextInput

        ti = TextInput(hint_text="Search by item name", multiline=False)
        ti.bind(text=self.on_search_text_changed)
        return ti

    def _build_buttons(self):
        self.button_layout = BoxLayout(
            orientation="horizontal", spacing=5, size_hint=(1, 0.1)
        )
        mk = lambda txt, cb: MDRaisedButton(text=txt, on_release=lambda *_: cb())
        self.button_layout.add_widget(mk("Today", self.filter_today))
        self.button_layout.add_widget(mk("Yesterday", self.filter_yesterday))
        self.button_layout.add_widget(mk("Specific Day", self.show_specific_day_popup))
        self.button_layout.add_widget(mk("Custom Range", self.show_custom_range_popup))
        self.button_layout.add_widget(mk("Export CSV", self.export_history))

    def _build_rv(self):
        self.rv = RecycleView()
        lm = RecycleBoxLayout(
            default_size=(None, dp(48)),
            default_size_hint=(1, None),
            size_hint_y=None,
            spacing=5,
            padding=5,
            orientation="vertical",
        )
        lm.bind(minimum_height=lm.setter("height"))
        self.rv.add_widget(lm)  # attach layout manager first
        self.rv.viewclass = HistoryRow  # then set viewclass

    def show_reporting_popup(self, order_history):
        self.order_history = order_history or []
        try:
            self.rv_data = [
                {
                    "order_id": str(order[0]),
                    "items": self.format_items(order[1]),
                    "total": self.format_money(order[2]),
                    "tax": self.format_money(order[3]),
                    "discount": self.format_money(order[4]),
                    "total_with_tax": self.format_money(order[5]),
                    "timestamp": self.format_date(order[6]),
                    "payment_method": order[7],
                    "amount_tendered": self.format_money(order[8]),
                    "change_given": self.format_money(order[9]),
                    "history_view": self,
                }
                for order in reversed(self.order_history)
            ]
            self.rv.data = self.rv_data
        except Exception as e:
            logger.warning(f"[HistoryManager] show_reporting_popup\n{e}")

    def update_rv_data(self, filtered_history, num_days=None, date_range=None):
        try:
            self.rv_data = [
                {
                    "order_id": str(order[0]),
                    "items": self.format_items(order[1]),
                    "total": self.format_money(order[2]),
                    "tax": self.format_money(order[3]),
                    "discount": self.format_money(order[4]),
                    "total_with_tax": self.format_money(order[5]),
                    "timestamp": self.format_date(order[6]),
                    "payment_method": order[7],
                    "amount_tendered": self.format_money(order[8]),
                    "change_given": self.format_money(order[9]),
                    "history_view": self,
                    "num_days": num_days,
                    "date_range": date_range,
                }
                for order in reversed(filtered_history)
            ]
            self.rv.data = self.rv_data
        except Exception as e:
            logger.warning(f"[HistoryManager]: update_rv_data \n{e}")

    def update_totals(self):
        if not self.rv_data:
            # reset labels cleanly
            self.average_label.text = ""
            self.total_amount_label.text = (
                "[size=20]Total: 0.00 + 0.00 tax = \n[b]$0.00[/b][/size]"
            )
            self.total_cash_label.text = (
                "[size=20]Cash: 0.00 - 0.00 change = \n[b]$0.00[/b][/size]"
            )
            self.current_filter_label.text = f"Current Filter: {self.current_filter}"
            return

        f = lambda key: sum(float(o.get(key, 0) or 0) for o in self.rv_data)
        total_amount = f("total")
        total_tax = f("tax")
        total_with_tax = f("total_with_tax")
        total_tendered = f("amount_tendered")
        total_change = f("change_given")
        total_cash = total_tendered - total_change

        if self.current_filter == "custom_range":
            first = self.rv_data[0].get("date_range", [None])[0]
            last = self.rv_data[0].get("date_range", [None])[-1]
            num_days = self.rv_data[0].get("num_days") or 0
            avg_txt = ""
            if num_days:
                avg_txt = f"Av: {float(total_with_tax) / num_days:.2f}"
            self.average_label.text = avg_txt
            if first and last:
                self.current_filter_label.text = (
                    f"Range: {first.strftime('%m/%d/%Y')} - {last.strftime('%m/%d/%Y')}"
                )
            else:
                self.current_filter_label.text = "Range"
        else:
            self.average_label.text = ""
            self.current_filter_label.text = f"Current Filter: {self.current_filter}"

        self.total_amount_label.text = f"[size=20]Total: {total_amount:.2f} + {total_tax:.2f} tax = \n[b]${total_with_tax:.2f}[/b][/size]"
        self.total_cash_label.text = f"[size=20]Cash: {total_tendered:.2f} - {total_change:.2f} change = \n[b]${total_cash:.2f}[/b][/size]"

    def is_today(self, dtobj):
        return dtobj.date() == datetime.today().date()

    def is_yesterday(self, dtobj):
        return dtobj.date() == (datetime.today() - timedelta(days=1)).date()

    def is_this_week(self, dtobj):
        today = datetime.today()
        start = today - timedelta(days=today.weekday())
        end = start + timedelta(days=6)
        return start.date() <= dtobj.date() <= end.date()

    def is_this_month(self, dtobj):
        today = datetime.today()
        return dtobj.month == today.month and dtobj.year == today.year

    def _parse_dt(self, s):
        return datetime.strptime(s, "%Y-%m-%d %H:%M:%S.%f")

    def filter_today(self):
        self.current_filter = "today"
        fh = [o for o in self.order_history if self.is_today(self._parse_dt(o[6]))]
        self.update_rv_data(fh)
        self.update_totals()

    def filter_yesterday(self):
        self.current_filter = "yesterday"
        fh = [o for o in self.order_history if self.is_yesterday(self._parse_dt(o[6]))]
        self.update_rv_data(fh)
        self.update_totals()

    def filter_this_week(self):
        self.current_filter = "this_week"
        fh = [o for o in self.order_history if self.is_this_week(self._parse_dt(o[6]))]
        self.update_rv_data(fh)
        self.update_totals()

    def filter_this_month(self):
        self.current_filter = "this_month"
        fh = [o for o in self.order_history if self.is_this_month(self._parse_dt(o[6]))]
        self.update_rv_data(fh)
        self.update_totals()

    def on_search_text_changed(self, instance, value):
        value = (value or "").strip()
        if value:
            self.current_filter = "search"
            self.search_order_by_item_name(value)
        else:
            self.filter_today()

    def search_order_by_item_name(self, term):
        term = term.lower()
        results = []
        for order in self.order_history:
            try:
                items = json.loads(order[1])
            except json.JSONDecodeError as e:
                logger.warning(f"[OrderManager]: search_order_by_item_name\n{e}")
                continue
            if isinstance(items, dict):
                items = [items]
            if any(term in (it.get("name", "") or "").lower() for it in items):
                results.append(order)
        self.update_rv_data(results)
        self.update_totals()

    def show_specific_day_popup(self):
        picker = MDDatePicker()
        picker.bind(on_save=self.on_specific_day_selected)
        picker.open()

    def on_specific_day_selected(self, instance, value, date_range):
        self.current_filter = "specific_day"
        target = value
        fh = [o for o in self.order_history if self._parse_dt(o[6]).date() == target]
        self.update_rv_data(fh)
        self.update_totals()

    def show_custom_range_popup(self):
        picker = MDDatePicker(mode="range", min_year=2024)
        picker.bind(on_save=self.on_custom_range_selected)
        picker.open()

    def on_custom_range_selected(self, instance, value, date_range):
        self.current_filter = "custom_range"
        date_set = set(date_range or [])
        num_days = len(date_set)
        fh = [o for o in self.order_history if self._parse_dt(o[6]).date() in date_set]
        self.update_rv_data(fh, num_days=num_days, date_range=date_range or [])
        self.update_totals()

    def display_order_details(self, order_id):
        oid = str(order_id)
        try:
            specific = next((o for o in self.order_history if str(o[0]) == oid), None)
        except Exception as e:
            logger.warning(f"[HistoryManager] display_order_details\n{e}")
            specific = None

        if specific:
            try:
                popup = OrderDetailsPopup(specific, self.receipt_printer)
                popup.open()
            except Exception as e:
                logger.warning(e)

    def show_order_details(self, order_id):
        specific = next(
            (o for o in self.order_history if str(o[0]) == str(order_id)), None
        )
        if specific:
            self.clear_widgets()
            try:
                # Optional: render a single HistoryRow fullscreen
                row = HistoryRow()
                row.order_id = str(specific[0])
                row.items = self.format_items(specific[1])
                row.total = self.format_money(specific[2])
                row.tax = self.format_money(specific[3])
                row.total_with_tax = self.format_money(specific[5])
                row.timestamp = self.format_date(specific[6])
                row.history_view = self
                self.add_widget(row)
            except Exception as e:
                logger.warning(f"[HistoryManager] show_order_details\n{e}")

    def format_items(self, items_str):
        try:
            parsed = json.loads(items_str)
            items = [parsed] if isinstance(parsed, dict) else parsed
            names = ", ".join(it.get("name", "Unknown") for it in items)
            return self.truncate_text(names)
        except json.JSONDecodeError as e:
            logger.warning(f"JSON parsing error in format_items: {e}")
            return self.truncate_text("Error parsing items")

    def format_money(self, v):
        try:
            return f"{float(v):.2f}"
        except Exception:
            return "0.00"

    def format_date(self, s):
        try:
            return datetime.strptime(s, "%Y-%m-%d %H:%M:%S.%f").strftime(
                "%d %b %Y, %H:%M"
            )
        except Exception as e:
            logger.warning(e)
            return s

    def truncate_text(self, text, max_length=120):
        return text if len(text) <= max_length else text[: max_length - 3] + "..."

    def export_history(self, *_):
        filename = self.get_export_filename()
        rows = self.prepare_csv_data()
        with open(filename, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(
                [
                    "Order ID",
                    "Items",
                    "Total",
                    "Tax",
                    "Discount",
                    "Total with Tax",
                    "Timestamp",
                    "Payment Method",
                    "Amount Tendered",
                    "Change Given",
                ]
            )
            w.writerows(rows)
        logger.info(f"[HistoryManager] Exported {len(rows)} rows to {filename}")

    def get_export_filename(self):
        today = datetime.now().strftime("%Y-%m-%d")
        m = self.current_filter
        if m == "today":
            return f"Order_History_Today_{today}.csv"
        if m == "this_week":
            return f"Order_History_This_Week_{today}.csv"
        if m == "this_month":
            return f"Order_History_This_Month_{today}.csv"
        if m == "custom_range":
            return f"Order_History_Custom_Range_{today}.csv"
        if m == "specific_day":
            return f"Order_History_Specific_Day_{today}.csv"
        return f"Order_History_All_{today}.csv"

    def prepare_csv_data(self):
        return [
            [
                o.get("order_id"),
                o.get("items"),
                o.get("total"),
                o.get("tax"),
                o.get("discount"),
                o.get("total_with_tax"),
                o.get("timestamp"),
                o.get("payment_method"),
                o.get("amount_tendered"),
                o.get("change_given"),
            ]
            for o in self.rv_data
        ]


class HistoryPopup(Popup):
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(HistoryPopup, cls).__new__(cls, *args, **kwargs)
        return cls._instance

    def __init__(self, **kwargs):
        if getattr(self, "_init", False):
            return
        super().__init__(**kwargs)
        self._init = True
        self.db_manager = DatabaseManager("db/inventory.db", self)
        self.history_view = (
            HistoryView()
        )  # keep a single view to preserve filters between opens

    def show_hist_reporting_popup(self, instance=None):
        order_history = self.db_manager.get_order_history()
        self.history_view.show_reporting_popup(order_history)
        self.history_view.filter_today()
        self.content = self.history_view
        self.size_hint = (0.9, 0.9)
        self.title = "Order History"
        self.open()

    def dismiss_popup(self):
        self.dismiss()


class OrderDetailsPopup(Popup):
    def __init__(self, order, receipt_printer, **kwargs):
        super().__init__(**kwargs)
        self.title = f"Order Details - {order[0]}"
        self.size_hint = (0.4, 0.8)
        self.receipt_printer = receipt_printer
        self.db_manager = DatabaseManager("db/inventory.db", self)
        self.history_view = HistoryView()
        self.history_popup = HistoryPopup()

        content_layout = GridLayout(spacing=5, cols=1, rows=3)
        # header
        hv = HistoryView()
        f = self.format_order_details(order, hv)
        top_layout = Label(halign="center", size_hint_y=0.1, text=f"\n{f['Timestamp']}")
        # body
        items_split = (f["Items"] or "").split(",")
        formatted_items = "\n".join(items_split)
        middle_layout = Label(halign="center", text=formatted_items)
        if f["Payment Method"] == "Cash":
            bottom_txt = (
                f"Subtotal: {f['Total']}\nDiscount: {f['Discount']}\nTax: {f['Tax']}"
                f"\nTotal: {f['Total with Tax']}\n\nPaid with {f['Payment Method']}"
                f"\nAmount Tendered: {f['Amount Tendered']}\nChange Given: {f['Change Given']}"
            )
        else:
            bottom_txt = (
                f"Subtotal: {f['Total']}\nDiscount: {f['Discount']}\nTax: {f['Tax']}"
                f"\nTotal: {f['Total with Tax']}\n\nPaid with {f['Payment Method']}"
            )

        bottom_layout = Label(halign="center", text=bottom_txt)

        card = MDCard(orientation="vertical")
        card.add_widget(middle_layout)
        card.add_widget(bottom_layout)

        # footer buttons
        btns = BoxLayout(size_hint=(1, 0.1), height=dp(50), spacing=5)
        btns.add_widget(
            MDRaisedButton(
                text="Print Receipt", on_release=lambda *_: self.print_receipt(order)
            )
        )
        btns.add_widget(MDRaisedButton(text="Refund", on_release=self.refund))
        btns.add_widget(
            MDRaisedButton(
                text="Edit",
                on_release=lambda *_: self.open_modify_order_popup(order[0]),
            )
        )
        btns.add_widget(
            MDRaisedButton(text="Close", on_release=lambda *_: self.dismiss())
        )

        content_layout.add_widget(top_layout)
        content_layout.add_widget(card)
        content_layout.add_widget(btns)
        self.content = content_layout

    def format_order_details(self, order, history_view):
        return {
            "Order ID": order[0],
            "Items": history_view.format_items(order[1]),
            "Total": f"${history_view.format_money(order[2])}",
            "Tax": f"${history_view.format_money(order[3])}",
            "Discount": f"${history_view.format_money(order[4])}",
            "Total with Tax": f"${history_view.format_money(order[5])}",
            "Timestamp": history_view.format_date(order[6]),
            "Payment Method": order[7],
            "Amount Tendered": f"${history_view.format_money(order[8])}",
            "Change Given": f"${history_view.format_money(order[9])}",
        }

    def print_receipt(self, order):
        if self.receipt_printer:
            order_dict = self.convert_order_to_dict(order)
            self.receipt_printer.print_receipt(order_dict, reprint=True)

    def refund(self, *_):  # TODO
        pass

    def convert_order_to_dict(self, order):
        (
            order_id,
            items_json,
            total,
            tax,
            discount,
            total_with_tax,
            timestamp,
            payment_method,
            amount_tendered,
            change_given,
        ) = order
        try:
            items = json.loads(items_json)
        except json.JSONDecodeError as e:
            logger.warning(f"[OrderDetailsPopup] convert_order_to_dict \n{e}")
            items = []

        items_dict = (
            {str(i): it for i, it in enumerate(items)}
            if isinstance(items, list)
            else items
        )
        return {
            "order_id": order_id,
            "items": items_dict,
            "subtotal": total,
            "tax_amount": tax,
            "total_with_tax": total_with_tax,
            "timestamp": timestamp,
            "discount": discount,
            "payment_method": payment_method,
            "amount_tendered": amount_tendered,
            "change_given": change_given,
        }

    def open_modify_order_popup(self, order_id):
        # fetch and parse items
        order_details = self.db_manager.get_order_by_id(order_id)
        items_json = order_details[1]
        try:
            items = json.loads(items_json)
        except json.JSONDecodeError:
            items = []

        modify_order_container = MDBoxLayout(
            orientation="vertical", size_hint=(1, 1), padding=5, spacing=5
        )
        modify_order_layout = GridLayout(rows=max(1, len(items)), padding=5, spacing=5)

        item_name_inputs = []
        for item in items:
            ti = TextInput(
                text=item.get("name", ""), multiline=False, size_hint_y=None, height=50
            )
            item_name_inputs.append(ti)
            modify_order_layout.add_widget(ti)

        def on_confirm(_instance):
            # apply edits
            for item, name_input in zip(items, item_name_inputs):
                item["name"] = name_input.text
            updated_items_json = json.dumps(items)

            # persist
            self.db_manager.modify_order(order_id, items=updated_items_json)

            # close popups and refresh history
            try:
                self.modify_order_popup.dismiss()
            except Exception:
                pass
            try:
                self.dismiss()  # close order details
            except Exception:
                pass
            try:
                self.history_popup.dismiss_popup()
                Clock.schedule_once(self.history_popup.show_hist_reporting_popup, 0.2)
            except Exception as e:
                logger.warning(f"[OrderDetailsPopup] refresh after modify:\n{e}")

        buttons_layout = BoxLayout(
            orientation="horizontal", size_hint_y=None, height=75, padding=5, spacing=5
        )
        confirm_button = MDRaisedButton(
            text="Confirm Changes", on_release=on_confirm, size_hint=(1, 1)
        )
        cancel_button = MDRaisedButton(
            text="Cancel",
            on_release=lambda _i: self.modify_order_popup.dismiss(),
            size_hint=(1, 1),
        )
        delete_button = MDFlatButton(
            text="Delete Order",
            on_release=lambda _i: self.open_delete_order_confirmation_popup(
                order_id, admin=True
            ),
            size_hint=(0.5, 1),
        )
        _blank = MDBoxLayout(size_hint=(1, 1))

        buttons_layout.add_widget(confirm_button)
        buttons_layout.add_widget(cancel_button)
        buttons_layout.add_widget(_blank)
        buttons_layout.add_widget(delete_button)

        modify_order_container.add_widget(modify_order_layout)
        modify_order_container.add_widget(buttons_layout)

        self.modify_order_popup = Popup(
            size_hint=(0.8, 0.8),
            content=modify_order_container,
            title="",
            separator_height=0,
        )
        self.modify_order_popup.open()

    def open_delete_order_confirmation_popup(self, order_id, admin=False):
        if not admin:
            return
        container = MDBoxLayout(orientation="vertical")
        layout = MDCard(orientation="vertical")
        message = MarkupLabel(
            text=f"Warning!\nOrder ID {order_id}\nWill Be Permanently Deleted!\nAre you sure?",
            halign="center",
        )
        layout.add_widget(message)
        btn_layout = MDBoxLayout(orientation="horizontal")
        confirm_button = MDFlatButton(
            text="Yes", on_release=lambda _i: self.delete_order(order_id)
        )
        _blank = MDBoxLayout(size_hint=(1, 0.4))
        cancel_button = MDFlatButton(
            text="No!",
            on_release=lambda _i: self.delete_order_confirmation_popup.dismiss(),
        )
        btn_layout.add_widget(confirm_button)
        btn_layout.add_widget(_blank)
        btn_layout.add_widget(cancel_button)
        container.add_widget(layout)
        container.add_widget(btn_layout)
        self.delete_order_confirmation_popup = Popup(
            size_hint=(0.2, 0.2), content=container, title="", separator_height=0
        )
        self.delete_order_confirmation_popup.open()

    def delete_order(self, order_id):
        self.db_manager.delete_order(order_id)
        try:
            self.delete_order_confirmation_popup.dismiss()
        except Exception:
            pass
        try:
            self.modify_order_popup.dismiss()
        except Exception:
            pass
        try:
            self.dismiss()
        except Exception:
            pass
        # refresh history
        try:
            self.history_popup.dismiss_popup()
            Clock.schedule_once(self.history_popup.show_hist_reporting_popup, 0.2)
        except Exception as e:
            logger.warning(f"[OrderDetailsPopup] refresh after delete:\n{e}")
