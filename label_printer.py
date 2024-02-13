import barcode
import textwrap
from barcode.writer import ImageWriter
from barcode.upc import UniversalProductCodeA as upc_a
from PIL import Image, ImageDraw, ImageFont
import brother_ql
from brother_ql.conversion import convert
from brother_ql.backends.helpers import send
from kivymd.uix.boxlayout import BoxLayout
from kivy.uix.popup import Popup
from kivy.uix.label import Label
from kivy.properties import StringProperty, ListProperty, ObjectProperty
from kivy.uix.textinput import TextInput
from kivymd.uix.button import MDFlatButton, MDRaisedButton
from kivymd.uix.recycleview import RecycleView
from kivy.metrics import dp





class LabelPrintingRow(BoxLayout):
    barcode = StringProperty()
    name = StringProperty()
    price = StringProperty()
    label_printer = ObjectProperty()

    def add_to_print_queue(self):
        self.show_label_popup()

    def create_focus_popup(self, title, content, textinput, size_hint, pos_hint={}):
        popup = FocusPopup(
            title=title, content=content, size_hint=size_hint, pos_hint=pos_hint
        )
        popup.focus_on_textinput(textinput)
        return popup

    def show_label_popup(self):
        content = BoxLayout(orientation="vertical")
        quantity_input = TextInput(text="", size_hint=(1, 0.4), input_filter="int")
        content.add_widget(Label(text=f"Enter quantity for {self.name}"))
        content.add_widget(quantity_input)
        btn_layout = BoxLayout(
            orientation="horizontal", size_hint=(0.8, 0.8), spacing=10
        )
        popup = self.create_focus_popup(
            title="Label Quantity",
            content=content,
            textinput=quantity_input,
            size_hint=(0.4, 0.4),
            pos_hint={"top": 1},
        )


        add_button = MDRaisedButton(
                text="Add",
                size_hint=(0.2, 0.8),
                on_press=lambda x: self.on_add_button_press(quantity_input, popup),
                disabled=True
            )

        btn_layout.add_widget(add_button)

        btn_layout.add_widget(
            MDRaisedButton(
                text="Cancel",
                size_hint=(0.2, 0.8),
                on_press=lambda x: popup.dismiss(),
            )
        )
        content.add_widget(btn_layout)
        def on_text(instance, value):

            add_button.disabled = not(value.isdigit() and int(value) > 0)


        quantity_input.bind(text=on_text)


        popup.open()

    def on_add_button_press(self, quantity_input, popup):
        self.add_quantity_to_queue(quantity_input.text)
        popup.dismiss()

    def add_quantity_to_queue(self, quantity):
        if quantity.isdigit() and int(quantity) > 0:
            self.label_printer.add_to_queue(self.barcode, self.name, self.price, quantity)


