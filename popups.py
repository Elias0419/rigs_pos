# import logging
#
# logger = logging.getLogger(__name__)
from kivymd.uix.selectioncontrol import MDCheckbox
from kivy.uix.widget import Widget
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.popup import Popup
from kivy.uix.gridlayout import GridLayout
from kivy.uix.boxlayout import BoxLayout
from kivymd.uix.button import MDRaisedButton, MDFlatButton, MDIconButton
from kivy.uix.textinput import TextInput
from kivymd.color_definitions import palette
from kivy.uix.floatlayout import FloatLayout
from label_printer import LabelPrintingView
from inventory_manager import InventoryManagementView, InventoryView
from open_cash_drawer import open_cash_drawer
from kivy.clock import Clock
from kivymd.uix.label import MDLabel
from kivymd.uix.list import MDList
from kivymd.uix.card import MDCard
from kivymd.uix.dialog import MDDialog
from kivy.uix.scrollview import ScrollView
from kivy.uix.image import Image
import os
from datetime import datetime
from functools import partial
from kivymd.uix.gridlayout import MDGridLayout
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.button import MDRaisedButton
from kivymd.uix.textfield import MDTextField
from kivy.utils import get_color_from_hex


class PopupManager:
    def __init__(self, ref):
        self.app = ref

    def create_category_popup(self):
        self.selected_categories = []
        categories = self.app.utilities.initialize_categories()
        main_layout = GridLayout(orientation="lr-tb", cols=1, rows=2)
        layout = GridLayout(
            orientation="lr-tb", spacing=5, size_hint=(1, 1), rows=10, cols=5
        )

        layout.bind(minimum_height=layout.setter("height"))

        for category in categories:
            layout.add_widget(self.create_category_item(category))
        main_layout.add_widget(layout)
        button_layout = GridLayout(
            orientation="lr-tb", spacing=5, cols=2, rows=2, size_hint=(1, 0.2)
        )
        confirm_button = MDRaisedButton(
            text="Confirm",
            on_release=lambda instance: self.app.utilities.apply_categories(),
            size_hint=(0.2, 1),
        )

        cancel_button = MDRaisedButton(
            text="Cancel",
            on_release=lambda instance: self.category_button_popup.dismiss(),
            size_hint=(0.2, 1),
        )
        button_layout.add_widget(confirm_button)
        button_layout.add_widget(cancel_button)
        main_layout.add_widget(button_layout)
        self.category_button_popup = Popup(content=main_layout, size_hint=(0.8, 0.8))
        # self.category_button_popup_inv.open()

        return self.category_button_popup

    def open_update_category_button_popup(self):
        self.selected_categories_row = []
        categories = self.app.utilities.initialize_categories()
        main_layout = GridLayout(orientation="lr-tb", cols=1, rows=2)
        layout = GridLayout(
            orientation="lr-tb", spacing=5, size_hint=(1, 1), rows=10, cols=5
        )

        layout.bind(minimum_height=layout.setter("height"))

        for category in categories:
            layout.add_widget(self.create_category_item_row(category))
        main_layout.add_widget(layout)
        button_layout = GridLayout(
            orientation="lr-tb", spacing=5, cols=2, rows=2, size_hint=(1, 0.2)
        )
        confirm_button = MDRaisedButton(
            text="Confirm",
            on_release=lambda instance: self.app.utilities.apply_categories_row(),
            size_hint=(0.2, 1),
        )
        cancel_button = MDRaisedButton(
            text="Cancel",
            on_release=lambda instance: self.category_button_popup_row.dismiss(),
            size_hint=(0.2, 1),
        )
        button_layout.add_widget(confirm_button)
        button_layout.add_widget(cancel_button)
        main_layout.add_widget(button_layout)
        self.category_button_popup_row = Popup(
            content=main_layout, size_hint=(0.8, 0.8)
        )
        self.category_button_popup_row.open()

    def open_category_button_popup_inv(self):
        self.selected_categories_inv = []
        categories = self.app.utilities.initialize_categories()
        main_layout = GridLayout(orientation="lr-tb", cols=1, rows=2)
        layout = GridLayout(
            orientation="lr-tb", spacing=5, size_hint=(1, 1), rows=10, cols=5
        )

        layout.bind(minimum_height=layout.setter("height"))

        for category in categories:
            layout.add_widget(self.create_category_item_inv(category))
        main_layout.add_widget(layout)
        button_layout = GridLayout(
            orientation="lr-tb", spacing=5, cols=2, rows=2, size_hint=(1, 0.2)
        )
        confirm_button = MDRaisedButton(
            text="Confirm",
            on_release=lambda instance: self.app.utilities.apply_categories_inv(),
            size_hint=(0.2, 1),
        )
        cancel_button = MDRaisedButton(
            text="Cancel",
            on_release=lambda instance: self.category_button_popup_inv.dismiss(),
            size_hint=(0.2, 1),
        )
        button_layout.add_widget(confirm_button)
        button_layout.add_widget(cancel_button)
        main_layout.add_widget(button_layout)
        self.category_button_popup_inv = Popup(
            content=main_layout, size_hint=(0.8, 0.8)
        )
        self.category_button_popup_inv.open()

    def create_category_item(self, category):
        checkbox = MDCheckbox(size_hint=(None, None), size=(48, 48))
        checkbox.bind(
            active=lambda instance, is_active, cat=category: self.app.utilities.toggle_category_selection(
                is_active, cat
            )
        )

        container = TouchableMDBoxLayout(
            orientation="horizontal", size_hint_y=None, height=40, checkbox=checkbox
        )
        label = MDLabel(text=category, size_hint_y=None, height=40)

        container.add_widget(checkbox)
        container.add_widget(label)

        return container

    def create_category_item_inv(self, category):
        checkbox = MDCheckbox(size_hint=(None, None), size=(48, 48))
        checkbox.bind(
            active=lambda instance, is_active, cat=category: self.app.utilities.toggle_category_selection_inv(
                is_active, cat
            )
        )
        container = TouchableMDBoxLayout(
            orientation="horizontal", size_hint_y=None, height=40, checkbox=checkbox
        )

        label = MDLabel(text=category, size_hint_y=None, height=40)
        container.add_widget(checkbox)
        container.add_widget(label)
        return container

    def create_category_item_row(self, category):
        checkbox = MDCheckbox(size_hint=(None, None), size=(48, 48))
        checkbox.bind(
            active=lambda instance, is_active, cat=category: self.app.utilities.toggle_category_selection_row(
                is_active, cat
            )
        )
        container = TouchableMDBoxLayout(
            orientation="horizontal", size_hint_y=None, height=40, checkbox=checkbox
        )

        label = MDLabel(text=category, size_hint_y=None, height=40)
        container.add_widget(checkbox)
        container.add_widget(label)
        return container

    def open_category_button_popup(self):
        category_button_popup = self.create_category_popup()
        category_button_popup.open()

    def inventory_item_popup_row(self, instance):

        content = BoxLayout(orientation="vertical", padding=10)
        name_layout = BoxLayout(orientation="horizontal", size_hint_y=0.4)
        name_input = TextInput(text=instance.name)
        name_layout.add_widget(Label(text="Name", size_hint_x=0.2))
        name_layout.add_widget(name_input)
        barcode_layout = BoxLayout(orientation="horizontal", size_hint_y=0.4)

        self.item_barcode_input = TextInput(
            input_filter="int", text=instance.barcode if instance.barcode else ""
        )
        barcode_layout.add_widget(Label(text="Barcode", size_hint_x=0.2))
        barcode_layout.add_widget(self.item_barcode_input)

        price_layout = BoxLayout(orientation="horizontal", size_hint_y=0.4)
        price_input = TextInput(input_filter="float", text=instance.price)
        price_layout.add_widget(Label(text="Price", size_hint_x=0.2))
        price_layout.add_widget(price_input)

        cost_layout = BoxLayout(orientation="horizontal", size_hint_y=0.4)
        cost_input = TextInput(text=instance.cost, input_filter="float")
        cost_layout.add_widget(Label(text="Cost", size_hint_x=0.2))
        cost_layout.add_widget(cost_input)

        sku_layout = BoxLayout(orientation="horizontal", size_hint_y=0.4)
        sku_input = TextInput(text=instance.sku)
        sku_layout.add_widget(Label(text="SKU", size_hint_x=0.2))
        sku_layout.add_widget(sku_input)

        category_layout = BoxLayout(orientation="horizontal", size_hint_y=0.4)
        self.add_to_db_category_input_row = TextInput(
            text=instance.category, disabled=True
        )
        category_layout.add_widget(Label(text="Categories", size_hint_x=0.2))
        category_layout.add_widget(self.add_to_db_category_input_row)

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
                text="Update Details",
                on_press=lambda x: self.app.utilities.update_confirm_and_close(
                    barcode_input.text,
                    name_input.text,
                    price_input.text,
                    cost_input.text,
                    sku_input.text,
                    self.add_to_db_category_input_row.text,
                    self.inventory_item_update_popup,
                ),
            )
        )
        button_layout.add_widget(
            MDRaisedButton(
                text="Categories",
                on_press=lambda x: self.open_update_category_button_popup(),
            )
        )

        button_layout.add_widget(
            MDRaisedButton(
                text="Close",
                on_press=lambda x: self.inventory_item_update_popup.dismiss(),
            )
        )

        content.add_widget(button_layout)

        self.inventory_item_update_popup = Popup(
            title="Item details",
            pos_hint={"top": 1},
            content=content,
            size_hint=(0.8, 0.4),
            on_dismiss=lambda x: self.app.inventory_manager.reset_inventory_context(),
        )
        self.inventory_item_update_popup.open()

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

    def show_add_or_bypass_popup(self, barcode):

        popup_layout = BoxLayout(orientation="vertical", spacing=5)
        self.barcode_label = Label(text=f"Barcode: {barcode} ")
        popup_layout.add_widget(self.barcode_label)
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
            item_discount = item_info.get("discount", {"amount": 0, "percent": False})
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
                lambda x, item_id=item_id: self.open_add_discount_popup(item_id),
                # self.add_discount_popup,
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

    def open_add_discount_popup(self, item_id):
        self.add_discount_popup(item_id)

    def add_discount_popup(self, item_id, instance=None):
        print("add_discount_popup", item_id)
        discount_item_popup_layout = GridLayout(
            orientation="tb-lr", spacing=5, cols=1, rows=2
        )
        self.discount_item_popup = Popup(
            title="Add Discount",
            content=discount_item_popup_layout,
            size_hint=(0.6, 0.8),
        )

        discounts = [
            {"type": "percent", "values": [10, 20, 30, 40, 50]},
            {"type": "amount", "values": [10, 20, 30, 40, 50]},
        ]

        discount_item_layout = GridLayout(orientation="tb-lr", cols=2, spacing=10)

        for discount_type in discounts:
            for value in discount_type["values"]:
                label = (
                    f"[size=20][b]{value}%[/size][/b]"
                    if discount_type["type"] == "percent"
                    else f"[size=20][b]${value}[/size][/b]"
                )
                discount_button = self.app.utilities.create_md_raised_button(
                    label,
                    lambda x, v=value, t=discount_type[
                        "type"
                    ]: self.apply_item_discount(v, t, item_id=item_id),
                    (0.8, 0.8),
                )
                discount_item_layout.add_widget(discount_button)
        button_layout = GridLayout(
            orientation="lr-tb", spacing=5, cols=2, rows=1, size_hint_y=0.2
        )
        custom_button = Button(
            text="Custom",
            on_press=lambda x: self.custom_add_item_discount_popup(item_id=item_id),
        )
        cancel_button = Button(
            text="Cancel",
            on_press=lambda x: self.app.utilities.dismiss_single_discount_popup(),
        )

        button_layout.add_widget(custom_button)
        button_layout.add_widget(cancel_button)
        discount_item_popup_layout.add_widget(discount_item_layout)
        discount_item_popup_layout.add_widget(button_layout)

        self.discount_item_popup.open()

    def apply_item_discount(self, value, discount_type, item_id=""):
        print("apply_item_discount", item_id)
        if discount_type == "percent":

            self.app.order_manager.discount_single_item(
                discount_amount=value, percent=True, item_id=item_id
            )
        else:

            self.app.order_manager.discount_single_item(
                discount_amount=value, percent=False, item_id=item_id
            )

    def custom_add_item_discount_popup(self, item_id, instance=None):

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
                item_id=item_id,
            ),
            (0.8, 0.8),
        )
        percent_button = self.app.utilities.create_md_raised_button(
            "Percent",
            lambda x: self.app.order_manager.discount_single_item(
                discount_amount=self.discount_amount_input.text,
                percent=True,
                item_id=item_id,
            ),
            (0.8, 0.8),
        )

        cancel_button = Button(
            text="Cancel",
            on_press=lambda x: self.app.utilities.dismiss_single_discount_popup(),
            size_hint=(0.8, 0.8),
        )

        keypad_layout.add_widget(amount_button)
        keypad_layout.add_widget(percent_button)
        keypad_layout.add_widget(cancel_button)
        discount_popup_layout.add_widget(keypad_layout)

        self.discount_popup.open()

    def custom_add_order_discount_popup(self):

        custom_discount_order_popup_layout = BoxLayout(
            orientation="vertical", spacing=10
        )
        self.custom_discount_order_popup = Popup(
            title="Add Discount",
            content=custom_discount_order_popup_layout,
            size_hint=(0.8, 0.8),
        )
        self.custom_discount_order_amount_input = TextInput(
            text="",
            disabled=True,
            multiline=False,
            input_filter="float",
            font_size=30,
            size_hint_y=None,
            height=50,
        )
        custom_discount_order_popup_layout.add_widget(
            self.custom_discount_order_amount_input
        )

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
            lambda x: self.app.order_manager.discount_entire_order(
                discount_amount=self.custom_discount_order_amount_input.text
            ),
            size_hint=(0.8, 0.8),
        )
        percent_button = self.app.utilities.create_md_raised_button(
            "Percent",
            lambda x: self.app.order_manager.discount_entire_order(
                discount_amount=self.custom_discount_order_amount_input.text,
                percent=True,
            ),
            size_hint=(0.8, 0.8),
        )

        cancel_button = Button(
            text="Cancel",
            on_press=lambda x: self.app.utilities.dismiss_entire_discount_popup(),
            size_hint=(0.8, 0.8),
        )

        keypad_layout.add_widget(amount_button)
        keypad_layout.add_widget(percent_button)
        keypad_layout.add_widget(cancel_button)
        custom_discount_order_popup_layout.add_widget(keypad_layout)

        self.custom_discount_order_popup.open()

    def add_order_discount_popup(self):
        discount_order_popup_layout = GridLayout(
            orientation="tb-lr", spacing=5, cols=1, rows=2
        )
        self.discount_order_popup = Popup(
            title="Add Discount",
            content=discount_order_popup_layout,
            size_hint=(0.6, 0.8),
        )

        discounts = [
            {"type": "percent", "values": [10, 20, 30, 40, 50]},
            {"type": "amount", "values": [10, 20, 30, 40, 50]},
        ]

        discount_layout = GridLayout(orientation="tb-lr", cols=2, spacing=10)

        for discount_type in discounts:
            for value in discount_type["values"]:
                label = (
                    f"[size=20][b]{value}%[/size][/b]"
                    if discount_type["type"] == "percent"
                    else f"[size=20][b]${value}[/size][/b]"
                )
                discount_button = self.app.utilities.create_md_raised_button(
                    label,
                    lambda x, v=value, t=discount_type["type"]: self.apply_discount(
                        v, t
                    ),
                    (0.8, 0.8),
                )
                discount_layout.add_widget(discount_button)
        button_layout = GridLayout(
            orientation="lr-tb", spacing=5, cols=2, rows=1, size_hint_y=0.2
        )
        custom_button = Button(
            text="Custom",
            on_press=lambda x: self.custom_add_order_discount_popup(),
        )
        cancel_button = Button(
            text="Cancel",
            on_press=lambda x: self.app.utilities.dismiss_discount_order_popup(),
        )

        button_layout.add_widget(custom_button)
        button_layout.add_widget(cancel_button)
        discount_order_popup_layout.add_widget(discount_layout)
        discount_order_popup_layout.add_widget(button_layout)

        self.discount_order_popup.open()

    def apply_discount(self, value, discount_type):
        if discount_type == "percent":

            self.app.order_manager.discount_entire_order(
                discount_amount=value, percent=True
            )
        else:

            self.app.order_manager.discount_entire_order(
                discount_amount=value, percent=False
            )

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
        self.label_printing_popup = Popup(
            title="Label Printing", content=label_printing_view, size_hint=(0.9, 0.9)
        )
        self.label_printing_popup.bind(
            on_dismiss=self.app.utilities.reset_to_main_context
        )
        self.label_printing_popup.open()

    def show_inventory_management_view(self):

        self.inventory_management_view = InventoryManagementView()
        inventory = self.app.db_manager.get_all_items()
        self.inventory_management_view.show_inventory_for_manager(inventory)
        self.app.current_context = "inventory"

        self.inventory_management_view_popup = Popup(
            title="Inventory Management",
            content=self.inventory_management_view,
            size_hint=(0.9, 0.9),
        )
        self.inventory_management_view_popup.bind(
            on_dismiss=self.on_inventory_manager_dismiss
        )
        self.inventory_management_view_popup.open()

    def on_inventory_manager_dismiss(self, instance):
        self.app.utilities.reset_to_main_context(instance)
        self.app.inventory_manager.detach_from_parent()
        self.inventory_management_view.ids.inv_search_input.text = ""

    def show_adjust_price_popup(self):

        self.adjust_price_popup_layout = BoxLayout(orientation="vertical", spacing=10)
        self.adjust_price_popup = Popup(
            title="Enter Target Amount",
            content=self.adjust_price_popup_layout,
            size_hint=(0.8, 0.8),
            on_dismiss=lambda x: setattr(self.adjust_price_cash_input, "text", ""),
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
        # return self.adjust_price_popup

    def show_guard_screen(self):
        if not self.app.is_guard_screen_displayed:
            guard_layout = BoxLayout(orientation="vertical")

            clock_label = Label(size_hint_y=0.1, font_size=30)

            def update_time(*args):
                clock_label.text = datetime.now().strftime("%I:%M %p")

            Clock.schedule_interval(update_time, 1)

            guard_image = Image(source="images/guard.jpg")

            guard_layout.add_widget(clock_label)
            guard_layout.add_widget(guard_image)

            self.guard_popup = Popup(
                title="Guard Screen",
                content=guard_layout,
                size_hint=(1, 1),
                auto_dismiss=False,
            )
            self.guard_popup.bind(
                on_touch_down=lambda x, touch: self.app.utilities.dismiss_guard_popup()
            )

            self.guard_popup.bind(
                on_dismiss=lambda x: setattr(
                    self.app, "is_guard_screen_displayed", False
                )
            )

            self.guard_popup.open()
            update_time()

    def show_lock_screen(self):

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
                        on_press=partial(
                            self.app.button_handler.on_lock_screen_button_press, button
                        ),
                        background_normal="images/lockscreen_background_up.png",
                        background_down="images/lockscreen_background_down.png",
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
            # lock_layout.add_widget(self.pin_input)
            lock_layout.add_widget(clock_layout)
            self.lock_popup = Popup(
                title="",
                content=lock_layout,
                size_hint=(1, 1),
                auto_dismiss=False,
                background_color=(0.78, 0.78, 0.78, 1),
            )

            self.lock_popup.bind(
                on_dismiss=lambda instance: setattr(
                    self, "is_lock_screen_displayed", False
                )
            )

            self.lock_popup.open()

    def flash_buttons_red(self):  # move to utils

        for btn in self.lockscreen_keypad_layout.children:
            original_background = btn.background_normal
            btn.background_normal = "red_background.png"

            Clock.schedule_once(
                lambda dt, btn=btn, original=original_background: setattr(
                    btn, "background_normal", original
                ),
                0.5,
            )

    def create_clock_layout(self):  # not a popup - to utils

        self.pin_input = MDLabel(
            text="",
            size_hint_y=None,
            font_style="H4",
            height=80,
            color=self.app.utilities.get_text_color(),
            halign="center",
        )
        clock_layout = BoxLayout(orientation="vertical", size_hint_x=1 / 3)
        image_path = "images/RIGS2.png"
        if os.path.exists(image_path):
            img = Image(source=image_path, size_hint=(1, 0.75))
        else:

            img = Label(text="", size_hint=(1, 0.75), halign="center")
        self.clock_label = MDLabel(
            text="",
            size_hint_y=None,
            font_style="H4",
            height=80,
            color=self.app.utilities.get_text_color(),
            halign="center",
        )

        Clock.schedule_interval(self.app.utilities.update_lockscreen_clock, 1)
        clock_layout.add_widget(img)
        clock_layout.add_widget(self.pin_input)
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
            size_hint=(0.4, 1),
            pos_hint={"top": 1},
        )
        self.inventory_popup.open()

    def show_tools_popup(self):

        float_layout = FloatLayout()

        tool_buttons = [
            "Clear Order",
            "Calculator",
            "Open Register",
            "Reporting",
            "Label Printer",
            "Inventory Management",
            "System",
        ]

        for index, tool in enumerate(tool_buttons):
            btn = MDRaisedButton(
                text=tool,
                size_hint=(1, 0.125),
                pos_hint={"center_x": 0.5, "center_y": 1 - 0.15 * index},
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

    def show_custom_item_popup(self, barcode="01234567890"):

        self.custom_item_popup_layout = BoxLayout(orientation="vertical", spacing=5)
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
            btn = Button(
                text=button,
                on_press=self.app.button_handler.on_numeric_button_press,
                size_hint=(0.8, 0.8),
                font_size=30,
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
        self.custom_item_popup = FocusPopup(
            title="Custom Item",
            content=self.custom_item_popup_layout,
            size_hint=(0.6, 0.6),
            on_dismiss=lambda x: setattr(self.cash_input, "text", ""),
        )
        self.custom_item_popup.focus_on_textinput(self.cash_input)
        self.custom_item_popup.open()

    def show_order_popup(self, order_summary):

        order_details = self.app.order_manager.get_order_details()
        popup_layout = GridLayout(orientation="lr-tb", spacing=5, cols=2, rows=1)
        items_and_totals_layout = GridLayout(
            orientation="tb-lr", spacing=5, cols=1, rows=3
        )
        items_layout = BoxLayout(
            orientation="vertical",
            size_hint_y=1,
        )

        def determine_label_height(text, max_line_length):

            if len(text) > max_line_length:
                return 40
            else:
                return 20

        max_line_length = 42

        for item_id, item_details in order_details["items"].items():
            item_text = f"{item_details['quantity']}x {item_details['name']} - ${item_details['total_price']:.2f}"
            text_height = determine_label_height(item_text, max_line_length)
            item_label = MDLabel(
                text=item_text, halign="left", size_hint_y=None, height=text_height
            )
            items_layout.add_widget(item_label)
        items_and_totals_layout.add_widget(items_layout)
        spacer = Widget(size_hint_y=1)
        items_and_totals_layout.add_widget(spacer)
        totals_layout = BoxLayout(size_hint_y=None, height=100, orientation="vertical")
        subtotal_label = MDLabel(
            text=f"Subtotal: ${order_details['subtotal']:.2f}", halign="left"
        )
        tax_label = MDLabel(
            text=f"Tax: ${order_details['tax_amount']:.2f}", halign="left"
        )
        total_label = MDLabel(
            text=f"[size=25]Total: [b]${order_details['total_with_tax']:.2f}[/b][/size]",
            halign="left",
        )

        totals_layout.add_widget(subtotal_label)
        if order_details["discount"] > 0:
            discount_label = MDLabel(
                text=f"Discount: -${order_details['discount']:.2f}", halign="left"
            )
            totals_layout.add_widget(discount_label)
        totals_layout.add_widget(tax_label)
        totals_layout.add_widget(total_label)
        items_and_totals_layout.add_widget(totals_layout)
        popup_layout.add_widget(items_and_totals_layout)

        buttons_layout = GridLayout(orientation="tb-lr", spacing=5, cols=1, rows=5)

        btn_pay_cash = self.app.utilities.create_md_raised_button(
            f"[b][size=20]Pay Cash[/b][/size]",
            self.app.button_handler.on_payment_button_press,
            (0.8, 1),
        )

        btn_pay_credit = self.app.utilities.create_md_raised_button(
            f"[b][size=20]Pay Credit[/b][/size]",
            self.app.button_handler.on_payment_button_press,
            (0.8, 1),
        )
        btn_pay_debit = self.app.utilities.create_md_raised_button(
            f"[b][size=20]Pay Debit[/b][/size]",
            self.app.button_handler.on_payment_button_press,
            (0.8, 1),
        )

        btn_pay_split = self.app.utilities.create_md_raised_button(
            f"[b][size=20]Split[/b][/size]",
            self.app.button_handler.on_payment_button_press,
            (0.8, 1),
        )

        btn_cancel = Button(
            text="Cancel",
            on_press=self.app.button_handler.on_payment_button_press,
            size_hint=(0.8, 1),
        )
        buttons_layout.add_widget(btn_pay_cash)
        buttons_layout.add_widget(btn_pay_debit)
        buttons_layout.add_widget(btn_pay_credit)
        buttons_layout.add_widget(btn_pay_split)
        buttons_layout.add_widget(btn_cancel)
        popup_layout.add_widget(buttons_layout)

        bottom_layout = BoxLayout(
            orientation="vertical", size_hint_y=None, height=90, spacing=5
        )

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
            btn_text = (
                f"[b][size=20]${common_amounts[i]:.2f}[/size][/b]"
                if i < len(common_amounts)
                else "-"
            )
            btn = MarkupButton(
                text=btn_text, on_press=self.app.button_handler.on_preset_amount_press
            )
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
            size_hint=(0.6, 0.8),
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
            btn = Button(
                text=button,
                on_press=self.app.button_handler.on_custom_cash_numeric_button_press,
                size_hint=(0.8, 0.8),
                font_size=30,
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
            size_hint=(0.6, 0.6),
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

        confirmation_layout.add_widget(Label(text=order_summary, size_hint=(0.5, 0.9)))
        confirmation_layout.add_widget(
            MDLabel(
                text=f"[b]${total_with_tax:.2f} Paid With {order_details['payment_method']}[/b]",
                size_hint_y=0.2,
                halign="center",
            )
        )
        button_layout = BoxLayout(orientation="vertical", spacing=5, size_hint=(1, 0.4))
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

            btn_text = (
                f"[b][size=20]${common_amounts[i]}[/size][/b]"
                if i < len(common_amounts)
                else "-"
            )
            btn = MarkupButton(
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
                "Done",
                lambda x: self.app.utilities.split_cash_continue(amount),
                (1, 0.4),
            )
        else:
            split_cash_confirm_next_btn = self.app.utilities.create_md_raised_button(
                "Next",
                lambda x: self.app.utilities.split_cash_continue(amount),
                (1, 0.4),
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
                "Next",
                lambda x: self.app.utilities.split_card_continue(amount, method),
                (1, 0.4),
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
        if hasattr(self, "label_errors_popup") and self.label_errors_popup._is_open:
            self.label_errors_popup.dismiss()
        label_errors_layout = GridLayout(orientation="tb-lr", rows=2)
        label_errors_text = Label(
            text=f"Caught an error from the label printer:\n\n{e}\n\nMake sure it's plugged in and turned on.",
            size_hint_y=0.5,
            pos_hint={"top": 1},
        )
        label_errors_icon_button = MDRaisedButton(
            text="Try Again",
            on_press=lambda x: self.app.label_printer.process_queue(),
            size_hint_x=1,
        )
        label_errors_button = MDRaisedButton(
            text="Dismiss",
            on_press=lambda x: self.label_errors_popup.dismiss(),
            size_hint_x=1,
        )
        label_errors_layout.add_widget(label_errors_text)
        buttons_layout = GridLayout(
            orientation="lr-tb", cols=2, size_hint_y=0.1, spacing=5
        )
        buttons_layout.add_widget(label_errors_button)
        buttons_layout.add_widget(label_errors_icon_button)
        label_errors_layout.add_widget(buttons_layout)
        self.label_errors_popup = Popup(
            content=label_errors_layout,
            size_hint=(0.4, 0.4),
            title="Label Printer Error",
        )
        self.label_errors_popup.open()

    def catch_receipt_printer_errors(self, e, order_details):

        if hasattr(self, "receipt_errors_popup") and self.receipt_errors_popup._is_open:
            self.receipt_errors_popup.dismiss()
        receipt_errors_layout = GridLayout(orientation="tb-lr", rows=2)
        receipt_errors_text = Label(
            text=f"Caught an error from the receipt printer:\n\n{e}\n\nMake sure it's plugged in and turned on.",
            size_hint_y=0.5,
            pos_hint={"top": 1},
        )
        receipt_errors_icon_button = MDRaisedButton(
            text="Try Again",
            on_press=lambda x: self.app.receipt_printer.re_initialize_after_error(order_details),
            size_hint_x=1,
        )
        receipt_errors_button = MDRaisedButton(
            text="Dismiss",
            on_press=lambda x: self.receipt_errors_popup.dismiss(),
            size_hint_x=1,
        )
        receipt_errors_layout.add_widget(receipt_errors_text)
        buttons_layout = GridLayout(
            orientation="lr-tb", cols=2, size_hint_y=0.1, spacing=5
        )
        buttons_layout.add_widget(receipt_errors_button)
        buttons_layout.add_widget(receipt_errors_icon_button)
        receipt_errors_layout.add_widget(buttons_layout)
        self.receipt_errors_popup = Popup(
            content=receipt_errors_layout,
            size_hint=(0.4, 0.4),
            title="Receipt Printer Error",
        )
        self.receipt_errors_popup.open()


    def unrecoverable_error(self):
        print("unrecoverable")
        error_layout = BoxLayout(orientation="vertical")
        error_text = Label(
            text=f"There has been an unrecoverable error\nand the system needs to reboot\nSorry!"
        )
        error_button = Button(text="Reboot", on_press=lambda x: self.app.reboot())
        error_layout.add_widget(error_text)
        error_layout.add_widget(error_button)
        error_popup = Popup(
            title="Uh-Oh",
            auto_dismiss=False,
            size_hint=(0.4, 0.4),
            content=error_layout,
        )
        error_popup.open()

    def open_inventory_item_popup(self, barcode=None):

        self.app.current_context = "inventory_item"

        content = BoxLayout(orientation="vertical", padding=10)
        name_layout = BoxLayout(orientation="horizontal", size_hint_y=0.4)
        name_input = TextInput(text=self.app.inventory_manager.name)
        name_layout.add_widget(Label(text="Name", size_hint_x=0.2))
        name_layout.add_widget(name_input)

        barcode_layout = BoxLayout(orientation="horizontal", size_hint_y=0.4)
        self.barcode_input = TextInput(
            input_filter="int", text=barcode if barcode else ""
        )
        barcode_layout.add_widget(Label(text="Barcode", size_hint_x=0.2))
        barcode_layout.add_widget(self.barcode_input)

        price_layout = BoxLayout(orientation="horizontal", size_hint_y=0.4)
        price_input = TextInput(
            text=self.app.inventory_manager.price, input_filter="float"
        )
        price_layout.add_widget(Label(text="Price", size_hint_x=0.2))
        price_layout.add_widget(price_input)

        cost_layout = BoxLayout(orientation="horizontal", size_hint_y=0.4)
        cost_input = TextInput(
            text=self.app.inventory_manager.cost, input_filter="float"
        )
        cost_layout.add_widget(Label(text="Cost", size_hint_x=0.2))
        cost_layout.add_widget(cost_input)

        sku_layout = BoxLayout(orientation="horizontal", size_hint_y=0.4)
        sku_input = TextInput(text=self.app.inventory_manager.sku)
        sku_layout.add_widget(Label(text="SKU", size_hint_x=0.2))

        sku_layout.add_widget(sku_input)

        category_layout = BoxLayout(orientation="horizontal", size_hint_y=0.4)
        self.add_to_db_category_input_inv = TextInput(
            text=self.app.inventory_manager.category, disabled=True
        )
        category_layout.add_widget(Label(text="Category", size_hint_x=0.2))

        category_layout.add_widget(self.add_to_db_category_input_inv)

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
                on_press=lambda x: self.app.utilities.inventory_item_confirm_and_close(
                    self.barcode_input,
                    name_input,
                    price_input,
                    cost_input,
                    sku_input,
                    self.add_to_db_category_input_inv,
                    self.inventory_item_popup,
                ),
            )
        )
        button_layout.add_widget(
            MDRaisedButton(
                text="Generate Barcode",
                on_press=lambda *args: self.app.utilities.set_generated_barcode(
                    self.barcode_input
                ),
            )
        )
        button_layout.add_widget(
            MDRaisedButton(
                text="Categories",
                on_press=lambda *args: self.open_category_button_popup_inv(),
            )
        )
        button_layout.add_widget(
            MDRaisedButton(
                text="Cancel",
                on_press=lambda *args: self.inventory_item_popup.dismiss(),
            )
        )

        content.add_widget(button_layout)

        self.inventory_item_popup = Popup(
            title="Item details",
            pos_hint={"top": 1},
            content=content,
            size_hint=(0.8, 0.4),
        )

        self.inventory_item_popup.bind(
            on_dismiss=lambda x: self.on_inventory_item_dismiss(x)
        )
        self.app.inventory_manager.refresh_inventory()
        self.inventory_item_popup.open()

    def on_inventory_item_dismiss(self, instance):
        self.app.inventory_manager.reset_inventory_context()
        # self.app.inventory_manager.detach_from_parent()


    def handle_duplicate_barcodes(self, barcode):
        items = self.app.db_manager.handle_duplicate_barcodes(barcode)
        layout = GridLayout(rows=10,cols=1)
        for item in items:
            button = MDRaisedButton(text=item['name'])
            layout.add_widget(button)
        self.handle_duplicate_barcodes_popup = Popup(
            title="Duplicate Barcode Detected!",
            content=layout,
            size_hint=(0.4,0.4),
            on_press=lambda x, barcode=barcode: self.add_dupe_choice_to_order(barcode=barcode)
            )
        self.handle_duplicate_barcodes_popup.open()

    def add_dupe_choice_to_order(self, barcode):
        item_details = self.app.db_manager.get_item_details(barcode)
        if item_details:
            print("found item details", item_details)
            item_name, item_price = item_details[:2]
            self.app.order_manager.add_item(item_name, item_price)
            self.handle_duplicate_barcodes_popup.dismiss()
            self.app.utilities.update_display()
            self.app.utilities.update_financial_summary()


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
            pos_hint={"center_x": 0.5, "center_y": 1},
            size_hint=(1, 0.15),
            on_press=lambda x: self.app.popup_manager.add_order_discount_popup(),
        )
        clear_order_button = MDRaisedButton(
            text="Clear Order",
            pos_hint={"center_x": 0.5, "center_y": 1 - 0.2},
            size_hint=(1, 0.15),
            on_press=lambda x: self.clear_order(),
        )
        adjust_price_button = MDRaisedButton(
            text="Adjust Payment",
            pos_hint={"center_x": 0.5, "center_y": 1 - 0.4},
            size_hint=(1, 0.15),
            on_press=lambda x: self.adjust_price(),
        )
        save_order_button = MDRaisedButton(
            text="Save Order",
            pos_hint={"center_x": 0.5, "center_y": 1 - 0.6},
            size_hint=(1, 0.15),
            on_press=lambda x: self.save_order(),
        )
        load_order_button = MDRaisedButton(
            text="Load Order",
            pos_hint={"center_x": 0.5, "center_y": 1 - 0.8},
            size_hint=(1, 0.15),
            on_press=lambda x: self.open_list_saved_orders_popup(),
        )
        order_mod_layout.add_widget(save_order_button)
        order_mod_layout.add_widget(load_order_button)
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

    def save_order(self):
        self.app.order_manager.save_order_to_disk()
        self.open_save_order_popup()
        self.app.order_manager.clear_order()
        self.order_mod_popup.dismiss()
        self.app.utilities.update_display()
        self.app.utilities.update_financial_summary()

    def open_list_saved_orders_popup(self):
        content_layout=GridLayout(orientation="lr-tb", cols=3, rows=10)
        orders = self.app.order_manager.list_all_saved_orders()
        for order in orders:
            order_str = ""
            for item in order["items"]:
                order_str.join(item)
            items = str(order["items"])
            order_id = str(order["order_id"])
            entry = MDLabel(text=f"{order_id}\n{items}", size_hint_y=0.1)
            button = Button(text="Open", size_hint_y=0.1, on_press=lambda x, order=order:self.load_order(order=order))
            del_button = Button(text="Delete", size_hint_y=0.1, on_press=lambda x, order=order:self.delete_order(order=order))
            content_layout.add_widget(entry)
            content_layout.add_widget(button)
            content_layout.add_widget(del_button)
        self.list_saved_orders_popup = Popup(content=content_layout, size_hint=(0.8,0.4))
        self.list_saved_orders_popup.open()

    def delete_order(self, order):
        self.app.order_manager.delete_order_from_disk(order)
        self.list_saved_orders_popup.dismiss()
        self.open_list_saved_orders_popup()

    def load_order(self, order):
        self.app.order_manager.load_order_from_disk(order)
        self.list_saved_orders_popup.dismiss()
        self.app.financial_summary.order_mod_popup.dismiss()

    def open_save_order_popup(self):
        layout = GridLayout(orientation="tb-lr", rows=1, cols=1)
        label = Label(text="Saved!", size_hint=(1, 0.5))
        #button = MDRaisedButton(text="Dismiss", size_hint=(1, 0.5), on_press=lambda x: self.save_order_popup.dismiss())
        layout.add_widget(label)
        #layout.add_widget(button)
        self.save_order_popup = Popup(size_hint=(0.2, 0.2),
                                      content=layout,
                                      title="",
                                        background="images/transparent.png",
                                        background_color=(0, 0, 0, 0),
                                        separator_height=0,)
        self.save_order_popup.open()

        Clock.schedule_once(lambda dt: self.save_order_popup.dismiss(), 1)


    def adjust_price(self):
        self.app.popup_manager.show_adjust_price_popup()
        self.order_mod_popup.dismiss()


class Calculator:
    def __init__(self):
        self.operators = ["+", "-", "*", "/"]
        self.last_was_operator = None
        self.last_button = None
        self.calculation = ""

    def create_calculator_layout(self):
        main_layout = MDGridLayout(cols=1, rows=3, spacing=5, size_hint=(1, 1))
        text_layout = MDBoxLayout(orientation="horizontal", size_hint_y=0.1)
        self.solution = MDTextField(
            multiline=False,
            readonly=True,
            halign="right",
            font_size=30,
            mode="rectangle",
        )
        text_layout.add_widget(self.solution)
        main_layout.add_widget(text_layout)

        number_layout = MDGridLayout(cols=3, spacing=5, rows=4, size_hint=(1, 1))

        buttons = [
            "1",
            "2",
            "3",
            "4",
            "5",
            "6",
            "7",
            "8",
            "9",
            ".",
            "0",
            "C",
        ]

        for button in buttons:
            number_layout.add_widget(
                MDRaisedButton(
                    text=button,
                    font_style="H6",
                    size_hint=(1, 1),
                    on_press=self.on_button_press,
                )
            )
        main_layout.add_widget(number_layout)

        operation_button_layout = MDGridLayout(
            cols=5, spacing=5, rows=1, size_hint=(1, 0.2)
        )
        operation_buttons = ["+", "-", "*", "/", "="]
        for op_button in operation_buttons:
            if op_button == "=":

                operation_button_layout.add_widget(
                    MDRaisedButton(
                        text=op_button,
                        md_bg_color=get_color_from_hex("#4CAF50"),
                        size_hint=(1, 1),
                        font_style="H6",
                        on_press=self.on_solution,
                    )
                )
            else:

                operation_button_layout.add_widget(
                    MDRaisedButton(
                        text=op_button,
                        md_bg_color=get_color_from_hex("#2196F3"),
                        size_hint=(1, 1),
                        font_style="H6",
                        on_press=self.on_button_press,
                    )
                )
        main_layout.add_widget(operation_button_layout)

        return main_layout

    def on_button_press(self, instance):
        current = self.solution.text
        button_text = instance.text

        if button_text == "C":
            self.solution.text = ""
        else:
            if current and (self.last_was_operator and button_text in self.operators):
                return
            elif current == "" and button_text in self.operators:
                return
            else:
                new_text = current + button_text
                self.solution.text = new_text

        self.last_was_operator = button_text in self.operators
        self.last_button = button_text

    def on_solution(self, instance):
        text = self.solution.text
        if text:
            try:
                self.solution.text = str(eval(self.solution.text))
            except Exception:
                self.solution.text = "Error"

    def show_calculator_popup(self):
        calculator_layout = self.create_calculator_layout()
        calculator_popup = Popup(
            content=calculator_layout,
            size_hint=(0.4, 0.8),
            title="",
            background="images/transparent.png",
            background_color=(0, 0, 0, 0),
            separator_height=0,
        )
        calculator_popup.open()


class TouchableMDBoxLayout(BoxLayout):
    def __init__(self, checkbox, **kwargs):
        super(TouchableMDBoxLayout, self).__init__(**kwargs)
        self.checkbox = checkbox

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            self.checkbox.active = not self.checkbox.active
            return True
        return super(TouchableMDBoxLayout, self).on_touch_down(touch)
