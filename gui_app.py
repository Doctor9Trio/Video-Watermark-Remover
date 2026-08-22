#!/usr/bin/env python3
"""
╔════════════════════════════════════════════════════════════════════════╗
║                   WATERMARK STUDIO - PROFESSIONAL WORKSPACE            ║
║  Light-First Editorial Design System • Zero-Scrollbar Pro Hub Layout   ║
║  64px Top Navigation • 46/54 Hero Section with Technical Flow Visualizer║
║  Home • Video Studio • Image Studio • Queue • Diagnostics • Credits    ║
║  Restore. Remove. Refine.                                              ║
╚════════════════════════════════════════════════════════════════════════╝
"""

import sys
import os
import shutil
import threading
import queue
import time
import webbrowser
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox

import cv2
import numpy as np
from PIL import Image, ImageTk
import customtkinter as ctk

# Local Modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import watermark_remover as vlr
import icons
from pipeline_visualizer import TechnicalPipelineCanvas

# ──────────────────────────────────────────────
#  GLOBAL THEME INITIALIZATION (LIGHT-FIRST)
# ──────────────────────────────────────────────
ctk.set_appearance_mode("light")
ctk.set_default_color_theme("blue")

# Design System Tokens
ACCENT_PRIMARY = "#F05A28"
ACCENT_HOVER = "#D94C20"
ACCENT_SOFT = "#FFF1EB"
ACCENT_DARK = "#B83D17"

BG_CANVAS = ("#FFFFFF", "#111111")
BG_SURFACE = ("#F5F5F3", "#181818")
BG_SURFACE_STRONG = ("#EEEEEC", "#202020")
BORDER_DEFAULT = ("#E5E5E2", "#30302E")
BORDER_STRONG = ("#D5D5D1", "#40403D")

TEXT_PRIMARY = ("#111111", "#F5F5F2")
TEXT_SECONDARY = ("#4A4A47", "#B7B7B1")
TEXT_MUTED = ("#777773", "#85857F")


# ──────────────────────────────────────────────
#  CANVAS WORKSPACE (VIDEO / IMAGE VIEWPORT)
# ──────────────────────────────────────────────
class MediaCanvasViewport(ctk.CTkFrame):
    def __init__(self, master, app):
        super().__init__(master, corner_radius=10, fg_color=("#151515", "#151515"),
                         border_width=1, border_color=BORDER_DEFAULT)
        self.app = app
        self.scale = 1.0
        self.offset_x = 0
        self.offset_y = 0
        self.photo = None
        self.image_id = None
        self.rect_id = None
        self.drag_start = None

        self.canvas = tk.Canvas(self, bg="#151515", highlightthickness=0, cursor="crosshair")
        self.canvas.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)

        self.canvas.bind("<ButtonPress-1>", self._on_press)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)
        self.canvas.bind("<Configure>", self._on_resize)

        self.render_placeholder()

    def render_placeholder(self):
        self.canvas.delete("all")
        self.image_id = None
        self.rect_id = None
        cw = max(100, self.canvas.winfo_width())
        ch = max(100, self.canvas.winfo_height())
        cx, cy = cw // 2, ch // 2

        mode_text = "Video" if self.app.active_view_name == "video" else "Image"

        self.canvas.create_text(
            cx, cy - 16,
            text=f"Drag & Select Watermark Region",
            font=("Segoe UI", 14, "bold"), fill="#F5F5F2"
        )
        self.canvas.create_text(
            cx, cy + 14,
            text=f"Open a {mode_text} file to begin | 4K UHD 60FPS • MOV • MP4 • MKV • PNG • JPG • WEBP",
            font=("Segoe UI", 10), fill="#85857F"
        )

    def _on_resize(self, event):
        if self.app.current_frame is not None:
            self.show_frame(self.app.current_frame)
        else:
            self.render_placeholder()

    def show_frame(self, frame):
        cw = self.canvas.winfo_width()
        ch = self.canvas.winfo_height()
        if cw < 10 or ch < 10:
            return

        h, w = frame.shape[:2]
        self.scale = min(cw / w, ch / h)
        disp_w = max(1, int(w * self.scale))
        disp_h = max(1, int(h * self.scale))
        self.offset_x = (cw - disp_w) // 2
        self.offset_y = (ch - disp_h) // 2

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        pil_img = Image.fromarray(rgb).resize((disp_w, disp_h), Image.Resampling.BILINEAR)
        self.photo = ImageTk.PhotoImage(pil_img)

        self.canvas.delete("all")
        self.image_id = self.canvas.create_image(
            self.offset_x, self.offset_y, anchor=tk.NW, image=self.photo
        )
        self.rect_id = None

        if self.app.region:
            self.draw_region(self.app.region)

    def draw_region(self, region):
        if self.rect_id:
            self.canvas.delete(self.rect_id)
        x, y, w, h = region
        cx1 = self.offset_x + int(x * self.scale)
        cy1 = self.offset_y + int(y * self.scale)
        cx2 = self.offset_x + int((x + w) * self.scale)
        cy2 = self.offset_y + int((y + h) * self.scale)

        self.rect_id = self.canvas.create_rectangle(
            cx1, cy1, cx2, cy2,
            outline=ACCENT_PRIMARY, width=2, dash=(6, 4)
        )

    def clear_region(self):
        if self.rect_id:
            self.canvas.delete(self.rect_id)
            self.rect_id = None

    def _canvas_to_real(self, cx, cy):
        rx = (cx - self.offset_x) / max(self.scale, 1e-6)
        ry = (cy - self.offset_y) / max(self.scale, 1e-6)
        return rx, ry

    def _on_press(self, event):
        if self.app.current_frame is None or self.app.processing:
            return
        self.drag_start = (event.x, event.y)
        if self.rect_id:
            self.canvas.delete(self.rect_id)

    def _on_drag(self, event):
        if not self.drag_start:
            return
        if self.rect_id:
            self.canvas.delete(self.rect_id)
        sx, sy = self.drag_start
        self.rect_id = self.canvas.create_rectangle(
            sx, sy, event.x, event.y,
            outline=ACCENT_PRIMARY, width=2, dash=(6, 4)
        )

    def _on_release(self, event):
        if not self.drag_start or self.app.current_frame is None:
            return
        sx, sy = self.drag_start
        ex, ey = event.x, event.y
        self.drag_start = None

        rx1, ry1 = self._canvas_to_real(min(sx, ex), min(sy, ey))
        rx2, ry2 = self._canvas_to_real(max(sx, ex), max(sy, ey))

        h, w = self.app.current_frame.shape[:2]
        x = max(0, int(rx1))
        y = max(0, int(ry1))
        rw = min(w - x, int(rx2 - rx1))
        rh = min(h - y, int(ry2 - ry1))

        if rw < 5 or rh < 5:
            return

        self.app.region = (x, y, rw, rh)
        self.draw_region(self.app.region)
        self.app.sidebar.update_region_display()


