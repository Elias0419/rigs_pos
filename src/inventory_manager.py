from kivy.app import App
from kivy.clock import Clock
from kivy.metrics import dp
from kivy.properties import StringProperty, ObjectProperty, BooleanProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.recycleview import RecycleView
from kivy.uix.recycleboxlayout import RecycleBoxLayout
from kivy.uix.recycleview.views import RecycleDataViewBehavior
from kivy.graphics import Color, Line
from kivy.factory import Factory

from kivymd.uix.button import MDRaisedButton, MDFlatButton


from database_manager import DatabaseManager
import logging

logger = logging.getLogger("rigs_pos")


class MarkupLabel(Label):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.markup = True
        self.halign = "left"
        self.bind(size=self._set_text_size)

    def _set_text_size(self, *_):
        self.text_size = self.size


def add_bottom_divider(widget, rgba=(0.5, 0.5, 0.5, 1), width=1):
    with widget.canvas.after:
        Color(*rgba)
        widget._divider = Line(
            points=[widget.x, widget.y, widget.right, widget.y], width=width
        )
    widget.bind(
        pos=lambda *_: _update_divider(widget), size=lambda *_: _update_divider(widget)
    )


def _update_divider(widget):
    if hasattr(widget, "_divider") and widget._divider is not None:
        widget._divider.points = [widget.x, widget.y, widget.right, widget.y]


class InventoryRow(RecycleDataViewBehavior, BoxLayout):
    barcode = StringProperty()
    name = StringProperty()
    price = StringProperty()
    order_manager = ObjectProperty(allownone=True)
    formatted_price = StringProperty()
    formatted_name = StringProperty("")

    def __init__(self, **kwargs):
        super().__init__(orientation="horizontal", spacing=5, padding=5, **kwargs)
        self.app = App.get_running_app()
        self._name_lbl = MarkupLabel()
        self._price_lbl = Label(size_hint_x=0.2)
        self._btn = MDFlatButton(text="Add to Order")
        self._btn.bind(on_release=lambda *_: self.add_to_order())

        self.bind(formatted_name=self._name_lbl.setter("text"))
        self.bind(formatted_price=self._price_lbl.setter("text"))
        self.bind(name=self._on_name)
        self.bind(price=self._on_price)

        self.add_widget(self._name_lbl)
        self.add_widget(self._price_lbl)
        self.add_widget(self._btn)

        add_bottom_divider(self)

    def refresh_view_attrs(self, rv, index, data):
        res = super().refresh_view_attrs(rv, index, data)
        # ensure initial formatting is applied
        self._on_name(self, self.name)
        self._on_price(self, self.price)
        # if the RecycleView passed an order_manager, use it
        if "order_manager" in data and data["order_manager"] is not None:
            self.order_manager = data["order_manager"]
        return res

    def _on_name(self, *_):
        name = self.name or ""
        self.formatted_name = f"[b][size=20]{name}[/size][/b]" if name else "[b][/b]"

    def _on_price(self, *_):
        try:
            self.formatted_price = f"{float(self.price):.2f}"
        except Exception:
            self.formatted_price = "Invalid"

    def add_to_order(self):
        item_details = self.app.db_manager.get_item_details(barcode=self.barcode)
        item_id = item_details.get("item_id")
        barcode = item_details.get("barcode")
        is_custom = False
        try:
            price_float = float(self.price)
        except (TypeError, ValueError) as e:
            logger.error(f"[Inventory Manager] add_to_order failed to convert price to float for some reason\n{e}")
            return

        om = self.order_manager or self.app.order_manager
        om.add_item(self.name, price_float, item_id=item_id, barcode=barcode, is_custom=is_custom)
        self.app.utilities.update_display()
        self.app.utilities.update_financial_summary()
        self.app.popup_manager.inventory_popup.dismiss()


