import json
import logging
import threading
import re
from io import BytesIO

import barcode
from barcode.writer import ImageWriter
import brother_ql
from brother_ql.backends.helpers import send
from brother_ql.conversion import convert
from PIL import Image, ImageDraw, ImageFont

from kivy.app import App
from kivy.clock import Clock
from kivy.core.image import Image as CoreImage
from kivy.graphics import Color, Line
from kivy.metrics import dp
from kivy.properties import ObjectProperty, StringProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.gridlayout import GridLayout
from kivy.uix.image import Image as KivyImage
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.recycleboxlayout import RecycleBoxLayout
from kivy.uix.recycleview import RecycleView
from kivy.uix.recycleview.views import RecycleDataViewBehavior
from kivy.uix.tabbedpanel import TabbedPanel, TabbedPanelItem
from kivy.uix.textinput import TextInput

from kivymd.uix.boxlayout import BoxLayout, MDBoxLayout
from kivymd.uix.button import MDFlatButton, MDIconButton, MDRaisedButton
from kivymd.uix.label import MDLabel
from kivymd.uix.recycleview import RecycleView

logger = logging.getLogger("rigs_pos")


PRINTER_MODEL = "QL-710W"
PRINTER_IDENTIFIER = "usb://0x04F9:0x2043"
PRINTER_BACKEND = "pyusb"
CONTINUOUS_LABEL_NAME = "62"  # 64mm / 2.4in continuous tape
CONTINUOUS_LABEL_WIDTH = 696  # 300dpi printable width for 64mm/2.4in stock
STANDARD_LABEL_HEIGHT = 450  # 1.5in at 300dpi
STANDARD_TEXT_CHAR_LIMIT = 50

# Standard label layout knobs.
STANDARD_MARGIN_X = 12
STANDARD_MARGIN_Y = 10
STANDARD_BAND_GAP = 8
STANDARD_COLUMN_GAP = 18
STANDARD_BARCODE_FRACTION = 0.48
STANDARD_TOP_FONT_SIZE = 42
STANDARD_BOTTOM_FONT_SIZE = 42
STANDARD_PRICE_START_FONT_SIZE = 170
STANDARD_PRICE_MIN_FONT_SIZE = 60
STANDARD_BARCODE_MODULE_HEIGHT = 22.0
STANDARD_BARCODE_MODULE_WIDTH = 0.22
STANDARD_BARCODE_QUIET_ZONE = 1.0

# Small-label pair (2-up) layout knobs.
LABEL_MODE_STANDARD = "standard"
LABEL_MODE_SMALL = "small"
SMALL_PAIR_LABEL_HEIGHT = 420
SMALL_PAIR_SIDE_GAP = 16
SMALL_LABEL_MARGIN_X = 10
SMALL_LABEL_MARGIN_Y = 8
SMALL_SECTION_GAP = 6
SMALL_BARCODE_BAND_FRACTION = 0.40
SMALL_PRICE_START_FONT_SIZE = 78
SMALL_PRICE_MIN_FONT_SIZE = 26
SMALL_TEXT_FONT_SIZE = 28
SMALL_TEXT_MIN_FONT_SIZE = 16
SMALL_BARCODE_MODULE_HEIGHT = 16.0


class MarkupLabel(MDLabel):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.markup = True


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


def _left_label(**kw):
    lb = MarkupLabel(halign="left", **kw)
    lb.bind(size=lambda *_: setattr(lb, "text_size", lb.size))
    return lb


