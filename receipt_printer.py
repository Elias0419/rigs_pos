from datetime import datetime
from PIL import Image
import escpos
import base64
import logging
from escpos.config import Config as _BaseConfig
from escpos import exceptions, printer
import yaml

class Config(_BaseConfig):
    def load(self, config_source=None, *, is_yaml_str: bool = False):

        if is_yaml_str or isinstance(config_source, (bytes, bytearray)):
            self._reset_config()
            try:
                cfg = yaml.safe_load(config_source)
            except yaml.YAMLError:
                raise exceptions.ConfigSyntaxError("Error parsing YAML")

            if not isinstance(cfg, dict):
                raise exceptions.ConfigSyntaxError("Error parsing YAML")

            if "printer" in cfg:
                pc = dict(cfg["printer"])
                self._printer_name = pc.pop("type").title()
                if not self._printer_name or not hasattr(printer, self._printer_name):
                    raise exceptions.ConfigSyntaxError(
                        f'Printer type "{self._printer_name}" is invalid'
                    )
                self._printer_config = pc

            self._has_loaded = True
            return

        return super().load(config_source)

logger = logging.getLogger("rigs_pos")

PRINTER_YAML = """
printer:
    type: "Usb"
    model: "TM-T20III"
    connection: "usb"
    idVendor: 0x04b8
    idProduct: 0x0e28
    media.width:
        pixel: 612
"""

