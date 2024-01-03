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
import json
# External Imports
from barcode_scanner import BarcodeScanner
from database_manager import DatabaseManager
from order_manager import OrderManager
#from open_cash_drawer import open_cash_drawer
from mock_open_cash_drawer import open_cash_drawer

class CashRegisterApp(App):
    def build(self):
        self.barcode_scanner = BarcodeScanner()
        self.db_manager = DatabaseManager("my_items_database.db")
        self.order_manager = OrderManager()
        main_layout = BoxLayout(orientation='horizontal')
        button_layout = GridLayout(cols=2)
        main_layout.add_widget(button_layout)
        self.display = TextInput(text='', multiline=True, readonly=True, halign='right', font_size=30)
        main_layout.add_widget(self.display)



        buttons = [
             'Manual Entry',
             'Clear Item',
             'Open Register',
            'Clear Order',  'Pay', 'Inventory'
        ]

        for button in buttons:
            button_layout.add_widget(Button(text=button, on_press=self.on_button_press))


        Clock.schedule_interval(self.check_for_scanned_barcode, 0.1)

        return main_layout

    def check_for_scanned_barcode(self, dt):
        #print("Checking for scanned barcode...")  # Debug print
        if self.barcode_scanner.is_barcode_ready():
            barcode = self.barcode_scanner.read_barcode()
            print(f"Barcode scanned: {barcode}")  # Debug print
            self.handle_scanned_barcode(barcode)

    def handle_scanned_barcode(self, barcode):
        print(f"Handling scanned barcode: {barcode}")  # Debug print
        try:
            item_details = self.db_manager.get_item_details(barcode)
            if item_details:
                print(item_details)
                item_name, item_price = item_details
                self.order_manager.items.append((item_name, item_price))
                self.order_manager.total += item_price
                self.display.text += f"{item_name}  ${item_price}\n"
            else:
                print(f"No details found for barcode: {barcode}")  # Debug print
        except Exception as e:
            print(f"Error handling scanned barcode: {e}")  # Error handling

    def finalize_order(self):
        # Logic to finalize the order
        total_with_tax = self.order_manager.calculate_total_with_tax()
        print(total_with_tax)
        order_summary = f"Order Summary:\n{self.display.text}\nTotal with Tax: ${total_with_tax:.2f}"
        self.show_order_popup(order_summary)

    def show_order_popup(self, order_summary):
        popup_layout = BoxLayout(orientation='vertical', spacing=10)
        popup_layout.add_widget(Label(text=order_summary))

        button_layout = BoxLayout(size_hint_y=None, height=50)
        for payment_method in ['Pay Cash', 'Pay Card', 'Cancel']:
            btn = Button(text=payment_method, on_press=self.on_payment_button_press)
            button_layout.add_widget(btn)
        popup_layout.add_widget(button_layout)

        self.popup = Popup(title='Finalize Order', content=popup_layout, size_hint=(0.8, 0.8))
        self.popup.open()

    def on_payment_button_press(self, instance):
        if instance.text == 'Pay Cash':
            self.show_cash_payment_popup()
        elif instance.text == 'Pay Card':
            self.handle_card_payment()
        elif instance.text == 'Cancel':
            self.popup.dismiss()

    def show_cash_payment_popup(self):
        self.cash_popup_layout = BoxLayout(orientation='vertical', spacing=10)
        self.cash_input = TextInput(text='', multiline=False, input_filter='float', font_size=30,
                                    size_hint_y=None, height=50)
        self.cash_popup_layout.add_widget(self.cash_input)

        # Numeric keypad grid layout
        keypad_layout = GridLayout(cols=3, spacing=10)

        # Numeric buttons
        numeric_buttons = ['1', '2', '3', '4', '5', '6', '7', '8', '9', '0',]
        for button in numeric_buttons:
            btn = Button(text=button, on_press=self.on_numeric_button_press)
            keypad_layout.add_widget(btn)

        # Confirm button
        confirm_button = Button(text="Confirm", on_press=self.on_cash_confirm)
        keypad_layout.add_widget(confirm_button)

        cancel_button = Button(text="Cancel", on_press=self.on_cash_cancel)
        keypad_layout.add_widget(cancel_button)

        self.cash_popup_layout.add_widget(keypad_layout)
        self.cash_popup = Popup(title='Enter Cash Amount', content=self.cash_popup_layout, size_hint=(0.8, 0.8))
        self.cash_popup.open()

    def on_numeric_button_press(self, instance):
        # Remove the decimal point and leading zeros
        current_input = self.cash_input.text.replace('.', '').lstrip('0')

        # Append the new digit
        new_input = current_input + instance.text

        # Pad with leading zeros if necessary to ensure at least two digits
        new_input = new_input.zfill(2)

        # Convert to integer, assuming it's in cents
        cents = int(new_input)

        # Convert the cents to dollars and cents
        dollars = cents // 100
        remaining_cents = cents % 100

        # Format the string as $dollars.remaining_cents
        self.cash_input.text = f"{dollars}.{remaining_cents:02d}"

    def on_cash_cancel(self, instance):
        self.cash_popup.dismiss()

    def on_cash_confirm(self, instance):
        amount_tendered = float(self.cash_input.text)
        total_with_tax = self.order_manager.calculate_total_with_tax()
        change = amount_tendered - total_with_tax
        self.cash_popup.dismiss()
        self.show_make_change_popup(change)


    def handle_card_payment(self):
        open_cash_drawer()  # Open the cash drawer for card payment
        self.show_payment_confirmation_popup()

    def show_payment_confirmation_popup(self):
        confirmation_layout = BoxLayout(orientation='vertical', spacing=10)
        order_summary = f"Order Summary:\n{self.display.text}\nPaid with card"
        confirmation_layout.add_widget(Label(text=order_summary))

        done_button = Button(text="Done", size_hint_y=None, height=50, on_press=self.on_done_button_press)
        confirmation_layout.add_widget(done_button)

        self.payment_popup = Popup(title='Payment Confirmation', content=confirmation_layout, size_hint=(0.8, 0.5))
        self.popup.dismiss()
        self.payment_popup.open()

    def show_make_change_popup(self, change):
        change_layout = BoxLayout(orientation='vertical', spacing=10)
        change_layout.add_widget(Label(text=f"Change to return: ${change:.2f}"))

        done_button = Button(text="Done", size_hint_y=None, height=50, on_press=self.on_change_done)
        change_layout.add_widget(done_button)

        self.change_popup = Popup(title='Change Calculation', content=change_layout, size_hint=(0.6, 0.3))
        self.change_popup.open()

    def on_change_done(self, instance):
        self.change_popup.dismiss()
        open_cash_drawer()  # Assuming you have this function to open the cash drawer
        self.show_payment_confirmation_popup()

    def send_order_to_history_database(self, order_details, order_manager, db_manager):
        db_manager.add_order_history(order_details['order_id'], json.dumps(order_details['items']),
                                    order_details['total_with_tax'],order_details['total'])
    def on_done_button_press(self, instance):
        # Save order to history database and clear order
        order_details = self.order_manager.get_order_details()
        self.send_order_to_history_database(order_details, self.order_manager, self.db_manager)
        self.order_manager.clear_order()

        # Close the popup and return to the main screen
        self.payment_popup.dismiss()
        self.display.text = ''


#
    def on_button_press(self, instance):
        current = self.display.text
        button_text = instance.text

        # Handling different button actions
        if button_text == 'Clear Order':
            self.display.text = ''
        elif button_text == 'Pay':
            self.finalize_order()
        elif button_text == 'Manual Entry':
            # Open manual entry dialog or page
            pass
        elif button_text == 'Clear Item':
            # Clear the last item from the order
            pass
        elif button_text == 'Open Register':
            open_cash_drawer()
        elif button_text == 'Inventory':
            # Switch to inventory management page
            pass
        else:
            # Add the button text (number) to the order
            self.display.text = current + button_text


if __name__ == '__main__':
    CashRegisterApp().run()

