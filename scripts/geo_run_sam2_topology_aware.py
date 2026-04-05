from pathlib import Path
import sys
import json
import math
import pandas as pd
import numpy as np
import geopandas as gpd
import cv2
from shapely import wkt
from shapely.geometry import shape, Point, Polygon, MultiPolygon
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
            mind = min((p[0]-q[0])**2 + (p[1]-q[1])**2 for q in selected)
            if mind > best_score:
                best_score = mind
                best_idx = i
        selected.append(remaining.pop(best_idx))
    return selected


def polygon_metrics(poly):
    poly = poly.buffer(0)
    area = float(poly.area)
    perimeter = float(poly.length) if poly.length > 0 else 0.0
    hull_area = float(poly.convex_hull.area) if poly.convex_hull.area > 0 else area
    concavity_ratio = area / hull_area if hull_area > 0 else 1.0

    minx, miny, maxx, maxy = poly.bounds
    bw = maxx - minx
    bh = maxy - miny
    elongation = max(bw, bh) / max(min(bw, bh), 1e-6)

    compactness = 0.0
    if perimeter > 0:
        compactness = 4.0 * math.pi * area / (perimeter ** 2)

    hole_count = len(poly.interiors) if isinstance(poly, Polygon) else sum(len(p.interiors) for p in poly.geoms)

    return {
        "area": area,
        "concavity_ratio": concavity_ratio,
        "elongation": elongation,
        "compactness": compactness,
        "hole_count": hole_count,
    }


def is_complex(poly, rules):
    m = polygon_metrics(poly)
    if m["hole_count"] > 0:
        return True, m
    if not rules["enable_complexity_logic"]:
        return False, m
    if m["concavity_ratio"] < rules["concavity_threshold"]:
        return True, m
    if m["compactness"] < rules["compactness_threshold"]:
        return True, m
    if m["elongation"] > rules["elongation_threshold"]:
        return True, m
    return False, m


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


def sample_hole_negative_points(poly, max_points, min_hole_area):
    hole_pts = []

    def handle_polygon(p):
        for ring in p.interiors:
            hole_poly = Polygon(ring)
            if hole_poly.area >= min_hole_area:
                rp = hole_poly.representative_point()
                hole_pts.append((rp.x, rp.y))

    if isinstance(poly, Polygon):
        handle_polygon(poly)
    elif isinstance(poly, MultiPolygon):
        for p in poly.geoms:
            handle_polygon(p)

    hole_pts = unique_points(hole_pts)
    return hole_pts[:max_points]


def bbox_from_poly(poly, pad_px=0, w=None, h=None):
    minx, miny, maxx, maxy = poly.bounds
    x1, y1, x2, y2 = float(minx), float(miny), float(maxx), float(maxy)
    if pad_px > 0 and w is not None and h is not None:
        x1 = max(0.0, x1 - pad_px)
        y1 = max(0.0, y1 - pad_px)
        x2 = min(float(w - 1), x2 + pad_px)
        y2 = min(float(h - 1), y2 + pad_px)
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