# ──────────────────────────────────────────────
#  EDITORIAL CONTROL SIDEBAR (WORKSTATION)
# ──────────────────────────────────────────────
class ControlSidebar(ctk.CTkFrame):
    def __init__(self, master, app):
        super().__init__(master, width=330, corner_radius=10,
                         fg_color=BG_CANVAS,
                         border_width=1, border_color=BORDER_DEFAULT)
        self.app = app
        self.pack_propagate(False)

        self._build_header_section()
        self._build_source_section()
        self._build_presets_section()
        self._build_region_section()
        self._build_engine_section()
        self._build_action_section()

    def _build_header_section(self):
        hw = vlr.get_hardware_info()
        card = ctk.CTkFrame(self, corner_radius=6, fg_color=BG_SURFACE,
                            border_width=1, border_color=BORDER_DEFAULT)
        card.pack(fill=tk.X, padx=8, pady=(8, 3))

        row = ctk.CTkFrame(card, fg_color="transparent")
        row.pack(fill=tk.X, padx=8, pady=(6, 2))

        dot_color = "#17824B" if hw["has_cuda"] else "#A96500"
        ctk.CTkLabel(row, text="●", font=ctk.CTkFont(size=9), text_color=dot_color).pack(side=tk.LEFT, padx=(0, 4))
        gpu_name = hw['gpu_name'] if hw["has_cuda"] else "CPU Native"
        ctk.CTkLabel(row, text=gpu_name, font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
                     text_color=TEXT_PRIMARY).pack(side=tk.LEFT)

        self.status_tag = ctk.CTkLabel(row, text="Ready", font=ctk.CTkFont(size=9, weight="bold"),
                                       fg_color=BG_SURFACE_STRONG, text_color=TEXT_SECONDARY,
                                       corner_radius=4, padx=6, pady=1)
        self.status_tag.pack(side=tk.RIGHT)

        self.specs_label = ctk.CTkLabel(
            card, text="No media loaded", font=ctk.CTkFont(size=10),
            text_color=TEXT_MUTED, justify=tk.LEFT, anchor="w"
        )
        self.specs_label.pack(fill=tk.X, padx=8, pady=(0, 6))

    def _build_source_section(self):
        sec = ctk.CTkFrame(self, corner_radius=6, fg_color=BG_SURFACE,
                           border_width=1, border_color=BORDER_DEFAULT)
        sec.pack(fill=tk.X, padx=8, pady=3)

        btn_row = ctk.CTkFrame(sec, fg_color="transparent")
        btn_row.pack(fill=tk.X, padx=6, pady=5)

        self.open_file_btn = ctk.CTkButton(
            btn_row, text="Choose File →", font=ctk.CTkFont(size=11, weight="bold"),
            fg_color="#111111", hover_color=ACCENT_PRIMARY, text_color="#FFFFFF",
            corner_radius=4, command=self._open_file, height=30
        )
        self.open_file_btn.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 3))

        self.open_folder_btn = ctk.CTkButton(
            btn_row, text="Batch Queue", font=ctk.CTkFont(size=11),
            fg_color=BG_CANVAS, text_color=TEXT_PRIMARY,
            hover_color=BG_SURFACE_STRONG, border_width=1, border_color=BORDER_STRONG,
            corner_radius=4, command=self._open_folder, height=30
        )
        self.open_folder_btn.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(3, 0))

        self.file_name_label = ctk.CTkLabel(
            sec, text="No file selected", font=ctk.CTkFont(size=10),
            text_color=TEXT_MUTED, anchor="w"
        )
        self.file_name_label.pack(fill=tk.X, padx=8, pady=(0, 5))

    def _build_presets_section(self):
        sec = ctk.CTkFrame(self, corner_radius=6, fg_color=BG_SURFACE,
                           border_width=1, border_color=BORDER_DEFAULT)
        sec.pack(fill=tk.X, padx=8, pady=3)

        preset_names = [
            "Custom (Draw Box)",
            "Google Gemini Sparkle",
            "NotebookLM Badge",
            "TikTok Watermark",
            "YouTube Subscribe Bug",
            "CapCut Outro Stamp",
            "Bandicam Top Header"
        ]
        self.preset_var = ctk.StringVar(value="Custom (Draw Box)")
        self.preset_menu = ctk.CTkOptionMenu(
            sec, variable=self.preset_var, values=preset_names,
            command=self._on_preset_selected, height=26, corner_radius=4,
            fg_color=BG_CANVAS, text_color=TEXT_PRIMARY, button_color=BG_SURFACE_STRONG,
            font=ctk.CTkFont(size=10)
        )
        self.preset_menu.pack(fill=tk.X, padx=6, pady=5)

    def _on_preset_selected(self, val):
        if self.app.current_frame is None:
            messagebox.showwarning("No Media", "Open a video or image first to apply preset.")
            return

        h, w = self.app.current_frame.shape[:2]
        key_map = {
            "Google Gemini Sparkle": "gemini",
            "NotebookLM Badge": "notebooklm",
            "TikTok Watermark": "tiktok",
            "YouTube Subscribe Bug": "youtube",
            "CapCut Outro Stamp": "capcut",
            "Bandicam Top Header": "bandicam"
        }
        if val in key_map:
            p_key = key_map[val]
            roi = vlr.LOGO_PRESETS[p_key]["get_roi"](w, h)
            self.app.region = roi
            self.update_region_display()
            self.app.canvas_workspace.draw_region(roi)

    def _build_region_section(self):
        sec = ctk.CTkFrame(self, corner_radius=6, fg_color=BG_SURFACE,
                           border_width=1, border_color=BORDER_DEFAULT)
        sec.pack(fill=tk.X, padx=8, pady=3)

        grid = ctk.CTkFrame(sec, fg_color="transparent")
        grid.pack(fill=tk.X, padx=6, pady=(4, 2))

        self.coord_vars = {}
        for idx, (label, var_name) in enumerate([("X", "x"), ("Y", "y"), ("W", "w"), ("H", "h")]):
            row = idx // 2
            col = (idx % 2) * 2
            ctk.CTkLabel(grid, text=f"{label}:", font=ctk.CTkFont(size=10, weight="bold"),
                         text_color=TEXT_PRIMARY, width=16).grid(row=row, column=col, padx=(2, 2), pady=1)
            var = tk.StringVar(value="0")
            self.coord_vars[var_name] = var
            entry = ctk.CTkEntry(grid, textvariable=var, width=88, height=24, corner_radius=4,
                                 border_color=BORDER_STRONG, fg_color=BG_CANVAS, text_color=TEXT_PRIMARY,
                                 font=ctk.CTkFont(size=10))
            entry.grid(row=row, column=col+1, padx=(1, 4), pady=1)

        btn_row = ctk.CTkFrame(sec, fg_color="transparent")
        btn_row.pack(fill=tk.X, padx=6, pady=(3, 3))

        ctk.CTkButton(btn_row, text="Auto Detect", command=self._auto_detect,
                      height=24, corner_radius=4, font=ctk.CTkFont(size=10),
                      fg_color=BG_CANVAS, text_color=TEXT_PRIMARY, border_width=1, border_color=BORDER_STRONG,
                      hover_color=BG_SURFACE_STRONG).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 2))
        ctk.CTkButton(btn_row, text="Apply", command=self._apply_manual,
                      height=24, corner_radius=4, font=ctk.CTkFont(size=10),
                      fg_color=BG_CANVAS, text_color=TEXT_PRIMARY, border_width=1, border_color=BORDER_STRONG,
                      hover_color=BG_SURFACE_STRONG).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(2, 2))
        ctk.CTkButton(btn_row, text="Clear", command=self._clear_region,
                      height=24, corner_radius=4, font=ctk.CTkFont(size=10),
                      fg_color="#C93636", hover_color="#A82828", text_color="#FFFFFF",
                      width=44).pack(side=tk.LEFT, padx=(2, 0))

        self.tracking_var = ctk.BooleanVar(value=False)
        self.tracking_switch = ctk.CTkSwitch(
            sec, text="Track Moving Watermark", variable=self.tracking_var,
            progress_color=ACCENT_PRIMARY, font=ctk.CTkFont(size=10, weight="bold")
        )
        self.tracking_switch.pack(fill=tk.X, padx=8, pady=(2, 5))

    def _build_engine_section(self):
        sec = ctk.CTkFrame(self, corner_radius=6, fg_color=BG_SURFACE,
                           border_width=1, border_color=BORDER_DEFAULT)
        sec.pack(fill=tk.X, padx=8, pady=3)

        self.engine_var = ctk.StringVar(value="Seamless Pro (Best Quality)")
        engine_options = [
            "Seamless Pro (Best Quality)",
            "Ultra-Fast Native (Instant 1000 FPS)",
            "Smart Texture Clone (Nearby Patch)",
            "Smart Frosted Blur (Instant)",
            "OpenCV Classical (Fast Fallback)"
        ]
        self.engine_dropdown = ctk.CTkOptionMenu(
            sec, variable=self.engine_var, values=engine_options, height=26, corner_radius=4,
            fg_color=BG_CANVAS, text_color=TEXT_PRIMARY, button_color=BG_SURFACE_STRONG,
            font=ctk.CTkFont(size=10)
        )
        self.engine_dropdown.pack(fill=tk.X, padx=6, pady=(5, 2))

        tog_frame = ctk.CTkFrame(sec, fg_color="transparent")
        tog_frame.pack(fill=tk.X, padx=6, pady=1)

        self.color_match_var = ctk.BooleanVar(value=True)
        self.grain_var = ctk.BooleanVar(value=True)

        ctk.CTkSwitch(tog_frame, text="LAB Color", variable=self.color_match_var,
                      progress_color=ACCENT_PRIMARY, font=ctk.CTkFont(size=10)).pack(side=tk.LEFT, expand=True)
        ctk.CTkSwitch(tog_frame, text="Film Grain", variable=self.grain_var,
                      progress_color=ACCENT_PRIMARY, font=ctk.CTkFont(size=10)).pack(side=tk.RIGHT, expand=True)

        crf_row = ctk.CTkFrame(sec, fg_color="transparent")
        crf_row.pack(fill=tk.X, padx=6, pady=(3, 1))
        ctk.CTkLabel(crf_row, text="Quality (CRF):", font=ctk.CTkFont(size=10),
                     text_color=TEXT_PRIMARY).pack(side=tk.LEFT)
        self.crf_val_label = ctk.CTkLabel(crf_row, text="16 (Pristine 4K)",
                                          font=ctk.CTkFont(size=10, weight="bold"),
                                          text_color=ACCENT_PRIMARY)
        self.crf_val_label.pack(side=tk.RIGHT)

        self.crf_slider = ctk.CTkSlider(
            sec, from_=0, to=28, number_of_steps=28, height=12,
            progress_color=ACCENT_PRIMARY, button_color="#111111", command=self._on_crf_change
        )
        self.crf_slider.set(16)
        self.crf_slider.pack(fill=tk.X, padx=6, pady=(1, 5))

    def _build_action_section(self):
        sec = ctk.CTkFrame(self, corner_radius=6, fg_color=BG_SURFACE,
                           border_width=1, border_color=BORDER_DEFAULT)
        sec.pack(fill=tk.X, padx=8, pady=(3, 6))

        self.process_btn = ctk.CTkButton(
            sec, text="Process Media Now →", font=ctk.CTkFont(size=12, weight="bold"),
            fg_color="#111111", hover_color=ACCENT_PRIMARY, text_color="#FFFFFF",
            corner_radius=4, command=self._process, height=36
        )
        self.process_btn.pack(fill=tk.X, padx=6, pady=(5, 3))

        sub_row = ctk.CTkFrame(sec, fg_color="transparent")
        sub_row.pack(fill=tk.X, padx=6, pady=2)

        self.preview_btn = ctk.CTkButton(
            sub_row, text="Preview Inpaint", font=ctk.CTkFont(size=10),
            fg_color=BG_CANVAS, text_color=TEXT_PRIMARY, border_width=1, border_color=BORDER_STRONG,
            hover_color=BG_SURFACE_STRONG, corner_radius=4,
            command=self._preview, height=26
        )
        self.preview_btn.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 2))

        self.cancel_btn = ctk.CTkButton(
            sub_row, text="Cancel", font=ctk.CTkFont(size=10, weight="bold"),
            fg_color="#C93636", hover_color="#A82828", text_color="#FFFFFF",
            corner_radius=4, command=self._cancel,
            height=26, state="disabled", width=58
        )
        self.cancel_btn.pack(side=tk.LEFT, padx=(2, 0))

    def _on_crf_change(self, val):
        crf = int(val)
        desc = "0 (Lossless)" if crf == 0 else f"{crf} (Pristine 4K)" if crf <= 16 else f"{crf} (High Quality)"
        self.crf_val_label.configure(text=desc)

    def update_region_display(self):
        if self.app.region:
            x, y, w, h = self.app.region
            self.coord_vars["x"].set(str(x))
            self.coord_vars["y"].set(str(y))
            self.coord_vars["w"].set(str(w))
            self.coord_vars["h"].set(str(h))

    def _open_file(self):
        if self.app.active_view_name == "video":
            types = [("Video Files", "*.mp4 *.mov *.avi *.mkv *.webm *.m4v *.ts"), ("All Files", "*.*")]
        else:
            types = [("Image Files", "*.png *.jpg *.jpeg *.webp *.bmp *.tiff"), ("All Files", "*.*")]

        path = filedialog.askopenfilename(title="Select Media File", filetypes=types)
        if path:
            self.app.load_media(Path(path))

    def _open_folder(self):
        self.app.switch_view("batch")

    def _auto_detect(self):
        if self.app.current_frame is None:
            messagebox.showwarning("No Media", "Open a file first.")
            return
        region = vlr.auto_detect_logo(self.app.current_frame)
        if region is None:
            messagebox.showinfo("Not Found", "Could not auto-detect watermark.\nPlease drag a box around it manually.")
            return
        self.app.region = region
        self.update_region_display()
        self.app.canvas_workspace.draw_region(region)

    def _apply_manual(self):
        try:
            x = int(self.coord_vars["x"].get())
            y = int(self.coord_vars["y"].get())
            w = int(self.coord_vars["w"].get())
            h = int(self.coord_vars["h"].get())
            if w < 5 or h < 5:
                raise ValueError
        except Exception:
            messagebox.showwarning("Invalid Region", "Enter valid integer X, Y, W, H values (min 5px).")
            return
        self.app.region = (x, y, w, h)
        self.app.canvas_workspace.draw_region(self.app.region)

    def _clear_region(self):
        self.app.region = None
        for v in self.coord_vars.values():
            v.set("0")
        self.app.canvas_workspace.clear_region()

    def _preview(self):
        if self.app.current_frame is None:
            messagebox.showwarning("No Media", "Open a file first.")
            return
        if self.app.region is None:
            messagebox.showwarning("No Region", "Select or detect a watermark region first.")
            return

        self.app._apply_settings()
        frame = self.app.current_frame.copy()
        region = self.app.region
        x, y, w, h = region
        fh, fw = frame.shape[:2]
        pad = int(40 * (max(fh, fw) / 1080.0))

        y1 = max(0, y - pad)
        y2 = min(fh, y + h + pad)
        x1 = max(0, x - pad)
        x2 = min(fw, x + w + pad)

        roi_crop = frame[y1:y2, x1:x2].copy()
        mask_crop = np.zeros((y2 - y1, x2 - x1), dtype=np.uint8)
        mask_crop[y - y1:y - y1 + h, x - x1:x - x1 + w] = 255

        inpainted_crop = vlr.inpaint_roi_batch([roi_crop], mask_crop)[0]
        EditorialPreviewModal(self.app, roi_crop, inpainted_crop)

    def _process(self):
        if self.app.current_frame is None:
            messagebox.showwarning("No Media", "Open a file first.")
            return
        if self.app.region is None:
            messagebox.showwarning("No Region", "Select or detect a watermark region first.")
            return
        if self.app.processing:
            return
        self.app.start_processing()

    def _cancel(self):
        self.app.cancel_processing()

    def set_processing_state(self, active):
        state = "disabled" if active else "normal"
        self.preview_btn.configure(state=state)
        self.process_btn.configure(state=state)
        self.cancel_btn.configure(state="normal" if active else "disabled")
        self.status_tag.configure(
            text="Processing" if active else "Ready",
            fg_color=ACCENT_SOFT if active else BG_SURFACE_STRONG,
            text_color=ACCENT_DARK if active else TEXT_SECONDARY
        )


