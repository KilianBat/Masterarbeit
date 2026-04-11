from pathlib import Path
import sys
import json
import math
import pandas as pd
import numpy as np
import geopandas as gpd
import cv2
from shapely import wkt
from shapely.geometry import shape, Point
from shapely.ops import unary_union
from rasterio.features import shapes
from rasterio.transform import from_bounds
import torch

from sam2.build_sam import build_sam2
from sam2.sam2_image_predictor import SAM2ImagePredictor


def unique_points(points, ndigits=1):
    seen = set()
    out = []
    for x, y in points:
        key = (round(float(x), ndigits), round(float(y), ndigits))
        if key not in seen:
            seen.add(key)
            out.append((float(x), float(y)))
    return out


def greedy_spread_select(points, k):
    if len(points) <= k:
        return points

    selected = [points[0]]
    remaining = points[1:]

    while len(selected) < k and remaining:
        best_idx = None
        best_score = -1
        for i, p in enumerate(remaining):
            mind = min((p[0] - q[0]) ** 2 + (p[1] - q[1]) ** 2 for q in selected)
            if mind > best_score:
                best_score = mind
                best_idx = i
        selected.append(remaining.pop(best_idx))

    return selected


def sample_positive_points(poly, n_points, strategy="deep_inside"):
    poly = poly.buffer(0)
    if poly.is_empty:
        return []

    candidates = []

    rp = poly.representative_point()
    candidates.append((rp.x, rp.y, poly.boundary.distance(rp)))

    c = poly.centroid
    if poly.contains(c) or poly.touches(c):
        candidates.append((c.x, c.y, poly.boundary.distance(c)))

    minx, miny, maxx, maxy = poly.bounds

    if strategy == "deep_inside":
        xs = np.linspace(minx, maxx, 9)
        ys = np.linspace(miny, maxy, 9)

        for y in ys:
            for x in xs:
                p = Point(float(x), float(y))
                if poly.contains(p) or poly.touches(p):
                    d = poly.boundary.distance(p)
                    candidates.append((x, y, d))

        candidates = sorted(candidates, key=lambda t: t[2], reverse=True)
        pts = unique_points([(x, y) for x, y, _ in candidates])
        pts = greedy_spread_select(pts, n_points)
        return pts[:n_points]

    pts = unique_points([(x, y) for x, y, _ in candidates])
    return pts[:n_points]


def expand_bbox(bbox, pad_px, img_w, img_h):
    if bbox is None:
        return None
    x1, y1, x2, y2 = bbox
    x1 = max(0.0, x1 - pad_px)
    y1 = max(0.0, y1 - pad_px)
    x2 = min(float(img_w - 1), x2 + pad_px)
    y2 = min(float(img_h - 1), y2 + pad_px)
    return np.array([x1, y1, x2, y2], dtype=np.float32)


def polygon_to_mask(poly, h, w):
    mask = np.zeros((h, w), dtype=np.uint8)

    if poly.is_empty:
        return mask

    polys = [poly] if poly.geom_type == "Polygon" else list(poly.geoms)

    for p in polys:
        ext = np.round(np.array(p.exterior.coords)).astype(np.int32)
        cv2.fillPoly(mask, [ext], 1)
        for ring in p.interiors:
            hole = np.round(np.array(ring.coords)).astype(np.int32)
            cv2.fillPoly(mask, [hole], 0)

    return mask


def mask_bbox(mask01):
    ys, xs = np.where(mask01 > 0)
    if len(xs) == 0 or len(ys) == 0:
        return None
    return np.array([xs.min(), ys.min(), xs.max(), ys.max()], dtype=np.float32)


def bbox_iou(box_a, box_b):
    if box_a is None or box_b is None:
        return 0.0

    ax1, ay1, ax2, ay2 = box_a
    bx1, by1, bx2, by2 = box_b

    ix1 = max(ax1, bx1)
    iy1 = max(ay1, by1)
    ix2 = min(ax2, bx2)
    iy2 = min(ay2, by2)

    iw = max(0.0, ix2 - ix1)
    ih = max(0.0, iy2 - iy1)
    inter = iw * ih

    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    union = area_a + area_b - inter

    return 0.0 if union <= 0 else float(inter / union)


