"""
High-Performance Media Inpainting Core Engine (v7.0 Pro Edition).
Features:
- Flawless Zero-Bleed AI Neural Inpainting (LaMa GPU accelerated)
- Precise Boundary-Aware Feathering (No ghosting or edge halos)
- Reinhard CIE-L*a*b* Color Calibration
- Optical Moving Watermark Tracker (cv2.TrackerKCF / CSRT)
- High-Performance FFmpeg Multi-Threaded Video Pipeline
"""

import os
import sys
import time
import json
import subprocess
import shutil
import re
import queue
import threading
from collections import deque
from pathlib import Path

import cv2
import numpy as np

# Global Parameters
INPAINT_ENGINE = "seamless_pro"   # "seamless_pro", "fast", "clone", "blur", "opencv"
TRACKING_MODE = False
COLOR_MATCH = True
ADD_GRAIN = True
CRF_QUALITY = 16
PRESET = "slow"
CODEC = "libx264"
BATCH_SIZE = 4
TEMPORAL_WINDOW = 3
MASK_PADDING = 8
DEFAULT_INPAINT_RADIUS = 5
INPAINT_METHOD = cv2.INPAINT_TELEA

_lama_model = None
_device_info = None


def get_ffmpeg_bin():
    """Locate standalone or system FFmpeg binary."""
    try:
        import imageio_ffmpeg
        exe = imageio_ffmpeg.get_ffmpeg_exe()
        if exe and os.path.exists(exe):
            return exe
    except Exception:
        pass
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    return "ffmpeg"


def ensure_ffmpeg():
    """Verify FFmpeg binaries are available."""
    bin_path = get_ffmpeg_bin()
    if bin_path == "ffmpeg" and not shutil.which("ffmpeg"):
        raise RuntimeError("FFmpeg binary could not be found.")
    return bin_path


def get_hardware_info():
    """Detect available GPU accelerator."""
    global _device_info
    if _device_info is not None:
        return _device_info

    info = {
        "has_cuda": False,
        "gpu_name": "CPU Native (Single Core / Multi-Thread)",
        "device": "cpu",
        "vram_gb": 0.0
    }
    try:
        import torch
        if torch.cuda.is_available():
            info["has_cuda"] = True
            info["gpu_name"] = torch.cuda.get_device_name(0)
            info["device"] = "cuda"
            info["vram_gb"] = round(torch.cuda.get_device_properties(0).total_memory / (1024**3), 1)
    except Exception:
        pass

    _device_info = info
    return info


def get_lama_model():
    """Lazy-load the LaMa model on GPU if available."""
    global _lama_model
    if _lama_model is None:
        try:
            from simple_lama_inpainting import SimpleLama
            hw = get_hardware_info()
            import torch
            device = torch.device(hw["device"])
            print(f"  Loading LaMa AI model on [{hw['gpu_name']}]...")
            _lama_model = SimpleLama(device=device)
            print("  LaMa model ready!")
        except Exception as e:
            print(f"  LaMa loading fallback: {e}")
            _lama_model = False

    return _lama_model if _lama_model is not False else None


# ──────────────────────────────────────────────
#  PRECISE COLOR & FUSION UTILITIES
# ──────────────────────────────────────────────
def match_color_lab(source_patch, target_context, mask_binary):
    """Reinhard LAB Color Calibration (matches background tone perfectly)."""
    clean_mask = (mask_binary == 0)
    if not np.any(clean_mask):
        return source_patch

    try:
        s_lab = cv2.cvtColor(source_patch, cv2.COLOR_BGR2LAB).astype(np.float32)
        t_lab = cv2.cvtColor(target_context, cv2.COLOR_BGR2LAB).astype(np.float32)

        for i in range(3):
            clean_target_pixels = t_lab[:, :, i][clean_mask]
            if len(clean_target_pixels) < 10:
                continue

            t_mean = float(np.mean(clean_target_pixels))
            t_std = float(np.std(clean_target_pixels)) + 1e-4

            s_pixels = s_lab[:, :, i]
            s_mean = float(np.mean(s_pixels))
            s_std = float(np.std(s_pixels)) + 1e-4

            s_lab[:, :, i] = (s_lab[:, :, i] - s_mean) * (t_std / s_std) + t_mean

        calibrated = cv2.cvtColor(np.clip(s_lab, 0, 255).astype(np.uint8), cv2.COLOR_LAB2BGR)
        return calibrated
    except Exception:
        return source_patch


