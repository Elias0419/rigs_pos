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

        # Generate barcode
        barcode_img = upc_a(barcode_data, writer=barcode_writer).render()

        # Create an empty image
        label_image = Image.new('RGB', (label_width, label_height), color='white')
        draw = ImageDraw.Draw(label_image)

        # Draw price text
        font = ImageFont.truetype(font_path, font_size)
        price_text = f"${float(item_price):.2f}"
        text_width = draw.textlength(price_text, font=font)
        text_height = 1.2 * font_size
        text_position = ((label_width - text_width) / 2, margin)
        draw.text(text_position, price_text, font=font, fill="black")

        # Place barcode
        barcode_target_width = label_width - 2 * margin
        # Calculate new height while maintaining aspect ratio
        barcode_aspect_ratio = barcode_img.height / barcode_img.width
        barcode_target_height = int(barcode_target_width * barcode_aspect_ratio)

        # Ensure barcode height does not exceed label height limit
        barcode_target_height = min(barcode_target_height, label_height * 3 // 4 - 2 * margin)

        barcode_img = barcode_img.resize((barcode_target_width, barcode_target_height))
        barcode_position_y = label_height // 4 + (label_height * 3 // 4 - barcode_target_height) // 2
        label_image.paste(barcode_img, (margin, barcode_position_y))


        # Save the image
        label_image.save(save_path)

        # Printing logic (as provided in your code)
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
