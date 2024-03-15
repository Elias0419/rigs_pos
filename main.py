# import logging
# from logger_conf import setup_logging
# setup_logging()
# logger = logging.getLogger(__name__)
# logger.info("Application starting..")

import eel
import sys
import os
from kivy.config import Config

#Config.set('kivy', 'keyboard_mode', 'systemanddock')
Config.set('kivy', 'keyboard_scale', '0.75')
#Config.set('postproc', 'double_tap_time', '500')
Config.set('input', 'isolution multitouch', 'hidinput,/dev/input/event12')
#Config.set('graphics', 'show_cursor', '0')
# Config.set('kivy', 'log_level', 'error')
Config.set("graphics", "multisamples", "8")
Config.set('graphics', 'kivy_clock', 'interrupt')
from kivymd.toast import toast
from kivymd.uix.snackbar import Snackbar
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.modules import monitor, inspector
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.image import Image
from kivy.uix.popup import Popup

from kivymd.app import MDApp
from kivymd.uix.boxlayout import BoxLayout
from kivymd.uix.button import MDIconButton, MDFlatButton
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
from util import Utilities, ReusableTimer#, CustomTextInput
from wrapper import Wrapper
from distributor_manager import DistPopup, DistView

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
        self.click = 0
        self.current_context = "main"
        self.theme_cls.theme_style = "Dark"
        self.theme_cls.primary_palette = "Brown"
        self.selected_categories = []

    def on_start(self):
        self.utilities.load_settings()

    def build(self):
        self.utilities = Utilities(self)
        self.utilities.initialize_receipt_printer()
        self.barcode_scanner = BarcodeScanner(self)
        self.db_manager = DatabaseManager("inventory.db", self)
        self.financial_summary = FinancialSummaryWidget(self)
        self.order_manager = OrderManager(self)
        self.history_manager = HistoryView(self)
        self.order_history_popup = OrderManager(self)
        self.history_popup = HistoryPopup()

        self.inventory_manager = InventoryManagementView()
        self.inventory_row = InventoryManagementRow()
        self.label_printer = LabelPrinter(self)
        self.label_manager = LabelPrintingView(self)

        self.pin_reset_timer = ReusableTimer(5.0, self.utilities.reset_pin)
        self.calculator = Calculator()
        self.dist_manager = DistView(self)
        self.dist_popup = DistPopup()
        self.button_handler = ButtonHandler(self)
        self.popup_manager = PopupManager(self)

        self.wrapper = Wrapper(self)
        self.categories = self.utilities.initialize_categories()
        self.barcode_cache = self.utilities.initialize_barcode_cache()
        self.inventory_cache = self.utilities.initialize_inventory_cache()
        self.dual_pane_mode = False
        self.check_dual_pane_mode()
        if self.dual_pane_mode:
            layout = self.main_init(dual_pane_mode=True)
        else:
            layout = self.main_init()
        return layout

    def enable_dual_pane_mode(self):
        flag_file_path = "dual_pane_mode.flag"
        with open(flag_file_path, 'w') as f:
            f.write("Activate dual pane mode")
        sys.exit(42)

    def check_dual_pane_mode(self):
        flag_file_path = "dual_pane_mode.flag"
        if os.path.exists(flag_file_path):
            self.dual_pane_mode = True
            os.remove(flag_file_path)

    def dual_pane(self):
        layout=GridLayout(orientation="lr-tb", cols=2)
        left = self.main_init()
        right = self.test_pane()
        layout.add_widget(left)
        layout.add_widget(right)
        popup = Popup(content=layout, size_hint=(1,1))
        popup.open()

    def test_pane(self):
        layout=MDBoxLayout(orientation="vertical")
        for i in range(20):
            label = MDLabel(text=f"{i}layout=GridLayout(orientation='lr-tb'', cols=2)")
            layout.add_widget(label)
        return layout


    def main_init(self, dual_pane_mode=False):

            if dual_pane_mode:
                dual_pane_layout = GridLayout(orientation="lr-tb", cols=2)
            main_layout = GridLayout(
                cols=1, spacing=5, orientation="lr-tb", row_default_height=60
            )

            top_area_layout = GridLayout(
                cols=4, rows=1, orientation="lr-tb", row_default_height=60, size_hint_x=0.95
            )
            right_area_layout = GridLayout(rows=2, orientation="tb-lr", padding=50)
            self.order_layout = GridLayout(
                orientation="tb-lr",
                cols=2,
                rows=10,
                spacing=5,
                row_default_height=60,
                row_force_default=True,
                size_hint_x=1 / 2,
            )
            clock_layout = self.create_clock_layout()
            top_area_layout.add_widget(clock_layout)

            center_container = GridLayout(rows=2, orientation="tb-lr", size_hint_y=0.01, size_hint_x=0.4)
            trash_icon_container = MDBoxLayout(size_hint_y=0.1)
            _blank = BoxLayout(size_hint_y=0.9)
            self.trash_icon = MDIconButton(icon="trash-can",pos_hint={"top":0.95, "right": 0}, on_press=lambda x: self.confirm_clear_order())
            trash_icon_container.add_widget(self.trash_icon)
            #center_container.add_widget(trash_icon_container)
            center_container.add_widget(_blank)
            top_area_layout.add_widget(center_container)

            right_area_layout.add_widget(self.order_layout)

            financial_button = self.create_financial_layout()
            financial_layout = BoxLayout(size_hint_y=0.2)
            financial_layout.add_widget(financial_button)
            right_area_layout.add_widget(financial_layout)
            top_area_layout.add_widget(right_area_layout)
            sidebar = BoxLayout(orientation="vertical", size_hint_x=0.05)
            lock_icon = MDIconButton(icon="lock")
            sidebar.add_widget(trash_icon_container)
            sidebar.add_widget(lock_icon)
            #sidebar.add_widget(trash_icon)
            top_area_layout.add_widget(sidebar)
            main_layout.add_widget(top_area_layout)
            # main_layout.add_widget(sidebar)
            button_layout = GridLayout(
                cols=4, spacing=10, padding=10, size_hint_y=0.05, size_hint_x=1, orientation="lr-tb"
            )

            btn_pay = self.utilities.create_md_raised_button(
                f"[b][size=40]Pay[/b][/size]",
                self.button_handler.on_button_press,
                (8, 8),
                "H6",
            )

            btn_custom_item = self.utilities.create_md_raised_button(
                f"[b][size=40]Custom[/b][/size]",

                self.button_handler.on_button_press,
                (8, 8),
                "H6",
            )
            btn_inventory = self.utilities.create_md_raised_button(
                f"[b][size=40]Search[/b][/size]",

                self.button_handler.on_button_press,
                (8, 8),
                "H6",
            )
            btn_tools = self.utilities.create_md_raised_button(
                f"[b][size=40]Tools[/b][/size]",


                #lambda x: self.enable_dual_pane_mode(),
                self.button_handler.on_button_press,
                # lambda x: self.popup_manager.show_add_or_bypass_popup("132414144141"),
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
            Clock.schedule_interval(self.barcode_scanner.check_for_scanned_barcode, 0.1)

            base_layout = FloatLayout()
            try:
                bg_image = Image(source="images/grey_mountains.jpg", fit_mode="fill")
                base_layout.add_widget(bg_image)

            except Exception as e:
                print(e)
                with base_layout.canvas.before:
                    Color(0.78, 0.78, 0.78, 1)
                    self.rect = Rectangle(size=base_layout.size, pos=base_layout.pos)

                def update_rect(instance, value):
                    instance.rect.size = instance.size
                    instance.rect.pos = instance.pos

                base_layout.bind(size=update_rect, pos=update_rect)

            base_layout.add_widget(main_layout)
            if dual_pane_mode:
                blank_layout = self.popup_manager.show_lock_screen(dual_pane=True)
                dual_pane_layout.add_widget(base_layout)
                dual_pane_layout.add_widget(blank_layout)
                return dual_pane_layout
            else:
                return base_layout

    def create_clock_layout(self):
        clock_layout = GridLayout(
            orientation="tb-lr",
            rows=4,
            size_hint_x=0.75,
            size_hint_y=1,
            padding=(60, 0, 0, 0),
        )
        top_container = BoxLayout(orientation="vertical", size_hint_y=0.1, padding=10)
        _nothing = BoxLayout(size_hint_y=1)
        logo_container = BoxLayout(size_hint_y=0.2, padding=(-200, 0, 0, 0))
        logo = Image(source="images/rigs_logo_scaled.png")
        logo_container.add_widget(logo)
        register_text = MDLabel(
            text="Cash Register",
            size_hint_y=None,
            font_style="H6",
            height=50,
            # valign="bottom",
            # halign="center",
        )
        blank_space = MDLabel(
            text="", size_hint_y=1, height=450, valign="top", halign="center"
        )
        clock_container = BoxLayout(size_hint_y=0.15)
        self.clock_label = MDLabel(
            text="Loading...",
            size_hint_y=None,
            # font_style="H6",
            height=150,
            size_hint_x=1,
            color=self.utilities.get_text_color(),
            markup=True,
            valign="bottom",
            # halign="center",
        )
        clock_container.add_widget(self.clock_label)
        line_container = MDBoxLayout(
            orientation="horizontal",
            height=1,
            size_hint_y=None,
        )
        blue_line = MDBoxLayout(size_hint_x=0.4)
        blue_line.md_bg_color = (0.56, 0.56, 1, 1)
        blank_line = MDBoxLayout(size_hint_x=0.2)
        blank_line.md_bg_color = (0, 0, 0, 0)
        blank_line2 = MDBoxLayout(size_hint_x=0.2)
        blank_line2.md_bg_color = (0, 0, 0, 0)
        line_container.add_widget(blue_line)
        line_container.add_widget(blank_line)

        line_container.add_widget(blank_line2)
        padlock_button = MDIconButton(
            icon="lock",
            # pos_hint={"right": 1},
            on_press=lambda x: self.utilities.trigger_guard_and_lock(trigger=True),
        )
        top_container.add_widget(register_text)
        top_container.add_widget(line_container)
        clock_layout.add_widget(top_container)
        clock_layout.add_widget(_nothing)
        clock_layout.add_widget(logo_container)

        Clock.schedule_interval(self.utilities.update_clock, 1)
        clock_layout.add_widget(clock_container)
        return clock_layout

    def create_financial_layout(self):
        financial_layout = GridLayout(cols=1, size_hint_x=1 / 3)

        self.financial_summary_widget = FinancialSummaryWidget(self)
        financial_layout.add_widget(self.financial_summary_widget)

        return financial_layout
    def clear_order_widget(self):
        if self.click == 0:
            self.click += 1
            self.clear_order.text = "Tap to Clear Order"
        elif self.click == 1:
            self.order_manager.clear_order()
            self.utilities.update_display()
            self.utilities.update_financial_summary()
            self.clear_order.text = f"[size=30]X[/size]"
            self.click = 0
        Clock.unschedule(self.reset)
        Clock.schedule_interval(self.reset, 3)

    def reset(self, dt):
        self.clear_order.text = f"[size=30]X[/size]"
        self.click = 0


    def confirm_clear_order(self):
        if self.click == 0:
            self.click += 1

            toast('Tap again to clear order')

            self.trash_icon.icon = "trash-can"
            self.trash_icon.icon_color = "red"
            Clock.unschedule(self.reset_confirmation)
            Clock.schedule_once(self.reset_confirmation, 3)
        else:
            self.perform_clear_order()

    def perform_clear_order(self):
        self.order_manager.clear_order()
        self.utilities.update_display()
        self.utilities.update_financial_summary()

        self.trash_icon.icon = "trash-can-outline"
        self.click = 0

    def reset_confirmation(self, dt):

        self.trash_icon.icon = "trash-can-outline"
        self.click = 0

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