def binary_iou(mask_a, mask_b):
    inter = np.logical_and(mask_a > 0, mask_b > 0).sum()
    union = np.logical_or(mask_a > 0, mask_b > 0).sum()
    return 0.0 if union == 0 else float(inter / union)


def mask_centroid(mask01):
    ys, xs = np.where(mask01 > 0)
    if len(xs) == 0:
        return None
    return np.array([xs.mean(), ys.mean()], dtype=np.float32)


def rerank_masks(masks, scores, hist_mask, hist_bbox, hist_centroid, chip_diag, weights):
    hist_area = float(hist_mask.sum())
    best_idx = None
    best_combined = -1.0
    best_metrics = None

    for i in range(len(scores)):
        pred01 = (masks[i] > 0).astype(np.uint8)
        pred_area = float(pred01.sum())

        if pred_area <= 0:
            continue

        # 1) SAM score
        sam_score = float(scores[i])

        # 2) area consistency
        area_ratio = pred_area / max(hist_area, 1.0)
        area_consistency = max(0.0, 1.0 - abs(area_ratio - 1.0))

        # 3) bbox similarity
        pred_bbox = mask_bbox(pred01)
        bbox_score = bbox_iou(pred_bbox, hist_bbox)

        # 4) centroid consistency
        pred_centroid = mask_centroid(pred01)
        if pred_centroid is None or hist_centroid is None:
            centroid_score = 0.0
        else:
            dist = np.linalg.norm(pred_centroid - hist_centroid)
            centroid_score = max(0.0, 1.0 - dist / max(0.35 * chip_diag, 1.0))

        # 5) overlap to historical mask as weak regularizer
        hist_iou = binary_iou(pred01, hist_mask)

        combined = (
            weights["sam_score"] * sam_score +
            weights["area_consistency"] * area_consistency +
            weights["bbox_iou_hist"] * bbox_score +
            weights["centroid_consistency"] * centroid_score +
            weights["hist_mask_iou"] * hist_iou
        )

        metrics = {
            "sam_score": sam_score,
            "area_consistency": area_consistency,
            "bbox_iou_hist": bbox_score,
            "centroid_consistency": centroid_score,
            "hist_mask_iou": hist_iou,
            "combined": combined,
            "pred_area_px": pred_area,
            "hist_area_px": hist_area
        }

        if combined > best_combined:
            best_combined = combined
            best_idx = i
            best_metrics = metrics

    if best_idx is None:
        best_idx = int(np.argmax(scores))
        best_metrics = {
            "sam_score": float(scores[best_idx]),
            "area_consistency": np.nan,
            "bbox_iou_hist": np.nan,
            "centroid_consistency": np.nan,
            "hist_mask_iou": np.nan,
            "combined": float(scores[best_idx]),
            "pred_area_px": np.nan,
            "hist_area_px": hist_area
        }

    return best_idx, best_metrics


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