class LabelPrintingView(BoxLayout):
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(LabelPrintingView, cls).__new__(cls, *args, **kwargs)
        return cls._instance

    def __init__(self, ref, **kwargs):
        if not hasattr(self, "_init"):
            super(LabelPrintingView, self).__init__(**kwargs)
            self.full_inventory = []
            self.app = ref
            self.label_printer = self.app.label_printer

            self._init = True

    def detach_from_parent(self):
        if self.parent:
            self.parent.remove_widget(self)

    def refresh_and_show_print_queue(self):
        if self.print_queue_popup is not None:
            self.print_queue_popup.dismiss()
        self.show_print_queue()

    def update_print_queue_with_label_text(self, item_name, optional_text):
        updated = False
        for item in self.label_printer.print_queue:
            if item["name"] == item_name:
                item["optional_text"] = optional_text
                updated = True
                break
        if updated:
            self.refresh_and_show_print_queue()

    def clear_search(self):
        self.ids.label_search_input.text = ""

    def show_inventory_for_label_printing(self, inventory_items):
        self.full_inventory = inventory_items
        self.ids.label_rv.data = self.generate_data_for_rv(inventory_items)

    def remove_from_queue(self, item_name):
        removed, is_empty = self.label_printer.remove_from_queue(item_name)
        if removed:
            if is_empty:
                self.print_queue_popup.dismiss()
            else:
                self.print_queue_popup.dismiss()
                self.show_print_queue()
        else:
            print("Item not found in queue")

    def handle_scanned_barcode(self, barcode):
        barcode = barcode.strip()

        self.ids.label_search_input.text = barcode

    def show_print_queue(self):
        queue_data = [
            {
                "name": item["name"],
                "quantity": str(item["quantity"]),
            }
            for item in self.label_printer.print_queue
        ]

        queue_layout = LabelQueueLayout()
        queue_layout.ids["label_queue_rv"].data = [
            {
                "name": item["name"],
                "quantity": str(item["quantity"]),
                "optional_text": item["optional_text"],
                "remove_callback": self.remove_from_queue,
                "quantity_changed_callback": self.update_print_queue_quantity,
                "add_label_text_callback": self.update_print_queue_with_label_text,
            }
            for item in self.label_printer.print_queue
        ]

        btn_layout = BoxLayout(orientation="horizontal", spacing=10)
        btn_layout.add_widget(MDRaisedButton(text="Print Now", on_press=self.print_now))
        btn_layout.add_widget(MDRaisedButton(text="Cancel", on_press=self.cancel_print))
        btn_layout.add_widget(
            MDRaisedButton(text="Clear Queue", on_press=self.clear_queue)
        )
        queue_layout.add_widget(btn_layout)
        self.print_queue_popup = Popup(
            title="Print Queue", content=queue_layout, size_hint=(0.8, 0.6)
        )

        self.print_queue_popup.open()

    def update_print_queue_quantity(self, item_name, new_quantity):
        self.label_printer.update_queue_item_quantity(item_name, new_quantity)

    def clear_queue(self, instance):
        self.label_printer.clear_queue()
        self.print_queue_popup.dismiss()

    def print_now(self, instance):
        self.label_printer.process_queue()


    def cancel_print(self, instance):
        self.print_queue_popup.dismiss()

    def generate_data_for_rv(self, items):
        return [
            {
                "barcode": str(item[0]),
                "name": item[1],
                "price": str(item[2]),
                "label_printer": self.label_printer,
            }
            for item in items
        ]

    def filter_inventory(self, query):
        if query:
            query = query.lower()
            filtered_items = []
            for item in self.full_inventory:
                barcode_match = query in str(item[0]).lower()
                name_match = query in item[1].lower()
                if barcode_match or name_match:
                    filtered_items.append(item)
        else:
            filtered_items = self.full_inventory

        self.ids.label_rv.data = self.generate_data_for_rv(filtered_items)


