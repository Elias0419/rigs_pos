import barcode
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


class LabelPrintingRow(BoxLayout):
    barcode = StringProperty()
    name = StringProperty()
    price = StringProperty()
    label_printer = ObjectProperty()

    def add_to_print_queue(self):
        self.show_label_popup()

    def show_label_popup(self):
        content = BoxLayout(orientation="vertical", padding=10)
        quantity_input = TextInput(text="1", input_filter="int")
        content.add_widget(Label(text=f"Enter quantity for {self.name}"))
        content.add_widget(quantity_input)
        content.add_widget(
            MDRaisedButton(
                text="Add",
                on_press=lambda *args: self.on_add_button_press(quantity_input, popup),
            )
        )
        popup = Popup(title="Label Quantity", content=content, size_hint=(0.8, 0.4))
        popup.open()

    def on_add_button_press(self, quantity_input, popup):
        self.add_quantity_to_queue(quantity_input.text)
        popup.dismiss()

    def add_quantity_to_queue(self, quantity):
        self.label_printer.add_to_queue(self.barcode, self.name, self.price, quantity)


class LabelPrintingView(BoxLayout):
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(LabelPrintingView, cls).__new__(cls, *args, **kwargs)
        return cls._instance

    def __init__(self, **kwargs):
        if not hasattr(self, "_init"):
            super(LabelPrintingView, self).__init__(**kwargs)
            self.full_inventory = []
            self.label_printer = LabelPrinter()

            self._init = True

    def clear_search(self):
        self.ids.label_search_input.text = ""

    def show_inventory_for_label_printing(self, inventory_items):
        self.full_inventory = inventory_items
        self.rv.data = self.generate_data_for_rv(inventory_items)

    def handle_scanned_barcode(self, barcode):
        barcode = barcode.strip()

        self.ids.label_search_input.text = barcode

    def show_print_queue(self):
        content = BoxLayout(orientation="vertical", spacing=10)
        for item in self.label_printer.print_queue:
            content.add_widget(Label(text=f"{item['name']} x {item['quantity']}"))

        content.add_widget(MDRaisedButton(text="Print Now", on_press=self.print_now))
        content.add_widget(MDRaisedButton(text="Cancel", on_press=self.cancel_print))

        self.print_queue_popup = Popup(
            title="Print Queue", content=content, size_hint=(0.8, 0.6)
        )
        self.print_queue_popup.open()

    def print_now(self, instance):
        self.label_printer.process_queue()
        self.print_queue_popup.dismiss()

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

        self.rv.data = self.generate_data_for_rv(filtered_items)


class LabelPrinter:
    def __init__(self):
        self.print_queue = []

    def add_to_queue(self, barcode, name, price, quantity):
        self.print_queue.append(
            {
                "barcode": barcode,
                "name": name,
                "price": price,
                "quantity": int(quantity),
            }
        )

    def print_barcode_label(self, barcode_data, item_price, save_path):
        label_width, label_height = 202, 202

        UPC = barcode.get_barcode_class("upc")
        writer = ImageWriter()
        upc = UPC(barcode_data, writer=writer)
        barcode_width, barcode_height = writer.calculate_size(len(barcode_data), 1)
        d_barcode_width = barcode_width / 800

        barcode_image = upc.render(
            {
                "module_width": d_barcode_width,
                "module_height": 10,
                "font_size": 4,
                "text_distance": 2,
                "dpi": 300,
            }
        )

        label_image = Image.new("RGB", (label_width, label_height), "white")
        draw = ImageDraw.Draw(label_image)

        font = ImageFont.truetype("/usr/share/fonts/TTF/Arialbd.TTF", 33)

        draw.text((60, 0), f"{item_price}", fill="black", font=font)

        barcode_position = (-70, 35)
        label_image.paste(barcode_image, barcode_position)

        # label_image.save(save_path)
        qlr = brother_ql.BrotherQLRaster("QL-710W")
        qlr.exception_on_warning = True
        convert(qlr=qlr, images=[label_image], label="23x23", cut=False)
        try:
            send(
                instructions=qlr.data,
                printer_identifier="usb://0x04F9:0x2043",
                backend_identifier="pyusb",
            )
        except ValueError as e:
            print(e)
            pass

    def process_queue(self):
        for item in self.print_queue:
            for _ in range(item["quantity"]):
                self.print_barcode_label(
                    item["barcode"], item["price"], f"{item['name']}_label.png"
                )
        self.print_queue.clear()


if __name__ == "__main__":
    printer = LabelPrinter()
    printer.print_barcode_label("123456789012", 9.99, "test.png")
