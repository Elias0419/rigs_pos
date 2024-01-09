from kivy.config import Config

Config.set("kivy", "keyboard_mode", "systemanddock")

import json
import datetime
import subprocess

from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.lang import Builder
from kivy.metrics import dp
from kivy.properties import StringProperty, ListProperty, ObjectProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.gridlayout import GridLayout
from kivy.uix.scrollview import ScrollView
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
    barcode = StringProperty()
    name = StringProperty()
    price = StringProperty()
    order_manager = ObjectProperty()

    def __init__(self, **kwargs):
        super(InventoryRow, self).__init__(**kwargs)
        self.order_manager = OrderManager()

    def add_to_order(self):
        print(f"Adding {self.name} to order")
        print(self.price)
        print(type(self.price))
        self.order_manager.add_item(self.name, self.price)
        app = App.get_running_app()
        app.update_display()


class HistoryRow(BoxLayout):
    pass


class InventoryView(BoxLayout):
    def __init__(self, order_manager, **kwargs):
        super(InventoryView, self).__init__(**kwargs)
        self.order_manager = order_manager

    def show_inventory(self, inventory_items):
        self.full_inventory = inventory_items
        data = self.generate_data_for_rv(inventory_items)
        for item in data:
            item["order_manager"] = self.order_manager
        self.rv.data = data

    def generate_data_for_rv(self, items):
        return [
            {
                "barcode": str(item[0]),
                "name": item[1],
                "price": str(item[2]),
                "order_manager": self.order_manager,
            }
            for item in items
        ]

    def filter_inventory(self, query):
        if query:
            query = query.lower()
            filtered_items = [
                item for item in self.full_inventory if query in item[1].lower()
            ]
        else:
            filtered_items = self.full_inventory
        self.rv.data = self.generate_data_for_rv(filtered_items)


class HistoryView(BoxLayout):
    def show_reporting_popup(self, order_history):
        self.rv.data = [
            {
                "items": str(order[1]),
                "total": str(order[2]),
                "tax": str(order[3]),
                "total_with_tax": str(order[4]),
                "timestamp": str(order[5]),
            }  # TODO look in truncating/wrapping/collapsing items
            for order in order_history
        ]


