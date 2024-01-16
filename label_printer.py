import barcode
from barcode.writer import ImageWriter
from barcode.upc import UniversalProductCodeA as upc_a
from PIL import Image, ImageDraw, ImageFont
import brother_ql
from brother_ql.conversion import convert
from brother_ql.backends.helpers import send


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
        desired_barcode_width = barcode_width / 800  # for example
        desired_barcode_height = barcode_height - 20
        barcode_image = upc.render(
            {
                "module_width": desired_barcode_width,
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
        # Printing logic
        qlr = brother_ql.BrotherQLRaster('QL-710W')
        qlr.exception_on_warning = True
        convert(qlr=qlr, images=[label_image], label='23x23', cut=False)
        send(instructions=qlr.data, printer_identifier='usb://0x04F9:0x2043', backend_identifier='pyusb')

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
