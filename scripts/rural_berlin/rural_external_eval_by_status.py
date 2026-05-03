from pathlib import Path
import sys
import json
import numpy as np
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

def load_buildings(path):
    layers = fiona.listlayers(path)
    layer = "buildings" if "buildings" in layers else layers[0]
    gdf = gpd.read_file(path, layer=layer)
    gdf = gdf[gdf.geometry.notnull()].copy()
    gdf = gdf[gdf.geom_type.isin(["Polygon", "MultiPolygon"])].copy()
    return gdf, layer

def best_match_to_any(geom, ref_gdf):
    best_idx = None
    best_iou = 0.0
    best_dist = float("inf")

    for idx, ref_geom in ref_gdf.geometry.items():
        val = iou(geom, ref_geom)
        dist = geom.distance(ref_geom) if geom is not None and not geom.is_empty else float("inf")
        if (val > best_iou) or (val == best_iou and dist < best_dist):
            best_iou = val
            best_idx = idx
            best_dist = dist

    return best_idx, float(best_iou), float(best_dist)

def main():
    if len(sys.argv) != 2:
        print("Usage: python scripts/rural_external_eval_by_status.py <config.json>")
        sys.exit(1)

    ROOT = Path(__file__).resolve().parents[1]
    cfg = json.loads((ROOT / sys.argv[1]).read_text())

    exp_name = cfg["experiment_name"]
    manifest_path = ROOT / cfg["manifest_path"]
    current_osm_path = ROOT / cfg["current_osm_path"]

    exp_gpkg = ROOT / "outputs" / exp_name / "berlin_update_proposals.gpkg"
    out_csv = ROOT / "outputs" / exp_name / "rural_external_eval_by_status.csv"
    out_gpkg = ROOT / "outputs" / exp_name / "rural_external_eval_by_status.gpkg"

    eval_gdf = gpd.read_file(exp_gpkg, layer="update_product")
    eval_gdf["orig_geom"] = eval_gdf["orig_wkt"].apply(wkt.loads)

    manifest = pd.read_csv(manifest_path)

    cur_gdf, cur_layer = load_buildings(current_osm_path)
    if cur_gdf.crs != eval_gdf.crs:
        cur_gdf = cur_gdf.to_crs(eval_gdf.crs)

    if "id" in cur_gdf.columns:
        cur_id_to_idx = {str(v): idx for idx, v in cur_gdf["id"].astype(str).items()}
    else:
        cur_id_to_idx = {}

    merged = eval_gdf.merge(
        manifest[["id", "hist_osm_id", "status_2018_to_2025", "matched_cur_osm_id", "best_iou_to_2025"]],
        on="id",
        how="left"
    )

    rows_eval = []
    rows_ref = []
    rows_orig = []

    for _, r in merged.iterrows():
        obj_id = int(r["id"])
        status = r["status_2018_to_2025"]
        orig_geom = r["orig_geom"]
        final_geom = r.geometry

        matched_cur_osm_id = r["matched_cur_osm_id"]
        ref_geom = None
        ref_idx = None

        if pd.notna(matched_cur_osm_id):
            ref_idx = cur_id_to_idx.get(str(int(matched_cur_osm_id)) if float(matched_cur_osm_id).is_integer() else str(matched_cur_osm_id), None)
            if ref_idx is not None:
                ref_geom = cur_gdf.loc[ref_idx].geometry

        record = {
            "id": obj_id,
            "status_2018_to_2025": status,
            "decision": r.get("decision", None),
            "final_source": r.get("final_source", None),
            "hist_osm_id": r.get("hist_osm_id", None),
            "matched_cur_osm_id": matched_cur_osm_id,
            "orig_wkt": orig_geom.wkt,
            "geometry": final_geom,
        }

        # unchanged / changed: compare to matched current object
        if status in {"unchanged_candidate", "changed_candidate"} and ref_geom is not None:
            iou_orig = iou(orig_geom, ref_geom)
            iou_final = iou(final_geom, ref_geom)

            record.update({
                "eval_mode": "matched_reference",
                "iou_orig2018_vs_osm2025": float(iou_orig),
                "iou_final_vs_osm2025": float(iou_final),
                "delta_iou_vs_osm2025": float(iou_final - iou_orig),
                "dist_orig_to_osm2025_m": float(orig_geom.distance(ref_geom)),
                "dist_final_to_osm2025_m": float(final_geom.distance(ref_geom)),
                "improved_vs_2018": bool(iou_final > iou_orig),
                "max_iou_orig_to_any_2025": np.nan,
                "max_iou_final_to_any_2025": np.nan,
                "removed_behavior": None,
            })

            rows_ref.append({
                "id": obj_id,
                "status_2018_to_2025": status,
                "geometry": ref_geom,
            })

        # removed: evaluate against all current buildings
        elif status == "removed_candidate":
            best_idx_orig, max_iou_orig, best_dist_orig = best_match_to_any(orig_geom, cur_gdf)
            best_idx_final, max_iou_final, best_dist_final = best_match_to_any(final_geom, cur_gdf)

            if max_iou_final < 0.10:
                removed_behavior = "still_removed_like"
            elif max_iou_final < 0.25:
                removed_behavior = "weak_overlap_with_current"
            else:
                removed_behavior = "snapped_to_current_building"

            record.update({
                "eval_mode": "removed_against_any_current",
                "iou_orig2018_vs_osm2025": np.nan,
                "iou_final_vs_osm2025": np.nan,
                "delta_iou_vs_osm2025": np.nan,
                "dist_orig_to_osm2025_m": np.nan,
                "dist_final_to_osm2025_m": np.nan,
                "improved_vs_2018": None,
                "max_iou_orig_to_any_2025": float(max_iou_orig),
                "max_iou_final_to_any_2025": float(max_iou_final),
                "removed_behavior": removed_behavior,
            })

            if best_idx_final is not None:
                rows_ref.append({
                    "id": obj_id,
                    "status_2018_to_2025": status,
                    "geometry": cur_gdf.loc[best_idx_final].geometry,
                })

        else:
            record.update({
                "eval_mode": "unmatched",
                "iou_orig2018_vs_osm2025": np.nan,
                "iou_final_vs_osm2025": np.nan,
                "delta_iou_vs_osm2025": np.nan,
                "dist_orig_to_osm2025_m": np.nan,
                "dist_final_to_osm2025_m": np.nan,
                "improved_vs_2018": None,
                "max_iou_orig_to_any_2025": np.nan,
                "max_iou_final_to_any_2025": np.nan,
                "removed_behavior": None,
            })

        rows_eval.append(record)
        rows_orig.append({
            "id": obj_id,
            "status_2018_to_2025": status,
            "geometry": orig_geom,
        })

    gdf_eval = gpd.GeoDataFrame(rows_eval, geometry="geometry", crs=eval_gdf.crs)
    gdf_ref = gpd.GeoDataFrame(rows_ref, geometry="geometry", crs=eval_gdf.crs)
    gdf_orig = gpd.GeoDataFrame(rows_orig, geometry="geometry", crs=eval_gdf.crs)

    if out_gpkg.exists():
        out_gpkg.unlink()
    if out_csv.exists():
        out_csv.unlink()

    gdf_eval.to_file(out_gpkg, layer="external_eval", driver="GPKG")
    if len(gdf_ref) > 0:
        gdf_ref.to_file(out_gpkg, layer="matched_or_nearest_2025", driver="GPKG")
    gdf_orig.to_file(out_gpkg, layer="orig_2018", driver="GPKG")

    pd.DataFrame(gdf_eval.drop(columns="geometry")).to_csv(out_csv, index=False)

    print("Loaded current OSM layer:", cur_layer)
    print("Saved CSV :", out_csv)
    print("Saved GPKG:", out_gpkg)
    print()

    # unchanged / changed summary
    uc = gdf_eval[gdf_eval["status_2018_to_2025"].isin(["unchanged_candidate", "changed_candidate"])].copy()
    if len(uc) > 0:
        print("Matched-reference summary (unchanged + changed):")
        print(
            uc.groupby("status_2018_to_2025")[[
                "iou_orig2018_vs_osm2025",
                "iou_final_vs_osm2025",
                "delta_iou_vs_osm2025",
                "dist_orig_to_osm2025_m",
                "dist_final_to_osm2025_m"
            ]].mean()
        )
        print()
        print("Improvement counts:")
        print(uc.groupby("status_2018_to_2025")["improved_vs_2018"].value_counts(dropna=False))

    # removed summary
    rem = gdf_eval[gdf_eval["status_2018_to_2025"] == "removed_candidate"].copy()
    if len(rem) > 0:
        print()
        print("Removed-candidate summary:")
        print(
            rem[[
                "max_iou_orig_to_any_2025",
                "max_iou_final_to_any_2025"
            ]].describe()
        )
        print()
        print("Removed behavior counts:")
        print(rem["removed_behavior"].value_counts(dropna=False))

if __name__ == "__main__":
    main()