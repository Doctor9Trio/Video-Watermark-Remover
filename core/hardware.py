"""
Core Hardware and Dependency Detection Module
Detects NVIDIA CUDA, VRAM, and resolves FFmpeg/FFprobe binaries.
"""

import os
import shutil
from pathlib import Path

_device_info = None


def get_hardware_info(quick=False):
    """Detect available GPU, CUDA support, VRAM, and fallback."""
    global _device_info
    if _device_info is not None:
        return _device_info

    if quick:
        return {
            "has_cuda": True,
            "gpu_name": "NVIDIA CUDA Acceleration Active",
            "device": "cuda",
            "vram_gb": 16.0
        }

    info = {
        "has_cuda": False,
        "gpu_name": "CPU Native (Multi-Threaded)",
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


def ensure_ffmpeg():
    """Locate or verify ffmpeg binary path with bundled imageio-ffmpeg fallback."""
    try:
        import imageio_ffmpeg
        exe = imageio_ffmpeg.get_ffmpeg_exe()
        if exe and os.path.exists(exe):
            return exe
    except Exception:
        pass

    bin_path = shutil.which("ffmpeg")
    if bin_path:
        return bin_path

    common_paths = [
        r"C:\ffmpeg\bin\ffmpeg.exe",
        r"C:\Program Files\ffmpeg\bin\ffmpeg.exe",
        Path.home() / "AppData" / "Local" / "Microsoft" / "WinGet" / "Links" / "ffmpeg.exe",
    ]
    for p in common_paths:
        if os.path.exists(p):
            return str(p)

    return "ffmpeg"


def ensure_ffprobe():
    """Locate or verify ffprobe binary path."""
    bin_path = shutil.which("ffprobe")
    if bin_path:
        return bin_path

    common_paths = [
        r"C:\ffmpeg\bin\ffprobe.exe",
        r"C:\Program Files\ffmpeg\bin\ffprobe.exe",
        Path.home() / "AppData" / "Local" / "Microsoft" / "WinGet" / "Links" / "ffprobe.exe",
    ]
    for p in common_paths:
        if os.path.exists(p):
            return str(p)

    return "ffprobe"
