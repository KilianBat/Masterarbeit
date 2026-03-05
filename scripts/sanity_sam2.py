from pathlib import Path
import os
import cv2
import numpy as np
import torch

from sam2.build_sam import build_sam2
from sam2.sam2_image_predictor import SAM2ImagePredictor


ROOT = Path(__file__).resolve().parents[1]  # .../Masterarbeit
SAM2_REPO = ROOT / "third_party" / "sam2_repo"

# 1) checkpoint wählen (falls du mehrere hast)
ckpt = SAM2_REPO / "checkpoints" / "sam2.1_hiera_large.pt"
assert ckpt.exists(), f"Checkpoint not found: {ckpt}"

# 2) config finden (wir suchen automatisch eine passende)
cfg = "configs/sam2.1/sam2.1_hiera_l.yaml"

print("Using checkpoint:", ckpt)
print("Using config:", cfg)

# 3) Beispielbild (nutze ein Bild aus sam2/assets)
asset_imgs = list((SAM2_REPO / "assets").glob("*.jpg")) + list((SAM2_REPO / "assets").glob("*.png"))
assert len(asset_imgs) > 0, f"No images found in {SAM2_REPO / 'assets'}"
img_path = asset_imgs[0]
print("Using image:", img_path)

image_bgr = cv2.imread(str(img_path))
assert image_bgr is not None, f"Could not read image: {img_path}"
image_rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
h, w = image_rgb.shape[:2]

# 4) Dummy-Box in der Bildmitte
box = np.array([w*0.25, h*0.25, w*0.75, h*0.75], dtype=np.float32)

# 5) Modell bauen
device = "cuda" if torch.cuda.is_available() else "cpu"
model = build_sam2(cfg, str(ckpt), device=device)
predictor = SAM2ImagePredictor(model)

# 6) Inference
with torch.inference_mode():
    if device == "cuda":
        with torch.autocast("cuda", dtype=torch.bfloat16):
            predictor.set_image(image_rgb)
            masks, scores, _ = predictor.predict(box=box)
    else:
        predictor.set_image(image_rgb)
        masks, scores, _ = predictor.predict(box=box)

print("OK - masks:", masks.shape, "scores:", scores[:5])