# ──────────────────────────────────────────────
#  EDITORIAL PREVIEW MODAL
# ──────────────────────────────────────────────
class EditorialPreviewModal(ctk.CTkToplevel):
    def __init__(self, parent, before_bgr, after_bgr):
        super().__init__(parent)
        self.title("Watermark Removal Preview - Before vs After")
        self.geometry("880x500")
        self.minsize(700, 400)

        h, w = before_bgr.shape[:2]
        max_w = 400
        scale = min(1.0, max_w / max(w, 1))
        dw, dh = max(1, int(w * scale)), max(1, int(h * scale))

        before_rgb = cv2.cvtColor(before_bgr, cv2.COLOR_BGR2RGB)
        after_rgb = cv2.cvtColor(after_bgr, cv2.COLOR_BGR2RGB)

        before_pil = Image.fromarray(before_rgb).resize((dw, dh), Image.Resampling.LANCZOS)
        after_pil = Image.fromarray(after_rgb).resize((dw, dh), Image.Resampling.LANCZOS)

        self.before_photo = ImageTk.PhotoImage(before_pil)
        self.after_photo = ImageTk.PhotoImage(after_pil)

        ctk.CTkLabel(self, text="Watermark Removal Comparison",
                     font=ctk.CTkFont(family="Segoe UI", size=16, weight="bold"),
                     text_color=TEXT_PRIMARY).pack(pady=(16, 12))

        cards_frame = ctk.CTkFrame(self, fg_color="transparent")
        cards_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=8)

        card_l = ctk.CTkFrame(cards_frame, corner_radius=8, fg_color=BG_SURFACE,
                             border_width=1, border_color=BORDER_DEFAULT)
        card_l.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=8)
        ctk.CTkLabel(card_l, text="ORIGINAL SOURCE", font=ctk.CTkFont(size=11, weight="bold"),
                     text_color="#C93636").pack(pady=6)
        tk.Label(card_l, image=self.before_photo, bg="#151515", bd=0).pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))

        card_r = ctk.CTkFrame(cards_frame, corner_radius=8, fg_color=BG_SURFACE,
                             border_width=1, border_color=BORDER_DEFAULT)
        card_r.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=8)
        ctk.CTkLabel(card_r, text="RESTORED FRAME", font=ctk.CTkFont(size=11, weight="bold"),
                     text_color="#17824B").pack(pady=6)
        tk.Label(card_r, image=self.after_photo, bg="#151515", bd=0).pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))

        ctk.CTkButton(self, text="Close Preview", command=self.destroy,
                      fg_color="#111111", hover_color=ACCENT_PRIMARY, text_color="#FFFFFF",
                      corner_radius=4, width=130, height=34).pack(pady=(4, 14))

        self.transient(parent)
        self.grab_set()


