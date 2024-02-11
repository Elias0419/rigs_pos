from open_cash_drawer import open_cash_drawer
import sys

class ButtonHandler:
    def __init__(self, ref):
        self.app = ref

    def on_tool_button_press(self, instance):
            if instance.text == "Clear Order":
                self.app.order_layout.clear_widgets()
                self.app.order_manager.clear_order()
                self.app.update_financial_summary()
            elif instance.text == "Open Register":
                open_cash_drawer()
            elif instance.text == "Reporting":
                order_history = self.app.db_manager.get_order_history()
                self.app.history_popup.show_hist_reporting_popup()
            elif instance.text == "Label Printer":
                self.app.popup_manager.show_label_printing_view()
            elif instance.text == "Inventory Management":
                self.app.popup_manager.show_inventory_management_view()
            elif instance.text == "System":
                self.app.popup_manager.show_system_popup()
            self.app.popup_manager.tools_popup.dismiss()

    def on_payment_button_press(self, instance):
        if "Pay Cash" in instance.text:
            self.app.popup_manager.show_cash_payment_popup()
        elif "Pay Debit" in instance.text:
            self.app.order_manager.handle_debit_payment()
        elif "Pay Credit" in instance.text:
            self.app.order_manager.handle_credit_payment()
        elif "Split" in instance.text:
            self.app.popup_manager.handle_split_payment()
        elif "Cancel" in instance.text:
            self.app.popup_manager.finalize_order_popup.dismiss()

    def on_numeric_button_press(self, instance):
        current_input = self.app.popup_manager.cash_input.text.replace(".", "").lstrip("0")
        new_input = current_input + instance.text
        new_input = new_input.zfill(2)
        cents = int(new_input)
        dollars = cents // 100
        remaining_cents = cents % 100
        self.app.popup_manager.cash_input.text = f"{dollars}.{remaining_cents:02d}"

    def on_split_payment_numeric_button_press(self, instance):
        current_input = (
            self.app.popup_manager.split_payment_numeric_cash_input.text.replace(
                ".", ""
            ).lstrip("0")
        )
        new_input = current_input + instance.text
        new_input = new_input.zfill(2)
        cents = int(new_input)
        dollars = cents // 100
        remaining_cents = cents % 100
        self.app.popup_manager.split_payment_numeric_cash_input.text = (
            f"{dollars}.{remaining_cents:02d}"
        )

    def on_split_custom_cash_payment_numeric_button_press(self, instance):
        current_input = self.app.popup_manager.split_custom_cash_input.text.replace(
            ".", ""
        ).lstrip("0")
        new_input = current_input + instance.text
        new_input = new_input.zfill(2)
        cents = int(new_input)
        dollars = cents // 100
        remaining_cents = cents % 100
        self.app.popup_manager.split_custom_cash_input.text = (
            f"{dollars}.{remaining_cents:02d}"
        )

    def on_add_discount_numeric_button_press(self, instance):
        current_input = self.app.popup_manager.discount_amount_input.text.replace(
            ".", ""
        ).lstrip("0")
        new_input = current_input + instance.text
        new_input = new_input.zfill(2)
        cents = int(new_input)
        dollars = cents // 100
        remaining_cents = cents % 100
        self.app.popup_manager.discount_amount_input.text = (
            f"{dollars}.{remaining_cents:02d}"
        )

    def on_adjust_price_numeric_button_press(self, instance):
        current_input = self.app.popup_manager.adjust_price_cash_input.text.replace(
            ".", ""
        ).lstrip("0")
        new_input = current_input + instance.text
        new_input = new_input.zfill(2)
        cents = int(new_input)
        dollars = cents // 100
        remaining_cents = cents % 100
        self.app.popup_manager.adjust_price_cash_input.text = (
            f"{dollars}.{remaining_cents:02d}"
        )


    def on_system_button_press(self, instance):
        if instance.text == "Reboot System":
            self.app.popup_manager.reboot_are_you_sure()
        elif instance.text == "Restart App":
            sys.exit(42)
        elif instance.text == "Change Theme":
            self.app.popup_manager.show_theme_change_popup()
        # elif instance.text == "TEST":
        #     print("test button")
        #     eel_thread = threading.Thread(target=self.start_eel)
        #     eel_thread.daemon = True
        #     eel_thread.start()
        self.app.popup_manager.system_popup.dismiss()

    def on_button_press(self, instance):
        button_text = instance.text
        total = self.app.order_manager.calculate_total_with_tax()
        if button_text == "Clear Order":
            self.app.order_layout.clear_widgets()
            self.app.order_manager.clear_order()
        elif button_text == "Pay":
            if total > 0:
                self.app.order_manager.finalize_order()
        elif button_text == "Custom":
            self.app.popup_manager.show_custom_item_popup(barcode="1234567890")
        elif button_text == "Tools":
            self.app.popup_manager.show_tools_popup()
        elif button_text == "Search":
            self.app.popup_manager.show_inventory()

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
        else:
            self.app.entered_pin += button_text
            self.app.utilities.reset_pin_timer()

        if len(self.app.entered_pin) == 4:
            if self.app.entered_pin == self.app.correct_pin:
                self.app.popup_manager.lock_popup.dismiss()
                self.app.is_guard_screen_displayed = False
                self.app.is_lock_screen_displayed = False

            else:
                self.app.utilities.indicate_incorrect_pin(self.app.popup_manager.lock_popup)
                self.app.popup_manager.flash_buttons_red()
            self.app.entered_pin = ""

    def on_preset_amount_press(self, instance):
        self.app.popup_manager.cash_payment_input.text = instance.text.strip("$")

    def split_on_preset_amount_press(self, instance):
        self.app.popup_manager.split_cash_input.text = instance.text.strip("$")

