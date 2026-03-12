from pathlib import Path
import cv2
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
ds_dir = ROOT / "data" / "processed" / "isprs_mini"
df = pd.read_csv(ds_dir / "manifest.csv")

# Bild 9 Hier!!!
r = df.iloc[8]
img = cv2.imread(r["image_path"])
mask = cv2.imread(r["mask_path"], cv2.IMREAD_UNCHANGED)
if mask.ndim == 3:
    mask = mask[:,:,0]

u = np.unique(mask)
print("Unique label ids:", u)

out_dir = ROOT / "outputs" / "debug_labels"
out_dir.mkdir(parents=True, exist_ok=True)

for k in u:
    bin01 = (mask == k).astype(np.uint8)
    # overlay: highlight class pixels in green
    overlay = img.copy()
    overlay[bin01 == 1] = (0, 255, 0)
    cv2.imwrite(str(out_dir / f"overlay_class_{int(k)}.png"), overlay)

print("Wrote overlays to:", out_dir)
print("Open a few overlay_class_*.png and identify which id corresponds to buildings.")