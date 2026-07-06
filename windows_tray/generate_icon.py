"""Generate windows_tray/app.ico - a simple monogram, no external art needed.

Run once (also called automatically by build.bat):
    python windows_tray/generate_icon.py

Swap in your own artwork later by just replacing app.ico (any standard
.ico works) - tray_app.py always loads whatever is at that path.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUTPUT_PATH = Path(__file__).resolve().parent / "app.ico"

BACKGROUND = (30, 30, 32, 255)
ACCENT = (214, 108, 58, 255)  # a warm terracotta, distinct in a crowded tray
TEXT = (245, 240, 232, 255)


def _draw_monogram(size: int) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    pad = max(1, size // 16)
    draw.rounded_rectangle(
        (pad, pad, size - pad, size - pad),
        radius=max(2, size // 5),
        fill=BACKGROUND,
        outline=ACCENT,
        width=max(1, size // 16),
    )
    # Two small dots suggest "proxy / relay" without needing a real logo.
    dot_r = max(1, size // 10)
    cy = size // 2
    draw.ellipse(
        (size * 0.28 - dot_r, cy - dot_r, size * 0.28 + dot_r, cy + dot_r),
        fill=ACCENT,
    )
    draw.ellipse(
        (size * 0.72 - dot_r, cy - dot_r, size * 0.72 + dot_r, cy + dot_r),
        fill=ACCENT,
    )
    if size >= 32:
        try:
            font = ImageFont.truetype("arial.ttf", size=int(size * 0.32))
        except OSError:
            font = ImageFont.load_default()
        text = "FC"
        bbox = draw.textbbox((0, 0), text, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        draw.text(
            ((size - tw) / 2 - bbox[0], (size - th) / 2 - bbox[1] + size * 0.02),
            text,
            font=font,
            fill=TEXT,
        )
    return img


def main() -> None:
    sizes = (16, 20, 24, 32, 40, 48, 64, 128, 256)
    largest = _draw_monogram(256)
    largest.save(
        OUTPUT_PATH,
        format="ICO",
        sizes=[(s, s) for s in sizes],
    )
    print(f"Wrote {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
