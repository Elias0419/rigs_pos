# Kivy Imports
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.recycleview import RecycleView
from kivy.uix.textinput import TextInput
from kivy.uix.recycleview.views import RecycleDataViewBehavior
from kivy.uix.label import Label
from kivy.properties import StringProperty, ListProperty
from kivy.uix.button import Button
from kivy.uix.gridlayout import GridLayout
from kivy.clock import Clock
from kivy.metrics import dp
from kivy.uix.popup import Popup
from kivy.core.window import Window

import json

# External Imports
from barcode_scanner import BarcodeScanner
from database_manager import DatabaseManager
from order_manager import OrderManager
from popups import PopupManager
# from open_cash_drawer import open_cash_drawer
from mock_open_cash_drawer import open_cash_drawer


class CashRegisterApp(App):
    def build(self):
        self.barcode_scanner = BarcodeScanner()
        self.db_manager = DatabaseManager("my_items_database.db")
        self.order_manager = OrderManager()
        main_layout = BoxLayout(orientation="horizontal")
        button_layout = GridLayout(cols=2)
        main_layout.add_widget(button_layout)
        self.display = TextInput(
            text="", multiline=True, readonly=True, halign="right", font_size=30
        )
        main_layout.add_widget(self.display)

        buttons = [
            "Custom Item",
            "Clear Item",
            "Open Register",
            "Clear Order",
            "Pay",
            "Inventory",
        ]

        for button in buttons:
            button_layout.add_widget(Button(text=button, on_press=self.on_button_press))

        Clock.schedule_interval(self.check_for_scanned_barcode, 0.1)

        return main_layout

    def check_for_scanned_barcode(self, dt):
        if self.barcode_scanner.is_barcode_ready():
            barcode = self.barcode_scanner.read_barcode()
            print(f"Barcode scanned: {barcode}")  # Debug print
            self.handle_scanned_barcode(barcode)

    """
    Barcode functions
    """
    def on_add_or_bypass_choice(self, instance, barcode):
        if instance.text == "Add Custom Item":
            self.show_custom_item_popup(barcode)
            self.popup.dismiss()
        elif instance.text == "Add to Database":
            self.show_add_to_database_popup(barcode)

    def handle_scanned_barcode(self, barcode):
        try:
            item_details = self.db_manager.get_item_details(barcode)
            if item_details:
                print(item_details)
                item_name, item_price = item_details
                self.order_manager.items.append((item_name, item_price))
                self.order_manager.total += item_price
                self.display.text += f"{item_name}  ${item_price}\n"
            else:
                PopupManager.show_add_or_bypass_popup(barcode, self.on_add_or_bypass_choice)
        except Exception as e:
            print(f"Error handling scanned barcode: {e}")




    """
    Order management functions
    """

    def finalize_order(self):
        total_with_tax = self.order_manager.calculate_total_with_tax()
        print(total_with_tax)
        order_summary = f"Order Summary:\n{self.display.text}\nTotal with Tax: ${total_with_tax:.2f}"
        PopupManager.show_order_popup(order_summary, self.on_payment_button_press)

    def on_button_press(self, instance):
        current = self.display.text
        button_text = instance.text

        if button_text == "Clear Order":
            self.display.text = ""
        elif button_text == "Pay":
            self.finalize_order()
        elif button_text == "Custom Item":
            barcode = "1234567890"
            cash_input = PopupManager.show_custom_item_popup(barcode, PopupManager.on_numeric_button_press, self.add_custom_item, self.on_custom_item_cancel)
            PopupManager.show_custom_item_popup(
            barcode,
            lambda x: PopupManager.on_numeric_button_press(cash_input, x),
            self.add_custom_item,
            self.on_custom_item_cancel
        )
        elif button_text == "Clear Item":
            # Clear the last item from the order
            pass
        elif button_text == "Open Register":
            open_cash_drawer()
        elif button_text == "Inventory":
            pass
        else:
            self.display.text = current + button_text

    def send_order_to_history_database(self, order_details, order_manager, db_manager):
        db_manager.add_order_history(
            order_details["order_id"],
            json.dumps(order_details["items"]),
            order_details["total_with_tax"],
            order_details["total"],
        )

    ########


    def add_item_to_database(self, barcode, name, price):
        try:

            if self.db_manager.add_item(barcode, name, price):
                print(f"Item '{name}' added to the database.")
        except Exception as e:
            print(f"Error adding item to database: {e}")
        finally:
            pass


    #popups.py
    # def on_done_button_press(self, instance):
    #     order_details = self.order_manager.get_order_details()
    #     self.send_order_to_history_database(
    #         order_details, self.order_manager, self.db_manager
    #     )
    #     self.order_manager.clear_order()
    #
    #     PopupManager.dismiss_current_popup()
    #     self.display.text = ""
    #
    # """
    # Payment functions
    # """
    #
    # def on_payment_button_press(self, instance):
    #     if instance.text == "Pay Cash":
    #         PopupManager.show_cash_payment_popup(self.on_numeric_button_press, self.on_cash_confirm, self.on_cash_cancel)
    #     elif instance.text == "Pay Card":
    #         self.handle_card_payment()
    #     elif instance.text == "Cancel":
    #         PopupManager.dismiss_current_popup()

    def handle_card_payment(self, display_text):
        open_cash_drawer()
        PopupManager.show_payment_confirmation_popup(display_text, self.on_done_button_press)

    def on_change_done(self, instance, display_text):
        PopupManager.dismiss_current_popup()
        open_cash_drawer()
        PopupManager.show_payment_confirmation_popup(display_text, self.on_done_button_press)

    def on_order_complete(self, instance):
        PopupManager.dismiss_current_popup()

    # def on_numeric_button_press(self, instance):
    #     current_input = self.cash_input.text.replace(".", "").lstrip("0")
    #     new_input = current_input + instance.text
    #     new_input = new_input.zfill(2)
    #     cents = int(new_input)
    #     dollars = cents // 100
    #     remaining_cents = cents % 100


        self.cash_input.text = f"{dollars}.{remaining_cents:02d}"

    def on_cash_cancel(self, instance):
        PopupManager.dismiss_current_popup()

    def on_cash_confirm(self, instance):
        amount_tendered = float(self.cash_input.text)
        total_with_tax = self.order_manager.calculate_total_with_tax()
        change = amount_tendered - total_with_tax
        PopupManager.dismiss_current_popup()
        PopupManager.show_make_change_popup(change, self.on_change_done)

    def add_custom_item(self, instance):
        price = self.cash_input.text
        try:
            price = float(price)
        except ValueError:
            # Handle invalid price input
            return

        custom_item_name = "Custom Item"

        self.order_manager.items.append((custom_item_name, price))
        self.order_manager.total += price
        self.display.text += f"{custom_item_name}  ${price:.2f}\n"
        PopupManager.dismiss_current_popup()


    def on_custom_item_cancel(self, instance):
        PopupManager.dismiss_current_popup()

    #


if __name__ == "__main__":
    CashRegisterApp().run()
