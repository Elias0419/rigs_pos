import barcode
from barcode.writer import ImageWriter
from barcode.upc import UniversalProductCodeA as upc_a
from barcode_scanner import BarcodeScanner
barcode_data = 'placeholder'


with open("somefile.jpeg", "wb") as f:
    upc_a(barcode_data, writer=ImageWriter()).write(f)

