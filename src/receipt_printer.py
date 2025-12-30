from datetime import datetime
from PIL import Image
import escpos
import base64
import logging
from typing import Any, Dict
from escpos.config import Config as _BaseConfig
from escpos import exceptions, printer
import yaml

from order_manager import LineItem, Order


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
WIDTH = 48


class ReceiptPrinter:
    def __init__(self, ref):
        self.config_handler = Config()
        self.config_handler.load(PRINTER_YAML.encode("utf-8"))
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

    def _normalize_order_payload(self, order_details: Order) -> Dict[str, Any]:
        if not isinstance(order_details, Order):
            raise TypeError(f"Expected Order instance, got {type(order_details)}")

        # Ensure totals on the Order and each LineItem are up to date.
        order_details.recalculate_totals()

        normalized_items: Dict[str, Dict[str, Any]] = {}
        for item_id, line_item in order_details.items.items():
            if not isinstance(line_item, LineItem):
                raise TypeError(f"Order items must be LineItem instances, got {type(line_item)}")

            line_item.recompute()
            item_dict = {
                "item_id": line_item.item_id,
                "barcode": line_item.barcode,
                "is_custom": line_item.is_custom,
                "name": line_item.name,
                "quantity": int(line_item.quantity),
                "unit_price": float(line_item.unit_price),
                "line_subtotal": float(line_item.line_subtotal),
                "line_discount_total": float(line_item.line_discount_total),
                "total_price": float(line_item.total_price),
            }
            normalized_items[str(item_id)] = item_dict

        tax_amount = float(order_details.tax_amount)
        total_with_tax = order_details.total_with_tax
        if total_with_tax is None:
            total_with_tax = order_details.calculate_total_with_tax()

        payload: Dict[str, Any] = {
            "order_id": str(order_details.order_id),
            "items": normalized_items,
            "subtotal": float(order_details.subtotal),
            "total_discount": float(order_details.total_discount),
            "total": float(order_details.total),
            "tax_rate": float(order_details.tax_rate),
            "tax_amount": tax_amount,
            "total_with_tax": float(total_with_tax),
            "payment_method": order_details.payment_method,
            "amount_tendered": float(order_details.amount_tendered),
            "change_given": float(order_details.change_given),
        }

        return payload

    def print_receipt(self, order_details, reprint=False, draft=False, qr_code=False):
        try:
            normalized_order = self._normalize_order_payload(order_details)
        except Exception as e:
            self.app.popup_manager.catch_receipt_printer_errors(e, order_details)
            return False

        if len(normalized_order.get("items", {})) == 0:
            return
        logo = self._rcpt_load_logo()

        try:
            date_str = self._rcpt_print_header(logo)
            self._rcpt_print_items(normalized_order)
            self._rcpt_print_totals(normalized_order, draft)
            self._rcpt_print_review_and_barcode(normalized_order, draft, qr_code)
            self._rcpt_print_footer(normalized_order, reprint, draft, date_str)
            self.printer.cut()
            return True
        except Exception as e:
            self.app.popup_manager.catch_receipt_printer_errors(e, order_details)
            return False

    def _fmt_line(self, left: str, right: str, width: int = WIDTH) -> str:
        left = (left or "").strip()
        right = (right or "").strip()
        pad = max(1, width - len(left) - len(right))
        return f"{left}{' ' * pad}{right}"

    def _calc_paper_tax_total(self, order_details) -> float:
        total = 0.0
        for e in self._collect_rolling_paper_tax_entries(order_details):
            qty = int(e.get("quantity") or 0)
            per_pack_tax = float(e.get("_total_paper_tax_per_pack", 0.0) or 0.0)
            if qty > 0 and per_pack_tax > 0.0:
                total += per_pack_tax * qty
        return round(total, 2)

    def _collect_rolling_paper_tax_entries(self, order_details):
        entries = []
        items = order_details.get("items", {}) or {}

        for item_id, item in items.items():
            if not item_id:
                continue

            try:
                quantity = int(item.get("quantity", 1) or 0)
            except (TypeError, ValueError):
                quantity = 0
            if quantity <= 0:
                continue

            try:
                lookup_id = str(item_id)
            except Exception:
                lookup_id = item_id

            try:
                details = self.app.db_manager.get_item_details(item_id=lookup_id)
            except Exception:
                details = None

            if not details or not details.get("is_rolling_papers"):
                continue

            papers_per_pack = details.get("papers_per_pack")
            summary = self.app.utilities.build_paper_tax_summary(papers_per_pack)

            if summary["paper_count"] <= 0 or summary["_total_paper_tax_per_pack"] <= 0:
                continue

            summary["quantity"] = quantity
            summary["item_name"] = details.get("name") or item.get("name")
            entries.append(summary)

        return entries

    def _rcpt_print_rolling_paper_tax(self, order_details):
        entries = self._collect_rolling_paper_tax_entries(order_details)
        if not entries:
            return

        WIDTH = 48

        def line_left_right(left: str, right: str) -> str:
            left = (left or "")[:WIDTH]  # safety
            right = (right or "")[:WIDTH]
            pad = max(1, WIDTH - len(left) - len(right))
            return left + (" " * pad) + right

        per_paper_rate = float(entries[0].get("per_paper_tax", 0.0) or 0.0)

        total_tax = 0.0

        self.printer.textln()
        self.printer.set(align="left", font="a", bold=True)
        self.printer.textln(
            line_left_right("RI PAPER TAX", f"@ ${per_paper_rate:.3f}/leaf")
        )
        self.printer.set(align="left", font="a", bold=False)

        for entry in entries:
            qty = int(entry.get("quantity") or 0)
            if qty <= 0:
                continue

            name = (entry.get("item_name") or "Rolling Papers").strip()
            papers = int(entry.get("paper_count") or 0)
            per_pack_tax = float(entry.get("_total_paper_tax_per_pack", 0.0) or 0.0)

            item_tax = per_pack_tax * qty
            total_tax += item_tax

            left = f"{name} x{qty} ({papers}/pack)"
            right = f"${item_tax:.2f}"
            self.printer.textln(line_left_right(left, right))

        if total_tax > 0.0:
            self.printer.set(align="left", font="a", bold=True)
            self.printer.textln(
                line_left_right("RI PAPER TAX TOTAL", f"${total_tax:.2f}")
            )
            self.printer.set(align="right", font="a", bold=True)

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
        self.printer.set(align="center", font="a", bold=False)
        self.printer.textln("402C Main Street")
        self.printer.textln("Wakefield, RI")
        self.printer.textln("401-363-9866")
        self.printer.textln()
        self.printer.textln()
        self.printer.textln()

        self.printer.set(align="left", font="a", bold=False)
        return date_str

    def _rcpt_print_items(self, order_details):
        self.printer.set(align="left", font="a", bold=False)

        for item in order_details["items"].values():
            qty = int(item.get("quantity") or 0)
            name = (item.get("name") or "").strip()
            total_price = float(item.get("total_price") or 0.0)

            # First line: item name (+ qty) in bold, price right
            self.printer.set(align="left", font="a", bold=True)
            label = f"{name} x{qty}" if qty > 1 else name
            self.printer.textln(self._fmt_line(label, f"${total_price:.2f}"))

            # Optional second line(s): per-item discount etc. not bold
            self.printer.set(align="left", font="a", bold=False)
            try:
                disc_amt = float(item.get("line_discount_total", 0.0) or 0.0)
            except Exception:
                disc_amt = 0.0
            if disc_amt > 0:
                self.printer.textln(self._fmt_line("  Discount", f"-${disc_amt:.2f}"))

            # Spacer between items
            self.printer.textln("")

    def _rcpt_print_totals(self, order_details, draft):
        orig_subtotal = float(order_details.get("subtotal") or 0.0)
        tax_amount = float(order_details.get("tax_amount") or 0.0)
        total_with_tax = float(order_details.get("total_with_tax") or 0.0)

        paper_excise = self._calc_paper_tax_total(order_details)
        display_subtotal = max(0.0, round(orig_subtotal - paper_excise, 2))

        try:
            order_disc = float(order_details.get("total_discount", 0) or 0)
        except Exception:
            order_disc = 0.0

        self.printer.textln("")
        self.printer.set(align="left", font="a", bold=True)
        self.printer.textln(self._fmt_line("Subtotal", f"${display_subtotal:.2f}"))

        if order_disc > 0:
            self.printer.set(align="left", font="a", bold=False)
            self.printer.textln(self._fmt_line("Discount", f"-${order_disc:.2f}"))

        if paper_excise > 0:
            self.printer.set(align="left", font="a", bold=True)
            self.printer.textln(
                self._fmt_line("RI ROLLING PAPER TAX", f"${paper_excise:.2f}")
            )

        self.printer.set(align="left", font="a", bold=False)
        self.printer.textln(self._fmt_line("7% RI Sales Tax", f"${tax_amount:.2f}"))

        self.printer.set(align="left", font="a", bold=True)
        self.printer.textln(self._fmt_line("Total", f"${total_with_tax:.2f}"))

        if not draft:
            self.printer.set(align="left", font="a", bold=False)
            pm = order_details.get("payment_method")
            if pm == "Cash":
                self.printer.textln(
                    self._fmt_line(
                        "Cash",
                        f"${float(order_details.get('amount_tendered') or 0.0):.2f}",
                    )
                )
                self.printer.textln(
                    self._fmt_line(
                        "Change",
                        f"${float(order_details.get('change_given') or 0.0):.2f}",
                    )
                )
            elif pm == "Split":
                self.printer.textln("Split Payment")
            elif pm == "Debit":
                self.printer.textln("Debit Payment")
            else:
                self.printer.textln("Credit Payment")

    def _rcpt_print_review_and_barcode(self, order_details, draft, qr_code):
        self.printer.set(align="center", font="a", bold=False)
        self.printer.textln()

        barcode_data = str(order_details["order_id"])
        short_uuid = barcode_data[:13]
        barcode_data_short = "{B" + short_uuid

        if not draft:
            if qr_code:
                review_url = "https://g.page/r/CfHmpKJDLRqXEBM/review"
                self.printer.set(align="center", font="a", bold=False)
                self.printer.textln()
                self.printer.textln("Thanks for shopping at RIGS!")
                self.printer.set(align="center", font="a", bold=True)
                self.printer.textln("Scan the QR Code to review us on Google!")
                # self.printer.set(align="center", font="a", bold=False)
                # self.printer.textln("It really helps!")
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
