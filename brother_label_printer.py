from PIL import Image, ImageDraw, ImageFont
import brother_ql
from brother_ql.conversion import convert
from brother_ql.backends.helpers import send


text = "Hello \nWorld"
width, height = 202, 202
font_path = "/usr/share/fonts/TTF/Hack-Bold.ttf"
font_size = 50
image = Image.new("L", (width, height), color=255)
draw = ImageDraw.Draw(image)
font = ImageFont.truetype(font_path, font_size)
draw.text((10, 10), text, font=font, fill=0)


image.save("hello_world_label.png")


model = "QL-710W"
backend = "pyusb"
label_type = "23x23"
usb_interface = "usb://0x04F9:0x2043"


qlr = brother_ql.BrotherQLRaster(model)
qlr.exception_on_warning = True


convert(qlr=qlr, images=[image], label=label_type)


send(
    instructions=qlr.data, printer_identifier=usb_interface, backend_identifier=backend
)
