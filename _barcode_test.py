import threading
import usb.core
import usb.util
from Levenshtein import distance as levenshtein_distance
from rapidfuzz import process, fuzz
import time

class BarcodeScanner:
    def __init__(self, ref):
        self.app = ref
        self.current_barcode = ""
        # work
        self.idVendor = 0x05e0
        self.idProduct = 0x1200
        # home
        #self.idVendor = 0x28e9
        #self.idProduct = 0x03da
        try:
            self.device = self.initializeUSBDevice()
        except ValueError as e:
            print(e)  # TODO do something

        self.barcode_ready = threading.Event()
        self.stop_thread = threading.Event()
        self.thread = threading.Thread(target=self.capture_raw_data, daemon=True)
        self.thread.start()

    # def initializeUSBDevice(self, max_attempts=5, delay_between_attempts=1):
    #     attempt = 0
    #     while attempt < max_attempts:
    #         try:
    #             device = usb.core.find(idVendor=self.idVendor, idProduct=self.idProduct)
    #             if device is None:
    #                 raise ValueError("[Barcode Scanner]: Device Not Found")
    #
    #             if device.is_kernel_driver_active(0):
    #                 device.detach_kernel_driver(0)
    #
    #             device.set_configuration()
    #             configuration = device.get_active_configuration()
    #             interface = configuration[(0, 0)]
    #
    #             endpoint = usb.util.find_descriptor(
    #                 interface,
    #                 custom_match=lambda e: usb.util.endpoint_direction(e.bEndpointAddress)
    #                 == usb.util.ENDPOINT_IN,
    #             )
    #
    #             if endpoint is None:
    #                 raise ValueError("[Barcode Scanner]: Endpoint not found")
    #
    #             return device
    #         except ValueError as e:
    #             print(f"Attempt {attempt + 1} failed: {e}")
    #             time.sleep(delay_between_attempts)
    #             attempt += 1
    #     raise ValueError("[Barcode Scanner]: Failed to initialize after multiple attempts")

    def initializeUSBDevice(self):

        device = usb.core.find(idVendor=self.idVendor, idProduct=self.idProduct)
        if device is None:
            raise ValueError("[Barcode Scanner]: Device Not Found")
        try:
            if device.is_kernel_driver_active(0):
                device.detach_kernel_driver(0)
        except Exception as e:
            print(f"[Barcode Scanner] detach_kernel_driver fail\n{e}")
        try:
            device.set_configuration()
        except Exception as e:
            print(f"[Barcode Scanner] set_configuration fail\n{e}")
        try:
            configuration = device.get_active_configuration()
        except Exception as e:
            print(f"[Barcode Scanner] get_active_configuration fail\n{e}")

        interface = configuration[(0, 0)]
        try:
            self.endpoint = usb.util.find_descriptor(
                interface,
                custom_match=lambda e: usb.util.endpoint_direction(e.bEndpointAddress)
                == usb.util.ENDPOINT_IN,
            )
        except Exception as e:
            print(f"[Barcode Scanner] set endpoint fail\n{e}")
        # if self.endpoint is None:
        #     raise ValueError("[Barcode Scanner]: Endpoint not found")

        return device

    def capture_raw_data(self):

        conversion_table = {
            0: ["", ""],
            4: ["a", "A"],
            5: ["b", "B"],
            6: ["c", "C"],
            7: ["d", "D"],
            8: ["e", "E"],
            9: ["f", "F"],
            10: ["g", "G"],
            11: ["h", "H"],
            12: ["i", "I"],
            13: ["j", "J"],
            14: ["k", "K"],
            15: ["l", "L"],
            16: ["m", "M"],
            17: ["n", "N"],
            18: ["o", "O"],
            19: ["p", "P"],
            20: ["q", "Q"],
            21: ["r", "R"],
            22: ["s", "S"],
            23: ["t", "T"],
            24: ["u", "U"],
            25: ["v", "V"],
            26: ["w", "W"],
            27: ["x", "X"],
            28: ["y", "Y"],
            29: ["z", "Z"],
            30: ["1", "!"],
            31: ["2", "@"],
            32: ["3", "#"],
            33: ["4", "$"],
            34: ["5", "%"],
            35: ["6", "^"],
            36: ["7", "&"],
            37: ["8", "*"],
            38: ["9", "("],
            39: ["0", ")"],
            40: ["\n", "\n"],
            41: ["\x1b", "\x1b"],
            42: ["\b", "\b"],
            43: ["\t", "\t"],
            44: [" ", " "],
            45: ["-", "-"],
            46: ["=", "+"],
            47: ["[", "{"],
            48: ["]", "}"],
            49: ["\\", "|"],
            50: ["#", "~"],
            51: [";", ":"],
            52: ["'", '"'],
            53: ["`", "~"],
            54: [",", "<"],
            55: [".", ">"],
            56: ["/", "?"],
            100: ["\\", "|"],
            103: ["=", "="],
        }

        while not self.stop_thread.is_set():
            try:
                data = self.device.read(
                    self.endpoint.bEndpointAddress,
                    self.endpoint.wMaxPacketSize,
                    timeout=5000,
                )
                if data[2] != 0:
                    character = conversion_table.get(data[2], [""])[0]
                    if character == "\n":

                        self.barcode_ready.set()

                    else:
                        self.current_barcode += character
            except AttributeError as e:
                print(e)
                break
            except usb.core.USBError as e:
                if e.errno == 110:
                    continue

                else:
                    raise

    def is_barcode_ready(self):
        return self.barcode_ready.is_set()

    def check_for_scanned_barcode(self, dt):
        if self.is_barcode_ready():
            barcode = self.current_barcode
            self.handle_global_barcode_scan(barcode)
            self.current_barcode = ""
            self.barcode_ready.clear()

    def handle_global_barcode_scan(self, barcode):

        if self.app.current_context == "inventory":
            self.app.inventory_manager.handle_scanned_barcode(barcode)
        elif self.app.current_context == "label":
            self.app.label_manager.handle_scanned_barcode(barcode)
        elif self.app.current_context == "inventory_item":
            self.app.inventory_manager.handle_scanned_barcode_item(barcode)

        else:
            self.handle_scanned_barcode(barcode)



    def handle_scanned_barcode(self, barcode):
        try:

            if "-" in barcode and any(c.isalpha() for c in barcode):
                self.app.history_manager.display_order_details_from_barcode_scan(barcode)
            else:
                known_barcodes = self.app.barcode_cache.keys()


                if barcode in known_barcodes:
                    barcode_data = self.app.barcode_cache.get(barcode)
                    if barcode_data['is_dupe']:
                        print(f'\n\n\n\n\n\ntest\n{barcode}')


        #             item_details = self.app.db_manager.get_item_details(barcode)
        #             if item_details:
        #                 self.process_item_details(item_details)
        #             return
        #
        #
        #         for known_barcode in known_barcodes:
        #             if known_barcode[1:] == barcode:
        #
        #                 item_details = self.app.db_manager.get_item_details(known_barcode)
        #                 if item_details:
        #                     self.process_item_details(item_details)
        #                 return
        #
        #
        #         self.app.popup_manager.show_add_or_bypass_popup(barcode)
        #
        except Exception as e:
            print(f"Exception in handle_scanned_barcode\n{e}")

    def process_item_details(self, item_details):
        item_name, item_price = item_details[:2]
        self.app.order_manager.add_item(item_name, item_price)
        self.app.utilities.update_display()
        self.app.utilities.update_financial_summary()

    # def find_closest_barcode(self, scanned_barcode, max_distance=1):
    #     closest_matches = []
    #     min_distance = float('inf')
    #
    #     for barcode in self.app.barcode_cache.keys():
    #
    #         dist = levenshtein_distance(scanned_barcode, barcode)
    #
    #         if dist < min_distance and dist <= max_distance:
    #             closest_matches = [barcode]
    #             min_distance = dist
    #         elif dist == min_distance:
    #             closest_matches.append(barcode)
    #
    #     return closest_matches

    # def find_closest_barcode(self, scanned_barcode, score_cutoff=90):
    #     closest_matches = []
    #     scores = process.extract(scanned_barcode, self.app.barcode_cache.keys(), scorer=fuzz.ratio, score_cutoff=score_cutoff)
    #
    #     for match, score, *_ in scores:
    #         if score >= score_cutoff:
    #             closest_matches.append(match)
    #
    #     return closest_matches
    def find_closest_barcode(self, scanned_barcode, ignore_chars=1):
        matches = []
        known_barcodes = self.app.barcode_cache.keys()
        # Slice to ignore first and last 'ignore_chars' characters
        core_scanned = scanned_barcode[ignore_chars:-ignore_chars] if ignore_chars > 0 else scanned_barcode

        for barcode in known_barcodes:
            core_barcode = barcode[ignore_chars:-ignore_chars] if ignore_chars > 0 else barcode
            if core_scanned == core_barcode:
                matches.append(barcode)

        return matches

    def close(self):
        self.stop_thread.set()
        if self.device.is_kernel_driver_active(0):
            self.device.attach_kernel_driver(0)
