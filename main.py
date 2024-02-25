# import logging
# from logger_conf import setup_logging
# setup_logging()
# logger = logging.getLogger(__name__)
# logger.info("Application starting..")

import eel
import sys

from kivy.config import Config

Config.set("kivy", "keyboard_mode", "systemanddock")
Config.set('kivy', 'keyboard_scale', '0.5')

#Config.set('graphics', 'show_cursor', '0')
# Config.set('kivy', 'log_level', 'error')
Config.set("graphics", "multisamples", "4")
Config.set('graphics', 'kivy_clock', 'interrupt')

from kivy.clock import Clock
from kivy.core.window import Window
from kivy.modules import monitor, inspector
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.image import Image

from kivymd.app import MDApp
from kivymd.uix.boxlayout import BoxLayout
from kivymd.uix.button import MDIconButton
from kivymd.uix.gridlayout import GridLayout
from kivymd.uix.label import MDLabel
from kivymd.uix.boxlayout import MDBoxLayout

from _barcode_test import BarcodeScanner

# from barcode_scanner import BarcodeScanner
from button_handlers import ButtonHandler
from database_manager import DatabaseManager
from history_manager import HistoryView, HistoryPopup, OrderDetailsPopup
from inventory_manager import InventoryManagementView, InventoryManagementRow
from label_printer import LabelPrintingView, LabelPrinter
from order_manager import OrderManager
from popups import PopupManager, FinancialSummaryWidget, Calculator
from receipt_printer import ReceiptPrinter
from util import Utilities, ReusableTimer
from wrapper import Wrapper


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

        self.current_context = "main"
        self.theme_cls.theme_style = "Dark"
        self.theme_cls.primary_palette = "Brown"
        self.selected_categories = []

    def on_start(self):
        self.utilities.load_settings()

    def build(self):
        self.barcode_scanner = BarcodeScanner(self)
        self.db_manager = DatabaseManager("inventory.db", self)
        self.financial_summary = FinancialSummaryWidget(self)
        self.order_manager = OrderManager(self)
        self.history_manager = HistoryView(self)
        self.order_history_popup = OrderManager(self)
        self.history_popup = HistoryPopup()
        self.receipt_printer = ReceiptPrinter(
            self,
            "receipt_printer_config.yaml"
            )
        self.inventory_manager = InventoryManagementView()
        self.inventory_row = InventoryManagementRow()
        self.label_printer = LabelPrinter(self)
        self.label_manager = LabelPrintingView(self)
        self.utilities = Utilities(self)
        self.pin_reset_timer = ReusableTimer(5.0, self.utilities.reset_pin)
        self.calculator = Calculator()
        self.button_handler = ButtonHandler(self)
        self.popup_manager = PopupManager(self)

        self.wrapper = Wrapper(self)
        self.categories = self.utilities.initialize_categories()
        self.barcode_cache = self.utilities.initialize_barcode_cache()

        main_layout = GridLayout(
            cols=1, spacing=5, orientation="tb-lr", row_default_height=60
        )
        top_area_layout = GridLayout(
            cols=3,
            orientation="lr-tb",
            row_default_height=60
            )
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
            cols=4,
            spacing=5,
            size_hint_y=0.05,
            size_hint_x=1,
            orientation="lr-tb"
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
            #lambda x: self.popup_manager.open_category_button_popup(),
            self.button_handler.on_button_press,
            #lambda x: self.popup_manager.show_add_or_bypass_popup("132414144141"),
            # lambda x: sys.exit(42),
            (8, 8),
            "H6",
        )
        button_layout.add_widget(btn_pay)
        button_layout.add_widget(btn_custom_item)
        button_layout.add_widget(btn_inventory)
        button_layout.add_widget(btn_tools)
        main_layout.add_widget(button_layout)

        Clock.schedule_interval(self.utilities.check_inactivity, 10)
        Clock.schedule_interval(
            self.barcode_scanner.check_for_scanned_barcode,
            0.1
            )

        base_layout = FloatLayout()

        try:
            if self.theme_cls.theme_style == "Light":
                bg_image = Image(
                    source="images/gradient_wallpaper.png",
                    allow_stretch=True,
                    keep_ratio=False,
                )
                base_layout.add_widget(bg_image)
            else:
                bg_image = Image(
                    source="images/grey_mountains.jpg",
                    allow_stretch=True,
                    keep_ratio=False,
                )
                base_layout.add_widget(bg_image)

        except Exception as e:
            print(e)
            with base_layout.canvas.before:
                Color(0.78, 0.78, 0.78, 1)
                self.rect = Rectangle(
                    size=base_layout.size,
                    pos=base_layout.pos
                    )

            def update_rect(instance, value):
                instance.rect.size = instance.size
                instance.rect.pos = instance.pos

            base_layout.bind(size=update_rect, pos=update_rect)

        base_layout.add_widget(main_layout)
        return base_layout

    def create_clock_layout(self):
        clock_layout = BoxLayout(orientation="vertical", size_hint_x=1 / 3)
        register_text = MDLabel(
            text="Cash Register",
            size_hint_y=None,
            # font_style="H8",
            height=50,
            valign="bottom",
            halign="center",
        )
        blank_space = MDLabel(
            text="", size_hint_y=1, height=450, valign="top", halign="center"
        )

        self.clock_label = MDLabel(
            text="Loading...",
            size_hint_y=None,
            font_style="H6",
            height=80,
            color=self.utilities.get_text_color(),
            halign="center",
        )
        line_container = MDBoxLayout(
            orientation="horizontal", size_hint_y=None, height=1
        )
        blue_line = MDBoxLayout(size_hint_x=0.2)
        blue_line.md_bg_color = (0.56, 0.56, 1, 1)
        blank_line = MDBoxLayout(size_hint_x=0.2)
        blank_line.md_bg_color = (0, 0, 0, 0)
        blank_line2 = MDBoxLayout(size_hint_x=0.2)
        blank_line2.md_bg_color = (0, 0, 0, 0)
        line_container.add_widget(blank_line)
        line_container.add_widget(blue_line)
        line_container.add_widget(blank_line2)
        padlock_button = MDIconButton(
            icon="lock",
            pos_hint={"right": 1},
            on_press=lambda x: self.utilities.trigger_guard_and_lock(
                trigger=True),
        )
        clock_layout.add_widget(register_text)
        clock_layout.add_widget(line_container)
        clock_layout.add_widget(blank_space)
        clock_layout.add_widget(padlock_button)

        Clock.schedule_interval(self.utilities.update_clock, 1)
        clock_layout.add_widget(self.clock_label)
        return clock_layout

    def create_financial_layout(self):
        financial_layout = GridLayout(cols=1, size_hint_x=1 / 3)

        self.financial_summary_widget = FinancialSummaryWidget(self)
        financial_layout.add_widget(self.financial_summary_widget)

        return financial_layout

    def reboot(self):
        print("reboot")
        sys.exit(43)
        # try:
        #     subprocess.run(["systemctl", "reboot"])
        # except Exception as e:
        #     print(e)

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
