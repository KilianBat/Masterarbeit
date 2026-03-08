from pathlib import Path
import cv2
import numpy as np
import pandas as pd
import torch
from tqdm import tqdm

from sam2.build_sam import build_sam2
from sam2.sam2_image_predictor import SAM2ImagePredictor

BUILDING_ID = 2  # confirmed

def bbox_from_mask(mask01: np.ndarray):
    ys, xs = np.where(mask01 > 0)
    if len(xs) == 0:
        return None
    return np.array([xs.min(), ys.min(), xs.max(), ys.max()], dtype=np.float32)

def centroid_point(mask01: np.ndarray):
    ys, xs = np.where(mask01 > 0)
    if len(xs) == 0:
        return None
    cx = float(xs.mean())
    cy = float(ys.mean())
    return np.array([[cx, cy]], dtype=np.float32)

def metrics(gt01, pr01):
    tp = np.logical_and(gt01 == 1, pr01 == 1).sum()
    fp = np.logical_and(gt01 == 0, pr01 == 1).sum()
    fn = np.logical_and(gt01 == 1, pr01 == 0).sum()
    union = tp + fp + fn
    iou = 0.0 if union == 0 else tp / union
    prec = 0.0 if (tp + fp) == 0 else tp / (tp + fp)
    rec  = 0.0 if (tp + fn) == 0 else tp / (tp + fn)
    f1   = 0.0 if (prec + rec) == 0 else 2 * prec * rec / (prec + rec)
    return float(iou), float(prec), float(rec), float(f1)

ROOT = Path(__file__).resolve().parents[1]
SAM2_REPO = ROOT / "third_party" / "sam2_repo"

ckpt = SAM2_REPO / "checkpoints" / "sam2.1_hiera_large.pt"
cfg  = "configs/sam2.1/sam2.1_hiera_l.yaml"

ds_dir = ROOT / "data" / "processed" / "isprs_mini"
df = pd.read_csv(ds_dir / "manifest.csv")

device = "cuda" if torch.cuda.is_available() else "cpu"
model = build_sam2(cfg, str(ckpt), device=device)
predictor = SAM2ImagePredictor(model)

rows = []
for _, r in tqdm(df.iterrows(), total=len(df)):
    img_bgr = cv2.imread(r["image_path"])
    img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)

    m = cv2.imread(r["mask_path"], cv2.IMREAD_UNCHANGED)
    if m.ndim == 3:
        m = m[:,:,0]
    gt01 = (m == BUILDING_ID).astype(np.uint8)

    box = bbox_from_mask(gt01)
    pt = centroid_point(gt01)

    if box is None or pt is None:
        rows.append({**r.to_dict(), "iou": 0.0, "precision": 0.0, "recall": 0.0, "f1": 0.0, "note": "no_building"})
        continue

    with torch.inference_mode():
        if device == "cuda":
            with torch.autocast("cuda", dtype=torch.bfloat16):
                predictor.set_image(img_rgb)
                masks, scores, _ = predictor.predict(
                    box=box,
                    point_coords=pt,
                    point_labels=np.array([1], dtype=np.int32),
                )
        else:
            predictor.set_image(img_rgb)
            masks, scores, _ = predictor.predict(
                box=box,
                point_coords=pt,
                point_labels=np.array([1], dtype=np.int32),
            )

    best = int(np.argmax(scores))
    pr01 = (masks[best] > 0).astype(np.uint8)

    iou, prec, rec, f1 = metrics(gt01, pr01)
    rows.append({**r.to_dict(), "iou": iou, "precision": prec, "recall": rec, "f1": f1, "note": ""})

out = pd.DataFrame(rows)
out_path = ROOT / "outputs" / "isprs_mini_metrics_boxpoint.csv"
out.to_csv(out_path, index=False)

print("Wrote:", out_path)
print(out[["iou","precision","recall","f1"]].describe())
print("no_building:", (out["note"] == "no_building").sum(), "/", len(out))