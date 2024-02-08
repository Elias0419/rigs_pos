import uuid


class OrderManager:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(OrderManager, cls).__new__(cls, *args, **kwargs)
        return cls._instance


    def __init__(self, tax_rate=0.07):
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
