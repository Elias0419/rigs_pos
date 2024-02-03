from kivy.app import App

from kivy.clock import Clock
from kivymd.uix.boxlayout import BoxLayout
from kivy.uix.popup import Popup
from kivy.uix.label import Label
from kivy.properties import StringProperty, ListProperty, ObjectProperty
from database_manager import DatabaseManager
from order_manager import OrderManager
from kivy.uix.textinput import TextInput
from kivymd.uix.button import MDFlatButton, MDRaisedButton
from barcode.upc import UniversalProductCodeA as upc_a
import random


class InventoryManagementView(BoxLayout):
    barcode = StringProperty()
    name = StringProperty()
    price = StringProperty()
    cost = StringProperty()
    sku = StringProperty()
    category= StringProperty()
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(InventoryManagementView, cls).__new__(
                cls, *args, **kwargs
            )
        return cls._instance

    def __init__(self, **kwargs):
        if not hasattr(self, "_init"):
            super(InventoryManagementView, self).__init__(**kwargs)
            self.full_inventory = []
            self.database_manager = DatabaseManager("inventory.db")
            self._init = True

    def detach_from_parent(self):
        if self.parent:
            self.parent.remove_widget(self)

    def update_search_input(self, barcode):
        self.ids.inv_search_input.text = barcode

    def handle_scanned_barcode(self, barcode):
        barcode = barcode.strip()
        items = self.database_manager.get_all_items()
        if any(item[0] == barcode for item in items):
            Clock.schedule_once(lambda dt: self.update_search_input(barcode), 0.1)
        else:
            self.show_add_item_popup(barcode)


    def generate_unique_barcode(self):
        while True:
            new_barcode = str(
                upc_a(
                    str(random.randint(100000000000, 999999999999)), writer=None
                ).get_fullcode()
            )

            if not self.database_manager.barcode_exists(new_barcode):
                return new_barcode

    def show_add_item_popup(self, scanned_barcode):
        self.barcode = scanned_barcode
        self.inventory_item_popup()

    def show_inventory_for_manager(self, inventory_items):
        self.full_inventory = inventory_items
        self.rv.data = self.generate_data_for_rv(inventory_items)

    def refresh_inventory(self):
        updated_inventory = self.database_manager.get_all_items()
        self.show_inventory_for_manager(updated_inventory)

    def add_item_to_database(
        self,
        barcode_input,
        name_input,
        price_input,
        cost_input,
        sku_input,
        category_input,
    ):
        if barcode_input and name_input and price_input:
            try:
                self.database_manager.add_item(
                    barcode_input.text,
                    name_input.text,
                    price_input.text,
                    cost_input.text,
                    sku_input.text,
                    category_input.text,
                )
            except Exception as e:
                print(e)

    def inventory_item_popup(self, barcode=None):
        content = BoxLayout(orientation="vertical", padding=10)
        name_layout = BoxLayout(orientation="horizontal", size_hint_y=0.4)
        name_input = TextInput(text=self.name)
        name_layout.add_widget(Label(text="Name", size_hint_x=0.2))
        name_layout.add_widget(name_input)

        barcode_layout = BoxLayout(orientation="horizontal", size_hint_y=0.4)
        barcode_input = TextInput(
            input_filter="int", text=self.barcode if self.barcode else ""
        )
        barcode_layout.add_widget(Label(text="Barcode", size_hint_x=0.2))
        barcode_layout.add_widget(barcode_input)

        price_layout = BoxLayout(orientation="horizontal", size_hint_y=0.4)
        price_input = TextInput(text=self.price, input_filter="float")
        price_layout.add_widget(Label(text="Price", size_hint_x=0.2))
        price_layout.add_widget(price_input)

        cost_layout = BoxLayout(orientation="horizontal", size_hint_y=0.4)
        cost_input = TextInput(text=self.cost, input_filter="float")
        cost_layout.add_widget(Label(text="Cost", size_hint_x=0.2))
        cost_layout.add_widget(cost_input)

        sku_layout = BoxLayout(orientation="horizontal", size_hint_y=0.4)
        sku_input = TextInput(text=self.sku)
        sku_layout.add_widget(Label(text="SKU", size_hint_x=0.2))

        sku_layout.add_widget(sku_input)

        category_layout = BoxLayout(orientation="horizontal", size_hint_y=0.4)
        category_input = TextInput(text=self.category)
        category_layout.add_widget(Label(text="SKU", size_hint_x=0.2))

        category_layout.add_widget(sku_layout)

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
                    barcode_input, name_input, price_input, cost_input, sku_input, category_input, popup
                ),
            )
        )

        button_layout.add_widget(
            MDRaisedButton(text="Cancel", on_press=lambda *args: popup.dismiss())
        )
        button_layout.add_widget(
            MDRaisedButton(
                text="Generate Barcode",
                on_press=lambda *args: self.set_generated_barcode(barcode_input),
            )
        )

        content.add_widget(button_layout)

        popup = Popup(
            title="Item details",
            pos_hint={"top": 1},
            content=content,
            size_hint=(0.8, 0.4),
        )
        popup.open()

    def confirm_and_close(
        self,
        barcode_input,
        name_input,
        price_input,
        cost_input,
        sku_input,
        category_input,
        popup,
    ):
        self.add_item_to_database(
            barcode_input,
            name_input,
            price_input,
            cost_input,
            sku_input,
            category_input,
        )
        self.refresh_inventory()
        popup.dismiss()

    def clear_search(self):
        self.ids.inv_search_input.text = ""

    def set_generated_barcode(self, barcode_input):
        unique_barcode = self.generate_unique_barcode()
        barcode_input.text = unique_barcode

    def open_inventory_manager(self):
        self.inventory_item_popup()

    def generate_data_for_rv(self, items):
        data = [
            {
                "barcode": str(item[0]),
                "name": item[1],
                "price": str(item[2]),
                "cost": str(item[3]),
                "sku": str(item[4]),
            }
            for item in items
        ]

        return data

    def filter_inventory(self, query):
        if query:
            query = query.lower()
            filtered_items = []
            for item in self.full_inventory:
                barcode = str(item[0]).lower()
                name = item[1].lower()
                if query == barcode or query in name:
                    filtered_items.append(item)

        else:
            filtered_items = self.full_inventory

        self.rv.data = self.generate_data_for_rv(filtered_items)


