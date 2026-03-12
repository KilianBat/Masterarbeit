from pathlib import Path
import pandas as pd
import geopandas as gpd
from shapely import wkt

ROOT = Path(__file__).resolve().parents[1]

pred_path = ROOT / "outputs" / "berlin_predictions.gpkg"
out_gpkg = ROOT / "outputs" / "berlin_update_proposals.gpkg"
out_csv = ROOT / "outputs" / "berlin_update_report.csv"

gdf = gpd.read_file(pred_path, layer="predictions")
gdf["orig_geom"] = gdf["orig_wkt"].apply(wkt.loads)

rows = []
for _, r in gdf.iterrows():
    orig = r["orig_geom"]
    pred = r.geometry

    if pred is None or pred.is_empty:
        rows.append(
            {
                "id": r["id"],
                "sam_score": r["sam_score"],
                "iou_map_vs_sam": 0.0,
                "area_diff_m2": None,
                "area_diff_frac": None,
                "centroid_shift_m": None,
                "decision": "flag_no_prediction",
                "orig_wkt": orig.wkt,
                "geometry": pred,
            }
        )
        continue

    inter = orig.intersection(pred).area
    union = orig.union(pred).area
    iou = 0.0 if union == 0 else inter / union

    area_diff = pred.area - orig.area
    area_diff_frac = None if orig.area == 0 else area_diff / orig.area
    centroid_shift = orig.centroid.distance(pred.centroid)

    if iou >= 0.85 and abs(area_diff_frac) <= 0.15 and centroid_shift <= 2.0:
        decision = "keep"
    elif iou >= 0.25:
        decision = "update"
    else:
        decision = "flag_review"

    rows.append(
        {
            "id": r["id"],
            "sam_score": r["sam_score"],
            "iou_map_vs_sam": float(iou),
            "area_diff_m2": float(area_diff),
            "area_diff_frac": None if area_diff_frac is None else float(area_diff_frac),
            "centroid_shift_m": float(centroid_shift),
            "decision": decision,
            "orig_wkt": orig.wkt,
            "geometry": pred,
        }
    )

out = gpd.GeoDataFrame(rows, geometry="geometry", crs=gdf.crs)
out.to_file(out_gpkg, layer="update_proposals", driver="GPKG")

pd.DataFrame(out.drop(columns="geometry")).to_csv(out_csv, index=False)

print("Saved:", out_gpkg)
print("Saved:", out_csv)
print(out[["iou_map_vs_sam", "sam_score", "decision"]].head(10))
print(out["decision"].value_counts(dropna=False))