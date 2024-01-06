from pynput.keyboard import Key, Listener
import threading
import requests
import time
import re


class BarcodeScanner:
    def __init__(self):
        self.current_barcode = ''
        self.scan_timeout = 0.1
        self.last_key_time = None
        self.barcode_ready = threading.Event()
        self.listener = Listener(on_press=self.on_press, on_release=self.on_release)
        self.listener.start()

    def is_barcode_ready(self):
        return self.barcode_ready.is_set()

    # def on_press(self, key):
    #     current_time = time.time()
    #     if self.last_key_time is not None:
    #         time_diff = current_time - self.last_key_time
    #         if time_diff >= 0.1:  # assume a human can't type this fast
    #             self.current_barcode = ''
    #
    #     self.last_key_time = current_time
    #
    #     try:
    #         if key.char is not None:
    #             self.current_barcode += key.char
    #     except AttributeError:
    #         pass
    #
    # def on_release(self, key):
    #
    #     if len(self.current_barcode) == 12:
    #         self.barcode_ready.set()

    def on_press(self, key):
        current_time = time.time()
        if self.last_key_time is not None:
            time_diff = current_time - self.last_key_time
            if time_diff >= self.scan_timeout:
                self.current_barcode = ''
        self.last_key_time = current_time

        try:
            if key.char is not None:
                self.current_barcode += key.char
        except AttributeError:
            pass

    def on_release(self, key):
        if self.is_valid_barcode(self.current_barcode):
            self.barcode_ready.set()

    def is_valid_barcode(self, barcode):
        return re.match(r'^\d{6,8,12,13}\s*$', barcode) is not None


    def read_barcode(self):
        self.barcode_ready.wait()
        barcode = self.current_barcode
        self.current_barcode = ''
        self.barcode_ready.clear()
        return barcode

    def on_barcode_scanned(self, barcode):
        pass


    def close(self):
        self.listener.stop()