class LabelPrinter:
    def __init__(self, ref):
        self.print_queue = []
        self.app = ref


    def add_to_queue(self, barcode, name, price, quantity):
        try:
            self.print_queue.append(
                {
                    "barcode": barcode,
                    "name": name,
                    "price": price,
                    "quantity": int(quantity),
                    "optional_text": "",
                }
            )
        except Exception as e:
            print(f"Error adding labels to the queue. Probably tried to add 0 \n{e}")

    def update_queue_item_quantity(self, name, new_quantity):
        for item in self.print_queue:
            if item["name"] == name:
                item["quantity"] = new_quantity
                break

    def clear_queue(self):
        self.print_queue.clear()



    def print_barcode_label(
        self, barcode_data, item_price, save_path, include_text=False, optional_text=""
    ):
        label_width, label_height = 202, 202
        barcode_y_position = 35

        UPC = barcode.get_barcode_class("upc")
        writer = ImageWriter()

        upc = UPC(barcode_data, writer=writer)

        barcode_image = upc.render(
            {
                "module_width": 0.17,
                "module_height": 10 if not include_text else 8,
                "font_size": 4,
                "dpi": 300,
                "write_text": False,
            }
        )

        label_image = Image.new("RGB", (label_width, label_height), "white")
        draw = ImageDraw.Draw(label_image)

        font_size = 33
        font = ImageFont.truetype("/usr/share/fonts/TTF/Arialbd.TTF", font_size)
        text = f"${item_price}"
        text_bbox = draw.textbbox((0, 0), text, font=font)
        text_width = text_bbox[2] - text_bbox[0]
        x_text = (label_width - text_width) / 2
        draw.text((x_text, 0), text, fill="black", font=font)

        barcode_width, barcode_height = barcode_image.size
        barcode_position = ((label_width - barcode_width) // 2, barcode_y_position)
        label_image.paste(barcode_image, barcode_position)

        if include_text and optional_text:
            additional_text_font_size = 30
            additional_font = ImageFont.truetype(
                "/usr/share/fonts/TTF/Arial.TTF", additional_text_font_size
            )
            additional_text_bbox = draw.textbbox(
                (0, 0), optional_text, font=additional_font
            )
            additional_text_width = additional_text_bbox[2] - additional_text_bbox[0]
            x_additional_text = (label_width - additional_text_width) / 2
            additional_text_y_position = barcode_y_position + barcode_height + 10
            draw.text(
                (x_additional_text, additional_text_y_position),
                optional_text,
                fill="black",
                font=additional_font,
            )

        #label_image.show()
        qlr = brother_ql.BrotherQLRaster("QL-710W")
        qlr.exception_on_warning = True
        convert(qlr=qlr, images=[label_image], label="23x23", cut=False)
        try:
            send(
                instructions=qlr.data,
                printer_identifier="usb://0x04F9:0x2043",
                backend_identifier="pyusb",
            )
            return True
        except Exception as e:
            self.app.popup_manager.catch_label_printing_errors(e)
            return False

    def process_queue(self):
        self.print_success = True

        for item in self.print_queue:
            include_text = "optional_text" in item and item["optional_text"] != ""
            optional_text = item.get("optional_text", "")
            for _ in range(item["quantity"]):
                success = self.print_barcode_label(
                    item["barcode"],
                    item["price"],
                    f"{item['name']}_label.png",
                    include_text=include_text,
                    optional_text=optional_text,
                )
                if not success:
                    self.print_success = False

        if self.print_success:
            self.print_queue.clear()
            self.app.label_manager.print_queue_popup.dismiss()

    def remove_from_queue(self, name):
        for i, item in enumerate(self.print_queue):
            if item["name"] == name:
                self.print_queue.pop(i)
                return True, len(self.print_queue) == 0
        return False, False


class PrintQueueRow(BoxLayout):
    name = StringProperty()
    quantity = StringProperty()
    remove_callback = ObjectProperty()
    quantity_changed_callback = ObjectProperty()
    add_label_text_callback = ObjectProperty()
    optional_text = StringProperty()

    def on_remove_button_press(self):
        if self.remove_callback:
            self.remove_callback(self.name)

    def add_label_text(self):
        add_lable_layout = BoxLayout(orientation="vertical")
        add_label_text_layout = BoxLayout(orientation="vertical")
        add_label_text_label = Label(text="15 Characters Max")
        self.add_label_text_input = TextInput(size_hint=(1, 0.4))
        add_label_text_layout.add_widget(add_label_text_label)
        add_label_text_layout.add_widget(self.add_label_text_input)
        add_label_button_layout = BoxLayout(orientation="horizontal", spacing=5)
        add_label_confirm_button = MDRaisedButton(
            text="Confirm", on_press=lambda x: self.on_add_label_confirm_button_press()
        )
        add_label_cancel_button = MDRaisedButton(
            text="Cancel", on_press=lambda x: self.add_label_popup.dismiss()
        )
        add_label_button_layout.add_widget(add_label_confirm_button)
        add_label_button_layout.add_widget(add_label_cancel_button)
        add_lable_layout.add_widget(add_label_text_layout)
        add_lable_layout.add_widget(add_label_button_layout)
        self.add_label_popup = self.create_focus_popup(
            title="Add Text to Selected Label",
            content=add_lable_layout,
            textinput=self.add_label_text_input,
            pos_hint={"top": 1},
            size_hint=(0.4, 0.4),
        )
        self.add_label_popup.open()

    def create_focus_popup(self, title, content, textinput, size_hint, pos_hint={}):
        popup = FocusPopup(
            title=title, content=content, size_hint=size_hint, pos_hint=pos_hint
        )
        popup.focus_on_textinput(textinput)
        return popup

    def on_add_label_confirm_button_press(self):
        optional_text = self.add_label_text_input.text

        if self.add_label_text_callback:
            self.add_label_text_callback(self.name, optional_text)
        self.add_label_popup.dismiss()

    def increment_quantity(self):
        new_quantity = int(self.quantity) + 1
        self.quantity = str(new_quantity)
        if self.quantity_changed_callback:
            self.quantity_changed_callback(self.name, new_quantity)

    def decrement_quantity(self):
        new_quantity = max(1, int(self.quantity) - 1)
        self.quantity = str(new_quantity)
        if self.quantity_changed_callback:
            self.quantity_changed_callback(self.name, new_quantity)


class LabelQueueLayout(BoxLayout):
    def __init__(self, **kwargs):
        super(LabelQueueLayout, self).__init__(**kwargs)

        self.bind(children=self.update_height)

        self.orientation = "vertical"
        self.height = self.minimum_height

    def update_height(self, *args):
        self.height = len(self.children) * dp(48)


class FocusPopup(Popup):
    def focus_on_textinput(self, textinput):
        self.textinput_to_focus = textinput

    def on_open(self):
        if hasattr(self, "textinput_to_focus"):
            self.textinput_to_focus.focus = True


if __name__ == "__main__":
    printer = LabelPrinter()
    printer.print_barcode_label("123456789012", 9.99, "test.png")
