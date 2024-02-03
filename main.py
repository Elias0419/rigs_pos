from datetime import datetime
import json
import random
import re
import subprocess
import sys
import time
import ast
import threading
from threading import Thread

import eel
from kivy.config import Config

Config.set("kivy", "keyboard_mode", "systemanddock")

from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.lang import Builder
from kivy.metrics import dp
from kivy.modules import inspector
from kivy.properties import StringProperty, ListProperty, ObjectProperty

from kivy.uix.button import Button
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.recycleview.views import RecycleDataViewBehavior
from kivy.uix.textinput import TextInput
from kivy.utils import get_color_from_hex


from kivymd.app import MDApp
from kivymd.color_definitions import palette
from kivymd.uix.boxlayout import BoxLayout
from kivymd.uix.button import MDFlatButton, MDRaisedButton, MDIconButton
from kivymd.uix.gridlayout import GridLayout
from kivymd.uix.label import MDLabel
from kivymd.uix.recycleview import RecycleView

from barcode.upc import UniversalProductCodeA as upc_a
from barcode_scanner import BarcodeScanner
from database_manager import DatabaseManager
from label_printer import LabelPrinter, LabelPrintingRow, LabelPrintingView
from open_cash_drawer import open_cash_drawer
from order_manager import OrderManager
from history_manager import HistoryPopup
from receipt_printer import ReceiptPrinter
from inventory_manager import (
    InventoryManagementRow,
    InventoryManagementView,
    InventoryRow,
    InventoryView,
)

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
        self.load_settings()

    def build(self):
        self.barcode_scanner = BarcodeScanner()
        self.db_manager = DatabaseManager("inventory.db")

        self.order_manager = OrderManager()
        self.history_popup = HistoryPopup()
        self.receipt_printer = ReceiptPrinter("receipt_printer_config.yaml")
        self.inventory_manager = InventoryManagementView()
        self.label_manager = LabelPrintingView()
        main_layout = GridLayout(cols=1, spacing=5, orientation="tb-lr", row_default_height=60)
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
        button_layout = GridLayout(cols=4, spacing=5, size_hint_y=1 / 8, size_hint_x=1, orientation="lr-tb")

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
            self.on_button_press,
            (8, 8),
            "H6",
        )
        button_layout.add_widget(btn_pay)
        button_layout.add_widget(btn_custom_item)
        button_layout.add_widget(btn_inventory)
        button_layout.add_widget(btn_tools)
        main_layout.add_widget(button_layout)

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
                self.show_add_or_bypass_popup(barcode)
        except Exception as e:
            print(e)

    """
    Button handlers
    """

    def on_payment_button_press(self, instance):
        if instance.text == "Pay Cash":
            self.show_cash_payment_popup()
        elif instance.text == "Pay Debit":
            self.handle_debit_payment()
        elif instance.text == "Pay Credit":
            self.handle_credit_payment()
        elif instance.text == "Split":
            self.handle_split_payment()
        elif instance.text == "Cancel":
            self.finalize_order_popup.dismiss()

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
            self.update_financial_summary()
        elif instance.text == "Open Register":
            open_cash_drawer()
        elif instance.text == "Reporting":
            self.history_popup.show_hist_reporting_popup()
        elif instance.text == "Label Printer":
            self.show_label_printing_view()
        elif instance.text == "Inventory Management":
            self.show_inventory_management_view()
        elif instance.text == "System":
            self.show_system_popup()
        self.tools_popup.dismiss()

    def on_system_button_press(self, instance):
        if instance.text == "Reboot System":
            self.reboot_are_you_sure()
        elif instance.text == "Restart App":
            sys.exit(42)
        elif instance.text == "Change Theme":
            self.show_theme_change_popup()
        elif instance.text == "TEST":
            print("test button")
            eel_thread = threading.Thread(target=self.start_eel)
            eel_thread.daemon = True
            eel_thread.start()
        self.system_popup.dismiss()


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
            self.show_custom_item_popup(barcode="1234567890")
        elif button_text == "Tools":
            self.show_tools_popup()
        elif button_text == "Search":
            self.show_inventory()

    def on_done_button_press(self, instance):
        order_details = self.order_manager.get_order_details()
        self.send_order_to_history_database(
            order_details, self.order_manager, self.db_manager
        )
        self.order_manager.clear_order()
        self.payment_popup.dismiss()
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
        self.show_split_payment_popup()

    def show_split_payment_popup(self, subsequent_payment=False):
        self.dismiss_popups(
            "split_cash_confirm_popup",
            "split_cash_popup",
            "split_change_popup",
            "finalize_order_popup",
        )

        split_amount_layout = BoxLayout(size_hint=(1,1),orientation="vertical")
        if subsequent_payment:
            amount_remaining = f"{self.split_payment_info['remaining_amount']:.2f}"
            split_amount_input = TextInput(
                text=amount_remaining,
                height=20,
                multiline=False,
            )
        else:
            split_amount_input = TextInput(hint_text="Enter Amount of First Payment",height=20, multiline=False)
        split_amount_buttons = BoxLayout(
            orientation="horizontal", spacing=5, size_hint=(1, 1)
        )
        split_amount_remaining = MarkupLabel(
            text=str(
                f"[b]Remaining Amount: {self.split_payment_info['remaining_amount']:.2f}[/b]"
            )
        )
        self.split_amount_popup = self.create_focus_popup(
            size_hint=(0.8, 0.4),
            content=split_amount_layout,
            pos_hint={"top": 1},
            title="Split Payment",
            textinput=split_amount_input
        )

        split_cash_btn = self.create_md_raised_button(
            "Cash",
            lambda x: self.handle_split_input(
                amount=split_amount_input.text, method="Cash",

            ),
            (1,1),
        )
        split_credit_btn = self.create_md_raised_button(
            "Credit",
            lambda x: self.handle_split_input(
                amount=split_amount_input.text, method="Credit",

            ),
             (1,1),
        )
        split_debit_btn = self.create_md_raised_button(
            "Debit",
            lambda x: self.handle_split_input(
                amount=split_amount_input.text, method="Debit",

            ),
             (1,1),
        )
        split_cancel_btn = Button(
            text="Cancel", on_press=lambda x: self.split_amount_popup.dismiss(),
            size_hint=(1,1),
        )
        split_amount_buttons.add_widget(split_cash_btn)
        split_amount_buttons.add_widget(split_credit_btn)
        split_amount_buttons.add_widget(split_debit_btn)
        split_amount_buttons.add_widget(split_cancel_btn)
        split_amount_layout.add_widget(split_amount_remaining)
        split_amount_layout.add_widget(split_amount_input)
        split_amount_layout.add_widget(split_amount_buttons)

        self.split_amount_popup.open()

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
            self.split_amount_popup.dismiss()
        elif method == "Debit":
            self.show_split_card_confirm(amount, method)
            self.split_amount_popup.dismiss()
        elif method == "Credit":
            self.show_split_card_confirm(amount, method)
            self.split_amount_popup.dismiss()

    def split_cash_continue(self, amount):
        tolerance = 0.001
        self.dismiss_popups(
            "split_cash_popup", "split_cash_confirm_popup", "split_change_popup"
        )

        if abs(self.split_payment_info["remaining_amount"]) <= tolerance:
            self.finalize_split_payment()
        else:
            self.show_split_payment_popup(subsequent_payment=True)

    def split_card_continue(self, amount, method):
        print("split_card_continue", amount, method)
        tolerance = 0.001
        self.dismiss_popups("split_card_confirm_popup")

        if abs(self.split_payment_info["remaining_amount"]) <= tolerance:
            self.finalize_split_payment()
        else:
            self.show_split_payment_popup(subsequent_payment=True)

    def show_split_card_confirm(self, amount, method):
        open_cash_drawer()
        split_card_confirm = BoxLayout()
        split_card_confirm_text = Label(text=f"{amount} {method} payment confirmed")
        tolerance = 0.001

        if abs(self.split_payment_info["remaining_amount"]) <= tolerance:
            split_card_confirm_next_btn = self.create_md_raised_button(
                "Done",
                lambda x: self.split_card_continue(amount, method),
            )
        else:
            split_card_confirm_next_btn = self.create_md_raised_button(
                "Next",
                lambda x: self.split_card_continue(amount, method),
            )
        split_card_confirm.add_widget(split_card_confirm_text)
        split_card_confirm.add_widget(split_card_confirm_next_btn)
        self.split_card_confirm_popup = Popup(
            content=split_card_confirm,
            size_hint=(0.4, 0.4),
        )
        self.split_card_confirm_popup.open()

    def show_split_cash_confirm(self, amount):
        split_cash_confirm = BoxLayout()
        split_cash_confirm_text = Label(text=f"{amount} cash payment confirmed")
        tolerance = 0.001

        if abs(self.split_payment_info["remaining_amount"]) <= tolerance:
            split_cash_confirm_next_btn = self.create_md_raised_button(
                "Done",
                lambda x: self.split_cash_continue(amount),
            )
        else:
            split_cash_confirm_next_btn = self.create_md_raised_button(
                "Next",
                lambda x: self.split_cash_continue(amount),
            )

        split_cash_confirm.add_widget(split_cash_confirm_text)
        split_cash_confirm.add_widget(split_cash_confirm_next_btn)
        self.split_cash_confirm_popup = Popup(
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
        for cash_amount in common_amounts:
            btn = Button(
                text=f"${cash_amount}",
                on_press=self.split_on_preset_amount_press,
            )
            split_cash_keypad_layout.add_widget(btn)

        split_custom_cash_button = self.create_md_raised_button(
            "Custom",
            lambda x: self.split_open_custom_cash_popup,  #####
            (0.8, 0.8),
        )

        split_cash_confirm_button = self.create_md_raised_button(
            "Confirm",
            lambda x: self.split_on_cash_confirm(x, amount),
            (0.8, 0.8),
        )

        split_cash_cancel_button = Button(
            text="Cancel",
            on_press=lambda x: self.split_on_cash_cancel,
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
        print("end of split cash popup")
        self.split_cash_popup.open()

    def split_on_preset_amount_press(self, instance):
        self.split_cash_input.text = instance.text.strip("$")

    def split_open_custom_cash_popup(self, instance):
        pass

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
            size_hint=(None, None),
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
    Popup display functions
    """

    def show_add_or_bypass_popup(self, barcode):
        popup_layout = BoxLayout(orientation="vertical", spacing=5)
        popup_layout.add_widget(Label(text=f"Barcode: {barcode}"))
        button_layout = BoxLayout(orientation="horizontal", spacing=5)

        for option in ["Add Custom Item", "Add to Database"]:
            btn = self.create_md_raised_button(
                option,
                lambda x, barcode=barcode: self.dismiss_bypass_popup(x, barcode),
                (0.5, 0.4),
            )
            button_layout.add_widget(btn)

        popup_layout.add_widget(button_layout)

        self.popup = Popup(
            title="Item Not Found", content=popup_layout, size_hint=(0.8, 0.6)
        )
        self.popup.open()

    def on_item_click(self, item_id):
        item_info = self.order_manager.items.get(item_id)
        if item_info:
            item_name = item_info["name"]
            item_quantity = item_info["quantity"]
            item_price = item_info["total_price"]

        item_popup_layout = GridLayout(rows=3, size_hint=(0.8, 0.8))
        details_layout = BoxLayout(orientation="vertical")
        details_layout.add_widget(
            Label(text=f"Name: {item_name}\nPrice: ${item_price}")
        )

        item_popup_layout.add_widget(details_layout)

        quantity_layout = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height="48dp",
        )
        quantity_layout.add_widget(
            self.create_md_raised_button(
                "-",
                lambda x: self.adjust_item_quantity(item_id, -1),
            )
        )
        quantity_layout.add_widget(Label(text=str(item_quantity)))
        quantity_layout.add_widget(
            self.create_md_raised_button(
                "+",
                lambda x: self.adjust_item_quantity(item_id, 1),
            )
        )
        item_popup_layout.add_widget(quantity_layout)

        buttons_layout = BoxLayout(
            orientation="horizontal", spacing=5, size_hint_y=None, size_hint_x=1
        )
        buttons_layout.add_widget(
            self.create_md_raised_button(
                "Add Discount",
                lambda x: self.add_discount_popup(item_name, item_price),
                (1, 0.4),
            )
        )

        buttons_layout.add_widget(
            self.create_md_raised_button(
                "Remove Item",
                lambda x: self.remove_item(item_name, item_price),
                (1, 0.4),
            )
        )
        buttons_layout.add_widget(
            Button(
                text="Cancel",
                on_press=lambda x: self.close_item_popup(),
                size_hint=(1, 0.4),
            )
        )
        item_popup_layout.add_widget(buttons_layout)

        self.item_popup = Popup(
            title="Item Details", content=item_popup_layout, size_hint=(0.4, 0.4)
        )
        self.item_popup.open()

    def add_discount_popup(self, item_name, item_price):
        discount_layout = BoxLayout(
            orientation="vertical", size_hint_x=0.8, size_hint_y=0.8
        )

        percent_layout = BoxLayout(orientation="horizontal", size_hint_y=0.1)
        percent_input = TextInput(multiline=False, hint_text="Percent")
        percent_layout.add_widget(percent_input)

        amount_layout = BoxLayout(orientation="horizontal", size_hint_y=0.1)
        amount_input = TextInput(multiline=False, hint_text="Amount")
        amount_layout.add_widget(amount_input)

        button_layout = BoxLayout(
            orientation="horizontal", size_hint_y=None, height="50dp", spacing=10
        )
        button_layout.add_widget(
            self.create_md_raised_button(
                "Confirm",
                lambda x: self.discount_single_item(
                    discount_amount=amount_input.text,
                    discount_percentage=percent_input.text,
                    discount_popup=popup,
                ),
                (0.8, 0.8),
            )
        )
        button_layout.add_widget(
            self.Button(
                text="Cancel",
                on_press=lambda x: self.dismiss_add_discount_popup(discount_popup=popup),
            )
        )
        discount_layout.add_widget(percent_layout)
        discount_layout.add_widget(amount_layout)
        discount_layout.add_widget(button_layout)

        popup = Popup(
            title="Add Discount",
            pos_hint={"top": 1},
            content=discount_layout,
            size_hint=(0.8, 0.4),
        )
        popup.open()

    def show_theme_change_popup(self):
        layout = GridLayout(cols=4, rows=8, orientation="lr-tb")

        button_layout = GridLayout(
            cols=4, rows=8, orientation="lr-tb", spacing=5, size_hint=(1, 0.4)
        )
        button_layout.bind(minimum_height=button_layout.setter("height"))

        for color in palette:
            button = self.create_md_raised_button(
                color,
                lambda x, col=color: self.set_primary_palette(col),
                (0.8, 0.8),
            )

            button_layout.add_widget(button)

        dark_btn = MDRaisedButton(
            text="Dark Mode",
            size_hint=(0.8, 0.8),
            md_bg_color=(0, 0, 0, 1),
            on_release=lambda x, col=color: self.toggle_dark_mode(),
        )
        button_layout.add_widget(dark_btn)
        layout.add_widget(button_layout)

        self.theme_change_popup = Popup(
            title="",
            content=layout,
            size_hint=(0.6, 0.6),
            background="transparent.png",
            background_color=(0, 0, 0, 0),
            separator_height=0,
        )
        self.theme_change_popup.open()

    def show_system_popup(self):
        float_layout = FloatLayout()

        system_buttons = [
            "Change Theme",
            "Reboot System",
            "Restart App",
            "TEST"
        ]

        for index, tool in enumerate(system_buttons):
            btn = MDRaisedButton(
                text=tool,
                size_hint=(0.4, 0.1),
                pos_hint={"center_x": 0.5, "center_y": 1 - 0.2 * index},
                on_press=self.on_system_button_press,
            )
            float_layout.add_widget(btn)

        self.system_popup = Popup(
            content=float_layout,
            size_hint=(0.6, 0.6),
            title="",
            background="transparent.png",
            background_color=(0, 0, 0, 0),
            separator_height=0,
        )
        self.system_popup.open()

    def show_label_printing_view(self):
        inventory = self.db_manager.get_all_items()
        label_printing_view = LabelPrintingView()
        self.current_context = "label"
        print("label printing context", self.current_context)
        label_printing_view.show_inventory_for_label_printing(inventory)
        popup = Popup(
            title="Label Printing", content=label_printing_view, size_hint=(0.9, 0.9)
        )
        popup.bind(on_dismiss=self.reset_to_main_context)
        popup.open()

    def show_inventory_management_view(self):
        self.in_inventory_management_view = True
        self.inventory_manager_view = InventoryManagementView()
        inventory = self.db_manager.get_all_items()
        self.inventory_manager_view.show_inventory_for_manager(inventory)
        self.current_context = "inventory"

        popup = Popup(
            title="Inventory Management",
            content=self.inventory_manager_view,
            size_hint=(0.9, 0.9),
        )
        popup.bind(on_dismiss=self.reset_to_main_context)
        popup.open()

    def show_adjust_price_popup(self):
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

        confirm_button = self.create_md_raised_button(
            "Confirm",
            self.add_adjusted_price_item,
        )

        cancel_button = Button(
            text="Cancel",
            on_press=self.on_adjust_price_cancel,
        )
        self.adjust_price_popup_layout.add_widget(confirm_button)
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
            guard_layout = BoxLayout()
            guard_popup = Popup(
                title="Guard Screen",
                content=guard_layout,
                size_hint=(1, 1),
                auto_dismiss=False,
            )
            guard_popup.bind(on_touch_down=lambda x, touch: guard_popup.dismiss())
            self.is_guard_screen_displayed = True
            guard_popup.bind(
                on_dismiss=lambda x: setattr(self, "is_guard_screen_displayed", False)
            )
            guard_popup.open()

    def show_lock_screen(self):
        if not self.is_lock_screen_displayed:
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
                "0",
                "Reset",
                " ",
            ]

            for button in numeric_buttons:
                if button != " ":
                    btn = MDFlatButton(
                        text=button,
                        text_color=(0, 0, 0, 1),
                        font_style="H4",
                        size_hint=(0.8, 0.8),
                        on_press=self.on_lock_screen_button_press,
                    )
                    keypad_layout.add_widget(btn)
                else:
                    btn_2 = Button(
                        size_hint=(0.8, 0.8),
                        opacity=0,
                        background_color=(0, 0, 0, 0),
                    )
                    btn_2.bind(on_press=self.manual_override)
                    keypad_layout.add_widget(btn_2)

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

    def show_inventory(self):
        inventory = self.db_manager.get_all_items()
        inventory_view = InventoryView(order_manager=self.order_manager)
        inventory_view.show_inventory(inventory)
        popup = self.create_focus_popup(

            title="Inventory",
            content=inventory_view,
            textinput=inventory_view.ids.label_search_input,
            size_hint=(0.9, 0.9),

        )
        popup.open()

    def show_tools_popup(self):
        float_layout = FloatLayout()

        tool_buttons = [
            "Clear Order",
            "Open Register",
            "Reporting",
            "Label Printer",
            "Inventory Management",
            "System",
        ]

        for index, tool in enumerate(tool_buttons):
            btn = MDRaisedButton(
                text=tool,
                size_hint=(0.4, 0.1),
                pos_hint={"center_x": 0.5, "center_y": 1 - 0.2 * index},
                on_press=self.on_tool_button_press,
            )
            float_layout.add_widget(btn)

        self.tools_popup = Popup(
            content=float_layout,
            size_hint=(0.6, 0.6),
            title="",
            background="transparent.png",
            background_color=(0, 0, 0, 0),
            separator_height=0,
        )
        self.tools_popup.open()

    def show_custom_item_popup(self, barcode):
        self.custom_item_popup_layout = BoxLayout(orientation="vertical", spacing=10)
        self.cash_input = TextInput(
            text="",
            disabled=True,
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
            btn = Button(
                text=button,
                on_press=self.on_numeric_button_press,
                size_hint=(0.8, 0.8),
            )
            keypad_layout.add_widget(btn)

        confirm_button = self.create_md_raised_button(
            "Confirm",
            self.add_custom_item,
            (0.8, 0.8),
        )

        cancel_button = Button(
            text="Cancel",
            on_press=self.on_custom_item_cancel,
            size_hint=(0.8, 0.8),
        )

        keypad_layout.add_widget(confirm_button)
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

        button_layout = BoxLayout(
            size_hint_y=None,
            height=50,
            spacing=5,
        )

        btn_pay_cash = self.create_md_raised_button(
            f"[b][size=20]Pay Cash[/b][/size]",
            self.on_payment_button_press,
            (0.8, 1.5),
        )

        btn_pay_credit = self.create_md_raised_button(
            f"[b][size=20]Pay Credit[/b][/size]",
            self.on_payment_button_press,
            (0.8, 1.5),
        )
        btn_pay_debit = self.create_md_raised_button(
            f"[b][size=20]Pay Debit[/b][/size]",
            self.on_payment_button_press,
            (0.8, 1.5),
        )

        btn_pay_split = self.create_md_raised_button(
            "Split",
            self.on_payment_button_press,
            (0.8, 1.5),
        )

        btn_cancel = Button(
            text="Cancel",
            on_press=self.on_payment_button_press,
            size_hint=(0.8, 1.5),
        )
        button_layout.add_widget(btn_pay_cash)
        button_layout.add_widget(btn_pay_debit)
        button_layout.add_widget(btn_pay_credit)
        button_layout.add_widget(btn_pay_split)
        button_layout.add_widget(btn_cancel)

        popup_layout.add_widget(button_layout)

        self.finalize_order_popup = Popup(
            title="Finalize Order", content=popup_layout, size_hint=(0.8, 0.8)
        )
        self.finalize_order_popup.open()

    def show_cash_payment_popup(self):
        total_with_tax = self.order_manager.calculate_total_with_tax()
        common_amounts = self.calculate_common_amounts(total_with_tax)

        self.cash_popup_layout = BoxLayout(orientation="vertical", spacing=10)
        self.cash_input = MoneyInput(
            text=f"{total_with_tax:.2f}",
            disabled=True,
            input_type="number",
            multiline=False,
            input_filter="float",
            font_size=30,
            size_hint_y=0.2,
            size_hint_x=0.3,
            height=50,
        )
        self.cash_popup_layout.add_widget(self.cash_input)

        keypad_layout = GridLayout(cols=2, spacing=5)
        other_buttons = BoxLayout(
            orientation="horizontal",
            spacing=5,
            size_hint=(1, 0.4),
        )

        for amount in common_amounts:
            btn = Button(text=f"${amount}", on_press=self.on_preset_amount_press)
            keypad_layout.add_widget(btn)

        custom_cash_button = self.create_md_raised_button(
            "Custom",
            self.open_custom_cash_popup,
            (0.4, 0.8),
        )

        confirm_button = self.create_md_raised_button(
            f"[b]Confirm[/b]",
            self.on_cash_confirm,
            (0.4, 0.8),
        )

        cancel_button = Button(
            text="Cancel",
            on_press=self.on_cash_cancel,
            size_hint=(0.4, 0.8),
        )

        other_buttons.add_widget(confirm_button)
        other_buttons.add_widget(cancel_button)
        other_buttons.add_widget(custom_cash_button)


        self.cash_popup_layout.add_widget(keypad_layout)
        self.cash_popup_layout.add_widget(other_buttons)
        self.cash_popup = Popup(
            title="Amount Tendered",
            content=self.cash_popup_layout,
            size_hint=(0.8, 0.8),
        )
        self.cash_popup.open()

    def open_custom_cash_popup(self, instance):
        self.custom_cash_popup_layout = BoxLayout(orientation="vertical", spacing=10)
        self.cash_input = TextInput(
            text="",
            multiline=False,
            input_filter="float",
            font_size=30,
            size_hint_y=None,
            height=50,
        )
        self.custom_cash_popup_layout.add_widget(self.cash_input)

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
            btn = self.create_md_raised_button(
                button,
                self.on_numeric_button_press,
                (0.8, 0.8),
            )
            keypad_layout.add_widget(btn)

        confirm_button = self.create_md_raised_button(
            "Confirm",
            lambda instance: self.on_cash_confirm(instance),
            (0.8, 0.8),
        )

        cancel_button = Button(
            text="Cancel",
            on_press=self.on_custom_cash_cancel,
            size_hint=(0.8, 0.8),
        )
        keypad_layout.add_widget(confirm_button)
        keypad_layout.add_widget(cancel_button)

        self.custom_cash_popup_layout.add_widget(keypad_layout)
        self.custom_cash_popup = Popup(
            title="Custom Item",
            content=self.custom_cash_popup_layout,
            size_hint=(0.8, 0.8),
        )
        self.custom_cash_popup.open()

    def show_payment_confirmation_popup(self):
        confirmation_layout = GridLayout(
            orientation="lr-tb",
            cols=1,
            size_hint=(1, 1),
            spacing=10,
        )
        total_with_tax = self.order_manager.calculate_total_with_tax()
        order_summary = "Order Complete:\n\n"

        for item_id, item_details in self.order_manager.items.items():
            item_name = item_details["name"]
            quantity = item_details["quantity"]
            total_price_for_item = item_details["total_price"]

            try:
                total_price_float = float(total_price_for_item)
            except ValueError as e:
                print(e)
                continue

            order_summary += f"{item_name} x{quantity}  ${total_price_float:.2f}\n"

        order_summary += f"Total with Tax: ${total_with_tax:.2f}"
        confirmation_layout.add_widget(Label(text=order_summary))

        done_button = self.create_md_raised_button(
            "Done",
            self.on_done_button_press,
            (0.2, 0.2),
        )

        receipt_button = self.create_md_raised_button(
            "Print Receipt",
            self.on_receipt_button_press,
            (0.2, 0.2),
        )

        confirmation_layout.add_widget(done_button)
        confirmation_layout.add_widget(receipt_button)

        self.payment_popup = Popup(
            title="Payment Confirmation",
            content=confirmation_layout,
            size_hint=(0.8, 0.8),
        )
        self.finalize_order_popup.dismiss()
        self.payment_popup.open()

    def show_make_change_popup(self, change):
        change_layout = BoxLayout(orientation="vertical", spacing=10)
        change_layout.add_widget(Label(text=f"Change to return: ${change:.2f}"))

        done_button = self.create_md_raised_button(
            "Done",
            self.on_change_done,
        )
        change_layout.add_widget(done_button)

        self.change_popup = Popup(
            title="Change Calculation", content=change_layout, size_hint=(0.6, 0.3)
        )
        self.change_popup.open()

    def show_add_to_database_popup(self, barcode):
        content = BoxLayout(orientation="vertical", padding=10)

        name_layout = BoxLayout(orientation="horizontal", size_hint_y=0.4)
        name_input = TextInput()
        name_layout.add_widget(Label(text="Name", size_hint_x=0.2))
        name_layout.add_widget(name_input)

        barcode_layout = BoxLayout(orientation="horizontal", size_hint_y=0.4)
        barcode_input = TextInput(
            input_filter="int", text=barcode
        )
        barcode_layout.add_widget(Label(text="Barcode", size_hint_x=0.2))
        barcode_layout.add_widget(barcode_input)

        price_layout = BoxLayout(orientation="horizontal", size_hint_y=0.4)
        price_input = TextInput(input_filter="float")
        price_layout.add_widget(Label(text="Price", size_hint_x=0.2))
        price_layout.add_widget(price_input)

        cost_layout = BoxLayout(orientation="horizontal", size_hint_y=0.4)
        cost_input = TextInput(input_filter="float")
        cost_layout.add_widget(Label(text="Cost", size_hint_x=0.2))
        cost_layout.add_widget(cost_input)

        sku_layout = BoxLayout(orientation="horizontal", size_hint_y=0.4)
        sku_input = TextInput()
        sku_layout.add_widget(Label(text="SKU", size_hint_x=0.2))
        sku_layout.add_widget(sku_input)

        content.add_widget(name_layout)
        content.add_widget(barcode_layout)
        content.add_widget(price_layout)
        content.add_widget(cost_layout)
        content.add_widget(sku_layout)

        button_layout = BoxLayout(
            orientation="horizontal", size_hint_y=None, height="50dp", spacing=10
        )

        button_layout.add_widget(
            MDRaisedButton(
                text="Confirm",
                on_press=lambda x: self.add_item_to_database(
                    barcode,
                    name_input.text,
                    price_input.text,
                    cost_input.text,
                    sku_input.text
                )
            )
        )

        button_layout.add_widget(
            Button(text="Cancel", on_press=lambda x: self.close_add_to_database_popup(x))
        )

        content.add_widget(button_layout)

        self.add_to_db_popup = Popup(
            title="Add to Database",
            content=content,
            size_hint=(0.8, 0.4),
            auto_dismiss=False,
            pos_hint={"top": 1},
        )

        self.add_to_db_popup.open()

    """
    Accessory functions
    """

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

    def remove_item(self, item_name, item_price):
        self.order_manager.remove_item(item_name)
        self.update_display()
        self.update_financial_summary()
        self.close_item_popup()

    def close_item_popup(self):
        if self.item_popup:
            self.item_popup.dismiss()

    def dismiss_add_discount_popup(self, discount_popup):
        if discount_popup:
            discount_popup.dismiss()

    def reset_pin_timer(self):
        if self.pin_reset_timer is not None:
            self.pin_reset_timer.cancel()

        self.pin_reset_timer = threading.Timer(5.0, self.reset_pin)
        self.pin_reset_timer.start()

    def reset_pin(self):
        self.entered_pin = ""

    def adjust_item_quantity(self, item_id, adjustment):
        self.order_manager.adjust_item_quantity(item_id, adjustment)
        self.item_popup.dismiss()
        self.on_item_click(item_id)
        self.update_display()
        self.update_financial_summary()

    def discount_single_item(
        self, discount_popup, discount_amount=None, discount_percentage=None
    ):
        try:
            discount_amount = float(discount_amount) if discount_amount else None
            discount_percentage = (
                float(discount_percentage) if discount_percentage else None
            )
        except ValueError as e:
            print(e)

        if discount_amount is not None:
            self.order_manager.add_discount(discount_amount=discount_amount)
            self.update_display()
            self.update_financial_summary()
        elif discount_percentage is not None:
            self.order_manager.add_discount(discount_percentage=discount_percentage)

            self.update_display()
            self.update_financial_summary()
        discount_popup.dismiss()
        if hasattr(self, "item_popup") and self.item_popup is not None:
            self.item_popup.dismiss()

    def dismiss_bypass_popup(self, instance, barcode):
        self.on_add_or_bypass_choice(instance.text, barcode)
        self.popup.dismiss()

    def on_add_or_bypass_choice(self, choice_text, barcode):
        if choice_text == "Add Custom Item":
            self.show_custom_item_popup(barcode)
        elif choice_text == "Add to Database":
            self.show_add_to_database_popup(barcode)

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

    def close_add_to_database_popup(self, instance):
        self.add_to_db_popup.dismiss()

    def update_clock(self, *args):
        self.clock_label.text = time.strftime("%I:%M %p\n%A\n%B %d, %Y\n")
        self.clock_label.color = self.get_text_color()

    def get_text_color(self):
        if self.theme_cls.theme_style == "Dark":
            return (1, 1, 1, 1)
        else:
            return (0, 0, 0, 1)

    def update_financial_summary(self):
        subtotal = self.order_manager.subtotal
        total_with_tax = self.order_manager.calculate_total_with_tax()
        tax = self.order_manager.tax_amount
        discount = self.order_manager.order_discount

        self.financial_summary_widget.update_summary(
            subtotal, tax, total_with_tax, discount
        )

    def add_adjusted_price_item(self, instance):
        target_amount = self.target_amount_input.text
        try:
            target_amount = float(target_amount)
        except ValueError as e:
            print(e)

        self.order_manager.adjust_order_to_target_total(target_amount)
        self.update_display()
        self.update_financial_summary()
        self.adjust_price_popup.dismiss()

    def is_monitor_off(self):
        try:
            result = subprocess.run(["xset", "-q"], stdout=subprocess.PIPE)
            output = result.stdout.decode("utf-8")
            return "Monitor is Off" in output
        except Exception as e:
            print(e)
            return False

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

    def turn_off_monitor(self):
        touchscreen_device = "iSolution multitouch"

        try:
            subprocess.run(["xinput", "disable", touchscreen_device], check=True)
        except subprocess.CalledProcessError as e:
            print(e)
            return

        try:
            subprocess.run(["xset", "dpms", "force", "off"], check=True)
        except subprocess.CalledProcessError as e:
            print(e)
            subprocess.run(["xinput", "enable", touchscreen_device])
            return

        def reenable_touchscreen():
            time.sleep(1)
            try:
                subprocess.run(["xinput", "enable", touchscreen_device], check=True)
            except subprocess.CalledProcessError as e:
                print(e)

        threading.Thread(target=reenable_touchscreen).start()

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

        order_summary = "Order Summary:\n\n"
        for item_id, item_details in self.order_manager.items.items():
            item_name = item_details["name"]
            quantity = item_details["quantity"]
            total_price_for_item = item_details["total_price"]

            try:
                total_price_float = float(total_price_for_item)
            except ValueError as e:
                print(e)
                continue

            order_summary += f"{item_name} x{quantity}  ${total_price_float:.2f}\n"
        order_summary += f"Total with Tax: ${total_with_tax:.2f}"

        self.show_order_popup(order_summary)

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
            item_button.bind(on_press=lambda instance, x=item_id: self.on_item_click(x))
            self.order_layout.add_widget(item_button)

    def handle_credit_payment(self):
        open_cash_drawer()
        self.order_manager.set_payment_method("Credit")
        self.show_payment_confirmation_popup()

    def handle_debit_payment(self):
        open_cash_drawer()
        self.order_manager.set_payment_method("Debit")
        self.show_payment_confirmation_popup()

    def on_change_done(self, instance):
        self.change_popup.dismiss()
        self.show_payment_confirmation_popup()

    def on_cash_confirm(self, instance):
        amount_tendered = float(self.cash_input.text)
        total_with_tax = self.order_manager.calculate_total_with_tax()
        change = amount_tendered - total_with_tax
        if hasattr(self, "cash_popup"):
            self.cash_popup.dismiss()
        if hasattr(self, "custom_cash_popup"):
            self.custom_cash_popup.dismiss()
        open_cash_drawer()
        self.order_manager.set_payment_method("Cash")
        self.order_manager.set_payment_details(amount_tendered, change)
        self.show_make_change_popup(change)

    def on_cash_cancel(self, instance):
        self.cash_popup.dismiss()

    def reset_to_main_context(self, instance):
        self.current_context = "main"
        try:
            self.inventory_manager.detach_from_parent()
            self.label_manager.detach_from_parent()
        except Exception as e:
            print(e)

    def on_adjust_price_cancel(self, instance):
        self.adjust_price_popup.dismiss()

    def on_preset_amount_press(self, instance):
        self.cash_input.text = instance.text.strip("$")

    def add_custom_item(self, instance):
        price = self.cash_input.text
        try:
            price = float(price)
        except ValueError:
            return

        custom_item_name = "Custom Item"
        self.order_manager.add_item(custom_item_name, price)
        self.update_display()
        self.update_financial_summary()
        self.custom_item_popup.dismiss()

    def on_custom_item_cancel(self, instance):
        self.custom_item_popup.dismiss()

    def on_custom_cash_cancel(self, instance):
        self.custom_cash_popup.dismiss()

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

    def add_item_to_database(self, barcode, name, price, cost=0.0, sku=None):
        if barcode and name and price:
            try:
                self.db_manager.add_item(barcode, name, price, cost, sku)
                self.add_to_db_popup.dismiss()
            except Exception as e:
                print(e)
        else:
            print("must have barcode and name and price")

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

    @eel.expose
    @staticmethod
    def get_order_history_for_eel():
        db_manager = DatabaseManager("inventory.db")
        order_history = db_manager.get_order_history()
        formatted_data = [
            {"order_id": order[0], "items": order[1], "total": order[2], "tax": order[3], "discount": order[4],
            "total_with_tax": order[5], "timestamp": order[6], "payment_method": order[7],
            "amount_tendered": order[8], "change_given": order[9]}
            for order in order_history
        ]
        return formatted_data


    def start_eel(self):
        eel.init('web')
        print("start eel")
        eel.start('index.html')

    def create_focus_popup(self, title, content, textinput, size_hint, pos_hint={}):
        popup = FocusPopup(title=title, content=content, size_hint=size_hint, pos_hint=pos_hint)
        popup.focus_on_textinput(textinput)
        return popup

    def create_md_raised_button(
        self,
        text,
        on_press_action,
        size_hint = (None, None),
        font_style="Body1",
        height=50,
        # size_hint_y=None,
        # size_hint_x=None,
    ):
        button = MDRaisedButton(
            text=text,
            on_press=on_press_action,
            size_hint=size_hint,
            font_style=font_style,
            height=height,
            # size_hint_y=size_hint_y,
            # size_hint_x=size_hint_x,
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

class MarkupLabel(Label):
    pass


class MoneyInput(TextInput):
    def insert_text(self, substring, from_undo=False):
        if not from_undo:
            current_text = self.text.replace(".", "") + substring
            current_text = current_text.zfill(3)
            new_text = current_text[:-2] + "." + current_text[-2:]
            super(MoneyInput, self).insert_text(new_text, from_undo=from_undo)
            return True
        else:
            return super(MoneyInput, self).insert_text(substring, from_undo=from_undo)

class FocusPopup(Popup):
    def focus_on_textinput(self, textinput):
        self.textinput_to_focus = textinput

    def on_open(self):
        if hasattr(self, 'textinput_to_focus'):
            self.textinput_to_focus.focus = True

class FinancialSummaryWidget(MDRaisedButton):
    def __init__(self, **kwargs):
        super(FinancialSummaryWidget, self).__init__(**kwargs)
        self.size_hint_y = None
        self.size_hint_x = 1
        self.height = 80
        self.orientation = "vertical"

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

    def open_order_modification_popup(self):
        order_mod_layout = GridLayout(cols=1, size_hint=(0.8, 0.8))
        adjust_price_button = MDRaisedButton(
            text="Adjust Payment",
            on_press=lambda x: app.show_adjust_price_popup(),
        )

        order_mod_layout.add_widget(adjust_price_button)
        popup = Popup(
            title="Modify Order",
            content=order_mod_layout,
            size_hint=(None, None),
            size=(400, 400),
        )
        popup.open()






try:
    app = CashRegisterApp()
    app.run()
except KeyboardInterrupt:
    print("test")
# if __name__ == "__main__":
#     app = CashRegisterApp()
#     app.run()
#     #app.show_lock_screen()
