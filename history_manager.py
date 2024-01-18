from kivymd.uix.boxlayout import BoxLayout
from kivy.uix.popup import Popup
from kivy.uix.label import Label
from kivy.properties import StringProperty, ListProperty, ObjectProperty
import ast
from datetime import datetime

class HistoryRow(BoxLayout):
    history_view = ObjectProperty(None)
    items = StringProperty("")
    total = StringProperty("")
    tax = StringProperty("")
    total_with_tax = StringProperty("")
    timestamp = StringProperty("")
    order_id = StringProperty("")

    def __init__(self, **kwargs):
        super(HistoryRow, self).__init__(**kwargs)
        self.orientation = "horizontal"
        self.size_hint_y = None
        self.height = 40
        self.order_history = None


class OrderDetailsPopup(Popup):
    def __init__(self, order, **kwargs):
        super(OrderDetailsPopup, self).__init__(**kwargs)
        self.title = f"Order Details - {order[0]}"
        self.history_view = HistoryView()
        self.content = Label(
            text=self.format_order_details(order), valign="top", halign="left"
        )
        self.size_hint = (0.8, 0.6)

    def format_items(self, items_str):
        try:
            items_list = ast.literal_eval(items_str)
            all_item_names = ", ".join(
                item.get("name", "Unknown") for item in items_list
            )
            return all_item_names
        except (ValueError, SyntaxError):
            pass

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


class HistoryView(BoxLayout):
    def __init__(self, **kwargs):
        super(HistoryView, self).__init__(**kwargs)
        self.order_history = []

    def set_order_history(self, order_history):
        self.order_history = order_history

    def show_reporting_popup(self, order_history):
        self.set_order_history(order_history)
        self.clear_widgets()
        for order in order_history:
            history_row = self.create_history_row(order)
            self.add_widget(history_row)

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
            popup = OrderDetailsPopup(order=specific_order)
            popup.open()
        else:
            pass

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

    def show_order_details(self, order_id):
        specific_order = next(
            (order for order in self.order_history if order[0] == order_id), None
        )
        if specific_order:
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
            return self.truncate_text(all_item_names, max_length=40)
        except (ValueError, SyntaxError):
           pass

    def format_money(self, value):
        return "{:.2f}".format(value)

    def format_date(self, date_str):
        try:
            date_obj = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S.%f")
            return date_obj.strftime("%d %b %Y, %H:%M")
        except ValueError:
            pass

    def truncate_text(self, text, max_length=40):
        return text if len(text) <= max_length else text[: max_length - 3] + "..."
