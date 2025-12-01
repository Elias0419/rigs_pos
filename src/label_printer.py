import json
import logging
import threading
from io import BytesIO
from typing import Dict

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
from kivy.uix.textinput import TextInput
from kivy.uix.togglebutton import ToggleButton

from kivymd.uix.boxlayout import BoxLayout, MDBoxLayout
from kivymd.uix.button import MDFlatButton, MDIconButton, MDRaisedButton
from kivymd.uix.label import MDLabel
from kivymd.uix.recycleview import RecycleView

logger = logging.getLogger("rigs_pos")


PRINTER_MODEL = "QL-710W"
PRINTER_IDENTIFIER = "usb://0x04F9:0x2043"
PRINTER_BACKEND = "pyusb"
CONTINUOUS_LABEL_NAME = "29"  # DK-2210 29mm continuous tape
CONTINUOUS_LABEL_WIDTH = 306  # 300dpi printable width for DK-2210
LEGACY_LABEL_NAME = "23x23"
LEGACY_SIZE = (202, 202)


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

        type_row = MDBoxLayout(orientation="horizontal", spacing=5, size_hint_y=None, height=dp(40))
        self.label_type = "small"
        for label_type, text in [
            ("small", "Small (default)"),
            ("medium", "Medium"),
            ("large", "Large"),
            ("legacy23", "Legacy 23x23"),
        ]:
            btn = ToggleButton(text=text, group="label_size", state="down" if label_type == "small" else "normal")
            btn.bind(on_release=lambda inst, lt=label_type: self._on_label_type_selected(lt))
            type_row.add_widget(btn)
        content.add_widget(type_row)

        form_layout = MDBoxLayout(orientation="vertical", spacing=5)
        self.price_input = TextInput(
            text=f"{float(self.price):.2f}" if self.price not in ("Not Found", "") else "",
            hint_text="Price (e.g. 9.99)",
            multiline=False,
            size_hint_y=None,
            height=dp(40),
        )
        self.small_text_input = TextInput(
            text=self.name[:30],
            hint_text="One line of text",
            multiline=False,
            size_hint_y=None,
            height=dp(40),
        )
        self.medium_name_input = TextInput(
            text=self.name[:60],
            hint_text="Title (shows on medium & large)",
            multiline=False,
            size_hint_y=None,
            height=dp(40),
        )
        self.medium_line1_input = TextInput(hint_text="Line 1", multiline=False, size_hint_y=None, height=dp(36))
        self.medium_line2_input = TextInput(hint_text="Line 2", multiline=False, size_hint_y=None, height=dp(36))
        self.medium_line3_input = TextInput(hint_text="Line 3", multiline=False, size_hint_y=None, height=dp(36))
        self.large_body_input = TextInput(
            hint_text="Description for large label",
            multiline=True,
            size_hint_y=None,
            height=dp(120),
        )
        self.legacy_optional_text = TextInput(
            hint_text="Optional text for legacy label",
            multiline=False,
            size_hint_y=None,
            height=dp(40),
        )

        form_layout.add_widget(self.price_input)
        form_layout.add_widget(self.small_text_input)
        form_layout.add_widget(self.medium_name_input)
        form_layout.add_widget(self.medium_line1_input)
        form_layout.add_widget(self.medium_line2_input)
        form_layout.add_widget(self.medium_line3_input)
        form_layout.add_widget(self.large_body_input)
        form_layout.add_widget(self.legacy_optional_text)
        content.add_widget(form_layout)

        self._update_form_visibility("small")

        btn_layout = BoxLayout(
            orientation="horizontal", size_hint=(1, None), height=dp(48), spacing=10
        )
        popup = self.create_focus_popup(
            title="",
            content=content,
            textinput=quantity_input,
            size_hint=(0.7, 0.8),
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

    def _on_label_type_selected(self, label_type: str):
        self.label_type = label_type
        self._update_form_visibility(label_type)

    def _update_form_visibility(self, label_type: str):
        widgets = [
            self.price_input,
            self.small_text_input,
            self.medium_name_input,
            self.medium_line1_input,
            self.medium_line2_input,
            self.medium_line3_input,
            self.large_body_input,
            self.legacy_optional_text,
        ]
        for w in widgets:
            w.opacity = 0
            w.disabled = True
            w.height = 0

        def show(widget):
            widget.opacity = 1
            widget.disabled = False
            widget.height = dp(40) if widget is not self.large_body_input else dp(120)

        show(self.price_input)
        if label_type == "small":
            show(self.small_text_input)
        elif label_type == "medium":
            show(self.medium_name_input)
            show(self.medium_line1_input)
            show(self.medium_line2_input)
            show(self.medium_line3_input)
        elif label_type == "large":
            show(self.medium_name_input)
            self.large_body_input.height = dp(120)
            self.large_body_input.opacity = 1
            self.large_body_input.disabled = False
        elif label_type == "legacy23":
            show(self.legacy_optional_text)

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
            content: Dict[str, str] = {}
            price_text = self.price_input.text.strip()
            if price_text and not price_text.startswith("$"):
                price_text = f"${price_text}"

            if self.label_type == "small":
                content = {
                    "info_text": self.small_text_input.text.strip(),
                }
            elif self.label_type == "medium":
                content = {
                    "title": self.medium_name_input.text.strip() or self.name,
                    "line1": self.medium_line1_input.text.strip(),
                    "line2": self.medium_line2_input.text.strip(),
                    "line3": self.medium_line3_input.text.strip(),
                }
            elif self.label_type == "large":
                content = {
                    "title": self.medium_name_input.text.strip() or self.name,
                    "body": self.large_body_input.text.strip(),
                }
            elif self.label_type == "legacy23":
                content = {"optional_text": self.legacy_optional_text.text.strip()}

            self.label_printer.add_to_queue(
                barcode=self.barcode,
                name=self.name,
                price=price_text or self.price,
                quantity=quantity,
                label_type=self.label_type,
                content=content,
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

    def update_print_queue_with_label_text(self, item_name, optional_text):

        updated = False
        for item in self.label_printer.print_queue:
            if item["name"] == item_name and item.get("label_type", "legacy23") == "legacy23":
                item["optional_text"] = optional_text
                item.setdefault("content", {})["optional_text"] = optional_text
                updated = True
                break
        if updated and not self.dual_pane_mode:
            self.refresh_and_show_print_queue()

    def clear_search(self):
        self.label_search_input.text = ""

    def show_inventory_for_label_printing(self, inventory_items, dual_pane_mode=False):
        self.full_inventory = inventory_items or []
        self.dual_pane_mode = bool(dual_pane_mode)
        self.rv.data = self.generate_data_for_rv(
            self.full_inventory, self.dual_pane_mode
        )

    def remove_from_queue(self, item_name, embed=False):
        removed, is_empty = self.label_printer.remove_from_queue(item_name)
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

        for item in self.label_printer.print_queue:
            name_text = (
                f"{item['name'][:27]}..."
                if (embed and len(item["name"]) > 30)
                else item["name"]
            )
            name_label = Label(text=name_text, size_hint_x=0.2)
            qty_label = Label(text=f"Qty: {item['quantity']}", size_hint_x=0.05)
            summary = self.label_printer.describe_queue_item(item)
            text_label = Label(text=summary, size_hint_x=0.35, halign="left")

            if embed:
                plus_button = MDIconButton(
                    icon="plus",
                    size_hint_x=0.1,
                    on_release=lambda _b, item=item: self.increment_quantity(
                        item_str=item["name"], embed=True
                    ),
                )
                minus_button = MDIconButton(
                    icon="minus",
                    size_hint_x=0.1,
                    on_release=lambda _b, item=item: self.decrement_quantity(
                        item_str=item["name"], embed=True
                    ),
                )
                rm_button = Button(
                    text="Remove",
                    size_hint_x=0.1,
                    on_release=lambda _b, item=item: self.remove_from_queue(
                        item_name=item["name"], embed=True
                    ),
                )
            else:
                plus_button = MDIconButton(
                    icon="plus",
                    size_hint_x=0.1,
                    on_release=lambda _b, item=item: self.increment_quantity(
                        item_str=item["name"]
                    ),
                )
                minus_button = MDIconButton(
                    icon="minus",
                    size_hint_x=0.1,
                    on_release=lambda _b, item=item: self.decrement_quantity(
                        item_str=item["name"]
                    ),
                )
                rm_button = Button(
                    text="Remove",
                    size_hint_x=0.1,
                    on_release=lambda _b, item=item: self.remove_from_queue(
                        item_name=item["name"]
                    ),
                )

            if item.get("label_type", "legacy23") == "legacy23":
                text_button = Button(
                    text="Add Text",
                    size_hint_x=0.1,
                    on_release=lambda _b, item=item: self.add_label_text(
                        item_str=item["name"]
                    ),
                )
            else:
                text_button = BoxLayout(size_hint_x=0.1)
            preview_button = Button(
                text="Preview",
                size_hint_x=0.1,
                on_release=lambda _b, item=item: self.label_printer.preview_barcode_label(
                    name=item["name"]
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

    def add_label_text(self, item_str):
        target_item = next(
            (i for i in self.label_printer.print_queue if i.get("name") == item_str),
            None,
        )
        if not target_item or target_item.get("label_type", "legacy23") != "legacy23":
            return
        layout = BoxLayout(orientation="vertical", size_hint_y=1)
        text_layout = BoxLayout(orientation="vertical", size_hint_y=0.5)
        self.add_label_text_input = TextInput(
            text=target_item.get("optional_text", "")[:30],
            size_hint=(1, 0.1),
            multiline=False,
        )
        text_layout.add_widget(self.add_label_text_input)

        btns = BoxLayout(orientation="horizontal", spacing=5, size_hint=(1, 0.5))
        confirm = MDRaisedButton(
            text="Confirm",
            size_hint=(1, 1),
            on_release=lambda _b: self.on_add_label_confirm_button_press(item_str),
        )
        cancel = MDRaisedButton(
            text="Cancel",
            size_hint=(1, 1),
            on_release=lambda _b: self.add_label_popup.dismiss(),
        )
        btns.add_widget(confirm)
        btns.add_widget(cancel)

        layout.add_widget(text_layout)
        layout.add_widget(btns)
        self.add_label_popup = self.create_focus_popup(
            title="Add Text to Selected Label",
            content=layout,
            textinput=self.add_label_text_input,
            size_hint=(0.4, 0.2),
        )
        self.add_label_popup.open()

    def on_add_label_confirm_button_press(self, item_str):
        self.add_label_popup.dismiss()
        for item in self.label_printer.print_queue:
            if item_str == item["name"]:
                optional_text = self.add_label_text_input.text
                item["optional_text"] = optional_text
                item.setdefault("content", {})["optional_text"] = optional_text
                self.label_printer.save_queue()
                self.refresh_and_show_print_queue()
                break

    def increment_quantity(self, item_str, embed=False):
        for item in self.label_printer.print_queue:
            if item["name"] == item_str:
                item["quantity"] += 1
                self.label_printer.save_queue()
                (
                    self.refresh_print_queue_for_embed()
                    if embed
                    else self.refresh_and_show_print_queue()
                )
                break

    def decrement_quantity(self, item_str, embed=False):
        for item in self.label_printer.print_queue:
            if item["name"] == item_str and item["quantity"] > 1:
                item["quantity"] -= 1
                self.label_printer.save_queue()
                (
                    self.refresh_print_queue_for_embed()
                    if embed
                    else self.refresh_and_show_print_queue()
                )
                break

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

        for item in self.print_queue:
            item.setdefault("label_type", "legacy23")
            item.setdefault("content", {})
            if item.get("label_type") == "legacy23":
                item.setdefault("optional_text", item.get("content", {}).get("optional_text", ""))

    def _format_price(self, price_text: str) -> str:
        if not price_text:
            return ""
        price_text = price_text.strip()
        return price_text if price_text.startswith("$") else f"${price_text}"

    def add_to_queue(self, barcode, name, price, quantity, label_type="small", content=None):
        try:
            item = {
                "barcode": barcode,
                "name": name,
                "price": self._format_price(price),
                "quantity": int(quantity),
                "label_type": label_type,
                "content": content or {},
            }
            if label_type == "legacy23":
                item["optional_text"] = item["content"].get("optional_text", "")
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
        label_type = item.get("label_type", "legacy23")
        content = item.get("content", {})
        if label_type == "small":
            return f"Small: {content.get('info_text', '')[:30]}"
        if label_type == "medium":
            return "Medium: " + ", ".join(
                filter(None, [content.get("title"), content.get("line1"), content.get("line2"), content.get("line3")])
            )[:40]
        if label_type == "large":
            body = content.get("body", "")
            return f"Large: {body[:40]}" if body else "Large label"
        return f"Legacy text: {item.get('optional_text', '')[:40]}"

    def calculate_dynamic_font_size(
        self,
        draw,
        text,
        max_width,
        start_font_size=40,
        min_font_size=10,
        font_path="/usr/share/fonts/TTF/Arial.TTF",
    ):
        font_size = start_font_size

        try:
            font = ImageFont.truetype(font_path, font_size)
        except OSError:
            try:
                font = ImageFont.truetype("DejaVuSans.ttf", font_size)
            except OSError:
                font = ImageFont.load_default()

        text_bbox = draw.textbbox((0, 0), text, font=font)
        text_width = text_bbox[2] - text_bbox[0]

        while text_width > max_width and font_size > min_font_size:
            font_size -= 1
            font = ImageFont.truetype(font_path, font_size)
            text_bbox = draw.textbbox((0, 0), text, font=font)
            text_width = text_bbox[2] - text_bbox[0]

        return font_size

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
            "module_width": 0.20,
            "module_height": module_height,
            "quiet_zone": 1.0,
            "dpi": 300,
        }
        img = upc.render(writer_options=writer_options)
        if img.mode != "RGB":
            img = img.convert("RGB")
        return img

    def _render_small_label(self, barcode_data: str, price_text: str, info_text: str) -> Image.Image:
        margin_top = 8
        margin_bottom = 8
        gap_barcode_price = 4
        gap_price_info = 4

        barcode_img = self._make_barcode_image(barcode_data)
        bw, bh = barcode_img.size
        max_barcode_width = CONTINUOUS_LABEL_WIDTH - 2 * margin_top
        if bw > max_barcode_width:
            scale = max_barcode_width / float(bw)
            new_size = (int(bw * scale), int(bh * scale))
            barcode_img = barcode_img.resize(new_size, resample=Image.LANCZOS)
            bw, bh = barcode_img.size

        price_font = self._load_font(26)
        info_font = self._load_font(18)
        tmp_img = Image.new("RGB", (1, 1), "white")
        tmp_draw = ImageDraw.Draw(tmp_img)

        price_bbox = tmp_draw.textbbox((0, 0), price_text, font=price_font)
        price_height = price_bbox[3] - price_bbox[1]

        info_bbox = tmp_draw.textbbox((0, 0), info_text, font=info_font)
        info_height = info_bbox[3] - info_bbox[1]

        label_height = (
            margin_top
            + bh
            + gap_barcode_price
            + price_height
            + gap_price_info
            + info_height
            + margin_bottom
        )

        label_img = Image.new("RGB", (CONTINUOUS_LABEL_WIDTH, label_height), "white")
        draw = ImageDraw.Draw(label_img)

        barcode_x = (CONTINUOUS_LABEL_WIDTH - bw) // 2
        barcode_y = margin_top
        label_img.paste(barcode_img, (barcode_x, barcode_y))

        price_y = barcode_y + bh + gap_barcode_price
        price_width = price_bbox[2] - price_bbox[0]
        price_x = (CONTINUOUS_LABEL_WIDTH - price_width) // 2
        draw.text((price_x, price_y), price_text, fill="black", font=price_font)

        info_y = price_y + price_height + gap_price_info
        info_width = info_bbox[2] - info_bbox[0]
        info_x = (CONTINUOUS_LABEL_WIDTH - info_width) // 2
        draw.text((info_x, info_y), info_text, fill="black", font=info_font)
        return label_img

    def _render_medium_label(
        self,
        barcode_data: str,
        title: str,
        price_text: str,
        extra_lines: list[str],
    ) -> Image.Image:
        margin_top = 8
        margin_bottom = 8
        gap_between_lines = 4
        gap_before_barcode = 6

        barcode_img = self._make_barcode_image(barcode_data)
        bw, bh = barcode_img.size
        max_barcode_width = CONTINUOUS_LABEL_WIDTH - 2 * margin_top
        if bw > max_barcode_width:
            scale = max_barcode_width / float(bw)
            new_size = (int(bw * scale), int(bh * scale))
            barcode_img = barcode_img.resize(new_size, resample=Image.LANCZOS)
            bw, bh = barcode_img.size

        name_font = self._load_font(20)
        price_font = self._load_font(26)
        extra_font = self._load_font(16)

        tmp_img = Image.new("RGB", (1, 1), "white")
        tmp_draw = ImageDraw.Draw(tmp_img)

        def measure(text: str, font: ImageFont.FreeTypeFont) -> tuple[int, int]:
            bbox = tmp_draw.textbbox((0, 0), text, font=font)
            return bbox[2] - bbox[0], bbox[3] - bbox[1]

        name_w, name_h = measure(title, name_font)
        price_w, price_h = measure(price_text, price_font)
        measured_extras = [measure(t, extra_font) for t in extra_lines]
        extra_heights = [h for _, h in measured_extras]

        label_height = (
            margin_top
            + name_h
            + gap_between_lines
            + price_h
            + sum(extra_heights)
            + gap_between_lines * (len(extra_heights) + 1)
            + gap_before_barcode
            + bh
            + margin_bottom
        )

        label_img = Image.new("RGB", (CONTINUOUS_LABEL_WIDTH, label_height), "white")
        draw = ImageDraw.Draw(label_img)

        def draw_centered(text: str, y: int, font: ImageFont.FreeTypeFont) -> int:
            bbox = draw.textbbox((0, 0), text, font=font)
            text_w = bbox[2] - bbox[0]
            text_h = bbox[3] - bbox[1]
            x = (CONTINUOUS_LABEL_WIDTH - text_w) // 2
            draw.text((x, y), text, fill="black", font=font)
            return y + text_h

        y = margin_top
        y = draw_centered(title, y, name_font)
        y += gap_between_lines
        y = draw_centered(price_text, y, price_font)
        for line, (_, h) in zip(extra_lines, measured_extras):
            y += gap_between_lines
            y = draw_centered(line, y, extra_font)

        y += gap_before_barcode
        barcode_x = (CONTINUOUS_LABEL_WIDTH - bw) // 2
        barcode_y = label_height - margin_bottom - bh
        label_img.paste(barcode_img, (barcode_x, barcode_y))
        return label_img

    def _render_large_label(
        self, barcode_data: str, title: str, price_text: str, body: str
    ) -> Image.Image:
        margin_x = 8
        margin_y = 8
        col_gap = 10
        col_inner_margin_x = 4
        line_gap = 4

        name_font = self._load_font(24)
        price_font = self._load_font(28)
        body_font = self._load_font(16)

        barcode_img = self._make_barcode_image(barcode_data, module_height=20.0)
        barcode_img = barcode_img.rotate(90, expand=True)
        bw, bh = barcode_img.size

        max_barcode_height = CONTINUOUS_LABEL_WIDTH - 2 * margin_y
        if bh > max_barcode_height:
            scale = max_barcode_height / float(bh)
            new_size = (int(bw * scale), int(bh * scale))
            barcode_img = barcode_img.resize(new_size, resample=Image.LANCZOS)
            bw, bh = barcode_img.size

        barcode_col_width = bw + 2 * col_inner_margin_x

        tmp_img = Image.new("RGB", (1, 1), "white")
        tmp_draw = ImageDraw.Draw(tmp_img)

        def measure(text: str, font: ImageFont.FreeTypeFont) -> tuple[int, int]:
            bbox = tmp_draw.textbbox((0, 0), text, font=font)
            return bbox[2] - bbox[0], bbox[3] - bbox[1]

        name_w, name_h = measure(title, name_font)
        price_w, price_h = measure(price_text, price_font)
        available_height = CONTINUOUS_LABEL_WIDTH - 2 * margin_y

        BASE_MIN_TEXT_WIDTH = 300
        MAX_TEXT_WIDTH = 900
        STEP = 10

        min_width = max(BASE_MIN_TEXT_WIDTH, name_w, price_w)
        text_col_width = min_width
        best_lines: list[str] = []
        best_line_heights: list[int] = []

        while text_col_width <= MAX_TEXT_WIDTH:
            lines = self._wrap_text(tmp_draw, body, body_font, text_col_width)
            line_heights: list[int] = []
            total_body_height = 0
            for line in lines:
                _, lh = measure(line, body_font)
                line_heights.append(lh)
                total_body_height += lh
            if lines:
                total_body_height += line_gap * (len(lines) - 1)

            text_block_height = (
                name_h
                + line_gap
                + price_h
                + (line_gap if lines else 0)
                + total_body_height
            )

            if text_block_height <= available_height:
                best_lines = lines
                best_line_heights = line_heights
                break

            text_col_width += STEP

        if not best_lines:
            text_col_width = max(min_width, MAX_TEXT_WIDTH)
            best_lines = self._wrap_text(tmp_draw, body, body_font, text_col_width)
            best_line_heights = [measure(line, body_font)[1] for line in best_lines]
            total_body_height = sum(best_line_heights)
            if best_lines:
                total_body_height += line_gap * (len(best_line_heights) - 1)
            text_block_height = (
                name_h
                + line_gap
                + price_h
                + (line_gap if best_lines else 0)
                + total_body_height
            )
        else:
            total_body_height = sum(best_line_heights)
            if best_lines:
                total_body_height += line_gap * (len(best_line_heights) - 1)
            text_block_height = (
                name_h
                + line_gap
                + price_h
                + (line_gap if best_lines else 0)
                + total_body_height
            )

        logical_width = (
            margin_x + barcode_col_width + col_gap + text_col_width + margin_x
        )

        logical_img = Image.new("RGB", (logical_width, CONTINUOUS_LABEL_WIDTH), "white")
        draw = ImageDraw.Draw(logical_img)

        barcode_x = margin_x + col_inner_margin_x
        available_height = CONTINUOUS_LABEL_WIDTH - 2 * margin_y
        barcode_y = margin_y + (available_height - bh) // 2
        logical_img.paste(barcode_img, (barcode_x, barcode_y))

        text_x = margin_x + barcode_col_width + col_gap
        text_block_y_start = margin_y + (available_height - text_block_height) // 2
        y = text_block_y_start

        name_bbox = draw.textbbox((0, 0), title, font=name_font)
        name_draw_w = name_bbox[2] - name_bbox[0]
        name_x = text_x + (text_col_width - name_draw_w) // 2
        draw.text((name_x, y), title, fill="black", font=name_font)
        y += name_h + line_gap

        price_bbox = draw.textbbox((0, 0), price_text, font=price_font)
        price_draw_w = price_bbox[2] - price_bbox[0]
        price_x = text_x + (text_col_width - price_draw_w) // 2
        draw.text((price_x, y), price_text, fill="black", font=price_font)
        y += price_h

        if best_lines:
            y += line_gap

        for line, lh in zip(best_lines, best_line_heights):
            draw.text((text_x, y), line, fill="black", font=body_font)
            y += lh + line_gap

        return logical_img.rotate(270, expand=True)

    def _render_legacy_label(
        self, barcode_data: str, price_text: str, optional_text: str
    ) -> Image.Image:
        label_width, label_height = LEGACY_SIZE
        barcode_y_position = 35

        barcode_image = self._make_barcode_image(barcode_data, module_height=10)

        label_image = Image.new("RGB", (label_width, label_height), "white")
        draw = ImageDraw.Draw(label_image)

        font_size = 33
        try:
            font = ImageFont.truetype("/usr/share/fonts/TTF/Arialbd.TTF", font_size)
        except OSError:
            try:
                font = ImageFont.truetype("DejaVuSans.ttf", font_size)
            except OSError:
                font = ImageFont.load_default()

        text = self._format_price(price_text) or price_text
        text_bbox = draw.textbbox((0, 0), text, font=font)
        text_width = text_bbox[2] - text_bbox[0]
        x_text = (label_width - text_width) / 2
        draw.text((x_text, 0), text, fill="black", font=font)

        barcode_width, barcode_height = barcode_image.size
        barcode_position = ((label_width - barcode_width) // 2, barcode_y_position)
        label_image.paste(barcode_image, barcode_position)

        if optional_text:
            max_optional_text_width = label_width
            additional_text_font_size = self.calculate_dynamic_font_size(
                draw, optional_text, max_optional_text_width
            )
            try:
                additional_font = ImageFont.truetype(
                    "/usr/share/fonts/TTF/Arial.TTF", additional_text_font_size
                )
            except OSError:
                try:
                    additional_font = ImageFont.truetype(
                        "DejaVuSans.ttf", additional_text_font_size
                    )
                except OSError:
                    additional_font = ImageFont.load_default()

            additional_text_bbox = draw.textbbox(
                (0, 0), optional_text, font=additional_font
            )
            additional_text_width = additional_text_bbox[2] - additional_text_bbox[0]
            x_additional_text = (label_width - additional_text_width) / 2
            additional_text_y_position = barcode_y_position + barcode_height
            draw.text(
                (x_additional_text, additional_text_y_position),
                optional_text,
                fill="black",
                font=additional_font,
            )
        return label_image

    def _wrap_text(
        self,
        draw: ImageDraw.ImageDraw,
        text: str,
        font: ImageFont.FreeTypeFont,
        max_width: int,
    ) -> list[str]:
        words = text.split()
        if not words:
            return []
        lines: list[str] = []
        line = words[0]
        for word in words[1:]:
            test = f"{line} {word}"
            bbox = draw.textbbox((0, 0), test, font=font)
            w = bbox[2] - bbox[0]
            if w <= max_width:
                line = test
            else:
                lines.append(line)
                line = word
        lines.append(line)
        return lines

    def _render_label(self, item: dict) -> tuple[Image.Image, str, bool, int]:
        label_type = item.get("label_type", "legacy23")
        content = item.get("content", {})
        price_text = self._format_price(item.get("price", ""))
        if label_type == "small":
            info_text = content.get("info_text", "") or item.get("name", "")
            image = self._render_small_label(item["barcode"], price_text, info_text)
            return image, CONTINUOUS_LABEL_NAME, True, 0
        if label_type == "medium":
            title = content.get("title", item.get("name", ""))
            lines = [content.get("line1", ""), content.get("line2", ""), content.get("line3", "")]
            lines = [line for line in lines if line]
            image = self._render_medium_label(item["barcode"], title, price_text, lines)
            return image, CONTINUOUS_LABEL_NAME, True, 0
        if label_type == "large":
            title = content.get("title", item.get("name", ""))
            body = content.get("body", "")
            image = self._render_large_label(item["barcode"], title, price_text, body)
            return image, CONTINUOUS_LABEL_NAME, True, 0
        optional_text = content.get("optional_text") or item.get("optional_text", "")
        image = self._render_legacy_label(item["barcode"], price_text, optional_text)
        return image, LEGACY_LABEL_NAME, False, 0

    def _send_to_printer(self, image: Image.Image, label_name: str, cut: bool, rotate: int):
        qlr = brother_ql.BrotherQLRaster(PRINTER_MODEL)
        qlr.exception_on_warning = True
        convert(qlr=qlr, images=[image], label=label_name, cut=cut, rotate=rotate)
        send(
            instructions=qlr.data,
            printer_identifier=PRINTER_IDENTIFIER,
            backend_identifier=PRINTER_BACKEND,
        )

    def preview_barcode_label(self, name):
        for item in self.print_queue:
            if item["name"] == name:
                try:
                    image, label_name, cut, rotate = self._render_label(item)
                except Exception:
                    self.app.popup_manager.catch_label_printer_missing_barcode()
                    return
                self.open_preview_popup(image)
                break

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
        for item in self.print_queue:
            item_quantity = item.get("quantity", 1)
            for _ in range(item_quantity):
                try:
                    image, label_name, cut, rotate = self._render_label(item)
                    self._send_to_printer(image, label_name, cut, rotate)
                except Exception as e:
                    self.catch_label_printing_errors(e)
                    self.print_success = False
                    break
            if not self.print_success:
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

    def remove_from_queue(self, name):
        for i, item in enumerate(self.print_queue):
            if item["name"] == name:
                self.print_queue.pop(i)
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
        label_w, label_h = LEGACY_SIZE
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
        convert(qlr=qlr, images=[img], label=LEGACY_LABEL_NAME, cut=False)

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
    add_label_text_callback = ObjectProperty()
    preview_barcode_label_callback = ObjectProperty()
    optional_text = StringProperty()

    def __init__(self):
        self.label_printer = LabelPrinter()

    def on_remove_button_press(self):
        if self.remove_callback:
            self.remove_callback(self.name)

    def on_add_label_confirm_button_press(self):
        optional_text = self.add_label_text_input.text

        if self.add_label_text_callback:
            self.add_label_text_callback(self.name, optional_text)
        self.add_label_popup.dismiss()

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
