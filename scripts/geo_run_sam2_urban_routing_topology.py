from pathlib import Path
import sys
import json
import math
import numpy as np
import pandas as pd
import geopandas as gpd
import cv2
from shapely import wkt
from shapely.geometry import shape, Point, Polygon, MultiPolygon
from shapely.ops import unary_union, transform as shp_transform
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
            mind = min((p[0]-q[0])**2 + (p[1]-q[1])**2 for q in selected)
            if mind > best_score:
                best_score = mind
                best_idx = i
        selected.append(remaining.pop(best_idx))
    return selected


def world_to_chip_transform(row, chip_size=512):
    chip_transform = from_bounds(
        row["chip_left"], row["chip_bottom"], row["chip_right"], row["chip_top"], chip_size, chip_size
    )
    inv = ~chip_transform

    def _world_to_chip(x, y, z=None):
        x = np.asarray(x)
        y = np.asarray(y)
        cols = inv.a * x + inv.b * y + inv.c
        rows = inv.d * x + inv.e * y + inv.f
        return cols, rows

    return _world_to_chip, chip_transform


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


def sample_negative_points_from_hull_gap(poly, max_points, min_gap_area):
    poly = poly.buffer(0)
    hull = poly.convex_hull.buffer(0)
    gap = hull.difference(poly)

    if gap.is_empty:
        return []

    polys = []
    if isinstance(gap, Polygon):
        polys = [gap]
    elif isinstance(gap, MultiPolygon):
        polys = list(gap.geoms)

    polys = [p for p in polys if p.area >= min_gap_area]
    polys = sorted(polys, key=lambda g: g.area, reverse=True)

    pts = []
    for g in polys[:max_points]:
        rp = g.representative_point()
        pts.append((rp.x, rp.y))

    return unique_points(pts)[:max_points]


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


def concavity_ratio(poly):
    poly = poly.buffer(0)
    if poly.is_empty:
        return 1.0
    hull_area = poly.convex_hull.area
    if hull_area <= 0:
        return 1.0
    return float(poly.area / hull_area)


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


def rerank_masks(masks, scores, prior_mask, prior_bbox, prior_centroid, prior_poly_px, chip_diag, weights, chip_transform):
    prior_area = float(prior_mask.sum())
    prior_conc = concavity_ratio(prior_poly_px)

    best_idx = None
    best_combined = -1.0
    best_metrics = None

    for i in range(len(scores)):
        pred01 = (masks[i] > 0).astype(np.uint8)
        pred_area = float(pred01.sum())
        if pred_area <= 0:
            continue

        pred_bbox = mask_bbox(pred01)
        pred_centroid = mask_centroid(pred01)

        prior_iou = binary_iou(pred01, prior_mask)
        area_ratio = pred_area / max(prior_area, 1.0)
        area_consistency = max(0.0, 1.0 - abs(area_ratio - 1.0))

        bbox_score = bbox_iou(pred_bbox, prior_bbox)

        if pred_centroid is None or prior_centroid is None:
            centroid_score = 0.0
        else:
            dist = np.linalg.norm(pred_centroid - prior_centroid)
            centroid_score = max(0.0, 1.0 - dist / max(0.35 * chip_diag, 1.0))

        pred_poly = mask_to_polygon(pred01, chip_transform)
        pred_conc = concavity_ratio(pred_poly) if pred_poly is not None else 1.0
        shape_match = max(0.0, 1.0 - abs(pred_conc - prior_conc))

        combined = (
            weights["sam_score"] * float(scores[i]) +
            weights["prior_iou"] * prior_iou +
            weights["area_consistency"] * area_consistency +
            weights["bbox_iou_prior"] * bbox_score +
            weights["centroid_consistency"] * centroid_score +
            weights["shape_match"] * shape_match
        )

        metrics = {
            "sam_score": float(scores[i]),
            "prior_iou": float(prior_iou),
            "area_consistency": float(area_consistency),
            "bbox_iou_prior": float(bbox_score),
            "centroid_consistency": float(centroid_score),
            "shape_match": float(shape_match),
            "combined": float(combined)
        }

        if combined > best_combined:
            best_combined = combined
            best_idx = i
            best_metrics = metrics

    if best_idx is None:
        best_idx = int(np.argmax(scores))
        best_metrics = {
            "sam_score": float(scores[best_idx]),
            "prior_iou": np.nan,
            "area_consistency": np.nan,
            "bbox_iou_prior": np.nan,
            "centroid_consistency": np.nan,
            "shape_match": np.nan,
            "combined": float(scores[best_idx]),
        }

    return best_idx, best_metrics


def load_predictions(root, exp_folder):
    path = root / "outputs" / exp_folder / "berlin_predictions.gpkg"
    return gpd.read_file(path, layer="predictions")[["id", "geometry", "sam_score"]]


