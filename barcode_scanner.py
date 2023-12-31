from pynput.keyboard import Key, Listener
import threading
import requests
import time

class BarcodeScanner:
    def __init__(self):
        self.current_barcode = ''
        self.last_key_time = None  # Initialize with None
        self.barcode_ready = threading.Event()
        self.listener = Listener(on_press=self.on_press, on_release=self.on_release)
        self.listener.start()

    def on_press(self, key):
        print("DEBUG barcode_scanner on_press")

        current_time = time.time()

        if self.last_key_time is not None:
            time_diff = current_time - self.last_key_time

            if time_diff >= 0.05:  # assume a human can't type this fast
                self.current_barcode = ''

        self.last_key_time = current_time

        try:
            if key.char is not None:
                self.current_barcode += key.char
        except AttributeError:
            pass

    def on_release(self, key):
        print("DEBUG barcode_scanner on_release")

        if key == Key.enter:
            if len(self.current_barcode) > 6:
                self.barcode_ready.set()
                #self.on_barcode_scanned(self.current_barcode) # part of flask integration
            self.current_barcode = ''

    def read_barcode(self):
        print("DEBUG barcode_scanner read_barcode")

        self.barcode_ready.wait()
        barcode = self.current_barcode
        self.current_barcode = ''
        self.barcode_ready.clear()
        return barcode

    def on_barcode_scanned(self, barcode):
        print("DEBUG barcode_scanner on_barcode_scanned")

        # url = 'http://localhost:5000/barcode-scanned' # part of flask integration TODO
        # data = {'barcode': barcode}
        # try:
        #     requests.post(url, json=data)
        # except requests.RequestException as e:
        #     print(f"Error sending barcode to server: {e}")

    def close(self):
        self.listener.stop()


if __name__ == "__main__":
    scanner = BarcodeScanner()
    try:
        while True:
            print("Scan a barcode...")
            barcode = scanner.read_barcode()
            if barcode:
                print(f"Scanned barcode: {barcode}")
    except KeyboardInterrupt:
        print("\nExiting barcode scanner.")
    finally:
        scanner.close()
