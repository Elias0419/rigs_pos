import uuid
import json
import os
import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from open_cash_drawer import open_cash_drawer

import logging

logger = logging.getLogger("rigs_pos")


class OrderException(Exception):
    pass


class CustomOrderMissingFields(OrderException):
    pass


@dataclass(frozen=True)
class Discount:
    # type: "percent" or "amount"
    type: str
    value: float
    per_unit: bool = True  # only meaningful for type=="amount"

    def to_dict(self) -> Dict[str, Any]:
        return {"type": self.type, "value": float(self.value), "per_unit": bool(self.per_unit)}

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "Discount":
        dtype = str(d.get("type"))
        if dtype not in ("percent", "amount"):
            raise ValueError(f"Invalid discount type: {dtype!r}")
        value = float(d.get("value"))
        per_unit = bool(d.get("per_unit", True))
        return Discount(type=dtype, value=value, per_unit=per_unit)


@dataclass
class LineItem:
    item_id: str
    name: str
    unit_price: float
    quantity: int = 1
    barcode: Optional[str] = None
    is_custom: int = 0  # stored as INTEGER in sqlite, so use 0/1

    discounts: List[Discount] = field(default_factory=list)

    # computed
    line_subtotal: float = 0.0
    line_discount_total: float = 0.0
    total_price: float = 0.0

    def recompute(self) -> None:
        price = float(self.unit_price)
        qty = int(self.quantity)
        if qty < 1:
            raise ValueError("quantity must be >= 1")

        subtotal = price * qty

        disc_total = 0.0
        for d in self.discounts:
            if d.type == "percent":
                pct = float(d.value)
                if pct < 0.0:
                    pct = 0.0
                if pct > 100.0:
                    pct = 100.0
                disc_total += price * (pct / 100.0) * qty
            elif d.type == "amount":
                amt = float(d.value)
                disc_total += (amt * qty) if d.per_unit else amt
            else:
                raise ValueError(f"Unknown discount type: {d.type!r}")

        if disc_total < 0.0:
            disc_total = 0.0
        if disc_total > subtotal:
            disc_total = subtotal

        self.line_subtotal = float(subtotal)
        self.line_discount_total = float(disc_total)
        self.total_price = float(subtotal - disc_total)

    def add_discount(self, discount: Discount) -> None:
        self.discounts.append(discount)
        self.recompute()

    def clear_discounts(self) -> None:
        self.discounts.clear()
        self.recompute()

    def increment_last_discount(self, delta: float) -> None:
        if not self.discounts:
            return
        last = self.discounts[-1]
        self.discounts[-1] = Discount(type=last.type, value=float(last.value) + float(delta), per_unit=last.per_unit)
        self.recompute()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "item_id": self.item_id,
            "barcode": self.barcode,
            "is_custom": int(self.is_custom),
            "name": self.name,
            "price": float(self.unit_price),
            "quantity": int(self.quantity),
            "discounts": [d.to_dict() for d in self.discounts],
            "line_subtotal": float(self.line_subtotal),
            "line_discount_total": float(self.line_discount_total),
            "total_price": float(self.total_price),
        }

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "LineItem":
        item_id = str(d["item_id"])
        name = str(d["name"])
        unit_price = float(d["price"])
        quantity = int(d.get("quantity", 1))

        barcode = d.get("barcode")
        barcode = str(barcode) if barcode not in (None, "") else None

        is_custom = int(d.get("is_custom", 0))

        discounts_raw = d.get("discounts", []) or []
        discounts = [Discount.from_dict(x) for x in discounts_raw]

        li = LineItem(
            item_id=item_id,
            name=name,
            unit_price=unit_price,
            quantity=quantity,
            barcode=barcode,
            is_custom=is_custom,
            discounts=discounts,
        )
        li.recompute()
        return li