class InventoryManagementRow(RecycleDataViewBehavior, BoxLayout):
    barcode = StringProperty()
    name = StringProperty()
    price = StringProperty()
    cost = StringProperty()
    sku = StringProperty()
    category = StringProperty()
    formatted_price = StringProperty()
    is_rolling_papers = BooleanProperty(False)
    papers_per_pack = StringProperty("")

    def __init__(self, **kwargs):
        super().__init__(orientation="horizontal", spacing=5, padding=5, **kwargs)
        self.app = App.get_running_app()

        grid = GridLayout(cols=3, size_hint_x=0.9)

        self._name_lbl = Label(halign="left")
        self._name_lbl.bind(
            size=lambda *_: setattr(self._name_lbl, "text_size", self._name_lbl.size)
        )
        self._barcode_lbl = Label(halign="left", size_hint_x=0.2)
        self._price_lbl = Label(halign="left", size_hint_x=0.2)

        grid.add_widget(self._name_lbl)
        grid.add_widget(self._barcode_lbl)
        grid.add_widget(self._price_lbl)

        details_btn = MDRaisedButton(text="Details", size_hint_x=0.1)
        details_btn.bind(
            on_release=lambda *_: self.app.utilities.open_inventory_manager_row(self)
        )

        self.add_widget(grid)
        self.add_widget(details_btn)

        # bind labels to props
        self.bind(name=self._name_lbl.setter("text"))
        self.bind(barcode=self._barcode_lbl.setter("text"))
        self.bind(price=self._on_price)

        add_bottom_divider(self)

    def refresh_view_attrs(self, rv, index, data):
        res = super().refresh_view_attrs(rv, index, data)
        self._on_price(self, self.price)
        if data:
            self.is_rolling_papers = bool(data.get("is_rolling_papers", False))
            self.papers_per_pack = str(data.get("papers_per_pack", "") or "")
        return res

    def _on_price(self, *_):
        try:
            self.formatted_price = f"{float(self.price):.2f}"
            self._price_lbl.text = self.formatted_price
        except Exception:
            self.formatted_price = "Invalid"
            self._price_lbl.text = "Invalid"

    def update_item_in_database(
        self,
        barcode,
        name,
        price,
        cost,
        sku,
        category,
        is_rolling_papers,
        papers_per_pack,
    ):
        barcode = (barcode or "").strip()
        if not barcode:
            logger.warning(
                "[InventoryManagementRow] Cannot update item without barcode"
            )
            return False

        item_details = self.app.db_manager.get_item_details(barcode=barcode)
        if not item_details:
            logger.warning(
                "[InventoryManagementRow] No matching item found for barcode %s",
                barcode,
            )
            return False

        try:
            price_value = float(price) if price not in (None, "") else 0.0
        except ValueError:
            logger.warning(
                "[InventoryManagementRow] Invalid price '%s' provided for barcode %s",
                price,
                barcode,
            )
            return False

        try:
            cost_value = float(cost) if cost not in (None, "") else 0.0
        except ValueError:
            logger.warning(
                "[InventoryManagementRow] Invalid cost '%s' provided for barcode %s",
                cost,
                barcode,
            )
            return False

        papers_per_pack_value = None
        if papers_per_pack not in (None, ""):
            try:
                papers_per_pack_value = int(papers_per_pack)
            except ValueError:
                logger.warning(
                    "[InventoryManagementRow] Invalid papers_per_pack '%s' provided for barcode %s",
                    papers_per_pack,
                    barcode,
                )
                return False

        success = self.app.db_manager.update_item(
            item_details["item_id"],
            barcode,
            name,
            price_value,
            cost_value,
            sku,
            category,
            taxable=item_details.get("taxable", True),
            is_rolling_papers=bool(is_rolling_papers),
            papers_per_pack=papers_per_pack_value,
        )

        if success:
            self.barcode = barcode
            self.name = name
            self.price = str(price_value)
            self.cost = str(cost_value)
            self.sku = sku or ""
            self.category = category or ""
            self.is_rolling_papers = bool(is_rolling_papers)
            self.papers_per_pack = (
                str(papers_per_pack_value) if papers_per_pack_value is not None else ""
            )

        return success


Factory.register("InventoryRow", cls=InventoryRow)
Factory.register("InventoryManagementRow", cls=InventoryManagementRow)
Factory.register("MarkupLabel", cls=MarkupLabel)


