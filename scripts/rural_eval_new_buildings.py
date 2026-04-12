from pathlib import Path
import sys
import json
import pandas as pd
import geopandas as gpd
from shapely import wkt

def iou(a, b):
    if a is None or b is None or a.is_empty or b.is_empty:
        return 0.0
    inter = a.intersection(b).area
    union = a.union(b).area
    return 0.0 if union == 0 else float(inter / union)

def centroid_shift(a, b):
    if a is None or b is None or a.is_empty or b.is_empty:
        return float("inf")
    return float(a.centroid.distance(b.centroid))

def main():
    if len(sys.argv) != 2:
        print("Usage: python scripts/rural_eval_new_buildings.py <config.json>")
        sys.exit(1)

    ROOT = Path(__file__).resolve().parents[1]
    cfg = json.loads((ROOT / sys.argv[1]).read_text())

    exp_name = cfg["experiment_name"]

    pred_gpkg = ROOT / "outputs" / exp_name / "new_predictions.gpkg"
    out_csv = ROOT / "outputs" / exp_name / "new_eval_report.csv"
    out_gpkg = ROOT / "outputs" / exp_name / "new_eval_layers.gpkg"

    preds = gpd.read_file(pred_gpkg, layer="predictions")
    preds["current_geom"] = preds["current_wkt"].apply(wkt.loads)

    rows = []
    layers_pred = []
    layers_ref = []

    for _, r in preds.iterrows():
        ref = r["current_geom"]
        pred = r.geometry
        score = float(r["sam_score"])

        val_iou = iou(pred, ref)
        area_diff_frac = 0.0 if ref.area == 0 else float((pred.area - ref.area) / ref.area)
        shift_m = centroid_shift(pred, ref)

        if val_iou >= 0.60:
            detection = "detected_good"
        elif val_iou >= 0.30:
            detection = "detected_partial"
        else:
            detection = "missed"

        rows.append({
            "id": r["id"],
            "current_osm_id": r.get("current_osm_id", None),
            "sam_score": score,
            "iou_pred_vs_current2025": val_iou,
            "area_diff_frac": area_diff_frac,
            "centroid_shift_m": shift_m,
            "detection": detection,
            "current_wkt": ref.wkt,
            "geometry": pred,
        })

        layers_pred.append({
            "id": r["id"],
            "sam_score": score,
            "detection": detection,
            "geometry": pred,
        })
        layers_ref.append({
            "id": r["id"],
            "geometry": ref,
        })

    gdf_eval = gpd.GeoDataFrame(rows, geometry="geometry", crs=preds.crs)
    gdf_pred = gpd.GeoDataFrame(layers_pred, geometry="geometry", crs=preds.crs)
    gdf_ref = gpd.GeoDataFrame(layers_ref, geometry="geometry", crs=preds.crs)

    if out_gpkg.exists():
        out_gpkg.unlink()
    if out_csv.exists():
        out_csv.unlink()

    gdf_eval.to_file(out_gpkg, layer="eval", driver="GPKG")
    gdf_pred.to_file(out_gpkg, layer="predicted_sam2", driver="GPKG")
    gdf_ref.to_file(out_gpkg, layer="current_osm_2025", driver="GPKG")

    pd.DataFrame(gdf_eval.drop(columns="geometry")).to_csv(out_csv, index=False)

    print("Saved CSV :", out_csv)
    print("Saved GPKG:", out_gpkg)
    print()
    print(gdf_eval[["id", "sam_score", "iou_pred_vs_current2025", "detection"]].head(10))
    print()
    print("Detection counts:")
    print(gdf_eval["detection"].value_counts(dropna=False))
    print()
    print("Mean IoU:", round(gdf_eval["iou_pred_vs_current2025"].mean(), 6))

if __name__ == "__main__":
    main()