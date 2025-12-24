import threading
import time
import serial
from kivy.clock import Clock
import logging
import re
from idc import id21_check, summarize_for_popup


logger = logging.getLogger("rigs_pos")
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


class BarcodeScanner:
    def __init__(self, ref, device_path="/dev/ttyACM0", baud=9600, idle_ms=30):
        self.app = ref
        self.device_path = device_path
        self.baud = baud
        self.idle_ms = idle_ms

        self.ser = serial.Serial(self.device_path, self.baud, timeout=0)
        self.current_barcode = ""

        self._context_handler = {
            "inventory": lambda bc: self.app.inventory_manager.handle_scanned_barcode(
                bc
            ),
            "inventory_item": lambda bc: self.app.inventory_manager.handle_scanned_barcode_item(
                bc
            ),
            "label": lambda bc: self.app.label_manager.handle_scanned_barcode(bc),
        }

        self.barcode_ready = threading.Event()
        self.stop_thread = threading.Event()
        self.thread = threading.Thread(target=self._capture_serial, daemon=True)
        self.thread.start()

    def is_barcode_ready(self):
        return self.barcode_ready.is_set()

    def check_for_scanned_barcode(self, dt):
        if self.is_barcode_ready():
            barcode = self.current_barcode
            self.handle_global_barcode_scan(barcode)
            self.current_barcode = ""
            self.barcode_ready.clear()

    def handle_global_barcode_scan(self, barcode):
        handler = self._context_handler.get(self.app.current_context)
        if handler:
            handler(barcode)
        else:
            self.handle_scanned_barcode(barcode)

    def handle_scanned_barcode(self, barcode):
        if "-" in barcode and any(c.isalpha() for c in barcode):
            self.app.history_manager.display_order_details_from_barcode_scan(barcode)
            return

        cache = self.app.barcode_cache
        canon = cache.variant.get(barcode)
        if canon:
            self._process_canonical_barcode(canon)
            return

        self.app.popup_manager.show_add_or_bypass_popup(barcode)

    def _process_canonical_barcode(self, canon):
        data = self.app.barcode_cache.main[canon]
        if data["is_dupe"]:
            self.app.popup_manager.handle_duplicate_barcodes(canon)
        else:
            item_details = self.app.db_manager.get_item_details(barcode=canon)
            if item_details:
                self.process_item_details(item_details)

    def handle_known_barcode(self, known_barcode):
        barcode_data = self.app.barcode_cache.get(known_barcode)
        if barcode_data["is_dupe"]:
            self.app.popup_manager.handle_duplicate_barcodes(known_barcode)
        else:
            item_details = self.app.db_manager.get_item_details(barcode=known_barcode)
            if item_details:
                self.process_item_details(item_details)

    def process_item_details(self, item_details):
        item_name = item_details.name
        item_price = item_details.price
        item_id = item_details.item_id
        barcode = item_details.barcode
        is_custom = False
        self.app.order_manager.add_item(item_name, item_price, item_id, barcode, is_custom)
        self.app.utilities.update_display()
        self.app.utilities.update_financial_summary()

    def close(self):
        self.stop_thread.set()
        try:
            if self.ser:
                self.ser.close()
        except Exception:
            # ignore errors for now, probably forever
            pass

    # groups bytes into one "scan" by idle gaps
    def _capture_serial(self):
        buf = bytearray()
        last = time.monotonic()

        while not self.stop_thread.is_set():
            try:
                chunk = self.ser.read(4096)
            except Exception:
                time.sleep(0.05)
                continue

            now = time.monotonic()

            if chunk:
                buf.extend(chunk)
                last = now
                continue

            # no new bytes
            if buf and (now - last) * 1000 >= self.idle_ms:
                payload = bytes(buf)
                self._dispatch_payload(payload)
                buf.clear()
            else:
                time.sleep(0.001)

    def _dispatch_payload(self, raw_bytes: bytes):
        text = raw_bytes.decode("utf-8", "ignore").strip()
        cleaned = text.replace("\r", "").replace("\n", "")

        # upcs
        if self._is_probable_upc(cleaned):
            self._emit_barcode(cleaned)
            return

        # license
        if self._is_license_payload(raw_bytes, text):
            self._handle_license_payload(raw_bytes)
            return

        # other
        if cleaned:
            self._emit_barcode(cleaned)

    def _emit_barcode(self, s: str):
        if self._looks_like_1d_license(s):
            # discard 1d license scans for now
            logger.info(f"Discarding likely 1D license scan: {s}")
            return
        self.current_barcode = s
        self.barcode_ready.set()

    def _is_probable_upc(self, s: str) -> bool:
        return s.isdigit() and len(s) in (8, 12, 13, 14)

    def _is_license_payload(self, raw: bytes, decoded: str) -> bool:
        head = decoded[:200].upper()
        if "ANSI " in head:
            return True

        aamva_markers = (
            "DAQ",
            "DCS",
            "DBB",
            "DBD",
            "DAU",
            "DAG",
            "DAI",
            "DAJ",
            "DCG",
            "DL",
        )
        score = sum(tok in head for tok in aamva_markers)
        if score >= 2:
            return True

        return False

    def _handle_license_payload(self, raw_bytes: bytes):
        Clock.schedule_once(lambda dt: self.is_21(raw_bytes), 0)

    def _looks_like_1d_license(self, s):

        u = s.strip().upper()
        # early returns
        # too short or too long
        if not (10 <= len(u) <= 24):
            return False
        # not all numbers and letters
        if not u.isalnum():
            return False
        # no letters
        if not any(c.isalpha() for c in u):
            return False
        # no numbers
        if not any(c.isdigit() for c in u):
            return False
        # at least 6 consecutive digits
        if re.search(r"\d{6,}", u) is None:
            return False

        STATES = {
            "AL",
            "AK",
            "AZ",
            "AR",
            "CA",
            "CO",
            "CT",
            "DC",
            "DE",
            "FL",
            "GA",
            "HI",
            "IA",
            "ID",
            "IL",
            "IN",
            "KS",
            "KY",
            "LA",
            "MA",
            "MD",
            "ME",
            "MI",
            "MN",
            "MO",
            "MS",
            "MT",
            "NC",
            "ND",
            "NE",
            "NH",
            "NJ",
            "NM",
            "NV",
            "NY",
            "OH",
            "OK",
            "OR",
            "PA",
            "PR",
            "RI",
            "SC",
            "SD",
            "TN",
            "TX",
            "UT",
            "VA",
            "VT",
            "WA",
            "WI",
            "WV",
        }
        if not any(abbr in u for abbr in STATES):
            return False

        if re.search(r"\d{3,}[A-Z]{2}[A-Z0-9]{2,}", u) or re.search(
            r"[A-Z]{2}\d{5,}", u
        ):
            return True
        # default false
        return False

    def is_21(self, raw_bytes, app=None):
        dec = id21_check(raw_bytes)
        summary = summarize_for_popup(dec)

        if dec.hard_fail:
            logger.warning("ID scan fail\n%s", summary)
            self.app.popup_manager.show_error(summary)
            return False

        if dec.needs_review:
            logger.info("ID needs review\n%s", summary)
            self.app.popup_manager.show_warning(summary)
            return True

        logger.info("ID 21+ verified\n%s", summary)
        self.app.popup_manager.show_info(summary)
        return True


if __name__ == "__main__":
    # b= BarcodeScanner("02260142RIK4SL01")
    pass
