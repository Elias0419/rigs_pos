import threading
from pynput.keyboard import Key, Listener


class MockBarcodeScanner:
    def __init__(self):
        self.current_barcode = ''
        self.barcode_ready = threading.Event()
        self.listener = Listener(on_press=self.on_press, on_release=self.on_release)
        self.listener.start()
    def on_press(self, key):
        # This method can be used to simulate barcode input
        self.current_barcode = input("Enter mock barcode: ")
        self.barcode_ready.set()
    def on_release(self, key):
        print("DEBUG barcode_scanner on_release")

        if key == Key.enter:
            self.barcode_ready.set()
            self.on_barcode_scanned(self.current_barcode)
            self.current_barcode = ''

    def read_barcode(self):
        print("DEBUG mock_barcode_scanner read_barcode")

        # Instead of waiting for hardware input, we simulate it with a command line input
        self.on_press("a")  # Simulate a barcode scan by calling on_press
        self.barcode_ready.wait()

        barcode = self.current_barcode
        self.current_barcode = ''
        self.barcode_ready.clear()
        return barcode

    def on_barcode_scanned(self, barcode):
        print("DEBUG mock_barcode_scanner on_barcode_scanned")
        # Simulate sending barcode to the server or handling it as needed
        print(f"Barcode {barcode} would be sent to server here.")

    def close(self):
        # This can be expanded to include any necessary cleanup
        pass


if __name__ == "__main__":
    scanner = MockBarcodeScanner()
    try:
        while True:
            print("Scan a barcode...")
            barcode = scanner.read_barcode()
            if barcode:
                print(f"Scanned mock barcode: {barcode}")
                scanner.on_barcode_scanned(barcode)
    except KeyboardInterrupt:
        print("\nExiting mock barcode scanner.")
    finally:
        scanner.close()
