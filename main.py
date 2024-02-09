from datetime import datetime
import json


from kivy.config import Config

Config.set("kivy", "keyboard_mode", "systemanddock")

import eel
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.modules import inspector
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput

from kivymd.app import MDApp
from kivymd.uix.boxlayout import BoxLayout
from kivymd.uix.button import MDIconButton
from kivymd.uix.gridlayout import GridLayout
from kivymd.uix.label import MDLabel

from barcode_scanner import BarcodeScanner
from database_manager import DatabaseManager
from label_printer import LabelPrintingView
from open_cash_drawer import open_cash_drawer
from order_manager import OrderManager
from history_manager import HistoryView, HistoryPopup
from receipt_printer import ReceiptPrinter
from inventory_manager import InventoryManagementView
from popups import PopupManager, FinancialSummaryWidget
from button_handlers import ButtonHandler
from util import Utilities
Window.maximize()
Window.borderless = True


class CashRegisterApp(MDApp):
    def __init__(self, **kwargs):
        super(CashRegisterApp, self).__init__(**kwargs)

        self.correct_pin = "1234"
        self.entered_pin = ""
        self.is_guard_screen_displayed = False
        self.is_lock_screen_displayed = False
        self.override_tap_time = 0
        self.pin_reset_timer = None
        self.current_context = "main"
        self.theme_cls.theme_style = "Light"
        self.theme_cls.primary_palette = "Brown"
        self.selected_categories = []


    def build(self):
        self.barcode_scanner = BarcodeScanner()
        self.db_manager = DatabaseManager("inventory.db")
        self.financial_summary = FinancialSummaryWidget(self)
        self.order_manager = OrderManager()
        self.history_manager = HistoryView(self)
        self.history_popup = HistoryPopup()
        self.receipt_printer = ReceiptPrinter(self, "receipt_printer_config.yaml")
        self.inventory_manager = InventoryManagementView()
        self.label_manager = LabelPrintingView()
        self.popup_manager = PopupManager(self)
        self.button_handler = ButtonHandler(self)
        self.utilities = Utilities(self)
        self.categories = self.utilities.initialze_categories()
        self.utilities.load_settings()

        main_layout = GridLayout(
            cols=1, spacing=5, orientation="tb-lr", row_default_height=60
        )
        top_area_layout = GridLayout(cols=3, orientation="lr-tb", row_default_height=60)
        self.order_layout = GridLayout(
            orientation="tb-lr",
            cols=2,
            rows=13,
            spacing=5,
            row_default_height=60,
            row_force_default=True,
            size_hint_x=1 / 3,
        )

        top_area_layout.add_widget(self.order_layout)
        financial_layout = self.create_financial_layout()
        top_area_layout.add_widget(financial_layout)
        clock_layout = self.create_clock_layout()
        top_area_layout.add_widget(clock_layout)
        main_layout.add_widget(top_area_layout)
        button_layout = GridLayout(
            cols=4, spacing=5, size_hint_y=1 / 8, size_hint_x=1, orientation="lr-tb"
        )

        btn_pay = self.utilities.create_md_raised_button(
            "Pay",
            self.button_handler.on_button_press,
            (8, 8),
            "H6",
        )

        btn_custom_item = self.utilities.create_md_raised_button(
            "Custom",
            self.button_handler.on_button_press,
            (8, 8),
            "H6",
        )
        btn_inventory = self.utilities.create_md_raised_button(
            "Search",
            self.button_handler.on_button_press,
            (8, 8),
            "H6",
        )
        btn_tools = self.utilities.create_md_raised_button(
            "Tools",
            self.button_handler.on_button_press,  #################
            # lambda x: self.show_add_or_bypass_popup("210973141121"),
            #lambda x: self.popup_manager.show_add_or_bypass_popup("220973141121"),
            # lambda x: self.open_category_button_popup(),
            (8, 8),
            "H6",
        )
        button_layout.add_widget(btn_pay)
        button_layout.add_widget(btn_custom_item)
        button_layout.add_widget(btn_inventory)
        button_layout.add_widget(btn_tools)
        main_layout.add_widget(button_layout)

        Clock.schedule_interval(self.utilities.check_inactivity, 10)
        Clock.schedule_interval(self.check_for_scanned_barcode, 0.1)

        if not hasattr(self, "monitor_check_scheduled"):
            Clock.schedule_interval(self.utilities.check_monitor_status, 5)
            self.monitor_check_scheduled = True

        return main_layout

    def create_clock_layout(self):
        clock_layout = BoxLayout(orientation="vertical", size_hint_x=1 / 3)
        self.clock_label = MDLabel(
            text="Loading...",
            size_hint_y=None,
            font_style="H6",
            height=80,
            color=self.utilities.get_text_color(),
            halign="center",
        )
        padlock_button = MDIconButton(
            icon="lock",
            pos_hint={"right": 1},
            on_press=lambda x: self.turn_off_monitor(),
        )
        clock_layout.add_widget(padlock_button)

        Clock.schedule_interval(self.utilities.update_clock, 1)
        clock_layout.add_widget(self.clock_label)
        return clock_layout

    def create_financial_layout(self):
        financial_layout = GridLayout(cols=1, size_hint_x=1 / 3)

        self.financial_summary_widget = FinancialSummaryWidget(self)
        financial_layout.add_widget(self.financial_summary_widget)

        return financial_layout

    """
    Barcode functions
    """

    def check_for_scanned_barcode(self, dt):
        if self.barcode_scanner.is_barcode_ready():
            barcode = self.barcode_scanner.read_barcode()
            self.handle_global_barcode_scan(barcode)

    def handle_global_barcode_scan(self, barcode):
        if self.current_context == "inventory":
            self.inventory_manager.handle_scanned_barcode(barcode)
        elif self.current_context == "label":
            self.label_manager.handle_scanned_barcode(barcode)
        elif self.current_context == "inventory_item":
            self.inventory_manager.handle_scanned_barcode_item(barcode)
        # elif self.current_context == "history":
        #     self.history_manager.handle_scanned_barcode(barcode)
        else:
            self.handle_scanned_barcode(barcode)

    def handle_scanned_barcode(self, barcode):
        try:
            if '-' in barcode and any(c.isalpha() for c in barcode):
                self.history_manager.display_order_details_from_barcode_scan(barcode)
            else:
                item_details = self.db_manager.get_item_details(barcode)

                if item_details:
                    item_name, item_price = item_details
                    self.order_manager.add_item(item_name, item_price)
                    self.utilities.update_display()
                    self.utilities.update_financial_summary()
                    return item_details
                else:
                    self.popup_manager.show_add_or_bypass_popup(barcode)

        except Exception as e:
            print(e)


    """
    Split payment stuff
    """

    def clear_split_numeric_input(self):
        self.popup_manager.split_payment_numeric_cash_input.text = ""

    def handle_split_input(self, amount, method):
        if not amount.strip():
            pass
        else:
            try:
                amount = float(amount)
                self.on_split_payment_confirm(amount=amount, method=method)
            except ValueError as e:
                print(e)

    def on_split_payment_confirm(self, amount, method):
        amount = float(f"{amount:.2f}")
        print("on_split_payment_confirm float", amount, method)
        self.popup_manager.split_payment_info["total_paid"] += amount
        self.popup_manager.split_payment_info["remaining_amount"] -= amount
        self.popup_manager.split_payment_info["payments"].append(
            {"method": method, "amount": amount}
        )

        if method == "Cash":
            print("method", method)
            self.popup_manager.show_split_cash_popup(amount)
            self.popup_manager.split_payment_numeric_popup.dismiss()
        elif method == "Debit":
            self.popup_manager.show_split_card_confirm(amount, method)
            self.popup_manager.split_payment_numeric_popup.dismiss()
        elif method == "Credit":
            self.popup_manager.show_split_card_confirm(amount, method)
            self.popup_manager.split_payment_numeric_popup.dismiss()

    def split_cash_continue(self, instance):
        tolerance = 0.001
        self.popup_manager.dismiss_popups(
            "split_cash_popup", "split_cash_confirm_popup", "split_change_popup"
        )

        if abs(self.popup_manager.split_payment_info["remaining_amount"]) <= tolerance:
            self.finalize_split_payment()
        else:
            self.popup_manager.show_split_payment_numeric_popup(subsequent_payment=True)

    def split_card_continue(self, amount, method):

        tolerance = 0.001
        self.popup_manager.dismiss_popups("split_card_confirm_popup")

        if abs(self.popup_manager.split_payment_info["remaining_amount"]) <= tolerance:
            self.finalize_split_payment()
        else:
            self.popup_manager.show_split_payment_numeric_popup(subsequent_payment=True)



    def split_on_custom_cash_confirm(self, amount):

        self.popup_manager.split_custom_cash_popup.dismiss()
        input_amount = float(self.popup_manager.split_custom_cash_input.text)
        print(input_amount, type(input_amount))
        amount = float(amount)
        print(amount, type(amount))
        if input_amount > amount:

            open_cash_drawer()
            change = float(self.popup_manager.split_custom_cash_input.text) - amount

            self.popup_manager.split_cash_make_change(change, amount)
        else:

            open_cash_drawer()
            self.popup_manager.show_split_cash_confirm(amount)

    def split_on_cash_confirm(self, amount):
        self.popup_manager.split_cash_popup.dismiss()
        if float(self.popup_manager.split_cash_input.text) > amount:
            open_cash_drawer()
            change = float(self.popup_manager.split_cash_input.text) - amount

            self.popup_manager.split_cash_make_change(change, amount)
        else:

            open_cash_drawer()
            self.popup_manager.show_split_cash_confirm(amount)

    def finalize_split_payment(self):
        self.order_manager.set_payment_method("Split")
        self.popup_manager.show_payment_confirmation_popup()

    """
    Orders
    """

    def handle_credit_payment(self):
        open_cash_drawer()
        self.order_manager.set_payment_method("Credit")
        self.popup_manager.show_payment_confirmation_popup()

    def handle_debit_payment(self):
        open_cash_drawer()
        self.order_manager.set_payment_method("Debit")
        self.popup_manager.show_payment_confirmation_popup()

    def on_cash_confirm(self, instance):
        amount_tendered = float(self.popup_manager.cash_payment_input.text)
        total_with_tax = self.order_manager.calculate_total_with_tax()
        change = amount_tendered - total_with_tax
        if hasattr(self.popup_manager, "cash_popup"):
            self.popup_manager.cash_popup.dismiss()
        if hasattr(self.popup_manager, "custom_cash_popup"):
            self.popup_manager.custom_cash_popup.dismiss()
        open_cash_drawer()
        self.order_manager.set_payment_method("Cash")
        self.order_manager.set_payment_details(amount_tendered, change)
        self.popup_manager.show_make_change_popup(change)

    def add_adjusted_price_item(self):
        target_amount = self.popup_manager.adjust_price_cash_input.text
        try:
            target_amount = float(target_amount)
        except ValueError as e:
            print(e)

        self.order_manager.adjust_order_to_target_total(target_amount)
        self.utilities.update_display()
        self.utilities.update_financial_summary()
        self.popup_manager.adjust_price_popup.dismiss()
        self.financial_summary.order_mod_popup.dismiss()

    def remove_item(self, item_name, item_price):
        self.order_manager.remove_item(item_name)
        self.utilities.update_display()
        self.utilities.update_financial_summary()
        self.popup_manager.item_popup.dismiss()

    def adjust_item_quantity(self, item_id, adjustment):
        self.order_manager.adjust_item_quantity(item_id, adjustment)
        self.popup_manager.item_popup.dismiss()
        self.popup_manager.show_item_details_popup(item_id)
        # self.on_item_click(item_id)
        self.utilities.update_display()
        self.utilities.update_financial_summary()

    def discount_single_item(self, discount_amount, percent=False):
        if percent:

            self.order_manager.add_discount(discount_amount, percent=True)
            self.utilities.update_display()
            self.utilities.update_financial_summary()
        else:
            self.order_manager.add_discount(discount_amount)
            self.utilities.update_display()
            self.utilities.update_financial_summary()

        self.popup_manager.discount_popup.dismiss()
        self.popup_manager.item_popup.dismiss()
        if hasattr(self.popup_manager, "item_popup") and self.popup_manager.item_popup is not None:
            self.popup_manager.item_popup.dismiss()

    def create_order_summary_item(self, item_name, quantity, total_price):
        return f"[b]{item_name}[/b] x{quantity} ${total_price:.2f}\n"

    def finalize_order(self):
        order_details = self.order_manager.get_order_details()

        order_summary = f"[size=18][b]Order Summary:[/b][/size]\n\n"

        for item_id, item_details in order_details["items"].items():
            item_name = item_details["name"]
            quantity = item_details["quantity"]
            total_price_for_item = item_details["total_price"]

            try:
                total_price_float = float(total_price_for_item)
            except ValueError as e:
                print(e)
                continue

            order_summary += self.create_order_summary_item(
                item_name, quantity, total_price_float
            )

        order_summary += f"\nSubtotal: ${order_details['subtotal']:.2f}"
        order_summary += f"\nTax: ${order_details['tax_amount']:.2f}"
        if order_details["discount"] > 0:
            order_summary += f"\nDiscount: ${order_details['discount']:.2f}"
        order_summary += (
            f"\n\n[size=20]Total: [b]${order_details['total_with_tax']:.2f}[/b][/size]"
        )

        self.popup_manager.show_order_popup(order_summary)

    def add_custom_item(self, instance):
        price = self.popup_manager.cash_input.text
        try:
            price = float(price)
        except Exception as e:
            print("Exception in add custom item main.py,", e)

        custom_item_name = "Custom Item"
        self.order_manager.add_item(custom_item_name, price)
        self.utilities.update_display()
        self.utilities.update_financial_summary()
        self.popup_manager.custom_item_popup.dismiss()

    """
    Database
    """

    def send_order_to_history_database(self, order_details, order_manager, db_manager):
        tax = order_details["total_with_tax"] - order_details["total"]
        timestamp = datetime.now()

        items_for_db = [
            {**{"name": item_name}, **item_details}
            for item_name, item_details in order_details["items"].items()
        ]

        db_manager.add_order_history(
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
                self.db_manager.add_item(barcode, name, price, cost, sku, categories)
                self.popup_manager.add_to_db_popup.dismiss()
            except Exception as e:
                print(e)



    """
    Web
    """

    @eel.expose
    @staticmethod
    def get_order_history_for_eel():
        db_manager = DatabaseManager("inventory.db")
        order_history = db_manager.get_order_history()
        formatted_data = [
            {
                "order_id": order[0],
                "items": order[1],
                "total": order[2],
                "tax": order[3],
                "discount": order[4],
                "total_with_tax": order[5],
                "timestamp": order[6],
                "payment_method": order[7],
                "amount_tendered": order[8],
                "change_given": order[9],
            }
            for order in order_history
        ]
        return formatted_data

    def start_eel(self):
        eel.init("web")
        print("start eel")
        eel.start("index.html")


class MarkupLabel(Label):
    pass


class MoneyInput(TextInput):
    def insert_text(self, substring, from_undo=False):
        if not from_undo:
            current_text = self.text.replace(".", "") + substring
            current_text = current_text.zfill(3)
            new_text = current_text[:-2] + "." + current_text[-2:]
            new_text = (
                str(float(new_text)).rstrip("0").rstrip(".")
                if "." in new_text
                else new_text
            )
            self.text = ""
            self.text = new_text
        else:
            super(MoneyInput, self).insert_text(substring, from_undo=from_undo)







try:
    app = CashRegisterApp()
    app.run()
except KeyboardInterrupt:
    print("test")
# if __name__ == "__main__":
#     app = CashRegisterApp()
#     app.run()
#     #app.show_lock_screen()