class ReceiptPrinter:
    def __init__(self, ref):
        self.config_handler = Config()
        self.config_handler.load(PRINTER_YAML.encode('utf-8'))
        self.app = ref

        try:
            self.printer = self.config_handler.printer()
        except Exception as e:
            logger.warn(e)

    def re_initialize_after_error(self, order_details):
        self.app.utilities.initialize_receipt_printer()
        success = self.print_receipt(order_details)
        if success:
            self.app.popup_manager.receipt_errors_popup.dismiss()

    def uuid_to_decimal_string(self, uuid_str):
        uuid_bytes = uuid_str.replace("-", "").encode()
        base64_bytes = base64.b64encode(uuid_bytes)
        return str(base64_bytes.decode("utf-8")).replace("=", "")

    def print_receipt(self, order_details, reprint=False, draft=False, qr_code=False):
        if len(order_details.get("items", {})) == 0:
            return
        logo = self._rcpt_load_logo()

        try:
            date_str = self._rcpt_print_header(logo)
            self._rcpt_print_items(order_details)
            self._rcpt_print_totals(order_details, draft)
            self._rcpt_print_review_and_barcode(order_details, draft, qr_code)
            self._rcpt_print_footer(order_details, reprint, draft, date_str)
            self.printer.cut()
            return True
        except Exception as e:
            self.app.popup_manager.catch_receipt_printer_errors(e, order_details)
            return False

    def _rcpt_load_logo(self):
        try:
            return Image.open("images/rigs_logo_scaled.png")
        except Exception as e:
            logger.warn("Error loading logo:", e)
            return None

    def _rcpt_print_header(self, logo):

        self.printer.image(logo, (200, -60))

        date_str = str(datetime.now().replace(microsecond=0))

        self.printer.textln()
        self.printer.set(align="center", font="a", bold=True)
        self.printer.textln("RIGS SMOKE SHOP")
        self.printer.set(align="center", font="a", normal_textsize=True, bold=False)
        self.printer.textln("402C Main Street")
        self.printer.textln("Wakefield, RI")
        self.printer.textln("401-363-9866")
        self.printer.textln()

        self.printer.set(align="left", font="a", bold=False)
        return date_str

    def _rcpt_print_items(self, order_details):
        max_line_width = 48

        for item in order_details["items"].values():
            if item["quantity"] > 1:
                item_name = f"{item['name']} x{item['quantity']}"
            else:
                item_name = item["name"]

            price = f"${item['total_price']:.2f}"
            spaces = " " * max(0, max_line_width - len(item_name) - len(price))
            item_line = item_name + spaces + price

            self.printer.textln(item_line)

            try:
                disc_amt = float(item.get("discount", {}).get("amount", 0) or 0)
            except Exception:
                disc_amt = 0.0

            if disc_amt > 0:
                discount_text = f"Discount: -${disc_amt:.2f}"
                spaces = " " * max(0, max_line_width - len(discount_text))
                self.printer.textln(spaces + discount_text)

            self.printer.textln()

    def _rcpt_print_totals(self, order_details, draft):
        self.printer.set(align="right", font="a", bold=True)
        self.printer.textln()

        self.printer.textln(f"Subtotal: ${order_details['subtotal']:.2f}")

        try:
            order_disc = float(order_details.get("discount", 0) or 0)
        except Exception:
            order_disc = 0.0
        if order_disc > 0:
            self.printer.textln(f"Discount: -${order_disc:.2f}")

        self.printer.textln(f"Tax: ${order_details['tax_amount']:.2f}")
        self.printer.textln(f"Total: ${order_details['total_with_tax']:.2f}")

        if not draft:
            pm = order_details.get("payment_method")
            if pm == "Cash":
                self.printer.textln(f"Cash: ${order_details['amount_tendered']:.2f}")
                self.printer.textln(f"Change: ${order_details['change_given']:.2f}")
            elif pm == "Split":
                self.printer.textln("Split Payment")
            elif pm == "Debit":
                self.printer.textln("Debit Payment")
            else:
                self.printer.textln("Credit Payment")

    def _rcpt_print_review_and_barcode(self, order_details, draft, qr_code):
        self.printer.set(align="center", font="b", bold=False)
        self.printer.textln()

        barcode_data = str(order_details["order_id"])
        short_uuid = barcode_data[:13]
        barcode_data_short = "{B" + short_uuid

        if not draft:
            if qr_code:
                review_url = "https://g.page/r/CfHmpKJDLRqXEBM/review"
                self.printer.set(align="center", font="a", bold=False)
                self.printer.textln()
                self.printer.textln("Thanks for supporting small business in RI!")
                self.printer.set(align="center", font="a", bold=True)
                self.printer.textln("Scan to review us on Google!")
                self.printer.set(align="center", font="a", bold=False)
                self.printer.textln("It really helps!")
                self.printer.qr(review_url, native=True, size=4)
                self.printer.set(align="center", font="a", bold=False)
                self.printer.textln("g.page/r/CfHmpKJDLRqXEBM/review")

            self.printer.barcode(barcode_data_short, "CODE128", pos="OFF")

    def _rcpt_print_footer(self, order_details, reprint, draft, date_str):
        self.printer.textln()
        self.printer.textln(date_str)
        self.printer.textln(order_details["order_id"])

        if reprint:
            self.printer.set(align="center", font="a", bold=True)
            self.printer.textln()
            self.printer.textln("Copy")

        if draft:
            self.printer.set(align="center", font="a", bold=True)
            self.printer.textln()
            self.printer.textln("UNPAID")

    def print_raw_text(self, text):

        if not hasattr(self, "printer"):
            logger.warn("Printer not initialized.")
            return False

        try:
            self.printer.set(align="left", font="a", bold=False)
            for line in text.splitlines():
                self.printer.textln(line)
            self.printer.cut()
            return True
        except Exception as e:
            self.app.popup_manager.catch_receipt_printer_errors(e, text)
            return False

    def close(self):
        try:
            self.printer.close()
        except:
            pass


if __name__ == "__main__":
    text = """

    """
    try:
        printer = ReceiptPrinter(
            None, "/home/rigs/rigs_pos/receipt_printer_config.yaml"
        )
        printer.print_raw_text(text)
    except (FileNotFoundError, escpos.exceptions.ConfigNotFoundError):
        print("No config file; printer not initialized")
