import torch
import time
import watermark_remover as v

v.get_lama_model()
model = v._lama_model.model.to("cuda")

print(f"\nBenchmarking PyTorch LaMa on {torch.cuda.get_device_name(0)}:")
print("-" * 55)

for B in [1, 4, 8, 16, 32]:
    img = torch.zeros(B, 3, 256, 256, device="cuda")
    mask = torch.zeros(B, 1, 256, 256, device="cuda")
    mask[:, :, 50:150, 50:150] = 1.0

    with torch.inference_mode():
        # Warmup
        for _ in range(3):
            model(img, mask)
        torch.cuda.synchronize()

        t0 = time.time()
        for _ in range(10):
            model(img, mask)
        torch.cuda.synchronize()
        total_time = (time.time() - t0) / 10
        ms_per_frame = (total_time / B) * 1000
        fps = B / total_time
        print(f"Batch Size {B:2d}:  {total_time*1000:6.1f} ms/batch | {ms_per_frame:5.2f} ms/frame | {fps:6.1f} FPS")

print("-" * 55)