# ──────────────────────────────────────────────
#  EDITORIAL SUCCESS MODAL
# ──────────────────────────────────────────────
class EditorialSuccessModal(ctk.CTkToplevel):
    def __init__(self, parent, output_path, elapsed_time, throughput_fps=None):
        super().__init__(parent)
        self.output_path = Path(output_path)
        self.title("Processing Complete")
        self.geometry("540x380")
        self.resizable(False, False)

        hdr = ctk.CTkFrame(self, fg_color="transparent")
        hdr.pack(fill=tk.X, padx=20, pady=(20, 6))

        ctk.CTkLabel(hdr, text="Processing Complete",
                     font=ctk.CTkFont(family="Segoe UI", size=18, weight="bold"),
                     text_color=TEXT_PRIMARY).pack(anchor="w")
        ctk.CTkLabel(hdr, text="Media restored and exported successfully.",
                     font=ctk.CTkFont(size=11), text_color=TEXT_MUTED).pack(anchor="w")

        card = ctk.CTkFrame(self, corner_radius=8, fg_color=BG_SURFACE,
                            border_width=1, border_color=BORDER_DEFAULT)
        card.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        file_size = self.output_path.stat().st_size / (1024 * 1024)
        info_lines = [
            f"File Name   : {self.output_path.name}",
            f"Format      : {self.output_path.suffix.upper()} (Exact Audio & Video Preservation)",
            f"File Size   : {file_size:.2f} MB",
            f"Render Time : {vlr.format_time(elapsed_time)}",
        ]
        if throughput_fps:
            info_lines.append(f"Throughput  : {throughput_fps:.1f} FPS")

        info_text = "\n".join(info_lines)
        ctk.CTkLabel(card, text=info_text, font=ctk.CTkFont(size=11, family="Consolas"),
                     text_color=TEXT_PRIMARY, justify=tk.LEFT, anchor="w").pack(fill=tk.BOTH, expand=True, padx=16, pady=12)

        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill=tk.X, padx=20, pady=(4, 20))

        ctk.CTkButton(btn_frame, text="Open File →", font=ctk.CTkFont(size=11, weight="bold"),
                      fg_color="#111111", hover_color=ACCENT_PRIMARY, text_color="#FFFFFF",
                      corner_radius=4, command=self._open_file, width=120, height=36).pack(side=tk.LEFT, padx=(0, 6))

        ctk.CTkButton(btn_frame, text="Show in Folder", font=ctk.CTkFont(size=11),
                      fg_color=BG_CANVAS, text_color=TEXT_PRIMARY, border_width=1, border_color=BORDER_STRONG,
                      hover_color=BG_SURFACE_STRONG, corner_radius=4,
                      command=self._open_folder, width=130, height=36).pack(side=tk.LEFT, padx=4)

        ctk.CTkButton(btn_frame, text="Close", font=ctk.CTkFont(size=11),
                      fg_color=BG_CANVAS, text_color=TEXT_MUTED, border_width=1, border_color=BORDER_DEFAULT,
                      hover_color=BG_SURFACE, corner_radius=4,
                      command=self.destroy, width=70, height=36).pack(side=tk.RIGHT, padx=(6, 0))

        self.transient(parent)
        self.grab_set()

    def _open_file(self):
        try:
            if sys.platform == "win32":
                os.startfile(str(self.output_path))
            elif sys.platform == "darwin":
                subprocess.run(["open", str(self.output_path)])
            else:
                subprocess.run(["xdg-open", str(self.output_path)])
        except Exception as e:
            messagebox.showerror("Error", f"Cannot open file: {e}")

    def _open_folder(self):
        try:
            folder = self.output_path.parent
            if sys.platform == "win32":
                os.startfile(str(folder))
            elif sys.platform == "darwin":
                subprocess.run(["open", str(folder)])
            else:
                subprocess.run(["xdg-open", str(folder)])
        except Exception as e:
            messagebox.showerror("Error", f"Cannot open folder: {e}")


# ──────────────────────────────────────────────
#  MAIN HUB (ZERO-SCROLLBAR HERO + WORKFLOWS)
# ──────────────────────────────────────────────
class MainHubView(ctk.CTkFrame):
    def __init__(self, master, app):
        super().__init__(master, corner_radius=0, fg_color=BG_CANVAS)
        self.app = app

        self._build_hero_section()
        self._build_workflow_cards_section()

    def _build_hero_section(self):
        hero = ctk.CTkFrame(self, fg_color="transparent")
        hero.pack(fill=tk.X, padx=28, pady=(16, 10))

        # 46% Content Column (Left)
        content_col = ctk.CTkFrame(hero, fg_color="transparent")
        content_col.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 16))

        ctk.CTkLabel(
            content_col, text="MEDIA INPAINTING WORKSPACE",
            font=ctk.CTkFont(family="Segoe UI", size=9, weight="bold"),
            text_color=TEXT_MUTED
        ).pack(anchor="w", pady=(0, 2))

        ctk.CTkLabel(
            content_col, text="Restore. Remove. Refine.",
            font=ctk.CTkFont(family="Segoe UI", size=26, weight="bold"),
            text_color=TEXT_PRIMARY
        ).pack(anchor="w", pady=(0, 2))

        ctk.CTkLabel(
            content_col, text="Professional media inpainting for image and video workflows.",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color=TEXT_SECONDARY
        ).pack(anchor="w", pady=(0, 10))

        # Capability Chips Row
        chips_row = ctk.CTkFrame(content_col, fg_color="transparent")
        chips_row.pack(anchor="w", pady=(0, 12))

        for chip_text in ["● GPU READY", "4K / 60 FPS", "LOSSLESS PIPELINE"]:
            chip = ctk.CTkFrame(chips_row, corner_radius=4, fg_color=BG_SURFACE,
                                border_width=1, border_color=BORDER_DEFAULT)
            chip.pack(side=tk.LEFT, padx=(0, 5))
            ctk.CTkLabel(chip, text=chip_text, font=ctk.CTkFont(size=9, weight="bold"),
                         text_color=TEXT_SECONDARY).pack(padx=6, pady=2)

        # Actions Row
        action_row = ctk.CTkFrame(content_col, fg_color="transparent")
        action_row.pack(anchor="w")

        ctk.CTkButton(
            action_row, text="Start Processing →", font=ctk.CTkFont(size=11, weight="bold"),
            fg_color="#111111", hover_color=ACCENT_PRIMARY, text_color="#FFFFFF",
            corner_radius=4, width=140, height=34,
            command=lambda: self.app.switch_view("video")
        ).pack(side=tk.LEFT, padx=(0, 8))

        ctk.CTkButton(
            action_row, text="Documentation", font=ctk.CTkFont(size=11),
            fg_color=BG_CANVAS, text_color=TEXT_PRIMARY,
            border_width=1, border_color=BORDER_STRONG, hover_color=BG_SURFACE,
            corner_radius=4, width=120, height=34,
            command=lambda: webbrowser.open("https://github.com/Doctor9Trio/Video-Watermark-Remover#readme")
        ).pack(side=tk.LEFT)

        # 54% Technical Schematic Visualizer (Right)
        vis_col = ctk.CTkFrame(hero, width=440, height=140, corner_radius=8,
                               fg_color=BG_SURFACE, border_width=1, border_color=BORDER_DEFAULT)
        vis_col.pack(side=tk.RIGHT, fill=tk.BOTH, expand=False)
        vis_col.pack_propagate(False)

        self.pipeline_canvas = TechnicalPipelineCanvas(vis_col, width=436, height=136)
        self.pipeline_canvas.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)
        self.pipeline_canvas.start()

    def _build_workflow_cards_section(self):
        sec = ctk.CTkFrame(self, fg_color="transparent")
        sec.pack(fill=tk.BOTH, expand=True, padx=28, pady=(4, 16))

        ctk.CTkLabel(
            sec, text="PRIMARY WORKFLOWS",
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            text_color=TEXT_MUTED
        ).pack(anchor="w", pady=(0, 6))

        # 2-Column Grid for Top 4 Cards
        grid = ctk.CTkFrame(sec, fg_color="transparent")
        grid.pack(fill=tk.X, pady=(0, 8))
        grid.columnconfigure(0, weight=1)
        grid.columnconfigure(1, weight=1)

        # Card 01: Video
        self._build_product_card(
            grid, row=0, col=0,
            index_tag="VIDEO / 01",
            title="Video Inpainting",
            desc="Remove moving watermarks with frame-aware temporal tracking.",
            chips=["4K", "60 FPS", "TRACKING"],
            button_label="Open Studio →",
            command=lambda: self.app.switch_view("video")
        )

        # Card 02: Image
        self._build_product_card(
            grid, row=0, col=1,
            index_tag="IMAGE / 02",
            title="Image Inpainting",
            desc="Restore photos by removing logos, objects, text and distractions.",
            chips=["HIGH-RES", "LOSSLESS", "AI FILL"],
            button_label="Open Studio →",
            command=lambda: self.app.switch_view("image")
        )

        # Card 03: Batch
        self._build_product_card(
            grid, row=1, col=0,
            index_tag="BATCH / 03",
            title="Batch Processing",
            desc="Process multiple files in parallel with smart scheduling.",
            chips=["PARALLEL", "QUEUE", "AUTO OPTIMIZE"],
            button_label="Open Queue →",
            command=lambda: self.app.switch_view("batch")
        )

        # Card 04: Performance
        self._build_product_card(
            grid, row=1, col=1,
            index_tag="PERFORMANCE / 04",
            title="Performance Diagnostics",
            desc="Monitor GPU, memory and pipeline performance in real time.",
            chips=["GPU", "REAL-TIME", "METRICS"],
            button_label="Run Diagnostics →",
            command=lambda: self.app.switch_view("diagnostics")
        )

        # Horizontal 5th Card: About Strip
        about_card = ctk.CTkFrame(sec, corner_radius=8, fg_color=BG_CANVAS,
                                  border_width=1, border_color=BORDER_DEFAULT, height=44)
        about_card.pack(fill=tk.X, pady=(2, 0))
        about_card.pack_propagate(False)

        inner = ctk.CTkFrame(about_card, fg_color="transparent")
        inner.pack(fill=tk.BOTH, expand=True, padx=14, pady=4)

        ctk.CTkLabel(inner, text="ABOUT / 05", font=ctk.CTkFont(size=9, weight="bold"),
                     text_color=TEXT_MUTED).pack(side=tk.LEFT, padx=(0, 8))
        ctk.CTkLabel(inner, text="About & Developer Credits", font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
                     text_color=TEXT_PRIMARY).pack(side=tk.LEFT, padx=(0, 8))
        ctk.CTkLabel(inner, text="— MIT Open-Source License & Architecture details",
                     font=ctk.CTkFont(size=10), text_color=TEXT_SECONDARY).pack(side=tk.LEFT)

        ctk.CTkButton(
            inner, text="View Details →", font=ctk.CTkFont(size=10, weight="bold"),
            fg_color=BG_SURFACE, text_color=TEXT_PRIMARY, hover_color=BG_SURFACE_STRONG,
            border_width=1, border_color=BORDER_STRONG, corner_radius=4,
            command=lambda: self.app.switch_view("credits"), width=100, height=28
        ).pack(side=tk.RIGHT)

    def _build_product_card(self, parent, row, col, index_tag, title, desc, chips, button_label, command):
        card = ctk.CTkFrame(parent, corner_radius=8, fg_color=BG_CANVAS,
                            border_width=1, border_color=BORDER_DEFAULT, height=116)
        card.grid(row=row, column=col, padx=6, pady=4, sticky="nsew")
        card.pack_propagate(False)

        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill=tk.BOTH, expand=True, padx=14, pady=10)

        # Top row: Index Tag + Title
        top_row = ctk.CTkFrame(inner, fg_color="transparent")
        top_row.pack(fill=tk.X)

        ctk.CTkLabel(top_row, text=index_tag, font=ctk.CTkFont(size=9, weight="bold"),
                     text_color=TEXT_MUTED).pack(side=tk.LEFT, padx=(0, 6))
        ctk.CTkLabel(top_row, text=title, font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
                     text_color=TEXT_PRIMARY).pack(side=tk.LEFT)

        # Description
        ctk.CTkLabel(inner, text=desc, font=ctk.CTkFont(size=10),
                     text_color=TEXT_SECONDARY, justify=tk.LEFT, anchor="w", wraplength=360).pack(fill=tk.X, pady=(2, 6))

        # Bottom Row: Chips + Action Button
        bottom_row = ctk.CTkFrame(inner, fg_color="transparent")
        bottom_row.pack(fill=tk.X, side=tk.BOTTOM)

        chips_box = ctk.CTkFrame(bottom_row, fg_color="transparent")
        chips_box.pack(side=tk.LEFT)

        for c_text in chips:
            chip = ctk.CTkFrame(chips_box, corner_radius=3, fg_color=BG_SURFACE,
                                border_width=1, border_color=BORDER_DEFAULT)
            chip.pack(side=tk.LEFT, padx=(0, 4))
            ctk.CTkLabel(chip, text=c_text, font=ctk.CTkFont(size=8, weight="bold"),
                         text_color=TEXT_SECONDARY).pack(padx=5, pady=1)

        ctk.CTkButton(
            bottom_row, text=button_label, font=ctk.CTkFont(size=10, weight="bold"),
            fg_color="#111111", hover_color=ACCENT_PRIMARY, text_color="#FFFFFF",
            corner_radius=4, width=105, height=28, command=command
        ).pack(side=tk.RIGHT)


