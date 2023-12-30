class OrderManager:
    def __init__(self, tax_rate=0.7):
        self.items = []  
        self.total = 0.0
        self.tax_rate = tax_rate

    def add_item(self, item):
        print("DEBUG order_manager add_item", item)
        self.items.append(item)
        self.total += item['price']

    def calculate_total_with_tax(self):
        print("DEBUG order_manager calculate_total_with_tax")
        total_with_tax = self.total * (1 + self.tax_rate)
        self.total = 0  # Reset the total
        return total_with_tax

    def process_payment(self, amount_paid):
        total_with_tax = self.calculate_total_with_tax()
        return max(0, amount_paid - total_with_tax)  

    def clear_order(self):
        self.items = []
        self.total = 0.0

    def get_order_details(self):
        print("DEBUG order_manager get_order_details")
        print(self.items, self.total)
        return {
            'items': self.items,
            'total': self.total,
            'total_with_tax': self.calculate_total_with_tax()
        }


if __name__ == "__main__":
    print("DEBUG order_manager init")

    order_manager = OrderManager(tax_rate=0.08)  
    order_manager.add_item({'name': 'Item 1', 'price': 10.00})
    order_manager.add_item({'name': 'Item 2', 'price': 5.00})
    print("Order details:", order_manager.get_order_details())
    print("Change given:", order_manager.process_payment(20.00))  
    order_manager.clear_order()
