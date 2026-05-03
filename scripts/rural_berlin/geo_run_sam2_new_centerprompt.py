from pathlib import Path
import sys
import json
import math
import pandas as pd
import numpy as np
import geopandas as gpd
import cv2
from shapely import wkt
from shapely.geometry import shape
from shapely.ops import unary_union
from rasterio.features import shapes
from rasterio.transform import from_bounds
import torch

from sam2.build_sam import build_sam2
from sam2.sam2_image_predictor import SAM2ImagePredictor


def center_box(w, h, frac):
    bw = w * frac
    bh = h * frac
    cx, cy = w / 2.0, h / 2.0
    x1 = max(0.0, cx - bw / 2.0)
    y1 = max(0.0, cy - bh / 2.0)
    x2 = min(float(w - 1), cx + bw / 2.0)
    y2 = min(float(h - 1), cy + bh / 2.0)
    return np.array([x1, y1, x2, y2], dtype=np.float32)


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


def mask_centroid(mask01):
    ys, xs = np.where(mask01 > 0)
    if len(xs) == 0:
        return None
    return np.array([xs.mean(), ys.mean()], dtype=np.float32)


def rerank_new_masks(masks, scores, w, h, rerank_cfg):
    weights = rerank_cfg["weights"]
    min_area_frac = float(rerank_cfg["min_area_frac"])
    max_area_frac = float(rerank_cfg["max_area_frac"])

    img_area = float(w * h)
    center = np.array([w / 2.0, h / 2.0], dtype=np.float32)
    diag = math.sqrt(w * w + h * h)

    best_idx = None
    best_score = -1.0
    best_metrics = None

    for i in range(len(scores)):
        pred01 = (masks[i] > 0).astype(np.uint8)
        area = float(pred01.sum())
        if area <= 0:
            continue

        area_frac = area / img_area
        if area_frac < min_area_frac or area_frac > max_area_frac:
            area_reasonableness = 0.0
        else:
            mid = 0.5 * (min_area_frac + max_area_frac)
            span = max((max_area_frac - min_area_frac) / 2.0, 1e-6)
            area_reasonableness = max(0.0, 1.0 - abs(area_frac - mid) / span)

        c = mask_centroid(pred01)
        if c is None:
            centeredness = 0.0
        else:
            dist = np.linalg.norm(c - center)
            centeredness = max(0.0, 1.0 - dist / max(0.30 * diag, 1.0))

        ys, xs = np.where(pred01 > 0)
        if len(xs) == 0:
            compactness_proxy = 0.0
        else:
            bbox_area = float((xs.max() - xs.min() + 1) * (ys.max() - ys.min() + 1))
            compactness_proxy = area / max(bbox_area, 1.0)

        combined = (
            weights["sam_score"] * float(scores[i]) +
            weights["centeredness"] * centeredness +
            weights["area_reasonableness"] * area_reasonableness +
            weights["compactness_proxy"] * compactness_proxy
        )

        metrics = {
            "sam_score": float(scores[i]),
            "centeredness": float(centeredness),
            "area_reasonableness": float(area_reasonableness),
            "compactness_proxy": float(compactness_proxy),
            "combined": float(combined),
            "area_frac": float(area_frac),
        }

        if combined > best_score:
            best_score = combined
            best_idx = i
            best_metrics = metrics

    if best_idx is None:
        best_idx = int(np.argmax(scores))
        best_metrics = {
            "sam_score": float(scores[best_idx]),
            "centeredness": np.nan,
            "area_reasonableness": np.nan,
            "compactness_proxy": np.nan,
            "combined": float(scores[best_idx]),
            "area_frac": np.nan,
        }

    return best_idx, best_metrics


def main():
    if len(sys.argv) != 2:
        print("Usage: python scripts/geo_run_sam2_new_centerprompt.py <config.json>")
        sys.exit(1)

    ROOT = Path(__file__).resolve().parents[1]
    cfg = json.loads((ROOT / sys.argv[1]).read_text())

    exp_name = cfg["experiment_name"]
    manifest_path = ROOT / cfg["manifest_path"]
    ckpt = ROOT / cfg["checkpoint"]
    config_name = cfg["config_name"]

    out_dir = ROOT / "outputs" / exp_name
    out_dir.mkdir(parents=True, exist_ok=True)
    out_gpkg = out_dir / "new_predictions.gpkg"

    df = pd.read_csv(manifest_path)

    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = build_sam2(config_name, str(ckpt), device=device)
    predictor = SAM2ImagePredictor(model)

    rows = []

    for _, r in df.iterrows():
        cur_geom = wkt.loads(r["current_wkt"])

        chip_bgr = cv2.imread(r["chip_path"])
        chip_rgb = cv2.cvtColor(chip_bgr, cv2.COLOR_BGR2RGB)
        h, w = chip_rgb.shape[:2]

        chip_transform = from_bounds(
            r["chip_left"], r["chip_bottom"], r["chip_right"], r["chip_top"], w, h
        )

        point_coords = None
        point_labels = None
        box = None

        if cfg["center_prompt"]["use_center_point"]:
            point_coords = np.array([[w / 2.0, h / 2.0]], dtype=np.float32)
            point_labels = np.array([1], dtype=np.int32)

        if cfg["center_prompt"]["use_center_box"]:
            box = center_box(w, h, cfg["center_prompt"]["center_box_frac"])

        with torch.inference_mode():
            if device == "cuda":
                with torch.autocast("cuda", dtype=torch.bfloat16):
                    predictor.set_image(chip_rgb)
                    masks, scores, _ = predictor.predict(
                        box=box,
                        point_coords=point_coords,
                        point_labels=point_labels,
                    )
            else:
                predictor.set_image(chip_rgb)
                masks, scores, _ = predictor.predict(
                    box=box,
                    point_coords=point_coords,
                    point_labels=point_labels,
                )

        best_idx, best_metrics = rerank_new_masks(masks, scores, w, h, cfg["reranking"])
        pred_mask = (masks[best_idx] > 0).astype(np.uint8)
        pred_geom = mask_to_largest_polygon(pred_mask, chip_transform)

        rows.append({
            "id": r["id"],
            "current_osm_id": r.get("current_osm_id", None),
            "current_wkt": cur_geom.wkt,
            "sam_score": float(scores[best_idx]),
            "selected_mask_idx": int(best_idx),
            "rerank_combined": float(best_metrics["combined"]),
            "centeredness": float(best_metrics["centeredness"]) if not pd.isna(best_metrics["centeredness"]) else np.nan,
            "area_reasonableness": float(best_metrics["area_reasonableness"]) if not pd.isna(best_metrics["area_reasonableness"]) else np.nan,
            "compactness_proxy": float(best_metrics["compactness_proxy"]) if not pd.isna(best_metrics["compactness_proxy"]) else np.nan,
            "area_frac": float(best_metrics["area_frac"]) if not pd.isna(best_metrics["area_frac"]) else np.nan,
            "geometry": pred_geom,
        })

    gdf = gpd.GeoDataFrame(rows, geometry="geometry", crs=df["chip_crs"].iloc[0])
    gdf.to_file(out_gpkg, layer="predictions", driver="GPKG")
    (out_dir / "experiment_config.json").write_text(json.dumps(cfg, indent=2))

    print("Saved:", out_gpkg)
    print("Saved config copy:", out_dir / "experiment_config.json")
    print(gdf.head(5))

if __name__ == "__main__":
    main()