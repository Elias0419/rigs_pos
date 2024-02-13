# import logging
#
# logger = logging.getLogger(__name__)


from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.popup import Popup
from kivy.uix.gridlayout import GridLayout
from kivy.uix.boxlayout import BoxLayout
from kivymd.uix.button import MDRaisedButton, MDFlatButton
from kivy.uix.textinput import TextInput
from kivymd.color_definitions import palette
from kivy.uix.floatlayout import FloatLayout
from label_printer import LabelPrintingView
from inventory_manager import InventoryManagementView, InventoryView
from open_cash_drawer import open_cash_drawer
from kivy.clock import Clock
from kivymd.uix.label import MDLabel
from kivy.uix.image import Image
import os
from functools import partial

class PopupManager:
    def __init__(self, ref):
        self.app = ref

    def create_category_popup(self):
        category_button_layout = GridLayout(
            size_hint=(1, 0.8), pos_hint={"top": 1}, cols=7, spacing=5
        )
        for category in self.app.categories:
            btn = MDRaisedButton(
                text=category,
                on_release=lambda instance, cat=category: self.app.utilities.toggle_category_selection(
                    instance, cat
                ),
                size_hint=(1, 0.8),
            )
            category_button_layout.add_widget(btn)

        category_popup_layout = BoxLayout()
        confirm_button = MDRaisedButton(
            text="Confirm", on_release=lambda instance: self.app.utilities.apply_categories()
        )
        cancel_button = MDRaisedButton(
            text="Cancel",
            on_release=lambda instance: category_popup.dismiss(),
        )
        category_popup_layout.add_widget(category_button_layout)
        category_popup_layout.add_widget(confirm_button)
        category_popup_layout.add_widget(cancel_button)

        category_popup = Popup(content=category_popup_layout, size_hint=(0.9, 0.9))
        return category_popup

    def open_category_button_popup(self):
        self.category_button_popup = self.create_category_popup()
        self.category_button_popup.open()

    def show_add_or_bypass_popup(self, barcode):
        popup_layout = BoxLayout(orientation="vertical", spacing=5)
        popup_layout.add_widget(Label(text=f"Barcode: {barcode}"))
        button_layout = BoxLayout(orientation="horizontal", spacing=5)

        def on_button_press(instance, option):
            self.app.utilities.on_add_or_bypass_choice(option, barcode)
            self.add_or_bypass_popup.dismiss()

        for option in ["Add Custom Item", "Add to Database"]:
            btn = MDRaisedButton(
                text=option,
                on_release=lambda instance, opt=option: on_button_press(instance, opt),
                size_hint=(0.5, 0.4),
            )
            button_layout.add_widget(btn)

        popup_layout.add_widget(button_layout)

        self.add_or_bypass_popup = Popup(
            title="Item Not Found", content=popup_layout, size_hint=(0.6, 0.4)
        )
        self.add_or_bypass_popup.open()

    def show_item_details_popup(self, item_id):
        item_info = self.app.order_manager.items.get(item_id)
        if item_info:
            item_name = item_info["name"]
            item_quantity = item_info["quantity"]
            item_price = item_info["total_price"]

        item_popup_layout = GridLayout(rows=3, size_hint=(0.8, 0.8))
        details_layout = BoxLayout(orientation="vertical")
        try:
            details_layout.add_widget(
                Label(text=f"Name: {item_name}\nPrice: ${item_price}")
            )
        except Exception as e:
            print("Error in popups.py show_item_details_popup", e)
        item_popup_layout.add_widget(details_layout)

        quantity_layout = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height="48dp",
        )
        quantity_layout.add_widget(
            self.app.utilities.create_md_raised_button(
                "-",
                lambda x: self.app.order_manager.adjust_item_quantity_in(item_id, -1),
            )
        )
        quantity_layout.add_widget(Label(text=str(item_quantity)))
        quantity_layout.add_widget(
            self.app.utilities.create_md_raised_button(
                "+",
                lambda x: self.app.order_manager.adjust_item_quantity_in(item_id, 1),
            )
        )
        item_popup_layout.add_widget(quantity_layout)

        buttons_layout = BoxLayout(
            orientation="horizontal", spacing=5, size_hint_y=None, size_hint_x=1
        )
        buttons_layout.add_widget(
            self.app.utilities.create_md_raised_button(
                "Add Discount",
                lambda x: self.add_discount_popup(item_name, item_price),
                (1, 0.4),
            )
        )

        buttons_layout.add_widget(
            self.app.utilities.create_md_raised_button(
                "Remove Item",
                lambda x: self.app.order_manager.remove_item_in(item_name, item_price),
                (1, 0.4),
            )
        )
        buttons_layout.add_widget(
            Button(
                text="Cancel",
                size_hint=(1, 0.4),
                on_press=lambda x: self.close_item_popup(),
            )
        )
        item_popup_layout.add_widget(buttons_layout)

        self.item_popup = Popup(
            title="Item Details", content=item_popup_layout, size_hint=(0.4, 0.4)
        )
        self.item_popup.open()

    def close_item_popup(self):
        if self.item_popup:
            self.item_popup.dismiss()

    def add_discount_popup(self, item_name, item_price):
        discount_popup_layout = BoxLayout(orientation="vertical", spacing=10)
        self.discount_popup = Popup(
            title="Add Discount",
            content=discount_popup_layout,
            size_hint=(0.8, 0.8),
        )
        self.discount_amount_input = TextInput(
            text="",
            disabled=True,
            multiline=False,
            input_filter="float",
            font_size=30,
            size_hint_y=None,
            height=50,
        )
        discount_popup_layout.add_widget(self.discount_amount_input)

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
            "",
            "0",
            "",
        ]
        for button in numeric_buttons:

            if button == "":
                blank_space = Label(size_hint=(0.8, 0.8))
                keypad_layout.add_widget(blank_space)
            else:
                btn = Button(
                    text=button,
                    on_press=self.app.button_handler.on_add_discount_numeric_button_press,
                    size_hint=(0.8, 0.8),
                )
                keypad_layout.add_widget(btn)

        amount_button = self.app.utilities.create_md_raised_button(
            "Amount",
            lambda x: self.app.order_manager.discount_single_item(
                discount_amount=self.discount_amount_input.text,
            ),
            (0.8, 0.8),
        )
        percent_button = self.app.utilities.create_md_raised_button(
            "Percent",
            lambda x: self.app.order_manager.discount_single_item(
                discount_amount=self.discount_amount_input.text, percent=True
            ),
            (0.8, 0.8),
        )

        cancel_button = Button(
            text="Cancel",
            on_press=lambda x: self.discount_popup.dismiss(),
            size_hint=(0.8, 0.8),
        )

        keypad_layout.add_widget(amount_button)
        keypad_layout.add_widget(percent_button)
        keypad_layout.add_widget(cancel_button)
        discount_popup_layout.add_widget(keypad_layout)

        self.discount_popup.open()

    def add_order_discount_popup(self):
        discount_order_popup_layout = BoxLayout(orientation="vertical", spacing=10)
        self.discount_order_popup = Popup(
            title="Add Discount",
            content=discount_order_popup_layout,
            size_hint=(0.8, 0.8),
        )
        self.discount_order_amount_input = TextInput(
            text="",
            disabled=True,
            multiline=False,
            input_filter="float",
            font_size=30,
            size_hint_y=None,
            height=50,
        )
        discount_order_popup_layout.add_widget(self.discount_order_amount_input)

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
            "",
            "0",
            "",
        ]
        for button in numeric_buttons:

            if button == "":
                blank_space = Label(size_hint=(0.8, 0.8))
                keypad_layout.add_widget(blank_space)
            else:
                btn = Button(
                    text=button,
                    on_press=self.app.button_handler.on_add_order_discount_numeric_button_press,
                    size_hint=(0.8, 0.8),
                )
                keypad_layout.add_widget(btn)

        amount_button = self.app.utilities.create_md_raised_button(
            "Amount",
            lambda x: self.app.order_manager.discount_entire_order(discount_amount=self.discount_order_amount_input.text),
            size_hint=(0.8, 0.8),
        )
        percent_button = self.app.utilities.create_md_raised_button(
            "Percent",
            lambda x: self.app.order_manager.discount_entire_order(discount_amount=self.discount_order_amount_input.text, percent=True),
            size_hint=(0.8, 0.8),
        )

        cancel_button = Button(
            text="Cancel",
            on_press=lambda x: self.discount_order_popup.dismiss(),
            size_hint=(0.8, 0.8),
        )

        keypad_layout.add_widget(amount_button)
        keypad_layout.add_widget(percent_button)
        keypad_layout.add_widget(cancel_button)
        discount_order_popup_layout.add_widget(keypad_layout)

        self.discount_order_popup.open()

    def show_theme_change_popup(self):
        layout = GridLayout(cols=4, rows=8, orientation="lr-tb")

        button_layout = GridLayout(
            cols=4, rows=8, orientation="lr-tb", spacing=5, size_hint=(1, 0.4)
        )
        button_layout.bind(minimum_height=button_layout.setter("height"))

        for color in palette:
            button = self.app.utilities.create_md_raised_button(
                color,
                lambda x, col=color: self.app.utilities.set_primary_palette(col),
                (0.8, 0.8),
            )

            button_layout.add_widget(button)

        dark_btn = MDRaisedButton(
            text="Dark Mode",
            size_hint=(0.8, 0.8),
            md_bg_color=(0, 0, 0, 1),
            on_release=lambda x, col=color: self.app.utilities.toggle_dark_mode(),
        )
        button_layout.add_widget(dark_btn)
        layout.add_widget(button_layout)

        self.theme_change_popup = Popup(
            title="",
            content=layout,
            size_hint=(0.6, 0.6),
            background="images/transparent.png",
            background_color=(0, 0, 0, 0),
            separator_height=0,
        )
        self.theme_change_popup.open()

    def show_system_popup(self):
        float_layout = FloatLayout()

        system_buttons = ["Change Theme", "Reboot System", "Restart App", "TEST"]

        for index, tool in enumerate(system_buttons):
            btn = MDRaisedButton(
                text=tool,
                size_hint=(1, 0.15),
                pos_hint={"center_x": 0.5, "center_y": 1 - 0.2 * index},
                on_press=self.app.button_handler.on_system_button_press,
            )
            float_layout.add_widget(btn)

        self.system_popup = Popup(
            content=float_layout,
            size_hint=(0.2, 0.6),
            title="",
            background="images/transparent.png",
            background_color=(0, 0, 0, 0),
            separator_height=0,
        )
        self.system_popup.open()

    def show_label_printing_view(self):
        inventory = self.app.db_manager.get_all_items()
        label_printing_view = self.app.label_manager
        self.app.current_context = "label"

        label_printing_view.show_inventory_for_label_printing(inventory)
        label_printing_popup = Popup(
            title="Label Printing", content=label_printing_view, size_hint=(0.9, 0.9)
        )
        label_printing_popup.bind(on_dismiss=self.app.utilities.reset_to_main_context)
        label_printing_popup.open()

    def show_inventory_management_view(self):

        self.inventory_management_view = InventoryManagementView()
        inventory = self.app.db_manager.get_all_items()
        self.inventory_management_view.show_inventory_for_manager(inventory)
        self.app.current_context = "inventory"

        popup = Popup(
            title="Inventory Management",
            content=self.inventory_management_view,
            size_hint=(0.9, 0.9),
        )
        popup.bind(on_dismiss=self.app.utilities.reset_to_main_context)
        popup.open()

    def show_adjust_price_popup(self):
        self.adjust_price_popup_layout = BoxLayout(orientation="vertical", spacing=10)
        self.adjust_price_popup = Popup(
            title="Enter Target Amount",
            content=self.adjust_price_popup_layout,
            size_hint=(0.8, 0.8),
        )

        self.adjust_price_cash_input = TextInput(
            text="",
            disabled=True,
            multiline=False,
            input_filter="float",
            font_size=30,
            size_hint_y=None,
            height=50,
        )
        self.adjust_price_popup_layout.add_widget(self.adjust_price_cash_input)

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
                on_press=self.app.button_handler.on_adjust_price_numeric_button_press,
                size_hint=(0.8, 0.8),
            )
            keypad_layout.add_widget(btn)

        buttons_layout = GridLayout(cols=4, size_hint_y=1 / 7, spacing=5)
        confirm_button = self.app.utilities.create_md_raised_button(
            "Confirm",
            lambda x: self.app.order_manager.add_adjusted_price_item(),
            (0.8, 0.8),
        )

        cancel_button = self.app.utilities.create_md_raised_button(
            "Cancel",
            lambda x: self.adjust_price_popup.dismiss(),
            (0.8, 0.8),
        )

        buttons_layout.add_widget(confirm_button)
        buttons_layout.add_widget(cancel_button)

        self.adjust_price_popup_layout.add_widget(keypad_layout)
        self.adjust_price_popup_layout.add_widget(buttons_layout)

        self.adjust_price_popup.open()

    def show_guard_screen(self):

        if not self.app.is_guard_screen_displayed:

            guard_layout = BoxLayout()
            self.guard_popup = Popup(
                title="Guard Screen",
                content=guard_layout,
                size_hint=(1, 1),
                auto_dismiss=False,
            )
            self.guard_popup.bind(
                on_touch_down=lambda x, touch: self.app.utilities.dismiss_guard_popup()
            )
            self.app.is_guard_screen_displayed = True

            self.guard_popup.bind(
                on_dismiss=lambda x: setattr(
                    self.app, "is_guard_screen_displayed", False
                )
            )
            self.guard_popup.open()

    def show_lock_screen(self, x):

        if not self.app.is_lock_screen_displayed:

            lock_layout = BoxLayout(orientation="horizontal", size_hint=(1, 1))
            lock_button_layout = BoxLayout(orientation="vertical", size_hint=(0.5, 1))
            self.lockscreen_keypad_layout = GridLayout(cols=3, spacing=1)

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
                    btn = MarkupButton(
                        text=f"[b][size=20]{button}[/size][/b]",
                        color=(1, 1, 1, 1),
                        size_hint=(0.8, 0.8),
                        on_press=partial(self.app.button_handler.on_lock_screen_button_press, button),
                        background_normal='images/lockscreen_background_up.png',
                        background_down='images/lockscreen_background_down.png'
                    )
                    self.lockscreen_keypad_layout.add_widget(btn)

                else:
                    btn_2 = Button(
                        size_hint=(0.8, 0.8),
                        opacity=0,
                        background_color=(0, 0, 0, 0),
                    )
                    btn_2.bind(on_press=self.app.utilities.manual_override)
                    self.lockscreen_keypad_layout.add_widget(btn_2)
            clock_layout = self.create_clock_layout()
            lock_button_layout.add_widget(self.lockscreen_keypad_layout)
            lock_layout.add_widget(lock_button_layout)
            lock_layout.add_widget(clock_layout)
            self.lock_popup = Popup(
                title="",
                content=lock_layout,
                size_hint=(1, 1),
                auto_dismiss=False,
                background_color=(0.78, 0.78, 0.78, 1)
            )
            self.app.is_lock_screen_displayed = True

            self.lock_popup.bind(
                on_dismiss=lambda instance: setattr(
                    self, "is_lock_screen_displayed", False
                )
            )
            self.lock_popup.open()

    def flash_buttons_red(self):

        for btn in self.lockscreen_keypad_layout.children:
            original_background = btn.background_normal
            btn.background_normal = 'red_background.png'

            Clock.schedule_once(lambda dt, btn=btn, original=original_background: setattr(btn, 'background_normal', original), 0.5)

    def create_clock_layout(self):
        # logger.info("test")
        clock_layout = BoxLayout(orientation="vertical", size_hint_x=1 / 3)
        image_path = 'images/RIGS2.png'
        if os.path.exists(image_path):
            img = Image(source=image_path, size_hint=(1, 0.75))
        else:

            img = Label(text="", size_hint=(1, 0.75), halign='center')
        self.clock_label = MDLabel(
            text="",
            size_hint_y=None,
            font_style="H6",
            height=80,
            color=self.app.utilities.get_text_color(),
            halign="center",
        )


        Clock.schedule_interval(self.app.utilities.update_lockscreen_clock, 1)
        clock_layout.add_widget(img)
        clock_layout.add_widget(self.clock_label)
        return clock_layout

    def show_inventory(self):
        inventory = self.app.db_manager.get_all_items()
        inventory_view = InventoryView(order_manager=self.app.order_manager)
        inventory_view.show_inventory(inventory)
        self.inventory_popup = self.create_focus_popup(
            title="Inventory",
            content=inventory_view,
            textinput=inventory_view.ids.label_search_input,
            size_hint=(0.8, 1),
            pos_hint={"top": 1},
        )
        self.inventory_popup.open()

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
                size_hint=(1, 0.15),
                pos_hint={"center_x": 0.5, "center_y": 1 - 0.2 * index},
                on_press=self.app.button_handler.on_tool_button_press,
            )
            float_layout.add_widget(btn)

        self.tools_popup = Popup(
            content=float_layout,
            size_hint=(0.2, 0.6),
            title="",
            background="images/transparent.png",
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
                on_press=self.app.button_handler.on_numeric_button_press,
                size_hint=(0.8, 0.8),
            )
            keypad_layout.add_widget(btn)

        confirm_button = self.app.utilities.create_md_raised_button(
            "Confirm",
            self.app.order_manager.add_custom_item,
            (0.8, 0.8),
        )

        cancel_button = Button(
            text="Cancel",
            on_press=self.app.utilities.on_custom_item_cancel,
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
        order_details = self.app.order_manager.get_order_details()
        popup_layout = BoxLayout(orientation="vertical", spacing=10)
        popup_layout.add_widget(MarkupLabel(text=order_summary, halign="left"))

        button_layout = BoxLayout(
            size_hint_y=None,
            height=50,
            spacing=5,
        )

        btn_pay_cash = self.app.utilities.create_md_raised_button(
            f"[b][size=20]Pay Cash[/b][/size]",
            self.app.button_handler.on_payment_button_press,
            (0.8, 1.5),
        )

        btn_pay_credit = self.app.utilities.create_md_raised_button(
            f"[b][size=20]Pay Credit[/b][/size]",
            self.app.button_handler.on_payment_button_press,
            (0.8, 1.5),
        )
        btn_pay_debit = self.app.utilities.create_md_raised_button(
            f"[b][size=20]Pay Debit[/b][/size]",
            self.app.button_handler.on_payment_button_press,
            (0.8, 1.5),
        )

        btn_pay_split = self.app.utilities.create_md_raised_button(
            f"[b][size=20]Split[/b][/size]",
            self.app.button_handler.on_payment_button_press,
            (0.8, 1.5),
        )

        btn_cancel = Button(
            text="Cancel",
            on_press=self.app.button_handler.on_payment_button_press,
            size_hint=(0.8, 1.5),
        )
        button_layout.add_widget(btn_pay_cash)
        button_layout.add_widget(btn_pay_debit)
        button_layout.add_widget(btn_pay_credit)
        button_layout.add_widget(btn_pay_split)
        button_layout.add_widget(btn_cancel)

        popup_layout.add_widget(button_layout)

        self.finalize_order_popup = Popup(
            title=f"Finalize Order - {order_details['order_id']}",
            content=popup_layout,
            size_hint=(0.6, 0.8),
        )
        self.finalize_order_popup.open()

    def show_cash_payment_popup(self):
        total_with_tax = self.app.order_manager.calculate_total_with_tax()
        common_amounts = self.app.utilities.calculate_common_amounts(total_with_tax)

        self.cash_popup_layout = BoxLayout(orientation="vertical", spacing=10)
        self.cash_payment_input = MoneyInput(
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
        self.cash_popup_layout.add_widget(self.cash_payment_input)

        keypad_layout = GridLayout(cols=2, spacing=5)
        other_buttons = BoxLayout(
            orientation="horizontal",
            spacing=5,
            size_hint=(1, 0.4),
        )

        placeholder_amounts = [0] * 5
        for i, amount in enumerate(placeholder_amounts):
            btn_text = f"${common_amounts[i]}" if i < len(common_amounts) else "-"
            btn = Button(text=btn_text, on_press=self.app.button_handler.on_preset_amount_press)
            btn.disabled = i >= len(common_amounts)
            keypad_layout.add_widget(btn)

        custom_cash_button = Button(
            text="Custom",
            on_press=self.open_custom_cash_popup,
            size_hint=(0.4, 0.8),
        )

        confirm_button = self.app.utilities.create_md_raised_button(
            f"[b]Confirm[/b]",
            self.app.order_manager.on_cash_confirm,
            (0.4, 0.8),
        )

        cancel_button = Button(
            text="Cancel",
            on_press=self.app.utilities.on_cash_cancel,
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
        self.custom_cash_input = TextInput(
            text="",
            multiline=False,
            input_filter="float",
            font_size=30,
            size_hint_y=None,
            height=50,
        )
        self.custom_cash_popup_layout.add_widget(self.custom_cash_input)

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
            btn = self.app.utilities.create_md_raised_button(
                button,
                self.app.button_handler.on_custom_cash_numeric_button_press,
                (0.8, 0.8),
            )
            keypad_layout.add_widget(btn)

        confirm_button = self.app.utilities.create_md_raised_button(
            "Confirm",
            lambda instance: self.app.order_manager.on_custom_cash_confirm(instance),
            (0.8, 0.8),
        )

        cancel_button = Button(
            text="Cancel",
            on_press=self.app.utilities.on_custom_cash_cancel,
            size_hint=(0.8, 0.8),
        )
        keypad_layout.add_widget(confirm_button)
        keypad_layout.add_widget(cancel_button)

        self.custom_cash_popup_layout.add_widget(keypad_layout)
        self.custom_cash_popup = Popup(
            title="Custom Cash",
            content=self.custom_cash_popup_layout,
            size_hint=(0.8, 0.8),
        )
        self.custom_cash_popup.open()

    def show_payment_confirmation_popup(self):
        confirmation_layout = BoxLayout(
            orientation="vertical",

            size_hint=(1, 1),
            spacing=10,
        )
        total_with_tax = self.app.order_manager.calculate_total_with_tax()
        order_details = self.app.order_manager.get_order_details()
        order_summary = "Order Complete:\n\n"

        for item_id, item_details in self.app.order_manager.items.items():
            item_name = item_details["name"]
            quantity = item_details["quantity"]
            total_price_for_item = item_details["total_price"]

            try:
                total_price_float = float(total_price_for_item)
            except ValueError as e:
                print(e)
                continue

            order_summary += f"{item_name} x{quantity}\n"

        # order_summary += (
        #     f"\n${total_with_tax:.2f} Paid With {order_details['payment_method']}"
        # )
        confirmation_layout.add_widget(Label(text=order_summary,size_hint=(0.5,0.9), halign="left", valign="top"))
        confirmation_layout.add_widget(Label(text=f"\n${total_with_tax:.2f} Paid With {order_details['payment_method']}", size_hint_y = 0.2))
        button_layout = BoxLayout(orientation="horizontal", spacing=5, size_hint=(1,0.2))
        done_button = self.app.utilities.create_md_raised_button(
            "Done",
            self.app.button_handler.on_done_button_press,
            (1, 1),
        )

        receipt_button = self.app.utilities.create_md_raised_button(
            "Print Receipt",
            self.app.button_handler.on_receipt_button_press,
            (1, 1),
        )

        button_layout.add_widget(done_button)
        button_layout.add_widget(receipt_button)
        confirmation_layout.add_widget(button_layout)
        self.payment_popup = Popup(
            title="Payment Confirmation",
            content=confirmation_layout,
            size_hint=(0.4, 0.8),
            auto_dismiss=False,
        )
        self.finalize_order_popup.dismiss()
        self.payment_popup.open()

    def show_make_change_popup(self, change):
        change_layout = BoxLayout(orientation="vertical", spacing=10)
        change_layout.add_widget(Label(text=f"Change to return: ${change:.2f}"))

        done_button = self.app.utilities.create_md_raised_button(
            "Done", self.app.utilities.on_change_done, (1, 0.4)
        )
        change_layout.add_widget(done_button)

        self.change_popup = Popup(
            title="Change Calculation", content=change_layout, size_hint=(0.6, 0.3)
        )
        self.change_popup.open()

    def show_add_to_database_popup(self, barcode, categories=None):
        content = BoxLayout(orientation="vertical", padding=10)
        name_layout = BoxLayout(orientation="horizontal", size_hint_y=0.4)
        name_input = TextInput()
        name_layout.add_widget(Label(text="Name", size_hint_x=0.2))
        name_layout.add_widget(name_input)
        barcode_layout = BoxLayout(orientation="horizontal", size_hint_y=0.4)
        barcode_input = TextInput(input_filter="int", text=barcode if barcode else "")
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

        category_layout = BoxLayout(orientation="horizontal", size_hint_y=0.4)
        self.add_to_db_category_input = TextInput(disabled=True)
        category_layout.add_widget(Label(text="Categories", size_hint_x=0.2))
        category_layout.add_widget(self.add_to_db_category_input)

        content.add_widget(name_layout)
        content.add_widget(barcode_layout)
        content.add_widget(price_layout)
        content.add_widget(cost_layout)
        content.add_widget(sku_layout)
        content.add_widget(category_layout)

        button_layout = BoxLayout(
            orientation="horizontal", size_hint_y=None, height="50dp", spacing=10
        )

        button_layout.add_widget(
            MDRaisedButton(
                text="Confirm",
                on_press=lambda _: self.app.db_manager.add_item_to_database(
                    barcode_input.text,
                    name_input.text,
                    price_input.text,
                    cost_input.text,
                    sku_input.text,
                    self.add_to_db_category_input.text,
                ),
            )
        )

        button_layout.add_widget(
            MDRaisedButton(
                text="Close", on_press=lambda x: self.add_to_db_popup.dismiss()
            )
        )
        button_layout.add_widget(
            MDRaisedButton(
                text="Categories", on_press=lambda x: self.open_category_button_popup()
            )
        )

        content.add_widget(button_layout)

        self.add_to_db_popup = Popup(
            title="Item details",
            pos_hint={"top": 1},
            content=content,
            size_hint=(0.8, 0.4),
        )
        self.add_to_db_popup.open()

    #################
    #################
    #################
    #################
    #################

    def handle_split_payment(self):
        self.dismiss_popups(
            "split_amount_popup", "split_cash_popup", "split_change_popup"
        )
        remaining_amount = self.app.order_manager.calculate_total_with_tax()
        remaining_amount = float(f"{remaining_amount:.2f}")
        self.split_payment_info = {
            "total_paid": 0.0,
            "remaining_amount": remaining_amount,
            "payments": [],
        }
        self.show_split_payment_numeric_popup()

    def split_cash_make_change(self, change, amount):
        split_change_layout = BoxLayout(orientation="vertical", spacing=10)
        split_change_layout.add_widget(Label(text=f"Change to return: ${change:.2f}"))

        split_done_button = self.app.utilities.create_md_raised_button(
            "Done",
            lambda x: self.app.utilities.split_cash_continue(amount),
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

    def show_split_cash_popup(self, amount):
        common_amounts = self.app.utilities.calculate_common_amounts(amount)
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
                on_press=self.app.button_handler.split_on_preset_amount_press,
            )

            btn.disabled = i >= len(common_amounts)
            split_cash_keypad_layout.add_widget(btn)

        split_custom_cash_button = Button(
            text="Custom",
            on_press=lambda x: self.split_open_custom_cash_popup(amount),
            size_hint=(0.8, 0.8),
        )

        split_cash_confirm_button = self.app.utilities.create_md_raised_button(
            "Confirm",
            lambda x: self.app.utilities.split_on_cash_confirm(amount),
            (0.8, 0.8),
        )

        split_cash_cancel_button = Button(
            text="Cancel",
            on_press=lambda x: self.app.utilities.split_on_cash_cancel(),
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

    def show_split_cash_confirm(self, amount):
        split_cash_confirm = BoxLayout(orientation="vertical")
        split_cash_confirm_text = Label(text=f"{amount} Cash Payment Confirmed")
        tolerance = 0.001

        if abs(self.split_payment_info["remaining_amount"]) <= tolerance:
            split_cash_confirm_next_btn = self.app.utilities.create_md_raised_button(
                "Done", lambda x: self.app.utilities.split_cash_continue(amount), (1, 0.4)
            )
        else:
            split_cash_confirm_next_btn = self.app.utilities.create_md_raised_button(
                "Next", lambda x: self.app.utilities.split_cash_continue(amount), (1, 0.4)
            )

        split_cash_confirm.add_widget(split_cash_confirm_text)
        split_cash_confirm.add_widget(split_cash_confirm_next_btn)
        self.split_cash_confirm_popup = Popup(
            title="Payment Confirmation",
            content=split_cash_confirm,
            size_hint=(0.4, 0.4),
        )
        self.split_cash_confirm_popup.open()

    def show_split_card_confirm(self, amount, method):
        open_cash_drawer()
        split_card_confirm = BoxLayout(orientation="vertical")
        split_card_confirm_text = Label(text=f"{amount} {method} Payment Confirmed")
        tolerance = 0.001

        if abs(self.split_payment_info["remaining_amount"]) <= tolerance:
            split_card_confirm_next_btn = self.app.utilities.create_md_raised_button(
                "Done",
                lambda x: self.app.utilities.split_card_continue(amount, method),
                (1, 0.4),
            )
        else:
            split_card_confirm_next_btn = self.app.utilities.create_md_raised_button(
                "Next", lambda x: self.app.utilities.split_card_continue(amount, method), (1, 0.4)
            )
        split_card_confirm.add_widget(split_card_confirm_text)
        split_card_confirm.add_widget(split_card_confirm_next_btn)
        self.split_card_confirm_popup = Popup(
            title="Payment Confirmation",
            content=split_card_confirm,
            size_hint=(0.4, 0.4),
        )
        self.split_card_confirm_popup.open()

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
                    on_press=lambda x: self.app.utilities.clear_split_numeric_input(),
                    size_hint=(0.8, 0.8),
                )
                keypad_layout.add_widget(clr_button)
            else:
                btn = Button(
                    text=button,
                    on_press=self.app.button_handler.on_split_payment_numeric_button_press,
                    size_hint=(0.8, 0.8),
                )
                keypad_layout.add_widget(btn)

        buttons_layout = GridLayout(cols=4, size_hint_y=1 / 7, spacing=5)
        cash_button = self.app.utilities.create_md_raised_button(
            "Cash",
            lambda x: self.app.utilities.handle_split_input(
                self.split_payment_numeric_cash_input.text, "Cash"
            ),
            (0.8, 0.8),
        )

        debit_button = self.app.utilities.create_md_raised_button(
            "Debit",
            lambda x: self.app.utilities.handle_split_input(
                self.split_payment_numeric_cash_input.text, "Debit"
            ),
            (0.8, 0.8),
        )
        credit_button = self.app.utilities.create_md_raised_button(
            "Credit",
            lambda x: self.app.utilities.handle_split_input(
                self.split_payment_numeric_cash_input.text, "Credit"
            ),
            (0.8, 0.8),
        )

        cancel_button = Button(
            text="Cancel",
            on_press=lambda x: self.app.utilities.split_cancel(),
            size_hint=(0.8, 0.8),
        )

        buttons_layout.add_widget(cash_button)
        buttons_layout.add_widget(debit_button)
        buttons_layout.add_widget(credit_button)
        buttons_layout.add_widget(cancel_button)

        self.split_payment_numeric_popup_layout.add_widget(keypad_layout)
        self.split_payment_numeric_popup_layout.add_widget(buttons_layout)

        self.split_payment_numeric_popup.open()

    def split_open_custom_cash_popup(self, amount):
        self.split_custom_cash_popup_layout = BoxLayout(
            orientation="vertical", spacing=10
        )
        self.split_custom_cash_input = TextInput(
            text="",
            multiline=False,
            input_filter="float",
            font_size=30,
            size_hint_y=None,
            height=50,
        )
        self.split_custom_cash_popup_layout.add_widget(self.split_custom_cash_input)

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
            btn = self.app.utilities.create_md_raised_button(
                button,
                self.app.button_handler.on_split_custom_cash_payment_numeric_button_press,
                (0.8, 0.8),
            )
            keypad_layout.add_widget(btn)
        # amount = float(self.split_custom_cash_input.text)
        confirm_button = self.app.utilities.create_md_raised_button(
            "Confirm",
            lambda x: self.app.utilities.split_on_custom_cash_confirm(amount),
            (0.8, 0.8),
        )

        cancel_button = Button(
            text="Cancel",
            on_press=self.app.utilities.on_split_custom_cash_cancel,
            size_hint=(0.8, 0.8),
        )
        keypad_layout.add_widget(confirm_button)
        keypad_layout.add_widget(cancel_button)

        self.split_custom_cash_popup_layout.add_widget(keypad_layout)
        self.split_custom_cash_popup = Popup(
            title="Split Custom Cash",
            content=self.split_custom_cash_popup_layout,
            size_hint=(0.8, 0.8),
        )
        self.split_custom_cash_popup.open()

    def reboot_are_you_sure(self):
        arys_layout = BoxLayout()

        btn = self.app.utilities.create_md_raised_button(
            "Yes!",
            self.app.utilities.reboot,
            (0.9, 0.9),
        )
        btn2 = self.app.utilities.create_md_raised_button(
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

    def dismiss_popups(self, *popups):
        for popup_attr in popups:
            if hasattr(self, popup_attr):
                try:
                    popup = getattr(self, popup_attr)
                    if popup._is_open:
                        popup.dismiss()
                except Exception as e:
                    print(e)

    def create_focus_popup(self, title, content, textinput, size_hint, pos_hint={}):
        popup = FocusPopup(
            title=title, content=content, size_hint=size_hint, pos_hint=pos_hint
        )
        popup.focus_on_textinput(textinput)
        return popup

    def catch_label_printing_errors(self, e):
        label_errors_layout = BoxLayout(orientation="vertical")
        label_errors_text = Label(text=f"Caught an error from the label printer\nCheck that the printer is turned on and plugged in\nand there are labels in it.\n The full error is below:\n\n{e}")
        label_errors_button = MDRaisedButton(text="Dismiss", on_press=lambda x: self.label_errors_popup.dismiss())
        label_errors_layout.add_widget(label_errors_text)
        label_errors_layout.add_widget(label_errors_button)

        self.label_errors_popup = Popup(content=label_errors_layout, size_hint=(0.4,0.4))
        self.label_errors_popup.open()

    def unrecoverable_error(self):
        print("unrecoverable")
        error_layout=BoxLayout(orientation="vertical")
        error_text=Label(text=f"There has been an unrecoverable error\nand the system needs to reboot\nSorry!")
        error_button=Button(text="Reboot", on_press=lambda x: self.app.reboot())
        error_layout.add_widget(error_text)
        error_layout.add_widget(error_button)
        error_popup=Popup(
            title="Uh-Oh",
            auto_dismiss=False,
            size_hint=(0.4,0.4),
            content=error_layout
            )
        error_popup.open()



class MarkupLabel(Label):
    pass
class MarkupButton(Button):
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

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(FinancialSummaryWidget, cls).__new__(cls)
        return cls._instance

    def __init__(self, ref, **kwargs):
        if not hasattr(self, "_initialized"):
            self.app = ref
            super(FinancialSummaryWidget, self).__init__(**kwargs)
            self.size_hint_y = None
            self.size_hint_x = 1
            self.height = 80
            self.orientation = "vertical"
            self.order_mod_popup = None
            print(self)
            self._initialized = True

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
        self.app.order_layout.clear_widgets()
        self.app.order_manager.clear_order()
        self.app.utilities.update_financial_summary()
        self.order_mod_popup.dismiss()

    def open_order_modification_popup(self):
        order_mod_layout = FloatLayout()

        discount_order_button = MDRaisedButton(
            text="Add Order Discount",
            pos_hint={"center_x": 0.5, "center_y": 1 - 0.2},
            size_hint=(1, 0.15),
            on_press=lambda x: self.app.popup_manager.add_order_discount_popup()
        )
        clear_order_button = MDRaisedButton(
            text="Clear Order",
            pos_hint={"center_x": 0.5, "center_y": 1 - 0.2},
            size_hint=(1, 0.15),
            on_press=lambda x: self.clear_order()
        )
        adjust_price_button = MDRaisedButton(
            text="Adjust Payment",
            pos_hint={"center_x": 0.5, "center_y": 1 - 0.4},
            size_hint=(1, 0.15),
            on_press=lambda x: self.adjust_price()
        )
        clear_order_button = MDRaisedButton(
            text="Clear Order",
            pos_hint={"center_x": 0.5, "center_y": 1 - 0.6},
            size_hint=(1, 0.15),
            on_press=lambda x: self.clear_order()
        )
        order_mod_layout.add_widget(discount_order_button)
        order_mod_layout.add_widget(adjust_price_button)
        order_mod_layout.add_widget(clear_order_button)
        self.order_mod_popup = Popup(
            title="",
            content=order_mod_layout,
            size_hint=(0.2, 0.6),
            background="images/transparent.png",
            background_color=(0, 0, 0, 0),
            separator_height=0,

        )
        self.order_mod_popup.open()

    def adjust_price(self):
        self.app.popup_manager.show_adjust_price_popup()
        self.order_mod_popup.dismiss()



