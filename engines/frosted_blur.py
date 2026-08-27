"""
Smart Frosted Blur Inpainting Engine
Bilateral filtering with edge-preserving diffusion strictly within the masked region.
"""

import cv2
import numpy as np
from core.fusion import apply_boundary_fusion

DEFAULT_BLUR_RADIUS = 25


def smart_blur_inpaint(roi_bgr, roi_mask_binary, blur_radius=None):
    """
    Edge-Preserving Frosted Blur Inpainting.
    Uses bilateral filtering and local diffusion strictly on the watermark-masked pixels,
    preserving background image sharpness without over-blurring.
    """
    r = DEFAULT_BLUR_RADIUS if blur_radius is None else blur_radius
    r = max(3, int(r) | 1)

    try:
        mask_clean = (roi_mask_binary > 127).astype(np.uint8) * 255

        # Edge-preserving bilateral filter + slight frosted blur
        bilateral = cv2.bilateralFilter(roi_bgr, d=r, sigmaColor=75, sigmaSpace=75)
        blurred = cv2.GaussianBlur(bilateral, (r, r), 0)

        return apply_boundary_fusion(blurred, roi_bgr, roi_mask_binary)
    except Exception:
        return roi_bgr
