import uuid

class OrderManager:
    def __init__(self, tax_rate=0.07):  # Adjusted tax rate
        self.items = []
        self.total = 0.0
        self.tax_rate = tax_rate
        self._total_with_tax = None
        self.order_id = str(uuid.uuid4())  # Unique order ID

    def _update_total_with_tax(self):
        self._total_with_tax = self.total * (1 + self.tax_rate)

    def add_item(self, item):
        print("DEBUG order_manager add_item", item)
        self.items.append(item)
        self.total += item['price']
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
        self.order_id = str(uuid.uuid4())  # Reset with a new order ID

    # def process_payment(self, amount_paid):
    #     total_with_tax = self.calculate_total_with_tax()
    #     return max(0, amount_paid - total_with_tax)




if __name__ == "__main__":
    print("DEBUG order_manager init")

    order_manager = OrderManager(tax_rate=0.08)  
    order_manager.add_item({'name': 'Item 1', 'price': 10.00})
    order_manager.add_item({'name': 'Item 2', 'price': 5.00})
    print("Order details:", order_manager.get_order_details())
    print("Change given:", order_manager.process_payment(20.00))  
    order_manager.clear_order()
