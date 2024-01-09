from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.popup import Popup
from kivy.uix.textinput import TextInput
from kivy.uix.gridlayout import GridLayout


class PopupManager:
    current_popup = None

    @staticmethod
    def dismiss_current_popup():
        if PopupManager.current_popup is not None:
            PopupManager.current_popup.dismiss()
            PopupManager.current_popup = None

    @staticmethod
    def show_custom_item_popup(
        barcode, on_numeric_button_press, add_custom_item, on_custom_item_cancel
    ):
        custom_item_popup_layout = BoxLayout(orientation="vertical", spacing=10)
        cash_input = TextInput(
            text="",
            multiline=False,
            input_filter="float",
            font_size=30,
            size_hint_y=None,
            height=50,
        )
        custom_item_popup_layout.add_widget(cash_input)

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
            btn = Button(text=button, on_press=on_numeric_button_press)
            keypad_layout.add_widget(btn)

        confirm_button = Button(text="Confirm", on_press=add_custom_item)
        keypad_layout.add_widget(confirm_button)

        cancel_button = Button(text="Cancel", on_press=on_custom_item_cancel)
        keypad_layout.add_widget(cancel_button)

        custom_item_popup_layout.add_widget(keypad_layout)
        custom_item_popup = Popup(
            title="Enter Cash Amount",
            content=custom_item_popup_layout,
            size_hint=(0.8, 0.8),
        )
        custom_item_popup.open()
        return cash_input

    @staticmethod
    def show_order_popup(order_summary, on_payment_button_press):
        popup_layout = BoxLayout(orientation="vertical", spacing=10)
        popup_layout.add_widget(Label(text=order_summary))

        button_layout = BoxLayout(size_hint_y=None, height=50)
        for payment_method in ["Pay Cash", "Pay Card", "Cancel"]:
            btn = Button(text=payment_method, on_press=on_payment_button_press)
            button_layout.add_widget(btn)
        popup_layout.add_widget(button_layout)

        order_popup = Popup(
            title="Finalize Order", content=popup_layout, size_hint=(0.8, 0.8)
        )
        order_popup.open()

    @staticmethod
    def show_cash_payment_popup(
        on_numeric_button_press, on_cash_confirm, on_cash_cancel
    ):
        cash_popup_layout = BoxLayout(orientation="vertical", spacing=10)
        cash_input = TextInput(
            text="",
            multiline=False,
            input_filter="float",
            font_size=30,
            size_hint_y=None,
            height=50,
        )
        cash_popup_layout.add_widget(cash_input)

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
            btn = Button(text=button, on_press=on_numeric_button_press)
            keypad_layout.add_widget(btn)

        confirm_button = Button(text="Confirm", on_press=on_cash_confirm)
        keypad_layout.add_widget(confirm_button)

        cancel_button = Button(text="Cancel", on_press=on_cash_cancel)
        keypad_layout.add_widget(cancel_button)

        cash_popup_layout.add_widget(keypad_layout)
        cash_popup = Popup(
            title="Enter Cash Amount",
            content=cash_popup_layout,
            size_hint=(0.8, 0.8),
        )
        cash_popup.open()
        return cash_input

        #######################

    @staticmethod
    def show_payment_confirmation_popup(display_text, on_done_button_press):
        confirmation_layout = BoxLayout(orientation="vertical", spacing=10)
        order_summary = f"Order Summary:\n{display_text}\nPaid with card"
        confirmation_layout.add_widget(Label(text=order_summary))

        done_button = Button(
            text="Done", size_hint_y=None, height=50, on_press=on_done_button_press
        )
        confirmation_layout.add_widget(done_button)

        payment_popup = Popup(
            title="Payment Confirmation",
            content=confirmation_layout,
            size_hint=(0.8, 0.5),
        )
        PopupManager.dismiss_current_popup()
        PopupManager.current_popup = payment_popup
        payment_popup.open()

    @staticmethod
    def show_make_change_popup(change, on_change_done):
        change_layout = BoxLayout(orientation="vertical", spacing=10)
        change_layout.add_widget(Label(text=f"Change to return: ${change:.2f}"))

        done_button = Button(
            text="Done", size_hint_y=None, height=50, on_press=on_change_done
        )
        change_layout.add_widget(done_button)

        change_popup = Popup(
            title="Change Calculation", content=change_layout, size_hint=(0.6, 0.3)
        )
        PopupManager.current_popup = change_popup
        change_popup.open()

    @staticmethod
    def show_add_to_database_popup(
        barcode, add_item_to_database, close_add_to_database_popup
    ):
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

        popup_layout.add_widget(barcode_input)
        popup_layout.add_widget(name_input)
        popup_layout.add_widget(price_input)

        cancel_button = Button(
            text="Cancel",
            size_hint_y=None,
            height=50,
            on_press=close_add_to_database_popup,
        )
        confirm_button = Button(
            text="Confirm",
            size_hint_y=None,
            height=50,
            on_press=lambda instance: (
                add_item_to_database(barcode, name_input.text, price_input.text),
                close_add_to_database_popup(instance),
            ),
        )

        popup_layout.add_widget(cancel_button)
        popup_layout.add_widget(confirm_button)

        add_to_db_popup = Popup(
            title="Add to Database",
            content=popup_layout,
            size_hint=(0.8, 0.8),
            auto_dismiss=False,
        )
        PopupManager.current_popup = database_popup
        add_to_db_popup.open()

    @staticmethod
    def show_add_or_bypass_popup(barcode, on_add_or_bypass_choice):
        popup_layout = BoxLayout(orientation="vertical", spacing=10)
        for option in ["Add Custom Item", "Add to Database"]:
            btn = Button(
                text=option, on_press=lambda x: on_add_or_bypass_choice(x, barcode)
            )
            popup_layout.add_widget(btn)

        popup = Popup(
            title="Item Not Found", content=popup_layout, size_hint=(0.8, 0.6)
        )
        popup.open()

    @staticmethod
    def close_add_to_database_popup():
        add_to_db_popup.dismiss()

    @staticmethod
    def on_done_button_press(order_manager, db_manager, update_display_callback):
        order_details = order_manager.get_order_details()
        # Assuming send_order_to_history_database is a static method or can be called independently
        PopupManager.send_order_to_history_database(
            order_details, order_manager, db_manager
        )
        order_manager.clear_order()

        PopupManager.dismiss_current_popup()
        update_display_callback("")

    @staticmethod
    def on_payment_button_press(
        instance, show_cash_payment_callback, handle_card_payment_callback
    ):
        if instance.text == "Pay Cash":
            show_cash_payment_callback()
        elif instance.text == "Pay Card":
            handle_card_payment_callback()
        elif instance.text == "Cancel":
            PopupManager.dismiss_current_popup()

    @staticmethod
    def on_numeric_button_press(cash_input, instance):
        current_input = cash_input.text.replace(".", "").lstrip("0")
        new_input = current_input + instance.text
        new_input = new_input.zfill(2)
        cents = int(new_input)
        dollars = cents // 100
        remaining_cents = cents % 100

        cash_input.text = f"{dollars}.{remaining_cents:02d}"


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
