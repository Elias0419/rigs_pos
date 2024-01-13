import datetime
import json
import random
import re
import subprocess
import sys
import time

from kivy.app import App
from kivy.clock import Clock
from kivy.config import Config
from kivy.core.window import Window
from kivy.lang import Builder
from kivy.metrics import dp
from kivy.modules import inspector
from kivy.properties import StringProperty, ListProperty, ObjectProperty
from kivy.uix.anchorlayout import AnchorLayout
from kivy.uix.button import Button
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.recycleview.views import RecycleDataViewBehavior
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput

from kivymd.app import MDApp
from kivymd.color_definitions import palette
from kivymd.theming import ThemeManager
from kivymd.uix.boxlayout import BoxLayout
from kivymd.uix.button import (MDFlatButton, MDIconButton, MDRaisedButton,
                               MDRectangleFlatButton,
                               MDRectangleFlatIconButton)
from kivymd.uix.dialog import MDDialog
from kivymd.uix.gridlayout import GridLayout
from kivymd.uix.label import MDLabel
from kivymd.uix.menu.menu import MDDropdownMenu
from kivymd.uix.recycleview import RecycleView
from kivymd.uix.scrollview import ScrollView as MDScrollView
from kivymd.uix.selectioncontrol import MDSwitch
from kivymd.uix.textfield import MDTextField, MDTextFieldRect

from barcode.upc import UniversalProductCodeA as upc_a
from barcode_scanner import BarcodeScanner
from database_manager import DatabaseManager
from label_printer import LabelPrinter
from open_cash_drawer import open_cash_drawer
from order_manager import OrderManager

Config.set("kivy", "keyboard_mode", "systemanddock")
Window.maximize()
Window.borderless = True


