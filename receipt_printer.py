from datetime import datetime
from escpos.printer import Usb
from PIL import Image, ImageDraw, ImageFont
from escpos.config import Config
import textwrap


class ReceiptPrinter:
    def __init__(self, config_path):
        self.config_handler = Config()
        self.config_handler.load(config_path)
        self.printer = self.config_handler.printer()

    def create_receipt_image(self, order_details):
        print(order_details)
        font_size = 25
        alt_font_size = 18
        line_spacing = 50
        initial_height = 250
        max_line_width = 25

        font = ImageFont.truetype(
            "/usr/share/fonts/TTF/JetBrainsMono-ExtraBold.ttf", font_size
        )
        alt_font = ImageFont.truetype(
            "/usr/share/fonts/TTF/JetBrainsMono-ExtraBold.ttf", alt_font_size
        )

        def wrap_text(text, line_width):
            return textwrap.wrap(text, line_width)

        num_lines = 4
        for item in order_details["items"].values():
            wrapped_item_name = wrap_text(item["name"], max_line_width)
            num_lines += len(wrapped_item_name)

        if order_details["discount"] > 0:
            num_lines += 1

        total_height = initial_height + (num_lines * line_spacing) + 50

        canvas = Image.new("RGB", (600, total_height), color="white")
        draw = ImageDraw.Draw(canvas)
        date = str(datetime.now().replace(microsecond=0))

        logo = Image.open("logo.png")
        canvas.paste(logo, (100, -60))

        y_position = initial_height
        draw.text((100, 200), date, fill="black", font=font)

        for item in order_details["items"].values():
            wrapped_item_name = wrap_text(item["name"], max_line_width)
            for line_index, line in enumerate(wrapped_item_name):
                if line_index == len(wrapped_item_name) - 1:
                    item_line = (
                        f"{line} x{item['quantity']}  ${item['total_price']:.2f}"
                    )
                else:
                    item_line = line

                draw.text((10, y_position), item_line, fill="black", font=font)
                y_position += line_spacing

        draw.text(
            (10, y_position + 20),
            f"Subtotal: ${order_details['subtotal']:.2f}",
            fill="black",
            font=font,
        )
        y_position += line_spacing

        if order_details["discount"] > 0:
            draw.text(
                (10, y_position),
                f"Discount: -${order_details['discount']:.2f}",
                fill="black",
                font=font,
            )
            y_position += line_spacing

        draw.text(
            (10, y_position),
            f"Tax: ${order_details['tax_amount']:.2f}",
            fill="black",
            font=font,
        )
        y_position += line_spacing
        draw.text(
            (10, y_position),
            f"Total: ${order_details['total_with_tax']:.2f}",
            fill="black",
            font=font,
        )
        y_position += line_spacing
        draw.text(
            (10, y_position + 50),
            f"{order_details['order_id']}",
            fill="black",
            font=alt_font,
        )
        return canvas

    def print_image(self, img_source):
        try:
            self.printer.image(img_source)
            self.printer.cut()
        except:
            pass


if __name__ == "__main__":
    printer = ReceiptPrinter("receipt_printer_config.yaml")
    receipt_image = printer.create_receipt_image()
    printer.print_image(receipt_image)
