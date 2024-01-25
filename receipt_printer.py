from datetime import datetime
from escpos.printer import Usb
from PIL import Image
from escpos.config import Config
import textwrap


class ReceiptPrinter:
    def __init__(self, config_path):
        self.config_handler = Config()
        self.config_handler.load(config_path)
        self.printer = self.config_handler.printer()

    def print_receipt(self, order_details):
        logo = Image.open("logo.png")
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
        self.printer.textln(order_details["order_id"])
        self.printer.cut()

    def close(self):
        self.printer.close()


if __name__ == "__main__":
    printer = ReceiptPrinter("receipt_printer_config.yaml")
    order_details = {
        "items": {
            "item1": {"name": "Item 1", "quantity": 2, "total_price": 10.00},
            "item2": {"name": "Item 2", "quantity": 1, "total_price": 5.00},
        },
        "subtotal": 15.00,
        "discount": 0,
        "tax_amount": 1.50,
        "total_with_tax": 16.50,
        "order_id": "12345",
    }
    printer.print_receipt(order_details)
    printer.close()
