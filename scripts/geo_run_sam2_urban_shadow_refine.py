from pathlib import Path
import sys
import json
import math
import numpy as np
import pandas as pd
import geopandas as gpd
import cv2
from shapely import wkt
from shapely.geometry import shape, Point
from shapely.ops import unary_union, transform as shp_transform
from rasterio.features import shapes
from rasterio.transform import from_bounds
import torch
import fiona

from sam2.build_sam import build_sam2
from sam2.sam2_image_predictor import SAM2ImagePredictor


def load_layer(path, preferred_layer):
    layers = fiona.listlayers(path)
    layer = preferred_layer if preferred_layer in layers else layers[0]
    return gpd.read_file(path, layer=layer)


def gamma_correct_rgb(img_rgb, gamma):
    x = img_rgb.astype(np.float32) / 255.0
    y = np.power(x, gamma)
    y = np.clip(y * 255.0, 0, 255).astype(np.uint8)
    return y


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
            mind = min((p[0]-q[0])**2 + (p[1]-q[1])**2 for q in selected)
            if mind > best_score:
                best_score = mind
                best_idx = i
        selected.append(remaining.pop(best_idx))
    return selected


def sample_deep_inside_points(poly, n_points):
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


def expand_bbox(bounds, pad_px, w, h):
    x1, y1, x2, y2 = bounds
    x1 = max(0.0, x1 - pad_px)
    y1 = max(0.0, y1 - pad_px)
    x2 = min(float(w - 1), x2 + pad_px)
    y2 = min(float(h - 1), y2 + pad_px)
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


def binary_iou(mask_a, mask_b):
    inter = np.logical_and(mask_a > 0, mask_b > 0).sum()
    union = np.logical_or(mask_a > 0, mask_b > 0).sum()
    return 0.0 if union == 0 else float(inter / union)


def mask_centroid(mask01):
    ys, xs = np.where(mask01 > 0)
    if len(xs) == 0:
        return None
    return np.array([xs.mean(), ys.mean()], dtype=np.float32)


def mask_to_polygon(mask01, transform):
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


def rerank_masks(masks, scores, prior_mask, prior_centroid, chip_diag, weights):
    prior_area = float(prior_mask.sum())

    best_idx = None
    best_combined = -1.0

    for i in range(len(scores)):
        pred01 = (masks[i] > 0).astype(np.uint8)
        pred_area = float(pred01.sum())
        if pred_area <= 0:
            continue

        prior_iou = binary_iou(pred01, prior_mask)

        area_ratio = pred_area / max(prior_area, 1.0)
        area_consistency = max(0.0, 1.0 - abs(area_ratio - 1.0))

        pred_centroid = mask_centroid(pred01)
        if pred_centroid is None or prior_centroid is None:
            centroid_consistency = 0.0
        else:
            dist = np.linalg.norm(pred_centroid - prior_centroid)
            centroid_consistency = max(0.0, 1.0 - dist / max(0.35 * chip_diag, 1.0))

        ys, xs = np.where(pred01 > 0)
        if len(xs) == 0:
            compactness = 0.0
        else:
            bbox_area = float((xs.max() - xs.min() + 1) * (ys.max() - ys.min() + 1))
            compactness = pred_area / max(bbox_area, 1.0)

        combined = (
            weights["sam_score"] * float(scores[i]) +
            weights["prior_iou"] * float(prior_iou) +
            weights["area_consistency"] * float(area_consistency) +
            weights["centroid_consistency"] * float(centroid_consistency) +
            weights["compactness"] * float(compactness)
        )

        if combined > best_combined:
            best_combined = combined
            best_idx = i

    if best_idx is None:
        best_idx = int(np.argmax(scores))

    return best_idx


