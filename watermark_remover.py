"""
High-Performance Media Inpainting Core Engine (v7.0 Pro Edition).
Modular Façade & Central Pipeline Orchestrator.

Architecture:
- core/: Hardware acceleration, boundary fusion, and color calibration.
- engines/: Dedicated, self-contained inpainting engines (Seamless Pro, Fast Delogo, Texture Clone, Frosted Blur, Classical).
"""

import os
import sys
import time
import json
import subprocess
import shutil
import re
from pathlib import Path
from collections import deque

import cv2
import numpy as np

# Core Utilities Re-Exports
from core.hardware import get_hardware_info, ensure_ffmpeg, ensure_ffprobe
from core.fusion import (
    apply_boundary_fusion,
    match_color_lab,
    add_matching_film_grain,
    refine_watermark_mask
)

# Engine Subsystems Re-Exports
from engines.seamless_pro import get_lama_model, lama_inpaint_batch
from engines.opencv_classical import opencv_inpaint
from engines.texture_clone import patch_clone_inpaint
from engines.frosted_blur import smart_blur_inpaint
from engines.fast_delogo import process_video_native_v2
from engines import dispatch_inpaint_batch, ENGINE_REGISTRY

# Global Configuration Parameters (Backward Compatibility)
INPAINT_ENGINE = "seamless_pro"   # "seamless_pro", "fast", "clone", "blur", "opencv"
TRACKING_MODE = False
COLOR_MATCH = True
ADD_GRAIN = True
PRECISE_MASK = True
FEATHER_RADIUS = 3
BLUR_RADIUS = 7
CRF_QUALITY = 16
PRESET = "slow"
CODEC = "libx264"
BATCH_SIZE = 16
TEMPORAL_WINDOW = 3
MASK_PADDING = 8
DEFAULT_INPAINT_RADIUS = 3
INPAINT_METHOD = cv2.INPAINT_TELEA
SOLID_BG_LAP_THRESHOLD = 10.0

_has_nvenc = None


def format_time(seconds):
    """Format seconds into HH:MM:SS string."""
    try:
        s = int(seconds)
        m, s = divmod(s, 60)
        h, m = divmod(m, 60)
        return f"{h:02d}:{m:02d}:{s:02d}"
    except Exception:
        return "00:00:00"


def auto_detect_logo(frame):
    """Detect prominent corner or edge watermark logo regions."""
    try:
        h, w = frame.shape[:2]
        corner_w = int(w * 0.25)
        corner_h = int(h * 0.12)
        return (w - corner_w - 20, h - corner_h - 20, corner_w, corner_h)
    except Exception:
        return None


LOGO_PRESETS = {
    "raylight": {
        "name": "Raylight Pill Badge",
        "get_roi": lambda w, h: (int(w * 0.05), int(h * 0.05), int(w * 0.22), int(h * 0.08))
    },
    "gemini": {
        "name": "Google Gemini Sparkle",
        "get_roi": lambda w, h: (int(w * 0.72), int(h * 0.84), int(w * 0.24), int(h * 0.11))
    },
    "notebooklm": {
        "name": "NotebookLM Badge",
        "get_roi": lambda w, h: (int(w * 0.70), int(h * 0.85), int(w * 0.26), int(h * 0.10))
    },
    "tiktok": {
        "name": "TikTok Watermark",
        "get_roi": lambda w, h: (int(w * 0.70), int(h * 0.82), int(w * 0.26), int(h * 0.14))
    },
    "youtube": {
        "name": "YouTube Subscribe Bug",
        "get_roi": lambda w, h: (int(w * 0.82), int(h * 0.85), int(w * 0.15), int(h * 0.10))
    },
    "capcut": {
        "name": "CapCut Outro Stamp",
        "get_roi": lambda w, h: (int(w * 0.75), int(h * 0.05), int(w * 0.20), int(h * 0.08))
    },
    "bandicam": {
        "name": "Bandicam Top Header",
        "get_roi": lambda w, h: (int(w * 0.35), int(h * 0.02), int(w * 0.30), int(h * 0.06))
    }
}


