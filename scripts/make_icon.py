"""Generate the app icon -> build/icon.png (1024x1024).

electron-builder reads build/icon.png and derives the Windows .ico and macOS
.icns at package time, so this only needs to run when the icon changes; the
committed PNG is what CI consumes. Rendered at 4x and downscaled (LANCZOS) for
smooth, anti-aliased edges.

Motif: a dark rounded-square with an emerald "recovery ring" (a near-full arc
with a gap) and a white ECG/heartbeat pulse through the center.
"""
import math
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter

OUT = Path(__file__).resolve().parent.parent / "build" / "icon.png"
SIZE = 1024
SS = 4                      # supersample factor
S = SIZE * SS
EMERALD = (34, 197, 94)
EMERALD_HI = (74, 222, 128)
WHITE = (250, 250, 250)


def _vertical_gradient(size, top, bottom):
    grad = Image.new("RGB", (1, size))
    for y in range(size):
        t = y / (size - 1)
        grad.putpixel((0, y), tuple(round(top[i] + (bottom[i] - top[i]) * t) for i in range(3)))
    return grad.resize((size, size))


def _radial_glow(size, color, cx, cy, radius, max_alpha):
    """Soft circular glow as an RGBA layer."""
    layer = Image.new("L", (size, size), 0)
    d = ImageDraw.Draw(layer)
    steps = 60
    for i in range(steps, 0, -1):
        r = radius * i / steps
        a = round(max_alpha * (1 - i / steps) ** 2)
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=a)
    out = Image.new("RGBA", (size, size), color + (0,))
    out.putalpha(layer)
    return out


def _round_polyline(draw, pts, width, color):
    """Polyline with round caps + joints (filled circles at every vertex)."""
    draw.line(pts, fill=color, width=width, joint="curve")
    r = width // 2
    for (x, y) in pts:
        draw.ellipse([x - r, y - r, x + r, y + r], fill=color)


def build():
    # --- background squircle with vertical gradient ---
    bg = _vertical_gradient(S, (15, 32, 24), (8, 10, 12)).convert("RGBA")
    mask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, S - 1, S - 1], radius=int(S * 0.225), fill=255)
    icon = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    icon.paste(bg, (0, 0), mask)

    # subtle emerald glow behind the ring
    glow = _radial_glow(S, EMERALD, S // 2, int(S * 0.46), int(S * 0.34), 70)
    icon = Image.alpha_composite(icon, Image.composite(glow, Image.new("RGBA", (S, S), (0, 0, 0, 0)), mask))

    draw = ImageDraw.Draw(icon)

    # --- recovery ring: thick emerald arc with a gap at lower-right ---
    cx = cy = S / 2
    R = S * 0.315
    W = int(S * 0.082)
    box = [cx - R, cy - R, cx + R, cy + R]
    draw.arc(box, start=130, end=410, fill=EMERALD, width=W)          # ~280° sweep, gap at bottom
    # rounded caps on the arc ends
    for ang in (130, 410):
        ex = cx + R * math.cos(math.radians(ang))
        ey = cy + R * math.sin(math.radians(ang))
        draw.ellipse([ex - W / 2, ey - W / 2, ex + W / 2, ey + W / 2], fill=EMERALD_HI)

    # --- ECG / heartbeat pulse through the center ---
    y0 = cy
    span = S * 0.40
    x0 = cx - span / 2
    def P(fx, fy):  # fx along span, fy as fraction of S offset from center
        return (x0 + span * fx, y0 - S * fy)
    pulse = [
        P(0.00, 0.00), P(0.22, 0.00), P(0.34, 0.075), P(0.46, -0.115),
        P(0.58, 0.16), P(0.68, 0.00), P(1.00, 0.00),
    ]
    pw = int(S * 0.038)
    # very soft emerald under-glow (on its own layer, blurred) then crisp white stroke
    glow_layer = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    _round_polyline(ImageDraw.Draw(glow_layer), pulse, int(pw * 2.1), EMERALD + (130,))
    icon.alpha_composite(glow_layer.filter(ImageFilter.GaussianBlur(S * 0.012)))
    draw = ImageDraw.Draw(icon)
    _round_polyline(draw, pulse, pw, WHITE)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    icon.resize((SIZE, SIZE), Image.LANCZOS).save(OUT)
    print(f"wrote {OUT} ({SIZE}x{SIZE})")


if __name__ == "__main__":
    build()
