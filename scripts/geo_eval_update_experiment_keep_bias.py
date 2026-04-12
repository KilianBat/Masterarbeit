from pathlib import Path
import sys
import json
import pandas as pd
import geopandas as gpd
from shapely import wkt
import fiona

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
        print("Usage: python scripts/geo_eval_update_experiment_keep_bias.py <config.json>")
        sys.exit(1)

    ROOT = Path(__file__).resolve().parents[1]
    cfg = json.loads((ROOT / sys.argv[1]).read_text())

    exp_name = cfg["experiment_name"]
    rules = cfg["decision_rules"]

    pred_gpkg = ROOT / "outputs" / exp_name / "berlin_predictions.gpkg"
    out_gpkg = ROOT / "outputs" / exp_name / "berlin_update_proposals.gpkg"
    out_csv = ROOT / "outputs" / exp_name / "berlin_update_report.csv"

    preds = gpd.read_file(pred_gpkg, layer="predictions")
    preds["orig_geom"] = preds["orig_wkt"].apply(wkt.loads)

    rows = []
    layers_update = []
    layers_orig = []
    layers_pred = []

    for _, r in preds.iterrows():
        orig = r["orig_geom"]
        pred = r.geometry
        score = float(r["sam_score"])

        iou_map_vs_sam = iou(orig, pred)
        area_diff_frac = 0.0 if orig.area == 0 else float((pred.area - orig.area) / orig.area)
        centroid_shift_m = centroid_shift(orig, pred)

        abs_area_diff = abs(area_diff_frac)

        stable_keep = (
            iou_map_vs_sam >= rules["keep_if_iou_ge"] and
            abs_area_diff <= rules["keep_if_abs_area_diff_le"] and
            centroid_shift_m <= rules["keep_if_centroid_shift_le_m"]
        )

        strong_update = (
            score >= rules["update_if_score_ge"] and
            iou_map_vs_sam <= rules["update_if_iou_le"] and
            abs_area_diff >= rules["update_if_abs_area_diff_ge"] and
            centroid_shift_m >= rules["update_if_centroid_shift_ge_m"]
        )

        review_case = (
            score >= rules["review_if_score_ge"] and (
                iou_map_vs_sam <= rules["review_if_iou_le"] or
                abs_area_diff >= rules["review_if_abs_area_diff_ge"] or
                centroid_shift_m >= rules["review_if_centroid_shift_ge_m"]
            )
        )

        if stable_keep:
            decision = "keep"
            final_source = "osm"
            final_geom = orig
        elif strong_update:
            decision = "update"
            final_source = "sam2"
            final_geom = pred
        elif review_case:
            decision = "flag_review"
            final_source = "osm_review"
            final_geom = orig
        else:
            decision = "keep"
            final_source = "osm"
            final_geom = orig

        rows.append({
            "id": r["id"],
            "decision": decision,
            "final_source": final_source,
            "iou_map_vs_sam": iou_map_vs_sam,
            "sam_score": score,
            "area_diff_frac": area_diff_frac,
            "centroid_shift_m": centroid_shift_m,
            "orig_wkt": orig.wkt,
            "geometry": final_geom,
        })

        layers_update.append({
            "id": r["id"],
            "decision": decision,
            "final_source": final_source,
            "orig_wkt": orig.wkt,
            "geometry": final_geom,
        })
        layers_orig.append({
            "id": r["id"],
            "geometry": orig,
        })
        layers_pred.append({
            "id": r["id"],
            "sam_score": score,
            "geometry": pred,
        })

    gdf_update = gpd.GeoDataFrame(layers_update, geometry="geometry", crs=preds.crs)
    gdf_orig = gpd.GeoDataFrame(layers_orig, geometry="geometry", crs=preds.crs)
    gdf_pred = gpd.GeoDataFrame(layers_pred, geometry="geometry", crs=preds.crs)

    if out_gpkg.exists():
        out_gpkg.unlink()
    if out_csv.exists():
        out_csv.unlink()

    gdf_update.to_file(out_gpkg, layer="update_product", driver="GPKG")
    gdf_orig.to_file(out_gpkg, layer="original_osm", driver="GPKG")
    gdf_pred.to_file(out_gpkg, layer="predicted_sam2", driver="GPKG")

    pd.DataFrame(rows).to_csv(out_csv, index=False)

    print("Saved GPKG:", out_gpkg)
    print("Saved CSV :", out_csv)
    print()
    print(pd.DataFrame(rows)[["id", "decision", "final_source", "iou_map_vs_sam", "sam_score"]].head(10))
    print()
    print("Decision counts:")
    print(pd.DataFrame(rows)["decision"].value_counts(dropna=False))
    print()
    print("Final source counts:")
    print(pd.DataFrame(rows)["final_source"].value_counts(dropna=False))

if __name__ == "__main__":
    main()