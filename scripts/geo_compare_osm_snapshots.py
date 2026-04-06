from pathlib import Path
import sys
import json
import geopandas as gpd
import pandas as pd
import fiona

def iou(a, b):
    if a is None or b is None or a.is_empty or b.is_empty:
        return 0.0
    inter = a.intersection(b).area
    union = a.union(b).area
    return 0.0 if union == 0 else float(inter / union)

def load_buildings(path):
    layers = fiona.listlayers(path)
    layer = "buildings" if "buildings" in layers else layers[0]
    gdf = gpd.read_file(path, layer=layer)
    gdf = gdf[gdf.geometry.notnull()].copy()
    gdf = gdf[gdf.geom_type.isin(["Polygon", "MultiPolygon"])].copy()
    return gdf

def main():
    if len(sys.argv) != 2:
        print("Usage: python scripts/geo_compare_osm_snapshots.py <config.json>")
        sys.exit(1)

    ROOT = Path(__file__).resolve().parents[1]
    cfg = json.loads((ROOT / sys.argv[1]).read_text())
    area_name = cfg["area_name"]

    hist_path = ROOT / "data" / "raw" / f"{area_name}_buildings_20180101.gpkg"
    cur_path = ROOT / "data" / "raw" / f"{area_name}_buildings.gpkg"

    out_gpkg = ROOT / "outputs" / area_name / "osm_snapshot_diff.gpkg"
    out_csv = ROOT / "outputs" / area_name / "osm_snapshot_diff.csv"
    out_gpkg.parent.mkdir(parents=True, exist_ok=True)

    hist = load_buildings(hist_path)
    cur = load_buildings(cur_path)

    if hist.crs != cur.crs:
        cur = cur.to_crs(hist.crs)

    matched_cur = set()
    rows_hist = []

    for idx_h, row_h in hist.iterrows():
        geom_h = row_h.geometry
        best_idx = None
        best_iou = 0.0

        for idx_c, row_c in cur.iterrows():
            geom_c = row_c.geometry
            val = iou(geom_h, geom_c)
            if val > best_iou:
                best_iou = val
                best_idx = idx_c

        if best_idx is None or best_iou < 0.1:
            status = "removed_candidate"
        elif best_iou >= 0.85:
            status = "unchanged_candidate"
            matched_cur.add(best_idx)
        else:
            status = "changed_candidate"
            matched_cur.add(best_idx)

        rows_hist.append({
            "source": "osm_2018",
            "status": status,
            "best_iou_to_2025": float(best_iou),
            "geometry": geom_h,
        })

    rows_cur = []
    for idx_c, row_c in cur.iterrows():
        if idx_c not in matched_cur:
            rows_cur.append({
                "source": "osm_2025",
                "status": "new_candidate",
                "best_iou_to_2018": 0.0,
                "geometry": row_c.geometry,
            })

    gdf_hist = gpd.GeoDataFrame(rows_hist, geometry="geometry", crs=hist.crs)
    gdf_cur = gpd.GeoDataFrame(rows_cur, geometry="geometry", crs=hist.crs)

    if out_gpkg.exists():
        out_gpkg.unlink()
    if out_csv.exists():
        out_csv.unlink()

    gdf_hist.to_file(out_gpkg, layer="historic_2018", driver="GPKG")
    if len(gdf_cur) > 0:
        gdf_cur.to_file(out_gpkg, layer="new_2025", driver="GPKG")

    summary = pd.concat([
        pd.DataFrame(gdf_hist.drop(columns="geometry")),
        pd.DataFrame(gdf_cur.drop(columns="geometry")) if len(gdf_cur) > 0 else pd.DataFrame()
    ], ignore_index=True)
    summary.to_csv(out_csv, index=False)

    print("Saved GPKG:", out_gpkg)
    print("Saved CSV :", out_csv)
    print()
    print("2018 statuses:")
    print(gdf_hist["status"].value_counts(dropna=False))
    if len(gdf_cur) > 0:
        print()
        print("2025-only new candidates:", len(gdf_cur))

if __name__ == "__main__":
    main()