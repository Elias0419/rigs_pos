from datetime import datetime
import json

from kivy.modules import monitor
from kivy.config import Config

Config.set("kivy", "keyboard_mode", "systemanddock")

import eel
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.modules import inspector
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.image import Image

from kivymd.app import MDApp
from kivymd.uix.boxlayout import BoxLayout
from kivymd.uix.button import MDIconButton
from kivymd.uix.gridlayout import GridLayout
from kivymd.uix.label import MDLabel

from barcode_scanner import BarcodeScanner
from database_manager import DatabaseManager
from label_printer import LabelPrintingView, LabelPrinter
from open_cash_drawer import open_cash_drawer
from order_manager import OrderManager
from history_manager import HistoryView, HistoryPopup
from receipt_printer import ReceiptPrinter
from inventory_manager import InventoryManagementView
from popups import PopupManager, FinancialSummaryWidget
from button_handlers import ButtonHandler
from util import Utilities
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
        self.selected_categories = []


    def build(self):
        self.barcode_scanner = BarcodeScanner()
        self.db_manager = DatabaseManager("inventory.db", self)
        self.financial_summary = FinancialSummaryWidget(self)
        self.order_manager = OrderManager(self)
        self.history_manager = HistoryView(self)
        self.history_popup = HistoryPopup()
        self.receipt_printer = ReceiptPrinter(self, "receipt_printer_config.yaml")
        self.inventory_manager = InventoryManagementView()
        self.label_printer = LabelPrinter(self)
        self.label_manager = LabelPrintingView(self)
        self.popup_manager = PopupManager(self)
        self.button_handler = ButtonHandler(self)
        self.utilities = Utilities(self)
        self.categories = self.utilities.initialze_categories()
        self.utilities.load_settings()

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

        btn_pay = self.utilities.create_md_raised_button(
            "Pay",
            self.button_handler.on_button_press,
            (8, 8),
            "H6",
        )

        btn_custom_item = self.utilities.create_md_raised_button(
            "Custom",
            self.button_handler.on_button_press,
            (8, 8),
            "H6",
        )
        btn_inventory = self.utilities.create_md_raised_button(
            "Search",
            self.button_handler.on_button_press,
            (8, 8),
            "H6",
        )
        btn_tools = self.utilities.create_md_raised_button(
            "Tools",
            #self.popup_manager.show_lock_screen,
            self.button_handler.on_button_press,
            (8, 8),
            "H6",
        )
        button_layout.add_widget(btn_pay)
        button_layout.add_widget(btn_custom_item)
        button_layout.add_widget(btn_inventory)
        button_layout.add_widget(btn_tools)
        main_layout.add_widget(button_layout)

        Clock.schedule_interval(self.utilities.check_inactivity, 10)
        Clock.schedule_interval(self.check_for_scanned_barcode, 0.1)

        # if not hasattr(self, "monitor_check_scheduled"):
        #     Clock.schedule_interval(self.utilities.check_monitor_status, 5)
        #     self.monitor_check_scheduled = True

        base_layout = FloatLayout()

        try:
            if self.theme_cls.theme_style == "Light":
                bg_image = Image(source='images/gradient_wallpaper.png', allow_stretch=True, keep_ratio=False)
                base_layout.add_widget(bg_image)
            else:
                bg_image = Image(source='images/grey_mountains.jpg', allow_stretch=True, keep_ratio=False)
                base_layout.add_widget(bg_image)

        except Exception as e:

            with base_layout.canvas.before:
                Color(0.78, 0.78, 0.78, 1)
                self.rect = Rectangle(size=base_layout.size, pos=base_layout.pos)

            def update_rect(instance, value):
                instance.rect.size = instance.size
                instance.rect.pos = instance.pos

            base_layout.bind(size=update_rect, pos=update_rect)

        base_layout.add_widget(main_layout)
        return base_layout

    def create_clock_layout(self):
        clock_layout = BoxLayout(orientation="vertical", size_hint_x=1 / 3)
        self.clock_label = MDLabel(
            text="Loading...",
            size_hint_y=None,
            font_style="H6",
            height=80,
            color=self.utilities.get_text_color(),
            halign="center",
        )
        padlock_button = MDIconButton(
            icon="lock",
            pos_hint={"right": 1},
            on_press=lambda x: self.utilities.trigger_guard_and_lock(),
            # on_press=lambda x: self.utilities.turn_off_monitor(),
        )
        clock_layout.add_widget(padlock_button)

        Clock.schedule_interval(self.utilities.update_clock, 1)
        clock_layout.add_widget(self.clock_label)
        return clock_layout

    def create_financial_layout(self):
        financial_layout = GridLayout(cols=1, size_hint_x=1 / 3)

        self.financial_summary_widget = FinancialSummaryWidget(self)
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
        # elif self.current_context == "history":
        #     self.history_manager.handle_scanned_barcode(barcode)
        else:
            self.handle_scanned_barcode(barcode)

    def handle_scanned_barcode(self, barcode):
        try:
            if '-' in barcode and any(c.isalpha() for c in barcode):
                self.history_manager.display_order_details_from_barcode_scan(barcode)
            else:
                item_details = self.db_manager.get_item_details(barcode)

                if item_details:
                    item_name, item_price = item_details
                    self.order_manager.add_item(item_name, item_price)
                    self.utilities.update_display()
                    self.utilities.update_financial_summary()
                    return item_details
                else:
                    self.popup_manager.show_add_or_bypass_popup(barcode)

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




try:
    app = CashRegisterApp()
    app.run()
except KeyboardInterrupt:
    print("test")
# if __name__ == "__main__":
#     app = CashRegisterApp()
#     app.run()
#     #app.show_lock_screen()
