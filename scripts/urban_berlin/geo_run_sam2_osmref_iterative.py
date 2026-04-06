from pathlib import Path
import sys
import json
import pandas as pd
import numpy as np
import geopandas as gpd
import cv2
from shapely import wkt
from shapely.geometry import shape, Polygon, MultiPolygon
from shapely.ops import unary_union
from rasterio.features import shapes
from rasterio.transform import from_bounds
import torch

from sam2.build_sam import build_sam2
from sam2.sam2_image_predictor import SAM2ImagePredictor


def polygon_to_mask(poly, h, w):
    mask = np.zeros((h, w), dtype=np.uint8)

    def draw_polygon(p):
        if p.is_empty:
            return
        ext = np.round(np.array(p.exterior.coords)).astype(np.int32)
        cv2.fillPoly(mask, [ext], 1)
        for ring in p.interiors:
            hole = np.round(np.array(ring.coords)).astype(np.int32)
            cv2.fillPoly(mask, [hole], 0)

    if isinstance(poly, Polygon):
        draw_polygon(poly)
    elif isinstance(poly, MultiPolygon):
        for p in poly.geoms:
            draw_polygon(p)

    return mask


def representative_point_xy(poly):
    rp = poly.representative_point()
    return float(rp.x), float(rp.y)


def bbox_from_poly(poly, pad_px=0, w=None, h=None):
    minx, miny, maxx, maxy = poly.bounds
    x1, y1, x2, y2 = float(minx), float(miny), float(maxx), float(maxy)
    if pad_px > 0 and w is not None and h is not None:
        x1 = max(0.0, x1 - pad_px)
        y1 = max(0.0, y1 - pad_px)
        x2 = min(float(w - 1), x2 + pad_px)
        y2 = min(float(h - 1), y2 + pad_px)
    return np.array([x1, y1, x2, y2], dtype=np.float32)


def sample_deep_points_from_mask(mask01, n_points, suppression_radius=12):
    pts = []
    if mask01.sum() == 0:
        return pts

    dist = cv2.distanceTransform(mask01.astype(np.uint8), cv2.DIST_L2, 5)
    work = dist.copy()

    for _ in range(n_points):
        y, x = np.unravel_index(np.argmax(work), work.shape)
        if work[y, x] <= 0:
            break
        pts.append((float(x), float(y)))
        cv2.circle(work, (int(x), int(y)), suppression_radius, 0, thickness=-1)

    return pts


def prior_score(pred01, prior01, sam_score, weights):
    pred_area = float(pred01.sum())
    prior_area = float(prior01.sum())

    if pred_area == 0 or prior_area == 0:
        return 0.0, {
            "iou_prior": 0.0,
            "precision_prior": 0.0,
            "recall_prior": 0.0,
            "area_consistency": 0.0
        }

    inter = np.logical_and(pred01 == 1, prior01 == 1).sum()
    union = np.logical_or(pred01 == 1, prior01 == 1).sum()

    iou_prior = 0.0 if union == 0 else inter / union
    precision_prior = inter / pred_area
    recall_prior = inter / prior_area
    area_consistency = max(0.0, 1.0 - abs(pred_area - prior_area) / prior_area)

    combined = (
        weights["w_iou_prior"] * iou_prior +
        weights["w_precision_prior"] * precision_prior +
        weights["w_recall_prior"] * recall_prior +
        weights["w_area_consistency"] * area_consistency +
        weights["w_sam_score"] * float(sam_score)
    )

    return float(combined), {
        "iou_prior": float(iou_prior),
        "precision_prior": float(precision_prior),
        "recall_prior": float(recall_prior),
        "area_consistency": float(area_consistency)
    }


