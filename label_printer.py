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
from kivymd.uix.recycleview import RecycleView
from kivy.metrics import dp


class LabelPrintingRow(BoxLayout):
    barcode = StringProperty()
    name = StringProperty()
    price = StringProperty()
    label_printer = ObjectProperty()

    def add_to_print_queue(self):
        self.show_label_popup()

    def show_label_popup(self):
        content = BoxLayout(orientation="vertical")
        quantity_input = TextInput(text="1",size_hint=(1,0.4), input_filter="int")
        content.add_widget(Label(text=f"Enter quantity for {self.name}"))
        content.add_widget(quantity_input)
        btn_layout = BoxLayout(orientation="horizontal", size_hint=(0.8,0.8), spacing=10)
        popup = Popup(title="Label Quantity",  content=content, size_hint=(0.8, 0.4),  pos_hint={"top": 1})
        btn_layout.add_widget(
            MDRaisedButton(
                text="Add",
                size_hint=(0.8,0.8),
                on_press=lambda *args: self.on_add_button_press(quantity_input, popup),
            )
        )
        btn_layout.add_widget(
        MDRaisedButton(
            text="Cancel",
            size_hint=(None,0.8),

            on_press=lambda *args: popup.dismiss(),
            )
        )
        content.add_widget(btn_layout)

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

    def detach_from_parent(self):
        if self.parent:
            self.parent.remove_widget(self)

    def clear_search(self):
        self.ids.label_search_input.text = ""

    def show_inventory_for_label_printing(self, inventory_items):
        self.full_inventory = inventory_items
        self.ids.label_rv.data = self.generate_data_for_rv(inventory_items)

    def remove_from_queue(self, item_name):
        self.label_printer.remove_from_queue(item_name)
        self.show_print_queue()


    def handle_scanned_barcode(self, barcode):
        barcode = barcode.strip()

        self.ids.label_search_input.text = barcode

    def show_print_queue(self):
        queue_data = [
            {
                'name': item['name'],
                'quantity': str(item['quantity']),
            }
            for item in self.label_printer.print_queue
        ]
        print("Queue Data:", queue_data)  # Debugging
        queue_layout = LabelQueueLayout()
        queue_layout.ids['label_queue_rv'].data = [
            {
                'name': item['name'],
                'quantity': str(item['quantity']),
                'remove_callback': self.remove_from_queue,
                'quantity_changed_callback': self.update_print_queue_quantity,
            }
            for item in self.label_printer.print_queue
        ]

        btn_layout = BoxLayout(orientation="horizontal", spacing=10)
        btn_layout.add_widget(MDRaisedButton(text="Print Now", on_press=self.print_now))
        btn_layout.add_widget(MDRaisedButton(text="Cancel", on_press=self.cancel_print))
        btn_layout.add_widget(MDRaisedButton(text="Clear Queue", on_press=self.clear_queue))
        queue_layout.add_widget(btn_layout)
        self.print_queue_popup = Popup(
            title="Print Queue", content=queue_layout, size_hint=(0.8, 0.6)
        )
        print("Popup content:", self.print_queue_popup.content)
        self.print_queue_popup.open()

    def update_print_queue_quantity(self, item_name, new_quantity):
        self.label_printer.update_queue_item_quantity(item_name, new_quantity)

    def clear_queue(self, instance):
        self.label_printer.clear_queue()
        self.print_queue_popup.dismiss()

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

        self.ids.label_rv.data = self.generate_data_for_rv(filtered_items)


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

    def update_queue_item_quantity(self, name, new_quantity):
        for item in self.print_queue:
            if item['name'] == name:
                item['quantity'] = new_quantity
                break

    def clear_queue(self):
        self.print_queue.clear()
        print("Print queue cleared")  # Debugging print


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

class PrintQueueRow(BoxLayout):
    name = StringProperty()
    quantity = StringProperty()
    remove_callback = ObjectProperty()
    quantity_changed_callback = ObjectProperty()

    def on_remove_button_press(self):
        if self.remove_callback:
            self.remove_callback(self.name)

    def increment_quantity(self):
        new_quantity = int(self.quantity) + 1
        self.quantity = str(new_quantity)
        if self.quantity_changed_callback:
            self.quantity_changed_callback(self.name, new_quantity)
        print(f"Incremented: {self.name} to {new_quantity}")


    def decrement_quantity(self):
        new_quantity = max(1, int(self.quantity) - 1)
        self.quantity = str(new_quantity)
        if self.quantity_changed_callback:
            self.quantity_changed_callback(self.name, new_quantity)
        print(f"Decremented: {self.name} to {new_quantity}")




class LabelQueueLayout(BoxLayout):
    def __init__(self, **kwargs):
        super(LabelQueueLayout, self).__init__(**kwargs)
        print("RecycleView ID:", self.ids.get('label_queue_rv'))  # Debugging
        self.bind(children=self.update_height)

        self.orientation = 'vertical'
        self.height = self.minimum_height
        print("Layout size:", self.size)

    def update_height(self, *args):
        self.height = len(self.children) * dp(48)


if __name__ == "__main__":
    printer = LabelPrinter()
    printer.print_barcode_label("123456789012", 9.99, "test.png")
