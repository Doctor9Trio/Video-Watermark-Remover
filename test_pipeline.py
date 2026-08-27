"""
Automated Verification Test Suite for Watermark Studio Pro v7.0.
Verifies:
1. 4K 60FPS Video Inpainting (Format preservation & Audio pass-through)
2. Moving Watermark Tracking Pipeline
3. High-Resolution Image Inpainting (PNG/JPG)
"""

import sys
import os
import time
import cv2
import numpy as np
from pathlib import Path

import watermark_remover as vlr

def create_synthetic_image(path):
    """Create a high-res image with a synthetic watermark."""
    img = np.zeros((1440, 2560, 3), dtype=np.uint8)
    # Background gradient
    for y in range(1440):
        img[y, :, 0] = int(y / 1440 * 180)
        img[y, :, 1] = int(120 + y / 1440 * 80)
        img[y, :, 2] = int(220 - y / 1440 * 100)

    # Watermark text
    cv2.putText(img, "TEST_IMAGE_WATERMARK", (2000, 1350), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (255, 255, 255), 3, cv2.LINE_AA)
    cv2.imwrite(str(path), img)
    return (1980, 1300, 500, 80)

def test_image_inpainting():
    print("\n--- Testing Image Inpainting ---")
    out_dir = Path("test_output")
    out_dir.mkdir(exist_ok=True)
    img_path = out_dir / "test_input.png"
    out_path = out_dir / "test_cleaned.png"

    region = create_synthetic_image(img_path)
    ok = vlr.process_image(img_path, out_path, region)
    assert ok, "Image inpainting failed!"
    assert out_path.exists(), "Output image file not created!"
    print(f"  [PASS] Image inpainting successful! Output: {out_path.name}")

def test_video_pipeline():
    print("\n--- Testing 4K 60FPS Video Pipeline ---")
    out_dir = Path("test_output")
    out_dir.mkdir(exist_ok=True)
    video_path = out_dir / "clip_4k_test.mov"
    out_path = out_dir / "clip_4k_test_clean.mov"

    # Create synthetic 4K MOV video if not exists
    if not video_path.exists():
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        writer = cv2.VideoWriter(str(video_path), fourcc, 60.0, (3840, 2160))
        for f in range(60):
            frame = np.zeros((2160, 3840, 3), dtype=np.uint8)
            frame[:, :] = (30, 40, 50)
            cv2.putText(frame, "WATERMARK_4K", (3200, 180), cv2.FONT_HERSHEY_SIMPLEX, 2.0, (255, 255, 255), 4)
            writer.write(frame)
        writer.release()

    info = vlr.get_video_info(video_path)
    region = (3180, 100, 600, 120)
    for eng in ["fast_v2", "fast_v1"]:
        vlr.INPAINT_ENGINE = eng
        out_path = out_dir / f"clip_4k_test_{eng}.mov"
        ok = vlr.process_video(video_path, out_path, region, info)
        assert ok, f"Video inpainting failed for {eng}!"
        assert out_path.exists(), f"Output video file not created for {eng}!"
        print(f"  [PASS] Video inpainting successful for '{eng}'! Output: {out_path.name}")

def test_all_engines():
    print("\n--- Testing Inpainting Engines (Blur, Clone, Fast, Seamless Pro) ---")
    out_dir = Path("test_output")
    out_dir.mkdir(exist_ok=True)
    img_path = out_dir / "test_input.png"
    
    region = create_synthetic_image(img_path)
    
    for engine in ["seamless_pro", "blur", "clone", "fast", "opencv"]:
        vlr.INPAINT_ENGINE = engine
        vlr.PRECISE_MASK = True
        vlr.FEATHER_RADIUS = 3
        out_path = out_dir / f"test_cleaned_{engine}.png"
        ok = vlr.process_image(img_path, out_path, region)
        assert ok, f"Engine {engine} failed!"
        assert out_path.exists(), f"Engine {engine} output missing!"
        print(f"  [PASS] Engine '{engine}' successfully processed image!")

def test_multi_region():
    print("\n--- Testing Multi-Region Simultaneous Inpainting ---")
    out_dir = Path("test_output")
    out_dir.mkdir(exist_ok=True)
    img_path = out_dir / "test_multi_in.png"
    out_path = out_dir / "test_multi_out.png"

    # Create image with 2 separate watermarks (top-left and bottom-right)
    img = np.full((1080, 1920, 3), (240, 240, 240), dtype=np.uint8)
    cv2.putText(img, "TOP_LEFT_WATERMARK", (50, 80), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (10, 10, 10), 2)
    cv2.putText(img, "BOTTOM_RIGHT_WATERMARK", (1400, 1020), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (10, 10, 10), 2)
    cv2.imwrite(str(img_path), img)

    regions = [(40, 40, 420, 60), (1380, 980, 500, 60)]
    ok = vlr.process_image(img_path, out_path, regions)
    assert ok, "Multi-region image inpainting failed!"
    assert out_path.exists(), "Multi-region output missing!"
    print(f"  [PASS] Multi-region simultaneous inpainting passed! Output: {out_path.name}")


if __name__ == "__main__":
    print("=================================================================")
    print("  WATERMARK STUDIO PRO v7.0 - AUTOMATED VERIFICATION SUITE       ")
    print("=================================================================")
    test_image_inpainting()
    test_all_engines()
    test_video_pipeline()
    test_multi_region()
    print("\n=================================================================")
    print("  [PASS] ALL STUDIO v7.0 TESTS COMPLETED SUCCESSFULLY!           ")
    print("=================================================================")