def main():
    if len(sys.argv) != 2:
        print("Usage: python scripts/geo_run_sam2_urban_shadow_refine.py <config.json>")
        sys.exit(1)

    ROOT = Path(__file__).resolve().parents[1]
    cfg = json.loads((ROOT / sys.argv[1]).read_text())

    exp_name = cfg["experiment_name"]
    routing_csv = ROOT / cfg["routing_table_csv"]
    baseline_exp = cfg["baseline_experiment"]
    manifest_csv = ROOT / cfg["manifest_path"]

    out_dir = ROOT / "outputs" / exp_name
    out_dir.mkdir(parents=True, exist_ok=True)
    out_gpkg = out_dir / "berlin_predictions.gpkg"

    routing = pd.read_csv(routing_csv)
    manifest = pd.read_csv(manifest_csv)

    baseline_preds_gdf = load_layer(
        ROOT / "outputs" / baseline_exp / "berlin_predictions.gpkg",
        "predictions"
    )
    crs_ref = baseline_preds_gdf.crs
    
    baseline_preds = baseline_preds_gdf[["id", "orig_wkt", "geometry", "sam_score"]].copy()
    baseline_preds = baseline_preds.rename(columns={
        "geometry": "baseline_geom",
        "sam_score": "baseline_score"
    })
    
    merged = routing.merge(manifest, on="id", how="left", suffixes=("", "_manifest"))
    merged = merged.merge(baseline_preds, on="id", how="left", suffixes=("", "_baseline"))
    
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = build_sam2(cfg["config_name"], str(ROOT / cfg["checkpoint"]), device=device)
    predictor = SAM2ImagePredictor(model)
    
    shadow_cfg = cfg["shadow_second_pass"]
    weights = cfg["reranking"]["weights"]
    rules = cfg["acceptance_rules"]
    
    rows = []

    for _, r in merged.iterrows():
        obj_id = int(r["id"])
        route = r["routing_decision"]

        baseline_geom = r["baseline_geom"]
        baseline_score = float(r["baseline_score"])

        if route not in shadow_cfg["enabled_routes"]:
            rows.append({
                "id": obj_id,
                "orig_wkt": r["orig_wkt"],
                "sam_score": baseline_score,
                "routing_decision": route,
                "selected_source": "baseline_current_best",
                "shadow_second_pass_used": False,
                "shadow_second_pass_accepted": False,
                "geometry": baseline_geom
            })
            continue

        chip_bgr = cv2.imread(r["chip_path"])
        chip_rgb = cv2.cvtColor(chip_bgr, cv2.COLOR_BGR2RGB)
        chip_rgb_bright = gamma_correct_rgb(chip_rgb, shadow_cfg["gamma"])

        h, w = chip_rgb.shape[:2]
        chip_transform = from_bounds(
            r["chip_left"], r["chip_bottom"], r["chip_right"], r["chip_top"], w, h
        )
        inv = ~chip_transform

        def world_to_chip(x, y, z=None):
            x = np.asarray(x)
            y = np.asarray(y)
            cols = inv.a * x + inv.b * y + inv.c
            rows = inv.d * x + inv.e * y + inv.f
            return cols, rows

        prior_poly_px = shp_transform(world_to_chip, baseline_geom).buffer(0)

        bbox = expand_bbox(prior_poly_px.bounds, shadow_cfg["box_expand_px"], w, h)
        pos_pts = sample_deep_inside_points(prior_poly_px, shadow_cfg["n_positive_points"])

        point_coords = np.array([[x, y] for x, y in pos_pts], dtype=np.float32)
        point_labels = np.array([1] * len(pos_pts), dtype=np.int32)

        prior_mask = polygon_to_mask(prior_poly_px, h, w)
        prior_centroid = mask_centroid(prior_mask)
        chip_diag = math.sqrt(h*h + w*w)

        with torch.inference_mode():
            if device == "cuda":
                with torch.autocast("cuda", dtype=torch.bfloat16):
                    predictor.set_image(chip_rgb_bright)
                    masks, scores, _ = predictor.predict(
                        box=bbox,
                        point_coords=point_coords,
                        point_labels=point_labels,
                    )
            else:
                predictor.set_image(chip_rgb_bright)
                masks, scores, _ = predictor.predict(
                    box=bbox,
                    point_coords=point_coords,
                    point_labels=point_labels,
                )

        best_idx = rerank_masks(masks, scores, prior_mask, prior_centroid, chip_diag, weights)
        pred_mask = (masks[best_idx] > 0).astype(np.uint8)
        pred_geom = mask_to_polygon(pred_mask, chip_transform)

        # acceptance in world coordinates
        iou_to_prior = 0.0
        centroid_shift_m = float("inf")
        area_ratio = float("inf")

        if pred_geom is not None and not pred_geom.is_empty:
            inter = pred_geom.intersection(baseline_geom).area
            union = pred_geom.union(baseline_geom).area
            iou_to_prior = 0.0 if union == 0 else float(inter / union)
            centroid_shift_m = float(pred_geom.centroid.distance(baseline_geom.centroid))
            area_ratio = float(pred_geom.area / max(baseline_geom.area, 1e-9))

        accept = (
            float(scores[best_idx]) >= rules["min_sam_score"] and
            iou_to_prior >= rules["min_iou_to_prior"] and
            centroid_shift_m <= rules["max_centroid_shift_m"] and
            area_ratio >= rules["min_area_ratio_vs_prior"] and
            area_ratio <= rules["max_area_ratio_vs_prior"]
        )

        rows.append({
            "id": obj_id,
            "orig_wkt": r["orig_wkt"],
            "sam_score": float(scores[best_idx]) if accept else baseline_score,
            "routing_decision": route,
            "selected_source": "shadow_pass2" if accept else "baseline_current_best",
            "shadow_second_pass_used": True,
            "shadow_second_pass_accepted": bool(accept),
            "iou_to_prior": iou_to_prior,
            "centroid_shift_to_prior_m": centroid_shift_m,
            "area_ratio_to_prior": area_ratio,
            "geometry": pred_geom if accept else baseline_geom
        })

    gdf = gpd.GeoDataFrame(rows, geometry="geometry", crs=crs_ref)
    gdf.to_file(out_gpkg, layer="predictions", driver="GPKG")
    (out_dir / "experiment_config.json").write_text(json.dumps(cfg, indent=2))

    print("Saved:", out_gpkg)
    print("Saved config copy:", out_dir / "experiment_config.json")
    print()
    print(gdf[[
        "id",
        "routing_decision",
        "selected_source",
        "shadow_second_pass_used",
        "shadow_second_pass_accepted",
        "sam_score"
    ]])
    print()
    print("Accepted shadow second pass count:", int(gdf["shadow_second_pass_accepted"].fillna(False).sum()))

if __name__ == "__main__":
    main()