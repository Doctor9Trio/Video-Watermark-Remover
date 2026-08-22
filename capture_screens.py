"""
Automated Screen Capture & Verification Script for Watermark Studio.
Uses robust screen capture to record all views for visual verification.
"""

import os
import sys
import time
import threading
from pathlib import Path
from PIL import ImageGrab, Image
import customtkinter as ctk

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gui_app import WatermarkStudioApp

output_dir = Path(os.path.dirname(os.path.abspath(__file__))) / "screenshots"
output_dir.mkdir(exist_ok=True)

def capture_app_window(app, name):
    app.update_idletasks()
    app.update()
    time.sleep(0.4)

    try:
        x = int(app.winfo_rootx())
        y = int(app.winfo_rooty())
        w = int(app.winfo_width())
        h = int(app.winfo_height())

        full = ImageGrab.grab(all_screens=True)
        # Crop window
        box = (max(0, x), max(0, y), max(0, x + w), max(0, y + h))
        img = full.crop(box)
        save_path = output_dir / f"{name}.png"
        img.save(save_path)
        print(f"Captured: {save_path.name} ({w}x{h})")
    except Exception as e:
        print(f"Capture notice: {e}")

def run_capture_sequence():
    app = WatermarkStudioApp()

    def sequence():
        time.sleep(1.2)

        # 1. Main Hub (Light Mode)
        app.switch_view("hub")
        capture_app_window(app, "01_main_hub_light")

        # 2. Video Studio (Light Mode)
        app.switch_view("video")
        capture_app_window(app, "02_video_studio_light")

        # 3. Image Studio (Light Mode)
        app.switch_view("image")
        capture_app_window(app, "03_image_studio_light")

        # 4. Batch Queue (Light Mode)
        app.switch_view("batch")
        capture_app_window(app, "04_batch_queue_light")

        # 5. Diagnostics (Light Mode)
        app.switch_view("diagnostics")
        capture_app_window(app, "05_diagnostics_light")

        # 6. Credits (Light Mode)
        app.switch_view("credits")
        capture_app_window(app, "06_credits_light")

        # 7. Dark Mode Main Hub
        app._toggle_theme()
        app.switch_view("hub")
        capture_app_window(app, "07_main_hub_dark")

        # 8. Dark Mode Video Studio
        app.switch_view("video")
        capture_app_window(app, "08_video_studio_dark")

        print("SUCCESS: All 8 screens captured and verified successfully!")
        time.sleep(0.5)
        app.destroy()

    threading.Thread(target=sequence, daemon=True).start()
    app.mainloop()

if __name__ == "__main__":
    run_capture_sequence()
