"""
Lucide / Apple Pro Minimalist Outline Icon System for Watermark Studio.
Strict 1.75px stroke, rounded joins, monochrome Light (#111111) & Dark (#F5F5F2) palette.
"""

from PIL import Image, ImageDraw
import numpy as np
import customtkinter as ctk

def _draw_lucide_icon(name, size=20, color="#111111"):
    """Render anti-aliased vector stroke icon using 4x supersampling."""
    scale = 4
    canvas_size = size * scale
    img = Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    w, h = canvas_size, canvas_size
    pad = int(canvas_size * 0.16)
    lw = max(2, int(scale * 1.75))
    cx, cy = w // 2, h // 2

    if name == "ws" or name == "logo":
        # Minimal WS compact geometric mark
        bw, bh = int(scale * 10), int(scale * 10)
        draw.rounded_rectangle([cx - bw, cy - bh, cx + bw, cy + bh], radius=int(scale * 2.5), fill=color)
        # Cutout inner accent
        inner_pad = int(scale * 2.5)
        draw.line([(cx - bw + inner_pad, cy), (cx, cy + bh - inner_pad), (cx + bw - inner_pad, cy - bh + inner_pad)],
                  fill="#ffffff" if color in ["#111111", "#0b0b0b", "#181818"] else "#111111", width=max(2, int(scale * 1.5)))

    elif name == "video":
        # Lucide Video Camera
        rx1, ry1 = pad, pad + int(scale * 2)
        rx2, ry2 = w - pad - int(scale * 5), h - pad - int(scale * 2)
        draw.rounded_rectangle([rx1, ry1, rx2, ry2], radius=int(scale * 2.5), outline=color, width=lw)
        # Lens
        tx1, ty1 = rx2, cy - int(scale * 3)
        tx2, ty2 = w - pad, cy - int(scale * 6)
        tx3, ty3 = w - pad, cy + int(scale * 6)
        tx4, ty4 = rx2, cy + int(scale * 3)
        draw.polygon([(tx1, ty1), (tx2, ty2), (tx3, ty3), (tx4, ty4)], outline=color, fill=None)
        draw.line([(tx1, ty1), (tx2, ty2), (tx3, ty3), (tx4, ty4), (tx1, ty1)], fill=color, width=lw)

    elif name == "image":
        # Lucide Image
        draw.rounded_rectangle([pad, pad, w - pad, h - pad], radius=int(scale * 2.5), outline=color, width=lw)
        # Sun dot
        sr = int(scale * 2)
        draw.ellipse([pad + int(scale * 3.5), pad + int(scale * 3.5), pad + int(scale * 3.5) + sr * 2, pad + int(scale * 3.5) + sr * 2], fill=color)
        # Mountains
        m_pts = [
            (pad + lw, h - pad - lw),
            (pad + int(w * 0.32), pad + int(h * 0.44)),
            (pad + int(w * 0.52), pad + int(h * 0.60)),
            (pad + int(w * 0.70), pad + int(h * 0.36)),
            (w - pad - lw, h - pad - lw)
        ]
        draw.line(m_pts, fill=color, width=lw, joint="curve")

    elif name == "layers" or name == "batch":
        # Lucide Layers
        off = int(scale * 3.5)
        draw.rounded_rectangle([pad + off, pad, w - pad, h - pad - off], radius=int(scale * 2), outline=color, width=lw)
        draw.rounded_rectangle([pad, pad + off, w - pad - off, h - pad], radius=int(scale * 2), outline=color, width=lw)

    elif name == "activity" or name == "benchmark" or name == "diagnostics":
        # Lucide Activity / Gauge
        draw.ellipse([pad, pad, w - pad, h - pad], outline=color, width=lw)
        pulse = [
            (pad + int(scale * 3.5), cy),
            (cx - int(scale * 3), cy),
            (cx - int(scale * 1), cy - int(scale * 5)),
            (cx + int(scale * 1.5), cy + int(scale * 5)),
            (cx + int(scale * 3.5), cy),
            (w - pad - int(scale * 3.5), cy)
        ]
        draw.line(pulse, fill=color, width=lw, joint="curve")

    elif name == "info":
        # Lucide Info
        draw.ellipse([pad, pad, w - pad, h - pad], outline=color, width=lw)
        draw.ellipse([cx - lw // 2, pad + int(scale * 3.5), cx + lw // 2, pad + int(scale * 3.5) + lw], fill=color)
        draw.line([(cx, pad + int(scale * 6.5)), (cx, h - pad - int(scale * 3.5))], fill=color, width=lw)

    elif name == "check":
        # Lucide Checkmark
        pts = [(pad + int(scale * 2), cy), (cx - int(scale * 1), h - pad - int(scale * 3)), (w - pad - int(scale * 1), pad + int(scale * 3))]
        draw.line(pts, fill=color, width=lw, joint="curve")

    elif name == "scan" or name == "crosshair":
        # Lucide Scan Box
        d = int(scale * 4)
        # Top-Left
        draw.line([(pad, pad + d), (pad, pad), (pad + d, pad)], fill=color, width=lw)
        # Top-Right
        draw.line([(w - pad - d, pad), (w - pad, pad), (w - pad, pad + d)], fill=color, width=lw)
        # Bottom-Left
        draw.line([(pad, h - pad - d), (pad, h - pad), (pad + d, h - pad)], fill=color, width=lw)
        # Bottom-Right
        draw.line([(w - pad - d, h - pad), (w - pad, h - pad), (w - pad, h - pad - d)], fill=color, width=lw)

    elif name == "github":
        # Clean Code Bracket
        draw.ellipse([pad, pad, w - pad, h - pad], outline=color, width=lw)
        draw.line([(cx - int(scale * 2.5), cy - int(scale * 2.5)), (cx - int(scale * 5), cy), (cx - int(scale * 2.5), cy + int(scale * 2.5))], fill=color, width=lw)
        draw.line([(cx + int(scale * 2.5), cy - int(scale * 2.5)), (cx + int(scale * 5), cy), (cx + int(scale * 2.5), cy + int(scale * 2.5))], fill=color, width=lw)

    elif name == "theme" or name == "contrast":
        # Half-filled circle (Theme toggle)
        draw.ellipse([pad, pad, w - pad, h - pad], outline=color, width=lw)
        draw.pieslice([pad, pad, w - pad, h - pad], 90, 270, fill=color)

    else:
        # Default dot
        draw.ellipse([cx - int(scale * 3), cy - int(scale * 3), cx + int(scale * 3), cy + int(scale * 3)], fill=color)

    return img.resize((size, size), Image.Resampling.LANCZOS)


def get_icon(name, size=18):
    """Returns a theme-adaptive CTkImage (#111111 in Light, #F5F5F2 in Dark)."""
    light_img = _draw_lucide_icon(name, size=size, color="#111111")
    dark_img = _draw_lucide_icon(name, size=size, color="#F5F5F2")
    return ctk.CTkImage(light_image=light_img, dark_image=dark_img, size=(size, size))


def get_accent_icon(name, size=18):
    """Returns an accent-colored CTkImage (#F05A28 in Light, #FF6B36 in Dark)."""
    light_img = _draw_lucide_icon(name, size=size, color="#F05A28")
    dark_img = _draw_lucide_icon(name, size=size, color="#FF6B36")
    return ctk.CTkImage(light_image=light_img, dark_image=dark_img, size=(size, size))
