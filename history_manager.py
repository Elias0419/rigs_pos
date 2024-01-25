import ast
import csv
import json
from datetime import datetime, timedelta
from functools import partial

from kivymd.app import MDApp
from kivy.metrics import dp
from kivymd.uix.boxlayout import BoxLayout
from kivymd.uix.gridlayout import GridLayout
from kivymd.uix.recycleview import RecycleView
from kivy.uix.recycleboxlayout import RecycleBoxLayout
from kivy.uix.popup import Popup
from kivy.uix.label import Label
from kivy.properties import StringProperty, ObjectProperty
from kivymd.uix.pickers import MDDatePicker
from kivymd.uix.button import MDRaisedButton
from kivy.uix.popup import Popup

from database_manager import DatabaseManager
from receipt_printer import ReceiptPrinter


class HistoryPopup(Popup):
    def __init__(self, **kwargs):
        super(HistoryPopup, self).__init__(**kwargs)
        self.db_manager = DatabaseManager("inventory.db")

    def show_hist_reporting_popup(self):
        order_history = self.db_manager.get_order_history()
        history_view = HistoryView()
        history_view.show_reporting_popup(order_history)

        self.content = history_view
        self.size_hint = (0.9, 0.9)
        self.title = "Order History"

        self.open()


class HistoryRow(BoxLayout):
    order_id = StringProperty()
    items = StringProperty()
    total = StringProperty()
    tax = StringProperty()
    total_with_tax = StringProperty()
    timestamp = StringProperty()
    history_view = ObjectProperty()

    def __init__(self, **kwargs):
        super(HistoryRow, self).__init__(**kwargs)
        self.order_history = None


