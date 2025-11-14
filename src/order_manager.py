import uuid
import json
import os
from open_cash_drawer import open_cash_drawer

import logging

logger = logging.getLogger("rigs_pos")

class OrderException(Exception):
    pass

class OrderManager:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(OrderManager, cls).__new__(cls)
        return cls._instance

    def __init__(self, ref, tax_rate=0.07):
        if not hasattr(self, "_init"):

            self.items = {}
            self.total = 0.0
            self.subtotal = 0.0
            self.tax_amount = 0.0
            self.change_given = 0.0
            self.amount_tendered = 0.0
            self.tax_rate = tax_rate
            self.payment_method = None
            self._total_with_tax = None
            self.order_id = str(uuid.uuid4())
            self.saved_orders_dir = "saved_orders"

            # refactoring to seperate order and line discounts 8/27/25
            # !82725
            self.order_level_discount = 0.0
            self.line_item_discount_total = 0.0
            self.total_discount = 0.0
            self.order_discount = 0.0

            self.app = ref

            if not os.path.exists(self.saved_orders_dir):
                os.makedirs(self.saved_orders_dir)

            self._init = True

    def _compute_line_discounts(self, item) -> float:

        price = float(item.get("price", 0.0))
        qty = int(item.get("quantity", 1))
        subtotal = price * qty

        total = 0.0
        for d in item.get("discounts", []):
            dtype = d.get("type")
            if dtype == "percent":
                pct = max(0.0, min(100.0, float(d.get("value", 0.0))))
                total += price * (pct / 100.0) * qty
            elif dtype == "amount":
                val = float(d.get("value", 0.0))
                if d.get("per_unit", True):
                    total += val * qty
                else:
                    total += val

        return min(total, subtotal)

    def _recompute_line(self, item):
        price = float(item.get("price", 0.0))
        qty = int(item.get("quantity", 1))
        line_subtotal = price * qty
        line_discount_total = self._compute_line_discounts(item)
        line_total = max(line_subtotal - line_discount_total, 0.0)

        item["line_subtotal"] = line_subtotal
        item["line_discount_total"] = line_discount_total
        item["total_price"] = line_total

        # !82725 mirror to remain compatible with existing gui
        item["discount"] = {
            "amount": f"{line_discount_total:.2f}",
            "amount_value": float(line_discount_total),
            "percent": False,
        }
        return item

    def recalculate_order_totals(self, remove=False):
        # !82725 recompute every line first
        for it in self.items.values():
            self._recompute_line(it)

        self.subtotal = sum(float(it["line_subtotal"]) for it in self.items.values())

        # sum line item discounts and combine with order level
        self.line_item_discount_total = sum(
            float(it.get("line_discount_total", 0.0)) for it in self.items.values()
        )
        self.total_discount = float(self.order_level_discount) + float(
            self.line_item_discount_total
        )

        self.order_discount = self.total_discount

        self.total = max(self.subtotal - self.total_discount, 0.0)
        self._update_total_with_tax()
        return self.total

    def _update_total_with_tax(self):
        self.tax_amount = self.total * self.tax_rate
        self._total_with_tax = self.total + self.tax_amount

    def calculate_total_with_tax(self):
        self._update_total_with_tax()
        return self._total_with_tax

    def update_tax_amount(self):
        self.tax_amount = max(self.total * self.tax_rate, 0)
        # print(self.tax_amount)
        return self.tax_amount

    def _get_discount_value(self, item) -> float:
        d = item.get("discount") or {}
        try:
            return float(d.get("amount_value", d.get("amount", 0.0)))
        except (TypeError, ValueError):
            return 0.0

    def _set_discount(self, item, amount: float, percent: bool) -> None:
        # !82725
        amt = float(amount)
        item["discount"] = {
            "amount": f"{amt:.2f}",  # display string for gui
            "amount_value": amt,  # numeric for calculations
            "percent": bool(percent),
        }

    def add_item(self, item_name, item_price, custom_item=False, item_id=None):
        existing_item = next(
            (
                key
                for key, value in self.items.items()
                if value["name"] == item_name and value["price"] == item_price
            ),
            None,
        )

        if existing_item:
            self.items[existing_item]["quantity"] += 1
        else:
            self.items[item_id] = {
                "name": item_name,
                "price": float(item_price),
                "quantity": 1,
                "discounts": [],  # !82725 canonical list
                "total_price": float(item_price),
                "discount": {"amount": "0.00", "percent": False},  # mirror
            }

        self.recalculate_order_totals()

    ## !82725
    def add_line_discount(self, item_id, value, percent=False, per_unit=True):

        if item_id in self.items:
            entry = {"type": "percent" if percent else "amount", "value": float(value)}
            if not percent:
                entry["per_unit"] = bool(per_unit)
            self.items[item_id].setdefault("discounts", []).append(entry)
            self.recalculate_order_totals()

    def clear_line_discounts(self, item_id):
        if item_id in self.items:
            self.items[item_id]["discounts"] = []
            self.recalculate_order_totals()

    def increment_last_line_discount(self, item_id, delta):

        if item_id in self.items:
            lst = self.items[item_id].get("discounts", [])
            if lst:
                lst[-1]["value"] = float(lst[-1].get("value", 0.0)) + float(delta)
                self.recalculate_order_totals()

    def decrement_last_line_discount(self, item_id, delta):
        self.increment_last_line_discount(item_id, -float(delta))

    ##
    ##

    def remove_item(self, item_name):
        item_to_remove = next(
            (key for key, value in self.items.items() if value["name"] == item_name),
            None,
        )
        if item_to_remove:
            del self.items[item_to_remove]
            self.recalculate_order_totals()

    def adjust_item_quantity(self, item_id, adjustment):
        if item_id in self.items:
            item = self.items[item_id]
            original_quantity = int(item.get("quantity", 1))
            new_quantity = max(original_quantity + int(adjustment), 1)
            item["quantity"] = new_quantity
            self.recalculate_order_totals()

    def recalculate_order_discount(self):

        self.order_discount = sum(
            float(item.get("discount", {}).get("amount", "0"))
            for item in self.items.values()
        )

    def get_order_details(self):
        return {
            "order_id": self.order_id,
            "items": self.items,
            "subtotal": self.subtotal,
            "total": self.total,
            "tax_rate": self.tax_rate,
            "tax_amount": self.tax_amount,
            "total_with_tax": self._total_with_tax,
            "discount": self.total_discount,
            "order_level_discount": self.order_level_discount,
            "line_item_discount_total": self.line_item_discount_total,
            "total_discount": self.total_discount,
            "payment_method": self.payment_method,
            "amount_tendered": self.amount_tendered,
            "change_given": self.change_given,
        }

    def clear_order(self):
        self.items = {}
        self.subtotal = 0.0
        self.total = 0.0
        self.tax_amount = 0.0
        self._total_with_tax = None
        self.order_level_discount = 0.0
        self.line_item_discount_total = 0.0
        self.total_discount = 0.0
        self.order_discount = 0.0
        self.payment_method = None
        self.amount_tendered = 0.0
        self.change_given = 0.0
        self.order_id = str(uuid.uuid4())

    def save_order_to_disk(self):
        if not os.path.exists(self.saved_orders_dir):
            os.makedirs(self.saved_orders_dir)

        order_details = self.get_order_details()
        order_filename = f"order_{self.order_id}.json"

        filepath = os.path.join(self.saved_orders_dir, order_filename)

        with open(filepath, "w") as file:
            json.dump(order_details, file)

    def delete_order_from_disk(self, order):
        order_id = order["order_id"]
        order_filename = f"order_{order_id}.json"
        full_path = os.path.join(self.saved_orders_dir, order_filename)
        try:
            os.remove(full_path)
        except Exception as e:
            logger.info(
                f"[Order Manager] Expected error in delete_order_from_disk\n{e}"
            )

    def load_order_from_disk(self, order):
        order_id = order["order_id"]
        order_filename = f"order_{order_id}.json"
        full_path = os.path.join(self.saved_orders_dir, order_filename)

        try:
            with open(full_path, "r") as file:
                order_data = json.load(file)
        except Exception as e:
            logger.warn(f"[Order Manager] load_order_from_disk\n{e}")
        try:
            self.order_id = order_data["order_id"]
            self.items = order_data["items"]
            self.subtotal = order_data["subtotal"]
            self.total = order_data["total"]
            self.tax_rate = order_data["tax_rate"]
            self.tax_amount = order_data["tax_amount"]
            self._total_with_tax = order_data["total_with_tax"]
            self.order_discount = order_data["discount"]
            self.payment_method = order_data["payment_method"]
            self.amount_tendered = order_data["amount_tendered"]
            self.change_given = order_data["change_given"]
            self.app.utilities.update_display()
            self.app.utilities.update_financial_summary()
            return True
        except Exception as e:
            logger.warn(e)

    def list_all_saved_orders(self):
        all_order_details = []
        for file_name in os.listdir(self.saved_orders_dir):
            if file_name.startswith("order_") and file_name.endswith(".json"):
                full_path = os.path.join(self.saved_orders_dir, file_name)

                try:
                    with open(full_path, "r") as file:
                        order_data = json.load(file)
                        item_names = [
                            item["name"] for item in order_data["items"].values()
                        ]
                        order_dict = {
                            "order_id": order_data["order_id"],
                            "items": item_names,
                        }
                        all_order_details.append(order_dict)
                except Exception as e:
                    logger.warn(
                        f"[Order Manager] Error reading order file {file_name}\n{e}"
                    )

        return all_order_details

    def adjust_order_to_target_total(self, target_total_with_tax):
        if target_total_with_tax != "":
            target_total_with_tax = float(target_total_with_tax)
            adjusted_subtotal = target_total_with_tax / (1 + self.tax_rate)
            required_order_level = self.subtotal - adjusted_subtotal
            if required_order_level < 0 or required_order_level > self.subtotal:
                return False
            self.set_order_level_discount(required_order_level)
            return True

    def add_discount(self, discount_amount, percent=False):
        discount_amount = float(discount_amount)
        if percent:
            discount = self.subtotal * (discount_amount / 100)
            self.order_discount += discount

        else:
            self.order_discount += min(discount_amount, self.subtotal)
        self.total = max(self.subtotal - self.order_discount, 0)
        self.update_tax_amount()
        self._update_total_with_tax()

    def set_payment_method(self, method):
        self.payment_method = method

    def set_payment_details(self, amount_tendered=None, change=None):
        self.amount_tendered = amount_tendered if amount_tendered is not None else 0.0
        self.change_given = change if change is not None else 0.0

    def add_custom_item(self, name, price):
        if not name:
            raise OrderException("Name is missing")
        if not price:
            raise OrderException("Price is missing")

        item_id = str(uuid.uuid4())
        try:
            price = float(price)
        except Exception as e:
            logger.warn("Exception in add custom item order_manager.py,", e)
            return
        try:
            self.add_item(name, price, custom_item=True, item_id=item_id)
        except Exception as e:
            logger.warn("Exception in add custom item order_manager.py,", e)
        try:
            self.app.utilities.update_display()
            self.app.utilities.update_financial_summary()
            self.app.popup_manager.custom_item_popup.dismiss()
            self.app.popup_manager.cash_input.text = ""
        except Exception as e:
            logger.warn(f"[Order Manager]: add_custom_item\n{e}")

    def finalize_order(self):
        order_details = self.get_order_details()

        order_summary = f"[size=18][b]Order Summary:[/b][/size]\n\n"

        for item_id, item_details in order_details["items"].items():
            item_name = item_details["name"]
            quantity = item_details["quantity"]
            total_price_for_item = item_details["total_price"]

            try:
                total_price_float = float(total_price_for_item)
            except ValueError as e:
                logger.warn(e)
                continue

            order_summary += self.create_order_summary_item(
                item_name, quantity, total_price_float
            )

        order_summary += f"\nSubtotal: ${order_details['subtotal']:.2f}"
        order_summary += f"\nTax: ${order_details['tax_amount']:.2f}"
        if order_details["discount"] > 0:
            order_summary += f"\nDiscount: ${order_details['discount']:.2f}"
        order_summary += (
            f"\n\n[size=20]Total: [b]${order_details['total_with_tax']:.2f}[/b][/size]"
        )

        self.app.popup_manager.show_order_popup(order_summary)

    def create_order_summary_item(self, item_name, quantity, total_price):
        return f"[b]{item_name}[/b] x{quantity} ${total_price:.2f}\n"

    def remove_single_item_discount(self, item_id):
        if item_id in self.items:
            self.clear_line_discounts(item_id)
            self.app.utilities.update_display()
            self.app.utilities.update_financial_summary()
            self.app.popup_manager.item_popup.dismiss()

    def discount_single_item(self, discount_amount, item_id="", percent=False):
        try:
            if item_id in self.items:
                # amount and percent are per-unit for scaling.
                self.add_line_discount(
                    item_id, discount_amount, percent=percent, per_unit=True
                )
            self.app.utilities.update_display()
            self.app.utilities.update_financial_summary()
            try:
                self.app.popup_manager.discount_amount_input.text = ""
            except:
                pass
            self.app.popup_manager.discount_item_popup.dismiss()
            try:
                self.app.popup_manager.discount_popup.dismiss()
            except:
                pass
            self.app.popup_manager.item_popup.dismiss()
        except:
            pass

    def set_order_level_discount(self, amount):
        self.order_level_discount = max(0.0, float(amount))
        self.recalculate_order_totals()

    def add_order_level_discount(self, amount):
        self.order_level_discount = max(
            0.0, float(self.order_level_discount) + float(amount)
        )
        self.recalculate_order_totals()

    def discount_entire_order(self, discount_amount, percent=False):
        if discount_amount != "":
            try:
                discount_amount = float(discount_amount)
            except ValueError:
                return
            if percent:
                add_val = self.subtotal * (discount_amount / 100.0)
            else:
                add_val = discount_amount
            add_val = min(add_val, self.subtotal)
            self.add_order_level_discount(add_val)
            try:
                self.update_tax_amount()
                self._update_total_with_tax()
                self.app.utilities.update_display()
                self.app.utilities.update_financial_summary()
            except Exception as e:
                logger.warn(
                    f"[Order Manager]: discount_entire_order\n exception updating totals\n{e}"
                )
            try:
                self.app.popup_manager.custom_discount_order_amount_input.text = ""
            except AttributeError:
                logger.info(
                    "[Order Manager]: discount_entire_order\nExpected error popup_manager.custom_discount_order_amount_input.text is None"
                )
            try:
                self.app.popup_manager.discount_order_popup.dismiss()
            except AttributeError:
                logger.info(
                    "[Order Manager]: discount_entire_order\nExpected error popup_manager.discount_order_popup is None"
                )
            try:
                self.app.popup_manager.custom_discount_order_popup.dismiss()
            except AttributeError:
                logger.info(
                    "[Order Manager]: discount_entire_order\nExpected error popup_manager.custom_discount_order_popup is None"
                )
            self.app.financial_summary.order_mod_popup.dismiss()

    def remove_order_discount(self):
        if float(self.order_level_discount) > 0:
            self.order_level_discount = 0.0
            self.recalculate_order_totals()
            self.app.utilities.update_display()
            self.app.utilities.update_financial_summary()

    def add_adjusted_price_item(self):
        target_amount = self.app.popup_manager.adjust_price_cash_input.text
        try:
            target_amount = float(target_amount)
        except ValueError as e:
            logger.warn(e)

        self.adjust_order_to_target_total(target_amount)
        self.app.utilities.update_display()
        self.app.utilities.update_financial_summary()
        self.app.popup_manager.adjust_price_popup.dismiss()
        self.app.financial_summary.order_mod_popup.dismiss()

    def remove_item_in(self, item_name, item_price):
        self.remove_item(item_name)
        self.app.utilities.update_display()
        self.app.utilities.update_financial_summary()
        self.app.popup_manager.item_popup.dismiss()

    def adjust_item_quantity_in(self, item_id, item_button, adjustment):
        self.adjust_item_quantity(item_id, adjustment)
        self.app.utilities.update_display()
        self.app.utilities.update_financial_summary()

    def handle_credit_payment(self):
        open_cash_drawer()
        self.set_payment_method("Credit")
        self.app.popup_manager.show_payment_confirmation_popup()

    def handle_debit_payment(self):
        open_cash_drawer()
        self.set_payment_method("Debit")
        self.app.popup_manager.show_payment_confirmation_popup()

    def on_cash_confirm(self, instance):
        amount_tendered = float(self.app.popup_manager.cash_payment_input.text)
        total_with_tax = self.app.order_manager.calculate_total_with_tax()
        change = amount_tendered - total_with_tax
        if hasattr(self.app.popup_manager, "cash_popup"):
            self.app.popup_manager.cash_popup.dismiss()
        if hasattr(self.app.popup_manager, "custom_cash_popup"):
            self.app.popup_manager.custom_cash_popup.dismiss()
        open_cash_drawer()
        self.set_payment_method("Cash")
        self.set_payment_details(amount_tendered, change)
        self.app.popup_manager.show_make_change_popup(change)

    def on_custom_cash_confirm(self, instance):
        amount_tendered = float(self.app.popup_manager.custom_cash_input.text)
        total_with_tax = self.app.order_manager.calculate_total_with_tax()
        change = amount_tendered - total_with_tax
        if hasattr(self.app.popup_manager, "cash_popup"):
            self.app.popup_manager.cash_popup.dismiss()
        if hasattr(self.app.popup_manager, "custom_cash_popup"):
            self.app.popup_manager.custom_cash_popup.dismiss()
        open_cash_drawer()
        self.set_payment_method("Cash")
        self.set_payment_details(amount_tendered, change)
        self.app.popup_manager.show_make_change_popup(change)
