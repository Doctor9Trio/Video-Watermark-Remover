"""Core utilities package."""

from .hardware import get_hardware_info, ensure_ffmpeg, ensure_ffprobe
from .fusion import (
    apply_boundary_fusion,
    match_color_lab,
    add_matching_film_grain,
    refine_watermark_mask
)

__all__ = [
    "get_hardware_info",
    "ensure_ffmpeg",
    "ensure_ffprobe",
    "apply_boundary_fusion",
    "match_color_lab",
    "add_matching_film_grain",
    "refine_watermark_mask",
]
