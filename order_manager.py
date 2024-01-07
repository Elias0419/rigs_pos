import uuid

class OrderManager:
    def __init__(self, tax_rate=0.07):
        self.items = []
        self.total = 0.0
        self.tax_rate = tax_rate
        self._total_with_tax = None
        self.order_id = str(uuid.uuid4())

    def _update_total_with_tax(self):
        self._total_with_tax = self.total * (1 + self.tax_rate)

    def calculate_total_with_tax(self):
        self._update_total_with_tax()
        return self._total_with_tax

    def add_manual_item(self, name, price):
        item = {'name': name, 'price': price}
        self.items.append(item)
        self.total += price

    def add_item(self, item, price):
        self.items.append({'name': item, 'price': float(price)})
        self.total += float(price)
        self._update_total_with_tax()


    def remove_item(self, item_id):
        print("DEBUG order_manager remove_item", item_id)
        item_to_remove = next((item for item in self.items if item['id'] == item_id), None)
        if item_to_remove:
            self.items.remove(item_to_remove)
            self.total -= item_to_remove['price']
            self._update_total_with_tax()
        else:
            print(f"Item with ID {item_id} not found.")

    def get_order_details(self):
        print("DEBUG order_manager get_order_details")
        print(self.items, self.total)
        return {
            'order_id': self.order_id,
            'items': self.items,
            'total': self.total,
            'total_with_tax': self._total_with_tax
        }

    def clear_order(self):
        self.items = []
        self.total = 0.0
        self._total_with_tax = None
        self.order_id = str(uuid.uuid4())