class HistoryView(BoxLayout):
    def __init__(self, **kwargs):
        super(HistoryView, self).__init__(**kwargs)
        self.order_history = []
        self.orientation = "vertical"
        self.current_filter = None
        # self.size_hint = (1, 1)
        self.receipt_printer = ReceiptPrinter("receipt_printer_config.yaml")

        self.button_layout = BoxLayout(orientation="horizontal", size_hint=(1, 0.2))
        self.button_layout.add_widget(
            MDRaisedButton(
                text="Today", size_hint=(0.2, 0.5), on_press=self.filter_today
            )
        )
        self.button_layout.add_widget(
            MDRaisedButton(
                text="This Week", size_hint=(0.2, 0.5), on_press=self.filter_this_week
            )
        )
        self.button_layout.add_widget(
            MDRaisedButton(
                text="This Month", size_hint=(0.2, 0.5), on_press=self.filter_this_month
            )
        )
        self.button_layout.add_widget(
            MDRaisedButton(
                text="Specific Day",
                size_hint=(0.2, 0.5),
                on_press=self.show_specific_day_popup,
            )
        )
        self.button_layout.add_widget(
            MDRaisedButton(
                text="Custom Range",
                size_hint=(0.2, 0.5),
                on_press=self.show_custom_range_popup,
            )
        )
        self.button_layout.add_widget(
            MDRaisedButton(
                text="Export CSV", size_hint=(0.2, 0.5), on_press=self.export_history
            )
        )
        self.rv_data = []

        self.add_widget(self.button_layout)

    def export_history(self, instance):
        filename = self.get_export_filename()

        csv_data = self.prepare_csv_data()

        with open(filename, "w", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)
            writer.writerow(
                ["Order ID", "Items", "Total", "Tax", "Total with Tax", "Timestamp"]
            )
            for row in csv_data:
                writer.writerow(row)

    def get_export_filename(self):
        today = datetime.now().strftime("%Y-%m-%d")
        if self.current_filter == "today":
            return f"Order_History_Today_{today}.csv"
        elif self.current_filter == "this_week":
            return f"Order_History_This_Week_{today}.csv"
        elif self.current_filter == "this_month":
            return f"Order_History_This_Month_{today}.csv"
        elif self.current_filter == "custom_range":
            return f"Order_History_Custom_Range_{today}.csv"
        elif self.current_filter == "specific_day":
            return f"Order_History_Custom_Range_{today}.csv"
        else:
            return f"Order_History_All_{today}.csv"

    def prepare_csv_data(self):
        return [
            [
                order["order_id"],
                order["items"],
                order["total"],
                order["tax"],
                order["total_with_tax"],
                order["timestamp"],
            ]
            for order in self.rv_data
        ]

    def show_reporting_popup(self, order_history):
        self.order_history = order_history
        self.rv_data = [
            {
                "order_id": order[0],
                "items": self.format_items(order[1]),
                "total": self.format_money(order[2]),
                "tax": self.format_money(order[3]),
                "total_with_tax": self.format_money(order[4]),
                "timestamp": self.format_date(order[5]),
                "history_view": self,
            }
            for order in order_history
        ]
        self.rv_data.reverse()

        self.ids.history_rv.data = self.rv_data

    def create_history_row(self, order):
        history_row = HistoryRow()
        history_row.order_id = order[0]
        history_row.items = self.format_items(order[1])
        history_row.total = self.format_money(order[2])
        history_row.tax = self.format_money(order[3])
        history_row.total_with_tax = self.format_money(order[4])
        history_row.timestamp = self.format_date(order[5])

        history_row.history_view = self

        return history_row

    def show_specific_day_popup(self, instance):
        specific_day_picker = MDDatePicker()
        specific_day_picker.bind(on_save=self.on_specific_day_selected)
        specific_day_picker.open()

    def on_specific_day_selected(self, instance, picker, date):
        self.current_filter = "specific_day"

        filtered_history = [
            order
            for order in self.order_history
            if datetime.strptime(order[5], "%Y-%m-%d %H:%M:%S.%f").date() == picker
        ]
        self.update_rv_data(filtered_history)

    def show_custom_range_popup(self, instance):
        custom_range_picker = MDDatePicker(mode="range")
        custom_range_picker.bind(on_save=self.on_custom_range_selected)
        custom_range_picker.open()

    def on_custom_range_selected(self, instance, picker, date_range):
        self.current_filter = "custom_range"

        date_set = set(date_range)

        filtered_history = [
            order
            for order in self.order_history
            if datetime.strptime(order[5], "%Y-%m-%d %H:%M:%S.%f").date() in date_set
        ]
        self.update_rv_data(filtered_history)

    def update_rv_data(self, filtered_history):
        self.rv_data = [
            {
                "order_id": order[0],
                "items": self.format_items(order[1]),
                "total": self.format_money(order[2]),
                "tax": self.format_money(order[3]),
                "total_with_tax": self.format_money(order[4]),
                "timestamp": self.format_date(order[5]),
                "history_view": self,
            }
            for order in filtered_history
        ]
        self.rv_data.reverse()
        self.ids.history_rv.data = self.rv_data

    def is_today(self, date_obj):
        return date_obj.date() == datetime.today().date()

    def filter_today(self, instance):
        self.current_filter = "today"
        filtered_history = [
            order
            for order in self.order_history
            if self.is_today(datetime.strptime(order[5], "%Y-%m-%d %H:%M:%S.%f"))
        ]
        self.update_rv_data(filtered_history)

    def is_this_week(self, date_obj):
        today = datetime.today()
        start_week = today - timedelta(days=today.weekday())
        end_week = start_week + timedelta(days=6)
        return start_week.date() <= date_obj.date() <= end_week.date()

    def filter_this_week(self, instance):
        self.current_filter = "this_week"
        filtered_history = [
            order
            for order in self.order_history
            if self.is_this_week(datetime.strptime(order[5], "%Y-%m-%d %H:%M:%S.%f"))
        ]
        self.update_rv_data(filtered_history)

    def is_this_month(self, date_obj):
        today = datetime.today()
        return date_obj.month == today.month and date_obj.year == today.year

    def filter_this_month(self, instance):
        self.current_filter = "this_month"

        filtered_history = [
            order
            for order in self.order_history
            if self.is_this_month(datetime.strptime(order[5], "%Y-%m-%d %H:%M:%S.%f"))
        ]
        self.update_rv_data(filtered_history)

    def set_order_history(self, order_history):
        self.order_history = order_history

    def display_order_details(
        self,
        order_id,
    ):
        order_id_str = str(order_id)
        try:
            specific_order = next(
                (
                    order
                    for order in self.order_history
                    if str(order[0]) == order_id_str
                ),
                None,
            )
        except:
            pass

        if specific_order:
            popup = OrderDetailsPopup(specific_order, self.receipt_printer)

            popup.open()
        else:
            pass

    def show_order_details(self, order_id):
        specific_order = next(
            (order for order in self.order_history if order[0] == order_id), None
        )
        if specific_order:
            print(specific_order)
            self.clear_widgets()
            history_row = self.create_history_row(specific_order)
            self.add_widget(history_row)
        else:
            pass

    def format_items(self, items_str):
        try:
            items_list = ast.literal_eval(items_str)
            all_item_names = ", ".join(
                item.get("name", "Unknown") for item in items_list
            )
            return self.truncate_text(all_item_names)
        except:
            pass

    def format_money(self, value):
        return "{:.2f}".format(value)

    def format_date(self, date_str):
        try:
            date_obj = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S.%f")
            return date_obj.strftime("%d %b %Y, %H:%M")
        except:
            pass

    def truncate_text(self, text, max_length=120):
        return text if len(text) <= max_length else text[: max_length - 3] + "..."


