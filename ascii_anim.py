"""
High-Density Pure 3D ASCII Art Animation for Watermark Studio Hub.
Renders a smooth 60FPS mathematical 3D rotating ASCII Torus / Cyber Matrix
using standard ASCII characters (.,-~:;=!*#$@) with zero clutter.
"""

import tkinter as tk
import numpy as np

class AsciiNeuralCanvas(tk.Canvas):
    def __init__(self, master, width=540, height=520, **kwargs):
        self.is_dark = True
        bg = "#09090b"
        super().__init__(master, width=width, height=height, bg=bg, highlightthickness=0, **kwargs)
        self.anim_width = width
        self.anim_height = height
        self.A = 0.0
        self.B = 0.0
        self.running = False
        self._chars = " .,-~:;=!*#$@"
        self._update_colors()

        self.bind("<Configure>", self._on_resize)

    def _update_colors(self):
        if self.is_dark:
            self.bg_color = "#09090b"
            self.fg_color = "#38bdf8"       # Cyber Sky Cyan
            self.fg_alt = "#0ea5e9"         # Deep Cyan
            self.fg_highlight = "#e0f2fe"   # White Cyan Glow
        else:
            self.bg_color = "#f8fafc"
            self.fg_color = "#0284c7"       # Rich Blue
            self.fg_alt = "#0369a1"         # Navy Blue
            self.fg_highlight = "#0c4a6e"   # Deepest Navy
        self.configure(bg=self.bg_color)

    def set_theme(self, mode):
        self.is_dark = (mode.lower() == "dark")
        self._update_colors()

    def _on_resize(self, event):
        if event.width > 20 and event.height > 20:
            self.anim_width = event.width
            self.anim_height = event.height

    def start(self):
        if not self.running:
            self.running = True
            self._render_loop()

    def stop(self):
        self.running = False

    def _render_loop(self):
        if not self.running:
            return

        self.delete("all")
        self.A += 0.040
        self.B += 0.024

        w, h = max(100, self.anim_width), max(100, self.anim_height)
        cx, cy = w // 2, h // 2

        # 3D Torus ASCII projection
        cosA, sinA = np.cos(self.A), np.sin(self.A)
        cosB, sinB = np.cos(self.B), np.sin(self.B)

        cols = max(44, min(72, w // 8))
        rows = max(24, min(42, h // 13))

        b = np.full((rows, cols), " ", dtype=object)
        z = np.zeros((rows, cols), dtype=np.float32)

        theta_range = np.linspace(0, 2 * np.pi, 36)
        phi_range = np.linspace(0, 2 * np.pi, 60)

        R1 = 1.0  # Ring radius
        R2 = 2.0  # Distance from center

        for theta in theta_range:
            costheta = np.cos(theta)
            sintheta = np.sin(theta)
            for phi in phi_range:
                cosphi = np.cos(phi)
                sinphi = np.sin(phi)

                circlex = R2 + R1 * costheta
                circley = R1 * sintheta

                x = circlex * (cosB * cosphi + sinA * sinB * sinphi) - circley * cosA * sinB
                y = circlex * (sinB * cosphi - sinA * cosB * sinphi) + circley * cosA * cosB
                z_val = circlex * cosA * sinphi + circley * sinA + 5.0
                ooz = 1.0 / z_val

                xp = int(cols / 2 + 28 * ooz * x * 1.5)
                yp = int(rows / 2 + 15 * ooz * y)

                L = cosphi * costheta * sinB - cosA * costheta * sinphi - sinA * sintheta + cosB * (cosA * sintheta - costheta * sinA * sinphi)
                if L > 0:
                    if 0 <= xp < cols and 0 <= yp < rows:
                        if ooz > z[yp, xp]:
                            z[yp, xp] = ooz
                            lum_idx = min(len(self._chars) - 1, max(0, int(L * 8)))
                            b[yp, xp] = self._chars[lum_idx]

        # Draw ASCII lines on Canvas
        line_h = 13
        start_y = max(10, cy - (rows * line_h) // 2)

        for r_idx in range(rows):
            row_str = "".join(b[r_idx])
            y_pos = start_y + r_idx * line_h

            # Dynamic ASCII color shading
            if r_idx % 4 == 0:
                color = self.fg_highlight
            elif r_idx % 2 == 0:
                color = self.fg_color
            else:
                color = self.fg_alt

            self.create_text(
                cx, y_pos, text=row_str, font=("Consolas", 10, "bold"),
                fill=color
            )

        if self.running:
            self.after(30, self._render_loop)