def main():
    if len(sys.argv) != 2:
        print("Usage: python scripts/geo_run_sam2_urban_routing_topology.py <config.json>")
        sys.exit(1)

    ROOT = Path(__file__).resolve().parents[1]
    cfg = json.loads((ROOT / sys.argv[1]).read_text())

    exp_name = cfg["experiment_name"]
    routing_csv = ROOT / cfg["routing_table_csv"]
    manifest_csv = ROOT / cfg["manifest_path"]

    out_dir = ROOT / "outputs" / exp_name
    out_dir.mkdir(parents=True, exist_ok=True)
    out_gpkg = out_dir / "berlin_predictions.gpkg"

    routing = pd.read_csv(routing_csv)
    manifest = pd.read_csv(manifest_csv)

    source_preds = {}
    for short_name, folder in cfg["pass1_experiments"].items():
        gdf = load_predictions(ROOT, folder).rename(columns={
            "geometry": f"geom_{short_name}",
            "sam_score": f"sam_score_{short_name}"
        })
        source_preds[short_name] = gdf

    merged = routing.merge(manifest, on="id", how="left")
    for short_name, gdf in source_preds.items():
        merged = merged.merge(gdf, on="id", how="left")

    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = build_sam2(cfg["config_name"], str(ROOT / cfg["checkpoint"]), device=device)
    predictor = SAM2ImagePredictor(model)

    topo_cfg = cfg["topology_second_pass"]
    weights = cfg["reranking"]["weights"]

    rows = []

    for _, r in merged.iterrows():
        obj_id = int(r["id"])
        route = r["routing_decision"]
        pass1_source = r["pass1_source"]

        chip_bgr = cv2.imread(r["chip_path"])
        chip_rgb = cv2.cvtColor(chip_bgr, cv2.COLOR_BGR2RGB)
        h, w = chip_rgb.shape[:2]

        world2chip, chip_transform = world_to_chip_transform(r, chip_size=w)

        # prior geometry from selected pass1 source
        prior_world = r[f"geom_{pass1_source}"]
        prior_poly_px = shp_transform(world2chip, prior_world).buffer(0)

        if route in topo_cfg["enabled_for_routes"]:
            bbox = expand_bbox(prior_poly_px.bounds, topo_cfg["box_expand_px"], w, h)
            pos_pts = sample_deep_inside_points(prior_poly_px, topo_cfg["n_positive_points"])
            neg_pts = sample_negative_points_from_hull_gap(
                prior_poly_px,
                topo_cfg["max_negative_points"],
                topo_cfg["min_negative_area_px2"]
            )

            point_coords = np.array([[x, y] for x, y in pos_pts + neg_pts], dtype=np.float32)
            point_labels = np.array([1] * len(pos_pts) + [0] * len(neg_pts), dtype=np.int32)

            prior_mask = polygon_to_mask(prior_poly_px, h, w)
            prior_bbox = mask_bbox(prior_mask)
            prior_centroid = mask_centroid(prior_mask)
            chip_diag = math.sqrt(h * h + w * w)

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
                prior_mask=prior_mask,
                prior_bbox=prior_bbox,
                prior_centroid=prior_centroid,
                prior_poly_px=prior_poly_px,
                chip_diag=chip_diag,
                weights=weights,
                chip_transform=chip_transform
            )

            pred_mask = (masks[best_idx] > 0).astype(np.uint8)
            pred_geom = mask_to_polygon(pred_mask, chip_transform)

            rows.append({
                "id": obj_id,
                "orig_wkt": r["orig_wkt"],
                "sam_score": float(scores[best_idx]),
                "chip_path": r["chip_path"],
                "routing_decision": route,
                "pass1_source": pass1_source,
                "second_pass_used": True,
                "n_pos": len(pos_pts),
                "n_neg": len(neg_pts),
                "rerank_combined": float(best_metrics["combined"]),
                "prior_iou": float(best_metrics["prior_iou"]) if not pd.isna(best_metrics["prior_iou"]) else np.nan,
                "area_consistency": float(best_metrics["area_consistency"]) if not pd.isna(best_metrics["area_consistency"]) else np.nan,
                "bbox_iou_prior": float(best_metrics["bbox_iou_prior"]) if not pd.isna(best_metrics["bbox_iou_prior"]) else np.nan,
                "centroid_consistency": float(best_metrics["centroid_consistency"]) if not pd.isna(best_metrics["centroid_consistency"]) else np.nan,
                "shape_match": float(best_metrics["shape_match"]) if not pd.isna(best_metrics["shape_match"]) else np.nan,
                "geometry": pred_geom,
            })

        else:
            # carry through pass1 geometry unchanged
            rows.append({
                "id": obj_id,
                "orig_wkt": r["orig_wkt"],
                "sam_score": float(r[f"sam_score_{pass1_source}"]),
                "chip_path": r["chip_path"],
                "routing_decision": route,
                "pass1_source": pass1_source,
                "second_pass_used": False,
                "n_pos": 0,
                "n_neg": 0,
                "rerank_combined": np.nan,
                "prior_iou": np.nan,
                "area_consistency": np.nan,
                "bbox_iou_prior": np.nan,
                "centroid_consistency": np.nan,
                "shape_match": np.nan,
                "geometry": prior_world,
            })

    gdf = gpd.GeoDataFrame(rows, geometry="geometry", crs=load_predictions(ROOT, cfg["pass1_experiments"]["exp04"]).crs)
    gdf.to_file(out_gpkg, layer="predictions", driver="GPKG")
    (out_dir / "experiment_config.json").write_text(json.dumps(cfg, indent=2))

    print("Saved:", out_gpkg)
    print("Saved config copy:", out_dir / "experiment_config.json")
    print()
    print(gdf[["id", "routing_decision", "pass1_source", "second_pass_used", "sam_score"]])

if __name__ == "__main__":
    main()