def add_matching_film_grain(patch, context, mask_binary):
    """Adaptive Micro-Grain Synthesis."""
    clean_mask = (mask_binary == 0)
    if not np.any(clean_mask):
        return patch

    try:
        gray_ctx = cv2.cvtColor(context, cv2.COLOR_BGR2GRAY)
        laplacian = cv2.Laplacian(gray_ctx, cv2.CV_64F)
        clean_noise = laplacian[clean_mask]
        sigma = float(np.std(clean_noise)) * 0.25
        sigma = max(0.2, min(4.0, sigma))

        noise = np.random.normal(0, sigma, patch.shape).astype(np.float32)
        grain_patch = np.clip(patch.astype(np.float32) + noise, 0, 255).astype(np.uint8)
        return grain_patch
    except Exception:
        return patch


def apply_boundary_fusion(inpainted_roi, original_roi, mask_binary):
    """
    Zero-Bleed Boundary Fusion:
    Ensures the watermark region is 100% completely replaced by inpainting,
    with smooth anti-aliased blending strictly outside the watermark boundary.
    """
    try:
        # Dilate mask so full watermark is 100% replaced
        dil_k = max(3, int(min(mask_binary.shape[:2]) * 0.03) | 1)
        core_mask = cv2.dilate((mask_binary > 127).astype(np.uint8) * 255, np.ones((dil_k, dil_k), np.uint8), iterations=1)

        # Outer feathering strictly outside core watermark
        feather_k = max(5, int(min(mask_binary.shape[:2]) * 0.08) | 1)
        weight = cv2.GaussianBlur(core_mask.astype(np.float32) / 255.0, (feather_k, feather_k), 0)
        weight = np.clip(weight * 1.25, 0.0, 1.0)[:, :, np.newaxis]

        fused = inpainted_roi.astype(np.float32) * weight + original_roi.astype(np.float32) * (1.0 - weight)
        return np.clip(fused, 0, 255).astype(np.uint8)
    except Exception:
        return inpainted_roi


# ──────────────────────────────────────────────
#  INPAINTING IMPLEMENTATIONS
# ──────────────────────────────────────────────
def lama_inpaint_batch(roi_bgr_list, roi_mask_binary, enable_color_match=True, enable_grain=True):
    """Batched GPU inpainting using LaMa deep neural network."""
    model_wrapper = get_lama_model()
    if model_wrapper is None:
        return [opencv_inpaint(img, roi_mask_binary) for img in roi_bgr_list]

    try:
        import torch
        h, w = roi_bgr_list[0].shape[:2]
        d_size = max(5, int(max(h, w) * 0.04) | 1)
        dilate_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (d_size, d_size))
        mask_clean = cv2.dilate((roi_mask_binary > 127).astype(np.uint8) * 255, dilate_kernel, iterations=1)

        pad_h = (8 - (h % 8)) % 8
        pad_w = (8 - (w % 8)) % 8

        batch_size = len(roi_bgr_list)
        imgs_rgb = []
        for img in roi_bgr_list:
            rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            if pad_h > 0 or pad_w > 0:
                rgb = np.pad(rgb, ((0, pad_h), (0, pad_w), (0, 0)), mode="edge")
            imgs_rgb.append(rgb)

        if pad_h > 0 or pad_w > 0:
            mask_padded = np.pad(mask_clean, ((0, pad_h), (0, pad_w)), mode="constant", constant_values=0)
        else:
            mask_padded = mask_clean

        imgs_np = np.stack(imgs_rgb, axis=0).astype(np.float32) / 255.0
        imgs_tensor = torch.from_numpy(imgs_np).permute(0, 3, 1, 2).contiguous()

        mask_np = (mask_padded > 127).astype(np.float32)
        mask_tensor = torch.from_numpy(mask_np).unsqueeze(0).unsqueeze(0).repeat(batch_size, 1, 1, 1).contiguous()

        device = model_wrapper.device
        imgs_tensor = imgs_tensor.to(device, non_blocking=True)
        mask_tensor = mask_tensor.to(device, non_blocking=True)

        with torch.inference_mode():
            out_tensor = model_wrapper.model(imgs_tensor, mask_tensor)
            out_np = out_tensor.permute(0, 2, 3, 1).detach().cpu().numpy()

        results_bgr = []
        for i in range(batch_size):
            res_rgb = np.clip(out_np[i, :h, :w] * 255.0, 0, 255).astype(np.uint8)
            res_bgr = cv2.cvtColor(res_rgb, cv2.COLOR_RGB2BGR)

            if enable_color_match:
                res_bgr = match_color_lab(res_bgr, roi_bgr_list[i], roi_mask_binary)

            if enable_grain:
                res_bgr = add_matching_film_grain(res_bgr, roi_bgr_list[i], roi_mask_binary)

            res_bgr = apply_boundary_fusion(res_bgr, roi_bgr_list[i], roi_mask_binary)
            results_bgr.append(res_bgr)

        return results_bgr
    except Exception as e:
        print(f"LaMa inpaint fallback: {e}")
        return [opencv_inpaint(img, roi_mask_binary) for img in roi_bgr_list]


