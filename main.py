import time
import sys
import termios
import tty
import threading
import os
import logging
import json
from pynput.keyboard import Listener
from barcode_scanner import BarcodeScanner
from mock_barcode_scanner import MockBarcodeScanner
from database_manager import DatabaseManager
from order_manager import OrderManager
#from open_cash_drawer import open_cash_drawer
from mock_open_cash_drawer import open_cash_drawer
# from flask_backend import run_flask_app

# Initialize logging
logging.basicConfig(level=logging.INFO)

def flush_input():
    try:
        termios.tcflush(sys.stdin, termios.TCIOFLUSH)
    except Exception as e:
        logging.error(f"Error flushing input: {e}")

def setup_scanner():
    try:
        return BarcodeScanner()
    except Exception as e:
        logging.error(f"Error setting up scanner: {e}")
        sys.exit(1)

def setup_database_manager():
    try:
        return DatabaseManager('my_items_database.db')
    except Exception as e:
        logging.error(f"Error setting up database manager: {e}")
        sys.exit(1)

def setup_order_manager():
    try:
        return OrderManager(tax_rate=0.07)
    except Exception as e:
        logging.error(f"Error setting up order manager: {e}")
        sys.exit(1)

def restart_scanner_listener(scanner):
    try:
        scanner.listener.stop()
        time.sleep(0.5)
        flush_input()
        scanner.listener = Listener(on_press=scanner.on_press, on_release=scanner.on_release)
        scanner.listener.start()
    except Exception as e:
        logging.error(f"Error restarting scanner listener: {e}")

def process_checkout(scanner, order_manager, db_manager, order_details):
    try:
        total = order_details['total']
        total_with_tax = order_manager.calculate_total_with_tax()
        print(f"Total amount with tax: ${total_with_tax:.2f}")

        payment_method = input("Enter payment method (cash/card): ").lower()

        if payment_method == "cash":
            while True:
                amount_paid = float(input("Enter amount paid in cash: "))
                if amount_paid < total_with_tax:
                    print("Insufficient amount paid. Please enter a valid amount.")
                    continue
                change = amount_paid - total_with_tax
                print(f"Change to give back: ${change:.2f}")
                break

        elif payment_method == "card":
            print("Processing card payment. Please put the receipt in the register.")

        open_cash_drawer()
        order_details = order_manager.get_order_details()
        send_order_to_history_database(order_details, order_manager, db_manager)
        order_manager.clear_order()

    except ValueError as e:
        print(f"Invalid input: {e}")
    except Exception as e:
        logging.error(f"Error processing checkout: {str(e)}")

def send_order_to_history_database(order_details, order_manager, db_manager):
    db_manager.add_order_history(order_details['order_id'], json.dumps(order_details['items']),
                                 order_details['total_with_tax'],order_details['total'])




def add_item_to_database(db_manager, barcode):
    try:
        name = input("Enter item name: ")
        price = float(input("Enter item price: "))
        if db_manager.add_item(barcode, name, price):
            print(f"Item '{name}' added to the database.")
    except Exception as e:
        logging.error(f"Error adding item to database: {e}")
    finally:
        pass

def on_press(key):
    if key == Key.esc:
        return False  # Stop listener

def enter_command_mode(scanner, order_manager, db_manager, order_details):
    print("DEBUG main entered command mode function")

    while True:
        flush_input()
        command = input("'c' to checkout, 'h' for history, 'p' to print current order, 'm' for manual transaction, 'e' return to barcode scanner: ").lower()
        if command == 'c':
            process_checkout(scanner, order_manager, db_manager, order_details)
            break
        elif command == 'h':
            print("Help: [Your help instructions here]")
        elif command == 'p':
            updated_order_details = order_manager.get_order_details()
            print(updated_order_details)
            updated_order_details = None
        elif command == 'm':
            item_name = input("Enter item name: ")
            item_price = float(input("Enter item price: "))
            order_manager.add_manual_item(item_name, item_price)
            print(f"Added {item_name} for ${item_price:.2f} to the order.")
        elif command == 'e': # this is the string E TODO consider listeners here
            print("DEBUG main pressed escape to exit command mode")
            restart_scanner_listener(scanner)
            break
        time.sleep(0.1)


def main():
    scanner = setup_scanner()
    db_manager = setup_database_manager()
    order_manager = setup_order_manager()
    order_details = order_manager.get_order_details()

    try:
        while True:
           # print("Scan a barcode or press 'esc' to enter commands.")

            if scanner.command_mode:
                print("DEBUG main command mod check #1")
                enter_command_mode(scanner, order_manager, db_manager, order_details)
                print("DEBUG: Exiting command mode")
                scanner.command_mode = False  # Reset the command mode flag
                restart_scanner_listener(scanner)
                continue
            if scanner.is_barcode_ready():
                print("DEBUG main is_barcode_ready")
                barcode = scanner.read_barcode()
                print(f"DEBUG: Scanned barcode: {barcode}")
                if barcode:
                    try:
                        item_details = db_manager.get_item_details(barcode)
                    except Exception as e:
                        logging.error(f"Error retrieving item details: {e}")
                        continue

                    if item_details:
                        item = {'name': item_details[0], 'price': item_details[1]}
                        order_manager.add_item(item)
                        print(f"Added to order: {item['name']} for ${item['price']:.2f}")
                    else:
                        print("Item not found in the database.")
                        restart_scanner_listener(scanner)
                        add_item_to_database(db_manager, barcode)
                    scanner.current_barcode = ''
            # if scanner.command_mode:
            #     print("DEBUG main command mod check #2")
            #     enter_command_mode()
            #     scanner.command_mode = False
            #     continue

            # Handle case where no barcode is scanned
           # print("No barcode scanned.")
            time.sleep(0.1)

    except KeyboardInterrupt:
        print("\nExiting main application.")
    finally:
        ("DEBUG main inside the finally loop")
        # Stop the barcode scanner listener if it's running
        if scanner and scanner.listener:
            ("DEBUG main scanner stopping")
            scanner.listener.stop()

        # Close any open database connections
        if db_manager:
            db_manager.close_connection()

        # Log the application shutdown
        logging.info("Application shutdown gracefully.")
if __name__ == "__main__":
    db_manager = DatabaseManager('my_items_database.db')
    db_manager.create_order_history_table()
    #flask_thread = threading.Thread(target=run_flask_app)
    #flask_thread.start()
    main()