# ──────────────────────────────────────────────
#  PERFORMANCE DIAGNOSTICS VIEW
# ──────────────────────────────────────────────
class PerformanceDiagnosticsView(ctk.CTkFrame):
    def __init__(self, master, app):
        super().__init__(master, corner_radius=0, fg_color=BG_CANVAS)
        self.app = app

        content = ctk.CTkFrame(self, fg_color="transparent")
        content.pack(fill=tk.BOTH, expand=True, padx=32, pady=20)

        # Top breadcrumb / return
        top_bar = ctk.CTkFrame(content, fg_color="transparent")
        top_bar.pack(fill=tk.X, pady=(0, 8))

        ctk.CTkButton(
            top_bar, text="← Back to Overview", font=ctk.CTkFont(size=10, weight="bold"),
            fg_color=BG_SURFACE, text_color=TEXT_PRIMARY, hover_color=BG_SURFACE_STRONG,
            border_width=1, border_color=BORDER_STRONG, corner_radius=4, height=28, width=120,
            command=lambda: self.app.switch_view("hub")
        ).pack(side=tk.LEFT)

        ctk.CTkLabel(
            content, text="PERFORMANCE DIAGNOSTICS",
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            text_color=TEXT_MUTED
        ).pack(anchor="w", pady=(4, 2))

        ctk.CTkLabel(
            content, text="Real-Time Hardware & Inference Telemetry",
            font=ctk.CTkFont(family="Segoe UI", size=22, weight="bold"),
            text_color=TEXT_PRIMARY
        ).pack(anchor="w", pady=(0, 14))

        grid = ctk.CTkFrame(content, fg_color="transparent")
        grid.pack(fill=tk.X, pady=(0, 14))
        grid.columnconfigure(0, weight=1)
        grid.columnconfigure(1, weight=1)

        hw = vlr.get_hardware_info()

        self._build_metric_box(grid, 0, 0, "GPU HARDWARE", hw['gpu_name'], "NVIDIA CUDA Tensor Cores Active")
        self._build_metric_box(grid, 0, 1, "INPAINTING PIPELINE", "Seamless Pro + Native C++", "1000 FPS Capable Ultra Fast Engine")
        self._build_metric_box(grid, 1, 0, "COLOR MODEL", "Reinhard CIE-L*a*b*", "Zero Color Fringe or Inpainting Shifts")
        self._build_metric_box(grid, 1, 1, "FFMPEG INTEGRATION", "H.264 / H.265 / ProRes", "Lossless Audio Streams Preserved")

    def _build_metric_box(self, parent, row, col, label, val, sub):
        box = ctk.CTkFrame(parent, corner_radius=6, fg_color=BG_SURFACE,
                           border_width=1, border_color=BORDER_DEFAULT)
        box.grid(row=row, column=col, padx=6, pady=6, sticky="nsew")

        inner = ctk.CTkFrame(box, fg_color="transparent")
        inner.pack(fill=tk.BOTH, expand=True, padx=14, pady=12)

        ctk.CTkLabel(inner, text=label, font=ctk.CTkFont(size=9, weight="bold"),
                     text_color=TEXT_MUTED, anchor="w").pack(fill=tk.X)
        ctk.CTkLabel(inner, text=val, font=ctk.CTkFont(family="Segoe UI", size=15, weight="bold"),
                     text_color=TEXT_PRIMARY, anchor="w").pack(fill=tk.X, pady=(2, 2))
        ctk.CTkLabel(inner, text=sub, font=ctk.CTkFont(size=10),
                     text_color=TEXT_SECONDARY, anchor="w").pack(fill=tk.X)