class OrderManager:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(OrderManager, cls).__new__(cls)
        return cls._instance

    def __init__(self, ref, tax_rate=0.07):
        if hasattr(self, "_init"):
            return

        self.items: Dict[str, LineItem] = {}

        self.total = 0.0
        self.subtotal = 0.0
        self.tax_amount = 0.0
        self.change_given = 0.0
        self.amount_tendered = 0.0
        self.tax_rate = float(tax_rate)
        self.payment_method = None
        self._total_with_tax = None
        self.order_id = str(uuid.uuid4())
        self.saved_orders_dir = "saved_orders"

        # order-level discounts only (line-level discounts live on LineItem)
        self.order_level_discount = 0.0
        self.line_item_discount_total = 0.0
        self.total_discount = 0.0

        self.app = ref

        if not os.path.exists(self.saved_orders_dir):
            os.makedirs(self.saved_orders_dir)

        self._init = True

    def recalculate_order_totals(self, remove=False):
        for it in self.items.values():
            it.recompute()

        self.subtotal = sum(float(it.line_subtotal) for it in self.items.values())
        self.line_item_discount_total = sum(float(it.line_discount_total) for it in self.items.values())

        self.total_discount = float(self.order_level_discount) + float(self.line_item_discount_total)
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
        self.tax_amount = max(self.total * self.tax_rate, 0.0)
        return self.tax_amount

    def add_line_discount(self, item_id, value, percent=False, per_unit=True):
        if item_id in self.items:
            d = Discount(
                type="percent" if percent else "amount",
                value=float(value),
                per_unit=bool(per_unit),
            )
            self.items[item_id].add_discount(d)
            self.recalculate_order_totals()

    def clear_line_discounts(self, item_id):
        if item_id in self.items:
            self.items[item_id].clear_discounts()
            self.recalculate_order_totals()

    def increment_last_line_discount(self, item_id, delta):
        if item_id in self.items:
            self.items[item_id].increment_last_discount(float(delta))
            self.recalculate_order_totals()

    def decrement_last_line_discount(self, item_id, delta):
        self.increment_last_line_discount(item_id, -float(delta))

    def remove_item(self, item_name):
        item_to_remove = next((key for key, value in self.items.items() if value.name == item_name), None)
        if item_to_remove:
            del self.items[item_to_remove]
            self.recalculate_order_totals()

    def adjust_item_quantity(self, item_id, adjustment):
        if item_id in self.items:
            item = self.items[item_id]
            new_quantity = max(int(item.quantity) + int(adjustment), 1)
            item.quantity = new_quantity
            item.recompute()
            self.recalculate_order_totals()

    def get_order_details(self):
        return {
            "order_id": self.order_id,
            "items": {item_id: li.to_dict() for item_id, li in self.items.items()},
            "subtotal": float(self.subtotal),
            "total": float(self.total),
            "tax_rate": float(self.tax_rate),
            "tax_amount": float(self.tax_amount),
            "total_with_tax": float(self._total_with_tax) if self._total_with_tax is not None else None,
            "order_level_discount": float(self.order_level_discount),
            "line_item_discount_total": float(self.line_item_discount_total),
            "total_discount": float(self.total_discount),
            "payment_method": self.payment_method,
            "amount_tendered": float(self.amount_tendered),
            "change_given": float(self.change_given),
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
            logger.info(f"[Order Manager] Expected error in delete_order_from_disk\n{e}")

    def load_order_from_disk(self, order):
        order_id = order["order_id"]
        order_filename = f"order_{order_id}.json"
        full_path = os.path.join(self.saved_orders_dir, order_filename)

        try:
            with open(full_path, "r") as file:
                order_data = json.load(file)
        except Exception as e:
            logger.warning(f"[Order Manager] load_order_from_disk\n{e}")
            return False

        try:
            self.order_id = str(order_data["order_id"])

            items_payload = order_data.get("items", {}) or {}
            new_items: Dict[str, LineItem] = {}
            for _, payload in items_payload.items():
                if not isinstance(payload, dict):
                    continue
                li = LineItem.from_dict(payload)
                new_items[li.item_id] = li
            self.items = new_items

            self.order_level_discount = float(order_data.get("order_level_discount", 0.0))
            self.payment_method = order_data.get("payment_method")
            self.amount_tendered = float(order_data.get("amount_tendered", 0.0))
            self.change_given = float(order_data.get("change_given", 0.0))

            self.recalculate_order_totals()

            self.app.utilities.update_display()
            self.app.utilities.update_financial_summary()
            return True
        except Exception as e:
            logger.warning(e)
            return False

    def list_all_saved_orders(self):
        all_order_details = []
        for file_name in os.listdir(self.saved_orders_dir):
            if not (file_name.startswith("order_") and file_name.endswith(".json")):
                continue

            full_path = os.path.join(self.saved_orders_dir, file_name)
            try:
                with open(full_path, "r") as file:
                    order_data = json.load(file)
                items_payload = order_data.get("items", {}) or {}
                item_names = []
                for _, payload in items_payload.items():
                    if isinstance(payload, dict):
                        item_names.append(str(payload.get("name", "")))
                all_order_details.append(
                    {
                        "order_id": order_data.get("order_id"),
                        "items": item_names,
                    }
                )
            except Exception as e:
                logger.warning(f"[Order Manager] Error reading order file {file_name}\n{e}")

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

    def _finalize_adjust_price(self):
        self.app.utilities.update_display()
        self.app.utilities.update_financial_summary()
        try:
            self.app.popup_manager.adjust_price_popup.dismiss()
        except AttributeError:
            logger.info("[Order Manager]: adjust price popup already dismissed")

        try:
            self.app.financial_summary.order_mod_popup.dismiss()
        except AttributeError:
            logger.info("[Order Manager]: order mod popup already dismissed")

    def round_down_payment_adjustment(self, denomination):
        try:
            denomination = float(denomination)
        except (TypeError, ValueError):
            logger.warning("[Order Manager]: invalid denomination for round down")
            return False

        if denomination <= 0:
            logger.warning("[Order Manager]: denomination must be positive for round down")
            return False

        current_total = self.calculate_total_with_tax()
        target_total = math.floor(current_total / denomination) * denomination

        if target_total <= 0:
            logger.warning("[Order Manager]: target total not positive after round down")
            return False

        if not self.adjust_order_to_target_total(target_total):
            return False

        self._finalize_adjust_price()
        return True

    def add_discount(self, discount_amount, percent=False):
        # order-level discount only
        discount_amount = float(discount_amount)
        if percent:
            add_val = self.subtotal * (discount_amount / 100.0)
        else:
            add_val = discount_amount
        add_val = min(add_val, self.subtotal)
        self.add_order_level_discount(add_val)

    def set_payment_method(self, method):
        self.payment_method = method

    def set_payment_details(self, amount_tendered=None, change=None):
        self.amount_tendered = amount_tendered if amount_tendered is not None else 0.0
        self.change_given = change if change is not None else 0.0

    def add_custom_item(self, name, price, item_id, barcode, is_custom):
        if not name or not price:
            raise CustomOrderMissingFields()

        try:
            price = float(price)
        except (ValueError, TypeError) as e:
            logger.error("[Order Manager] add_custom_item, coercing price to float failed\n%s", e)
            return

        try:
            self.add_item(name, price, item_id, barcode, is_custom)
        except Exception as e:
            logger.warning("Exception in add custom item order_manager.py: %s", e)

        try:
            self.app.utilities.update_display()
            self.app.utilities.update_financial_summary()
            self.app.popup_manager.custom_item_popup.dismiss()
            self.app.popup_manager.cash_input.text = ""
        except Exception as e:
            logger.warning(f"[Order Manager]: add_custom_item\n{e}")

    def add_item(self, item_name, item_price, item_id, barcode, is_custom):
        # Aggregate by item_id (custom items typically have unique item_id and therefore won't aggregate).
        item_id = str(item_id)

        if item_id in self.items:
            li = self.items[item_id]
            li.quantity = int(li.quantity) + 1
            li.recompute()
        else:
            li = LineItem(
                item_id=item_id,
                barcode=str(barcode) if barcode not in (None, "") else None,
                is_custom=int(bool(is_custom)),
                name=str(item_name),
                unit_price=float(item_price),
                quantity=1,
            )
            li.recompute()
            self.items[li.item_id] = li

        self.recalculate_order_totals()

    def finalize_order(self):
        order_details = self.get_order_details()

        order_summary = f"[size=18][b]Order Summary:[/b][/size]\n\n"

        for _, item_details in order_details["items"].items():
            item_name = item_details["name"]
            quantity = item_details["quantity"]
            total_price_for_item = item_details["total_price"]

            try:
                total_price_float = float(total_price_for_item)
            except ValueError as e:
                logger.warning(e)
                continue

            order_summary += self.create_order_summary_item(item_name, quantity, total_price_float)

        order_summary += f"\nSubtotal: ${order_details['subtotal']:.2f}"
        order_summary += f"\nTax: ${order_details['tax_amount']:.2f}"
        if order_details["total_discount"] > 0:
            order_summary += f"\nDiscount: ${order_details['total_discount']:.2f}"
        order_summary += f"\n\n[size=20]Total: [b]${order_details['total_with_tax']:.2f}[/b][/size]"

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
                self.add_line_discount(item_id, discount_amount, percent=percent, per_unit=True)
            self.app.utilities.update_display()
            self.app.utilities.update_financial_summary()
            try:
                self.app.popup_manager.discount_amount_input.text = ""
            except Exception:
                pass
            self.app.popup_manager.discount_item_popup.dismiss()
            try:
                self.app.popup_manager.discount_popup.dismiss()
            except Exception:
                pass
            self.app.popup_manager.item_popup.dismiss()
        except Exception:
            pass

    def set_order_level_discount(self, amount):
        self.order_level_discount = max(0.0, float(amount))
        self.recalculate_order_totals()

    def add_order_level_discount(self, amount):
        self.order_level_discount = max(0.0, float(self.order_level_discount) + float(amount))
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
                self.app.utilities.update_display()
                self.app.utilities.update_financial_summary()
            except Exception as e:
                logger.warning(f"[Order Manager]: discount_entire_order\n exception updating totals\n{e}")

            try:
                self.app.popup_manager.custom_discount_order_amount_input.text = ""
            except AttributeError:
                logger.info(
                    "[Order Manager]: discount_entire_order\nExpected error popup_manager.custom_discount_order_amount_input.text is None"
                )

            try:
                self.app.popup_manager.discount_order_popup.dismiss()
            except AttributeError:
                logger.info("[Order Manager]: discount_entire_order\nExpected error popup_manager.discount_order_popup is None")

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
            logger.warning(e)

        if self.adjust_order_to_target_total(target_amount):
            self._finalize_adjust_price()

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
