import time
import sys
import termios
import tty
import threading
import os
import logging
from pynput.keyboard import Listener
from barcode_scanner import BarcodeScanner
from mock_barcode_scanner import MockBarcodeScanner
from database_manager import DatabaseManager
from order_manager import OrderManager
from open_cash_drawer import open_cash_drawer
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
        return OrderManager(tax_rate=0.08)
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

def process_checkout(scanner, order_manager):
    try:
        total_with_tax = order_manager.calculate_total_with_tax()
        print(f"Total amount with tax: ${total_with_tax:.2f}")

        # Ask for payment method
        payment_method = input("Enter payment method (cash/card): ").lower()

        if payment_method == "cash":
            while True:  # Keep asking until a valid amount is provided
                amount_paid = float(input("Enter amount paid in cash: "))
                if amount_paid < total_with_tax:
                    print("Insufficient amount paid. Please enter a valid amount.")
                    continue  # Prompt again for the correct amount
                change = amount_paid - total_with_tax
                print(f"Change to give back: ${change:.2f}")
                open_cash_drawer()
                order_manager.clear_order()
                break  # Break the loop once a valid amount is entered

        elif payment_method == "card":
            print("Processing card payment. Please put the receipt in the register.")
            open_cash_drawer()
            order_manager.clear_order()
            # Additional logic for credit card processing can be added here

        order_manager.clear_order()
    except ValueError as e:
        print(f"Invalid input: {e}")
    except Exception as e:
        logging.error(f"Error processing checkout: {e}")




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

def enter_command_mode(scanner, order_manager):
    print("DEBUG main entered command mode function")
    while True:
        command = input("Hit 'C' to checkout, 'H' for help, 'esc' to return to the barcode scanner: ").lower()
        if command == 'c':
            process_checkout(scanner, order_manager)
            break
        elif command == 'h':
            print("Help: [Your help instructions here]")
        elif command == 'esc':
            break


def main():
    scanner = setup_scanner()
    db_manager = setup_database_manager()
    order_manager = setup_order_manager()

    try:
        while True:
           # print("Scan a barcode or press 'esc' to enter commands.")
            #print("DEBUG main loop scanner.command_mode ", scanner.command_mode)
            # Check if command mode was activated before waiting for barcode
            if scanner.command_mode:
                print("DEBUG main command mod check #1")
                enter_command_mode(scanner, order_manager)
                scanner.command_mode = False  # Reset the command mode flag
                restart_scanner_listener(scanner)
                continue

            if scanner.is_barcode_ready():
                print("DEBUG main is_barcode_ready")
                barcode = scanner.read_barcode()

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
    #flask_thread = threading.Thread(target=run_flask_app)
    #flask_thread.start()
    main()
