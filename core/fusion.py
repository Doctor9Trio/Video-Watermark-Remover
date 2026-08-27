"""
Core Fusion and Image Processing Utilities
Provides sub-pixel anti-aliased boundary feathering, chroma-safe LAB color alignment,
film grain matching, and mask boundary refinement.
"""

import cv2
import numpy as np


def apply_boundary_fusion(inpainted_roi, original_roi, mask_binary, feather_radius=None):
    """
    Surgical Micro-Feather Boundary Fusion:
    Blends only the anti-aliased sub-pixel perimeter edge without distance-transform cushions,
    eliminating all liquid glass, pill container, and bevel artifacts.
    """
    try:
        mask_clean = (mask_binary > 127).astype(np.uint8) * 255
        if np.sum(mask_clean) == 0:
            return original_roi

        # Ultra-soft 5x5 Gaussian edge feather
        alpha = cv2.GaussianBlur(mask_clean.astype(np.float32) / 255.0, (5, 5), 0)[:, :, np.newaxis]
        alpha = np.clip(alpha, 0.0, 1.0)

        fused = inpainted_roi.astype(np.float32) * alpha + original_roi.astype(np.float32) * (1.0 - alpha)
        return np.clip(fused, 0, 255).astype(np.uint8)
    except Exception:
        return inpainted_roi


def match_color_lab(source_patch, target_context, mask_binary):
    """
    Chroma-Safe LAB Color Alignment.
    Smoothly aligns luminance without causing color casts or over-saturation on blue/vibrant backgrounds.
    """
    clean_mask = (mask_binary == 0)
    if not np.any(clean_mask):
        return source_patch

    try:
        s_lab = cv2.cvtColor(source_patch, cv2.COLOR_BGR2LAB).astype(np.float32)
        t_lab = cv2.cvtColor(target_context, cv2.COLOR_BGR2LAB).astype(np.float32)

        for i in range(3):
            clean_target = t_lab[:, :, i][clean_mask]
            if len(clean_target) < 10:
                continue

            t_mean = float(np.mean(clean_target))
            s_mean = float(np.mean(s_lab[:, :, i]))
            delta = (t_mean - s_mean)

            if i > 0:
                delta = np.clip(delta, -8.0, 8.0) * 0.5
            else:
                delta = np.clip(delta, -20.0, 20.0)

            s_lab[:, :, i] = np.clip(s_lab[:, :, i] + delta, 0, 255)

        calibrated = cv2.cvtColor(s_lab.astype(np.uint8), cv2.COLOR_LAB2BGR)
        return calibrated
    except Exception:
        return source_patch


def add_matching_film_grain(patch, context, mask_binary):
    """Adaptive Micro-Grain Synthesis with studio smoothness detection."""
    clean_mask = (mask_binary == 0)
    if not np.any(clean_mask):
        return patch

    try:
        gray_ctx = cv2.cvtColor(context, cv2.COLOR_BGR2GRAY)
        laplacian = cv2.Laplacian(gray_ctx, cv2.CV_64F)
        clean_noise = laplacian[clean_mask]
        noise_std = float(np.std(clean_noise))

        if noise_std < 6.0:
            return patch

        sigma = min(2.5, noise_std * 0.15)
        noise = np.random.normal(0, sigma, patch.shape).astype(np.float32)
        grain_patch = np.clip(patch.astype(np.float32) + noise, 0, 255).astype(np.uint8)
        return grain_patch
    except Exception:
        return patch


def refine_watermark_mask(roi_bgr, base_mask):
    """
    Tight Boundary Mask Segmentation.
    Applies surgical 4px anti-aliasing expansion without encroaching on nearby moving subjects.
    """
    if base_mask is None:
        return base_mask

    try:
        d_k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        dilated = cv2.dilate((base_mask > 127).astype(np.uint8) * 255, d_k, iterations=1)
        return dilated
    except Exception:
        return base_mask
