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
    unit_cost: Optional[float] = None
    is_cigarette: Optional[int] = None

    discounts: List[Discount] = field(default_factory=list)

    # computed
    line_subtotal: float = 0.0
    line_discount_total: float = 0.0
    total_price: float = 0.0
    line_cost: float = 0.0

    def recompute(self) -> None:
        price = float(self.unit_price)
        qty = int(self.quantity)
        if qty < 1:
            raise ValueError("quantity must be >= 1")

        if self.is_cigarette is not None:
            self.is_cigarette = int(bool(self.is_cigarette))

        self.unit_cost = float(self.unit_cost) if self.unit_cost is not None else None

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
        self.line_cost = (
            float(self.unit_cost) * qty if self.unit_cost is not None else 0.0
        )

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
            "cost": float(self.unit_cost) if self.unit_cost is not None else None,
            "unit_cost": float(self.unit_cost) if self.unit_cost is not None else None,
            "line_cost": float(self.line_cost) if self.unit_cost is not None else None,
            "is_cigarette": int(self.is_cigarette) if self.is_cigarette is not None else None,
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

        unit_cost_raw = d.get("unit_cost", d.get("cost"))
        unit_cost = float(unit_cost_raw) if unit_cost_raw not in (None, "") else None

        barcode = d.get("barcode")
        barcode = str(barcode) if barcode not in (None, "") else None

        is_custom = int(d.get("is_custom", 0))
        is_cigarette_raw = d.get("is_cigarette")
        is_cigarette = (
            int(is_cigarette_raw) if is_cigarette_raw not in (None, "") else None
        )

        discounts_raw = d.get("discounts", []) or []
        discounts = [Discount.from_dict(x) for x in discounts_raw]

        li = LineItem(
            item_id=item_id,
            name=name,
            unit_price=unit_price,
            quantity=quantity,
            barcode=barcode,
            is_custom=is_custom,
            unit_cost=unit_cost,
            is_cigarette=is_cigarette,
            discounts=discounts,
        )
        li.recompute()
        return li


@dataclass
class Order:
    tax_rate: float
    items: Dict[str, LineItem] = field(default_factory=dict)
    order_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    subtotal: float = 0.0
    line_item_discount_total: float = 0.0
    order_level_discount: float = 0.0
    total_discount: float = 0.0
    total: float = 0.0
    tax_amount: float = 0.0
    total_with_tax: Optional[float] = None
    payment_method: Optional[str] = None
    amount_tendered: float = 0.0
    change_given: float = 0.0

    def recalculate_totals(self) -> float:
        for item in self.items.values():
            item.recompute()

        self.subtotal = sum(float(it.line_subtotal) for it in self.items.values())
        self.line_item_discount_total = sum(float(it.line_discount_total) for it in self.items.values())

        self.total_discount = float(self.order_level_discount) + float(self.line_item_discount_total)
        self.total = max(self.subtotal - self.total_discount, 0.0)

        self._update_total_with_tax()
        return self.total

    def _update_total_with_tax(self) -> None:
        self.tax_amount = max(self.total * self.tax_rate, 0.0)
        self.total_with_tax = self.total + self.tax_amount

    def calculate_total_with_tax(self) -> Optional[float]:
        self._update_total_with_tax()
        return self.total_with_tax

    def clear(self) -> None:
        self.items = {}
        self.subtotal = 0.0
        self.total = 0.0
        self.tax_amount = 0.0
        self.total_with_tax = None
        self.order_level_discount = 0.0
        self.line_item_discount_total = 0.0
        self.total_discount = 0.0
        self.payment_method = None
        self.amount_tendered = 0.0
        self.change_given = 0.0
        self.order_id = str(uuid.uuid4())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "order_id": self.order_id,
            "items": {item_id: li.to_dict() for item_id, li in self.items.items()},
            "subtotal": float(self.subtotal),
            "total": float(self.total),
            "tax_rate": float(self.tax_rate),
            "tax_amount": float(self.tax_amount),
            "total_with_tax": float(self.total_with_tax) if self.total_with_tax is not None else None,
            "order_level_discount": float(self.order_level_discount),
            "line_item_discount_total": float(self.line_item_discount_total),
            "total_discount": float(self.total_discount),
            "payment_method": self.payment_method,
            "amount_tendered": float(self.amount_tendered),
            "change_given": float(self.change_given),
        }

    @staticmethod
    def from_dict(payload: Dict[str, Any]) -> "Order":
        order = Order(
            tax_rate=float(payload.get("tax_rate", 0.0)),
            order_id=str(payload.get("order_id", uuid.uuid4())),
        )

        items_payload = payload.get("items", {}) or {}
        items: Dict[str, LineItem] = {}
        for _, item_payload in items_payload.items():
            if not isinstance(item_payload, dict):
                continue
            li = LineItem.from_dict(item_payload)
            items[li.item_id] = li
        order.items = items

        order.order_level_discount = float(payload.get("order_level_discount", 0.0))
        order.payment_method = payload.get("payment_method")
        order.amount_tendered = float(payload.get("amount_tendered", 0.0))
        order.change_given = float(payload.get("change_given", 0.0))

        order.recalculate_totals()
        return order