def opencv_inpaint(roi_bgr, roi_mask_uint8):
    """Classical Multi-Stage Navier-Stokes / Telea Inpainting."""
    d_size = max(3, int(max(roi_bgr.shape[:2]) * 0.03) | 1)
    mask_bin = cv2.dilate((roi_mask_uint8 > 127).astype(np.uint8) * 255, np.ones((d_size, d_size), np.uint8), iterations=1)

    inpainted_telea = cv2.inpaint(roi_bgr, mask_bin, DEFAULT_INPAINT_RADIUS, cv2.INPAINT_TELEA)
    inpainted_ns = cv2.inpaint(roi_bgr, mask_bin, DEFAULT_INPAINT_RADIUS, cv2.INPAINT_NS)
    inpainted = cv2.addWeighted(inpainted_telea, 0.6, inpainted_ns, 0.4, 0)

    calibrated = match_color_lab(inpainted, roi_bgr, roi_mask_uint8)
    return apply_boundary_fusion(calibrated, roi_bgr, roi_mask_uint8)


def inpaint_roi_batch(roi_bgr_list, roi_mask_binary):
    """Inpaint a batch of cropped watermark regions."""
    if INPAINT_ENGINE in ["seamless_pro", "lama"]:
        return lama_inpaint_batch(roi_bgr_list, roi_mask_binary, enable_color_match=COLOR_MATCH, enable_grain=ADD_GRAIN)
    return [opencv_inpaint(roi, roi_mask_binary) for roi in roi_bgr_list]


# ──────────────────────────────────────────────
#  IMAGE STUDIO INPAINTING
# ──────────────────────────────────────────────
def process_image(input_path, output_path, region, progress_callback=None):
    """Inpaint single image preserving full resolution and color fidelity."""
    input_path = Path(input_path).resolve()
    output_path = Path(output_path).resolve()

    img = cv2.imread(str(input_path))
    if img is None:
        return False

    h, w = img.shape[:2]
    x, y, rw, rh = region

    context_pad = int(max(max(rw, rh) * 2.2, 80))
    roi_y1 = max(0, y - context_pad)
    roi_y2 = min(h, y + rh + context_pad)
    roi_x1 = max(0, x - context_pad)
    roi_x2 = min(w, x + rw + context_pad)

    roi_crop = img[roi_y1:roi_y2, roi_x1:roi_x2].copy()
    roi_mask = np.zeros((roi_y2 - roi_y1, roi_x2 - roi_x1), dtype=np.uint8)
    roi_mask[y - roi_y1:y - roi_y1 + rh, x - roi_x1:x - roi_x1 + rw] = 255

    inpainted_roi = inpaint_roi_batch([roi_crop], roi_mask)[0]

    result = img.copy()
    result[roi_y1:roi_y2, roi_x1:roi_x2] = inpainted_roi

    ext = output_path.suffix.lower()
    if ext in [".jpg", ".jpeg"]:
        cv2.imwrite(str(output_path), result, [int(cv2.IMWRITE_JPEG_QUALITY), 99])
    elif ext == ".png":
        cv2.imwrite(str(output_path), result, [int(cv2.IMWRITE_PNG_COMPRESSION), 1])
    elif ext == ".webp":
        cv2.imwrite(str(output_path), result, [int(cv2.IMWRITE_WEBP_QUALITY), 99])
    else:
        cv2.imwrite(str(output_path), result)

    if progress_callback:
        progress_callback(1, 1, time.time())

    return True