def main():
    if len(sys.argv) != 2:
        print("Usage: python scripts/geo_run_sam2_rerank_experiment.py <config.json>")
        sys.exit(1)

    ROOT = Path(__file__).resolve().parents[1]
    cfg_path = ROOT / sys.argv[1]
    exp_cfg = json.loads(cfg_path.read_text())

    exp_name = exp_cfg["experiment_name"]
    manifest_path = ROOT / exp_cfg["manifest_path"]
    ckpt = ROOT / exp_cfg["checkpoint"]
    config_name = exp_cfg["config_name"]

    out_dir = ROOT / "outputs" / exp_name
    out_dir.mkdir(parents=True, exist_ok=True)
    out_gpkg = out_dir / "berlin_predictions.gpkg"

    df = pd.read_csv(manifest_path)

    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = build_sam2(config_name, str(ckpt), device=device)
    predictor = SAM2ImagePredictor(model)

    weights = exp_cfg["reranking"]["weights"]

    rows = []

    for _, r in df.iterrows():
        orig_geom = wkt.loads(r["orig_wkt"])
        poly_px = wkt.loads(r["poly_px_wkt"])

        chip_bgr = cv2.imread(r["chip_path"])
        chip_rgb = cv2.cvtColor(chip_bgr, cv2.COLOR_BGR2RGB)

        h, w = chip_rgb.shape[:2]
        chip_diag = math.sqrt(h * h + w * w)

        chip_transform = from_bounds(
            r["chip_left"], r["chip_bottom"], r["chip_right"], r["chip_top"], w, h
        )

        raw_bbox = np.array(poly_px.bounds, dtype=np.float32) if exp_cfg["use_box"] else None
        bbox = expand_bbox(
            raw_bbox,
            exp_cfg.get("box_expand_px", 0),
            w,
            h
        ) if raw_bbox is not None else None

        pos_pts = sample_positive_points(
            poly_px,
            exp_cfg["positive_points"]["n_points"],
            strategy=exp_cfg["positive_points"].get("strategy", "deep_inside"),
        )

        point_coords = np.array([[x, y] for x, y in pos_pts], dtype=np.float32)
        point_labels = np.array([1] * len(pos_pts), dtype=np.int32)

        hist_mask = polygon_to_mask(poly_px, h, w)
        hist_bbox = mask_bbox(hist_mask)
        hist_centroid = mask_centroid(hist_mask)

        with torch.inference_mode():
            if device == "cuda":
                with torch.autocast("cuda", dtype=torch.bfloat16):
                    predictor.set_image(chip_rgb)
                    masks, scores, _ = predictor.predict(
                        box=bbox,
                        point_coords=point_coords,
                        point_labels=point_labels,
                    )
            else:
                predictor.set_image(chip_rgb)
                masks, scores, _ = predictor.predict(
                    box=bbox,
                    point_coords=point_coords,
                    point_labels=point_labels,
                )

        best_idx, best_metrics = rerank_masks(
            masks=masks,
            scores=scores,
            hist_mask=hist_mask,
            hist_bbox=hist_bbox,
            hist_centroid=hist_centroid,
            chip_diag=chip_diag,
            weights=weights
        )

        pred_mask = (masks[best_idx] > 0).astype(np.uint8)
        pred_geom = mask_to_largest_polygon(pred_mask, chip_transform)

        rows.append({
            "id": r["id"],
            "orig_wkt": orig_geom.wkt,
            "sam_score": float(scores[best_idx]),
            "chip_path": r["chip_path"],
            "n_pos": len(pos_pts),
            "n_neg": 0,
            "selected_mask_idx": int(best_idx),
            "rerank_combined": float(best_metrics["combined"]),
            "rerank_area_consistency": float(best_metrics["area_consistency"]) if not pd.isna(best_metrics["area_consistency"]) else np.nan,
            "rerank_bbox_iou_hist": float(best_metrics["bbox_iou_hist"]) if not pd.isna(best_metrics["bbox_iou_hist"]) else np.nan,
            "rerank_centroid_consistency": float(best_metrics["centroid_consistency"]) if not pd.isna(best_metrics["centroid_consistency"]) else np.nan,
            "rerank_hist_mask_iou": float(best_metrics["hist_mask_iou"]) if not pd.isna(best_metrics["hist_mask_iou"]) else np.nan,
            "pred_area_px": float(best_metrics["pred_area_px"]) if not pd.isna(best_metrics["pred_area_px"]) else np.nan,
            "hist_area_px": float(best_metrics["hist_area_px"]) if not pd.isna(best_metrics["hist_area_px"]) else np.nan,
            "geometry": pred_geom,
        })

    gdf = gpd.GeoDataFrame(rows, geometry="geometry", crs=df["chip_crs"].iloc[0])
    gdf.to_file(out_gpkg, layer="predictions", driver="GPKG")

    (out_dir / "experiment_config.json").write_text(json.dumps(exp_cfg, indent=2))

    print("Saved:", out_gpkg)
    print("Saved config copy:", out_dir / "experiment_config.json")
    print(gdf.head(5))


if __name__ == "__main__":
    main()