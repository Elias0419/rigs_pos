import datetime
from escpos.printer import Usb
from PIL import Image, ImageDraw, ImageFont

class ReceiptPrinter:
    def __init__(self, printer_vendor_id, printer_product_id, printer_profile):
        self.printer = Usb(printer_vendor_id, printer_product_id, profile=printer_profile)

    def format_order_details(self, order_details):

        formatted_text = ""
        return formatted_text

    def print_receipt(self, order_details):

        formatted_text = self.format_order_details(order_details)
        self.printer.text(formatted_text)

        self.printer.cut()

    def add_logo(self, logo_path):
        pass

    def add_barcode(self, barcode_value, barcode_type='EAN13'):
        pass

    def add_datetime(self):
        current_datetime = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.printer.text(f"\n{current_datetime}\n")

class ReceiptPreview:
    def __init__(self, width=300, height=500):
        self.canvas = Image.new('RGB', (width, height), color='white')
        self.draw = ImageDraw.Draw(self.canvas)
        self.font = ImageFont.truetype('/usr/share/fonts/TTF/JetBrainsMono-ExtraBold.ttf', 15)

    def add_text(self, text, position):
        self.draw.text(position, text, fill='black', font=self.font)

    def add_image(self, image_path, position):
        image = Image.open(image_path)
        image = image.resize((100, 100), Image.Resampling.LANCZOS)
        self.canvas.paste(image, position)

    def show_preview(self):
        self.canvas.show()

preview = ReceiptPreview()
preview.add_image("logo.png", (80, 0))
preview.add_text("Store Name", (100, 100))
preview.add_text("Date", (100, 110))
preview.add_text("Other details", (100, 120))
preview.add_text("An item", (40, 150))
preview.add_text("An item price", (175, 150))
preview.add_text("An item 2", (40, 165))
preview.add_text("An item price 2", (175, 165))

preview.show_preview()


# class ReceiptPreview:
#     def __init__(self, width=300):
#         self.width = width
#         self.padding = 40
#         self.current_y = 10
#         self.canvas = Image.new('RGB', (self.width, 800), color='white')
#         self.draw = ImageDraw.Draw(self.canvas)
#         self.font = ImageFont.truetype('/usr/share/fonts/TTF/Arial.TTF', 15)
#
#     def add_text(self, text, position, font=None, anchor='left'):
#         if font is None:
#             font = self.font
#         bbox = self.draw.textbbox(position, text, font=font)
#         text_width = bbox[2] - bbox[0]
#         text_height = bbox[3] - bbox[1]
#
#         if anchor == 'right':
#             position = (self.width - text_width - self.padding, position[1])
#         elif anchor == 'center':
#             position = ((self.width - text_width) // 2, position[1])
#
#         self.draw.text(position, text, fill='black', font=font)
#         self.current_y = position[1] + text_height
#
#     def add_image(self, image_path, position, size=(100, 100)):
#         try:
#             image = Image.open(image_path)
#             image = image.resize(size, Image.Resampling.LANCZOS)
#             self.canvas.paste(image, position, image)
#         except IOError:
#             print("Error opening image file")
#
#     def show_preview(self):
#         self.canvas = self.canvas.crop((0, 0, self.width, self.current_y + self.padding))
#         self.canvas.show()
#
# preview = ReceiptPreview()
# preview.add_image("logo.png", (100, preview.current_y))
# preview.add_text("Store Name", (preview.padding, preview.current_y), anchor='center')
# preview.add_text("Date", (preview.padding, preview.current_y), anchor='center')
# preview.add_text("Other details", (preview.padding, preview.current_y), anchor='center')
# preview.add_text("An item", (preview.padding, preview.current_y))
# preview.add_text("An item price", (preview.width - preview.padding, preview.current_y), anchor='right')
# preview.add_text("An item 2", (preview.padding, preview.current_y))
# preview.add_text("An item price 2", (preview.width - preview.padding, preview.current_y), anchor='right')
#
# preview.show_preview()