# ──────────────────────────────────────────────
#  VIDEO INPAINTING ENGINE
# ──────────────────────────────────────────────
def process_video(input_path, output_path, region, video_info, cancel_event=None, progress_callback=None):
    """Main video dispatcher."""
    if TRACKING_MODE:
        return process_video_dynamic_tracking(input_path, output_path, region, video_info, cancel_event, progress_callback)
    elif INPAINT_ENGINE == "fast":
        return process_video_native_fast(input_path, output_path, region, video_info, cancel_event, progress_callback)
    else:
        return process_video_advanced(input_path, output_path, region, video_info, cancel_event, progress_callback)


def process_video_dynamic_tracking(input_path, output_path, initial_region, video_info, cancel_event=None, progress_callback=None):
    """Real-Time Object Tracking Pipeline."""
    ffmpeg_bin = ensure_ffmpeg()
    input_path = Path(input_path).resolve()
    output_path = Path(output_path).resolve()

    width = video_info["width"]
    height = video_info["height"]
    fps = video_info["fps"]
    total_frames = video_info["total_frames"] or 100

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
    ffmpeg_cmd += ["-c:v", "libx264", "-crf", str(CRF_QUALITY), "-preset", PRESET, "-pix_fmt", "yuv420p", "-movflags", "+faststart"]
    ffmpeg_cmd.append(str(output_path))

    proc = subprocess.Popen(ffmpeg_cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    cap = cv2.VideoCapture(str(input_path))
    ret, first_frame = cap.read()
    if not ret:
        cap.release()
        return False

    tracker = cv2.TrackerKCF_create() if hasattr(cv2, "TrackerKCF_create") else cv2.TrackerCSRT_create()
    x, y, rw, rh = initial_region
    tracker.init(first_frame, (x, y, rw, rh))

    start_time = time.time()
    frames_processed = 0
    curr_box = (x, y, rw, rh)
    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)

    while True:
        if cancel_event and cancel_event.is_set():
            break
        ret, frame = cap.read()
        if not ret:
            break

        ok, tracked_box = tracker.update(frame)
        if ok:
            tx, ty, tw, th = [int(v) for v in tracked_box]
            curr_box = (max(0, tx), max(0, ty), min(width - tx, tw), min(height - ty, th))

        bx, by, bw, bh = curr_box
        if bw > 5 and bh > 5:
            pad = int(max(max(bw, bh) * 1.5, 30))
            y1 = max(0, by - pad)
            y2 = min(height, by + bh + pad)
            x1 = max(0, bx - pad)
            x2 = min(width, bx + bw + pad)

            roi_crop = frame[y1:y2, x1:x2].copy()
            roi_mask = np.zeros((y2 - y1, x2 - x1), dtype=np.uint8)
            roi_mask[by - y1:by - y1 + bh, bx - x1:bx - x1 + bw] = 255

            inpainted_roi = inpaint_roi_batch([roi_crop], roi_mask)[0]
            frame[y1:y2, x1:x2] = inpainted_roi

        proc.stdin.write(frame.tobytes())
        frames_processed += 1

        if progress_callback:
            progress_callback(frames_processed, total_frames, start_time)

    cap.release()
    if proc.stdin:
        proc.stdin.close()
    proc.wait()

    return proc.returncode == 0


def process_video_native_fast(input_path, output_path, region, video_info, cancel_event=None, progress_callback=None):
    """Ultra-Fast Hardware Native Inpaint."""
    ffmpeg_bin = ensure_ffmpeg()
    x, y, rw, rh = region
    total_frames = video_info.get("total_frames")
    vf_filter = f"delogo=x={x}:y={y}:w={rw}:h={rh}"

    ffmpeg_cmd = [
        ffmpeg_bin, "-y",
        "-i", str(input_path),
        "-vf", vf_filter,
        "-map", "0:v:0",
    ]
    if video_info.get("has_audio", True):
        ffmpeg_cmd += ["-map", "0:a?", "-c:a", "copy"]
    ffmpeg_cmd += ["-map", "0:s?", "-c:s", "copy"]
    ffmpeg_cmd += ["-c:v", "libx264", "-crf", str(CRF_QUALITY), "-preset", PRESET, "-pix_fmt", "yuv420p", "-movflags", "+faststart"]
    ffmpeg_cmd.append(str(output_path))

    start_time = time.time()
    proc = subprocess.Popen(ffmpeg_cmd, stderr=subprocess.PIPE, universal_newlines=True)
    frame_pattern = re.compile(r"frame=\s*(\d+)")

    try:
        for line in proc.stderr:
            if cancel_event and cancel_event.is_set():
                proc.kill()
                return False
            match = frame_pattern.search(line)
            if match:
                current_frame = int(match.group(1))
                if progress_callback:
                    progress_callback(current_frame, total_frames, start_time)
        proc.wait()
    finally:
        if proc.poll() is None:
            proc.kill()

    return proc.returncode == 0