class CashRegisterApp(MDApp):
    def __init__(self, **kwargs):
        super(CashRegisterApp, self).__init__(**kwargs)
        self.last_scanned_item = None
        self.correct_pin = "1234"
        self.entered_pin = ""
        self.is_guard_screen_displayed = False
        self.is_lock_screen_displayed = False
        self.in_inventory_management_view = False
        self.inventory_manager_view = None
        self.theme_cls.theme_style = "Light"
        self.theme_cls.primary_palette = "Brown"
        self.load_settings()

    def build(self):
        self.barcode_scanner = BarcodeScanner()
        self.db_manager = DatabaseManager("inventory.db")
        self.order_manager = OrderManager()

        main_layout = GridLayout(cols=1, orientation="tb-lr", row_default_height=60)
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

        button_layout = GridLayout(cols=4, size_hint_y=1 / 8, orientation="lr-tb")

        btn_pay = MDRaisedButton(
            text="Pay", font_style="H6", size_hint=(8, 8), on_press=self.on_button_press
        )
        btn_custom_item = MDRaisedButton(
            text="Custom",font_style="H6", size_hint=(8, 8), on_press=self.on_button_press
        )
        btn_inventory = MDRaisedButton(
            text="Search",font_style="H6", size_hint=(8, 8), on_press=self.on_button_press
        )
        btn_tools = MDRaisedButton(
            text="Tools",font_style="H6", size_hint=(8, 8), on_press=self.on_button_press
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
            color=(0, 0, 0, 1),
            halign="center"
        )

        Clock.schedule_interval(self.update_clock, 1)

        clock_layout.add_widget(self.clock_label)
        return clock_layout

    def update_clock(self, *args):
        self.clock_label.text = time.strftime("%I:%M %p\n%A\n%B %d, %Y\n")

    def create_financial_layout(self):
        financial_layout = GridLayout(cols=1, size_hint_x=1 / 3)

        self.financial_summary_widget = FinancialSummaryWidget()
        financial_layout.add_widget(self.financial_summary_widget)

        return financial_layout

    def update_financial_summary(self):
        subtotal = self.order_manager.total
        tax = subtotal * self.order_manager.tax_rate
        total_with_tax = self.order_manager.calculate_total_with_tax()

        self.financial_summary_widget.update_summary(subtotal, tax, total_with_tax)



    """
    Barcode functions
    """

    def check_for_scanned_barcode(self, dt):
        if self.barcode_scanner.is_barcode_ready():
            barcode = self.barcode_scanner.read_barcode()
            print(f"Barcode scanned: {barcode}")
            self.handle_scanned_barcode(barcode)

    def handle_scanned_barcode(self, barcode):
        # if self.in_inventory_management_view and self.inventory_manager_view:
        #     self.inventory_manager_view.show_add_item_popup(barcode)
        # else:
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
                print(f"Error handling scanned barcode: {e}")

    def show_add_or_bypass_popup(self, barcode):
        popup_layout = BoxLayout(orientation="vertical", spacing=10)

        popup_layout.add_widget(Label(text=f"Barcode: {barcode}"))

        button_layout = BoxLayout(orientation="horizontal", spacing=10)

        for option in ["Add Custom Item", "Add to Database"]:
            btn = MDRaisedButton(
                text=option,
                size_hint=(0.5, 0.4),
                on_press=lambda x, barcode=barcode: self.dismiss_bypass_popup(
                    x, barcode
                ),
            )
            button_layout.add_widget(btn)

        popup_layout.add_widget(button_layout)

        self.popup = Popup(
            title="Item Not Found", content=popup_layout, size_hint=(0.8, 0.6)
        )
        self.popup.open()

    def dismiss_bypass_popup(self, instance, barcode):
        self.on_add_or_bypass_choice(instance.text, barcode)
        self.popup.dismiss()

    def on_add_or_bypass_choice(self, choice_text, barcode):
        if choice_text == "Add Custom Item":
            self.show_custom_item_popup(barcode)
        elif choice_text == "Add to Database":
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
            self.update_financial_summary()
        elif instance.text == "Open Register":
            open_cash_drawer()
        elif instance.text == "Reporting":
            self.show_reporting_popup()
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
            sys.exit(1)
        elif instance.text == "Change Theme":
            self.show_theme_change_popup()
        self.system_popup.dismiss()

    def on_button_press(self, instance):
        button_text = instance.text

        if button_text == "Clear Order":
            self.order_layout.clear_widgets()
            self.order_manager.clear_order()
        elif button_text == "Pay":
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

    def on_item_click(self, item_id):
        item_info = self.order_manager.items.get(item_id)
        if item_info:
            item_name = item_info['name']
            item_quantity = item_info['quantity']
            item_price = item_info['total_price']

        # Use GridLayout with 2 rows
        item_popup_layout = GridLayout(rows=2)

        # Top row for item details
        details_layout = BoxLayout(orientation="vertical")
        details_layout.add_widget(Label(text=f"Name: {item_name}\nPrice: ${item_price}"))
        #details_layout.add_widget(Label(text=f"Price: ${item_price}"))
        item_popup_layout.add_widget(details_layout)

        # Bottom row for buttons
        buttons_layout = BoxLayout(orientation="horizontal", spacing=10, size_hint_y=None, size_hint_x=None)
        buttons_layout.add_widget(MDRaisedButton(
            text="Modify Item",
            size_hint=(0.8,0.8),
            on_press=lambda x: self.modify_item(item_name, item_price),
        ))
        buttons_layout.add_widget(MDRaisedButton(
            text="Tax Adjust",
            size_hint=(0.8,0.8),
            on_press=lambda x: self.show_adjust_price_popup(item_name, item_price),
        ))
        buttons_layout.add_widget(MDRaisedButton(
            text="Remove Item",
            size_hint=(0.8,0.8),
            on_press=lambda x: self.remove_item(item_name, item_price),
        ))
        buttons_layout.add_widget(MDRaisedButton(
            text="Cancel",
            size_hint=(0.8,0.8),
            on_press=lambda x: self.close_item_popup()

        ))
        item_popup_layout.add_widget(buttons_layout)

        # Create and open the popup
        self.item_popup = Popup(
            title="Item Details", content=item_popup_layout, size_hint=(0.8, 0.4)
        )
        self.item_popup.open()

    def modify_item(self, item_name, item_price):
        pass

    def remove_item(self, item_name, item_price):
        self.order_manager.remove_item(item_name)
        self.update_display()
        self.update_financial_summary()
        self.close_item_popup()

    def close_item_popup(self):
        if self.item_popup:
            self.item_popup.dismiss()

    """
    Popup display functions
    """

    def show_theme_change_popup(self):
        layout = GridLayout(cols=4, rows=8, orientation="lr-tb")

        button_layout = GridLayout(cols=4, rows=8, orientation="lr-tb", spacing=5, size_hint=(1, 0.4))
        button_layout.bind(minimum_height=button_layout.setter('height'))

        for color in palette:
            button = MDRaisedButton(
                text=color,
                size_hint=(0.8,0.8),
                #pos_hint={"center_x": 0.5, "center_y": 0.5},
                on_release=lambda x, col=color: self.set_primary_palette(col)
            )

            button_layout.add_widget(button)
        dark_btn =MDRaisedButton(
                text="Dark Mode",
                size_hint=(0.8,0.8),
                md_bg_color=(0,0,0,1),
                #pos_hint={"center_x": 0.5, "center_y": 0.5},
                on_release=lambda x, col=color: self.toggle_dark_mode()
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

    def set_primary_palette(self, color_name):
        self.theme_cls.primary_palette = color_name
        self.save_settings()


    def toggle_dark_mode(self):
        if self.theme_cls.theme_style == "Dark":
             self.theme_cls.theme_style = "Light"
        else:
            self.theme_cls.theme_style = "Dark"
        self.save_settings()


    def show_system_popup(self):
        float_layout = FloatLayout()

        system_buttons = [
            "Change Theme",
            "Reboot System",
            "Restart App",
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

    def reboot_are_you_sure(self):
        arys_layout = BoxLayout()

        btn = MDRaisedButton(
                text="Yes!",
                size_hint=(0.9, 0.9),

                on_press=self.reboot,
            )
        btn2 = MDRaisedButton(
                text="No!",
                size_hint=(0.9, 0.9),

                 on_press=lambda x: popup.dismiss()
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


    def show_label_printing_view(self):
        inventory = self.db_manager.get_all_items()
        label_printing_view = LabelPrintingView()
        label_printing_view.show_inventory_for_label_printing(inventory)
        popup = Popup(
            title="Label Printing", content=label_printing_view, size_hint=(0.9, 0.9)
        )
        popup.open()

    def show_inventory_management_view(self):
        self.in_inventory_management_view = True
        self.inventory_manager_view = InventoryManagementView()
        inventory = self.db_manager.get_all_items()
        #inventory_manager_view = InventoryManagementView()
        self.inventory_manager_view.show_inventory_for_manager(inventory)
        popup = Popup(
            title="Inventory Management",
            content=self.inventory_manager_view,
            size_hint=(0.9, 0.9),
        )
        popup.open()

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

        confirm_button = MDRaisedButton(
            text="Confirm", on_press=self.add_adjusted_price_item
        )
        self.adjust_price_popup_layout.add_widget(confirm_button)

        cancel_button = MDRaisedButton(
            text="Cancel", on_press=self.on_adjust_price_cancel
        )
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
                btn = MDFlatButton(
                    text=button,
                    text_color=(0,0,0,1),
                    font_style="H4",
                    size_hint=(0.8, 0.8),
                    on_press=self.on_lock_screen_button_press
                )
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
            btn = MDRaisedButton(
                text=button, size_hint=(0.8, 0.8), on_press=self.on_numeric_button_press
            )
            keypad_layout.add_widget(btn)

        confirm_button = MDRaisedButton(
            text="Confirm", size_hint=(0.8, 0.8), on_press=self.add_custom_item
        )
        keypad_layout.add_widget(confirm_button)

        cancel_button = MDRaisedButton(
            text="Cancel", size_hint=(0.8, 0.8), on_press=self.on_custom_item_cancel
        )
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

        btn_pay_cash = MDRaisedButton(
            text="Pay Cash", size_hint=(0.8, 1.5), on_press=self.on_payment_button_press
        )
        btn_pay_card = MDRaisedButton(
            text="Pay Card", size_hint=(0.8, 1.5), on_press=self.on_payment_button_press
        )
        btn_cancel = MDRaisedButton(
            text="Cancel", size_hint=(0.8, 1.5), on_press=self.on_payment_button_press
        )
        button_layout.add_widget(btn_pay_cash)
        button_layout.add_widget(btn_pay_card)
        button_layout.add_widget(btn_cancel)

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

        confirm_button = MDRaisedButton(
            text="Confirm",
            size_hint=(0.8,0.8),
            on_press=self.on_cash_confirm)
        keypad_layout.add_widget(confirm_button)

        cancel_button = MDRaisedButton(
            text="Cancel",
            size_hint=(0.8,0.8),
            on_press=self.on_cash_cancel)
        keypad_layout.add_widget(cancel_button)

        self.cash_popup_layout.add_widget(keypad_layout)
        self.cash_popup = Popup(
            title="Enter Cash Amount",
            content=self.cash_popup_layout,
            size_hint=(0.8, 0.8),
        )
        self.cash_popup.open()

    def show_payment_confirmation_popup(self):
        confirmation_layout = GridLayout(orientation="lr-tb",cols=1, size_hint=(1,1), spacing=10)
        total_with_tax = self.order_manager.calculate_total_with_tax()
        order_summary = "Order Complete:\n\n"

        for item_id, item_details in self.order_manager.items.items():
            item_name = item_details['name']  # Extracting the actual item name
            quantity = item_details['quantity']
            total_price_for_item = item_details['total_price']

            print(f"Processing item ID: {item_id}, Item name: {item_name}, Details: {item_details}")

            try:
                total_price_float = float(total_price_for_item)
            except ValueError:
                print(f"Error: Total price for {item_name} ({item_id}) is not a valid number.")
                continue

            order_summary += f"{item_name} x{quantity}  ${total_price_float:.2f}\n"

        order_summary += f"Total with Tax: ${total_with_tax:.2f}"
        confirmation_layout.add_widget(Label(text=order_summary))

        done_button = MDRaisedButton(
            text="Done", size_hint=(0.2,0.2), on_press=self.on_done_button_press  #####################
        )
        confirmation_layout.add_widget(done_button)

        self.payment_popup = Popup(
            title="Payment Confirmation",
            content=confirmation_layout,
            size_hint=(0.8, 0.8),
        )
        self.popup.dismiss()
        self.payment_popup.open()


    def show_make_change_popup(self, change):
        change_layout = BoxLayout(orientation="vertical", spacing=10)
        change_layout.add_widget(Label(text=f"Change to return: ${change:.2f}"))

        done_button = MDRaisedButton(
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

        button_layout = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            size_hint_x=None,
            height=50,
            spacing=10,
        )

        cancel_button = MDRaisedButton(
            text="Cancel",
            size_hint_x=1,
            on_press=self.close_add_to_database_popup,
        )
        confirm_button = MDRaisedButton(
            text="Confirm",
            size_hint_x=1,
            on_press=lambda instance: (
                self.add_item_to_database(barcode, name_input.text, price_input.text),
                self.close_add_to_database_popup(instance),
            ),
        )

        button_layout.add_widget(cancel_button)
        button_layout.add_widget(confirm_button)

        popup_layout.add_widget(button_layout)

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

    def add_item_to_label_printing_queue(self):
        pass

    def add_adjusted_price_item(self, instance):
        target_amount = self.target_amount_input.text
        try:
            target_amount = float(target_amount)
        except ValueError:
            return

        tax_rate = 0.07
        adjusted_price = target_amount / (1 + tax_rate)

        self.order_manager.update_item_price(self.current_item_name, adjusted_price)
        self.update_display()
        self.update_financial_summary()
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
        print(f"Total with tax: {total_with_tax}")

        order_summary = "Order Summary:\n\n"
        for item_id, item_details in self.order_manager.items.items():
            item_name = item_details['name']  # Extracting the actual item name
            quantity = item_details['quantity']
            total_price_for_item = item_details['total_price']

            print(f"Processing item ID: {item_id}, Item name: {item_name}, Details: {item_details}")

            try:
                total_price_float = float(total_price_for_item)
            except ValueError:
                print(f"Error: Total price for {item_name} ({item_id}) is not a valid number.")
                continue

            order_summary += f"{item_name} x{quantity}  ${total_price_float:.2f}\n"

        order_summary += f"Total with Tax: ${total_with_tax:.2f}"
        print(f"Final Order Summary:\n{order_summary}")

        self.show_order_popup(order_summary)






    def update_display(self):
        print("called update display")
        self.order_layout.clear_widgets()
        for item_id, item_info in self.order_manager.items.items():
            item_name = item_info['name']
            item_quantity = item_info['quantity']
            item_total_price = item_info['total_price']

            if item_quantity > 1:
                item_display_text = f"{item_name} x{item_quantity} ${item_total_price:.2f}"
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

            for widget in self.order_layout.children:
                print(f"Widget size: {widget.size}, pos: {widget.pos}")


    def calculate_width(self):
        return 400

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
        self.order_manager.add_item(custom_item_name, price)
        self.update_display()
        self.update_financial_summary()
        self.custom_item_popup.dismiss()


    def on_custom_item_cancel(self, instance):
        self.custom_item_popup.dismiss()

    def send_order_to_history_database(self, order_details, order_manager, db_manager):
        tax = order_details["total_with_tax"] - order_details["total"]
        timestamp = datetime.datetime.now()

        items_for_db = [{**{'name': item_name}, **item_details} for item_name, item_details in order_details["items"].items()]

        db_manager.add_order_history(
            order_details["order_id"],
            json.dumps(items_for_db),
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

    def close_inventory_management_view(self):
        self.in_inventory_management_view = False
        self.inventory_manager_view = None

    def reboot(self, instance):
        subprocess.run(["reboot"])

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
                self.theme_cls.primary_palette = settings.get("primary_palette", "Brown")
                self.theme_cls.theme_style = settings.get("theme_style", "Light")
        except FileNotFoundError:
            pass

class FinancialSummaryWidget(MDRaisedButton):
    def __init__(self, **kwargs):
        super(FinancialSummaryWidget, self).__init__(**kwargs)
        self.size_hint_y = None
        self.size_hint_x = 1
        self.height = 80
        self.orientation = "vertical"
        self.font_style = "H6"

    def update_summary(self, subtotal, tax, total_with_tax):
        self.text = (
            f"Subtotal: ${subtotal:.2f}\nTax: ${tax:.2f}\nTotal: ${total_with_tax:.2f}"
        )

    def on_press(self):
        self.open_order_modification_popup()

    def open_order_modification_popup(self):
        popup = Popup(
            title="Modify Order",
            content=MDLabel(text="Modify your order here"),
            size_hint=(None, None),
            size=(400, 400),
        )
        popup.open()

class InventoryManagementView(BoxLayout):
    barcode = StringProperty()
    name = StringProperty()
    price = StringProperty()
    cost = StringProperty()
    sku = StringProperty()

    def __init__(self, **kwargs):
        super(InventoryManagementView, self).__init__(**kwargs)

        self.full_inventory = []
        self.database_manager = DatabaseManager("inventory.db")

    def generate_unique_barcode(self):
        while True:
            new_barcode = str(upc_a(str(random.randint(100000000000, 999999999999)), writer=None).get_fullcode())

            if not self.database_manager.barcode_exists(new_barcode):
                return new_barcode

    def show_add_item_popup(self, scanned_barcode):
        self.barcode = scanned_barcode
        self.inventory_item_popup()

    def show_inventory_for_manager(self, inventory_items):
        self.full_inventory = inventory_items
        self.rv.data = self.generate_data_for_rv(inventory_items)

    def refresh_inventory(self):
        print("refresh")
        updated_inventory = self.database_manager.get_all_items()
        self.show_inventory_for_manager(updated_inventory)

    def add_item_to_database(self, barcode_input, name_input, price_input, cost_input, sku_input):
        if barcode_input and name_input and price_input:
            try:
                self.database_manager.add_item(
                    barcode_input.text, name_input.text, price_input.text, cost_input.text, sku_input.text
                )
            except Exception as e:
                print(e)

    def inventory_item_popup(self):
        content = BoxLayout(orientation="vertical", padding=10)


        name_layout = BoxLayout(orientation='horizontal', size_hint_y=0.4)
        name_input = TextInput(text=self.name)
        name_layout.add_widget(Label(text="Name", size_hint_x=0.2))
        name_layout.add_widget(name_input)

        barcode_layout = BoxLayout(orientation='horizontal', size_hint_y=0.4)
        barcode_input = TextInput(input_filter="int", text=self.barcode if self.barcode else '')
        barcode_layout.add_widget(Label(text="Barcode", size_hint_x=0.2))
        barcode_layout.add_widget(barcode_input)

        price_layout = BoxLayout(orientation='horizontal', size_hint_y=0.4)
        price_input = TextInput(text=self.price, input_filter="float")
        price_layout.add_widget(Label(text="Price", size_hint_x=0.2))
        price_layout.add_widget(price_input)

        cost_layout = BoxLayout(orientation='horizontal', size_hint_y=0.4)
        cost_input = TextInput(text=self.cost, input_filter="float")
        cost_layout.add_widget(Label(text="Cost", size_hint_x=0.2))
        cost_layout.add_widget(cost_input)

        sku_layout = BoxLayout(orientation='horizontal', size_hint_y=0.4)
        sku_input = TextInput(text=self.sku)
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
                on_press=lambda *args: self.confirm_and_close(
                    barcode_input, name_input, price_input, cost_input, sku_input, popup
                ),
            )
        )

        button_layout.add_widget(
            MDRaisedButton(text="Cancel", on_press=lambda *args: popup.dismiss())
        )
        button_layout.add_widget(
            MDRaisedButton(
                text="Generate Barcode",
                on_press=lambda *args: self.set_generated_barcode(barcode_input)
            )
        )

        content.add_widget(button_layout)

        popup = Popup(title="Item details",pos_hint={"top": 1},  content=content, size_hint=(0.8, 0.4))
        popup.open()

    def confirm_and_close(self, barcode_input, name_input, price_input, cost_input, sku_input, popup):
        self.add_item_to_database(barcode_input, name_input, price_input, cost_input, sku_input)
        self.refresh_inventory()
        popup.dismiss()

    def set_generated_barcode(self, barcode_input):
        unique_barcode = self.generate_unique_barcode()
        barcode_input.text = unique_barcode


    def open_inventory_manager(self):
        self.inventory_item_popup()

    def generate_data_for_rv(self, items):
        return [
            {
                "barcode": str(item[0]),
                "name": item[1],
                "price": str(item[2]),
                "cost": str(item[3]),
                "sku": str(item[4]),
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

class InventoryManagementRow(BoxLayout):
    barcode = StringProperty()
    name = StringProperty()
    price = StringProperty()
    cost = StringProperty()
    sku = StringProperty()

    def __init__(self, **kwargs):
        super(InventoryManagementRow, self).__init__(**kwargs)
        self.database_manager = DatabaseManager("inventory.db")
        self.inventory_management_view = InventoryManagementView()

    def inventory_item_popup(self):
        content = BoxLayout(orientation="vertical", padding=10)


        name_layout = BoxLayout(orientation='horizontal', size_hint_y=0.4)
        name_input = TextInput(text=self.name)
        name_layout.add_widget(Label(text="Name", size_hint_x=0.2))
        name_layout.add_widget(name_input)

        barcode_layout = BoxLayout(orientation='horizontal', size_hint_y=0.4)
        barcode_input = TextInput(input_filter="int", text=self.barcode if self.barcode else '')
        barcode_layout.add_widget(Label(text="Barcode", size_hint_x=0.2))
        barcode_layout.add_widget(barcode_input)

        price_layout = BoxLayout(orientation='horizontal', size_hint_y=0.4)
        price_input = TextInput(input_filter="float", text=self.price)
        price_layout.add_widget(Label(text="Price", size_hint_x=0.2))
        price_layout.add_widget(price_input)

        cost_layout = BoxLayout(orientation='horizontal', size_hint_y=0.4)
        cost_input = TextInput(text=self.cost, input_filter="float")
        cost_layout.add_widget(Label(text="Cost", size_hint_x=0.2))
        cost_layout.add_widget(cost_input)

        sku_layout = BoxLayout(orientation='horizontal', size_hint_y=0.4)
        sku_input = TextInput(text=self.sku)
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
                text="Update Details",
                on_press=lambda *args: self.confirm_and_close(
                    barcode_input, name_input, price_input, cost_input, sku_input, popup
                ),
            )
        )

        button_layout.add_widget(
            MDRaisedButton(text="Close", on_press=lambda *args: popup.dismiss()))

        content.add_widget(button_layout)

        popup = Popup(title="Item details", pos_hint={"top": 1}, content=content, size_hint=(0.8, 0.4))
        popup.open()

    def confirm_and_close(self, barcode_input, name_input, price_input, cost_input, sku_input, popup):
        self.update_item_in_database(barcode_input, name_input, price_input, cost_input, sku_input)
        self.inventory_management_view.refresh_inventory()
        popup.dismiss()



    def open_inventory_manager(self):
        self.inventory_item_popup()

    def update_item_in_database(self, barcode_input, name_input, price_input, cost_input, sku_input):
        if barcode_input and name_input and price_input:

            try:
                self.database_manager.update_item(
                    barcode_input.text, name_input.text, price_input.text, cost_input.text, sku_input.text
                )
            except Exception as e:
                print(e)



class LabelPrintingRow(BoxLayout):
    barcode = StringProperty()
    name = StringProperty()
    price = StringProperty()
    label_printer = ObjectProperty()

    def add_to_print_queue(self):
        print(f"Adding {self.name} to print queue")
        self.show_label_popup()

    def show_label_popup(self):
        content = BoxLayout(orientation="vertical", padding=10)
        quantity_input = TextInput(text="1", input_filter="int")
        content.add_widget(Label(text=f"Enter quantity for {self.name}"))
        content.add_widget(quantity_input)
        content.add_widget(
            MDRaisedButton(
                text="Add",
                on_press=lambda *args: self.on_add_button_press(quantity_input, popup),
            )
        )
        popup = Popup(title="Label Quantity", content=content, size_hint=(0.8, 0.4))
        popup.open()

    def on_add_button_press(self, quantity_input, popup):
        self.add_quantity_to_queue(quantity_input.text)
        popup.dismiss()

    def add_quantity_to_queue(self, quantity):
        self.label_printer.add_to_queue(self.barcode, self.name, self.price, quantity)


class LabelPrintingView(BoxLayout):
    def __init__(self, **kwargs):
        super(LabelPrintingView, self).__init__(**kwargs)
        self.full_inventory = []
        self.label_printer = LabelPrinter()

    def show_inventory_for_label_printing(self, inventory_items):
        self.full_inventory = inventory_items
        self.rv.data = self.generate_data_for_rv(inventory_items)

    def show_print_queue(self):
        content = BoxLayout(orientation="vertical", spacing=10)
        for item in self.label_printer.print_queue:
            content.add_widget(Label(text=f"{item['name']} x {item['quantity']}"))

        content.add_widget(MDRaisedButton(text="Print Now", on_press=self.print_now))
        content.add_widget(MDRaisedButton(text="Cancel", on_press=self.cancel_print))

        self.print_queue_popup = Popup(
            title="Print Queue", content=content, size_hint=(0.8, 0.6)
        )
        self.print_queue_popup.open()

    def print_now(self, instance):
        print("we are inside print now")
        self.label_printer.process_queue()
        self.print_queue_popup.dismiss()

    def cancel_print(self, instance):
        self.print_queue_popup.dismiss()

    def generate_data_for_rv(self, items):
        return [
            {
                "barcode": str(item[0]),
                "name": item[1],
                "price": str(item[2]),
                "label_printer": self.label_printer,
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
        try:
            price_float = float(self.price)
        except ValueError as e:
            print(e)
            pass
        self.order_manager.add_item(self.name, price_float)
        app = App.get_running_app()
        app.update_display()
        app.update_financial_summary()


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


app = CashRegisterApp()
app.run()
# if __name__ == "__main__":
#     app = CashRegisterApp()
#     app.run()
#     #app.show_lock_screen()
