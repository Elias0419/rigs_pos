import json

from kivy.app import App
from kivy.clock import Clock
from kivy.config import Config
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
# from open_cash_drawer import open_cash_drawer
from mock_open_cash_drawer import open_cash_drawer

Config.set('kivy', 'keyboard_mode', '')

class InventoryRow(BoxLayout):
    pass

kv = """
<InventoryRow>:
    barcode: barcode
    name: name
    price: price

    Label:
        id: barcode
        text: str(root.barcode)
    Label:
        id: name
        text: str(root.name)
    Label:
        id: price
        text: str(root.price)

<InventoryView>:
    orientation: 'vertical'
    rv: rv
    RecycleView:
        id: rv
        viewclass: 'InventoryRow'
        RecycleBoxLayout:
            default_size: None, dp(56)
            default_size_hint: 1, None
            size_hint_y: None
            height: self.minimum_height
            orientation: 'vertical'
"""

Builder.load_string(kv)

class InventoryView(BoxLayout):

    def show_inventory(self, inventory_items):
        self.rv.data = [{'barcode': str(item[0]), 'name': item[1], 'price': str(item[2])} for item in inventory_items]


class CashRegisterApp(App):
    def __init__(self, **kwargs):
        super(CashRegisterApp, self).__init__(**kwargs)
        self.last_scanned_item = None

    def build(self):
        self.barcode_scanner = BarcodeScanner()
        self.db_manager = DatabaseManager("inventory.db")

        self.order_manager = OrderManager()
        main_layout = BoxLayout(orientation="vertical")
        button_layout = GridLayout(cols=2, size_hint_y=1/3)

        self.display = TextInput(
            text="", multiline=True, readonly=True, halign="left", font_size=30, size_hint_y=2/3
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

        return main_layout

    def check_for_scanned_barcode(self, dt):
        if self.barcode_scanner.is_barcode_ready():
            barcode = self.barcode_scanner.read_barcode()
            print(f"Barcode scanned: {barcode}")  # Debug print
            self.handle_scanned_barcode(barcode)

    """
    Barcode functions
    """

    def handle_scanned_barcode(self, barcode):
        try:
            item_details = self.db_manager.get_item_details(barcode)
            if item_details:
                self.last_scanned_item = item_details
                print(item_details)
                item_name, item_price = item_details
                self.order_manager.items.append((item_name, item_price))
                self.order_manager.total += item_price
                # self.display.text += f"{item_name}  ${item_price}\n"
                # subtotal_with_tax = self.order_manager.calculate_total_with_tax()
                # self.display.text += f"Subtotal with tax: {subtotal_with_tax}\n"
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


    def update_display(self):
        # Clear the current display
        self.display.text = ''

        # Add all items to the display
        for item_name, item_price in self.order_manager.items:
            self.display.text += f"{item_name}  ${item_price:.2f}\n"

        # Calculate and display the subtotal with tax
        subtotal_with_tax = self.order_manager.calculate_total_with_tax()
        if subtotal_with_tax > 0:
            self.display.text += f"\nSubtotal with tax: ${subtotal_with_tax:.2f}"
        else:
            self.display.text = ""

    def show_tools_popup(self):
        tools_layout = BoxLayout(orientation="vertical", spacing=10)
        tool_buttons = ["Clear Order", "Open Register", "Inventory"]

        for tool in tool_buttons:
            btn = Button(text=tool, on_press=self.on_tool_button_press)
            tools_layout.add_widget(btn)

        self.tools_popup = Popup(
            title="Tools",
            content=tools_layout,
            size_hint=(0.5, 0.5)
        )
        self.tools_popup.open()

    def on_tool_button_press(self, instance):
        if instance.text == "Clear Order":
            self.display.text = ""
            self.order_manager.clear_order()
        elif instance.text == "Open Register":
            open_cash_drawer()
        elif instance.text == "Inventory":
            self.show_inventory()
        self.tools_popup.dismiss()

    """
    Order management functions
    """

    def finalize_order(self):
        total_with_tax = self.order_manager.calculate_total_with_tax()
        print(total_with_tax)
        order_summary = f"Order Summary:\n{self.display.text}\nTotal with Tax: ${total_with_tax:.2f}"
        self.show_order_popup(order_summary)



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
            self.show_add_to_database_popup("12321321414") ##################TEST REMOVE ME
            #self.show_tools_popup()
        elif button_text == "Clear Item"and self.last_scanned_item:
            item_name, item_price = self.last_scanned_item
            item_tuple = (item_name, item_price)

            # Check if the item is in the order before attempting to remove it
            if item_tuple in self.order_manager.items:
                self.order_manager.items.remove(item_tuple)
                self.order_manager.total -= item_price
                self.update_display()
            else:
                print("nothing to remove")
            # if item_string in self.display.text:
            #     self.display.text = self.display.text.replace(item_string, '', 1)
            #     self.order_manager.items.remove((item_name, item_price))
            #     self.order_manager.total -= item_price

        #
        # elif button_text == "Open Register":
        #     open_cash_drawer()
        # elif button_text == "Inventory":
        #     self.show_inventory()
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
        order_summary = f"Order Summary:\n{self.display.text}\nPaid with card"
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


    def show_inventory(self):
        inventory = self.db_manager.get_all_items()
        inventory_view = InventoryView()
        inventory_view.show_inventory(inventory)
        popup = Popup(title="Inventory", content=inventory_view, size_hint=(0.9, 0.9))
        popup.open()


    def show_add_to_database_popup(self, barcode):

        popup_layout = BoxLayout(orientation='vertical', spacing=10)


        barcode_input = TextInput(text=barcode, multiline=False, size_hint_y=None, height=50)
        name_input = TextInput(hint_text='Name', multiline=False, size_hint_y=None, height=50)
        price_input = TextInput(hint_text='Price', multiline=False, size_hint_y=None, height=50, input_filter='float')

        for text_input in [barcode_input, name_input, price_input]:
            text_input.bind(focus=self.on_input_focus)


        popup_layout.add_widget(barcode_input)
        popup_layout.add_widget(name_input)
        popup_layout.add_widget(price_input)


        cancel_button = Button(text='Cancel', size_hint_y=None, height=50, on_press=self.close_add_to_database_popup)
        confirm_button = Button(
            text='Confirm',
            size_hint_y=None,
            height=50,
            on_press=lambda instance: (
                self.add_item_to_database(barcode, name_input.text, price_input.text),
                self.close_add_to_database_popup(instance)
            )
        )



        # cancel_button.bind(on_press=lambda x: self.close_add_to_database_popup)
        #confirm_button.bind(on_press=lambda x: self.placeholder_confirm())


        popup_layout.add_widget(cancel_button)
        popup_layout.add_widget(confirm_button)


        self.add_to_db_popup = Popup(title="Add to Database",
                                    content=popup_layout,
                                    size_hint=(0.8, 0.5),
                                    auto_dismiss=False,
                                    pos_hint={'top': 1})

        # Open the popup
        self.add_to_db_popup.open()

    def on_input_focus(self, instance, value):
        if value:
            # If the TextInput is focused, show the keyboard
            instance.keyboard_mode = 'managed'
            instance.show_keyboard()
        else:
            # If the TextInput loses focus, hide the keyboard
            instance.hide_keyboard()

    def close_add_to_database_popup(self, instance):
        self.add_to_db_popup.dismiss()


    """
    Payment functions
    """

    def on_payment_button_press(self, instance):
        if instance.text == "Pay Cash":
            self.show_cash_payment_popup()
        elif instance.text == "Pay Card":
            self.handle_card_payment()
        elif instance.text == "Cancel":
            self.popup.dismiss()

    def handle_card_payment(self):
        open_cash_drawer()
        self.show_payment_confirmation_popup()

    def on_change_done(self, instance):
        self.change_popup.dismiss()
        open_cash_drawer()
        self.show_payment_confirmation_popup()

    def on_numeric_button_press(self, instance):
        current_input = self.cash_input.text.replace(".", "").lstrip("0")
        new_input = current_input + instance.text
        new_input = new_input.zfill(2)
        cents = int(new_input)
        dollars = cents // 100
        remaining_cents = cents % 100

        self.cash_input.text = f"{dollars}.{remaining_cents:02d}"

    def on_cash_cancel(self, instance):
        self.cash_popup.dismiss()

    def on_cash_confirm(self, instance):
        amount_tendered = float(self.cash_input.text)
        total_with_tax = self.order_manager.calculate_total_with_tax()
        change = amount_tendered - total_with_tax
        self.cash_popup.dismiss()
        self.show_make_change_popup(change)

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
        item_details = custom_item_name, price
        self.last_scanned_item = item_details
        # self.display.text += f"{custom_item_name}  ${price:.2f}\n"
        # subtotal_with_tax = self.order_manager.calculate_total_with_tax()
        # self.display.text += f"Subtotal with tax: {subtotal_with_tax}\n"
        self.update_display()
        self.custom_item_popup.dismiss()

    def on_custom_item_cancel(self, instance):
        self.custom_item_popup.dismiss()

    #


if __name__ == "__main__":
    CashRegisterApp().run()




     # ....



   # This version is for touchscreens
    # def show_add_to_database_popup(self, barcode):
    #     # Create the layout
    #     popup_layout = BoxLayout(orientation="vertical", spacing=10)
    #
    #     # Create text inputs
    #     barcode_input = TextInput(
    #         text=barcode, multiline=False, size_hint_y=None, height=50
    #     )
    #     name_input = TextInput(
    #         hint_text="Name", multiline=False, size_hint_y=None, height=50
    #     )
    #     price_input = TextInput(
    #         hint_text="Price",
    #         multiline=False,
    #         size_hint_y=None,
    #         height=50,
    #         input_filter="float",
    #     )
    #
    #     # Add text inputs to layout
    #     popup_layout.add_widget(barcode_input)
    #     popup_layout.add_widget(name_input)
    #     popup_layout.add_widget(price_input)
    #
    #     # Create buttons
    #     cancel_button = Button(text="Cancel", size_hint_y=None, height=50)
    #     confirm_button = Button(text="Confirm", size_hint_y=None, height=50)
    #
    #     # Placeholder functions for buttons
    #     cancel_button.bind(on_press=lambda x: self.placeholder_cancel())
    #     confirm_button.bind(on_press=lambda x: self.placeholder_confirm())
    #
    #     # Add buttons to layout
    #     popup_layout.add_widget(cancel_button)
    #     popup_layout.add_widget(confirm_button)
    #
    #     # Create the popup
    #     self.add_to_db_popup = Popup(
    #         title="Add to Database",
    #         content=popup_layout,
    #         size_hint=(0.8, 0.8),
    #         auto_dismiss=False,
    #     )
    #
    #     # Open the popup
    #     self.add_to_db_popup.open()
    #
    #     # Request keyboard
    #     Window.request_keyboard(self._keyboard_closed, self)
    #     self._keyboard = Window.request_keyboard(self._keyboard_closed, self)
    #     self._keyboard.bind(on_key_down=self._on_keyboard_down)
    # def _keyboard_closed(self):
    #     self._keyboard.unbind(on_key_down=self._on_keyboard_down)
    #     self._keyboard = None
    #
    # def _on_keyboard_down(self, keyboard, keycode, text, modifiers):
    #     # Logic for handling key press events
    #     pass
