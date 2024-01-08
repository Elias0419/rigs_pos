import barcode
from barcode.writer import ImageWriter
from barcode.upc import UniversalProductCodeA as upc_a
from PIL import Image, ImageDraw, ImageFont
import brother_ql
from brother_ql.conversion import convert
from brother_ql.backends.helpers import send

def print_barcode_label(barcode_data, item_price, save_path):
    # Constants
    label_width, label_height = 202, 202
    font_path = "/usr/share/fonts/TTF/Hack-Bold.ttf"
    font_size = 25
    barcode_scale = 0.9  # Barcode occupies 90% of label width

    # Generate barcode image
    barcode_writer = ImageWriter()
    barcode_img = upc_a(barcode_data, writer=barcode_writer).render(writer_options={"module_height": 15.0})

    # Resizing barcode to 90% of label width
    barcode_img_width = int(label_width * barcode_scale)
    barcode_img = barcode_img.resize((barcode_img_width, int(barcode_img.size[1] * (barcode_img_width / barcode_img.size[0]))), Image.Resampling.LANCZOS)

    # Create label image
    label_image = Image.new('L', (label_width, label_height), color=255)
    draw = ImageDraw.Draw(label_image)
    font = ImageFont.truetype(font_path, font_size)

    # Calculate positions
    barcode_x_position = (label_width - barcode_img_width) // 2
    price_text = f"${item_price:.2f}"

    # Calculate text width using textlength and height using font's getmetrics
    price_text_width = draw.textlength(price_text, font=font)
    price_text_height = font.getmetrics()[0]  # Get the ascent (height) of the font
    price_x_position = (label_width - price_text_width) // 2
    price_y_position = label_height - price_text_height - 10

    # Draw barcode and price on the label
    label_image.paste(barcode_img, (barcode_x_position, 10))
    draw.text((price_x_position, price_y_position), price_text, font=font, fill=0)

    barcode_img.save(save_path)
    # # Print label
    # qlr = brother_ql.BrotherQLRaster('QL-710W')
    # qlr.exception_on_warning = True
    # convert(qlr=qlr, images=[label_image], label='23x23')
    # send(instructions=qlr.data, printer_identifier='usb://0x04F9:0x2043', backend_identifier='pyusb')

# Example usage
print_barcode_label("123456789012", 9.99, "barcode_test.png")