# ──────────────────────────────────────────────
#  BATCH QUEUE VIEW
# ──────────────────────────────────────────────
class BatchQueueView(ctk.CTkFrame):
    def __init__(self, master, app):
        super().__init__(master, corner_radius=0, fg_color=BG_CANVAS)
        self.app = app

        content = ctk.CTkFrame(self, fg_color="transparent")
        content.pack(fill=tk.BOTH, expand=True, padx=32, pady=20)

        # Top breadcrumb / return
        nav_bar = ctk.CTkFrame(content, fg_color="transparent")
        nav_bar.pack(fill=tk.X, pady=(0, 8))

        ctk.CTkButton(
            nav_bar, text="← Back to Overview", font=ctk.CTkFont(size=10, weight="bold"),
            fg_color=BG_SURFACE, text_color=TEXT_PRIMARY, hover_color=BG_SURFACE_STRONG,
            border_width=1, border_color=BORDER_STRONG, corner_radius=4, height=28, width=120,
            command=lambda: self.app.switch_view("hub")
        ).pack(side=tk.LEFT)

        ctk.CTkLabel(
            content, text="BATCH PROCESSING QUEUE",
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            text_color=TEXT_MUTED
        ).pack(anchor="w", pady=(4, 2))

        ctk.CTkLabel(
            content, text="Parallel Multi-File Queue",
            font=ctk.CTkFont(family="Segoe UI", size=22, weight="bold"),
            text_color=TEXT_PRIMARY
        ).pack(anchor="w", pady=(0, 14))

        top_bar = ctk.CTkFrame(content, fg_color="transparent")
        top_bar.pack(fill=tk.X, pady=(0, 10))

        ctk.CTkButton(
            top_bar, text="Select Folder →", font=ctk.CTkFont(size=11, weight="bold"),
            fg_color="#111111", hover_color=ACCENT_PRIMARY, text_color="#FFFFFF",
            corner_radius=4, width=130, height=34, command=self._select_folder
        ).pack(side=tk.LEFT, padx=(0, 8))

        self.start_batch_btn = ctk.CTkButton(
            top_bar, text="Start Batch Queue", font=ctk.CTkFont(size=11, weight="bold"),
            fg_color=BG_SURFACE, text_color=TEXT_PRIMARY, border_width=1, border_color=BORDER_STRONG,
            hover_color=BG_SURFACE_STRONG, corner_radius=4, width=140, height=34,
            command=self._start_batch
        )
        self.start_batch_btn.pack(side=tk.LEFT, padx=4)

        self.queue_box = ctk.CTkFrame(content, corner_radius=8, fg_color=BG_SURFACE,
                                      border_width=1, border_color=BORDER_DEFAULT)
        self.queue_box.pack(fill=tk.BOTH, expand=True, pady=6)

        self.queue_label = ctk.CTkLabel(
            self.queue_box, text="No folder selected. Click 'Select Folder' to load files into queue.",
            font=ctk.CTkFont(size=11), text_color=TEXT_MUTED
        )
        self.queue_label.pack(expand=True)

    def _select_folder(self):
        folder = filedialog.askdirectory(title="Select Media Folder")
        if folder:
            exts = {".mp4", ".mov", ".avi", ".mkv", ".webm", ".png", ".jpg", ".jpeg", ".webp"}
            files = sorted(p for p in Path(folder).iterdir() if p.suffix.lower() in exts)
            if not files:
                messagebox.showinfo("No Files", "No matching media files found in the folder.")
                return
            self.app.batch_files = files
            self.app.load_media(files[0])
            self.queue_label.configure(
                text=f"Loaded {len(files)} files from {Path(folder).name}/\nReady to process with current watermark region.",
                text_color=TEXT_PRIMARY
            )

    def _start_batch(self):
        if not self.app.batch_files:
            messagebox.showwarning("No Files", "Select a folder first.")
            return
        if self.app.region is None:
            messagebox.showwarning("No Region", "Open Studio first and select the watermark region.")
            return
        self.app.switch_view("video" if self.app.batch_files[0].suffix.lower() in [".mp4", ".mov", ".avi", ".mkv"] else "image")
        self.app.start_batch_processing()


# ──────────────────────────────────────────────
#  CREDITS & ABOUT VIEW
# ──────────────────────────────────────────────
class CreditsView(ctk.CTkFrame):
    def __init__(self, master, app):
        super().__init__(master, corner_radius=0, fg_color=BG_CANVAS)
        self.app = app

        content = ctk.CTkFrame(self, fg_color="transparent")
        content.pack(fill=tk.BOTH, expand=True, padx=32, pady=20)

        # Top breadcrumb / return
        top_bar = ctk.CTkFrame(content, fg_color="transparent")
        top_bar.pack(fill=tk.X, pady=(0, 8))

        ctk.CTkButton(
            top_bar, text="← Back to Overview", font=ctk.CTkFont(size=10, weight="bold"),
            fg_color=BG_SURFACE, text_color=TEXT_PRIMARY, hover_color=BG_SURFACE_STRONG,
            border_width=1, border_color=BORDER_STRONG, corner_radius=4, height=28, width=120,
            command=lambda: self.app.switch_view("hub")
        ).pack(side=tk.LEFT)

        card = ctk.CTkFrame(content, corner_radius=10, fg_color=BG_SURFACE,
                            border_width=1, border_color=BORDER_DEFAULT)
        card.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)

        ctk.CTkLabel(
            card, text="WATERMARK STUDIO",
            font=ctk.CTkFont(family="Segoe UI", size=22, weight="bold"),
            text_color=TEXT_PRIMARY
        ).pack(pady=(16, 2))

        ctk.CTkLabel(
            card, text="Restore. Remove. Refine. • Professional Media Inpainting",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=TEXT_SECONDARY
        ).pack(pady=(0, 12))

        details_box = ctk.CTkFrame(card, corner_radius=6, fg_color=BG_CANVAS,
                                   border_width=1, border_color=BORDER_DEFAULT)
        details_box.pack(fill=tk.BOTH, expand=True, padx=20, pady=4)

        hw = vlr.get_hardware_info()
        info_str = (
            f"Developer       : Doctor9Trio\n"
            f"Profile URL     : https://github.com/Doctor9Trio\n"
            f"Repository      : https://github.com/Doctor9Trio/Video-Watermark-Remover\n"
            f"License         : MIT Open Source License\n"
            f"Hardware Device : {hw['gpu_name']}\n"
            f"Acceleration    : PyTorch CUDA Tensor Cores + C++ Native FFmpeg\n"
            f"Algorithms      : LaMa Neural Inpainting, Reinhard CIE-L*a*b*, Optical KCF/CSRT Tracker"
        )
        ctk.CTkLabel(
            details_box, text=info_str, font=ctk.CTkFont(size=11, family="Consolas"),
            justify=tk.LEFT, anchor="w", text_color=TEXT_PRIMARY
        ).pack(fill=tk.BOTH, expand=True, padx=16, pady=14)

        btn_row = ctk.CTkFrame(card, fg_color="transparent")
        btn_row.pack(pady=14)

        ctk.CTkButton(
            btn_row, text="GitHub Profile →", font=ctk.CTkFont(size=11, weight="bold"),
            fg_color="#111111", hover_color=ACCENT_PRIMARY, text_color="#FFFFFF",
            corner_radius=4, command=lambda: webbrowser.open("https://github.com/Doctor9Trio"),
            width=140, height=32
        ).pack(side=tk.LEFT, padx=6)

        ctk.CTkButton(
            btn_row, text="Project Repo →", font=ctk.CTkFont(size=11),
            fg_color=BG_CANVAS, text_color=TEXT_PRIMARY, border_width=1, border_color=BORDER_STRONG,
            hover_color=BG_SURFACE_STRONG, corner_radius=4,
            command=lambda: webbrowser.open("https://github.com/Doctor9Trio/Video-Watermark-Remover"),
            width=130, height=32
        ).pack(side=tk.LEFT, padx=6)


