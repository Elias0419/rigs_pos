from kivy.app import App
from kivy.uix.button import Button
from kivy.uix.gridlayout import GridLayout
from kivy.uix.textinput import TextInput
from kivy.uix.label import Label
from kivy.uix.boxlayout import BoxLayout
from open_cash_drawer import open_cash_drawer
import threading
from kivy.clock import Clock
from kivy.app import App
from barcode_scanner import BarcodeScanner
from database_manager import DatabaseManager

class CashRegisterApp(App):
    def build(self):
        # Main layout is a vertical box layout
        main_layout = BoxLayout(orientation='vertical')

        # Display for showing current order and input/output
        self.display = TextInput(text='', multiline=True, readonly=True, halign='right', font_size=30)
        main_layout.add_widget(self.display)

        # Grid layout for buttons
        button_layout = GridLayout(cols=4)
        main_layout.add_widget(button_layout)

        # Buttons for the cash register
        buttons = [
            '1', '2', '3', 'Manual Entry',
            '4', '5', '6', 'Clear Item',
            '7', '8', '9', 'Open Register',
            'Clear Order', '0', 'Enter', 'Inventory'
        ]

        for button in buttons:
            button_layout.add_widget(Button(text=button, on_press=self.on_button_press))

        self.barcode_scanner = BarcodeScanner()
        self.db_manager = DatabaseManager("my_items_database.db")
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
                # Assuming item_details is a tuple like (name, price)
                item_name, item_price = item_details
                self.display.text += f"\nScanned item: {item_name} - ${item_price}"
            else:
                print(f"No details found for barcode: {barcode}")  # Debug print
        except Exception as e:
            print(f"Error handling scanned barcode: {e}")  # Error handling



    def on_button_press(self, instance):
        current = self.display.text
        button_text = instance.text

        # Handling different button actions
        if button_text == 'Clear Order':
            self.display.text = ''
        elif button_text == 'Enter':
            # Logic to finalize the order
            pass
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
