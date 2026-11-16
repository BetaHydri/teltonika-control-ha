"""Draw the brand images of the integration (icon and logo) with Pillow.

Run it from the repository root, it writes into
custom_components/teltonika_control/brand:

    python tools/make_brand_images.py

The artwork is original. It is not the logo of Teltonika Networks.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUT = (
    Path(__file__).resolve().parents[1]
    / "custom_components"
    / "teltonika_control"
    / "brand"
)
BOLD_FONTS = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
    "DejaVuSans-Bold.ttf",
)

SIZE = 1024
TOP = (24, 112, 132)
BOTTOM = (10, 58, 72)
WHITE = (255, 255, 255, 255)
TEAL = (17, 94, 112, 255)
ACCENT = (130, 214, 196, 255)
LED = ((120, 220, 140, 255), (255, 190, 80, 255), (210, 230, 235, 255))


def font(size: int) -> ImageFont.FreeTypeFont:
    for path in BOLD_FONTS:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    raise SystemExit("No bold font found, install DejaVu Sans Bold.")


def draw_icon() -> Image.Image:
    """A router with antennas, Wi-Fi arcs and the text RUTx on a teal tile."""
    background = Image.new("RGBA", (SIZE, SIZE))
    lines = ImageDraw.Draw(background)
    for y in range(SIZE):
        t = y / (SIZE - 1)
        color = tuple(round(a + (b - a) * t) for a, b in zip(TOP, BOTTOM))
        lines.line([(0, y), (SIZE, y)], fill=(*color, 255))
    mask = Image.new("L", (SIZE, SIZE), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        (0, 0, SIZE - 1, SIZE - 1), radius=220, fill=255
    )
    image = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    image.paste(background, (0, 0), mask)
    draw = ImageDraw.Draw(image)

    for x in (250, 774):  # antennas
        draw.rounded_rectangle((x - 26, 430, x + 26, 650), radius=26, fill=WHITE)
    draw.rounded_rectangle((130, 600, 894, 860), radius=70, fill=WHITE)  # body

    cx, cy = 512, 520  # Wi-Fi arcs above the body
    for radius in (110, 200, 290):
        draw.arc(
            (cx - radius, cy - radius, cx + radius, cy + radius),
            228,
            312,
            fill=ACCENT,
            width=44,
        )
    draw.ellipse((cx - 40, cy - 40, cx + 40, cy + 40), fill=ACCENT)

    big, small = font(200), font(120)
    draw.text((180, 735), "RUT", font=big, fill=TEAL, anchor="lm")
    width = draw.textlength("RUT", font=big)
    draw.text((180 + width + 8, 757), "x", font=small, fill=(60, 140, 156, 255), anchor="lm")

    for index, color in enumerate(LED):  # status lights
        x = 748 + index * 52
        draw.ellipse((x - 18, 735 - 18, x + 18, 735 + 18), fill=color)
    return image


def draw_logo(text_color: tuple[int, int, int, int], scale: int) -> Image.Image:
    """The icon with the name next to it, 3:1, transparent background."""
    height = 256 * scale
    logo = Image.new("RGBA", (768 * scale, height), (0, 0, 0, 0))
    logo.paste(draw_icon().resize((height, height), Image.LANCZOS), (0, 0))
    draw = ImageDraw.Draw(logo)
    text_font = font(74 * scale)
    x = 290 * scale
    draw.text((x, 92 * scale), "Teltonika", font=text_font, fill=text_color, anchor="ls")
    draw.text((x, 184 * scale), "Control", font=text_font, fill=text_color, anchor="ls")
    return logo


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    icon = draw_icon()
    icon.resize((512, 512), Image.LANCZOS).save(OUT / "icon@2x.png")
    icon.resize((256, 256), Image.LANCZOS).save(OUT / "icon.png")
    for prefix, color in (("", (17, 70, 86, 255)), ("dark_", WHITE)):
        logo = draw_logo(color, 2)
        logo.save(OUT / f"{prefix}logo@2x.png")
        logo.resize((logo.width // 2, logo.height // 2), Image.LANCZOS).save(
            OUT / f"{prefix}logo.png"
        )
    print("written:", ", ".join(sorted(p.name for p in OUT.glob("*.png"))))


if __name__ == "__main__":
    main()