def main():
    if len(sys.argv) != 2:
        print("Usage: python scripts/geo_run_sam2_topology_aware.py <config.json>")
        sys.exit(1)

    ROOT = Path(__file__).resolve().parents[1]
    cfg_path = ROOT / sys.argv[1]
    exp_cfg = json.loads(cfg_path.read_text())

    exp_name = exp_cfg["experiment_name"]
    manifest_path = ROOT / exp_cfg["manifest_path"]
    ckpt = ROOT / exp_cfg["checkpoint"]
    config_name = exp_cfg["config_name"]

    topo_cfg = exp_cfg["topology_prompting"]
    rules = topo_cfg["complexity_rules"]

    out_dir = ROOT / "outputs" / exp_name
    out_dir.mkdir(parents=True, exist_ok=True)
    out_gpkg = out_dir / "berlin_predictions.gpkg"

    df = pd.read_csv(manifest_path)

    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = build_sam2(config_name, str(ckpt), device=device)
    predictor = SAM2ImagePredictor(model)

    rows = []

    for _, r in df.iterrows():
        orig_geom = wkt.loads(r["orig_wkt"])
        poly_px = wkt.loads(r["poly_px_wkt"]).buffer(0)

        chip_bgr = cv2.imread(r["chip_path"])
        chip_rgb = cv2.cvtColor(chip_bgr, cv2.COLOR_BGR2RGB)
        h, w = chip_rgb.shape[:2]

        chip_transform = from_bounds(
            r["chip_left"], r["chip_bottom"], r["chip_right"], r["chip_top"], w, h
        )

        bbox = bbox_from_poly(poly_px, exp_cfg.get("box_expand_px", 0), w, h) if exp_cfg["use_box"] else None

        complex_flag, m = is_complex(poly_px, rules)

        point_coords = []
        point_labels = []

        # always one stable positive point
        base_pts = sample_deep_inside_points(poly_px, topo_cfg["base_positive_points"])
        for x, y in base_pts:
            point_coords.append([x, y])
            point_labels.append(1)

        extra_pos = []
        if complex_flag:
            extra_pos = sample_deep_inside_points(poly_px, topo_cfg["base_positive_points"] + topo_cfg["max_extra_positive_points"])
            extra_pos = extra_pos[topo_cfg["base_positive_points"]:]  # only extras
            for x, y in extra_pos:
                point_coords.append([x, y])
                point_labels.append(1)

        hole_neg = []
        if topo_cfg["use_hole_negative_points"]:
            hole_neg = sample_hole_negative_points(
                poly_px,
                topo_cfg["max_hole_negative_points"],
                topo_cfg["min_hole_area_px2"],
            )
            for x, y in hole_neg:
                point_coords.append([x, y])
                point_labels.append(0)

        point_coords_arr = np.array(point_coords, dtype=np.float32) if len(point_coords) > 0 else None
        point_labels_arr = np.array(point_labels, dtype=np.int32) if len(point_labels) > 0 else None

        with torch.inference_mode():
            if device == "cuda":
                with torch.autocast("cuda", dtype=torch.bfloat16):
                    predictor.set_image(chip_rgb)
                    masks, scores, _ = predictor.predict(
                        box=bbox,
                        point_coords=point_coords_arr,
                        point_labels=point_labels_arr,
                    )
            else:
                predictor.set_image(chip_rgb)
                masks, scores, _ = predictor.predict(
                    box=bbox,
                    point_coords=point_coords_arr,
                    point_labels=point_labels_arr,
                )

        best = int(np.argmax(scores))
        pred_mask = (masks[best] > 0).astype(np.uint8)
        pred_geom = mask_to_largest_polygon(pred_mask, chip_transform)

        rows.append({
            "id": r["id"],
            "orig_wkt": orig_geom.wkt,
            "sam_score": float(scores[best]),
            "chip_path": r["chip_path"],
            "complex_flag": bool(complex_flag),
            "hole_count": int(m["hole_count"]),
            "concavity_ratio": float(m["concavity_ratio"]),
            "compactness": float(m["compactness"]),
            "elongation": float(m["elongation"]),
            "n_pos": int(sum(np.array(point_labels) == 1)),
            "n_neg": int(sum(np.array(point_labels) == 0)),
            "geometry": pred_geom,
        })

    gdf = gpd.GeoDataFrame(rows, geometry="geometry", crs=df["chip_crs"].iloc[0])
    gdf.to_file(out_gpkg, layer="predictions", driver="GPKG")
    (out_dir / "experiment_config.json").write_text(json.dumps(exp_cfg, indent=2))

    print("Saved:", out_gpkg)
    print("Saved config copy:", out_dir / "experiment_config.json")
    print(gdf[["id", "complex_flag", "hole_count", "n_pos", "n_neg", "sam_score"]].head(8))


if __name__ == "__main__":
    main()