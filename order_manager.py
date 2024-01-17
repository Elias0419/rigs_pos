import uuid


class OrderManager:
    def __init__(self, tax_rate=0.07):
        self.items = {}
        self.total = 0.0
        self.subtotal = 0.0
        self.tax_rate = tax_rate
        self.tax_amount = 0.0
        self._total_with_tax = None
        self.order_id = str(uuid.uuid4())
        self.order_discount = 0.0

    def _update_total_with_tax(self):
        self.tax_amount = self.total * self.tax_rate
        self._total_with_tax = self.total + self.tax_amount

    def calculate_total_with_tax(self):
        self._update_total_with_tax()
        return self._total_with_tax

    def update_tax_amount(self):
        self.tax_amount = self.total * self.tax_rate
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
        print(self.items)
        item_to_remove = next(
            (key for key, value in self.items.items() if value["name"] == item_name),
            None,
        )
        if item_to_remove:
            self.total -= self.items[item_to_remove]["total_price"]
            self.subtotal -= self.items[item_to_remove]["total_price"]

            del self.items[item_to_remove]
            self._update_total_with_tax()
        else:
            pass

    def get_order_details(self):
        return {
            "order_id": self.order_id,
            "items": self.items,
            "total": self.total,
            "total_with_tax": self._total_with_tax,
        }

    def clear_order(self):
        self.items = {}
        self.total = 0.0
        self._total_with_tax = None
        self.order_id = str(uuid.uuid4())
        self.order_discount = 0.0
        self.tax_amount = 0.0
        self.subtotal = 0.0

    def update_item_quantity(self, item_name, new_quantity):
        if item_name in self.items and new_quantity > 0:
            item = self.items[item_name]
            single_item_price = item["total_price"] / item["quantity"]
            self.total -= item["total_price"]
            self.items[item_name]["quantity"] = new_quantity
            self.items[item_name]["total_price"] = single_item_price * new_quantity
            self.total += self.items[item_name]["total_price"]
            self._update_total_with_tax()
        elif new_quantity == 0:
            self.remove_item(item_name)
        else:
            pass


    def adjust_order_to_target_total(self, target_total_with_tax):
        adjusted_subtotal = target_total_with_tax / (1 + self.tax_rate)

        discount = self.subtotal - adjusted_subtotal

        if discount < 0 or discount > self.subtotal:
            print("Adjustment not possible.")
            return False

        self.subtotal = adjusted_subtotal
        self.total = adjusted_subtotal
        self.order_discount += discount

        # Update tax amount and total with tax
        self.tax_amount = self.total * self.tax_rate
        self._total_with_tax = self.total + self.tax_amount

        return True




    def add_discount(self, discount_amount=None, discount_percentage=None):
        if discount_amount is not None:
            self.order_discount += discount_amount
            self.total = self.subtotal - discount_amount
        elif discount_percentage is not None:
            discount = self.subtotal * (discount_percentage / 100)
            self.order_discount += discount
            self.total = self.subtotal - discount
        self.update_tax_amount()
        self._update_total_with_tax()



    def calculate_final_total(self):

        discounted_total = self.total - self.order_discount
        final_total_with_tax = discounted_total * (1 + self.tax_rate)
        return final_total_with_tax