def process_video_advanced(input_path, output_path, region, video_info, cancel_event=None, progress_callback=None):
    """Seamless Pro Multi-Threaded Pipeline."""
    ensure_ffmpeg()
    if INPAINT_ENGINE in ["seamless_pro", "lama"]:
        get_lama_model()

    width = video_info["width"]
    height = video_info["height"]
    fps = video_info["fps"]
    total_frames = video_info["total_frames"] or 100
    res_scale = max(width, height) / 1080.0

    x, y, rw, rh = region
    context_pad = int(max(max(rw, rh) * 2.2, 90 * res_scale))

    roi_y1 = max(0, y - context_pad)
    roi_y2 = min(height, y + rh + context_pad)
    roi_x1 = max(0, x - context_pad)
    roi_x2 = min(width, x + rw + context_pad)

    rel_x = x - roi_x1
    rel_y = y - roi_y1
    roi_h = roi_y2 - roi_y1
    roi_w = roi_x2 - roi_x1

    roi_mask_binary = np.zeros((roi_h, roi_w), dtype=np.uint8)
    roi_mask_binary[rel_y:rel_y+rh, rel_x:rel_x+rw] = 255

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
    ffmpeg_cmd += ["-c:v", "libx264", "-crf", str(CRF_QUALITY), "-preset", PRESET, "-pix_fmt", "yuv420p", "-movflags", "+faststart"]
    ffmpeg_cmd.append(str(output_path))

    proc = subprocess.Popen(ffmpeg_cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    cap = cv2.VideoCapture(str(input_path))
    start_time = time.time()
    frames_processed = 0

    batch_frames = []
    batch_rois = []

    while True:
        if cancel_event and cancel_event.is_set():
            break

        ret, frame = cap.read()
        if not ret:
            break

        roi = frame[roi_y1:roi_y2, roi_x1:roi_x2].copy()
        batch_frames.append(frame)
        batch_rois.append(roi)

        if len(batch_frames) == BATCH_SIZE:
            inpainted_rois = inpaint_roi_batch(batch_rois, roi_mask_binary)
            for f, in_roi in zip(batch_frames, inpainted_rois):
                f[roi_y1:roi_y2, roi_x1:roi_x2] = in_roi
                proc.stdin.write(f.tobytes())
                frames_processed += 1
                if progress_callback:
                    progress_callback(frames_processed, total_frames, start_time)

            batch_frames = []
            batch_rois = []

    if batch_frames:
        inpainted_rois = inpaint_roi_batch(batch_rois, roi_mask_binary)
        for f, in_roi in zip(batch_frames, inpainted_rois):
            f[roi_y1:roi_y2, roi_x1:roi_x2] = in_roi
            proc.stdin.write(f.tobytes())
            frames_processed += 1
            if progress_callback:
                progress_callback(frames_processed, total_frames, start_time)

    cap.release()
    if proc.stdin:
        proc.stdin.close()
    proc.wait()

    return proc.returncode == 0


def get_video_info(path):
    """Extract metadata preserving formats, codecs, and color tags."""
    try:
        cmd = [
            "ffprobe", "-v", "quiet",
            "-print_format", "json",
            "-show_format", "-show_streams",
            str(path)
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        info = json.loads(result.stdout)
        video_stream = next(s for s in info["streams"] if s["codec_type"] == "video")
        audio_streams = [s for s in info["streams"] if s["codec_type"] == "audio"]

        fps = 30.0
        fps_str = video_stream.get("avg_frame_rate") or video_stream.get("r_frame_rate") or "30/1"
        if "/" in fps_str:
            num, den = fps_str.split("/")
            if float(den) > 0:
                fps = float(num) / float(den)
        else:
            fps = float(fps_str)

        duration = float(info["format"].get("duration") or video_stream.get("duration") or 0.0)
        total_frames = int(video_stream.get("nb_frames") or 0)
        if total_frames == 0 and duration > 0:
            total_frames = int(round(duration * fps))

        return {
            "width": int(video_stream["width"]),
            "height": int(video_stream["height"]),
            "fps": fps,
            "fps_str": fps_str,
            "duration": duration,
            "total_frames": total_frames if total_frames > 0 else None,
            "has_audio": len(audio_streams) > 0,
            "audio_count": len(audio_streams),
            "codec": video_stream.get("codec_name", "unknown"),
            "pix_fmt": video_stream.get("pix_fmt", "yuv420p"),
        }
    except Exception:
        cap = cv2.VideoCapture(str(path))
        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or None
        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        dur = frames / fps if (frames and fps) else 0.0
        cap.release()
        return {
            "width": w,
            "height": h,
            "fps": fps,
            "fps_str": f"{fps:.2f}",
            "duration": dur,
            "total_frames": frames,
            "has_audio": True,
            "audio_count": 1,
            "codec": "unknown",
            "pix_fmt": "yuv420p",
        }


def format_time(seconds):
    """Format seconds into HH:MM:SS."""
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def auto_detect_logo(frame):
    """Detect watermark logo in video corners."""
    h, w = frame.shape[:2]
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    margin_x, margin_y = int(w * 0.28), int(h * 0.28)
    corners = {
        "top-left":     (0, 0, margin_x, margin_y),
        "top-right":    (w - margin_x, 0, w, margin_y),
        "bottom-left":  (0, h - margin_y, margin_x, h),
        "bottom-right": (w - margin_x, h - margin_y, w, h),
    }

    scale = max(w, h) / 1080.0
    min_area = int(100 * scale * scale)
    max_area = int(margin_x * margin_y * 0.45)

    best_region = None
    best_score = 0

    for _, (x1, y1, x2, y2) in corners.items():
        roi = gray[y1:y2, x1:x2]
        thresh = cv2.adaptiveThreshold(
            roi, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY_INV, max(15, int(21 * scale) | 1), 10
        )
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            continue

        for cnt in contours:
            bx, by, bw, bh = cv2.boundingRect(cnt)
            area = bw * bh
            if area < min_area or area > max_area:
                continue

            aspect = bw / max(bh, 1)
            if 1.2 < aspect < 9.0:
                density = cv2.countNonZero(thresh[by:by+bh, bx:bx+bw]) / max(area, 1)
                score = density * area
                if score > best_score:
                    best_score = score
                    best_region = (x1 + bx, y1 + by, bw, bh)

    if best_region:
        x, y, rw, rh = best_region
        pad = int(max(MASK_PADDING * scale, 15))
        x = max(0, x - pad)
        y = max(0, y - pad)
        rw = min(w - x, rw + pad * 2)
        rh = min(h - y, rh + pad * 2)
        return (x, y, rw, rh)

    return None


LOGO_PRESETS = {
    "gemini": {
        "name": "Google Gemini Sparkle",
        "get_roi": lambda w, h: (int(w * 0.78), int(h * 0.04), int(w * 0.18), int(h * 0.12))
    },
    "notebooklm": {
        "name": "NotebookLM Badge",
        "get_roi": lambda w, h: (int(w * 0.04), int(h * 0.04), int(w * 0.22), int(h * 0.09))
    },
    "tiktok": {
        "name": "TikTok Watermark",
        "get_roi": lambda w, h: (int(w * 0.05), int(h * 0.12), int(w * 0.24), int(h * 0.08))
    },
    "youtube": {
        "name": "YouTube Subscribe Bug",
        "get_roi": lambda w, h: (int(w * 0.82), int(h * 0.84), int(w * 0.15), int(h * 0.12))
    },
    "capcut": {
        "name": "CapCut Outro Stamp",
        "get_roi": lambda w, h: (int(w * 0.75), int(h * 0.05), int(w * 0.20), int(h * 0.08))
    },
    "bandicam": {
        "name": "Bandicam Top Header",
        "get_roi": lambda w, h: (int(w * 0.35), 0, int(w * 0.30), int(h * 0.06))
    }
}