class InventoryView(BoxLayout):
    def __init__(self, order_manager, **kwargs):
        super().__init__(orientation="vertical", spacing=5, padding=10, **kwargs)
        self.order_manager = order_manager
        self.full_inventory = []

        # Top search bar
        top = BoxLayout(size_hint_y=None, height=dp(32), spacing=5)
        self.search_input = TextInput(hint_text="Search", multiline=False)
        self.search_input.bind(text=self.filter_inventory)
        top.add_widget(self.search_input)
        self.add_widget(top)

        # RecycleView
        self.rv = RecycleView()

        layout = RecycleBoxLayout(
            default_size=(None, dp(48)),
            default_size_hint=(1, None),
            size_hint_y=None,
            orientation="vertical",
        )
        layout.bind(minimum_height=layout.setter("height"))
        self.rv.add_widget(layout)

        self.rv.viewclass = InventoryRow
        self.add_widget(self.rv)

    def show_inventory(self, inventory_items):
        self.full_inventory = inventory_items
        data = self._generate_data(self.full_inventory)
        # attach order_manager for row-level use
        for d in data:
            d["order_manager"] = self.order_manager
        self.rv.data = data

    def _generate_data(self, items):
        # items: [(barcode, name, price, ...)]
        return [
            {"barcode": str(item[0]), "name": item[1], "price": str(item[2])}
            for item in items
        ]

    def filter_inventory(self, _, text):
        query = (text or "").lower().strip()
        if not query:
            return
        filtered = [it for it in self.full_inventory if query in it[1].lower()]
        self.rv.data = self._generate_data(filtered)


