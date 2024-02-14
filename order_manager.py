import uuid
from open_cash_drawer import open_cash_drawer

class OrderManager:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(OrderManager, cls).__new__(cls)
        return cls._instance


    def __init__(self, ref, tax_rate=0.07):
        if not hasattr(self, "_init"):
            print("order manager init", self)
            self.items = {}
            self.total = 0.0
            self.subtotal = 0.0
            self.tax_amount = 0.0
            self.change_given = 0.0
            self.order_discount = 0.0
            self.amount_tendered = 0.0
            self.tax_rate = tax_rate
            self.payment_method = None
            self._total_with_tax = None
            self.order_id = str(uuid.uuid4())
            self.app = ref
            self._init = True

    def _update_total_with_tax(self):
        self.tax_amount = self.total * self.tax_rate
        self._total_with_tax = self.total + self.tax_amount

    def calculate_total_with_tax(self):
        self._update_total_with_tax()
        return self._total_with_tax

    def update_tax_amount(self):
        self.tax_amount = max(self.total * self.tax_rate, 0)
        print(self.tax_amount)
        return self.tax_amount

    def add_item(self, item_name, item_price):
        item_id = str(uuid.uuid4())

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
            self.items[existing_item]["total_price"] += item_price
        else:
            self.items[item_id] = {
                "name": item_name,
                "price": item_price,
                "quantity": 1,
                "total_price": item_price,
            }
        self.total += item_price
        self.subtotal += item_price
        self._update_total_with_tax()

    def remove_item(self, item_name):
        print("Current Items:", self.items)
        item_to_remove = next(
            (key for key, value in self.items.items() if value["name"] == item_name),
            None,
        )
        if item_to_remove:
            removed_item_total = self.items[item_to_remove]["total_price"]
            self.subtotal -= removed_item_total

            self.total = max(self.subtotal - self.order_discount, 0)

            del self.items[item_to_remove]
            self.order_discount = 0.0
            self.update_tax_amount()
            self._update_total_with_tax()
        else:
            pass

    def get_order_details(self):
        return {
            "order_id": self.order_id,
            "items": self.items,
            "subtotal": self.subtotal,
            "total": self.total,
            "tax_rate": self.tax_rate,
            "tax_amount": self.tax_amount,
            "total_with_tax": self._total_with_tax,
            "discount": self.order_discount,
            "payment_method": self.payment_method,
            "amount_tendered": self.amount_tendered,
            "change_given": self.change_given,
        }

    def clear_order(self):
        self.items = {}
        self.total = 0.0
        self._total_with_tax = None
        self.order_id = str(uuid.uuid4())
        self.order_discount = 0.0
        self.tax_amount = 0.0
        self.subtotal = 0.0
        self.payment_method = None
        self.amount_tendered = 0.0
        self.change_given = 0.0

    def adjust_item_quantity(self, item_id, adjustment):
        if item_id in self.items:
            item = self.items[item_id]
            new_quantity = max(item["quantity"] + adjustment, 1)
            single_item_price = item["price"]
            self.total -= item["total_price"]
            item["quantity"] = new_quantity
            item["total_price"] = single_item_price * new_quantity
            self.total += item["total_price"]
            self.subtotal = max(self.total - self.order_discount, 0)
            self._update_total_with_tax()

    def adjust_order_to_target_total(self, target_total_with_tax):
        if target_total_with_tax != "":
            adjusted_subtotal = target_total_with_tax / (1 + self.tax_rate)
            discount = self.subtotal - adjusted_subtotal

            if discount < 0 or discount > self.subtotal:
                return False

            self.subtotal = adjusted_subtotal
            self.total = adjusted_subtotal
            self.order_discount += discount
            self.tax_amount = self.total * self.tax_rate
            self._total_with_tax = self.total + self.tax_amount

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

    def add_custom_item(self, instance):
        price = self.app.popup_manager.cash_input.text
        try:
            price = float(price)
        except Exception as e:
            print("Exception in add custom item order_manager.py,", e)

        custom_item_name = "Custom Item"
        self.add_item(custom_item_name, price)
        self.app.utilities.update_display()
        self.app.utilities.update_financial_summary()
        self.app.popup_manager.custom_item_popup.dismiss()
        self.app.popup_manager.cash_input.text = ""

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
                print(e)
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

    def discount_single_item(self, discount_amount, percent=False):
        if percent:

            self.add_discount(discount_amount, percent=True)

        else:
            self.add_discount(discount_amount)

        self.app.utilities.update_display()
        self.app.utilities.update_financial_summary()
        self.app.popup_manager.discount_amount_input.text = ""
        self.app.popup_manager.discount_popup.dismiss()
        self.app.popup_manager.item_popup.dismiss()

    def discount_entire_order(self, discount_amount, percent=False):
        if discount_amount != "":
            try:
                discount_amount = float(discount_amount)
            except Exception as e:
                print(f"exception in discount entire order\n{e}")
                pass
            if percent:
                discount_value = self.subtotal * discount_amount / 100
            else:
                discount_value = discount_amount

            discount_value = min(discount_value, self.subtotal)

            self.order_discount += discount_value
            self.total = max(self.subtotal - self.order_discount, 0)
            try:
                self.update_tax_amount()
                self._update_total_with_tax()
                self.app.utilities.update_display()
                self.app.utilities.update_financial_summary()
            except Exception as e:
                print(f"exception updating totals in discount entire order\n{e}")
            self.app.popup_manager.discount_order_amount_input.text = ""
            self.app.popup_manager.discount_order_popup.dismiss()
            self.app.financial_summary.order_mod_popup.dismiss()

    def add_adjusted_price_item(self):
        target_amount = self.app.popup_manager.adjust_price_cash_input.text
        try:
            target_amount = float(target_amount)
        except ValueError as e:
            print(e)

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

    def adjust_item_quantity_in(self, item_id, adjustment):
        self.adjust_item_quantity(item_id, adjustment)
        self.app.popup_manager.item_popup.dismiss()
        self.app.popup_manager.show_item_details_popup(item_id)
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