class OrderManager:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(OrderManager, cls).__new__(cls)
        return cls._instance

    def __init__(self, ref, tax_rate=0.07):
        if hasattr(self, "_init"):
            return

        self.order = Order(tax_rate=float(tax_rate))
        self.saved_orders_dir = "saved_orders"

        self.app = ref

        if not os.path.exists(self.saved_orders_dir):
            os.makedirs(self.saved_orders_dir)

        self._init = True

    @property
    def items(self) -> Dict[str, LineItem]:
        return self.order.items

    @property
    def subtotal(self) -> float:
        return self.order.subtotal

    @property
    def total(self) -> float:
        return self.order.total

    @property
    def tax_rate(self) -> float:
        return self.order.tax_rate

    @property
    def tax_amount(self) -> float:
        return self.order.tax_amount

    @property
    def order_level_discount(self) -> float:
        return self.order.order_level_discount

    @property
    def line_item_discount_total(self) -> float:
        return self.order.line_item_discount_total

    @property
    def total_discount(self) -> float:
        return self.order.total_discount

    @property
    def payment_method(self) -> Optional[str]:
        return self.order.payment_method

    @property
    def amount_tendered(self) -> float:
        return self.order.amount_tendered

    @property
    def change_given(self) -> float:
        return self.order.change_given

    @property
    def order_id(self) -> str:
        return self.order.order_id

    def recalculate_order_totals(self, remove=False):
        self.order.recalculate_totals()
        return self.order.total

    def _update_total_with_tax(self):
        self.order._update_total_with_tax()

    def calculate_total_with_tax(self):
        self._update_total_with_tax()
        return self.order.total_with_tax

    def update_tax_amount(self):
        self.order.tax_amount = max(self.order.total * self.order.tax_rate, 0.0)
        return self.order.tax_amount

    def add_line_discount(self, item_id, value, percent=False, per_unit=True):
        if item_id in self.order.items:
            d = Discount(
                type="percent" if percent else "amount",
                value=float(value),
                per_unit=bool(per_unit),
            )
            self.order.items[item_id].add_discount(d)
            self.recalculate_order_totals()

    def clear_line_discounts(self, item_id):
        if item_id in self.order.items:
            self.order.items[item_id].clear_discounts()
            self.recalculate_order_totals()

    def increment_last_line_discount(self, item_id, delta):
        if item_id in self.order.items:
            self.order.items[item_id].increment_last_discount(float(delta))
            self.recalculate_order_totals()

    def decrement_last_line_discount(self, item_id, delta):
        self.increment_last_line_discount(item_id, -float(delta))

    def remove_item(self, item_name):
        item_to_remove = next((key for key, value in self.order.items.items() if value.name == item_name), None)
        if item_to_remove:
            del self.order.items[item_to_remove]
            self.recalculate_order_totals()

    def adjust_item_quantity(self, item_id, adjustment):
        if item_id in self.order.items:
            item = self.order.items[item_id]
            new_quantity = max(int(item.quantity) + int(adjustment), 1)
            item.quantity = new_quantity
            item.recompute()
            self.recalculate_order_totals()

    def get_order_details(self):
        return self.order

    def clear_order(self):
        self.order.clear()

    def save_order_to_disk(self):
        if not os.path.exists(self.saved_orders_dir):
            os.makedirs(self.saved_orders_dir)

        order_details = self.order.to_dict()
        order_filename = f"order_{self.order.order_id}.json"
        filepath = os.path.join(self.saved_orders_dir, order_filename)

        with open(filepath, "w") as file:
            json.dump(order_details, file)

    def delete_order_from_disk(self, order):
        order_id = order.order_id if isinstance(order, Order) else order["order_id"]
        order_filename = f"order_{order_id}.json"
        full_path = os.path.join(self.saved_orders_dir, order_filename)
        try:
            os.remove(full_path)
        except Exception as e:
            logger.info(f"[Order Manager] Expected error in delete_order_from_disk\n{e}")

    def load_order_from_disk(self, order):
        order_id = order.order_id if isinstance(order, Order) else order["order_id"]
        order_filename = f"order_{order_id}.json"
        full_path = os.path.join(self.saved_orders_dir, order_filename)

        try:
            with open(full_path, "r") as file:
                order_data = json.load(file)
        except Exception as e:
            logger.warning(f"[Order Manager] load_order_from_disk\n{e}")
            return False

        try:
            self.order = Order.from_dict(order_data)
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

    def _determine_round_down_step(self, current_total: float) -> float:
        if current_total < 20:
            return 1.0
        if current_total < 75:
            return 2.0
        if current_total < 200:
            return 5.0
        if current_total < 500:
            return 10.0
        if current_total < 1000:
            return 20.0
        return 50.0

    def get_round_down_targets(self, max_options: int = 4) -> List[float]:
        current_total = self.calculate_total_with_tax()
        if current_total is None or current_total <= 0:
            return []

        step = self._determine_round_down_step(current_total)
        max_drop = max(current_total * 0.2, step)
        if current_total < 20:
            max_drop = min(max_drop, 1.0)

        targets = []
        base_target = math.floor(current_total / step) * step
        base_target = round(base_target, 2)
        if math.isclose(base_target, current_total):
            base_target = round(base_target - step, 2)

        while len(targets) < max_options and base_target > 0:
            drop_amount = current_total - base_target
            if drop_amount <= 0 or drop_amount > max_drop:
                break

            if targets and math.isclose(base_target, targets[-1]):
                base_target = round(base_target - step, 2)
                continue

            targets.append(base_target)
            base_target = round(base_target - step, 2)

        return targets

    def round_down_to_target_total(self, target_total_with_tax):
        try:
            target_total_with_tax = float(target_total_with_tax)
        except (TypeError, ValueError):
            logger.warning("[Order Manager]: invalid target total for round down")
            return False

        current_total = self.calculate_total_with_tax()
        if current_total is None or current_total <= 0:
            logger.warning("[Order Manager]: cannot round down without a valid current total")
            return False

        if target_total_with_tax <= 0:
            logger.warning("[Order Manager]: target total not positive after round down")
            return False

        if target_total_with_tax >= current_total:
            logger.warning("[Order Manager]: target total must be below current total for round down")
            return False

        if not self.adjust_order_to_target_total(target_total_with_tax):
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
        self.order.payment_method = method

    def set_payment_details(self, amount_tendered=None, change=None):
        self.order.amount_tendered = amount_tendered if amount_tendered is not None else 0.0
        self.order.change_given = change if change is not None else 0.0

    def add_custom_item(self, name, price, item_id, barcode, is_custom):
        if not name or not price:
            raise CustomOrderMissingFields()

        try:
            price = float(price)
        except (ValueError, TypeError) as e:
            logger.error("[Order Manager] add_custom_item, coercing price to float failed\n%s", e)
            return

        try:
            self.add_item(
                name,
                price,
                item_id,
                barcode,
                is_custom,
                unit_cost=None,
                is_cigarette=None,
            )
        except Exception as e:
            logger.warning("Exception in add custom item order_manager.py: %s", e)

        try:
            self.app.utilities.update_display()
            self.app.utilities.update_financial_summary()
            self.app.popup_manager.custom_item_popup.dismiss()
            self.app.popup_manager.cash_input.text = ""
        except Exception as e:
            logger.warning(f"[Order Manager]: add_custom_item\n{e}")

    def add_item(self, item_name, item_price, item_id=None, barcode=None, is_custom=False, unit_cost=None, is_cigarette=None):
        item_id = str(item_id) if item_id not in (None, "") else str(uuid.uuid4())

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
                unit_cost=float(unit_cost) if unit_cost not in (None, "") else None,
                is_cigarette=int(is_cigarette) if is_cigarette not in (None, "") else None,
                quantity=1,
            )
            li.recompute()
            self.items[li.item_id] = li

        self.recalculate_order_totals()

    def finalize_order(self):
        self.recalculate_order_totals()
        order_details = self.get_order_details()

        order_summary = f"[size=18][b]Order Summary:[/b][/size]\n\n"

        for item in order_details.items.values():
            item_name = item.name
            quantity = item.quantity
            total_price_for_item = item.total_price

            try:
                total_price_float = float(total_price_for_item)
            except ValueError as e:
                logger.warning(e)
                continue

            order_summary += self.create_order_summary_item(item_name, quantity, total_price_float)

        order_summary += f"\nSubtotal: ${order_details.subtotal:.2f}"
        order_summary += f"\nTax: ${order_details.tax_amount:.2f}"
        if order_details.total_discount > 0:
            order_summary += f"\nDiscount: ${order_details.total_discount:.2f}"
        order_summary += f"\n\n[size=20]Total: [b]${order_details.total_with_tax:.2f}[/b][/size]"

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
        self.order.order_level_discount = max(0.0, float(amount))
        self.recalculate_order_totals()

    def add_order_level_discount(self, amount):
        self.order.order_level_discount = max(0.0, float(self.order.order_level_discount) + float(amount))
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
        if float(self.order.order_level_discount) > 0:
            self.order.order_level_discount = 0.0
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