class LabelPrintingRow(RecycleDataViewBehavior, BoxLayout):
    barcode = StringProperty()
    name = StringProperty()
    price = StringProperty()
    label_printer = ObjectProperty(allownone=True)

    def __init__(self, **kwargs):
        super().__init__(orientation="horizontal", **kwargs)
        self.size_hint_y = None
        self.height = dp(56)
        self.app = App.get_running_app()

        row = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(56),
            padding=(1, 1, 1, 1),
        )
        self._name_lbl = _left_label(size_hint_x=0.7)
        self._price_lbl = Label(size_hint_x=0.2)
        add_btn = Button(text="Add to Queue", size_hint_x=0.1)
        add_btn.bind(on_release=lambda *_: self.add_to_print_queue())

        self.bind(name=self._name_lbl.setter("text"))
        self.bind(price=self._price_lbl.setter("text"))

        row.add_widget(self._name_lbl)
        row.add_widget(self._price_lbl)
        row.add_widget(add_btn)
        self.add_widget(row)

        add_bottom_divider(self)

    def refresh_view_attrs(self, rv, index, data):
        return super().refresh_view_attrs(rv, index, data)

    def add_to_print_queue(self):
        self.show_label_popup()

    def create_focus_popup(
        self, title, content, textinput, size_hint, pos_hint={}, separator_height=1
    ):
        popup = FocusPopup(
            title=title,
            content=content,
            size_hint=size_hint,
            pos_hint=pos_hint,
            separator_height=separator_height,
        )
        popup.focus_on_textinput(textinput)
        return popup

    def show_label_popup(self):
        content = BoxLayout(orientation="vertical", padding=5, spacing=5)

        quantity_input = TextInput(
            text="1", size_hint=(1, None), height=dp(40), input_filter="int", font_size=20
        )
        content.add_widget(Label(text=f"Enter quantity for {self.name}", size_hint_y=None, height=dp(24)))
        content.add_widget(quantity_input)

        form_layout = MDBoxLayout(orientation="vertical", spacing=5)
        self.price_input = TextInput(
            text=f"{float(self.price):.2f}" if self.price not in ("Not Found", "") else "",
            hint_text="Price (e.g. 9.99)",
            multiline=False,
            size_hint_y=None,
            height=dp(40),
            write_tab=False,
        )
        self.title_input = TextInput(
            text=self.name[:STANDARD_TEXT_CHAR_LIMIT],
            hint_text="Title",
            multiline=False,
            size_hint_y=None,
            height=dp(40),
            write_tab=False,
        )
        self.details_input = TextInput(
            hint_text="Details (optional)",
            multiline=False,
            size_hint_y=None,
            height=dp(40),
            write_tab=False,
        )

        self._bind_length_limit(self.title_input, STANDARD_TEXT_CHAR_LIMIT)
        self._bind_length_limit(self.details_input, STANDARD_TEXT_CHAR_LIMIT)

        form_layout.add_widget(self.price_input)
        form_layout.add_widget(self.title_input)
        form_layout.add_widget(self.details_input)
        content.add_widget(form_layout)

        mode_tabs = TabbedPanel(do_default_tab=False, size_hint=(1, None), height=dp(120))
        default_tab = TabbedPanelItem(text="Default")
        default_tab.add_widget(
            Label(text="Standard 64mm label layout", halign="left", valign="middle")
        )
        small_tab = TabbedPanelItem(text="Small (2-up)")
        small_tab.add_widget(
            Label(text="Two side-by-side labels per strip", halign="left", valign="middle")
        )
        mode_tabs.add_widget(default_tab)
        mode_tabs.add_widget(small_tab)
        mode_tabs.switch_to(default_tab)
        self._selected_label_mode = LABEL_MODE_STANDARD

        def on_tab_switch(_tabs, tab, *_args):
            self._selected_label_mode = (
                LABEL_MODE_SMALL if tab is small_tab else LABEL_MODE_STANDARD
            )

        mode_tabs.bind(current_tab=on_tab_switch)
        content.add_widget(mode_tabs)

        btn_layout = BoxLayout(
            orientation="horizontal", size_hint=(1, None), height=dp(48), spacing=10
        )
        popup = self.create_focus_popup(
            title="",
            content=content,
            textinput=quantity_input,
            size_hint=(0.7, 0.55),
            separator_height=0,
        )

        add_button = MDRaisedButton(
            text="Add",
            size_hint=(0.2, 0.8),
            on_release=lambda *_: self.on_add_button_press(quantity_input, popup),
        )
        btn_layout.add_widget(add_button)
        btn_layout.add_widget(
            MDRaisedButton(
                text="Cancel",
                size_hint=(0.2, 0.8),
                on_release=lambda *_: popup.dismiss(),
            )
        )
        content.add_widget(btn_layout)

        def on_text(_inst, value):
            add_button.disabled = not (value.isdigit() and int(value) > 0)

        quantity_input.bind(text=on_text)

        popup.open()

    def _bind_length_limit(self, text_input: TextInput, limit: int):
        def enforce_length(instance, value):
            if len(value) > limit:
                instance.text = value[:limit]

        text_input.bind(text=enforce_length)

    def refresh_print_queue_for_embed(self):
        Clock.schedule_once(self.refresh_print_queue_for_embed_main_thread, 0.1)

    def refresh_print_queue_for_embed_main_thread(self, *args):
        try:
            self.app.popup_manager.queue_container.remove_widget(
                self.app.popup_manager.print_queue_embed
            )
            self.app.popup_manager.print_queue_embed = (
                self.app.label_manager.show_print_queue(embed=True)
            )
            self.app.popup_manager.queue_container.add_widget(
                self.app.popup_manager.print_queue_embed
            )
        except AttributeError as e:
            logger.info(f"Expected error in refresh_print_queue_for_embed\n{e}")

    def on_add_button_press(self, quantity_input, popup):
        self.add_quantity_to_queue(quantity_input.text)
        self.refresh_print_queue_for_embed()
        popup.dismiss()

    def add_quantity_to_queue(self, quantity):
        if quantity.isdigit() and int(quantity) > 0 and self.label_printer:
            price_text = self.price_input.text.strip()
            if price_text and not price_text.startswith("$"):
                price_text = f"${price_text}"

            content = {
                "title": self.title_input.text.strip() or self.name,
                "details": self.details_input.text.strip(),
            }

            self.label_printer.add_to_queue(
                barcode=self.barcode,
                name=self.name,
                price=price_text or self.price,
                quantity=quantity,
                content=content,
                mode=getattr(self, "_selected_label_mode", LABEL_MODE_STANDARD),
            )


