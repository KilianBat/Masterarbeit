from pathlib import Path
import sys
import json
import pandas as pd
import geopandas as gpd
from shapely import wkt

def main():
    if len(sys.argv) != 2:
        print("Usage: python scripts/geo_eval_update_experiment.py <config.json>")
        sys.exit(1)

    ROOT = Path(__file__).resolve().parents[1]
    cfg_path = ROOT / sys.argv[1]
    exp_cfg = json.loads(cfg_path.read_text())
    exp_name = exp_cfg["experiment_name"]

    pred_path = ROOT / "outputs" / exp_name / "berlin_predictions.gpkg"
    out_gpkg = ROOT / "outputs" / exp_name / "berlin_update_proposals.gpkg"
    out_csv = ROOT / "outputs" / exp_name / "berlin_update_report.csv"

    if out_gpkg.exists():
        out_gpkg.unlink()
    if out_csv.exists():
        out_csv.unlink()

    gdf = gpd.read_file(pred_path, layer="predictions")
    gdf["orig_geom"] = gdf["orig_wkt"].apply(wkt.loads)

    rows_final = []
    rows_orig = []
    rows_pred = []

    for _, r in gdf.iterrows():
        obj_id = r["id"]
        sam_score = r["sam_score"]
        orig = r["orig_geom"]
        pred = r.geometry

        rows_orig.append({
            "id": obj_id,
            "source": "osm",
            "geometry": orig,
        })

        rows_pred.append({
            "id": obj_id,
            "source": "sam2",
            "sam_score": sam_score,
            "n_pos": r.get("n_pos", None),
            "n_neg": r.get("n_neg", None),
            "geometry": pred,
        })

        if pred is None or pred.is_empty:
            iou = 0.0
            area_diff = None
            area_diff_frac = None
            centroid_shift = None
            decision = "flag_no_prediction"

            final_geom = orig
            final_source = "osm_review"
            pred_wkt = None
        else:
            inter = orig.intersection(pred).area
            union = orig.union(pred).area
            iou = 0.0 if union == 0 else inter / union

            area_diff = pred.area - orig.area
            area_diff_frac = None if orig.area == 0 else area_diff / orig.area
            centroid_shift = orig.centroid.distance(pred.centroid)

            if iou >= 0.85 and abs(area_diff_frac) <= 0.15 and centroid_shift <= 2.0:
                decision = "keep"
                final_geom = orig
                final_source = "osm"
            elif iou >= 0.25:
                decision = "update"
                final_geom = pred
                final_source = "sam2"
            else:
                decision = "flag_review"
                final_geom = orig
                final_source = "osm_review"

            pred_wkt = pred.wkt

        rows_final.append({
            "id": obj_id,
            "decision": decision,
            "final_source": final_source,
            "sam_score": sam_score,
            "iou_map_vs_sam": float(iou),
            "area_diff_m2": None if area_diff is None else float(area_diff),
            "area_diff_frac": None if area_diff_frac is None else float(area_diff_frac),
            "centroid_shift_m": None if centroid_shift is None else float(centroid_shift),
            "orig_wkt": orig.wkt,
            "pred_wkt": pred_wkt,
            "geometry": final_geom,
        })

    crs = gdf.crs

    gdf_final = gpd.GeoDataFrame(rows_final, geometry="geometry", crs=crs)
    gdf_orig = gpd.GeoDataFrame(rows_orig, geometry="geometry", crs=crs)
    gdf_pred = gpd.GeoDataFrame(rows_pred, geometry="geometry", crs=crs)

    gdf_final.to_file(out_gpkg, layer="update_product", driver="GPKG")
    gdf_orig.to_file(out_gpkg, layer="original_osm", driver="GPKG")
    gdf_pred.to_file(out_gpkg, layer="predicted_sam2", driver="GPKG")

    pd.DataFrame(gdf_final.drop(columns="geometry")).to_csv(out_csv, index=False)

    print("Saved GPKG:", out_gpkg)
    print("Saved CSV :", out_csv)
    print()
    print(gdf_final[["id", "decision", "final_source", "iou_map_vs_sam", "sam_score"]].head(10))
    print()
    print("Decision counts:")
    print(gdf_final["decision"].value_counts(dropna=False))
    print()
    print("Final source counts:")
    print(gdf_final["final_source"].value_counts(dropna=False))


if __name__ == "__main__":
    main()