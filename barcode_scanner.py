from pynput.keyboard import Key, Listener
import threading
import time


class BarcodeScanner:
    def __init__(self, ref, barcode_scanned_callback=None):
        self.current_barcode = ""
        self.scan_timeout = 0.25
        self.last_key_time = None
        self.barcode_scanned_callback = barcode_scanned_callback
        self.barcode_ready = threading.Event()
        self.app = ref
        self.listener = Listener(on_press=self.on_press, on_release=self.on_release)
        self.listener.start()

    def is_barcode_ready(self):
        return self.barcode_ready.is_set()

    def on_press(self, key):
        current_time = time.time()
        if self.last_key_time is not None:
            time_diff = current_time - self.last_key_time
            if time_diff >= self.scan_timeout:
                self.current_barcode = ""

        self.last_key_time = current_time

        try:
            if key.char is not None:
                self.current_barcode += key.char
        except AttributeError:
            pass

    def on_release(self, key):
        if key == Key.enter:
            if self.current_barcode:
                self.barcode_ready.set()
                if self.barcode_scanned_callback:
                    self.barcode_scanned_callback(self.current_barcode.strip())

    def read_barcode(self):
        self.barcode_ready.wait()
        barcode = self.current_barcode.strip()
        self.current_barcode = ""
        self.barcode_ready.clear()
        return barcode



    def close(self):
        self.listener.stop()

    def check_for_scanned_barcode(self, dt):
        if self.is_barcode_ready():
            barcode = self.read_barcode()
            self.handle_global_barcode_scan(barcode)

    def handle_global_barcode_scan(self, barcode):
        if self.app.current_context == "inventory":
            self.app.inventory_manager.handle_scanned_barcode(barcode)
        elif self.app.current_context == "label":
            self.app.label_manager.handle_scanned_barcode(barcode)
        elif self.app.current_context == "inventory_item":
            self.app.inventory_manager.handle_scanned_barcode_item(barcode)
        # elif self.current_context == "history":
        #     self.history_manager.handle_scanned_barcode(barcode)
        else:
            self.handle_scanned_barcode(barcode)

    def handle_scanned_barcode(self, barcode):
        try:
            if '-' in barcode and any(c.isalpha() for c in barcode):
                self.app.history_manager.display_order_details_from_barcode_scan(barcode)
            else:
                item_details = self.app.db_manager.get_item_details(barcode)

                if item_details:
                    item_name, item_price = item_details
                    self.app.order_manager.add_item(item_name, item_price)
                    self.app.utilities.update_display()
                    self.app.utilities.update_financial_summary()
                    return item_details
                else:
                    #self.app.popup_preloader.update_and_show_add_or_bypass_popup(barcode)
                    self.app.popup_manager.show_add_or_bypass_popup(barcode)
        except Exception as e:
            print(f"Exception in handle_scanned_barcode\n{e}")