class CashRegisterApp(App):
    def __init__(self, **kwargs):
        super(CashRegisterApp, self).__init__(**kwargs)
        self.last_scanned_item = None
        self.correct_pin = "1234"
        self.entered_pin = ""
        self.is_guard_screen_displayed = False
        self.is_lock_screen_displayed = False

    def build(self):
        self.barcode_scanner = BarcodeScanner()
        self.db_manager = DatabaseManager("inventory.db")
        self.order_manager = OrderManager()
        main_layout = BoxLayout(orientation="vertical")
        button_layout = GridLayout(cols=2, size_hint_y=1 / 3)

        self.order_layout = BoxLayout(orientation="vertical", size_hint_y=None)
        self.order_layout.bind(minimum_height=self.order_layout.setter("height"))

        self.scroll_view = ScrollView(size_hint_y=2 / 3)
        self.scroll_view.add_widget(self.order_layout)

        main_layout.add_widget(self.scroll_view)
        main_layout.add_widget(button_layout)

        buttons = [
            "Custom Item",
            "Inventory",
            "Pay",
            "Tools",
        ]

        for button in buttons:
            button_layout.add_widget(Button(text=button, on_press=self.on_button_press))

        Clock.schedule_interval(self.check_for_scanned_barcode, 0.1)

        if not hasattr(self, "monitor_check_scheduled"):
            Clock.schedule_interval(self.check_monitor_status, 5)
            self.monitor_check_scheduled = True

        return main_layout

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
                item_name, item_price = item_details
                self.order_manager.items.append(
                    {"name": item_name, "price": item_price}
                )
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
            self.order_layout.clear_widgets()
            self.order_manager.clear_order()
        elif instance.text == "Open Register":
            open_cash_drawer()
        # elif instance.text == "Inventory":
        #     self.show_inventory()
        elif instance.text == "Reporting":
            self.show_reporting_popup()
        # elif instance.text == "Tax Adjustment":
        #     self.show_adjust_price_popup()
        self.tools_popup.dismiss()

    def on_button_press(self, instance):
        button_text = instance.text

        if button_text == "Clear Order":
            self.order_layout.clear_widgets()
            self.order_manager.clear_order()
        elif button_text == "Pay":
            self.finalize_order()
        elif button_text == "Custom Item":
            self.show_custom_item_popup(barcode="1234567890")
        elif button_text == "Tools":
            self.show_tools_popup()
        elif button_text == "Inventory":
            self.show_inventory()

    def on_done_button_press(self, instance):
        order_details = self.order_manager.get_order_details()
        self.send_order_to_history_database(
            order_details, self.order_manager, self.db_manager
        )
        self.order_manager.clear_order()

        self.payment_popup.dismiss()
        self.order_layout.clear_widgets()

    def on_item_click(self, instance):
        # instance.text will contain the item details
        # Extract item details from the button's text
        item_details = instance.text.split("  $")
        item_name = item_details[0]
        item_price = item_details[1]

        # Create a popup to show item details and modification options
        item_popup_layout = BoxLayout(orientation="vertical", spacing=10)
        item_popup_layout.add_widget(Label(text=f"Name: {item_name}"))
        item_popup_layout.add_widget(Label(text=f"Price: ${item_price}"))

        # Add buttons or other widgets for modification options (e.g., remove item)
        modify_button = Button(
            text="Modify Item",
            on_press=lambda x: self.modify_item(item_name, item_price),
        )
        item_popup_layout.add_widget(modify_button)
        adjust_price_button = Button(
            text="Adjust Price with Tax",
            on_press=lambda x: self.show_adjust_price_popup(item_name, item_price),
        )
        item_popup_layout.add_widget(adjust_price_button)
        remove_button = Button(
            text="Remove Item",
            on_press=lambda x: self.remove_item(item_name, item_price),
        )
        item_popup_layout.add_widget(remove_button)

        cancel_button = Button(
            text="Cancel", on_press=lambda x: self.close_item_popup()
        )
        item_popup_layout.add_widget(cancel_button)

        self.item_popup = Popup(
            title="Item Details", content=item_popup_layout, size_hint=(0.6, 0.4)
        )
        self.item_popup.open()

    def modify_item(self, item_name, item_price):
        # Logic to modify the selected item
        pass

    def remove_item(self, item_name, item_price):
        # Logic to remove the selected item
        pass

    def close_item_popup(self):
        # Close the item details popup
        if self.item_popup:
            self.item_popup.dismiss()

    """
    Popup display functions
    """

    def show_adjust_price_popup(self, item_name, item_price):
        self.current_item_name = item_name
        self.current_item_price = item_price
        self.adjust_price_popup_layout = BoxLayout(orientation="vertical", spacing=10)
        self.target_amount_input = TextInput(
            text="",
            multiline=False,
            input_filter="float",
            font_size=30,
            size_hint_y=None,
            height=50,
        )
        self.adjust_price_popup_layout.add_widget(self.target_amount_input)

        confirm_button = Button(text="Confirm", on_press=self.add_adjusted_price_item)
        self.adjust_price_popup_layout.add_widget(confirm_button)

        cancel_button = Button(text="Cancel", on_press=self.on_adjust_price_cancel)
        self.adjust_price_popup_layout.add_widget(cancel_button)

        self.adjust_price_popup = Popup(
            title="Enter Target Amount",
            content=self.adjust_price_popup_layout,
            size_hint=(0.8, 0.4),
            pos_hint={"top": 1},
        )
        self.adjust_price_popup.open()

    def show_guard_screen(self):
        if not self.is_guard_screen_displayed:
            print("Guard screen triggered", datetime.datetime.now())
            guard_layout = BoxLayout()
            guard_popup = Popup(
                title="Guard Screen",
                content=guard_layout,
                size_hint=(1, 1),
                auto_dismiss=False,
            )
            guard_popup.bind(
                on_touch_down=lambda instance, touch: guard_popup.dismiss()
            )
            self.is_guard_screen_displayed = True
            guard_popup.bind(
                on_dismiss=lambda instance: setattr(
                    self, "is_guard_screen_displayed", False
                )
            )
            guard_popup.open()

    def show_lock_screen(self):
        if not self.is_lock_screen_displayed:
            print("Lock screen triggered", datetime.datetime.now())

            lock_layout = BoxLayout(orientation="vertical")
            keypad_layout = GridLayout(cols=3)

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
                "*",
                "0",
                "#",
            ]
            for button in numeric_buttons:
                btn = Button(text=button, on_press=self.on_lock_screen_button_press)
                keypad_layout.add_widget(btn)

            lock_layout.add_widget(keypad_layout)
            self.lock_popup = Popup(
                title="Lock Screen",
                content=lock_layout,
                size_hint=(1, 1),
                auto_dismiss=False,
            )
            self.is_lock_screen_displayed = True
            self.lock_popup.bind(
                on_dismiss=lambda instance: setattr(
                    self, "is_lock_screen_displayed", False
                )
            )
            self.lock_popup.open()

    def on_lock_screen_button_press(self, instance):
        self.entered_pin += instance.text

        if len(self.entered_pin) == 4:
            if self.entered_pin == self.correct_pin:
                self.lock_popup.dismiss()
                self.entered_pin = ""
            else:
                self.entered_pin = ""

    def show_inventory(self):
        inventory = self.db_manager.get_all_items()
        inventory_view = InventoryView(order_manager=self.order_manager)
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
        tool_buttons = [
            "Clear Order",
            "Open Register",
            "Inventory",
            "Reporting",
            # "Tax Adjustment",
        ]

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

        confirm_button = Button(
            text="Confirm", on_press=self.add_custom_item
        )  ############
        keypad_layout.add_widget(confirm_button)

        cancel_button = Button(text="Cancel", on_press=self.on_custom_item_cancel)
        keypad_layout.add_widget(cancel_button)

        self.custom_item_popup_layout.add_widget(keypad_layout)
        self.custom_item_popup = Popup(
            title="Custom Item",
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

        # Generate the order summary from the order_manager
        order_summary = "Order Complete:\n"
        for item_name, item_price in self.order_manager.items:
            order_summary += f"{item_name}  ${item_price:.2f}\n"
        order_summary += "Order saved to the history database."

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
        self.popup.dismiss()  # Close the previous popup if any
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

    def add_adjusted_price_item(self, instance):
        target_amount = self.target_amount_input.text
        try:
            target_amount = float(target_amount)
        except ValueError:
            return

        tax_rate = 0.07
        adjusted_price = target_amount / (1 + tax_rate)

        # Update the specific item's price
        self.order_manager.update_item_price(self.current_item_name, adjusted_price)
        self.update_display()
        self.adjust_price_popup.dismiss()

    def is_monitor_off(self):
        try:
            result = subprocess.run(["xset", "-q"], stdout=subprocess.PIPE)
            output = result.stdout.decode("utf-8")
            return "Monitor is Off" in output
        except Exception as e:
            print(f"Error checking monitor status: {e}")
            return False

    def check_monitor_status(self, dt):
        if self.is_monitor_off():
            if not self.is_guard_screen_displayed and not self.is_lock_screen_displayed:
                self.show_lock_screen()
                self.show_guard_screen()
        else:
            self.is_guard_screen_displayed = False
            self.is_lock_screen_displayed = False

    def finalize_order(self):
        total_with_tax = self.order_manager.calculate_total_with_tax()
        print(total_with_tax)

        # Generate the order summary from the order_manager
        order_summary = "Order Summary:\n"
        for item_name, item_price in self.order_manager.items:
            order_summary += f"{item_name}  ${item_price:.2f}\n"
        order_summary += f"Total with Tax: ${total_with_tax:.2f}"

        self.show_order_popup(order_summary)

    def update_display(self):
        self.order_layout.clear_widgets()

        for item in self.order_manager.items:
            item_name = item["name"]
            try:
                item_price = float(
                    item["price"]
                )  # item['price'] is already a string representing a float
            except ValueError:
                print(f"Invalid item price for {item_name}: {item['price']}")
                continue

            item_button = Button(
                text=f"{item_name}  ${item_price:.2f}", size_hint_y=None, height=40
            )
            item_button.bind(on_press=self.on_item_click)
            self.order_layout.add_widget(item_button)

        subtotal_with_tax = self.order_manager.calculate_total_with_tax()
        if subtotal_with_tax > 0:
            subtotal_label = Label(
                text=f"\nSubtotal with tax: ${subtotal_with_tax:.2f}",
                size_hint_y=None,
                height=40,
            )
            self.order_layout.add_widget(subtotal_label)

    def handle_card_payment(self):
        open_cash_drawer()
        self.show_payment_confirmation_popup()

    def on_change_done(self, instance):
        self.change_popup.dismiss()
        # open_cash_drawer()
        self.show_payment_confirmation_popup()

    def on_cash_cancel(self, instance):
        self.cash_popup.dismiss()

    def on_adjust_price_cancel(self, instance):
        self.adjust_price_popup.dismiss()

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
        self.order_manager.items.append({"name": custom_item_name, "price": price})
        self.order_manager.total += price
        self.update_display()
        self.custom_item_popup.dismiss()

    def on_custom_item_cancel(self, instance):
        self.custom_item_popup.dismiss()

    def send_order_to_history_database(self, order_details, order_manager, db_manager):
        tax = order_details["total_with_tax"] - order_details["total"]
        timestamp = datetime.datetime.now()
        db_manager.add_order_history(
            order_details["order_id"],
            json.dumps(order_details["items"]),
            order_details["total"],
            tax,
            order_details["total_with_tax"],
            timestamp,
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
