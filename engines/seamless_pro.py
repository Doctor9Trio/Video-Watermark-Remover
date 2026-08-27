"""
Seamless Pro Inpainting Engine (LaMa Deep Neural Network)
Uses Fast Fourier Convolutions (FFC) with NVIDIA TensorFloat-32 on GPU.
"""

import cv2
import numpy as np
from core.hardware import get_hardware_info
from core.fusion import apply_boundary_fusion

_lama_model = None


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


def lama_inpaint_batch(roi_bgr_list, roi_mask_binary, enable_color_match=False, enable_grain=False):
    """
    Adaptive Per-Frame Inpainting:
    - Pure monochrome solid canvases (ring_std < 1.5) get exact border fill with 0.00 color error.
    - All split dividing lines, shape boundaries, text strokes, floor textures, and gradients run through LaMa Deep Neural Network on GPU with TensorFloat-32.
    """
    if not roi_bgr_list:
        return []

    h, w = roi_bgr_list[0].shape[:2]
    mask_clean = (roi_mask_binary > 127).astype(np.uint8) * 255

    outer_k = cv2.getStructuringElement(cv2.MORPH_RECT, (7, 7))
    outer_ring = cv2.dilate(mask_clean, outer_k) - mask_clean

    results = [None] * len(roi_bgr_list)
    neural_indices = []

    for idx, img in enumerate(roi_bgr_list):
        ring_pixels = img[outer_ring > 0]

        if len(ring_pixels) >= 10:
            ring_std = float(np.max(np.std(ring_pixels, axis=0)))
        else:
            ring_std = 999.0

        # Strict monochrome gating (< 1.5): only 100% solid flat canvases
        if ring_std < 1.5:
            sampled_color = np.median(ring_pixels, axis=0).astype(np.uint8)
            out = img.copy()
            out[mask_clean > 0] = sampled_color
            alpha = cv2.GaussianBlur(mask_clean.astype(np.float32) / 255.0, (5, 5), 0)[:, :, np.newaxis]
            results[idx] = np.clip(out.astype(np.float32) * alpha + img.astype(np.float32) * (1.0 - alpha), 0, 255).astype(np.uint8)
        else:
            neural_indices.append(idx)

    if neural_indices:
        neural_rois = [roi_bgr_list[idx] for idx in neural_indices]
        model_wrapper = get_lama_model()
        if model_wrapper is None:
            # Fallback if PyTorch/LaMa unavailable
            from .opencv_classical import opencv_inpaint
            for idx in neural_indices:
                results[idx] = opencv_inpaint(roi_bgr_list[idx], mask_clean)
        else:
            try:
                import torch
                torch.backends.cuda.matmul.allow_tf32 = True
                torch.backends.cudnn.allow_tf32 = True

                pad_h = (8 - (h % 8)) % 8
                pad_w = (8 - (w % 8)) % 8

                n_batch = len(neural_rois)
                imgs_rgb = []
                for img in neural_rois:
                    rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                    if pad_h > 0 or pad_w > 0:
                        rgb = np.pad(rgb, ((0, pad_h), (0, pad_w), (0, 0)), mode="reflect")
                    imgs_rgb.append(rgb)

                if pad_h > 0 or pad_w > 0:
                    mask_padded = np.pad(mask_clean, ((0, pad_h), (0, pad_w)), mode="constant", constant_values=0)
                else:
                    mask_padded = mask_clean

                imgs_np = np.stack(imgs_rgb, axis=0).astype(np.float32) / 255.0
                imgs_tensor = torch.from_numpy(imgs_np).permute(0, 3, 1, 2).contiguous()

                mask_np = (mask_padded > 127).astype(np.float32)
                mask_tensor = torch.from_numpy(mask_np).unsqueeze(0).unsqueeze(0).repeat(n_batch, 1, 1, 1).contiguous()

                device = model_wrapper.device
                imgs_tensor = imgs_tensor.to(device, non_blocking=True)
                mask_tensor = mask_tensor.to(device, non_blocking=True)

                with torch.inference_mode():
                    out_tensor = model_wrapper.model(imgs_tensor, mask_tensor)
                    out_np = out_tensor.permute(0, 2, 3, 1).detach().cpu().numpy()

                for j, idx in enumerate(neural_indices):
                    res_rgb = np.clip(out_np[j, :h, :w] * 255.0, 0, 255).astype(np.uint8)
                    res_bgr = cv2.cvtColor(res_rgb, cv2.COLOR_RGB2BGR)
                    results[idx] = apply_boundary_fusion(res_bgr, roi_bgr_list[idx], mask_clean)
            except Exception as e:
                print(f"LaMa inpaint fallback: {e}")
                from .opencv_classical import opencv_inpaint
                for idx in neural_indices:
                    results[idx] = opencv_inpaint(roi_bgr_list[idx], mask_clean)

    return results