class InventoryManagementView(BoxLayout):
    barcode = StringProperty()
    name = StringProperty()
    price = StringProperty()
    cost = StringProperty()
    sku = StringProperty()
    category = StringProperty()
    is_rolling_papers = BooleanProperty(False)
    papers_per_pack = StringProperty("")

    def __init__(self, **kwargs):
        super().__init__(orientation="vertical", **kwargs)

        self.app = App.get_running_app()
        self.database_manager = DatabaseManager("db/inventory.db", None)
        self.full_inventory = self.database_manager.get_all_items()

        # Top controls
        bar = BoxLayout(size_hint_y=None, height=dp(48), spacing=5)
        self.inv_search_input = TextInput(
            hint_text="Search", multiline=False, size_hint_x=0.8
        )
        self.inv_search_input.bind(text=self._on_search_text)

        clear_btn = MDRaisedButton(text="Clear", size_hint=(0.2, 1))
        clear_btn.bind(on_release=lambda *_: self.clear_search())

        add_btn = MDRaisedButton(text="Add Item", size_hint=(0.2, 1))
        add_btn.bind(on_release=lambda *_: self.open_inventory_manager())

        bar.add_widget(self.inv_search_input)
        bar.add_widget(clear_btn)
        bar.add_widget(add_btn)
        self.add_widget(bar)

        # RecycleView
        self.rv = RecycleView()

        layout = RecycleBoxLayout(
            default_size=(None, dp(48)),
            default_size_hint=(1, None),
            size_hint_y=None,
            orientation="vertical",
        )
        layout.bind(minimum_height=layout.setter("height"))
        self.rv.add_widget(layout)

        self.rv.viewclass = InventoryManagementRow
        self.add_widget(self.rv)

        # first render
        Clock.schedule_once(lambda dt: self.filter_inventory(None), 0.1)

    def detach_from_parent(self):
        if self.parent:
            self.parent.remove_widget(self)

    def update_search_input(self, barcode):
        self.inv_search_input.text = barcode

    def handle_scanned_barcode(self, barcode):
        barcode = barcode.strip()
        items = self.database_manager.get_all_items()
        if any(item[0] == barcode for item in items):
            Clock.schedule_once(lambda dt: self.update_search_input(barcode), 0.1)
            return
        for item in items:
            if (
                item[0][1:] == barcode
                or item[0] == barcode[:-4]
                or item[0][1:] == barcode[:-4]
            ):
                Clock.schedule_once(lambda dt: self.update_search_input(item[0]), 0.1)
                return
        self.app.popup_manager.open_inventory_item_popup(barcode)

    def handle_scanned_barcode_item(self, barcode):
        barcode = barcode.strip()
        try:
            self.app.popup_manager.barcode_input.text = barcode
        except AttributeError as e:
            logger.warning(f"inventory_manager:handle_scanned_barcode_item\n{e}")

    def show_inventory_for_manager(self, inventory_items):
        self.full_inventory = inventory_items

    def refresh_inventory(self, query=None):
        query = self.inv_search_input.text
        updated_inventory = self.database_manager.get_all_items()
        self.show_inventory_for_manager(updated_inventory)
        Clock.schedule_once(
            lambda dt: self.filter_inventory(query if query else None), 0.1
        )

    def add_item_to_database(
        self,
        barcode_input,
        name_input,
        price_input,
        cost_input,
        sku_input,
        category_input,
        is_rolling_papers=False,
        papers_per_pack=None,
    ):
        try:
            int(barcode_input.text)
        except ValueError:
            logger.warning("[Inventory Manager] add_item_to_database no barcode")
            self.app.popup_manager.catch_label_printer_missing_barcode()
            return
        papers_per_pack_value = None
        if papers_per_pack not in (None, ""):
            try:
                papers_per_pack_value = int(papers_per_pack)
            except ValueError:
                logger.warning(
                    "[Inventory Manager] Invalid papers_per_pack '%s' provided",
                    papers_per_pack,
                )
                self.app.popup_manager.show_missing_papers_count_warning()
                return
        if name_input:
            try:
                self.database_manager.add_item(
                    barcode_input.text,
                    name_input.text,
                    price_input.text,
                    cost_input.text,
                    sku_input.text,
                    category_input.text,
                    is_rolling_papers=is_rolling_papers,
                    papers_per_pack=papers_per_pack_value,
                )
                self.papers_per_pack = (
                    str(papers_per_pack_value)
                    if papers_per_pack_value is not None
                    else ""
                )
                self.app.utilities.update_inventory_cache()
                self.refresh_label_inventory_for_dual_pane_mode()
            except Exception as e:
                logger.warning(e)

    def refresh_label_inventory_for_dual_pane_mode(self):
        try:
            self.app.popup_manager.view_container.remove_widget(
                self.app.popup_manager.label_printing_view
            )
            inventory = self.app.inventory_cache
            self.app.popup_manager.label_printing_view.show_inventory_for_label_printing(
                inventory
            )
            self.app.popup_manager.view_container.add_widget(
                self.app.popup_manager.label_printing_view
            )
        except AttributeError as e:
            logger.info(
                f"[Inventory Manager] refresh_label_inventory_for_dual_pane_mode expected error when not in dual pane mode\n{e}"
            )
        except Exception as e:
            logger.error(f"[Inventory Manager] refresh_label_inventory_for_dual_pane_mode unexpected error\n{e}")

    def reset_inventory_context(self):
        self.app.current_context = "inventory"

    def clear_search(self):
        self.inv_search_input.text = ""

    def set_generated_barcode(self, barcode_input):
        unique_barcode = self.generate_unique_barcode()
        barcode_input.text = unique_barcode

    def open_inventory_manager(self):
        self.app.popup_manager.open_inventory_item_popup()

    def _generate_data_for_rv(self, items):
        return [
            {
                "barcode": str(item[0]),
                "name": item[1],
                "price": str(item[2]),
                "cost": str(item[3]),
                "sku": str(item[4]),
                "category": str(item[5]),
                "is_rolling_papers": bool(item[9]) if len(item) > 9 else False,
                "papers_per_pack": (
                    str(item[10]) if len(item) > 10 and item[10] is not None else ""
                ),
            }
            for item in items
        ]

    def filter_inventory(self, query):
        if query:
            query = query.lower()
            filtered = []
            for item in self.full_inventory:
                barcode = str(item[0]).lower()
                name = (item[1] or "").lower()
                if query == barcode or query in name:
                    filtered.append(item)
        else:
            filtered = self.full_inventory
        self.rv.data = self._generate_data_for_rv(filtered)

    def _on_search_text(self, _, text):
        self.filter_inventory(text)
