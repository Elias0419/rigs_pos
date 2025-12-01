#!/usr/bin/env python3
import sys

import barcode
from barcode.writer import ImageWriter
from PIL import Image, ImageDraw, ImageFont

from brother_ql.raster import BrotherQLRaster
from brother_ql.conversion import convert
from brother_ql.backends.helpers import send

PRINTER_MODEL = "QL-710W"
PRINTER_IDENTIFIER = "usb://0x04F9:0x2043"
BACKEND = "pyusb"

# 29 mm continuous tape (DK-2210)
LABEL_NAME = "29"
LABEL_WIDTH_PX = 306  # printable width at 300 dpi for "29" tape


def load_font(size: int) -> ImageFont.FreeTypeFont:
    font_paths = [
        "/usr/share/fonts/TTF/Arialbd.TTF",
        "/usr/share/fonts/TTF/Arial.TTF",
        "DejaVuSans-Bold.ttf",
        "DejaVuSans.ttf",
    ]
    for path in font_paths:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def make_barcode_image(code: str) -> Image.Image:
    """
    Generate a UPC-A barcode image using python-barcode + ImageWriter.

    We pass an 11-digit string; the library computes the check digit.
    """
    upc_cls = barcode.get_barcode_class("upc")
    upc = upc_cls(code, writer=ImageWriter())
    writer_options = {
        "write_text": False,
        "module_width": 0.20,
        "module_height": 15.0,
        "quiet_zone": 1.0,
        "dpi": 300,
    }
    img = upc.render(writer_options=writer_options)
    if img.mode != "RGB":
        img = img.convert("RGB")
    return img


def main() -> None:
    # Fixed dummy content
    barcode_data = "01234567890"  # 11 digits; UPC-A check digit is added automatically
    price_text = "$9.99"
    info_text = "Small DK-2210 label test"

    margin_top = 8
    margin_bottom = 8
    gap_barcode_price = 4
    gap_price_info = 4

    # 1) Build and scale the barcode to fit width
    barcode_img = make_barcode_image(barcode_data)
    bw, bh = barcode_img.size

    max_barcode_width = LABEL_WIDTH_PX - 2 * margin_top
    if bw > max_barcode_width:
        scale = max_barcode_width / float(bw)
        new_size = (int(bw * scale), int(bh * scale))
        barcode_img = barcode_img.resize(new_size, resample=Image.LANCZOS)
        bw, bh = barcode_img.size

    # 2) Measure text heights deterministically
    price_font = load_font(26)
    info_font = load_font(18)

    # Use a tiny temp image purely for measurement
    tmp_img = Image.new("RGB", (1, 1), "white")
    tmp_draw = ImageDraw.Draw(tmp_img)

    price_bbox = tmp_draw.textbbox((0, 0), price_text, font=price_font)
    price_height = price_bbox[3] - price_bbox[1]

    info_bbox = tmp_draw.textbbox((0, 0), info_text, font=info_font)
    info_height = info_bbox[3] - info_bbox[1]

    # 3) Compute exact label height from components
    label_height = (
        margin_top
        + bh
        + gap_barcode_price
        + price_height
        + gap_price_info
        + info_height
        + margin_bottom
    )

    # 4) Create final label image and draw content
    label_img = Image.new("RGB", (LABEL_WIDTH_PX, label_height), "white")
    draw = ImageDraw.Draw(label_img)

    # Barcode centered horizontally, at margin_top
    barcode_x = (LABEL_WIDTH_PX - bw) // 2
    barcode_y = margin_top
    label_img.paste(barcode_img, (barcode_x, barcode_y))

    # Price centered below barcode
    price_y = barcode_y + bh + gap_barcode_price
    price_bbox = draw.textbbox((0, 0), price_text, font=price_font)
    price_width = price_bbox[2] - price_bbox[0]
    price_x = (LABEL_WIDTH_PX - price_width) // 2
    draw.text((price_x, price_y), price_text, fill="black", font=price_font)

    # Info text centered below price
    info_y = price_y + price_height + gap_price_info
    info_bbox = draw.textbbox((0, 0), info_text, font=info_font)
    info_width = info_bbox[2] - info_bbox[0]
    info_x = (LABEL_WIDTH_PX - info_width) // 2
    draw.text((info_x, info_y), info_text, fill="black", font=info_font)

    # 5) Send to printer (single label, cut after)
    qlr = BrotherQLRaster(PRINTER_MODEL)
    qlr.exception_on_warning = True

    convert(
        qlr=qlr,
        images=[label_img],
        label=LABEL_NAME,
        cut=True,
        rotate=0,
    )

    send(
        instructions=qlr.data,
        printer_identifier=PRINTER_IDENTIFIER,
        backend_identifier=BACKEND,
    )


if __name__ == "__main__":
    sys.exit(main())