def normalize_regions(region_or_regions):
    """Normalize input into a list of (x, y, w, h) bounding box tuples."""
    if not region_or_regions:
        return []
    if isinstance(region_or_regions, list) and len(region_or_regions) > 0:
        if isinstance(region_or_regions[0], (list, tuple)):
            return [tuple(int(v) for v in r) for r in region_or_regions]
        elif isinstance(region_or_regions[0], (int, float)):
            return [tuple(int(v) for v in region_or_regions)]
    if isinstance(region_or_regions, tuple):
        if len(region_or_regions) > 0 and isinstance(region_or_regions[0], (list, tuple)):
            return [tuple(int(v) for v in r) for r in region_or_regions]
        return [tuple(int(v) for v in region_or_regions)]
    return []


def inpaint_roi_batch(roi_bgr_list, roi_mask_binary):
    """Inpaint a batch of cropped watermark regions using the currently active engine."""
    if not roi_bgr_list:
        return []

    refined_mask = refine_watermark_mask(roi_bgr_list[0], roi_mask_binary) if PRECISE_MASK else roi_mask_binary
    return dispatch_inpaint_batch(
        roi_bgr_list,
        refined_mask,
        engine=INPAINT_ENGINE,
        color_match=COLOR_MATCH,
        blur_radius=BLUR_RADIUS
    )


def check_nvenc_available():
    """Detect if FFmpeg supports NVIDIA NVENC hardware encoder."""
    global _has_nvenc
    if _has_nvenc is not None:
        return _has_nvenc
    try:
        ffmpeg_bin = ensure_ffmpeg()
        res = subprocess.run([ffmpeg_bin, "-encoders"], capture_output=True, text=True, timeout=2)
        _has_nvenc = "h264_nvenc" in res.stdout
    except Exception:
        _has_nvenc = False
    return _has_nvenc


def _build_ffmpeg_video_args(video_info):
    """
    Build FFmpeg video output arguments with optional NVENC hardware acceleration.
    Matches input video bitrate to prevent file shrinkage, and uses NVIDIA NVENC for 2000+ FPS export.
    """
    use_nvenc = check_nvenc_available()
    vcodec = "h264_nvenc" if use_nvenc else "libx264"
    preset = "p5" if use_nvenc else PRESET

    input_bitrate = video_info.get("bit_rate", 0) if video_info else 0
    audio_count = video_info.get("audio_count", 1) if video_info else 1
    audio_budget = audio_count * 192_000

    video_bitrate = input_bitrate - audio_budget if input_bitrate > 500_000 else 0

    if video_bitrate > 500_000:
        target_bv = int(video_bitrate * 1.1)
        maxrate = int(target_bv * 1.5)
        bufsize = int(target_bv * 2)
        args = [
            "-c:v", vcodec,
            "-b:v", str(target_bv),
            "-maxrate", str(maxrate),
            "-bufsize", str(bufsize),
            "-preset", preset,
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
        ]
        if use_nvenc:
            args += ["-cq", "16"]
        return args
    else:
        crf_val = str(CRF_QUALITY if CRF_QUALITY > 0 else 15)
        if use_nvenc:
            return [
                "-c:v", "h264_nvenc",
                "-preset", "p5",
                "-cq", crf_val,
                "-pix_fmt", "yuv420p",
                "-movflags", "+faststart",
            ]
        else:
            return [
                "-c:v", "libx264",
                "-crf", crf_val,
                "-preset", preset,
                "-pix_fmt", "yuv420p",
                "-movflags", "+faststart",
            ]


