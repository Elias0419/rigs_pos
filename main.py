from datetime import datetime
import json
import re
import subprocess
import sys
import time
import threading

from kivy.config import Config

Config.set("kivy", "keyboard_mode", "systemanddock")

import eel
from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.modules import inspector
from kivy.uix.button import Button
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.textinput import TextInput

from kivymd.app import MDApp
from kivymd.uix.boxlayout import BoxLayout
from kivymd.uix.button import MDFlatButton, MDRaisedButton, MDIconButton
from kivymd.uix.gridlayout import GridLayout
from kivymd.uix.label import MDLabel

from barcode_scanner import BarcodeScanner
from database_manager import DatabaseManager
from label_printer import LabelPrintingView
from open_cash_drawer import open_cash_drawer
from order_manager import OrderManager
from history_manager import HistoryPopup
from receipt_printer import ReceiptPrinter
from inventory_manager import (InventoryManagementView, InventoryView)
from popups import PopupManager

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
        self.categories = self.initialze_categories()
        self.selected_categories = []
        self.load_settings()

    def build(self):
        self.barcode_scanner = BarcodeScanner()
        self.db_manager = DatabaseManager("inventory.db")
        self.financial_summary = FinancialSummaryWidget()
        self.order_manager = OrderManager()
        self.history_popup = HistoryPopup()
        self.receipt_printer = ReceiptPrinter("receipt_printer_config.yaml")
        self.inventory_manager = InventoryManagementView()
        self.label_manager = LabelPrintingView()
        self.popup_manager = PopupManager(self)




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

        btn_pay = self.create_md_raised_button(
            "Pay",
            self.on_button_press,
            (8, 8),
            "H6",
        )

        btn_custom_item = self.create_md_raised_button(
            "Custom",
            self.on_button_press,
            (8, 8),
            "H6",
        )
        btn_inventory = self.create_md_raised_button(
            "Search",
            self.on_button_press,
            (8, 8),
            "H6",
        )
        btn_tools = self.create_md_raised_button(
            "Tools",
            #self.on_button_press,  #################
            #lambda x: self.show_add_or_bypass_popup("210973141121"),
            lambda x: self.popup_manager.show_add_or_bypass_popup("220973141121"),
            # lambda x: self.open_category_button_popup(),
            (8, 8),
            "H6",
        )
        button_layout.add_widget(btn_pay)
        button_layout.add_widget(btn_custom_item)
        button_layout.add_widget(btn_inventory)
        button_layout.add_widget(btn_tools)
        main_layout.add_widget(button_layout)

        Clock.schedule_interval(self.check_inactivity, 10)
        Clock.schedule_interval(self.check_for_scanned_barcode, 0.1)

        if not hasattr(self, "monitor_check_scheduled"):
            Clock.schedule_interval(self.check_monitor_status, 5)
            self.monitor_check_scheduled = True

        return main_layout

    def create_clock_layout(self):
        clock_layout = BoxLayout(orientation="vertical", size_hint_x=1 / 3)
        self.clock_label = MDLabel(
            text="Loading...",
            size_hint_y=None,
            font_style="H6",
            height=80,
            color=self.get_text_color(),
            halign="center",
        )
        padlock_button = MDIconButton(
            icon="lock",
            pos_hint={"right": 1},
            on_press=lambda x: self.turn_off_monitor(),
        )
        clock_layout.add_widget(padlock_button)

        Clock.schedule_interval(self.update_clock, 1)
        clock_layout.add_widget(self.clock_label)
        return clock_layout

    def create_financial_layout(self):
        financial_layout = GridLayout(cols=1, size_hint_x=1 / 3)

        self.financial_summary_widget = FinancialSummaryWidget()
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
        else:
            self.handle_scanned_barcode(barcode)

    def handle_scanned_barcode(self, barcode):
        try:
            item_details = self.db_manager.get_item_details(barcode)

            if item_details:
                item_name, item_price = item_details
                self.order_manager.add_item(item_name, item_price)
                self.update_display()
                self.update_financial_summary()
                return item_details
            else:
                self.popup_manager.show_add_or_bypass_popup(barcode)
                #self.show_add_or_bypass_popup(barcode)
        except Exception as e:
            print(e)

    """
    Button handlers
    """

    def on_payment_button_press(self, instance):
        if "Pay Cash" in instance.text:
            self.popup_manager.show_cash_payment_popup()
        elif "Pay Debit" in instance.text:
            self.handle_debit_payment()
        elif "Pay Credit" in instance.text:
            self.handle_credit_payment()
        elif "Split" in instance.text:
            self.handle_split_payment()
        elif "Cancel" in instance.text:
            self.popup_manager.finalize_order_popup.dismiss()

    def on_numeric_button_press(self, instance):
        current_input = self.popup_manager.cash_input.text.replace(".", "").lstrip("0")
        new_input = current_input + instance.text
        new_input = new_input.zfill(2)
        cents = int(new_input)
        dollars = cents // 100
        remaining_cents = cents % 100
        self.popup_manager.cash_input.text = f"{dollars}.{remaining_cents:02d}"

    def on_split_payment_numeric_button_press(self, instance):
        current_input = self.split_payment_numeric_cash_input.text.replace(
            ".", ""
        ).lstrip("0")
        new_input = current_input + instance.text
        new_input = new_input.zfill(2)
        cents = int(new_input)
        dollars = cents // 100
        remaining_cents = cents % 100
        self.split_payment_numeric_cash_input.text = f"{dollars}.{remaining_cents:02d}"

    def on_add_discount_numeric_button_press(self, instance):
        current_input = self.popup_manager.discount_amount_input.text.replace(".", "").lstrip("0")
        new_input = current_input + instance.text
        new_input = new_input.zfill(2)
        cents = int(new_input)
        dollars = cents // 100
        remaining_cents = cents % 100
        self.popup_manager.discount_amount_input.text = f"{dollars}.{remaining_cents:02d}"

    def on_tool_button_press(self, instance):
        if instance.text == "Clear Order":
            self.order_layout.clear_widgets()
            self.order_manager.clear_order()
            self.update_financial_summary()
        elif instance.text == "Open Register":
            open_cash_drawer()
        elif instance.text == "Reporting":
            self.history_popup.show_hist_reporting_popup()
        elif instance.text == "Label Printer":
            self.popup_manager.show_label_printing_view()
        elif instance.text == "Inventory Management":
            self.popup_manager.show_inventory_management_view()
        elif instance.text == "System":
            self.popup_manager.show_system_popup()
        self.popup_manager.tools_popup.dismiss()

    def on_system_button_press(self, instance):
        if instance.text == "Reboot System":
            self.reboot_are_you_sure()
        elif instance.text == "Restart App":
            sys.exit(42)
        elif instance.text == "Change Theme":
            self.popup_manager.show_theme_change_popup()
        elif instance.text == "TEST":
            print("test button")
            eel_thread = threading.Thread(target=self.start_eel)
            eel_thread.daemon = True
            eel_thread.start()
        self.popup_manager.system_popup.dismiss()

    def on_button_press(self, instance):
        button_text = instance.text
        total = self.order_manager.calculate_total_with_tax()
        if button_text == "Clear Order":
            self.order_layout.clear_widgets()
            self.order_manager.clear_order()
        elif button_text == "Pay":
            if total > 0:
                self.finalize_order()
        elif button_text == "Custom":
            self.popup_manager.show_custom_item_popup(barcode="1234567890")
        elif button_text == "Tools":
            self.popup_manager.show_tools_popup()
        elif button_text == "Search":
            self.popup_manager.show_inventory()

    def on_done_button_press(self, instance):
        order_details = self.order_manager.get_order_details()
        self.send_order_to_history_database(
            order_details, self.order_manager, self.db_manager
        )
        self.order_manager.clear_order()
        self.popup_manager.payment_popup.dismiss()
        self.update_financial_summary()
        self.order_layout.clear_widgets()

    def on_receipt_button_press(self, instance):
        printer = ReceiptPrinter("receipt_printer_config.yaml")
        order_details = self.order_manager.get_order_details()
        printer.print_receipt(order_details)

    def on_lock_screen_button_press(self, instance):
        if instance.text == "Reset":
            self.entered_pin = ""
        else:
            self.entered_pin += instance.text
            self.reset_pin_timer()

        if len(self.entered_pin) == 4:
            if self.entered_pin == self.correct_pin:
                self.lock_popup.dismiss()
                self.entered_pin = ""
            else:
                self.entered_pin = ""

    def on_adjust_price_numeric_button_press(self, instance):
        current_input = self.popup_manager.adjust_price_cash_input.text.replace(".", "").lstrip("0")
        new_input = current_input + instance.text
        new_input = new_input.zfill(2)
        cents = int(new_input)
        dollars = cents // 100
        remaining_cents = cents % 100
        self.popup_manager.adjust_price_cash_input.text = f"{dollars}.{remaining_cents:02d}"

    def on_preset_amount_press(self, instance):
        self.popup_manager.cash_payment_input.text = instance.text.strip("$")

    """
    Split payment stuff
    """

    def handle_split_payment(self):
        self.dismiss_popups(
            "split_amount_popup", "split_cash_popup", "split_change_popup"
        )
        remaining_amount = self.order_manager.calculate_total_with_tax()
        remaining_amount = float(f"{remaining_amount:.2f}")
        self.split_payment_info = {
            "total_paid": 0.0,
            "remaining_amount": remaining_amount,
            "payments": [],
        }
        self.show_split_payment_numeric_popup()

    def show_split_payment_numeric_popup(self, subsequent_payment=False):
        self.dismiss_popups(
            "split_cash_confirm_popup",
            "split_cash_popup",
            "split_change_popup",
            "finalize_order_popup",
        )

        self.split_payment_numeric_popup_layout = BoxLayout(
            orientation="vertical", spacing=10
        )
        self.split_payment_numeric_popup = Popup(
            title=f"Split Payment - Remaining Amount: {self.split_payment_info['remaining_amount']:.2f} ",
            content=self.split_payment_numeric_popup_layout,
            size_hint=(0.8, 0.8),
        )
        if subsequent_payment:
            self.split_payment_numeric_cash_input = TextInput(
                text=f"{self.split_payment_info['remaining_amount']:.2f}",
                disabled=True,
                multiline=False,
                input_filter="float",
                font_size=30,
                size_hint_y=None,
                height=50,
            )
            self.split_payment_numeric_popup_layout.add_widget(
                self.split_payment_numeric_cash_input
            )

        else:
            self.split_payment_numeric_cash_input = TextInput(
                text="",
                disabled=True,
                multiline=False,
                input_filter="float",
                font_size=30,
                size_hint_y=None,
                height=50,
            )
            self.split_payment_numeric_popup_layout.add_widget(
                self.split_payment_numeric_cash_input
            )

        keypad_layout = GridLayout(cols=3, rows=4, spacing=10)

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
            "",
            "0",
            "Clear",
        ]
        for button in numeric_buttons:
            if button == "":
                blank_space = Label(size_hint=(0.8, 0.8))
                keypad_layout.add_widget(blank_space)
            elif button == "Clear":
                clr_button = Button(
                    text=button,
                    on_press=lambda x: self.clear_split_numeric_input(),
                    size_hint=(0.8, 0.8),
                )
                keypad_layout.add_widget(clr_button)
            else:
                btn = Button(
                    text=button,
                    on_press=self.on_split_payment_numeric_button_press,
                    size_hint=(0.8, 0.8),
                )
                keypad_layout.add_widget(btn)

        buttons_layout = GridLayout(cols=4, size_hint_y=1 / 7, spacing=5)
        cash_button = self.create_md_raised_button(
            "Cash",
            lambda x: self.handle_split_input(
                self.split_payment_numeric_cash_input.text, "Cash"
            ),
            (0.8, 0.8),
        )

        debit_button = self.create_md_raised_button(
            "Debit",
            lambda x: self.handle_split_input(
                self.split_payment_numeric_cash_input.text, "Debit"
            ),
            (0.8, 0.8),
        )
        credit_button = self.create_md_raised_button(
            "Credit",
            lambda x: self.handle_split_input(
                self.split_payment_numeric_cash_input.text, "Credit"
            ),
            (0.8, 0.8),
        )

        cancel_button = Button(
            text="Cancel",
            on_press=lambda x: self.split_cancel(),
            size_hint=(0.8, 0.8),
        )

        buttons_layout.add_widget(cash_button)
        buttons_layout.add_widget(debit_button)
        buttons_layout.add_widget(credit_button)
        buttons_layout.add_widget(cancel_button)

        self.split_payment_numeric_popup_layout.add_widget(keypad_layout)
        self.split_payment_numeric_popup_layout.add_widget(buttons_layout)

        self.split_payment_numeric_popup.open()

    def clear_split_numeric_input(self):
        self.split_payment_numeric_cash_input.text = ""

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
        self.split_payment_info["total_paid"] += amount
        self.split_payment_info["remaining_amount"] -= amount
        self.split_payment_info["payments"].append({"method": method, "amount": amount})
        print(self.split_payment_info, "after Modify")

        if method == "Cash":
            print("method", method)
            self.show_split_cash_popup(amount)
            self.split_payment_numeric_popup.dismiss()
        elif method == "Debit":
            self.show_split_card_confirm(amount, method)
            self.split_payment_numeric_popup.dismiss()
        elif method == "Credit":
            self.show_split_card_confirm(amount, method)
            self.split_payment_numeric_popup.dismiss()

    def split_cash_continue(self, amount):
        tolerance = 0.001
        self.dismiss_popups(
            "split_cash_popup", "split_cash_confirm_popup", "split_change_popup"
        )

        if abs(self.split_payment_info["remaining_amount"]) <= tolerance:
            self.finalize_split_payment()
        else:
            self.show_split_payment_numeric_popup(subsequent_payment=True)

    def split_card_continue(self, amount, method):
        print("split_card_continue", amount, method)
        tolerance = 0.001
        self.dismiss_popups("split_card_confirm_popup")

        if abs(self.split_payment_info["remaining_amount"]) <= tolerance:
            self.finalize_split_payment()
        else:
            self.show_split_payment_numeric_popup(subsequent_payment=True)

    def show_split_card_confirm(self, amount, method):
        open_cash_drawer()
        split_card_confirm = BoxLayout(orientation="vertical")
        split_card_confirm_text = Label(text=f"{amount} {method} Payment Confirmed")
        tolerance = 0.001

        if abs(self.split_payment_info["remaining_amount"]) <= tolerance:
            split_card_confirm_next_btn = self.create_md_raised_button(
                "Done",
                lambda x: self.split_card_continue(amount, method),
                (1, 0.4),
            )
        else:
            split_card_confirm_next_btn = self.create_md_raised_button(
                "Next", lambda x: self.split_card_continue(amount, method), (1, 0.4)
            )
        split_card_confirm.add_widget(split_card_confirm_text)
        split_card_confirm.add_widget(split_card_confirm_next_btn)
        self.split_card_confirm_popup = Popup(
            title="Payment Confirmation",
            content=split_card_confirm,
            size_hint=(0.4, 0.4),
        )
        self.split_card_confirm_popup.open()

    def show_split_cash_confirm(self, amount):
        split_cash_confirm = BoxLayout(orientation="vertical")
        split_cash_confirm_text = Label(text=f"{amount} Cash Payment Confirmed")
        tolerance = 0.001

        if abs(self.split_payment_info["remaining_amount"]) <= tolerance:
            split_cash_confirm_next_btn = self.create_md_raised_button(
                "Done", lambda x: self.split_cash_continue(amount), (1, 0.4)
            )
        else:
            split_cash_confirm_next_btn = self.create_md_raised_button(
                "Next", lambda x: self.split_cash_continue(amount), (1, 0.4)
            )

        split_cash_confirm.add_widget(split_cash_confirm_text)
        split_cash_confirm.add_widget(split_cash_confirm_next_btn)
        self.split_cash_confirm_popup = Popup(
            title="Payment Confirmation",
            content=split_cash_confirm,
            size_hint=(0.4, 0.4),
        )
        self.split_cash_confirm_popup.open()

    def show_split_cash_popup(self, amount):
        common_amounts = self.calculate_common_amounts(amount)
        other_buttons = BoxLayout(
            orientation="horizontal",
            spacing=5,
            size_hint=(1, 0.4),
        )
        self.split_cash_popup_layout = BoxLayout(orientation="vertical", spacing=10)
        self.split_cash_input = MoneyInput(
            text=str(amount),
            input_type="number",
            multiline=False,
            disabled=True,
            input_filter="float",
            font_size=30,
            size_hint_y=0.2,
            size_hint_x=0.3,
            height=50,
        )
        self.split_cash_popup_layout.add_widget(self.split_cash_input)

        split_cash_keypad_layout = GridLayout(cols=2, spacing=5)

        placeholder_amounts = [0] * 5
        for i, placeholder in enumerate(placeholder_amounts):

            btn_text = f"${common_amounts[i]}" if i < len(common_amounts) else "-"
            btn = Button(
                text=btn_text,
                on_press=self.split_on_preset_amount_press,
            )

            btn.disabled = i >= len(common_amounts)
            split_cash_keypad_layout.add_widget(btn)

        split_custom_cash_button = self.create_md_raised_button(
            "Custom",
            lambda x: self.split_open_custom_cash_popup(),
            (0.8, 0.8),
        )

        split_cash_confirm_button = self.create_md_raised_button(
            "Confirm",
            lambda x: self.split_on_cash_confirm(x, amount),
            (0.8, 0.8),
        )

        split_cash_cancel_button = Button(
            text="Cancel",
            on_press=lambda x: self.split_on_cash_cancel(),
            size_hint=(0.8, 0.8),
        )

        other_buttons.add_widget(split_cash_confirm_button)
        other_buttons.add_widget(split_cash_cancel_button)
        other_buttons.add_widget(split_custom_cash_button)

        self.split_cash_popup_layout.add_widget(split_cash_keypad_layout)
        self.split_cash_popup_layout.add_widget(other_buttons)
        self.split_cash_popup = Popup(
            title="Amount Tendered",
            content=self.split_cash_popup_layout,
            size_hint=(0.8, 0.8),
        )
        print("End of split cash popup")
        self.split_cash_popup.open()

    def split_on_preset_amount_press(self, instance):
        self.split_cash_input.text = instance.text.strip("$")

    def split_on_cash_confirm(self, instance, amount):
        self.split_cash_popup.dismiss()
        if float(self.split_cash_input.text) > amount:
            open_cash_drawer()
            change = float(self.split_cash_input.text) - amount
            print("make change")
            self.split_cash_make_change(change, amount)
        else:
            print(amount)
            open_cash_drawer()
            self.show_split_cash_confirm(amount)

    def split_cash_make_change(self, change, amount):
        split_change_layout = BoxLayout(orientation="vertical", spacing=10)
        split_change_layout.add_widget(Label(text=f"Change to return: ${change:.2f}"))

        split_done_button = self.create_md_raised_button(
            "Done",
            lambda x: self.split_cash_continue(amount),
            size_hint=(1, 0.4),
            height=50,
        )
        split_change_layout.add_widget(split_done_button)

        self.split_change_popup = Popup(
            title="Change Calculation",
            content=split_change_layout,
            size_hint=(0.6, 0.3),
        )
        self.split_change_popup.open()

    def split_on_cash_cancel(self, instance):
        self.dismiss_popups("split_cash_popup")

    def finalize_split_payment(self):
        self.order_manager.set_payment_method("Split")
        self.show_payment_confirmation_popup()
        print("finalize")

    """
  #####################################
    """
    def open_category_button_popup(self):
        self.category_button_popup = self.popup_manager.create_category_popup()
        self.category_button_popup.open()
