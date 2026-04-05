from pathlib import Path
import sys
import pandas as pd
import geopandas as gpd
import fiona
from shapely import wkt

def iou(a, b):
    if a is None or b is None or a.is_empty or b.is_empty:
        return 0.0
    inter = a.intersection(b).area
    union = a.union(b).area
    return 0.0 if union == 0 else float(inter / union)

def best_match(row_orig, row_final, ref_gdf):
    """
    Match to the 2025 OSM object that best corresponds to this building.
    We choose the candidate maximizing max(IoU(final, ref), IoU(orig, ref)).
    Ties are broken by centroid distance to original geometry.
    """
    orig = row_orig
    final = row_final

    best_idx = None
    best_combined = -1.0
    best_dist = float("inf")

    for idx, ref in ref_gdf.geometry.items():
        iou_final = iou(final, ref)
        iou_orig = iou(orig, ref)
        combined = max(iou_final, iou_orig)

        dist = orig.centroid.distance(ref.centroid) if (orig is not None and not orig.is_empty) else float("inf")

        if (combined > best_combined) or (combined == best_combined and dist < best_dist):
            best_combined = combined
            best_dist = dist
            best_idx = idx

    return best_idx

def load_osm2025(path):
    layers = fiona.listlayers(path)
    layer = "buildings" if "buildings" in layers else layers[0]
    gdf = gpd.read_file(path, layer=layer)
    gdf = gdf[gdf.geometry.notnull()].copy()
    gdf = gdf[gdf.geom_type.isin(["Polygon", "MultiPolygon"])].copy()
    return gdf, layer

def main():
    if len(sys.argv) != 2:
        print("Usage: python scripts/eval_against_osm2025.py <experiment_name>")
        sys.exit(1)

    ROOT = Path(__file__).resolve().parents[1]
    exp_name = sys.argv[1]

    exp_gpkg = ROOT / "outputs" / exp_name / "berlin_update_proposals.gpkg"
    out_csv = ROOT / "outputs" / exp_name / "external_eval_osm2025.csv"
    out_gpkg = ROOT / "outputs" / exp_name / "external_eval_osm2025.gpkg"

    osm2025_path = ROOT / "data" / "raw" / "berlin_buildings.gpkg"

    if out_csv.exists():
        out_csv.unlink()
    if out_gpkg.exists():
        out_gpkg.unlink()

    exp_gdf = gpd.read_file(exp_gpkg, layer="update_product")
    exp_gdf["orig_geom"] = exp_gdf["orig_wkt"].apply(wkt.loads)

    ref_gdf, ref_layer = load_osm2025(osm2025_path)

    # same CRS
    if ref_gdf.crs != exp_gdf.crs:
        ref_gdf = ref_gdf.to_crs(exp_gdf.crs)

    rows_eval = []
    rows_ref = []
    rows_orig = []

    ref_id_col = "id" if "id" in ref_gdf.columns else None

    for _, r in exp_gdf.iterrows():
        obj_id = r["id"]
        final_geom = r.geometry
        orig_geom = r["orig_geom"]

        match_idx = best_match(orig_geom, final_geom, ref_gdf)
        ref_row = ref_gdf.loc[match_idx]
        ref_geom = ref_row.geometry

        iou_final = iou(final_geom, ref_geom)
        iou_orig = iou(orig_geom, ref_geom)

        area_diff_final = None if ref_geom.area == 0 else float((final_geom.area - ref_geom.area) / ref_geom.area)
        area_diff_orig = None if ref_geom.area == 0 else float((orig_geom.area - ref_geom.area) / ref_geom.area)

        centroid_shift_final = float(final_geom.centroid.distance(ref_geom.centroid))
        centroid_shift_orig = float(orig_geom.centroid.distance(ref_geom.centroid))

        improved = iou_final > iou_orig
        delta_iou = float(iou_final - iou_orig)

        rows_eval.append({
            "id": obj_id,
            "decision": r.get("decision", None),
            "final_source": r.get("final_source", None),
            "iou_final_vs_osm2025": float(iou_final),
            "iou_orig2018_vs_osm2025": float(iou_orig),
            "delta_iou_vs_osm2025": delta_iou,
            "centroid_shift_final_vs_osm2025_m": centroid_shift_final,
            "centroid_shift_orig2018_vs_osm2025_m": centroid_shift_orig,
            "area_diff_final_vs_osm2025_frac": area_diff_final,
            "area_diff_orig2018_vs_osm2025_frac": area_diff_orig,
            "improved_vs_2018": bool(improved),
            "matched_ref_index": int(match_idx),
            "matched_ref_id": None if ref_id_col is None else ref_row[ref_id_col],
            "orig_wkt": orig_geom.wkt,
            "geometry": final_geom,
        })

        rows_ref.append({
            "id": obj_id,
            "matched_ref_index": int(match_idx),
            "matched_ref_id": None if ref_id_col is None else ref_row[ref_id_col],
            "geometry": ref_geom,
        })

        rows_orig.append({
            "id": obj_id,
            "source": "orig_2018",
            "geometry": orig_geom,
        })

    gdf_eval = gpd.GeoDataFrame(rows_eval, geometry="geometry", crs=exp_gdf.crs)
    gdf_ref = gpd.GeoDataFrame(rows_ref, geometry="geometry", crs=exp_gdf.crs)
    gdf_orig = gpd.GeoDataFrame(rows_orig, geometry="geometry", crs=exp_gdf.crs)

    gdf_eval.to_file(out_gpkg, layer="external_eval", driver="GPKG")
    gdf_ref.to_file(out_gpkg, layer="matched_osm2025", driver="GPKG")
    gdf_orig.to_file(out_gpkg, layer="orig_2018", driver="GPKG")

    pd.DataFrame(gdf_eval.drop(columns="geometry")).to_csv(out_csv, index=False)

    print("Loaded 2025 OSM layer:", ref_layer)
    print("Saved CSV :", out_csv)
    print("Saved GPKG:", out_gpkg)
    print()
    print(gdf_eval[[
        "id",
        "iou_orig2018_vs_osm2025",
        "iou_final_vs_osm2025",
        "delta_iou_vs_osm2025",
        "improved_vs_2018"
    ]].head(10))
    print()
    print("Mean IoU orig2018 -> osm2025:", round(gdf_eval["iou_orig2018_vs_osm2025"].mean(), 6))
    print("Mean IoU final    -> osm2025:", round(gdf_eval["iou_final_vs_osm2025"].mean(), 6))
    print("Mean delta IoU:", round(gdf_eval["delta_iou_vs_osm2025"].mean(), 6))
    print("Improved objects:", int(gdf_eval["improved_vs_2018"].sum()), "/", len(gdf_eval))

if __name__ == "__main__":
    main()