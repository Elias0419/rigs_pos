from kivy.app import App

from kivy.clock import Clock
from kivy.uix.label import Label
from kivy.properties import StringProperty, ObjectProperty

from kivymd.uix.boxlayout import BoxLayout

from database_manager import DatabaseManager
from order_manager import OrderManager



class InventoryManagementView(BoxLayout):
    barcode = StringProperty()
    name = StringProperty()
    price = StringProperty()
    cost = StringProperty()
    sku = StringProperty()
    category = StringProperty()
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

            self.database_manager = DatabaseManager("inventory.db", None)
            self.full_inventory = self.database_manager.get_all_items()
            Clock.schedule_once(lambda dt: self.filter_inventory(None), 0.1)
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

            found = False
            for item in items:

                if item[0][1:] == barcode:

                    Clock.schedule_once(lambda dt: self.update_search_input(item[0]), 0.1)
                    found = True
                    break

            if not found:

                self.app.popup_manager.open_inventory_item_popup(barcode)

    def handle_scanned_barcode_item(self, barcode):
        barcode = barcode.strip()
        self.app.popup_manager.barcode_input.text = barcode

    def show_inventory_for_manager(self, inventory_items):
        self.full_inventory = inventory_items

    def refresh_inventory(self):

        updated_inventory = self.database_manager.get_all_items()

        self.show_inventory_for_manager(updated_inventory)
        Clock.schedule_once(lambda dt: self.filter_inventory(None), 0.1)

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
        #self.detach_from_parent()
        self.app.popup_manager.open_inventory_item_popup()

    def generate_data_for_rv(self, items):
        data = [
            {
                "barcode": str(item[0]),
                "name": item[1],
                "price": str(item[2]),
                "cost": str(item[3]),
                "sku": str(item[4]),
                "category": str(item[5]),
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

    def get_item_uuid(self, name_input, price_input):

        item_details = self.database_manager.get_item_details(name=name_input, price=price_input)
        if item_details:
            return item_details['item_id']
        else:
            return None

    def update_item_in_database(
            self,
            barcode_input,
            name_input,
            price_input,
            cost_input,
            sku_input,
            category_input,
        ):
        item_id = self.get_item_uuid(name_input, price_input)
        if item_id:
            try:
                self.database_manager.update_item(
                    item_id,
                    barcode_input,
                    name_input,
                    price_input,
                    cost_input,
                    sku_input,
                    category_input,
                )
            except Exception as e:
                print(e)


class InventoryRow(BoxLayout):
    barcode = StringProperty()
    name = StringProperty()
    price = StringProperty()
    order_manager = ObjectProperty()
    formatted_price = StringProperty()
    formatted_name = StringProperty("")

    def __init__(self, **kwargs):
        super(InventoryRow, self).__init__(**kwargs)
        self.bind(price=self.update_formatted_price)
        self.bind(name=self.update_formatted_name)
        self.order_manager = OrderManager(None)
        self.spacing = 5
        self.padding = 5
        self.app = App.get_running_app()

    def update_formatted_name(self, instance, name):
        formatted_name = f"[b][size=20]{name}[/size][/b]" if name else "[b][/b]"
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

        self.order_manager.add_item(self.name, price_float)

        self.app.utilities.update_display()
        self.app.utilities.update_financial_summary()
        self.app.popup_manager.inventory_popup.dismiss()


class InventoryView(BoxLayout):
    def __init__(self, order_manager, **kwargs):
        super(InventoryView, self).__init__(**kwargs)
        self.order_manager = order_manager
        self.pos_hint = {"top": 1}
        self.spacing = 5
        self.padding = 10
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
                item for item in self.full_inventory if query in item[1].lower()
            ]
        else:
            filtered_items = self.full_inventory

        self.rv.data = self.generate_data_for_rv(filtered_items)


class MarkupLabel(Label):
    pass