class LabelPrintingView(BoxLayout):
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(LabelPrintingView, cls).__new__(cls, *args, **kwargs)
        return cls._instance

    def __init__(self, ref=None, **kwargs):
        if getattr(self, "_init", False):
            return
        super().__init__(orientation="vertical", **kwargs)
        self._init = True

        self.app = ref or App.get_running_app()
        self.label_printer = getattr(self.app, "label_printer", None)
        if self.label_printer:
            self.label_printer.print_queue_ref = self

        self.full_inventory = []
        self.dual_pane_mode = False
        self.print_queue_popup = None

        self.print_queue_ref = self

        top = BoxLayout(
            size_hint_y=None, height=dp(48), orientation="horizontal", spacing=5
        )
        self.label_search_input = TextInput(
            hint_text="Search", size_hint_x=0.8, multiline=False
        )
        self.label_search_input.bind(text=self._on_search_text)

        clear_btn = MDRaisedButton(text="Clear", size_hint=(0.2, 1))
        clear_btn.bind(on_release=lambda *_: self.clear_search())

        show_btn = MDRaisedButton(text="Show Print Queue", size_hint=(0.2, 1))
        show_btn.bind(on_release=lambda *_: self.show_print_queue())

        top.add_widget(self.label_search_input)
        top.add_widget(clear_btn)
        top.add_widget(show_btn)
        self.add_widget(top)

        self.rv = RecycleView()
        lm = RecycleBoxLayout(
            default_size=(None, dp(56)),
            default_size_hint=(1, None),
            size_hint_y=None,
            orientation="vertical",
        )
        lm.bind(minimum_height=lm.setter("height"))
        self.rv.add_widget(lm)
        self.rv.viewclass = LabelPrintingRow
        self.add_widget(self.rv)

    def detach_from_parent(self):
        if self.parent:
            self.parent.remove_widget(self)

    def refresh_and_show_print_queue(self):

        try:
            if self.print_queue_popup is not None:
                self.print_queue_popup.dismiss()
        except AttributeError as e:
            logger.info(f"Expected error in refresh_and_show_print_queue {e}")
        except Exception as e:
            logger.info(f"Unepected error in refresh_and_show_print_queue {e}")

        if self.dual_pane_mode:
            self.print_queue_ref.refresh_print_queue_for_embed()
        else:
            self.show_print_queue()

    def clear_search(self):
        self.label_search_input.text = ""

    def show_inventory_for_label_printing(self, inventory_items, dual_pane_mode=False):
        self.full_inventory = inventory_items or []
        self.dual_pane_mode = bool(dual_pane_mode)
        self.rv.data = self.generate_data_for_rv(
            self.full_inventory, self.dual_pane_mode
        )

    def remove_from_queue(self, item_index, embed=False):
        removed, is_empty = self.label_printer.remove_from_queue(item_index)
        if removed:
            if is_empty:
                if embed:
                    self.refresh_print_queue_for_embed()
                else:
                    self.print_queue_popup.dismiss()
            else:
                if embed:
                    self.refresh_print_queue_for_embed()
                else:
                    self.print_queue_popup.dismiss()
                    self.show_print_queue()

    def update_search_input(self, barcode):
        self.label_search_input.text = barcode

    def handle_scanned_barcode(self, barcode):
        barcode = (barcode or "").strip()
        items = self.app.db_manager.get_all_items()

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

    def show_print_queue(self, embed=False):
        queue_layout = BoxLayout(orientation="vertical", spacing=5, padding=5)
        item_layout = BoxLayout(orientation="vertical", spacing=5, padding=5)

        for idx, item in enumerate(self.label_printer.print_queue):
            name_text = (
                f"{item['name'][:27]}..."
                if (embed and len(item["name"]) > 30)
                else item["name"]
            )
            name_label = Label(text=name_text, size_hint_x=0.2)
            qty_label = Label(text=f"Qty: {item['quantity']}", size_hint_x=0.05)
            summary = self.label_printer.describe_queue_item(item)
            mode_label = "Small 2-up" if item.get("mode") == LABEL_MODE_SMALL else "Standard"
            text_label = Label(text=f"[{mode_label}] {summary}", size_hint_x=0.35, halign="left")

            if embed:
                plus_button = MDIconButton(
                    icon="plus",
                    size_hint_x=0.1,
                    on_release=lambda _b, idx=idx: self.increment_quantity(
                        item_index=idx, embed=True
                    ),
                )
                minus_button = MDIconButton(
                    icon="minus",
                    size_hint_x=0.1,
                    on_release=lambda _b, idx=idx: self.decrement_quantity(
                        item_index=idx, embed=True
                    ),
                )
                rm_button = Button(
                    text="Remove",
                    size_hint_x=0.1,
                    on_release=lambda _b, idx=idx: self.remove_from_queue(
                        item_index=idx, embed=True
                    ),
                )
            else:
                plus_button = MDIconButton(
                    icon="plus",
                    size_hint_x=0.1,
                    on_release=lambda _b, idx=idx: self.increment_quantity(
                        item_index=idx
                    ),
                )
                minus_button = MDIconButton(
                    icon="minus",
                    size_hint_x=0.1,
                    on_release=lambda _b, idx=idx: self.decrement_quantity(
                        item_index=idx
                    ),
                )
                rm_button = Button(
                    text="Remove",
                    size_hint_x=0.1,
                    on_release=lambda _b, idx=idx: self.remove_from_queue(
                        item_index=idx
                    ),
                )

            text_button = BoxLayout(size_hint_x=0.1)
            preview_button = Button(
                text="Preview",
                size_hint_x=0.1,
                on_release=lambda _b, idx=idx: self.label_printer.preview_barcode_label(
                    index=idx
                ),
            )

            item_row = GridLayout(cols=8, spacing=5, size_hint_y=None, height=40)
            item_row.add_widget(name_label)
            item_row.add_widget(qty_label)
            item_row.add_widget(text_label)
            item_row.add_widget(plus_button)
            item_row.add_widget(minus_button)
            item_row.add_widget(text_button)
            item_row.add_widget(preview_button)
            item_row.add_widget(rm_button)
            item_layout.add_widget(item_row)

            line = MDBoxLayout(orientation="horizontal", size_hint_y=None, height=1)
            line.md_bg_color = (0.56, 0.56, 1, 1)
            item_layout.add_widget(line)

        btn_layout = BoxLayout(
            orientation="horizontal", spacing=5, padding=5, size_hint_y=0.2
        )
        btn_layout.add_widget(
            MDRaisedButton(
                text="[b][size=20]Print Now[/size][/b]",
                on_release=self.print_now,
                size_hint=(0.2, 1),
            )
        )
        btn_layout.add_widget(BoxLayout(size_hint_x=0.2))
        if not embed:
            btn_layout.add_widget(
                MDFlatButton(
                    text="Cancel",
                    md_bg_color="grey",
                    size_hint=(0.1, 1),
                    on_release=self.cancel_print,
                )
            )
        btn_layout.add_widget(
            MDFlatButton(
                text="Clear Queue",
                md_bg_color="grey",
                size_hint=(0.1, 1),
                on_release=lambda _b: self.clear_queue(embed=embed),
            )
        )

        queue_layout.add_widget(item_layout)
        queue_layout.add_widget(btn_layout)

        if embed:
            return queue_layout
        else:
            self.print_queue_popup = Popup(
                title="Print Queue", content=queue_layout, size_hint=(0.8, 0.6)
            )
            self.print_queue_popup.open()

    def refresh_print_queue_for_embed(self):
        Clock.schedule_once(self._refresh_queue_embed_main_thread, 0.1)

    def _refresh_queue_embed_main_thread(self, *args):
        try:
            self.app.popup_manager.queue_container.remove_widget(
                self.app.popup_manager.print_queue_embed
            )
            self.app.popup_manager.print_queue_embed = (
                self.app.label_manager.show_print_queue(embed=True)
            )
            self.app.popup_manager.queue_container.add_widget(
                self.app.popup_manager.print_queue_embed
            )
        except AttributeError as e:
            logger.info(f"Expected error in refresh_print_queue_for_embed\n{e}")
        except Exception as e:
            logger.error(f"Unexpected error in refresh_print_queue_for_embed\n{e}")

    def increment_quantity(self, item_index, embed=False):
        if 0 <= item_index < len(self.label_printer.print_queue):
            self.label_printer.print_queue[item_index]["quantity"] += 1
            self.label_printer.save_queue()
            (
                self.refresh_print_queue_for_embed()
                if embed
                else self.refresh_and_show_print_queue()
            )

    def decrement_quantity(self, item_index, embed=False):
        if 0 <= item_index < len(self.label_printer.print_queue):
            item = self.label_printer.print_queue[item_index]
            if item["quantity"] > 1:
                item["quantity"] -= 1
                self.label_printer.save_queue()
                (
                    self.refresh_print_queue_for_embed()
                    if embed
                    else self.refresh_and_show_print_queue()
                )

    def update_print_queue_quantity(self, item_name, new_quantity):
        self.label_printer.update_queue_item_quantity(item_name, new_quantity)
        self.label_printer.save_queue()

    def clear_queue(self, embed=False):
        self.label_printer.clear_queue()
        self.label_printer.save_queue()
        (
            self.refresh_print_queue_for_embed()
            if embed
            else self.print_queue_popup.dismiss()
        )

    def print_now(self, *_):
        self.label_printer.process_queue()

    def cancel_print(self, *_):
        if self.print_queue_popup:
            self.print_queue_popup.dismiss()

    def generate_data_for_rv(self, items, dual_pane_mode=False):
        data = []
        if dual_pane_mode:
            for item in items:
                name = item[1]
                name = f"{name[:77]}..." if len(str(name)) > 80 else name
                data.append(
                    {
                        "barcode": str(item[0]),
                        "name": name,
                        "price": f"{float(item[2]):.2f}" if item[2] else "Not Found",
                        "label_printer": self.label_printer,
                    }
                )
        else:
            for item in items:
                data.append(
                    {
                        "barcode": str(item[0]),
                        "name": item[1],
                        "price": f"{float(item[2]):.2f}" if item[2] else "Not Found",
                        "label_printer": self.label_printer,
                    }
                )
        return data

    def filter_inventory(self, query="", dual_pane_mode=False):
        q = (query or "").lower()
        filtered = (
            self.full_inventory
            if not q
            else [
                it
                for it in self.full_inventory
                if q in str(it[0]).lower() or q in (it[1] or "").lower()
            ]
        )
        self.rv.data = self.generate_data_for_rv(
            filtered, dual_pane_mode=dual_pane_mode
        )

    def _on_search_text(self, _inst, value):
        self.filter_inventory(value, self.dual_pane_mode)

    def create_focus_popup(
        self, title, content, textinput, size_hint, pos_hint={}, separator_height=1
    ):
        popup = FocusPopup(
            title=title,
            content=content,
            size_hint=size_hint,
            pos_hint=pos_hint,
            separator_height=separator_height,
        )
        popup.focus_on_textinput(textinput)
        return popup


