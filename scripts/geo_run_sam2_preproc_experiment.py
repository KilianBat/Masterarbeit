from pathlib import Path
import sys
import json
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


def sample_negative_points(poly, n_points, margin_px, img_w, img_h, adaptive_margin=True):
    poly = poly.buffer(0)
    minx, miny, maxx, maxy = poly.bounds
    bw = maxx - minx
    bh = maxy - miny

    margin = float(margin_px)
    if adaptive_margin:
        margin = max(margin, 0.18 * max(bw, bh))

    ex0 = max(0.0, minx - margin)
    ey0 = max(0.0, miny - margin)
    ex1 = min(float(img_w - 1), maxx + margin)
    ey1 = min(float(img_h - 1), maxy + margin)

    xs = [ex0, (ex0 + minx) / 2, (minx + maxx) / 2, (maxx + ex1) / 2, ex1]
    ys = [ey0, (ey0 + miny) / 2, (miny + maxy) / 2, (maxy + ey1) / 2, ey1]

    ring_candidates = [
        (xs[0], ys[0]), (xs[2], ys[0]), (xs[4], ys[0]),
        (xs[4], ys[2]), (xs[4], ys[4]),
        (xs[2], ys[4]), (xs[0], ys[4]),
        (xs[0], ys[2]),
        (xs[1], ys[0]), (xs[3], ys[0]),
        (xs[4], ys[1]), (xs[4], ys[3]),
        (xs[3], ys[4]), (xs[1], ys[4]),
        (xs[0], ys[3]), (xs[0], ys[1]),
    ]

    out = []
    poly_buf = poly.buffer(2.0)

    for x, y in ring_candidates:
        p = Point(float(x), float(y))
        if not poly_buf.contains(p):
            out.append((float(x), float(y)))

    out = unique_points(out)
    out = greedy_spread_select(out, n_points)
    return out[:n_points]


def expand_bbox(bbox, pad_px, img_w, img_h):
    if bbox is None:
        return None
    x1, y1, x2, y2 = bbox
    x1 = max(0.0, x1 - pad_px)
    y1 = max(0.0, y1 - pad_px)
    x2 = min(float(img_w - 1), x2 + pad_px)
    y2 = min(float(img_h - 1), y2 + pad_px)
    return np.array([x1, y1, x2, y2], dtype=np.float32)


def apply_clahe_rgb(image_rgb, clip_limit=2.0, tile_grid_size=8):
    lab = cv2.cvtColor(image_rgb, cv2.COLOR_RGB2LAB)
    l, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=float(clip_limit), tileGridSize=(int(tile_grid_size), int(tile_grid_size)))
    l2 = clahe.apply(l)
    lab2 = cv2.merge([l2, a, b])
    return cv2.cvtColor(lab2, cv2.COLOR_LAB2RGB)


def apply_gamma_rgb(image_rgb, gamma=0.85):
    gamma = float(gamma)
    x = np.clip(image_rgb.astype(np.float32) / 255.0, 0.0, 1.0)
    y = np.power(x, gamma)
    return np.clip(y * 255.0, 0, 255).astype(np.uint8)


def preprocess_image(image_rgb, pre_cfg):
    out = image_rgb.copy()

    if not pre_cfg.get("enabled", False):
        return out

    if pre_cfg.get("clahe", False):
        out = apply_clahe_rgb(
            out,
            clip_limit=pre_cfg.get("clahe_clip_limit", 2.0),
            tile_grid_size=pre_cfg.get("clahe_tile_grid_size", 8),
        )

    if pre_cfg.get("gamma", False):
        out = apply_gamma_rgb(
            out,
            gamma=pre_cfg.get("gamma_value", 0.85),
        )

    return out


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
        print("Usage: python scripts/geo_run_sam2_preproc_experiment.py <config.json>")
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

    for _, r in df.iterrows():
        orig_geom = wkt.loads(r["orig_wkt"])
        poly_px = wkt.loads(r["poly_px_wkt"])

        chip_bgr = cv2.imread(r["chip_path"])
        chip_rgb = cv2.cvtColor(chip_bgr, cv2.COLOR_BGR2RGB)
        chip_rgb = preprocess_image(chip_rgb, exp_cfg["preprocessing"])

        h, w = chip_rgb.shape[:2]

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

        point_coords = []
        point_labels = []

        if exp_cfg["positive_points"]["enabled"]:
            pos_pts = sample_positive_points(
                poly_px,
                exp_cfg["positive_points"]["n_points"],
                strategy=exp_cfg["positive_points"].get("strategy", "deep_inside"),
            )
            for x, y in pos_pts:
                point_coords.append([x, y])
                point_labels.append(1)
        else:
            pos_pts = []

        if exp_cfg["negative_points"]["enabled"]:
            neg_pts = sample_negative_points(
                poly_px,
                exp_cfg["negative_points"]["n_points"],
                exp_cfg["negative_points"]["margin_px"],
                w,
                h,
                adaptive_margin=exp_cfg["negative_points"].get("adaptive_margin", True),
            )
            for x, y in neg_pts:
                point_coords.append([x, y])
                point_labels.append(0)
        else:
            neg_pts = []

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
            "n_pos": len(pos_pts),
            "n_neg": len(neg_pts),
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