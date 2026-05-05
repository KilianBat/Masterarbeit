from pathlib import Path
import sys
import json
import math
import numpy as np
import pandas as pd
import cv2
from shapely import wkt
from shapely.geometry import Polygon, MultiPolygon

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

def compactness(poly):
    if poly.is_empty or poly.length == 0:
        return 0.0
    return float(4.0 * math.pi * poly.area / (poly.length ** 2))

def hull_gap_frac(poly):
    poly = poly.buffer(0)
    if poly.is_empty or poly.area == 0:
        return 0.0
    return float((poly.convex_hull.area - poly.area) / poly.area)

def main():
    if len(sys.argv) != 2:
        print("Usage: python scripts/urban_compute_auto_features.py <config.json>")
        sys.exit(1)

    ROOT = Path(__file__).resolve().parents[1]
    cfg = json.loads((ROOT / sys.argv[1]).read_text())

    manifest = pd.read_csv(ROOT / cfg["manifest_path"])
    routing = pd.read_csv(ROOT / cfg["routing_table_csv"])
    uncertainty = pd.read_csv(ROOT / cfg["uncertainty_csv"])

    thr = cfg["thresholds"]

    df = manifest.merge(routing[["id", "routing_decision", "primary_error_type"]], on="id", how="left")
    df = df.merge(
        uncertainty[["id", "uncertainty_level", "mean_pairwise_iou", "area_cv", "centroid_spread_m"]],
        on="id",
        how="left"
    )

    rows = []

    for _, r in df.iterrows():
        img = cv2.imread(r["chip_path"])
        rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        h, w = gray.shape[:2]
        poly_px = wkt.loads(r["poly_px_wkt"]).buffer(0)
        mask = polygon_to_mask(poly_px, h, w).astype(np.uint8)

        # ring outside polygon
        kernel = np.ones((9, 9), np.uint8)
        dil = cv2.dilate(mask, kernel, iterations=2)
        ring = ((dil > 0) & (mask == 0)).astype(np.uint8)

        inside_vals = gray[mask > 0]
        ring_vals = gray[ring > 0]

        inside_mean = float(np.mean(inside_vals)) if len(inside_vals) else np.nan
        inside_std = float(np.std(inside_vals)) if len(inside_vals) else np.nan
        ring_mean = float(np.mean(ring_vals)) if len(ring_vals) else np.nan

        if len(inside_vals):
            dark_thr = inside_mean - 12.0
            dark_frac = float(np.mean(inside_vals < dark_thr))
        else:
            dark_frac = np.nan

        mean_drop = float(ring_mean - inside_mean) if not np.isnan(ring_mean) and not np.isnan(inside_mean) else np.nan

        # edges inside polygon
        edges = cv2.Canny(gray, 60, 120)
        edge_density = float(edges[mask > 0].mean() / 255.0) if np.any(mask > 0) else np.nan

        feat_compactness = compactness(poly_px)
        feat_hull_gap = hull_gap_frac(poly_px)

        # auto routing rules
        if (
            not np.isnan(dark_frac) and not np.isnan(mean_drop) and
            dark_frac >= thr["shadow_dark_frac"] and mean_drop >= thr["shadow_mean_drop"]
        ):
            auto_route = "shadow_refine"
        elif (
            feat_hull_gap >= thr["topology_hull_gap_frac"] or
            feat_compactness <= thr["topology_compactness_max"] or
            (not np.isnan(edge_density) and edge_density >= thr["topology_edge_density"])
        ):
            auto_route = "topology_refine"
        elif r["uncertainty_level"] == "medium" and r["primary_error_type"] == "stable_case":
            auto_route = "review_keep"
        else:
            auto_route = "no_refine"

        rows.append({
            "id": int(r["id"]),
            "inside_mean": inside_mean,
            "inside_std": inside_std,
            "ring_mean": ring_mean,
            "dark_frac": dark_frac,
            "mean_drop_to_ring": mean_drop,
            "edge_density": edge_density,
            "compactness": feat_compactness,
            "hull_gap_frac": feat_hull_gap,
            "uncertainty_level": r["uncertainty_level"],
            "primary_error_type": r["primary_error_type"],
            "manual_route": r["routing_decision"],
            "auto_route": auto_route,
            "route_match": bool(auto_route == r["routing_decision"])
        })

    out_dir = ROOT / "outputs" / "urban_phaseB"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_csv = out_dir / "urban_auto_features.csv"

    out = pd.DataFrame(rows)
    out.to_csv(out_csv, index=False)

    print("Saved CSV :", out_csv)
    print()
    print(out[[
        "id", "primary_error_type", "manual_route", "auto_route",
        "dark_frac", "mean_drop_to_ring", "edge_density",
        "compactness", "hull_gap_frac", "route_match"
    ]])
    print()
    print("Route match counts:")
    print(out["route_match"].value_counts(dropna=False))
    print()
    print("Auto routes:")
    print(out["auto_route"].value_counts(dropna=False))

if __name__ == "__main__":
    main()