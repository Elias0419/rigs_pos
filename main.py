import time
import sys
import termios
import tty
import threading
import os
from pynput.keyboard import Listener
from barcode_scanner import BarcodeScanner
from mock_barcode_scanner import MockBarcodeScanner
from database_manager import DatabaseManager
from order_manager import OrderManager
from flask_backend import run_flask_app


def flush_input():
    termios.tcflush(sys.stdin, termios.TCIOFLUSH)


def main():
    scanner = BarcodeScanner()
    # mock scanner
    #scanner = MockBarcodeScanner()
    db_manager = DatabaseManager('my_items_database.db')
    order_manager = OrderManager(tax_rate=0.08)

    try:
        while True:
            print("Scan a barcode or type 'checkout' to finalize the order...")
            barcode = scanner.read_barcode()

            if barcode and barcode.lower() == 'checkout':
                scanner.listener.stop()
                time.sleep(0.5)
                flush_input()

                total = order_manager.calculate_total_with_tax()
                print(f"Total amount with tax: ${total:.2f}")
                amount_paid = float(input("Enter amount paid: "))
                change = order_manager.process_payment(amount_paid)
                print(f"Change to give back: ${change:.2f}")
                order_manager.clear_order()

                scanner.listener = Listener(on_press=scanner.on_press, on_release=scanner.on_release)
                scanner.listener.start()
                continue

            if barcode:
                item_details = db_manager.get_item_details(barcode)
                if item_details:
                    item = {'name': item_details[0], 'price': item_details[1]}
                    order_manager.add_item(item)
                    print(f"Added to order: {item['name']} for ${item['price']:.2f}")
                else:
                    print("Item not found in the database.")

                    scanner.listener.stop()
                    time.sleep(0.5)
                    flush_input()

                    name = input("Enter item name: ")
                    price = float(input("Enter item price: "))

                    if db_manager.add_item(barcode, name, price):
                        print(f"Item '{name}' added to the database.")

                    scanner.listener = Listener(on_press=scanner.on_press, on_release=scanner.on_release)
                    scanner.listener.start()
                scanner.current_barcode = ''
            else:
                print("No barcode scanned.")

    except KeyboardInterrupt:
        print("\nExiting main application.")
    finally:
        scanner.close()
        db_manager.close()


if __name__ == "__main__":
    flask_thread = threading.Thread(target=run_flask_app)
    flask_thread.start()
    main()
