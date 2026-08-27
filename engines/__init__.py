"""
Inpainting Engines Package
Unified registry and batch dispatcher for all video & image watermark removal algorithms.
"""

from .seamless_pro import get_lama_model, lama_inpaint_batch
from .opencv_classical import opencv_inpaint
from .texture_clone import patch_clone_inpaint
from .frosted_blur import smart_blur_inpaint
from .fast_delogo import process_video_native_v2

# Engine Registry Map
ENGINE_REGISTRY = {
    "seamless_pro": "Seamless Pro (Best Quality Neural AI)",
    "lama": "Seamless Pro (Best Quality Neural AI)",
    "fast": "Ultra-Fast Native (1000 FPS Delogo)",
    "fast_v1": "Ultra-Fast Native (1000 FPS Delogo)",
    "fast_v2": "Ultra-Fast Native (1000 FPS Delogo)",
    "clone": "Smart Texture Clone (Nearby Patch)",
    "blur": "Smart Frosted Blur (Instant)",
    "opencv": "OpenCV Classical (Fast Fallback)",
}


def dispatch_inpaint_batch(roi_bgr_list, roi_mask_binary, engine="seamless_pro", color_match=False, blur_radius=25):
    """
    Unified Inpainting Batch Dispatcher.
    Dispatches a batch of cropped ROI frames to the requested engine.
    """
    if not roi_bgr_list:
        return []

    engine_clean = str(engine).lower()

    if engine_clean in ["seamless_pro", "lama"]:
        return lama_inpaint_batch(roi_bgr_list, roi_mask_binary)

    if engine_clean in ["fast", "fast_v1", "fast_v2", "opencv"]:
        return [opencv_inpaint(img, roi_mask_binary, color_match=color_match) for img in roi_bgr_list]

    if engine_clean == "clone":
        return [patch_clone_inpaint(img, roi_mask_binary, color_match=color_match) for img in roi_bgr_list]

    if engine_clean == "blur":
        return [smart_blur_inpaint(img, roi_mask_binary, blur_radius=blur_radius) for img in roi_bgr_list]

    # Default fallback to seamless_pro / opencv
    return lama_inpaint_batch(roi_bgr_list, roi_mask_binary)


__all__ = [
    "get_lama_model",
    "lama_inpaint_batch",
    "opencv_inpaint",
    "patch_clone_inpaint",
    "smart_blur_inpaint",
    "process_video_native_v2",
    "dispatch_inpaint_batch",
    "ENGINE_REGISTRY",
]
