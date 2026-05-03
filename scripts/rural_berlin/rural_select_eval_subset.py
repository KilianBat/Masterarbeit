from pathlib import Path
import sys
import json
import pandas as pd
import geopandas as gpd
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
        print("Usage: python scripts/rural_select_eval_subset.py <config.json>")
        sys.exit(1)

    ROOT = Path(__file__).resolve().parents[1]
    cfg = json.loads((ROOT / sys.argv[1]).read_text())

    area_name = cfg["area_name"]
    subset_name = cfg["subset_name"]
    hist_date = cfg["osm_date_historic"][:10].replace("-", "")
    sel_cfg = cfg["selection"]

    hist_path = ROOT / "data" / "raw" / f"{area_name}_buildings_{hist_date}.gpkg"
    cur_path = ROOT / "data" / "raw" / f"{area_name}_buildings.gpkg"

    out_dir = ROOT / "data" / "processed" / subset_name
    out_dir.mkdir(parents=True, exist_ok=True)

    out_subset_gpkg = out_dir / "historic_subset.gpkg"
    out_subset_geojson = out_dir / "historic_subset.geojson"
    out_matched_cur_gpkg = out_dir / "matched_current_subset.gpkg"
    out_new_cur_gpkg = out_dir / "new_current_candidates.gpkg"
    out_summary_csv = out_dir / "subset_summary.csv"
    out_full_csv = out_dir / "full_status_summary.csv"

    hist = load_buildings(hist_path)
    cur = load_buildings(cur_path)

    if hist.crs != cur.crs:
        cur = cur.to_crs(hist.crs)

    hist = hist.reset_index(drop=True).copy()
    cur = cur.reset_index(drop=True).copy()

    hist["hist_row_idx"] = hist.index
    cur["cur_row_idx"] = cur.index

    hist["hist_osm_id"] = hist["id"] if "id" in hist.columns else hist.index
    cur["cur_osm_id"] = cur["id"] if "id" in cur.columns else cur.index

    matched_cur_indices = set()
    full_rows = []

    thr_unch = float(sel_cfg["iou_unchanged_threshold"])
    thr_removed = float(sel_cfg["iou_removed_threshold"])

    for _, row_h in hist.iterrows():
        geom_h = row_h.geometry

        best_idx = None
        best_iou = 0.0

        for idx_c, row_c in cur.iterrows():
            val = iou(geom_h, row_c.geometry)
            if val > best_iou:
                best_iou = val
                best_idx = idx_c

        if best_idx is None or best_iou < thr_removed:
            status = "removed_candidate"
            matched_cur_id = None
        elif best_iou >= thr_unch:
            status = "unchanged_candidate"
            matched_cur_indices.add(best_idx)
            matched_cur_id = cur.loc[best_idx, "cur_osm_id"]
        else:
            status = "changed_candidate"
            matched_cur_indices.add(best_idx)
            matched_cur_id = cur.loc[best_idx, "cur_osm_id"]

        full_rows.append({
            "hist_row_idx": int(row_h["hist_row_idx"]),
            "hist_osm_id": row_h["hist_osm_id"],
            "status": status,
            "best_iou_to_2025": float(best_iou),
            "matched_cur_row_idx": None if best_idx is None else int(best_idx),
            "matched_cur_osm_id": matched_cur_id,
            "geometry": geom_h,
        })

    full_gdf = gpd.GeoDataFrame(full_rows, geometry="geometry", crs=hist.crs)

    unchanged = full_gdf[full_gdf["status"] == "unchanged_candidate"].copy()
    changed = full_gdf[full_gdf["status"] == "changed_candidate"].copy()
    removed = full_gdf[full_gdf["status"] == "removed_candidate"].copy()

    n_unch = min(int(sel_cfg["n_unchanged_control"]), len(unchanged))
    unchanged_sample = unchanged.sample(n=n_unch, random_state=int(sel_cfg["random_seed"])) if n_unch > 0 else unchanged.iloc[0:0].copy()

    subset = pd.concat([changed, removed, unchanged_sample], ignore_index=True)
    subset = gpd.GeoDataFrame(subset, geometry="geometry", crs=hist.crs)
    subset["subset_id"] = range(1, len(subset) + 1)

    matched_current = cur[cur["cur_row_idx"].isin(
        [x for x in subset["matched_cur_row_idx"].dropna().astype(int).tolist()]
    )].copy()

    new_current = cur[~cur["cur_row_idx"].isin(matched_cur_indices)].copy()

    if out_subset_gpkg.exists():
        out_subset_gpkg.unlink()
    if out_matched_cur_gpkg.exists():
        out_matched_cur_gpkg.unlink()
    if out_new_cur_gpkg.exists():
        out_new_cur_gpkg.unlink()
    if out_summary_csv.exists():
        out_summary_csv.unlink()
    if out_full_csv.exists():
        out_full_csv.unlink()

    subset.to_file(out_subset_gpkg, layer="buildings", driver="GPKG")
    subset.to_file(out_subset_geojson, driver="GeoJSON")
    if len(matched_current) > 0:
        matched_current.to_file(out_matched_cur_gpkg, layer="buildings", driver="GPKG")
    if len(new_current) > 0:
        new_current.to_file(out_new_cur_gpkg, layer="buildings", driver="GPKG")

    pd.DataFrame(subset.drop(columns="geometry")).to_csv(out_summary_csv, index=False)
    pd.DataFrame(full_gdf.drop(columns="geometry")).to_csv(out_full_csv, index=False)

    print("Saved subset GPKG   :", out_subset_gpkg)
    print("Saved subset GeoJSON:", out_subset_geojson)
    print("Saved summary CSV   :", out_summary_csv)
    print("Saved full CSV      :", out_full_csv)
    if len(matched_current) > 0:
        print("Saved matched 2025  :", out_matched_cur_gpkg)
    if len(new_current) > 0:
        print("Saved new 2025 cand.:", out_new_cur_gpkg)
    print()
    print("Subset status counts:")
    print(subset["status"].value_counts(dropna=False))
    print()
    print("Full status counts:")
    print(full_gdf["status"].value_counts(dropna=False))

if __name__ == "__main__":
    main()