#########################################

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
        self.update_display()
        self.update_financial_summary()
        self.popup_manager.adjust_price_popup.dismiss()
        self.financial_summary.close_order_mod_popup()

    def remove_item(self, item_name, item_price):
        self.order_manager.remove_item(item_name)
        self.update_display()
        self.update_financial_summary()
        self.popup_manager.item_popup.dismiss()

    def adjust_item_quantity(self, item_id, adjustment):
        self.order_manager.adjust_item_quantity(item_id, adjustment)
        self.popup_manager.item_popup.dismiss()
        self.popup_manager.show_item_details_popup(item_id)
        #self.on_item_click(item_id)
        self.update_display()
        self.update_financial_summary()

    def discount_single_item(self, discount_amount, percent=False):
        if percent:

            self.order_manager.add_discount(discount_amount, percent=True)
            self.update_display()
            self.update_financial_summary()
        else:
            self.order_manager.add_discount(discount_amount)
            self.update_display()
            self.update_financial_summary()

        self.popup_manager.discount_popup.dismiss()
        self.popup_manager.item_popup.dismiss()
        if hasattr(self, "item_popup") and self.item_popup is not None:
            self.item_popup.dismiss()

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
        self.update_display()
        self.update_financial_summary()
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
    Utilities
    """

    def toggle_category_selection(self, instance, category):
        if category in self.selected_categories:
            self.selected_categories.remove(category)
            instance.text = category
        else:
            self.selected_categories.append(category)
            instance.text = f"{category}\n (Selected)"

    def apply_categories(self):
        categories_str = ", ".join(self.selected_categories)
        self.popup_manager.add_to_db_category_input.text = categories_str
        print("Applying categories:", self.selected_categories)
        self.category_button_popup.dismiss()

    def reset_pin_timer(self):
        if self.pin_reset_timer is not None:
            self.pin_reset_timer.cancel()

        self.pin_reset_timer = threading.Timer(5.0, self.reset_pin)
        self.pin_reset_timer.start()

    def reset_pin(self):
        self.entered_pin = ""

    def calculate_common_amounts(self, total):
        amounts = []
        for base in [1, 5, 10, 20, 50, 100]:
            amount = total - (total % base) + base
            if amount not in amounts and amount >= total:
                amounts.append(amount)
        return amounts

    def on_input_focus(self, instance, value):
        if value:
            instance.show_keyboard()
        else:
            instance.hide_keyboard()

    def update_clock(self, *args):
        self.clock_label.text = time.strftime("%I:%M %p\n%A\n%B %d, %Y\n")
        self.clock_label.color = self.get_text_color()

    def get_text_color(self):
        if self.theme_cls.theme_style == "Dark":
            return (1, 1, 1, 1)
        else:
            return (0, 0, 0, 1)

    def reset_to_main_context(self, instance):
        self.current_context = "main"
        try:
            self.inventory_manager.detach_from_parent()
            self.label_manager.detach_from_parent()
        except Exception as e:
            print(e)

    def create_focus_popup(self, title, content, textinput, size_hint, pos_hint={}):
        popup = FocusPopup(
            title=title, content=content, size_hint=size_hint, pos_hint=pos_hint
        )
        popup.focus_on_textinput(textinput)
        return popup

    def create_md_raised_button(
        self,
        text,
        on_press_action,
        size_hint=(None, None),
        font_style="Body1",
        height=50,
    ):
        button = MDRaisedButton(
            text=text,
            on_press=on_press_action,
            size_hint=size_hint,
            font_style=font_style,
            height=height,
        )
        return button

    def dismiss_popups(self, *popups):
        for popup_attr in popups:
            if hasattr(self, popup_attr):
                try:
                    popup = getattr(self, popup_attr)
                    if popup._is_open:
                        popup.dismiss()
                except Exception as e:
                    print(e)

    def update_display(self):
        print("called update display")
        self.order_layout.clear_widgets()
        for item_id, item_info in self.order_manager.items.items():
            item_name = item_info["name"]
            item_quantity = item_info["quantity"]
            item_total_price = item_info["total_price"]

            if item_quantity > 1:
                item_display_text = (
                    f"{item_name} x{item_quantity} ${item_total_price:.2f}"
                )
            else:
                item_display_text = f"{item_name} ${item_total_price:.2f}"

            item_button = MDRaisedButton(
                text=item_display_text,
                size_hint=(0.1, 0.1),
                halign="center",
                valign="center",
            )
            item_button.bind(on_press=lambda x: self.popup_manager.show_item_details_popup(item_id))
            self.order_layout.add_widget(item_button)

    def update_financial_summary(self):
        subtotal = self.order_manager.subtotal
        total_with_tax = self.order_manager.calculate_total_with_tax()
        tax = self.order_manager.tax_amount
        discount = self.order_manager.order_discount

        self.financial_summary_widget.update_summary(
            subtotal, tax, total_with_tax, discount
        )

    def manual_override(self, instance):
        current_time = time.time()
        if current_time - self.override_tap_time < 1:
            sys.exit(42)
        else:
            self.override_tap_time = current_time

    def set_primary_palette(self, color_name):
        self.theme_cls.primary_palette = color_name
        self.save_settings()

    def toggle_dark_mode(self):
        if self.theme_cls.theme_style == "Dark":
            self.theme_cls.theme_style = "Light"
        else:
            self.theme_cls.theme_style = "Dark"
        self.save_settings()

    def on_add_or_bypass_choice(self, choice_text, barcode):
        if choice_text == "Add Custom Item":
            self.popup_manager.show_custom_item_popup(barcode)
        elif choice_text == "Add to Database":
            self.popup_manager.show_add_to_database_popup(barcode)

    def initialze_categories(self):
        categories = [
            "Cdb",
            "Rig",
            "Nails",
            "Tubes",
            "Hand Pipes",
            "Chillum",
            "Ecig",
            "Butane",
            "Torch",
            "Toro",
            "Slides H",
            "Quartz",
            "Vaporizers",
            "Lighter",
            "9mm Thick",
            "Cleaning",
            "Edible",
            "Bubbler",
            "Sherlock",
            "Spoon",
            "Silicone",
            "Scales",
            "Slides",
            "Imported Glass",
            "Ash Catcher",
            "Soft Glass",
            "Vaporizers",
            "Pendant",
            "Smoker Accessory",
            "Ecig Accessories",
            "Happy Fruit",
            "Concentrate Accessories",
            "Conc. Devices, Atomizers",
            "Erigs And Accessory",
            "Mods Batteries Kits",
        ]
        return categories


    def dismiss_guard_popup(self):
        self.popup_manager.guard_popup.dismiss()
        self.turn_on_monitor()

    def close_item_popup(self):
        self.dismiss_popups('item_popup')

    def dismiss_add_discount_popup(self):
        self.dismiss_popups('discount_popup')

    def dismiss_bypass_popup(self, instance, barcode):
        self.on_add_or_bypass_choice(instance.text, barcode)
        #self.dismiss_popups('popup')

    def close_add_to_database_popup(self):
        self.popup_manager.add_to_db_popup.dismiss()

    def on_cash_cancel(self, instance):
        self.popup_manager.cash_popup.dismiss()

    def on_adjust_price_cancel(self, instance):
        self.popup_manager.adjust_price_popup.dismiss()

    def on_custom_item_cancel(self, instance):
        self.popup_manager.custom_item_popup.dismiss()

    def on_custom_cash_cancel(self, instance):
        self.popup_manager.custom_cash_popup.dismiss()

    def on_change_done(self, instance):
        self.popup_manager.change_popup.dismiss()
        self.popup_manager.show_payment_confirmation_popup()

    def split_cancel(self):
        self.dismiss_popups('split_payment_numeric_popup')
        self.popup_manager.finalize_order_popup.open()

    """
    System
    """

    def check_monitor_status(self, dt):
        if self.is_monitor_off():
            if not self.is_guard_screen_displayed and not self.is_lock_screen_displayed:
                self.show_lock_screen()
                self.show_guard_screen()
        else:
            self.is_guard_screen_displayed = False
            self.is_lock_screen_displayed = False

    def reboot(self, instance):
        try:
            subprocess.run(["systemctl", "reboot"])
        except Exception as e:
            print(e)

    def save_settings(self):
        settings = {
            "primary_palette": self.theme_cls.primary_palette,
            "theme_style": self.theme_cls.theme_style,
        }
        with open("settings.json", "w") as f:
            json.dump(settings, f)

    def load_settings(self):
        try:
            with open("settings.json", "r") as f:
                settings = json.load(f)
                self.theme_cls.primary_palette = settings.get(
                    "primary_palette", "Brown"
                )
                self.theme_cls.theme_style = settings.get("theme_style", "Light")
        except FileNotFoundError as e:
            print(e)

    def turn_off_monitor(self):
        touchscreen_device = "iSolution multitouch"
        try:
            subprocess.run(["xinput", "disable", touchscreen_device], check=True)
        except subprocess.CalledProcessError as e:
            print(e)
            subprocess.run(["xinput", "enable", touchscreen_device], check=True)
            return

        try:
            subprocess.run(
                ["xrandr", "--output", "HDMI-1", "--brightness", "0"], check=True
            )
        except subprocess.CalledProcessError as e:
            subprocess.run(
                ["xrandr", "--output", "HDMI-1", "--brightness", "1"], check=True
            )
            print(e)
            return

        def reenable_touchscreen():
            time.sleep(1)
            try:
                subprocess.run(["xinput", "enable", touchscreen_device], check=True)
            except subprocess.CalledProcessError as e:
                print(e)

        threading.Thread(target=reenable_touchscreen).start()

    def is_monitor_off(self):
        output_name = "HDMI-1"
        try:
            result = subprocess.run(
                ["xrandr", "--verbose"], stdout=subprocess.PIPE, check=True
            )
            output = result.stdout.decode("utf-8")
            pattern = rf"{output_name} connected.*?Brightness: (\d+\.\d+)"
            match = re.search(pattern, output, re.DOTALL)

            if match:
                current_brightness = float(match.group(1))
                return current_brightness == 0.0
            else:
                return False
        except Exception as e:
            print(e)
            return False

    def turn_on_monitor(self):
        try:
            subprocess.run(
                ["xrandr", "--output", "HDMI-1", "--brightness", "1"], check=True
            )
        except Exception as e:
            print(e)

    def reboot_are_you_sure(self):
        arys_layout = BoxLayout()

        btn = self.create_md_raised_button(
            "Yes!",
            self.reboot,
            (0.9, 0.9),
        )
        btn2 = self.create_md_raised_button(
            "No!",
            lambda x: popup.dismiss(),
            (0.9, 0.9),
        )
        arys_layout.add_widget(Label(text=f"Are you sure?"))
        arys_layout.add_widget(btn)
        arys_layout.add_widget(btn2)
        popup = Popup(
            title="Reboot",
            content=arys_layout,
            size_hint=(0.9, 0.2),
            pos_hint={"top": 1},
            background_color=[1, 0, 0, 1],
        )

        popup.open()

    def _test_current_context(self):
        while True:
            print(self.current_context)
            time.sleep(1)

    def _test_current_context_thread(self):
        test_thread = threading.Thread(target=self._test_current_context)
        test_thread.daemon = True
        test_thread.start()

    def check_inactivity(self, *args):
        try:

            result = subprocess.run(["xprintidle"], stdout=subprocess.PIPE, check=True)
            inactive_time = int(result.stdout.decode().strip())

            if inactive_time > 600000:
                self.turn_off_monitor()

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


class FocusPopup(Popup):
    def focus_on_textinput(self, textinput):
        self.textinput_to_focus = textinput

    def on_open(self):
        if hasattr(self, "textinput_to_focus"):
            self.textinput_to_focus.focus = True


class FinancialSummaryWidget(MDRaisedButton):

    _instance = None

    def __new__(cls, **kwargs):
        if cls._instance is None:
            cls._instance = super(FinancialSummaryWidget, cls).__new__(cls)
        return cls._instance

    def __init__(self, **kwargs):
        if not hasattr(self, "_initialized"):

            super(FinancialSummaryWidget, self).__init__(**kwargs)
            self.size_hint_y = None
            self.size_hint_x = 1
            self.height = 80
            self.orientation = "vertical"
            self.order_mod_popup = None
            print(self)
            app = App.get_running_app()

    def update_summary(self, subtotal, tax, total_with_tax, discount):
        self.text = (
            f"[size=20]Subtotal: ${subtotal:.2f}\n"
            f"Discount: ${discount:.2f}\n"
            f"Tax: ${tax:.2f}\n\n[/size]"
            f"[size=24]Total: [b]${total_with_tax:.2f}[/b][/size]"
        )

    def on_press(self):
        self.open_order_modification_popup()

    def clear_order(self):
        app.order_layout.clear_widgets()
        app.order_manager.clear_order()
        app.update_financial_summary()
        self.order_mod_popup.dismiss()

    def open_order_modification_popup(self):
        order_mod_layout = GridLayout(cols=2, spacing=5)
        adjust_price_button = MDRaisedButton(
            text="Adjust Payment",
            on_press=lambda x: app.popup_manager.show_adjust_price_popup(),
        )
        clear_order_button = MDRaisedButton(
            text="Clear Order", on_press=lambda x: self.clear_order()
        )

        order_mod_layout.add_widget(adjust_price_button)
        order_mod_layout.add_widget(clear_order_button)
        self.order_mod_popup = Popup(
            title="",
            content=order_mod_layout,
            size_hint=(0.2, 0.2),

        )
        self.order_mod_popup.open()

    def close_order_mod_popup(self):
        self.order_mod_popup.dismiss()


try:
    app = CashRegisterApp()
    app.run()
except KeyboardInterrupt:
    print("test")
# if __name__ == "__main__":
#     app = CashRegisterApp()
#     app.run()
#     #app.show_lock_screen()