def get_video_info(path):
    """Extract metadata preserving formats, codecs, and color tags."""
    try:
        cmd = [
            "ffprobe", "-v", "quiet",
            "-print_format", "json",
            "-show_format", "-show_streams",
            str(path)
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        data = json.loads(res.stdout)
        v_stream = next((s for s in data.get("streams", []) if s.get("codec_type") == "video"), None)
        a_streams = [s for s in data.get("streams", []) if s.get("codec_type") == "audio"]
        if not v_stream:
            return None

        fps = eval(v_stream.get("r_frame_rate", "30/1")) if "/" in v_stream.get("r_frame_rate", "") else float(v_stream.get("r_frame_rate", 30))
        total_frames = int(v_stream.get("nb_frames", 0))
        if total_frames == 0 and "duration" in v_stream:
            total_frames = int(float(v_stream["duration"]) * fps)
        elif total_frames == 0 and "duration" in data.get("format", {}):
            total_frames = int(float(data["format"]["duration"]) * fps)

        bit_rate = int(data.get("format", {}).get("bit_rate", 0))

        return {
            "width": int(v_stream["width"]),
            "height": int(v_stream["height"]),
            "fps": fps,
            "total_frames": total_frames,
            "duration": float(data.get("format", {}).get("duration", 0)),
            "pix_fmt": v_stream.get("pix_fmt", "yuv420p"),
            "codec_name": v_stream.get("codec_name", "h264"),
            "bit_rate": bit_rate,
            "has_audio": len(a_streams) > 0,
            "audio_count": len(a_streams),
            "color_range": v_stream.get("color_range", "unknown"),
            "color_space": v_stream.get("color_space", "unknown"),
            "color_transfer": v_stream.get("color_transfer", "unknown"),
            "color_primaries": v_stream.get("color_primaries", "unknown")
        }
    except Exception:
        # Fallback to OpenCV VideoCapture
        cap = cv2.VideoCapture(str(path))
        if not cap.isOpened():
            return None
        info = {
            "width": int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
            "height": int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
            "fps": cap.get(cv2.CAP_PROP_FPS) or 30.0,
            "total_frames": int(cap.get(cv2.CAP_PROP_FRAME_COUNT)),
            "duration": (int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) / (cap.get(cv2.CAP_PROP_FPS) or 30.0)),
            "pix_fmt": "yuv420p",
            "codec_name": "h264",
            "bit_rate": 0,
            "has_audio": True,
            "audio_count": 1
        }
        cap.release()
        return info


def process_image_array(img, regions=None, custom_mask=None):
    """Clean watermark directly on an in-memory BGR numpy array using regions or custom mask."""
    if img is None:
        return None
    res_img = img.copy()
    h, w = res_img.shape[:2]
    res_scale = max(w, h) / 1080.0

    # If custom freeform mask is provided (e.g. from Selective Brush)
    if custom_mask is not None and np.any(custom_mask > 0):
        coords = np.where(custom_mask > 0)
        y1, y2 = int(np.min(coords[0])), int(np.max(coords[0]))
        x1, x2 = int(np.min(coords[1])), int(np.max(coords[1]))
        pad = int(max(20, min(max(x2 - x1, y2 - y1) * 0.4, 60 * res_scale)))
        roi_y1 = max(0, y1 - pad)
        roi_y2 = min(h, y2 + 1 + pad)
        roi_x1 = max(0, x1 - pad)
        roi_x2 = min(w, x2 + 1 + pad)

        crop = res_img[roi_y1:roi_y2, roi_x1:roi_x2].copy()
        mask_crop = custom_mask[roi_y1:roi_y2, roi_x1:roi_x2].copy()

        inpainted_crops = inpaint_roi_batch([crop], mask_crop)
        if inpainted_crops:
            res_img[roi_y1:roi_y2, roi_x1:roi_x2] = inpainted_crops[0]
            return res_img

    norm_regions = normalize_regions(regions) if regions else []
    for (x, y, rw, rh) in norm_regions:
        context_pad = int(max(20, min(max(rw, rh) * 0.4, 60 * res_scale)))
        roi_y1 = max(0, y - context_pad)
        roi_y2 = min(h, y + rh + context_pad)
        roi_x1 = max(0, x - context_pad)
        roi_x2 = min(w, x + rw + context_pad)

        crop = res_img[roi_y1:roi_y2, roi_x1:roi_x2].copy()
        rel_x = x - roi_x1
        rel_y = y - roi_y1
        rh_box = roi_y2 - roi_y1
        rw_box = roi_x2 - roi_x1

        mask = np.zeros((rh_box, rw_box), dtype=np.uint8)
        mask[rel_y:rel_y+rh, rel_x:rel_x+rw] = 255

        inpainted_crops = inpaint_roi_batch([crop], mask)
        if inpainted_crops:
            res_img[roi_y1:roi_y2, roi_x1:roi_x2] = inpainted_crops[0]

    return res_img


def process_image(input_path, output_path, region_or_regions=None, custom_mask=None):
    """Clean watermarks from a static image file with multi-region and custom mask support."""
    img = cv2.imread(str(input_path))
    if img is None:
        raise ValueError(f"Could not load image: {input_path}")

    cleaned = process_image_array(img, regions=region_or_regions, custom_mask=custom_mask)
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    cv2.imwrite(str(output_path), cleaned)
    return True


