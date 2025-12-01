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
    # Fixed dummy content for the medium label
    barcode_data = "12345678901"  # 11 digits; UPC-A check digit added automatically
    item_name = "Medium DK-2210 Test"
    price_text = "$59.99"
    extra1 = "Hand-blown glass piece"
    extra2 = "Made in Providence, RI"
    extra3 = "@GlassWizardRI – sample text"

    margin_top = 8
    margin_bottom = 8
    gap_between_lines = 4
    gap_before_barcode = 6

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
    name_font = load_font(20)
    price_font = load_font(26)
    extra_font = load_font(16)

    tmp_img = Image.new("RGB", (1, 1), "white")
    tmp_draw = ImageDraw.Draw(tmp_img)

    def measure(text: str, font: ImageFont.FreeTypeFont) -> tuple[int, int]:
        bbox = tmp_draw.textbbox((0, 0), text, font=font)
        width = bbox[2] - bbox[0]
        height = bbox[3] - bbox[1]
        return width, height

    name_w, name_h = measure(item_name, name_font)
    price_w, price_h = measure(price_text, price_font)
    extra1_w, extra1_h = measure(extra1, extra_font)
    extra2_w, extra2_h = measure(extra2, extra_font)
    extra3_w, extra3_h = measure(extra3, extra_font)

    # 3) Compute exact label height from components
    # Order: top margin, name, gap, price, gap, extra1, gap, extra2, gap, extra3,
    #        gap_before_barcode, barcode, bottom margin
    label_height = (
        margin_top
        + name_h
        + gap_between_lines
        + price_h
        + gap_between_lines
        + extra1_h
        + gap_between_lines
        + extra2_h
        + gap_between_lines
        + extra3_h
        + gap_before_barcode
        + bh
        + margin_bottom
    )

    # 4) Create final label image and draw content
    label_img = Image.new("RGB", (LABEL_WIDTH_PX, label_height), "white")
    draw = ImageDraw.Draw(label_img)

    # Helper for centered text
    def draw_centered(text: str, y: int, font: ImageFont.FreeTypeFont) -> int:
        bbox = draw.textbbox((0, 0), text, font=font)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]
        x = (LABEL_WIDTH_PX - text_w) // 2
        draw.text((x, y), text, fill="black", font=font)
        return y + text_h

    y = margin_top
    y = draw_centered(item_name, y, name_font)
    y += gap_between_lines
    y = draw_centered(price_text, y, price_font)
    y += gap_between_lines
    y = draw_centered(extra1, y, extra_font)
    y += gap_between_lines
    y = draw_centered(extra2, y, extra_font)
    y += gap_between_lines
    y = draw_centered(extra3, y, extra_font)

    y += gap_before_barcode

    # Barcode at the bottom (centered)
    barcode_x = (LABEL_WIDTH_PX - bw) // 2
    barcode_y = label_height - margin_bottom - bh
    label_img.paste(barcode_img, (barcode_x, barcode_y))

    # 5) Send to printer (single medium label, cut after)
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
