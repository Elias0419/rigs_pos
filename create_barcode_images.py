import barcode
from barcode.writer import ImageWriter
from barcode.upc import UniversalProductCodeA as upc_a
barcode_data = '123456789012'  






with open("somefile.jpeg", "wb") as f:
    upc_a(barcode_data, writer=ImageWriter()).write(f)

