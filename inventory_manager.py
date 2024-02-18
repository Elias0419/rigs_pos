from kivy.app import App

from kivy.clock import Clock
from kivymd.uix.boxlayout import BoxLayout
from kivymd.uix.gridlayout import GridLayout
#
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
            self.database_manager = DatabaseManager("inventory.db",self)
            self.app = App.get_running_app()
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

    def handle_scanned_barcode_item(self,barcode):
        barcode = barcode.strip()
        self.app.popup_manager.barcode_input.text = barcode



    def show_inventory_for_manager(self, inventory_items):
        self.full_inventory = inventory_items

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
        if name_input:
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



    def reset_inventory_context(self):

        self.app.current_context = "inventory"



    def clear_search(self):
        self.ids.inv_search_input.text = ""

    def set_generated_barcode(self, barcode_input):
        unique_barcode = self.generate_unique_barcode()
        self.barcode_input.text = unique_barcode

    def open_inventory_manager(self):

        self.app.popup_manager.inventory_item_popup()

    def generate_data_for_rv(self, items):
        data = [
            {
                "barcode": str(item[0]),
                "name": item[1],
                "price": str(item[2]),
                "cost": str(item[3]),
                "sku": str(item[4]),
                "category": str(item[5])
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
    formatted_price = StringProperty()



    def __init__(self, **kwargs):
        super(InventoryManagementRow, self).__init__(**kwargs)
        self.bind(price=self.update_formatted_price)
        self.database_manager = DatabaseManager("inventory.db", self)
        self.inventory_management_view = InventoryManagementView()
        self.app = App.get_running_app()

    def update_formatted_price(self, instance, value):
        try:
            price_float = float(value)
            self.formatted_price = f"{price_float:.2f}"
        except ValueError:
            self.formatted_price = "Invalid"


    def inventory_item_popup_row(self):

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
        self.update_category_input = TextInput(text=self.category, disabled=True)
        category_layout.add_widget(Label(text="Categories", size_hint_x=0.2))
        category_layout.add_widget(self.update_category_input)

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
                on_press=lambda x: self.confirm_and_close(
                    barcode_input,
                    name_input,
                    price_input,
                    cost_input,
                    sku_input,
                    self.update_category_input,
                    popup,
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
            MDRaisedButton(text="Close", on_press=lambda x: popup.dismiss())
        )

        content.add_widget(button_layout)

        popup = Popup(
            title="Item details",
            pos_hint={"top": 1},
            content=content,
            size_hint=(0.8, 0.4),
        )
        popup.open()

    def open_update_category_button_popup(self):
        self.update_selected_categories = []
        category_button_layout = GridLayout(size_hint=(1, 0.8), pos_hint={"top":1},cols=7, spacing=5)
        for category in self.app.categories:
            btn = MDRaisedButton(
                text=category,
                on_release=lambda x, cat=category: self.update_toggle_category_selection(x, cat),
                size_hint=(1,0.8)
                )
            category_button_layout.add_widget(btn)
        category_popup_layout = BoxLayout()
        confirm_button = MDRaisedButton(
            text="Confirm",
            on_release=lambda x: self.update_apply_categories()
            )
        cancel_button = MDRaisedButton(
            text="Cancel",
            on_release=lambda x: self.update_category_button_popup.dismiss()
            )
        category_popup_layout.add_widget(category_button_layout)
        category_popup_layout.add_widget(confirm_button)
        category_popup_layout.add_widget(cancel_button)

        self.update_category_button_popup = Popup(
            content=category_popup_layout,
            size_hint=(0.9,0.9)
            )
        self.update_category_button_popup.open()

    def update_apply_categories(self):
        categories_str = ', '.join(self.update_selected_categories)
        self.update_category_input.text = categories_str
        self.update_category_button_popup.dismiss()

    def update_toggle_category_selection(self, instance, category):
        if category in self.update_selected_categories:
            self.update_selected_categories.remove(category)
            instance.text = category
        else:
            self.update_selected_categories.append(category)
            instance.text = f"{category}\n (Selected)"

    def confirm_and_close(
        self, barcode_input, name_input, price_input, cost_input, sku_input, category_input, popup
    ):
        self.update_item_in_database(
            barcode_input, name_input, price_input, cost_input, sku_input, category_input
        )
        self.inventory_management_view.refresh_inventory()
        popup.dismiss()

    def open_inventory_manager_row(self):

        self.inventory_item_popup_row()

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
    formatted_price = StringProperty()
    formatted_name = StringProperty('')

    def __init__(self, **kwargs):
        super(InventoryRow, self).__init__(**kwargs)
        self.bind(price=self.update_formatted_price)
        self.bind(name=self.update_formatted_name)
        self.order_manager = OrderManager(None)
        self.app = App.get_running_app()

    def update_formatted_name(self, instance, name):
        formatted_name = f"[b]{name}[/b]" if name else "[b][/b]"
        self.formatted_name = formatted_name

    def update_formatted_price(self, instance, value):
        try:
            price_float = float(value)
            self.formatted_price = f"{price_float:.2f}"
        except ValueError:
            self.formatted_price = "Invalid"


    def add_to_order(self):

        try:
            price_float = float(self.price)
        except ValueError as e:
            print(e)
            pass
        self.order_manager.add_item(self.name, price_float)

        self.app.utilities.update_display()
        self.app.utilities.update_financial_summary()
        self.app.popup_manager.inventory_popup.dismiss()

class InventoryView(BoxLayout):
    def __init__(self, order_manager, **kwargs):
        super(InventoryView, self).__init__(**kwargs)
        self.order_manager = order_manager
        self.pos_hint = {"top": 1}

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
            query = query.lower().strip()
            filtered_items = [
                item
                for item in self.full_inventory
                if query in item[1].lower()
            ]
        else:
            filtered_items = self.full_inventory

        self.rv.data = self.generate_data_for_rv(filtered_items)
class MarkupLabel(Label):
    pass
