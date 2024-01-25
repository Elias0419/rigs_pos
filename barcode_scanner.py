from pynput.keyboard import Key, Listener
import threading
import time


class BarcodeScanner:
    def __init__(self, barcode_scanned_callback=None):
        self.current_barcode = ""
        self.scan_timeout = 0.25
        self.last_key_time = None
        self.barcode_scanned_callback = barcode_scanned_callback
        self.barcode_ready = threading.Event()
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

    def on_barcode_scanned(self, barcode):
        pass

    def close(self):
        self.listener.stop()
