"""
Smart Texture Clone Inpainting Engine
Samples clean background patches from surrounding adjacent coordinates and aligns them.
"""

import cv2
import numpy as np
from core.fusion import apply_boundary_fusion, match_color_lab
from .opencv_classical import opencv_inpaint


def patch_clone_inpaint(roi_bgr, roi_mask_binary, color_match=False):
    """
    Adaptive Texture Clone Inpainting:
    Samples clean background texture from the nearest adjacent clean area.
    """
    try:
        h, w = roi_bgr.shape[:2]
        mask_clean = (roi_mask_binary > 127).astype(np.uint8) * 255
        box_coords = np.where(mask_clean > 127)
        if len(box_coords[0]) == 0:
            return roi_bgr

        y_min, y_max = int(np.min(box_coords[0])), int(np.max(box_coords[0]))
        x_min, x_max = int(np.min(box_coords[1])), int(np.max(box_coords[1]))
        bw = x_max - x_min + 1
        bh = y_max - y_min + 1

        # Prefer sampling from nearby clean area
        if y_min >= bh:
            src_y1, src_y2 = y_min - bh, y_min
            src_x1, src_x2 = x_min, x_max
        elif (h - y_max - 1) >= bh:
            src_y1, src_y2 = y_max + 1, y_max + 1 + bh
            src_x1, src_x2 = x_min, x_max
        elif x_min >= bw:
            src_y1, src_y2 = y_min, y_max
            src_x1, src_x2 = x_min - bw, x_min
        elif (w - x_max - 1) >= bw:
            src_y1, src_y2 = y_min, y_max
            src_x1, src_x2 = x_max + 1, x_max + 1 + bw
        else:
            return opencv_inpaint(roi_bgr, roi_mask_binary)

        patch = roi_bgr[src_y1:src_y2+1, src_x1:src_x2+1]
        if patch.shape[:2] != (bh, bw):
            patch = cv2.resize(patch, (bw, bh), interpolation=cv2.INTER_LINEAR)

        cloned_roi = roi_bgr.copy()
        cloned_roi[y_min:y_max+1, x_min:x_max+1] = patch

        if color_match:
            cloned_roi = match_color_lab(cloned_roi, roi_bgr, roi_mask_binary)

        return apply_boundary_fusion(cloned_roi, roi_bgr, roi_mask_binary)
    except Exception:
        return opencv_inpaint(roi_bgr, roi_mask_binary)