def process_video_advanced(input_path, output_path, region_or_regions, video_info, cancel_event=None, progress_callback=None):
    """Seamless Pro Multi-Threaded Pipeline with Multi-Region Support."""
    ensure_ffmpeg()
    if INPAINT_ENGINE in ["seamless_pro", "lama"]:
        get_lama_model()

    norm_regions = normalize_regions(region_or_regions)
    if not norm_regions:
        return False

    width = video_info["width"]
    height = video_info["height"]
    fps = video_info["fps"]
    total_frames = video_info["total_frames"] or 100
    res_scale = max(width, height) / 1080.0

    region_data = []
    for (x, y, rw, rh) in norm_regions:
        context_pad = int(max(20, min(max(rw, rh) * 0.4, 60 * res_scale)))
        roi_y1 = max(0, y - context_pad)
        roi_y2 = min(height, y + rh + context_pad)
        roi_x1 = max(0, x - context_pad)
        roi_x2 = min(width, x + rw + context_pad)
        rel_x = x - roi_x1
        rel_y = y - roi_y1
        rh_box = roi_y2 - roi_y1
        rw_box = roi_x2 - roi_x1
        mask = np.zeros((rh_box, rw_box), dtype=np.uint8)
        mask[rel_y:rel_y+rh, rel_x:rel_x+rw] = 255
        region_data.append({
            "bounds": (roi_x1, roi_y1, roi_x2, roi_y2),
            "mask": mask
        })

    ffmpeg_bin = ensure_ffmpeg()
    ffmpeg_cmd = [
        ffmpeg_bin, "-y", "-loglevel", "error",
        "-f", "rawvideo", "-pix_fmt", "bgr24",
        "-s", f"{width}x{height}", "-r", str(fps),
        "-i", "pipe:0", "-i", str(input_path),
        "-map", "0:v:0",
    ]

    if video_info.get("has_audio", True):
        ffmpeg_cmd += ["-map", "1:a?", "-c:a", "copy"]
    ffmpeg_cmd += ["-map", "1:s?", "-c:s", "copy"]
    ffmpeg_cmd += _build_ffmpeg_video_args(video_info)
    ffmpeg_cmd.append(str(output_path))

    proc = subprocess.Popen(ffmpeg_cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    cap = cv2.VideoCapture(str(input_path))
    start_time = time.time()
    frames_processed = 0

    batch_frames = []

    while True:
        if cancel_event and cancel_event.is_set():
            break

        ret, frame = cap.read()
        if not ret:
            break

        batch_frames.append(frame)

        if len(batch_frames) == BATCH_SIZE:
            for r_info in region_data:
                rx1, ry1, rx2, ry2 = r_info["bounds"]
                crops = [f[ry1:ry2, rx1:rx2].copy() for f in batch_frames]
                inpainted = inpaint_roi_batch(crops, r_info["mask"])
                for f, in_crop in zip(batch_frames, inpainted):
                    f[ry1:ry2, rx1:rx2] = in_crop

            for f in batch_frames:
                proc.stdin.write(f.tobytes())
                frames_processed += 1
                if progress_callback:
                    progress_callback(frames_processed, total_frames, start_time)

            batch_frames = []

    if batch_frames:
        for r_info in region_data:
            rx1, ry1, rx2, ry2 = r_info["bounds"]
            crops = [f[ry1:ry2, rx1:rx2].copy() for f in batch_frames]
            inpainted = inpaint_roi_batch(crops, r_info["mask"])
            for f, in_crop in zip(batch_frames, inpainted):
                f[ry1:ry2, rx1:rx2] = in_crop

        for f in batch_frames:
            proc.stdin.write(f.tobytes())
            frames_processed += 1
            if progress_callback:
                progress_callback(frames_processed, total_frames, start_time)

    cap.release()
    if proc.stdin:
        proc.stdin.close()
    proc.wait()

    return proc.returncode == 0


def process_video(input_path, output_path, region_or_regions, video_info, cancel_event=None, progress_callback=None):
    """Main Video Processing Orchestrator."""
    if INPAINT_ENGINE in ["fast", "fast_v1", "fast_v2"]:
        return process_video_native_v2(input_path, output_path, region_or_regions, video_info, cancel_event, progress_callback)
    return process_video_advanced(input_path, output_path, region_or_regions, video_info, cancel_event, progress_callback)