class InventoryManagementRow(BoxLayout):
    barcode = StringProperty()
    name = StringProperty()
    price = StringProperty()
    cost = StringProperty()
    sku = StringProperty()
    category = StringProperty()

    def __init__(self, **kwargs):
        super(InventoryManagementRow, self).__init__(**kwargs)
        self.database_manager = DatabaseManager("inventory.db")
        self.inventory_management_view = InventoryManagementView()

    def inventory_item_popup(self):
        content = BoxLayout(orientation="vertical", padding=10)
        name_layout = BoxLayout(orientation="horizontal", size_hint_y=0.4)
        name_input = TextInput(text=self.name)
        name_layout.add_widget(Label(text="Name", size_hint_x=0.2))
        name_layout.add_widget(name_input)
        barcode_layout = BoxLayout(orientation="horizontal", size_hint_y=0.4)
        barcode_input = TextInput(
            input_filter="int", text=self.barcode if self.barcode else ""
        )
        barcode_layout.add_widget(Label(text="Barcode", size_hint_x=0.2))
        barcode_layout.add_widget(barcode_input)

        price_layout = BoxLayout(orientation="horizontal", size_hint_y=0.4)
        price_input = TextInput(input_filter="float", text=self.price)
        price_layout.add_widget(Label(text="Price", size_hint_x=0.2))
        price_layout.add_widget(price_input)

        cost_layout = BoxLayout(orientation="horizontal", size_hint_y=0.4)
        cost_input = TextInput(text=self.cost, input_filter="float")
        cost_layout.add_widget(Label(text="Cost", size_hint_x=0.2))
        cost_layout.add_widget(cost_input)

        sku_layout = BoxLayout(orientation="horizontal", size_hint_y=0.4)
        sku_input = TextInput(text=self.sku)
        sku_layout.add_widget(Label(text="SKU", size_hint_x=0.2))
        sku_layout.add_widget(sku_input)

        category_layout = BoxLayout(orientation="horizontal", size_hint_y=0.4)
        category_input = TextInput(text=self.category, disabled=True)
        category_layout.add_widget(Label(text="Categories", size_hint_x=0.2))
        category_layout.add_widget(category_input)

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
                on_press=lambda _: self.confirm_and_close(
                    barcode_input,
                    name_input,
                    price_input,
                    cost_input,
                    sku_input,
                    category_input,
                    popup,
                ),
            )
        )

        button_layout.add_widget(
            MDRaisedButton(text="Close", on_press=lambda *args: popup.dismiss())
        )

        content.add_widget(button_layout)

        popup = Popup(
            title="Item details",
            pos_hint={"top": 1},
            content=content,
            size_hint=(0.8, 0.4),
        )
        popup.open()

    def confirm_and_close(
        self, barcode_input, name_input, price_input, cost_input, sku_input, category_input, popup
    ):
        self.update_item_in_database(
            barcode_input, name_input, price_input, cost_input, sku_input, category_input
        )
        self.inventory_management_view.refresh_inventory()
        popup.dismiss()

    def open_inventory_manager(self):
        self.inventory_item_popup()

    def update_item_in_database(
        self, barcode_input, name_input, price_input, cost_input, sku_input, category_input
    ):
        if barcode_input and name_input and price_input:
            try:
                self.database_manager.update_item(
                    barcode_input.text,
                    name_input.text,
                    price_input.text,
                    cost_input.text,
                    sku_input.text,
                    category_input.text
                )
            except Exception as e:
                print(e)


class InventoryRow(BoxLayout):
    barcode = StringProperty()
    name = StringProperty()
    price = StringProperty()
    order_manager = ObjectProperty()

    def __init__(self, **kwargs):
        super(InventoryRow, self).__init__(**kwargs)
        self.order_manager = OrderManager()

    def add_to_order(self):
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
                item
                for item in self.full_inventory
                if query in str(item[0]).lower() or query in item[1].lower()
            ]
        else:
            filtered_items = self.full_inventory

        self.rv.data = self.generate_data_for_rv(filtered_items)