class OrderDetailsPopup(Popup):
    def __init__(self, order, receipt_printer, **kwargs):
        super(OrderDetailsPopup, self).__init__(**kwargs)
        self.title = f"Order Details - {order[0]}"
        self.history_view = HistoryView()
        self.size_hint = (0.8, 0.6)
        self.receipt_printer = receipt_printer

        content_layout = BoxLayout(orientation="vertical", spacing=dp(10))

        content_layout.add_widget(
            Label(text=self.format_order_details(order), valign="top", halign="left")
        )

        button_layout = BoxLayout(size_hint_y=None, height=dp(50), spacing=dp(10))

        button_layout.add_widget(
            MDRaisedButton(
                text="Print Receipt", on_press=partial(self.print_receipt, order=order)
            )
        )
        button_layout.add_widget(MDRaisedButton(text="Refund", on_press=self.refund))
        button_layout.add_widget(
            MDRaisedButton(text="Close", on_press=self.dismiss_popup)
        )

        content_layout.add_widget(button_layout)

        self.content = content_layout

    def print_receipt(self, instance, order):

        order_dict = self.convert_order_to_dict(order)

        #receipt_image = self.receipt_printer.create_receipt_image(order_dict)
        self.receipt_printer.print_receipt(order_dict)

    def refund(self, instance):
        pass

    def dismiss_popup(self, instance):
        self.dismiss()

    def format_items(self, items_str):
        try:
            items_list = ast.literal_eval(items_str)
            all_item_names = ", ".join(
                item.get("name", "Unknown") for item in items_list
            )
            return all_item_names
        except (ValueError, SyntaxError):
            pass

    def convert_order_to_dict(self, order_tuple):
        order_id, items_json, total, tax, total_with_tax, timestamp = order_tuple
        try:
            items = json.loads(items_json)
        except json.JSONDecodeError:
            items = ast.literal_eval(items_json)

        if isinstance(items, list):
            items_dict = {str(i): item for i, item in enumerate(items)}
        else:
            items_dict = items

        order_dict = {
            "order_id": order_id,
            "items": items_dict,
            "subtotal": total,
            "tax_amount": tax,
            "total_with_tax": total_with_tax,
            "timestamp": timestamp,
            "discount": 0.0,
        }

        return order_dict

    def format_order_details(self, order):
        print(order)
        formatted_order = [
            f"Order ID: {order[0]}",
            f"Items: {self.format_items(order[1])}",
            f"Total: ${self.history_view.format_money(order[2])}",
            # f"Discount: ${self.history_view.format_money(order[2])}",
            f"Tax: ${self.history_view.format_money(order[3])}",
            f"Total with Tax: ${self.history_view.format_money(order[4])}",
            f"Timestamp: {self.history_view.format_date(order[5])}",
        ]
        return "\n".join(formatted_order)