def choose_best_mask(masks, scores, prior01, weights):
    best_idx = None
    best_combined = -1
    best_metrics = None

    for i in range(len(scores)):
        pred01 = (masks[i] > 0).astype(np.uint8)
        combined, metrics = prior_score(pred01, prior01, scores[i], weights)
        if combined > best_combined:
            best_combined = combined
            best_idx = i
            best_metrics = metrics

    return best_idx, best_combined, best_metrics


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
        print("Usage: python scripts/geo_run_sam2_osmref_iterative.py <config.json>")
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

    rows = []
    weights = exp_cfg["mask_selection"]

    for _, r in df.iterrows():
        orig_geom = wkt.loads(r["orig_wkt"])
        poly_px = wkt.loads(r["poly_px_wkt"])

        chip_bgr = cv2.imread(r["chip_path"])
        chip_rgb = cv2.cvtColor(chip_bgr, cv2.COLOR_BGR2RGB)
        h, w = chip_rgb.shape[:2]

        chip_transform = from_bounds(
            r["chip_left"], r["chip_bottom"], r["chip_right"], r["chip_top"], w, h
        )

        prior01 = polygon_to_mask(poly_px, h, w)
        bbox = bbox_from_poly(poly_px, exp_cfg.get("box_expand_px", 0), w, h) if exp_cfg["use_box"] else None

        # ---------- stage 1 ----------
        seed_x, seed_y = representative_point_xy(poly_px)
        stage1_coords = np.array([[seed_x, seed_y]], dtype=np.float32)
        stage1_labels = np.array([1], dtype=np.int32)

        with torch.inference_mode():
            if device == "cuda":
                with torch.autocast("cuda", dtype=torch.bfloat16):
                    predictor.set_image(chip_rgb)
                    masks1, scores1, _ = predictor.predict(
                        box=bbox,
                        point_coords=stage1_coords,
                        point_labels=stage1_labels,
                    )
            else:
                predictor.set_image(chip_rgb)
                masks1, scores1, _ = predictor.predict(
                    box=bbox,
                    point_coords=stage1_coords,
                    point_labels=stage1_labels,
                )

        idx1, comb1, metrics1 = choose_best_mask(masks1, scores1, prior01, weights)
        pred1 = (masks1[idx1] > 0).astype(np.uint8)

        # ---------- correction regions ----------
        missing01 = np.logical_and(prior01 == 1, pred1 == 0).astype(np.uint8)
        spill01 = np.logical_and(pred1 == 1, prior01 == 0).astype(np.uint8)

        max_missing = exp_cfg["stage2"]["max_missing_pos_points"]
        max_spill = exp_cfg["stage2"]["max_spill_neg_points"]
        suppress_r = exp_cfg["stage2"]["point_suppression_radius_px"]

        missing_pts = sample_deep_points_from_mask(missing01, max_missing, suppress_r)
        spill_pts = sample_deep_points_from_mask(spill01, max_spill, suppress_r)

        stage2_point_coords = [[seed_x, seed_y]]
        stage2_point_labels = [1]

        for x, y in missing_pts:
            stage2_point_coords.append([x, y])
            stage2_point_labels.append(1)

        for x, y in spill_pts:
            stage2_point_coords.append([x, y])
            stage2_point_labels.append(0)

        stage2_coords = np.array(stage2_point_coords, dtype=np.float32)
        stage2_labels = np.array(stage2_point_labels, dtype=np.int32)

        # ---------- stage 2 ----------
        with torch.inference_mode():
            if device == "cuda":
                with torch.autocast("cuda", dtype=torch.bfloat16):
                    predictor.set_image(chip_rgb)
                    masks2, scores2, _ = predictor.predict(
                        box=bbox,
                        point_coords=stage2_coords,
                        point_labels=stage2_labels,
                    )
            else:
                predictor.set_image(chip_rgb)
                masks2, scores2, _ = predictor.predict(
                    box=bbox,
                    point_coords=stage2_coords,
                    point_labels=stage2_labels,
                )

        idx2, comb2, metrics2 = choose_best_mask(masks2, scores2, prior01, weights)
        pred2 = (masks2[idx2] > 0).astype(np.uint8)
        pred_geom = mask_to_largest_polygon(pred2, chip_transform)

        rows.append({
            "id": r["id"],
            "orig_wkt": orig_geom.wkt,
            "sam_score": float(scores2[idx2]),
            "chip_path": r["chip_path"],
            "n_pos_stage2": int(sum(stage2_labels == 1)),
            "n_neg_stage2": int(sum(stage2_labels == 0)),
            "combined_stage1": float(comb1),
            "combined_stage2": float(comb2),
            "iou_prior_stage1": metrics1["iou_prior"],
            "iou_prior_stage2": metrics2["iou_prior"],
            "precision_prior_stage2": metrics2["precision_prior"],
            "recall_prior_stage2": metrics2["recall_prior"],
            "geometry": pred_geom,
        })

    gdf = gpd.GeoDataFrame(rows, geometry="geometry", crs=df["chip_crs"].iloc[0])
    gdf.to_file(out_gpkg, layer="predictions", driver="GPKG")
    (out_dir / "experiment_config.json").write_text(json.dumps(exp_cfg, indent=2))

    print("Saved:", out_gpkg)
    print("Saved config copy:", out_dir / "experiment_config.json")
    print(gdf.head(3))


if __name__ == "__main__":
    main()