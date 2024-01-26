from datetime import datetime
from escpos.printer import Usb
from PIL import Image
from escpos.config import Config
import textwrap

import io

class ReceiptPrinter:
    def __init__(self, config_path):
        self.config_handler = Config()
        self.config_handler.load(config_path)
        try:
            self.printer = self.config_handler.printer()
        except Exception as e:
            print(e)
            pass



    def print_receipt(self, order_details):
        logo = Image.open("logo.png")
        try:
            self.printer.image(logo, (100, -60))

            date = str(datetime.now().replace(microsecond=0))
            self.printer.set(align="center", font="a")
            self.printer.textln(date)
            self.printer.textln()

            max_line_width = 48
            self.printer.set(align="left", font="a", bold=False)

            for item in order_details["items"].values():
                if item["quantity"] > 1:
                    item_name = f"{item['name']} x{item['quantity']}"
                else:
                    item_name = item["name"]
                price = f"${item['total_price']:.2f}"
                spaces = " " * (max_line_width - len(item_name) - len(price))
                item_line = item_name + spaces + price

                self.printer.textln(item_line)
                self.printer.textln()
            self.printer.set(align="center", font="a", bold=True)
            self.printer.textln()
            self.printer.textln(f"Subtotal: ${order_details['subtotal']:.2f}")

            if order_details["discount"] > 0:
                self.printer.textln(f"Discount: -${order_details['discount']:.2f}")

            self.printer.textln(f"Tax: ${order_details['tax_amount']:.2f}")
            self.printer.textln(f"Total: ${order_details['total_with_tax']:.2f}")

            self.printer.set(align="center", font="b", bold=False)
            self.printer.textln()
            #barcode_data = "{Bwhat_the_fuck"
            barcode_data = str(order_details["order_id"])
            short_uuid = barcode_data[:14]   # test truncation length
            barcode_data_short = "{B" + short_uuid
            self.printer.barcode(barcode_data_short, "CODE128")



            self.printer.textln()
            self.printer.textln(order_details["order_id"])
            self.printer.cut()
        except Exception as e:
            print(e)
            pass

    def close(self):
        try:
            self.printer.close()
        except:
            pass


if __name__ == "__main__":
    printer = ReceiptPrinter("receipt_printer_config.yaml")

    printer.print_png_image("barcodes.png")
    printer.close()