class LabelPrinter:
    def __init__(self, ref=None):
        self.app = ref
        self.print_queue: list[dict] = []
        self.queue_file_path = "print_queue.json"
        self.print_queue_ref = None

        if ref:
            self.load_queue()

    def save_queue(self):
        try:
            with open(self.queue_file_path, "w") as file:
                json.dump(self.print_queue, file)
        except Exception as e:
            logger.warn(f"Error saving print queue: {e}")

    def load_queue(self):
        try:
            with open(self.queue_file_path, "r") as file:
                self.print_queue = json.load(file)
        except FileNotFoundError:
            self.print_queue = []
        except Exception as e:
            logger.warn(f"Error loading print queue: {e}")
            self.print_queue = []

        cleaned_queue = []
        for item in self.print_queue:
            content = item.get("content", {}) or {}
            cleaned_queue.append(
                {
                    "barcode": item.get("barcode", ""),
                    "name": item.get("name", ""),
                    "price": self._format_price(item.get("price", "")),
                    "quantity": int(item.get("quantity", 1) or 1),
                    "mode": item.get("mode", LABEL_MODE_STANDARD) if item.get("mode") in (LABEL_MODE_STANDARD, LABEL_MODE_SMALL) else LABEL_MODE_STANDARD,
                    "content": {
                        "title": (content.get("title") or item.get("name", ""))[:STANDARD_TEXT_CHAR_LIMIT],
                        "details": (content.get("details") or "")[:STANDARD_TEXT_CHAR_LIMIT],
                    },
                }
            )

        self.print_queue = cleaned_queue

    def _format_price(self, price_text: str) -> str:
        if not price_text:
            return ""

        price_text = price_text.strip()

        if not price_text.startswith("$"):
            price_text = f"${price_text}"

        # drop the cents
        m = re.fullmatch(r"\$([0-9][0-9,]*)\.00", price_text)
        if m:
            return f"${m.group(1)}"

        return price_text


    def add_to_queue(self, barcode, name, price, quantity, content=None, mode=LABEL_MODE_STANDARD):
        try:
            content = content or {}
            item = {
                "barcode": barcode,
                "name": name,
                "price": self._format_price(price),
                "quantity": int(quantity),
                "mode": mode if mode in (LABEL_MODE_STANDARD, LABEL_MODE_SMALL) else LABEL_MODE_STANDARD,
                "content": {
                    "title": (content.get("title") or name)[:STANDARD_TEXT_CHAR_LIMIT],
                    "details": (content.get("details") or "")[:STANDARD_TEXT_CHAR_LIMIT],
                },
            }
            self.print_queue.append(item)
            self.save_queue()
        except Exception as e:
            logger.warn(
                f"Error adding labels to the queue. Probably tried to add 0 \n{e}"
            )

    def update_queue_item_quantity(self, name, new_quantity):
        for item in self.print_queue:
            if item["name"] == name:
                item["quantity"] = new_quantity
                self.save_queue()
                break

    def clear_queue(self):
        self.print_queue.clear()
        self.save_queue()

    def describe_queue_item(self, item: dict) -> str:
        content = item.get("content", {})
        title = content.get("title", "")
        details = content.get("details", "")
        summary = " • ".join(part for part in [title, details] if part)
        if summary:
            return summary[:60]
        if item.get("mode") == LABEL_MODE_SMALL:
            return "Small 2-up label"
        return "Standard 64mm label"

    def handle_upc_e(self, barcode_data):
        logger.warn(f"inside handle_upc_e:\n'{barcode_data}")
        padding = 12 - len(barcode_data)
        upc = barcode_data + "0" * padding
        logger.warn(upc)
        return upc

    @staticmethod
    def _load_font(size: int) -> ImageFont.FreeTypeFont:
        font_paths = [
            "/usr/share/fonts/TTF/Arialbd.TTF",
            "/usr/share/fonts/TTF/Arial.TTF",
            "DejaVuSans-Bold.ttf",
            "DejaVuSans.ttf",
        ]
        for path in font_paths:
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                continue
        return ImageFont.load_default()

    def _make_barcode_image(self, code: str, module_height: float = 15.0) -> Image.Image:
        upc_cls = barcode.get_barcode_class("upc")
        try:
            upc = upc_cls(code, writer=ImageWriter())
        except barcode.errors.NumberOfDigitsError:
            upc = upc_cls(self.handle_upc_e(code), writer=ImageWriter())
        writer_options = {
            "write_text": False,
            "module_width": STANDARD_BARCODE_MODULE_WIDTH,
            "module_height": module_height,
            "quiet_zone": STANDARD_BARCODE_QUIET_ZONE,
            "dpi": 300,
        }
        img = upc.render(writer_options=writer_options)
        if img.mode != "RGB":
            img = img.convert("RGB")
        return img

    def _fit_font_size(
        self,
        draw: ImageDraw.ImageDraw,
        text: str,
        start_size: int,
        min_size: int,
        max_w: int,
        max_h: int,
    ) -> tuple[ImageFont.FreeTypeFont, int, int]:
        size = int(start_size)
        while size >= int(min_size):
            font = self._load_font(size)
            bbox = draw.textbbox((0, 0), text, font=font)
            w = bbox[2] - bbox[0]
            h = bbox[3] - bbox[1]
            if w <= max_w and h <= max_h:
                return font, w, h
            size -= 1

        font = self._load_font(int(min_size))
        bbox = draw.textbbox((0, 0), text, font=font)
        return font, bbox[2] - bbox[0], bbox[3] - bbox[1]

    def _render_standard_label(
        self, barcode_data: str, title: str, price_text: str, details: str
    ) -> Image.Image:
        canvas = Image.new("RGB", (CONTINUOUS_LABEL_WIDTH, STANDARD_LABEL_HEIGHT), "white")
        draw = ImageDraw.Draw(canvas)

        margin_x = STANDARD_MARGIN_X
        margin_y = STANDARD_MARGIN_Y
        band_gap = STANDARD_BAND_GAP
        column_gap = STANDARD_COLUMN_GAP
        barcode_fraction = max(0.1, min(0.9, STANDARD_BARCODE_FRACTION))

        usable_w = CONTINUOUS_LABEL_WIDTH - (2 * margin_x)

        def fit_single_line(text: str, font: ImageFont.FreeTypeFont) -> str:
            t = (text or "").strip()
            if not t:
                return ""
            if draw.textbbox((0, 0), t, font=font)[2] <= usable_w:
                return t
            while t and draw.textbbox((0, 0), f"{t}…", font=font)[2] > usable_w:
                t = t[:-1]
            return f"{t}…" if t else ""

        top_font = self._load_font(STANDARD_TOP_FONT_SIZE)
        bottom_font = self._load_font(STANDARD_BOTTOM_FONT_SIZE)

        top_text = fit_single_line(title, top_font)
        bottom_text = fit_single_line(details, bottom_font)

        top_h = 0
        if top_text:
            top_bbox = draw.textbbox((0, 0), top_text, font=top_font)
            top_h = top_bbox[3] - top_bbox[1]
            draw.text((margin_x, margin_y), top_text, fill="black", font=top_font)

        bottom_h = 0
        if bottom_text:
            bottom_bbox = draw.textbbox((0, 0), bottom_text, font=bottom_font)
            bottom_h = bottom_bbox[3] - bottom_bbox[1]
            draw.text(
                (margin_x, STANDARD_LABEL_HEIGHT - margin_y - bottom_h),
                bottom_text,
                fill="black",
                font=bottom_font,
            )

        y0 = margin_y + (top_h if top_h else 0) + (band_gap if top_h else 0)
        y1 = STANDARD_LABEL_HEIGHT - margin_y - (bottom_h if bottom_h else 0) - (band_gap if bottom_h else 0)
        middle_h = max(1, y1 - y0)

        barcode_col_w = int((usable_w - column_gap) * barcode_fraction)
        price_col_w = usable_w - column_gap - barcode_col_w
        barcode_x0 = margin_x
        price_x0 = margin_x + barcode_col_w + column_gap

        if barcode_data:
            barcode_img = self._make_barcode_image(
                barcode_data,
                module_height=STANDARD_BARCODE_MODULE_HEIGHT,
            )
            bw, bh = barcode_img.size
            max_bw = max(1, barcode_col_w)
            max_bh = max(1, middle_h)
            scale = min(
                max_bw / float(bw),
                max_bh / float(bh),
                1.0,
            )
            if scale < 1.0:
                barcode_img = barcode_img.resize(
                    (int(bw * scale), int(bh * scale)),
                    resample=Image.LANCZOS,
                )
                bw, bh = barcode_img.size

            barcode_x = barcode_x0 + (barcode_col_w - bw) // 2
            barcode_y = y0 + (middle_h - bh) // 2
            canvas.paste(barcode_img, (barcode_x, barcode_y))

        if price_text:
            price_font, price_w, price_h = self._fit_font_size(
                draw,
                price_text,
                STANDARD_PRICE_START_FONT_SIZE,
                STANDARD_PRICE_MIN_FONT_SIZE,
                max(1, price_col_w),
                max(1, middle_h),
            )
            price_x = price_x0 + (price_col_w - price_w) // 2
            price_y = y0 + (middle_h - price_h) // 2
            draw.text((price_x, price_y), price_text, fill="black", font=price_font)

        return canvas

    def _fit_text_to_width(
        self,
        draw: ImageDraw.ImageDraw,
        text: str,
        start_size: int,
        min_size: int,
        max_width: int,
    ) -> tuple[ImageFont.FreeTypeFont, str]:
        clean = (text or "").strip()
        if not clean:
            return self._load_font(min_size), ""

        size = int(start_size)
        while size >= int(min_size):
            font = self._load_font(size)
            candidate = clean
            while candidate and draw.textbbox((0, 0), candidate, font=font)[2] > max_width:
                candidate = candidate[:-1]
            if candidate:
                if candidate != clean:
                    candidate = f"{candidate}…"
                return font, candidate
            size -= 1
        return self._load_font(min_size), ""

    def _render_small_label_panel(self, panel_item: dict | None, panel_width: int, panel_height: int) -> Image.Image:
        panel = Image.new("RGB", (panel_width, panel_height), "white")
        if not panel_item:
            return panel

        draw = ImageDraw.Draw(panel)
        margin_x = SMALL_LABEL_MARGIN_X
        margin_y = SMALL_LABEL_MARGIN_Y
        section_gap = SMALL_SECTION_GAP
        available_h = max(1, panel_height - (2 * margin_y) - (2 * section_gap))
        barcode_h = int(available_h * SMALL_BARCODE_BAND_FRACTION)
        text_h = max(1, (available_h - barcode_h) // 2)
        barcode_h = max(1, available_h - (2 * text_h))

        content = panel_item.get("content", {})
        top_text = content.get("title") or panel_item.get("name", "")
        bottom_text = content.get("details") or panel_item.get("name", "")
        price_text = self._format_price(panel_item.get("price", ""))
        top_line = " ".join(part for part in [price_text, top_text] if part).strip()
        bottom_line = " ".join(part for part in [price_text, bottom_text] if part).strip()

        text_width = max(1, panel_width - (2 * margin_x))
        top_font, top_line = self._fit_text_to_width(
            draw, top_line, SMALL_TEXT_FONT_SIZE, SMALL_TEXT_MIN_FONT_SIZE, text_width
        )
        bottom_font, bottom_line = self._fit_text_to_width(
            draw, bottom_line, SMALL_TEXT_FONT_SIZE, SMALL_TEXT_MIN_FONT_SIZE, text_width
        )

        top_y = margin_y
        if top_line:
            tw = draw.textbbox((0, 0), top_line, font=top_font)[2]
            th = draw.textbbox((0, 0), top_line, font=top_font)[3]
            draw.text(((panel_width - tw) // 2, top_y + max(0, (text_h - th) // 2)), top_line, fill="black", font=top_font)

        barcode_y = top_y + text_h + section_gap
        barcode_data = panel_item.get("barcode")
        if barcode_data:
            barcode_img = self._make_barcode_image(barcode_data, module_height=SMALL_BARCODE_MODULE_HEIGHT)
            bw, bh = barcode_img.size
            scale = min(text_width / float(bw), barcode_h / float(bh), 1.0)
            if scale < 1.0:
                barcode_img = barcode_img.resize((int(bw * scale), int(bh * scale)), resample=Image.LANCZOS)
                bw, bh = barcode_img.size
            panel.paste(barcode_img, (margin_x + (text_width - bw) // 2, barcode_y + (barcode_h - bh) // 2))

        bottom_y = barcode_y + barcode_h + section_gap
        if bottom_line:
            bw = draw.textbbox((0, 0), bottom_line, font=bottom_font)[2]
            bh = draw.textbbox((0, 0), bottom_line, font=bottom_font)[3]
            draw.text(((panel_width - bw) // 2, bottom_y + max(0, (text_h - bh) // 2)), bottom_line, fill="black", font=bottom_font)

        return panel

    def _render_small_pair_label(self, left_item: dict, right_item: dict | None = None) -> Image.Image:
        canvas = Image.new("RGB", (CONTINUOUS_LABEL_WIDTH, SMALL_PAIR_LABEL_HEIGHT), "white")
        panel_width = (CONTINUOUS_LABEL_WIDTH - SMALL_PAIR_SIDE_GAP) // 2
        left_panel = self._render_small_label_panel(left_item, panel_width, SMALL_PAIR_LABEL_HEIGHT)
        right_panel = self._render_small_label_panel(right_item, panel_width, SMALL_PAIR_LABEL_HEIGHT)
        canvas.paste(left_panel, (0, 0))
        canvas.paste(right_panel, (panel_width + SMALL_PAIR_SIDE_GAP, 0))
        return canvas

    def _render_label(self, item: dict) -> tuple[Image.Image, str, bool, int]:
        mode = item.get("mode", LABEL_MODE_STANDARD)
        if mode == LABEL_MODE_SMALL:
            image = self._render_small_pair_label(item, None)
            return image, CONTINUOUS_LABEL_NAME, True, 0

        content = item.get("content", {})
        price_text = self._format_price(item.get("price", ""))
        title = content.get("title") or item.get("name", "")
        details = content.get("details", "")
        image = self._render_standard_label(item["barcode"], title, price_text, details)
        return image, CONTINUOUS_LABEL_NAME, True, 0

    def _send_to_printer(self, image: Image.Image, label_name: str, cut: bool, rotate: int):
        qlr = brother_ql.BrotherQLRaster(PRINTER_MODEL)
        qlr.exception_on_warning = True
        convert(qlr=qlr, images=[image], label=label_name, cut=cut, rotate=rotate)
        send(
            instructions=qlr.data,
            printer_identifier=PRINTER_IDENTIFIER,
            backend_identifier=PRINTER_BACKEND,
        )

    def preview_barcode_label(self, index):
        if not (0 <= index < len(self.print_queue)):
            return

        item = self.print_queue[index]
        try:
            if item.get("mode") == LABEL_MODE_SMALL:
                image = self._render_small_pair_label(item, None)
            else:
                image, _label_name, _cut, _rotate = self._render_label(item)
        except Exception:
            self.app.popup_manager.catch_label_printer_missing_barcode()
            return
        self.open_preview_popup(image)

    def open_preview_popup(self, label_image):
        blank_image = Image.open("images/blank_label.png")
        label_image = label_image.convert("RGBA")
        blank_image = blank_image.convert("RGBA")
        blank_width, blank_height = blank_image.size
        label_width, label_height = label_image.size
        x_position = (blank_width - label_width) // 2
        y_position = (blank_height - label_height) // 2

        blank_image.paste(label_image, (x_position, y_position), label_image)
        data = BytesIO()
        blank_image.save(data, format="PNG")
        data.seek(0)

        core_image = CoreImage(data, ext="png")
        kivy_image = KivyImage(texture=core_image.texture)
        layout = BoxLayout(orientation="vertical")
        layout.add_widget(kivy_image)

        self.preview_popup = Popup(
            content=layout,
            size_hint=(0.2, 0.2),
            title="",
            background="images/transparent.png",
            background_color=(0, 0, 0, 0),
            separator_height=0,
        )

        self.preview_popup.open()

    def catch_label_printing_errors(self, e):
        Clock.schedule_once(
            lambda dt: self.app.popup_manager.catch_label_printing_errors(e), 0
        )

    def process_queue(self):
        print_thread = threading.Thread(
            target=self._process_print_queue_thread, daemon=True
        )
        print_thread.start()

    def _process_print_queue_thread(self):
        self.print_success = True

        standard_jobs: list[dict] = []
        small_jobs: list[dict] = []
        for item in self.print_queue:
            qty = max(1, int(item.get("quantity", 1)))
            target = small_jobs if item.get("mode") == LABEL_MODE_SMALL else standard_jobs
            target.extend([item] * qty)

        for item in standard_jobs:
            try:
                image, label_name, cut, rotate = self._render_label(item)
                self._send_to_printer(image, label_name, cut, rotate)
            except Exception as e:
                self.catch_label_printing_errors(e)
                self.print_success = False
                break

        if self.print_success:
            for i in range(0, len(small_jobs), 2):
                left = small_jobs[i]
                right = small_jobs[i + 1] if (i + 1) < len(small_jobs) else None
                try:
                    image = self._render_small_pair_label(left, right)
                    self._send_to_printer(image, CONTINUOUS_LABEL_NAME, True, 0)
                except Exception as e:
                    self.catch_label_printing_errors(e)
                    self.print_success = False
                    break

        if self.print_success:
            self.print_queue.clear()
            self.save_queue()
            try:
                if self.print_queue_ref:
                    self.print_queue_ref.refresh_print_queue_for_embed()
            except Exception as e:
                logger.info(f"Error refreshing print queue embed: {e}")
            try:
                self.app.label_manager.print_queue_popup.dismiss()
            except AttributeError:
                pass
            try:
                self.app.popup_manager.label_errors_popup.dismiss()
            except AttributeError:
                pass

    def remove_from_queue(self, index):
        if 0 <= index < len(self.print_queue):
            self.print_queue.pop(index)
            self.save_queue()
            return True, len(self.print_queue) == 0
        return False, False

    def print_raw_text_label(
        self,
        text,
        font_path="/usr/share/fonts/TTF/Arial.TTF",
        start_font_size=40,
        min_font_size=10,
    ):
        label_w, label_h = CONTINUOUS_LABEL_WIDTH, STANDARD_LABEL_HEIGHT
        margin = 4
        lines = text.splitlines() or [text]

        font_size = start_font_size
        while font_size >= min_font_size:
            font = ImageFont.truetype(font_path, font_size)
            line_h = font.getbbox("Ag")[3] - font.getbbox("Ag")[1]
            total_h = line_h * len(lines)
            fits_vertically = total_h <= label_h - 2 * margin
            fits_horizontally = all(
                (font.getbbox(l)[2] - font.getbbox(l)[0]) <= label_w - 2 * margin
                for l in lines
            )
            if fits_vertically and fits_horizontally:
                break
            font_size -= 1
        else:  # fell below min_font_size
            font_size = min_font_size
            font = ImageFont.truetype(font_path, font_size)

        img = Image.new("RGB", (label_w, label_h), "white")
        draw = ImageDraw.Draw(img)
        line_h = font.getbbox("Ag")[3] - font.getbbox("Ag")[1]
        y = (label_h - line_h * len(lines)) // 2

        for l in lines:
            line_w = font.getbbox(l)[2] - font.getbbox(l)[0]
            x = (label_w - line_w) // 2
            draw.text((x, y), l, fill="black", font=font)
            y += line_h

        qlr = brother_ql.BrotherQLRaster(PRINTER_MODEL)
        qlr.exception_on_warning = True
        convert(qlr=qlr, images=[img], label=CONTINUOUS_LABEL_NAME, cut=True)

        try:
            send(
                instructions=qlr.data,
                printer_identifier=PRINTER_IDENTIFIER,
                backend_identifier=PRINTER_BACKEND,
            )
            return True
        except Exception as e:
            self.catch_label_printing_errors(e)
            return False


class PrintQueueRow(BoxLayout):
    name = StringProperty()
    quantity = StringProperty()
    remove_callback = ObjectProperty()
    quantity_changed_callback = ObjectProperty()
    preview_barcode_label_callback = ObjectProperty()

    def __init__(self):
        self.label_printer = LabelPrinter()

    def on_remove_button_press(self):
        if self.remove_callback:
            self.remove_callback(self.name)

    def preview_barcode_label(self):
        if self.preview_barcode_label_callback:
            self.preview_barcode_label_callback(self.name)


class LabelQueueLayout(BoxLayout):
    def __init__(self, **kwargs):
        super(LabelQueueLayout, self).__init__(**kwargs)

        # self.bind(children=self.update_height)

        self.orientation = "vertical"
        # self.height = self.minimum_height

    # def update_height(self, *args):
    #     self.height = len(self.children) * dp(48)


class FocusPopup(Popup):
    def focus_on_textinput(self, textinput):
        self.textinput_to_focus = textinput

    def on_open(self):
        if hasattr(self, "textinput_to_focus"):
            self.textinput_to_focus.focus = True


if __name__ == "__main__":
    text = """

    """
    try:
        printer = LabelPrinter(None)
        printer.print_raw_text_label(text)
    except Exception as e:
        print(e)
