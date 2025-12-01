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
LABEL_WIDTH_PX = 306                 # printable width at 300 dpi for "29" tape
LOGICAL_HEIGHT_PX = LABEL_WIDTH_PX   # height before rotation; becomes width after rotate


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
        "module_height": 20.0,
        "quiet_zone": 1.0,
        "dpi": 300,
    }
    img = upc.render(writer_options=writer_options)
    if img.mode != "RGB":
        img = img.convert("RGB")
    return img


def wrap_text(draw: ImageDraw.ImageDraw,
              text: str,
              font: ImageFont.FreeTypeFont,
              max_width: int) -> list[str]:
    words = text.split()
    if not words:
        return []

    lines: list[str] = []
    line = words[0]
    for word in words[1:]:
        test = f"{line} {word}"
        bbox = draw.textbbox((0, 0), test, font=font)
        w = bbox[2] - bbox[0]
        if w <= max_width:
            line = test
        else:
            lines.append(line)
            line = word
    lines.append(line)
    return lines


def main() -> None:
    # Dummy content for LARGE label
    barcode_data = "23456789012"  # 11 digits; UPC-A check digit added automatically
    item_name = "Heady Recycler Rig – Large Label Test"
    price_text = "$199.99"
    paragraph = (
        "Hand-blown in Providence, RI by local artist Glass Wizard. "
        "Kiln-annealed overnight for durability and smoother pulls on every hit. "
        "Features a precision recycler design that keeps your rips smooth and flavorful. "
        "Follow @GlassWizardRI on Instagram for new drops, collabs, and behind-the-scenes torch work."
    )

    # Margins and spacing in logical (unrotated) space
    margin_x = 8
    margin_y = 8
    col_gap = 10
    col_inner_margin_x = 4
    line_gap = 4

    # Fonts
    name_font = load_font(24)
    price_font = load_font(28)
    body_font = load_font(16)

    # 1) Barcode: generate, rotate 90° for logical layout, then scale to fit height
    barcode_img = make_barcode_image(barcode_data)
    barcode_img = barcode_img.rotate(90, expand=True)  # will be unrotated after final 270°
    bw, bh = barcode_img.size

    max_barcode_height = LOGICAL_HEIGHT_PX - 2 * margin_y
    if bh > max_barcode_height:
        scale = max_barcode_height / float(bh)
        new_size = (int(bw * scale), int(bh * scale))
        barcode_img = barcode_img.resize(new_size, resample=Image.LANCZOS)
        bw, bh = barcode_img.size

    barcode_col_width = bw + 2 * col_inner_margin_x

    # 2) Measure text and choose text column width so name/price fit and
    #    the paragraph fits vertically within LOGICAL_HEIGHT_PX.
    tmp_img = Image.new("RGB", (1, 1), "white")
    tmp_draw = ImageDraw.Draw(tmp_img)

    def measure(text: str, font: ImageFont.FreeTypeFont) -> tuple[int, int]:
        bbox = tmp_draw.textbbox((0, 0), text, font=font)
        return bbox[2] - bbox[0], bbox[3] - bbox[1]

    name_w, name_h = measure(item_name, name_font)
    price_w, price_h = measure(price_text, price_font)

    available_height = LOGICAL_HEIGHT_PX - 2 * margin_y

    BASE_MIN_TEXT_WIDTH = 300
    MAX_TEXT_WIDTH = 900
    STEP = 10

    min_width = max(BASE_MIN_TEXT_WIDTH, name_w, price_w)
    text_col_width = min_width
    best_lines: list[str] = []
    best_line_heights: list[int] = []

    while text_col_width <= MAX_TEXT_WIDTH:
        lines = wrap_text(tmp_draw, paragraph, body_font, text_col_width)
        line_heights: list[int] = []
        total_body_height = 0
        for line in lines:
            _, lh = measure(line, body_font)
            line_heights.append(lh)
            total_body_height += lh
        if lines:
            total_body_height += line_gap * (len(lines) - 1)

        text_block_height = (
            name_h
            + line_gap
            + price_h
            + (line_gap if lines else 0)
            + total_body_height
        )

        if text_block_height <= available_height:
            best_lines = lines
            best_line_heights = line_heights
            break

        text_col_width += STEP

    # Fallback if nothing fit within height constraint
    if not best_lines:
        text_col_width = max(min_width, MAX_TEXT_WIDTH)
        best_lines = wrap_text(tmp_draw, paragraph, body_font, text_col_width)
        best_line_heights = []
        for line in best_lines:
            _, lh = measure(line, body_font)
            best_line_heights.append(lh)
        total_body_height = sum(best_line_heights)
        if best_lines:
            total_body_height += line_gap * (len(best_line_heights) - 1)
        text_block_height = (
            name_h
            + line_gap
            + price_h
            + (line_gap if best_lines else 0)
            + total_body_height
        )
    else:
        total_body_height = sum(best_line_heights)
        if best_lines:
            total_body_height += line_gap * (len(best_line_heights) - 1)
        text_block_height = (
            name_h
            + line_gap
            + price_h
            + (line_gap if best_lines else 0)
            + total_body_height
        )

    # 3) Compute logical label width (drives cut length)
    logical_width = (
        margin_x
        + barcode_col_width
        + col_gap
        + text_col_width
        + margin_x
    )

    # 4) Build logical image and render barcode (left) + text (right)
    logical_img = Image.new("RGB", (logical_width, LOGICAL_HEIGHT_PX), "white")
    draw = ImageDraw.Draw(logical_img)

    # Barcode column (left), vertically centered
    barcode_x = margin_x + col_inner_margin_x
    barcode_y = margin_y + (available_height - bh) // 2
    logical_img.paste(barcode_img, (barcode_x, barcode_y))

    # Text column (right), vertically centered as a block
    text_x = margin_x + barcode_col_width + col_gap
    text_block_y_start = margin_y + (available_height - text_block_height) // 2
    y = text_block_y_start

    # Item name (centered in text column)
    name_bbox = draw.textbbox((0, 0), item_name, font=name_font)
    name_draw_w = name_bbox[2] - name_bbox[0]
    name_x = text_x + (text_col_width - name_draw_w) // 2
    draw.text((name_x, y), item_name, fill="black", font=name_font)
    y += name_h + line_gap

    # Price (centered in text column)
    price_bbox = draw.textbbox((0, 0), price_text, font=price_font)
    price_draw_w = price_bbox[2] - price_bbox[0]
    price_x = text_x + (text_col_width - price_draw_w) // 2
    draw.text((price_x, y), price_text, fill="black", font=price_font)
    y += price_h

    if best_lines:
        y += line_gap

    # Paragraph (left-aligned in text column)
    for line, lh in zip(best_lines, best_line_heights):
        draw.text((text_x, y), line, fill="black", font=body_font)
        y += lh + line_gap

    # 5) Rotate whole label 270° so:
    #    - barcode ends up unrotated (90° + 270° = 360°)
    #    - text ends up rotated 270°
    rotated_img = logical_img.rotate(270, expand=True)
    # After rotate(270), rotated_img.width == LOGICAL_HEIGHT_PX == LABEL_WIDTH_PX
    # and rotated_img.height == logical_width (the cut length).

    qlr = BrotherQLRaster(PRINTER_MODEL)
    qlr.exception_on_warning = True

    convert(
        qlr=qlr,
        images=[rotated_img],
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
