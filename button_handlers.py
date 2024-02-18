from open_cash_drawer import open_cash_drawer
import sys
import re
class ButtonHandler:
    def __init__(self, ref):
        self.app = ref
        self.pin_reset_timer = self.app.pin_reset_timer

    def clear_order(self):
        self.app.order_layout.clear_widgets()
        self.app.order_manager.clear_order()
        self.app.utilities.update_financial_summary()

    def show_reporting(self):
        self.app.db_manager.get_order_history()
        self.app.history_popup.show_hist_reporting_popup()

    def show_label_printer_view(self):
        self.app.popup_manager.show_label_printing_view()

    def show_inventory_management_view(self):
        self.app.popup_manager.show_inventory_management_view()

    def show_system_popup(self):
        self.app.popup_manager.show_system_popup()
    def show_calcultor_popup(self):
        self.app.calculator.show_calculator_popup()

    def on_tool_button_press(self, instance):
        tool_actions = {
            "Clear Order": self.clear_order,
            "Open Register": open_cash_drawer,
            "Reporting": self.show_reporting,
            "Label Printer": self.show_label_printer_view,
            "Inventory Management": self.show_inventory_management_view,
            "System": self.show_system_popup,
            "Calculator": self.show_calcultor_popup,
        }
        action = tool_actions.get(instance.text)
        if action:
            action()
        self.app.popup_manager.tools_popup.dismiss()


    def handle_numeric_input(self, input_field, instance_text):
        current_input = input_field.text.replace(".", "").lstrip("0")
        new_input = current_input + instance_text
        new_input = new_input.zfill(2)
        cents = int(new_input)
        dollars = cents // 100
        remaining_cents = cents % 100
        input_field.text = f"{dollars}.{remaining_cents:02d}"

    def on_numeric_button_press(self, instance):
        self.handle_numeric_input(self.app.popup_manager.cash_input, instance.text)

    def on_custom_cash_numeric_button_press(self, instance):
        self.handle_numeric_input(self.app.popup_manager.custom_cash_input, instance.text)

    def on_split_payment_numeric_button_press(self, instance):
        self.handle_numeric_input(self.app.popup_manager.split_payment_numeric_cash_input, instance.text)

    def on_split_custom_cash_payment_numeric_button_press(self, instance):
        self.handle_numeric_input(self.app.popup_manager.split_custom_cash_input, instance.text)

    def on_add_discount_numeric_button_press(self, instance):
        self.handle_numeric_input(self.app.popup_manager.discount_amount_input, instance.text)

    def on_add_order_discount_numeric_button_press(self, instance):
        self.handle_numeric_input(self.app.popup_manager.discount_order_amount_input, instance.text)

    def on_adjust_price_numeric_button_press(self, instance):
        self.handle_numeric_input(self.app.popup_manager.adjust_price_cash_input, instance.text)

    def on_payment_button_press(self, instance):
        payment_actions = {
            "Pay Cash": self.app.popup_manager.show_cash_payment_popup,
            "Pay Debit": self.app.order_manager.handle_debit_payment,
            "Pay Credit": self.app.order_manager.handle_credit_payment,
            "Split": self.app.popup_manager.handle_split_payment,
            "Cancel": lambda: self.app.popup_manager.finalize_order_popup.dismiss()
        }

        for action_text, action in payment_actions.items():
            if action_text in instance.text:
                action()
                break

    def on_system_button_press(self, instance):
        system_actions = {
            "Reboot System": self.app.popup_manager.reboot_are_you_sure,
            "Restart App": lambda: sys.exit(42),
            "Change Theme": self.app.popup_manager.show_theme_change_popup,

        }

        action = system_actions.get(instance.text)
        if action:
            action()
        self.app.popup_manager.system_popup.dismiss()

    def on_button_press(self, instance):
        button_actions = {
            "Clear Order": self.clear_order,
            "Pay": self.pay_order,
            "Custom": self.show_custom_item_popup,
            "Tools": self.show_tools_popup,
            "Search": self.show_inventory
        }

        action = button_actions.get(instance.text)
        if action:
            action()


    def pay_order(self):
        total = self.app.order_manager.calculate_total_with_tax()
        if total > 0:
            self.app.order_manager.finalize_order()

    def show_custom_item_popup(self):
        self.app.popup_manager.show_custom_item_popup()

    def show_tools_popup(self):
        self.app.popup_manager.show_tools_popup()

    def show_inventory(self):

        self.app.popup_manager.show_inventory()
    def on_system_button_press(self, instance):
        if instance.text == "Reboot System":
            self.app.popup_manager.reboot_are_you_sure()
        elif instance.text == "Restart App":
            sys.exit(42)
        elif instance.text == "Change Theme":
            self.app.popup_manager.show_theme_change_popup()

        self.app.popup_manager.system_popup.dismiss()



    def on_done_button_press(self, instance):
        order_details = self.app.order_manager.get_order_details()
        self.app.db_manager.send_order_to_history_database(
            order_details, self.app.order_manager, self.app.db_manager
        )
        self.app.order_manager.clear_order()
        self.app.popup_manager.payment_popup.dismiss()
        self.app.utilities.update_financial_summary()
        self.app.order_layout.clear_widgets()

    def on_receipt_button_press(self, instance):
        printer = self.app.receipt_printer
        order_details = self.app.order_manager.get_order_details()
        printer.print_receipt(order_details)

    def on_lock_screen_button_press(self, button_text, instance):
        if button_text == "Reset":
            self.app.entered_pin = ""
            self.app.popup_manager.pin_input.text = ""
            self.app.pin_reset_timer.reset()
        else:
            self.app.entered_pin += button_text
            self.app.popup_manager.pin_input.text += button_text
            self.app.pin_reset_timer.reset()

        if len(self.app.entered_pin) == 4:
            if self.app.entered_pin == self.app.correct_pin:
                self.app.popup_manager.lock_popup.dismiss()
                self.app.is_guard_screen_displayed = False
                self.app.is_lock_screen_displayed = False
                self.app.pin_reset_timer.stop()
            else:
                self.app.utilities.indicate_incorrect_pin(self.app.popup_manager.lock_popup)
                self.app.popup_manager.flash_buttons_red()
                self.app.popup_manager.pin_input.text = ""
                self.app.pin_reset_timer.reset()
            self.app.entered_pin = ""
            self.app.popup_manager.pin_input.text = ""

    def on_preset_amount_press(self, instance):
        amount = re.sub(r'\[.*?\]', '', instance.text)
        amount = amount.replace("$", "")

        self.app.popup_manager.cash_payment_input.text = amount

    def split_on_preset_amount_press(self, instance):
        amount = re.sub(r'\[.*?\]', '', instance.text)
        amount = amount.replace("$", "")
        self.app.popup_manager.split_cash_input.text = amount
