from kivy.config import Config

Config.set("kivy", "keyboard_mode", "systemanddock")
import json
import time
import subprocess

from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.lang import Builder
from kivy.metrics import dp
from kivy.properties import StringProperty, ListProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.recycleview import RecycleView
from kivy.uix.recycleview.views import RecycleDataViewBehavior
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput

from barcode_scanner import BarcodeScanner

# from mock_barcode_scanner import BarcodeScanner
from database_manager import DatabaseManager
from order_manager import OrderManager

from open_cash_drawer import open_cash_drawer
# from mock_open_cash_drawer import open_cash_drawer


class InventoryRow(BoxLayout):
    pass

class HistoryRow(BoxLayout):
    pass


class InventoryView(BoxLayout):
    def show_inventory(self, inventory_items):
        self.rv.data = [
            {"barcode": str(item[0]), "name": item[1], "price": str(item[2])}
            for item in inventory_items
        ]

class HistoryView(BoxLayout):
    def show_reporting_popup(self, order_history):
        # self.rv.data = [
        #     {"order_id": str(order[0]), "items":str(order[1]), "total":str(order[2]), "tax":str(order[3]), "total_with_tax":str(order[4]), "timestamp":str(order[5])} # TODO look in truncating or wrapping
        #     for order in order_history
        # ]
        self.rv.data = [
            {"items":str(order[1]), "total":str(order[2]), "tax":str(order[3]), "total_with_tax":str(order[4]), "timestamp":str(order[5])}
            for order in order_history
        ]

