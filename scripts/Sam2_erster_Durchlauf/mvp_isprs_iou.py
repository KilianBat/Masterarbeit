from pathlib import Path
import cv2
import numpy as np
import pandas as pd
import torch

from sam2.build_sam import build_sam2
from sam2.sam2_image_predictor import SAM2ImagePredictor


def bbox_from_mask(mask01: np.ndarray):
    ys, xs = np.where(mask01 > 0)
    if len(xs) == 0:
        return None
    return np.array([xs.min(), ys.min(), xs.max(), ys.max()], dtype=np.float32)


def iou_from_masks(a01: np.ndarray, b01: np.ndarray) -> float:
    inter = np.logical_and(a01, b01).sum()
    union = np.logical_or(a01, b01).sum()
    return 0.0 if union == 0 else float(inter) / float(union)


def load_mask_as_index_or_color(mask_path: str):
    """
    Returns:
      ("index", mask2d_uint8)  OR  ("color", mask_bgr_uint8)
    """
    m = cv2.imread(mask_path, cv2.IMREAD_UNCHANGED)
    if m is None:
        raise RuntimeError(f"Could not read mask: {mask_path}")

    # If 3-channel but actually grayscale replicated -> treat as index
    if m.ndim == 3:
        if np.all(m[:,:,0] == m[:,:,1]) and np.all(m[:,:,1] == m[:,:,2]):
            return "index", m[:,:,0]
        else:
            return "color", m
    else:
        return "index", m


def building_mask(mask_type, mask_data, building_id=1):
    """
    For color masks: building = BLUE in RGB => BGR(255,0,0)
    For index masks: building = class-id (default 1; adjust if needed)
    """
    if mask_type == "color":
        bgr = mask_data
        return ((bgr[:,:,0] == 255) & (bgr[:,:,1] == 0) & (bgr[:,:,2] == 0)).astype(np.uint8)
    else:
        idx = mask_data
        return (idx == building_id).astype(np.uint8)


ROOT = Path(__file__).resolve().parents[1]
SAM2_REPO = ROOT / "third_party" / "sam2_repo"

ckpt = SAM2_REPO / "checkpoints" / "sam2.1_hiera_large.pt"
cfg  = "configs/sam2.1/sam2.1_hiera_l.yaml"

ds_dir = ROOT / "data" / "processed" / "isprs_mini"
manifest = ds_dir / "manifest.csv"
df = pd.read_csv(manifest)

# --- Determine which mask style we have and what class ids exist ---
# Bild 9 Hier!!
first_mask = df.iloc[8]["mask_path"]
mtype, mdata = load_mask_as_index_or_color(first_mask)
print("Mask type detected:", mtype)

if mtype == "index":
    u = np.unique(mdata)
    print("Unique values in first mask:", u[:30], " ... total:", len(u))
    # Most ISPRS-style indexed datasets use building_id=1. If that yields empty, we'll try 2 automatically.
    candidate_building_ids = [int(x) for x in u]  # z.B. [1,2,3,4,5,6]
else:
    candidate_building_ids = [None]  # color-coded uses fixed blue

chosen = None
chosen_building_id = None

for _, r in df.iterrows():
    mtype, mdata = load_mask_as_index_or_color(r["mask_path"])

    if mtype == "color":
        b01 = building_mask("color", mdata)
        if b01.sum() > 0:
            chosen = r
            chosen_building_id = None
            break
    else:
        for bid in candidate_building_ids:
            b01 = building_mask("index", mdata, building_id=bid)
            if b01.sum() > 0:
                chosen = r
                chosen_building_id = bid
                break
        if chosen is not None:
            break

assert chosen is not None, "Still no building pixels found. Then the dataset label mapping differs—send the unique values output from Schritt 1."

# Load image + building GT
img_bgr = cv2.imread(chosen["image_path"])
img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)

mtype, mdata = load_mask_as_index_or_color(chosen["mask_path"])
gt01 = building_mask(mtype, mdata, building_id=chosen_building_id if chosen_building_id else 1)

box = bbox_from_mask(gt01)
assert box is not None

# SAM2
device = "cuda" if torch.cuda.is_available() else "cpu"
model = build_sam2(cfg, str(ckpt), device=device)
predictor = SAM2ImagePredictor(model)

with torch.inference_mode():
    if device == "cuda":
        with torch.autocast("cuda", dtype=torch.bfloat16):
            predictor.set_image(img_rgb)
            masks, scores, _ = predictor.predict(box=box)
    else:
        predictor.set_image(img_rgb)
        masks, scores, _ = predictor.predict(box=box)

best = int(np.argmax(scores))
pred01 = (masks[best] > 0).astype(np.uint8)

iou = iou_from_masks(gt01, pred01)
print(f"id={chosen['id']} building_id={chosen_building_id} best_score={scores[best]:.4f} IoU={iou:.4f}")