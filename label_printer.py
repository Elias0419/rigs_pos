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
        font_path = "/usr/share/fonts/TTF/Hack-Regular.ttf"
        font_size = 25
        barcode_writer = ImageWriter()

        # Try converting price to float and format it
        try:
            price_float = float(item_price)
            price_text = f"${price_float:.2f}"
        except ValueError:
            print(f"Invalid price format: {item_price}")
            return

        # Generate the barcode image
        barcode_img = upc_a(barcode_data, writer=barcode_writer).render()

        # Calculate barcode size to fit the bottom 3/4 of the label
        barcode_width = label_width - 2 * margin
        barcode_height = int(3 * (label_height - 2 * margin) / 4)

        barcode_img = barcode_img.resize((barcode_width, barcode_height), Image.Resampling.LANCZOS)

        # Create the label image
        label_image = Image.new("L", (label_width, label_height), color=255)
        draw = ImageDraw.Draw(label_image)
        font = ImageFont.truetype(font_path, font_size)

        # Calculate text positioning for the top 1/4
        price_text_width = draw.textlength(price_text, font=font)
        price_text_height = font.getmetrics()[0]
        price_x_position = (label_width - price_text_width) // 2
        price_y_position = margin

        # Calculate barcode positioning
        barcode_x_position = margin
        barcode_y_position = label_height - barcode_height - margin

        # Draw text and paste barcode
        draw.text((price_x_position, price_y_position - price_text_height - margin), price_text, font=font, fill=0)
        label_image.paste(barcode_img, (barcode_x_position, barcode_y_position))

        # Save and print the label
        label_image.save(save_path)
        qlr = brother_ql.BrotherQLRaster('QL-710W')
        qlr.exception_on_warning = True
        convert(qlr=qlr, images=[label_image], label='23x23', cut=False)
        send(instructions=qlr.data, printer_identifier='usb://0x04F9:0x2043', backend_identifier='pyusb')



    def process_queue(self):
        print("we are inside process queue")

        for item in self.print_queue:
            print("process_queue", item)

            for _ in range(item["quantity"]):
                self.print_barcode_label(
                    item["barcode"], item["price"], f"{item['name']}_label.png"
                )
        self.print_queue.clear()