# ──────────────────────────────────────────────
#  MAIN APPLICATION CONTAINER
# ──────────────────────────────────────────────
class WatermarkStudioApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Watermark Studio — Professional Media Inpainting")
        self.geometry("1240x780")
        self.minsize(1000, 650)

        # State
        self.active_view_name = "hub"
        self.current_file = None
        self.batch_files = []
        self.current_frame = None
        self.first_frame = None
        self.video_cap = None
        self.video_info = None
        self.region = None
        self.processing = False
        self.cancel_event = threading.Event()
        self.progress_queue = queue.Queue()

        self._build_top_bar()
        self._build_views_container()

        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_top_bar(self):
        top_bar = ctk.CTkFrame(self, height=54, corner_radius=0,
                               fg_color=BG_CANVAS,
                               border_width=1, border_color=BORDER_DEFAULT)
        top_bar.pack(fill=tk.X, side=tk.TOP)
        top_bar.pack_propagate(False)

        # Left: Clickable Logo Mark & Brand Text -> Jumps to Home
        left_box = ctk.CTkFrame(top_bar, fg_color="transparent", cursor="hand2")
        left_box.pack(side=tk.LEFT, padx=20)
        left_box.bind("<Button-1>", lambda e: self.switch_view("hub"))

        ws_icon = icons.get_icon("ws", size=18)
        brand_icon_lbl = ctk.CTkLabel(left_box, text="", image=ws_icon, cursor="hand2")
        brand_icon_lbl.pack(side=tk.LEFT, padx=(0, 8))
        brand_icon_lbl.bind("<Button-1>", lambda e: self.switch_view("hub"))

        brand_txt_lbl = ctk.CTkLabel(
            left_box, text="WATERMARK STUDIO",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            text_color=TEXT_PRIMARY, cursor="hand2"
        )
        brand_txt_lbl.pack(side=tk.LEFT)
        brand_txt_lbl.bind("<Button-1>", lambda e: self.switch_view("hub"))

        # Center Navigation Tabs (Home, Studio, Projects, Queue, Diagnostics, Credits)
        center_nav = ctk.CTkFrame(top_bar, fg_color="transparent")
        center_nav.pack(side=tk.LEFT, expand=True)

        self.nav_btns = {}
        tabs = [
            ("Home", "hub"),
            ("Studio", "video"),
            ("Projects", "image"),
            ("Queue", "batch"),
            ("Diagnostics", "diagnostics"),
            ("Credits", "credits")
        ]
        for tab_name, view_id in tabs:
            btn = ctk.CTkButton(
                center_nav, text=tab_name, font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
                fg_color="transparent", text_color=TEXT_SECONDARY, hover_color=BG_SURFACE,
                corner_radius=4, height=30, width=70,
                command=lambda v=view_id: self.switch_view(v)
            )
            btn.pack(side=tk.LEFT, padx=2)
            self.nav_btns[view_id] = btn

        # Right Controls
        right_tools = ctk.CTkFrame(top_bar, fg_color="transparent")
        right_tools.pack(side=tk.RIGHT, padx=20)

        # Status Dot
        hw = vlr.get_hardware_info()
        dot_col = "#17824B" if hw["has_cuda"] else "#A96500"
        status_box = ctk.CTkFrame(right_tools, fg_color="transparent")
        status_box.pack(side=tk.LEFT, padx=8)
        ctk.CTkLabel(status_box, text="●", font=ctk.CTkFont(size=10), text_color=dot_col).pack(side=tk.LEFT, padx=(0, 4))
        ctk.CTkLabel(status_box, text="GPU Ready", font=ctk.CTkFont(size=10, weight="bold"),
                     text_color=TEXT_PRIMARY).pack(side=tk.LEFT)

        # Theme Toggle
        theme_icon = icons.get_icon("theme", size=15)
        self.theme_btn = ctk.CTkButton(
            right_tools, text="", image=theme_icon, width=32, height=32,
            fg_color=BG_SURFACE, hover_color=BG_SURFACE_STRONG, corner_radius=4,
            command=self._toggle_theme
        )
        self.theme_btn.pack(side=tk.LEFT, padx=4)

        # GitHub Link
        github_icon = icons.get_icon("github", size=15)
        github_btn = ctk.CTkButton(
            right_tools, text="GitHub", image=github_icon, compound="left", width=75, height=32,
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            fg_color=BG_SURFACE, text_color=TEXT_PRIMARY, hover_color=BG_SURFACE_STRONG, corner_radius=4,
            command=lambda: webbrowser.open("https://github.com/Doctor9Trio/Video-Watermark-Remover")
        )
        github_btn.pack(side=tk.LEFT, padx=4)

    def _build_views_container(self):
        self.views_container = ctk.CTkFrame(self, fg_color=BG_CANVAS)
        self.views_container.pack(fill=tk.BOTH, expand=True)

        self.hub_view = MainHubView(self.views_container, self)
        self.credits_view = CreditsView(self.views_container, self)
        self.diag_view = PerformanceDiagnosticsView(self.views_container, self)
        self.batch_view = BatchQueueView(self.views_container, self)

        # Workstation Editor Frame (Video & Image Studios)
        self.workstation_frame = ctk.CTkFrame(self.views_container, fg_color="transparent")

        self.bread_bar = ctk.CTkFrame(self.workstation_frame, height=26, corner_radius=0, fg_color="transparent")
        self.bread_bar.pack(fill=tk.X, padx=12, pady=(2, 0))
        self.bread_bar.pack_propagate(False)

        ctk.CTkButton(
            self.bread_bar, text="← Back to Overview", font=ctk.CTkFont(size=9, weight="bold"),
            fg_color=BG_SURFACE, text_color=TEXT_PRIMARY, hover_color=BG_SURFACE_STRONG,
            border_width=1, border_color=BORDER_STRONG, corner_radius=4, height=22, width=110,
            command=lambda: self.switch_view("hub")
        ).pack(side=tk.LEFT, padx=(0, 10))

        self.breadcrumb_label = ctk.CTkLabel(
            self.bread_bar, text="Workspace / Video Inpainting",
            font=ctk.CTkFont(size=9, family="Segoe UI", weight="bold"), text_color=TEXT_MUTED
        )
        self.breadcrumb_label.pack(side=tk.LEFT)

        content = ctk.CTkFrame(self.workstation_frame, fg_color="transparent")
        content.pack(fill=tk.BOTH, expand=True, padx=12, pady=2)

        left_col = ctk.CTkFrame(content, fg_color="transparent")
        left_col.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 8))

        self.canvas_workspace = MediaCanvasViewport(left_col, self)
        self.canvas_workspace.pack(fill=tk.BOTH, expand=True)

        self.timeline_frame = ctk.CTkFrame(left_col, height=38, corner_radius=6,
                                           fg_color=BG_CANVAS,
                                           border_width=1, border_color=BORDER_DEFAULT)
        self.timeline_frame.pack(fill=tk.X, pady=(4, 0))
        self.timeline_frame.pack_propagate(False)

        ctk.CTkLabel(self.timeline_frame, text="Seek Frame:",
                     font=ctk.CTkFont(size=10, weight="bold"),
                     text_color=TEXT_PRIMARY).pack(side=tk.LEFT, padx=(10, 4))

        self.time_slider = ctk.CTkSlider(
            self.timeline_frame, from_=0, to=100, number_of_steps=100, height=12,
            progress_color=ACCENT_PRIMARY, button_color="#111111", command=self._on_seek
        )
        self.time_slider.set(0)
        self.time_slider.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=6)

        self.time_label = ctk.CTkLabel(
            self.timeline_frame, text="00:00:00 (0 / 0)", font=ctk.CTkFont(size=9, family="Consolas"),
            width=120, text_color=TEXT_MUTED
        )
        self.time_label.pack(side=tk.RIGHT, padx=10)

        self.sidebar = ControlSidebar(content, self)
        self.sidebar.pack(side=tk.RIGHT, fill=tk.Y)

        bottom = ctk.CTkFrame(self.workstation_frame, height=30, corner_radius=0,
                              fg_color=BG_CANVAS,
                              border_width=1, border_color=BORDER_DEFAULT)
        bottom.pack(fill=tk.X, side=tk.BOTTOM)
        bottom.pack_propagate(False)

        self.progress_bar = ctk.CTkProgressBar(bottom, height=5, corner_radius=2,
                                               progress_color=ACCENT_PRIMARY)
        self.progress_bar.set(0)
        self.progress_bar.pack(side=tk.LEFT, padx=12, fill=tk.X, expand=True)

        self.status_text = ctk.CTkLabel(
            bottom, text="Ready", font=ctk.CTkFont(size=9), text_color=TEXT_MUTED
        )
        self.status_text.pack(side=tk.RIGHT, padx=12)

        self.switch_view("hub")

    def switch_view(self, view_name):
        self.active_view_name = view_name
        self.hub_view.pack_forget()
        self.credits_view.pack_forget()
        self.diag_view.pack_forget()
        self.batch_view.pack_forget()
        self.workstation_frame.pack_forget()

        for v_id, btn in self.nav_btns.items():
            btn.configure(text_color=ACCENT_PRIMARY if v_id == view_name else TEXT_SECONDARY)

        if view_name == "hub":
            self.hub_view.pack(fill=tk.BOTH, expand=True)
            self.hub_view.pipeline_canvas.start()
        elif view_name == "diagnostics":
            self.hub_view.pipeline_canvas.stop()
            self.diag_view.pack(fill=tk.BOTH, expand=True)
        elif view_name == "batch":
            self.hub_view.pipeline_canvas.stop()
            self.batch_view.pack(fill=tk.BOTH, expand=True)
        elif view_name == "credits":
            self.hub_view.pipeline_canvas.stop()
            self.credits_view.pack(fill=tk.BOTH, expand=True)
        else:
            self.hub_view.pipeline_canvas.stop()
            self.workstation_frame.pack(fill=tk.BOTH, expand=True)

            if view_name == "image":
                self.timeline_frame.pack_forget()
                self.breadcrumb_label.configure(text="Workspace / Image Inpainting Studio")
            else:
                self.timeline_frame.pack(fill=tk.X, pady=(4, 0))
                self.breadcrumb_label.configure(text="Workspace / Video Inpainting Studio")

    def _toggle_theme(self):
        curr = ctk.get_appearance_mode()
        new_mode = "Dark" if curr == "Light" else "Light"
        ctk.set_appearance_mode(new_mode)
        self.hub_view.pipeline_canvas.set_theme(new_mode)

    def load_media(self, path):
        ext = path.suffix.lower()
        if ext in [".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff"]:
            self.switch_view("image")
            self._load_image(path)
        else:
            self.switch_view("video")
            self._load_video(path)

    def _load_image(self, path):
        self.current_file = path
        self.region = None
        self.sidebar._clear_region()

        img = cv2.imread(str(path))
        if img is None:
            messagebox.showerror("Error", f"Cannot load image: {path}")
            return

        self.current_frame = img
        h, w = img.shape[:2]
        self.sidebar.file_name_label.configure(text=f"{path.name} [{path.suffix.upper()}]")
        self.sidebar.specs_label.configure(text=f"Res: {w}x{h} ({'4K' if w>=3840 else 'HD'}) | Format: {path.suffix.upper()}")
        self.breadcrumb_label.configure(text=f"Workspace / Image Inpainting / {path.name} ({w}x{h})")

        self.canvas_workspace.show_frame(img)
        self.status_text.configure(text=f"Loaded Image: {path.name}")

    def _load_video(self, path):
        self.current_file = path
        self.region = None
        self.sidebar._clear_region()

        if self.video_cap:
            self.video_cap.release()

        self.video_cap = cv2.VideoCapture(str(path))
        ret, frame = self.video_cap.read()

        if not ret:
            messagebox.showerror("Error", f"Cannot read video: {path}")
            return

        self.current_frame = frame
        self.first_frame = frame.copy()
        self.video_info = vlr.get_video_info(path)

        info = self.video_info
        total_f = info["total_frames"] or 100
        self.time_slider.configure(to=total_f, number_of_steps=total_f)
        self.time_slider.set(0)
        self.time_label.configure(text=f"00:00:00 (1 / {total_f})")

        self.sidebar.file_name_label.configure(text=f"{path.name} [{path.suffix.upper()}]")
        self.sidebar.specs_label.configure(
            text=f"Res: {info['width']}x{info['height']} ({'4K' if info['width']>=3840 else 'HD'}) | {info['fps']:.1f} FPS\n"
                 f"Codec: {info.get('codec', '?')}"
        )
        self.breadcrumb_label.configure(text=f"Workspace / Video Inpainting / {path.name} ({info['width']}x{info['height']} @ {info['fps']:.1f}fps)")

        self.canvas_workspace.show_frame(frame)
        self.status_text.configure(text=f"Loaded Video: {path.name}")
        threading.Thread(target=vlr.get_lama_model, daemon=True).start()

    def _on_seek(self, val):
        if not self.video_cap or not self.video_info:
            return
        frame_idx = int(val)
        self.video_cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
        ret, frame = self.video_cap.read()
        if ret:
            self.current_frame = frame
            self.canvas_workspace.show_frame(frame)
            dur = frame_idx / max(self.video_info["fps"], 1.0)
            total_f = self.video_info["total_frames"] or 100
            self.time_label.configure(text=f"{vlr.format_time(dur)} ({frame_idx}/{total_f})")

    def _apply_settings(self):
        engine_str = self.sidebar.engine_var.get()
        if "Seamless Pro" in engine_str:
            vlr.INPAINT_ENGINE = "seamless_pro"
        elif "Ultra-Fast" in engine_str:
            vlr.INPAINT_ENGINE = "fast"
        elif "Clone" in engine_str:
            vlr.INPAINT_ENGINE = "clone"
        elif "Blur" in engine_str:
            vlr.INPAINT_ENGINE = "blur"
        else:
            vlr.INPAINT_ENGINE = "opencv"

        vlr.TRACKING_MODE = self.sidebar.tracking_var.get()
        vlr.COLOR_MATCH = self.sidebar.color_match_var.get()
        vlr.ADD_GRAIN = self.sidebar.grain_var.get()
        vlr.CRF_QUALITY = int(self.sidebar.crf_slider.get())

    def start_processing(self):
        self._apply_settings()
        self.cancel_event.clear()

        output_path = self.current_file.parent / f"{self.current_file.stem}_clean{self.current_file.suffix}"

        self.processing = True
        self.sidebar.set_processing_state(True)
        self.progress_bar.set(0)
        self.status_text.configure(text="Processing media...")
        start_time = time.time()

        def gui_progress(current, total, start_t):
            self.progress_queue.put((current, total, start_t))

        self._poll_progress()

        def worker():
            if self.active_view_name == "image":
                success = vlr.process_image(
                    str(self.current_file), str(output_path),
                    self.region, progress_callback=gui_progress
                )
            else:
                success = vlr.process_video(
                    str(self.current_file), str(output_path),
                    self.region, self.video_info,
                    cancel_event=self.cancel_event,
                    progress_callback=gui_progress
                )
            elapsed = time.time() - start_time
            self.after(0, lambda: self._on_done(success, output_path, elapsed))

        threading.Thread(target=worker, daemon=True).start()

    def start_batch_processing(self):
        self._apply_settings()
        self.cancel_event.clear()

        self.processing = True
        self.sidebar.set_processing_state(True)
        self.progress_bar.set(0)

        def gui_progress(current, total, start_time):
            self.progress_queue.put((current, total, start_time))

        self._poll_progress()

        region = self.region
        files = list(self.batch_files)

        def worker():
            results = []
            for i, filepath in enumerate(files):
                if self.cancel_event.is_set():
                    break
                self.after(0, lambda i=i, f=filepath: self.status_text.configure(text=f"[{i+1}/{len(files)}] {f.name}"))
                self.after(0, lambda: self.progress_bar.set(0))

                output = filepath.parent / f"{filepath.stem}_clean{filepath.suffix}"
                if self.active_view_name == "image":
                    ok = vlr.process_image(str(filepath), str(output), region, progress_callback=gui_progress)
                else:
                    info = vlr.get_video_info(filepath)
                    ok = vlr.process_video(
                        str(filepath), str(output), region, info,
                        cancel_event=self.cancel_event,
                        progress_callback=gui_progress
                    )
                results.append((filepath.name, ok))

            self.after(0, lambda: self._on_batch_done(results))

        threading.Thread(target=worker, daemon=True).start()

    def cancel_processing(self):
        if self.processing:
            self.cancel_event.set()
            self.status_text.configure(text="Cancelling...")

    def _poll_progress(self):
        try:
            while True:
                current, total, start_time = self.progress_queue.get_nowait()
                if total and total > 0:
                    pct = min(1.0, current / total)
                    self.progress_bar.set(pct)
                    elapsed = time.time() - start_time
                    if current > 0 and elapsed > 0:
                        fps = current / elapsed
                        eta = (total - current) / fps
                        video_fps = self.video_info["fps"] if self.video_info else 30.0
                        speed_mult = fps / max(video_fps, 1e-6)
                        self.status_text.configure(
                            text=f"Frame {current}/{total} ({pct*100:.1f}%) • {fps:.1f} FPS ({speed_mult:.1f}x) • ETA {vlr.format_time(eta)}")
        except queue.Empty:
            pass

        if self.processing:
            self.after(50, self._poll_progress)

    def _on_done(self, success, output_path, elapsed_time=0):
        self.processing = False
        self.sidebar.set_processing_state(False)
        self.progress_bar.set(1.0 if success else 0)

        if success:
            fps_val = None
            if self.video_info and self.video_info.get("total_frames") and elapsed_time > 0:
                fps_val = self.video_info["total_frames"] / elapsed_time
            self.status_text.configure(text=f"Completed: {output_path.name}")
            EditorialSuccessModal(self, output_path, elapsed_time, fps_val)
        elif self.cancel_event.is_set():
            self.status_text.configure(text="Processing cancelled.")
        else:
            self.status_text.configure(text="Processing failed.")
            messagebox.showerror("Error", "Media processing failed. Check terminal for details.")

    def _on_batch_done(self, results):
        self.processing = False
        self.sidebar.set_processing_state(False)
        self.progress_bar.set(1.0)
        ok_count = sum(1 for _, ok in results if ok)
        msg = f"Batch complete: {ok_count}/{len(results)} files processed successfully."
        self.status_text.configure(text=msg)
        messagebox.showinfo("Batch Complete", msg)

    def _on_close(self):
        if self.processing:
            if not messagebox.askyesno("Confirm Exit", "Media is currently processing.\nDo you want to stop and exit?"):
                return
            self.cancel_event.set()
        if self.video_cap:
            self.video_cap.release()
        self.destroy()


# ──────────────────────────────────────────────
#  ENTRY POINT
# ──────────────────────────────────────────────
def main():
    app = WatermarkStudioApp()
    app.mainloop()


if __name__ == "__main__":
    main()
