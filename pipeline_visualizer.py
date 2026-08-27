"""
Technical Inpainting Flow Schematic Visualizer for Watermark Studio.
Strictly implements the Light-First Editorial Reference Visualization (Points 14 & 15).
Compact, zero-scrollbar responsive canvas with clean vector lines, central AI Engine node,
and crisp technical metadata tags.
"""

import tkinter as tk
import numpy as np

class TechnicalPipelineCanvas(tk.Canvas):
    def __init__(self, master, width=440, height=140, **kwargs):
        self.is_dark = False
        super().__init__(master, width=width, height=height, bg="#FFFFFF", highlightthickness=0, **kwargs)
        self.anim_width = width
        self.anim_height = height
        self.running = False
        self.pulse_phase = 0.0
        self._anim_timer = None
        self._resize_timer = None

        self._update_colors()
        self._build_static_elements()
        self.bind("<Configure>", self._on_resize)

    def _update_colors(self):
        if self.is_dark:
            self.bg_color = "#181818"
            self.grid_color = "#222220"
            self.node_bg = "#202020"
            self.node_border = "#40403D"
            self.text_primary = "#F5F5F2"
            self.text_secondary = "#B7B7B1"
            self.text_muted = "#85857F"
            self.line_color = "#30302E"
            self.line_active = "#FF6B36"
            self.accent = "#FF6B36"
            self.badge_bg = "#202020"
        else:
            self.bg_color = "#FFFFFF"
            self.grid_color = "#F5F5F3"
            self.node_bg = "#FAFAF9"
            self.node_border = "#E5E5E2"
            self.text_primary = "#111111"
            self.text_secondary = "#4A4A47"
            self.text_muted = "#777773"
            self.line_color = "#D5D5D1"
            self.line_active = "#F05A28"
            self.accent = "#F05A28"
            self.badge_bg = "#F5F5F3"
        self.configure(bg=self.bg_color)

    def set_theme(self, mode):
        self.is_dark = (mode.lower() == "dark")
        self._update_colors()
        self._build_static_elements()

    def _on_resize(self, event):
        if event.width > 20 and event.height > 20:
            if event.width != self.anim_width or event.height != self.anim_height:
                self.anim_width = event.width
                self.anim_height = event.height
                if self._resize_timer:
                    self.after_cancel(self._resize_timer)
                self._resize_timer = self.after(30, self._build_static_elements)

    def _build_static_elements(self):
        self.delete("all")
        w, h = max(100, self.anim_width), max(100, self.anim_height)
        cx, cy = w // 2, h // 2

        # 1. Background Grid
        grid_step = 28
        for gx in range(0, w, grid_step):
            self.create_line(gx, 0, gx, h, fill=self.grid_color, width=1, tags="static")
        for gy in range(0, h, grid_step):
            self.create_line(0, gy, w, gy, fill=self.grid_color, width=1, tags="static")

        # 2. Input Nodes (Left side)
        in_x = int(w * 0.16)
        dy = min(36, h // 3 - 6)
        in_y_image = cy - dy
        in_y_video = cy
        in_y_mask = cy + dy

        # 3. Central AI Engine Node
        node_w, node_h = 124, 40
        self.node_x1 = cx - node_w // 2
        self.node_y1 = cy - node_h // 2
        self.node_x2 = cx + node_w // 2
        self.node_y2 = cy + node_h // 2

        # 4. Output Nodes (Right side)
        out_x = int(w * 0.84)
        out_y_image = cy - dy
        out_y_video = cy
        out_y_mask = cy + dy

        self.in_x_conn = in_x + 40
        self.out_x_conn = out_x - 48
        self.cy = cy

        # 5. Connection Lines (Input -> Engine)
        mid_in_x = cx - node_w // 2 - 24
        for in_y in [in_y_image, in_y_video, in_y_mask]:
            self.create_line(in_x + 40, in_y, mid_in_x, in_y, fill=self.line_color, width=1.5, tags="static")
            self.create_line(mid_in_x, in_y, mid_in_x, cy, fill=self.line_color, width=1.5, tags="static")
        self.create_line(mid_in_x, cy, self.node_x1, cy, fill=self.line_color, width=1.5, tags="static")

        # 6. Connection Lines (Engine -> Output)
        mid_out_x = cx + node_w // 2 + 24
        self.create_line(self.node_x2, cy, mid_out_x, cy, fill=self.line_color, width=1.5, tags="static")
        for out_y in [out_y_image, out_y_video, out_y_mask]:
            self.create_line(mid_out_x, cy, mid_out_x, out_y, fill=self.line_color, width=1.5, tags="static")
            self.create_line(mid_out_x, out_y, out_x - 48, out_y, fill=self.line_color, width=1.5, tags="static")

        # 7. Render Input Nodes
        inputs = [
            ("Image Source", in_y_image),
            ("Video Stream", in_y_video),
            ("Watermark Mask", in_y_mask)
        ]
        for name, iy in inputs:
            self.create_rectangle(in_x - 46, iy - 10, in_x + 40, iy + 10,
                                  fill=self.node_bg, outline=self.node_border, width=1, tags="static")
            self.create_text(in_x - 3, iy, text=name, font=("Segoe UI", 8, "bold"),
                             fill=self.text_secondary, tags="static")

        # 8. Render Central Engine Box
        self.engine_box_id = self.create_rectangle(
            self.node_x1, self.node_y1, self.node_x2, self.node_y2,
            fill=self.node_bg, outline=self.node_border, width=1.5, tags="engine_box"
        )
        self.create_oval(cx - 44, cy - 3, cx - 38, cy + 3, fill=self.accent, outline="", tags="static")
        self.create_text(cx + 6, cy - 5, text="AI INPAINTING", font=("Segoe UI", 8, "bold"),
                         fill=self.text_primary, tags="static")
        self.create_text(cx + 6, cy + 6, text="ENGINE CORE", font=("Segoe UI", 7, "bold"),
                         fill=self.text_muted, tags="static")

        # 9. Render Output Nodes
        outputs = [
            ("Clean Image", out_y_image),
            ("Clean Video", out_y_video),
            ("Restored Media", out_y_mask)
        ]
        for name, oy in outputs:
            self.create_rectangle(out_x - 48, oy - 10, out_x + 46, oy + 10,
                                  fill=self.node_bg, outline=self.node_border, width=1, tags="static")
            self.create_text(out_x - 1, oy, text=name, font=("Segoe UI", 8, "bold"),
                             fill=self.text_secondary, tags="static")

        # 10. Metadata Headers
        self.create_text(12, 10, text="PIPELINE: WATERMARK DETECTED → PROCESSING → RESTORED",
                         font=("Segoe UI", 7, "bold"), anchor=tk.NW, fill=self.text_muted, tags="static")
        self.create_text(w - 12, 10, text="4K UHD • 60 FPS",
                         font=("Segoe UI", 7, "bold"), anchor=tk.NE, fill=self.text_muted, tags="static")
        self.create_text(12, h - 10, text="● GPU TENSOR CORES ENGAGED",
                         font=("Segoe UI", 7, "bold"), anchor=tk.SW, fill=self.accent, tags="static")
        self.create_text(w - 12, h - 10, text="REINHARD CIE-L*A*B*",
                         font=("Segoe UI", 7, "bold"), anchor=tk.SE, fill=self.text_muted, tags="static")

        # 11. Dynamic Pulse Dot
        self.pulse_dot_id = self.create_oval(-10, -10, -5, -5, fill=self.accent, outline="", tags="pulse")

    def start(self):
        if not self.running:
            self.running = True
            self._render_loop()

    def stop(self):
        self.running = False
        if self._anim_timer:
            self.after_cancel(self._anim_timer)
            self._anim_timer = None

    def _render_loop(self):
        if not self.running:
            return

        self.pulse_phase += 0.05
        t = (self.pulse_phase % 2.0) / 2.0

        # Update pulse dot coordinates
        if t < 0.5:
            px = self.in_x_conn + t * 2 * (self.node_x1 - self.in_x_conn)
        else:
            t_out = (t - 0.5) * 2
            px = self.node_x2 + t_out * (self.out_x_conn - self.node_x2)

        self.coords(self.pulse_dot_id, px - 2.5, self.cy - 2.5, px + 2.5, self.cy + 2.5)

        # Subtle pulsing border on central engine node
        pulse_val = np.sin(self.pulse_phase * 2) * 1.2
        self.coords(self.engine_box_id,
                    self.node_x1 - pulse_val, self.node_y1 - pulse_val,
                    self.node_x2 + pulse_val, self.node_y2 + pulse_val)
        if pulse_val > 0.4:
            self.itemconfig(self.engine_box_id, outline=self.accent)
        else:
            self.itemconfig(self.engine_box_id, outline=self.node_border)

        if self.running:
            self._anim_timer = self.after(35, self._render_loop)