class CashRegisterApp(App):
    def __init__(self, **kwargs):
        super(CashRegisterApp, self).__init__(**kwargs)
        self.last_scanned_item = None
        self.correct_pin = "1234"  # Set your desired PIN here
        self.entered_pin = ""
        self.is_guard_screen_displayed = False
        self.is_lock_screen_displayed = False

    def build(self):
        self.barcode_scanner = BarcodeScanner()
        self.db_manager = DatabaseManager("inventory.db")
        self.order_manager = OrderManager()
        main_layout = BoxLayout(orientation="vertical")
        button_layout = GridLayout(cols=2, size_hint_y=1 / 3)

        self.display = TextInput(
            text="",
            multiline=True,
            readonly=True,
            halign="left",
            font_size=30,
            size_hint_y=2 / 3,
        )

        main_layout.add_widget(self.display)
        main_layout.add_widget(button_layout)

        buttons = [
            "Custom Item",
            "Clear Item",
            "Pay",
            "Tools",
        ]

        for button in buttons:
            button_layout.add_widget(Button(text=button, on_press=self.on_button_press))

        Clock.schedule_interval(self.check_for_scanned_barcode, 0.1)
        Clock.schedule_interval(self.check_monitor_status, 5)

        return main_layout

    def is_monitor_off(self):
        try:
            result = subprocess.run(['xset', '-q'], stdout=subprocess.PIPE)
            output = result.stdout.decode('utf-8')

            # Check if "Monitor is Off" is in the command output
            return "Monitor is Off" in output
        except Exception as e:
            print(f"Error checking monitor status: {e}")
            return False
    def check_monitor_status(self, dt):
        if not self.is_guard_screen_displayed and not self.is_lock_screen_displayed:
            if self.is_monitor_off():
                self.show_lock_screen()
                self.show_guard_screen()
                return 10  # Delay next check for 10 seconds
        return 1  # Check every second otherwise
    # def on_lock_screen_button_press(self, instance):
    #     # Append the pressed button's text to the entered PIN
    #     self.entered_pin += instance.text
    #
    #     # Check if the entered PIN has the required number of digits (e.g., 4)
    #     if len(self.entered_pin) == 4:
    #         if self.entered_pin == self.correct_pin:
    #             self.lock_popup.dismiss()  # Dismiss the lock screen if PIN is correct
    #             self.entered_pin = ""  # Reset entered PIN
    #         else:
    #             # Optionally, show an error message or clear the entered PIN
    #             self.entered_pin = ""  # Reset entered PIN for a new attempt


    """
    Barcode functions
    """

    def check_for_scanned_barcode(self, dt):
        if self.barcode_scanner.is_barcode_ready():
            barcode = self.barcode_scanner.read_barcode()
            print(f"Barcode scanned: {barcode}")  # Debug print
            self.handle_scanned_barcode(barcode)

    def handle_scanned_barcode(self, barcode):
        try:
            item_details = self.db_manager.get_item_details(barcode)
            if item_details:
                self.last_scanned_item = item_details
                print(item_details)
                item_name, item_price = item_details
                self.order_manager.items.append((item_name, item_price))
                self.order_manager.total += item_price
                self.update_display()

                return item_details
            else:
                self.show_add_or_bypass_popup(barcode)
        except Exception as e:
            print(f"Error handling scanned barcode: {e}")

    def show_add_or_bypass_popup(self, barcode):
        popup_layout = BoxLayout(orientation="vertical", spacing=10)
        for option in ["Add Custom Item", "Add to Database"]:
            btn = Button(
                text=option, on_press=lambda x: self.on_add_or_bypass_choice(x, barcode)
            )
            popup_layout.add_widget(btn)

        self.popup = Popup(
            title="Item Not Found", content=popup_layout, size_hint=(0.8, 0.6)
        )
        self.popup.open()

    def on_add_or_bypass_choice(self, instance, barcode):
        if instance.text == "Add Custom Item":
            self.show_custom_item_popup(barcode)
            self.popup.dismiss()
        elif instance.text == "Add to Database":
            self.show_add_to_database_popup(barcode)

    """
    Button handlers
    """

    def on_payment_button_press(self, instance):
        if instance.text == "Pay Cash":
            self.show_cash_payment_popup()
        elif instance.text == "Pay Card":
            self.handle_card_payment()
        elif instance.text == "Cancel":
            self.popup.dismiss()

    def on_numeric_button_press(self, instance):
        current_input = self.cash_input.text.replace(".", "").lstrip("0")
        new_input = current_input + instance.text
        new_input = new_input.zfill(2)
        cents = int(new_input)
        dollars = cents // 100
        remaining_cents = cents % 100
        self.cash_input.text = f"{dollars}.{remaining_cents:02d}"

    def on_tool_button_press(self, instance):
        if instance.text == "Clear Order":
            self.display.text = ""
            self.order_manager.clear_order()
        elif instance.text == "Open Register":
            open_cash_drawer()
        elif instance.text == "Inventory":
            self.show_inventory()
        elif instance.text == "Reporting":
            self.show_reporting_popup()
        self.tools_popup.dismiss()

    def on_button_press(self, instance):
        current = self.display.text
        button_text = instance.text

        if button_text == "Clear Order":
            self.display.text = ""
            self.order_manager.clear_order()
        elif button_text == "Pay":
            self.finalize_order()
        elif button_text == "Custom Item":
            self.show_custom_item_popup(barcode="1234567890")
        elif button_text == "Tools":
            # self.show_add_to_database_popup("12321321414") ##################TEST REMOVE ME
            self.show_tools_popup()
        elif button_text == "Clear Item" and self.last_scanned_item:
            item_name, item_price = self.last_scanned_item
            item_tuple = (item_name, item_price)

            if item_tuple in self.order_manager.items:
                self.order_manager.items.remove(item_tuple)
                self.order_manager.total -= item_price
                self.update_display()
            else:
                print("nothing to remove")
        else:
            self.display.text = current + button_text

    def on_done_button_press(self, instance):
        order_details = self.order_manager.get_order_details()
        self.send_order_to_history_database(
            order_details, self.order_manager, self.db_manager
        )
        self.order_manager.clear_order()

        self.payment_popup.dismiss()
        self.display.text = ""

    """
    Popup display functions
    """

    def show_guard_screen(self):
        if not self.is_guard_screen_displayed:
            guard_layout = BoxLayout()
            guard_popup = Popup(
                title="Guard Screen",
                content=guard_layout,
                size_hint=(1, 1),
                auto_dismiss=False
            )
            guard_popup.bind(on_touch_down=lambda instance, touch: guard_popup.dismiss())
            guard_popup.open()

    def show_lock_screen(self):
        if not self.is_lock_screen_displayed:
            lock_layout = BoxLayout(orientation="vertical")
            keypad_layout = GridLayout(cols=3)

            numeric_buttons = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "*", "0", "#"]
            for button in numeric_buttons:
                btn = Button(text=button, on_press=self.on_lock_screen_button_press)
                keypad_layout.add_widget(btn)

            lock_layout.add_widget(keypad_layout)
            self.lock_popup = Popup(
                title="Lock Screen",
                content=lock_layout,
                size_hint=(1, 1),
                auto_dismiss=False
            )
            self.lock_popup.open()

    def on_lock_screen_button_press(self, instance):
        # Append the pressed button's text to the entered PIN
        self.entered_pin += instance.text

        # Check if the entered PIN has the required number of digits (e.g., 4)
        if len(self.entered_pin) == 4:
            if self.entered_pin == self.correct_pin:
                self.lock_popup.dismiss()  # Dismiss the lock screen if PIN is correct
                self.entered_pin = ""  # Reset entered PIN
            else:
                # Optionally, show an error message or clear the entered PIN
                self.entered_pin = ""  # Reset entered PIN for a new attempt



    def show_inventory(self):
        inventory = self.db_manager.get_all_items()
        inventory_view = InventoryView()
        inventory_view.show_inventory(inventory)
        popup = Popup(title="Inventory", content=inventory_view, size_hint=(0.9, 0.9))
        popup.open()

    def show_reporting_popup(self):
        order_history = self.db_manager.get_order_history()
        history_view = HistoryView()
        history_view.show_reporting_popup(order_history)
        popup = Popup(title="Order History", content=history_view, size_hint=(0.9, 0.9))
        popup.open()

    def show_tools_popup(self):
        tools_layout = BoxLayout(orientation="vertical", spacing=10)
        tool_buttons = ["Clear Order", "Open Register", "Inventory", "Reporting"]

        for tool in tool_buttons:
            btn = Button(text=tool, on_press=self.on_tool_button_press)
            tools_layout.add_widget(btn)

        self.tools_popup = Popup(
            title="Tools", content=tools_layout, size_hint=(0.5, 0.5)
        )
        self.tools_popup.open()

    def show_custom_item_popup(self, barcode):
        self.custom_item_popup_layout = BoxLayout(orientation="vertical", spacing=10)
        self.cash_input = TextInput(
            text="",
            multiline=False,
            input_filter="float",
            font_size=30,
            size_hint_y=None,
            height=50,
        )
        self.custom_item_popup_layout.add_widget(self.cash_input)

        keypad_layout = GridLayout(cols=3, spacing=10)

        numeric_buttons = [
            "1",
            "2",
            "3",
            "4",
            "5",
            "6",
            "7",
            "8",
            "9",
            "0",
        ]
        for button in numeric_buttons:
            btn = Button(text=button, on_press=self.on_numeric_button_press)
            keypad_layout.add_widget(btn)

        confirm_button = Button(text="Confirm", on_press=self.add_custom_item)
        keypad_layout.add_widget(confirm_button)

        cancel_button = Button(text="Cancel", on_press=self.on_custom_item_cancel)
        keypad_layout.add_widget(cancel_button)

        self.custom_item_popup_layout.add_widget(keypad_layout)
        self.custom_item_popup = Popup(
            title="Enter Cash Amount",
            content=self.custom_item_popup_layout,
            size_hint=(0.8, 0.8),
        )
        self.custom_item_popup.open()

    def show_order_popup(self, order_summary):
        popup_layout = BoxLayout(orientation="vertical", spacing=10)
        popup_layout.add_widget(Label(text=order_summary))

        button_layout = BoxLayout(size_hint_y=None, height=50)
        for payment_method in ["Pay Cash", "Pay Card", "Cancel"]:
            btn = Button(text=payment_method, on_press=self.on_payment_button_press)
            button_layout.add_widget(btn)
        popup_layout.add_widget(button_layout)

        self.popup = Popup(
            title="Finalize Order", content=popup_layout, size_hint=(0.8, 0.8)
        )
        self.popup.open()

    def show_cash_payment_popup(self):
        self.cash_popup_layout = BoxLayout(orientation="vertical", spacing=10)
        self.cash_input = TextInput(
            text="",
            multiline=False,
            input_filter="float",
            font_size=30,
            size_hint_y=None,
            height=50,
        )
        self.cash_popup_layout.add_widget(self.cash_input)

        keypad_layout = GridLayout(cols=3, spacing=10)

        numeric_buttons = [
            "1",
            "2",
            "3",
            "4",
            "5",
            "6",
            "7",
            "8",
            "9",
            "0",
        ]
        for button in numeric_buttons:
            btn = Button(text=button, on_press=self.on_numeric_button_press)
            keypad_layout.add_widget(btn)

        confirm_button = Button(text="Confirm", on_press=self.on_cash_confirm)
        keypad_layout.add_widget(confirm_button)

        cancel_button = Button(text="Cancel", on_press=self.on_cash_cancel)
        keypad_layout.add_widget(cancel_button)

        self.cash_popup_layout.add_widget(keypad_layout)
        self.cash_popup = Popup(
            title="Enter Cash Amount",
            content=self.cash_popup_layout,
            size_hint=(0.8, 0.8),
        )
        self.cash_popup.open()

    def show_payment_confirmation_popup(self):
        confirmation_layout = BoxLayout(orientation="vertical", spacing=10)
        order_summary = f"Order Complete:\n{self.display.text}\nOrder saved to the history database."
        confirmation_layout.add_widget(Label(text=order_summary))

        done_button = Button(
            text="Done", size_hint_y=None, height=50, on_press=self.on_done_button_press
        )
        confirmation_layout.add_widget(done_button)

        self.payment_popup = Popup(
            title="Payment Confirmation",
            content=confirmation_layout,
            size_hint=(0.8, 0.5),
        )
        self.popup.dismiss()
        self.payment_popup.open()

    def show_make_change_popup(self, change):
        change_layout = BoxLayout(orientation="vertical", spacing=10)
        change_layout.add_widget(Label(text=f"Change to return: ${change:.2f}"))

        done_button = Button(
            text="Done", size_hint_y=None, height=50, on_press=self.on_change_done
        )
        change_layout.add_widget(done_button)

        self.change_popup = Popup(
            title="Change Calculation", content=change_layout, size_hint=(0.6, 0.3)
        )
        self.change_popup.open()



    def show_add_to_database_popup(self, barcode):
        popup_layout = BoxLayout(orientation="vertical", spacing=10)

        barcode_input = TextInput(
            text=barcode, multiline=False, size_hint_y=None, height=50
        )
        name_input = TextInput(
            hint_text="Name", multiline=False, size_hint_y=None, height=50
        )
        price_input = TextInput(
            hint_text="Price",
            multiline=False,
            size_hint_y=None,
            height=50,
            input_filter="float",
        )

        for text_input in [barcode_input, name_input, price_input]:
            text_input.bind(focus=self.on_input_focus)

        popup_layout.add_widget(barcode_input)
        popup_layout.add_widget(name_input)
        popup_layout.add_widget(price_input)

        cancel_button = Button(
            text="Cancel",
            size_hint_y=None,
            height=50,
            on_press=self.close_add_to_database_popup,
        )
        confirm_button = Button(
            text="Confirm",
            size_hint_y=None,
            height=50,
            on_press=lambda instance: (
                self.add_item_to_database(barcode, name_input.text, price_input.text),
                self.close_add_to_database_popup(instance),
            ),
        )

        popup_layout.add_widget(cancel_button)
        popup_layout.add_widget(confirm_button)

        self.add_to_db_popup = Popup(
            title="Add to Database",
            content=popup_layout,
            size_hint=(0.8, 0.4),
            auto_dismiss=False,
            pos_hint={"top": 1},
        )

        self.add_to_db_popup.open()

    def on_input_focus(self, instance, value):
        if value:
            # instance.keyboard_mode = 'managed'
            instance.show_keyboard()
        else:
            instance.hide_keyboard()

    def close_add_to_database_popup(self, instance):
        self.add_to_db_popup.dismiss()

    """
    Accessory functions
    """

    def finalize_order(self):
        total_with_tax = self.order_manager.calculate_total_with_tax()
        print(total_with_tax)
        order_summary = f"Order Summary:\n{self.display.text}\nTotal with Tax: ${total_with_tax:.2f}"
        self.show_order_popup(order_summary)

    def update_display(self):
        self.display.text = ""

        for item_name, item_price in self.order_manager.items:
            self.display.text += f"{item_name}  ${item_price:.2f}\n"

        subtotal_with_tax = self.order_manager.calculate_total_with_tax()
        if subtotal_with_tax > 0:
            self.display.text += f"\nSubtotal with tax: ${subtotal_with_tax:.2f}"
        else:
            self.display.text = ""

    def handle_card_payment(self):
        open_cash_drawer()
        self.show_payment_confirmation_popup()

    def on_change_done(self, instance):
        self.change_popup.dismiss()
        #open_cash_drawer()
        self.show_payment_confirmation_popup()

    def on_cash_cancel(self, instance):
        self.cash_popup.dismiss()

    def on_cash_confirm(self, instance):
        amount_tendered = float(self.cash_input.text)
        total_with_tax = self.order_manager.calculate_total_with_tax()
        change = amount_tendered - total_with_tax
        self.cash_popup.dismiss()
        open_cash_drawer()
        self.show_make_change_popup(change)

    def add_custom_item(self, instance):
        price = self.cash_input.text
        try:
            price = float(price)
        except ValueError:
            return

        custom_item_name = "Custom Item"
        self.order_manager.items.append((custom_item_name, price))
        self.order_manager.total += price
        item_details = custom_item_name, price
        self.last_scanned_item = item_details
        self.update_display()
        self.custom_item_popup.dismiss()

    def on_custom_item_cancel(self, instance):
        self.custom_item_popup.dismiss()

    def send_order_to_history_database(self, order_details, order_manager, db_manager):
        tax = order_details["total_with_tax"] - order_details["total"]
        timestamp = time.time()
        db_manager.add_order_history(
            order_details["order_id"],
            json.dumps(order_details["items"]),
            order_details["total"],
            tax,
            order_details["total_with_tax"],
            timestamp

        )

    def add_item_to_database(self, barcode, name, price):
        try:
            if self.db_manager.add_item(barcode, name, price):
                print(f"Item '{name}' added to the database.")
        except Exception as e:
            print(f"Error adding item to database: {e}")
        finally:
            pass


if __name__ == "__main__":
    CashRegisterApp().run()
