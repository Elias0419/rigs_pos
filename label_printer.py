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
        margin = 10
        font_path = "/usr/share/fonts/TTF/Hack-Bold.ttf"
        font_size = 25
        barcode_writer = ImageWriter()

        try:
            price_float = float(item_price)
            price_text = f"${price_float:.2f}"
        except ValueError:
            print(f"Invalid price format: {item_price}")
            return  # Exit if the price format is wrong

        barcode_img = upc_a(barcode_data, writer=barcode_writer).render(
            writer_options={"module_height": 15.0}
        )
        barcode_img_width = label_width - 2 * margin
        barcode_img_height = barcode_img.size[1] * (
            barcode_img_width / barcode_img.size[0]
        )

        barcode_img = barcode_img.resize(
            (barcode_img_width, int(barcode_img_height)), Image.Resampling.LANCZOS
        )

        label_image = Image.new("L", (label_width, label_height), color=255)
        draw = ImageDraw.Draw(label_image)
        font = ImageFont.truetype(font_path, font_size)

        price_text_width = draw.textlength(price_text, font=font)
        price_text_height = font.getmetrics()[0]

        price_x_position = (label_width - price_text_width) // 2
        price_y_position = margin  # Start at top margin

        barcode_x_position = (label_width - barcode_img_width) // 2
        barcode_y_position = (
            price_y_position + price_text_height + margin
        )  # Add a margin between price and barcode

        draw.text((price_x_position, price_y_position), price_text, font=font, fill=0)
        label_image.paste(barcode_img, (barcode_x_position, barcode_y_position))

        save_path = "test.png"
        label_image.save(save_path)
        # qlr = brother_ql.BrotherQLRaster('QL-710W')
        # qlr.exception_on_warning = True
        # convert(qlr=qlr, images=[label_image], label='23x23')
        # send(instructions=qlr.data, printer_identifier='usb://0x04F9:0x2043', backend_identifier='pyusb')

    def process_queue(self):
        print("we are inside process queue")

        for item in self.print_queue:
            print("process_queue", item)

            for _ in range(item["quantity"]):
                self.print_barcode_label(
                    item["barcode"], item["price"], f"{item['name']}_label.png"
                )
        self.print_queue.clear()
