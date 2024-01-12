# import uuid
#
#
# class OrderManager:
#     def __init__(self, tax_rate=0.07):
#         self.items = []
#         self.total = 0.0
#         self.tax_rate = tax_rate
#         self._total_with_tax = None
#         self.order_id = str(uuid.uuid4())
#
#     def _update_total_with_tax(self):
#         self._total_with_tax = self.total * (1 + self.tax_rate)
#
#     def calculate_total_with_tax(self):
#         self._update_total_with_tax()
#         return self._total_with_tax
#
#     def add_manual_item(self, name, price):
#         item = {"name": name, "price": price}
#         self.items.append(item)
#         self.total += price
#
#     def add_item(self, item, price):
#         self.items.append({"name": item, "price": float(price)})
#         self.total += float(price)
#         self._update_total_with_tax()
#
#     def remove_item(self, item_id):
#         print("DEBUG order_manager remove_item", item_id)
#         item_to_remove = next(
#             (item for item in self.items if item["id"] == item_id), None
#         )
#         if item_to_remove:
#             self.items.remove(item_to_remove)
#             self.total -= item_to_remove["price"]
#             self._update_total_with_tax()
#         else:
#             print(f"Item with ID {item_id} not found.")
#
#     def get_order_details(self):
#         print("DEBUG order_manager get_order_details")
#         print(self.items, self.total)
#         return {
#             "order_id": self.order_id,
#             "items": self.items,
#             "total": self.total,
#             "total_with_tax": self._total_with_tax,
#         }
#
#     def clear_order(self):
#         self.items = []
#         self.total = 0.0
#         self._total_with_tax = None
#         self.order_id = str(uuid.uuid4())
#
#     def update_item_price(self, name, new_price):
#         for i, item in enumerate(self.items):
#             if item.get("name") == name:
#                 old_price = item.get("price", 0)
#                 self.total -= old_price  # Subtract the old price
#                 self.items[i] = {
#                     "name": name,
#                     "price": new_price,
#                 }  # Update the dictionary
#                 self.total += new_price  # Add the new price
#                 self._update_total_with_tax()
#                 return  # Exit the method after updating the item
#
#         print(f"Item named '{name}' not found in the order.")
import uuid

class OrderManager:
    def __init__(self, tax_rate=0.07):
        self.items = {}
        self.total = 0.0
        self.tax_rate = tax_rate
        self._total_with_tax = None
        self.order_id = str(uuid.uuid4())

    def _update_total_with_tax(self):
        self._total_with_tax = self.total * (1 + self.tax_rate)

    def calculate_total_with_tax(self):
        self._update_total_with_tax()
        return self._total_with_tax


    def add_item(self, item_name, item_price):
        item_id = str(uuid.uuid4())

        existing_item = next((key for key, value in self.items.items()
                            if value['name'] == item_name and value['price'] == item_price), None)

        if existing_item:
            self.items[existing_item]['quantity'] += 1
            self.items[existing_item]['total_price'] += item_price
        else:
            self.items[item_id] = {
                'name': item_name,
                'price': item_price,
                'quantity': 1,
                'total_price': item_price
            }
        self.total += item_price
        self._update_total_with_tax()



    def remove_item(self, item_name):
        if item_name in self.items:
            item_to_remove = self.items[item_name]
            self.total -= item_to_remove['total_price']
            del self.items[item_name]
            self._update_total_with_tax()
        else:
            print(f"Item named '{item_name}' not found.")

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

    def update_item_quantity(self, item_name, new_quantity):
        if item_name in self.items and new_quantity > 0:
            item = self.items[item_name]
            single_item_price = item['total_price'] / item['quantity']
            self.total -= item['total_price']  # Subtract the old total price
            self.items[item_name]['quantity'] = new_quantity
            self.items[item_name]['total_price'] = single_item_price * new_quantity
            self.total += self.items[item_name]['total_price']  # Add the new total price
            self._update_total_with_tax()
        elif new_quantity == 0:
            self.remove_item(item_name)
        else:
            print(f"Item named '{item_name}' not found or invalid quantity.")

    def update_item_price(self, item_name, new_price):
        print("update item price")
        print(self.items)
        print("item_name", item_name)
        print("new_price", new_price)

        item_updated = False

        for item_id, item in self.items.items():
            if item['name'] == item_name:
                print("Found item to update")
                old_price = item["price"]
                old_total_price = item["total_price"]
                print("old_price", old_price)
                print("old_total_price", old_total_price)

                # Adjusting total price for the changed item price
                self.total -= old_total_price
                new_total_price = new_price * item['quantity']
                self.items[item_id] = {
                    "name": item_name,
                    "price": new_price,
                    "quantity": item["quantity"],
                    "total_price": new_total_price
                }

                self.total += new_total_price
                print("new items with new price", new_price)
                print("new total", self.total)
                item_updated = True
            self._update_total_with_tax()
            if item_updated:
                return

        print("Item not found")


        # for i, item in enumerate(self.items):
        #     if item['name'] == item_name:
        #         old_price = item["price"]
        #         self.total -= old_price
        #         self.items[i] = {
        #             "name": item_name,
        #             "price": new_price,
        #         }
        #         self.total += new_price
        #         self._update_total_with_tax()
        #         return

        # print(f"Item named '{name}' not found in the order.")

    # Add other necessary methods or update existing ones if needed
