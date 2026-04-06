from pathlib import Path
import pandas as pd
import numpy as np
import geopandas as gpd
import cv2
from rasterio.features import shapes
from rasterio.transform import from_bounds
from shapely import wkt
from shapely.geometry import shape
from shapely.ops import unary_union
import torch

from sam2.build_sam import build_sam2
from sam2.sam2_image_predictor import SAM2ImagePredictor

ROOT = Path(__file__).resolve().parents[1]
SAM2_REPO = ROOT / "third_party" / "sam2_repo"

manifest_path = ROOT / "data" / "processed" / "berlin_mvp" / "manifest.csv"
out_path = ROOT / "outputs" / "berlin_predictions.gpkg"

ckpt = SAM2_REPO / "checkpoints" / "sam2.1_hiera_large.pt"
cfg = "configs/sam2.1/sam2.1_hiera_l.yaml"

def mask_to_largest_polygon(mask01, transform):
    geoms = []
    for geom, val in shapes(mask01.astype(np.uint8), mask=mask01.astype(bool), transform=transform):
        if int(val) == 1:
            geoms.append(shape(geom))
    if not geoms:
        return None
    merged = unary_union(geoms)
    if merged.geom_type == "Polygon":
        return merged
    if merged.geom_type == "MultiPolygon":
        return max(merged.geoms, key=lambda g: g.area)
    return None

df = pd.read_csv(manifest_path)

device = "cuda" if torch.cuda.is_available() else "cpu"
model = build_sam2(cfg, str(ckpt), device=device)
predictor = SAM2ImagePredictor(model)

rows = []

for _, r in df.iterrows():
    orig_geom = wkt.loads(r["orig_wkt"])
    poly_px = wkt.loads(r["poly_px_wkt"])

    chip_bgr = cv2.imread(r["chip_path"])
    chip_rgb = cv2.cvtColor(chip_bgr, cv2.COLOR_BGR2RGB)
    h, w = chip_rgb.shape[:2]

    chip_transform = from_bounds(
        r["chip_left"], r["chip_bottom"], r["chip_right"], r["chip_top"], w, h
    )

    bbox = np.array(poly_px.bounds, dtype=np.float32)
    pt = np.array([[poly_px.centroid.x, poly_px.centroid.y]], dtype=np.float32)

    with torch.inference_mode():
        if device == "cuda":
            with torch.autocast("cuda", dtype=torch.bfloat16):
                predictor.set_image(chip_rgb)
                masks, scores, _ = predictor.predict(
                    box=bbox,
                    point_coords=pt,
                    point_labels=np.array([1], dtype=np.int32),
                )
        else:
            predictor.set_image(chip_rgb)
            masks, scores, _ = predictor.predict(
                box=bbox,
                point_coords=pt,
                point_labels=np.array([1], dtype=np.int32),
            )

    best = int(np.argmax(scores))
    pred_mask = (masks[best] > 0).astype(np.uint8)
    pred_geom = mask_to_largest_polygon(pred_mask, chip_transform)

    rows.append({
        "id": r["id"],
        "orig_wkt": orig_geom.wkt,
        "sam_score": float(scores[best]),
        "chip_path": r["chip_path"],
        "geometry": pred_geom,
    })

gdf = gpd.GeoDataFrame(rows, geometry="geometry", crs=df["chip_crs"].iloc[0])
out_path.parent.mkdir(parents=True, exist_ok=True)
gdf.to_file(out_path, layer="predictions", driver="GPKG")

print("Saved:", out_path)
print(gdf.head(3))