from pathlib import Path
import sys
import json
import pandas as pd
import geopandas as gpd
import fiona


def load_layer(path, preferred_layer):
    layers = fiona.listlayers(path)
    layer = preferred_layer if preferred_layer in layers else layers[0]
    return gpd.read_file(path, layer=layer)


def classify_runtime(row, thr):
    decision = row["decision"]
    final_source = row["final_source"]
    sam_score = float(row["sam_score"])
    iou_map_vs_sam = float(row["iou_map_vs_sam"])
    area_abs = abs(float(row["area_diff_frac"]))
    centroid_shift = float(row["centroid_shift_m"])
    route = row.get("routing_decision", None)
    uncertainty = row.get("uncertainty_level", None)
    selected_source = row.get("selected_source", None)
    second_pass_accepted = bool(row.get("second_pass_accepted", False))
    shadow_second_pass_accepted = bool(row.get("shadow_second_pass_accepted", False))

    accepted_special_pass = second_pass_accepted or shadow_second_pass_accepted or selected_source in {"pass2_topology", "shadow_pass2"}

    if decision == "flag_review":
        return "review", "flag_review_from_update_layer"

    if decision == "keep":
        if (
            iou_map_vs_sam >= thr["unchanged_keep_iou_min"]
            and area_abs <= thr["unchanged_keep_area_abs_max"]
            and centroid_shift <= thr["unchanged_keep_centroid_max_m"]
        ):
            return "unchanged", "stable_keep_geometry"
        return "review", "keep_but_not_geometrically_stable"

    if decision == "update":
        if iou_map_vs_sam <= thr["removed_iou_max"] and sam_score <= thr["removed_sam_score_max"]:
            return "removed_candidate", "weak_current_object_evidence"

        strong_modified = (
            sam_score >= thr["modified_sam_score_min"]
            and iou_map_vs_sam >= thr["modified_iou_min"]
            and area_abs <= thr["modified_area_abs_max"]
            and centroid_shift <= thr["modified_centroid_max_m"]
        )

        if strong_modified:
            return "modified", "strong_update_evidence"

        # accept slightly weaker evidence if a specialized pass was explicitly accepted
        if accepted_special_pass and sam_score >= 0.75 and iou_map_vs_sam >= 0.45:
            return "modified", "accepted_specialized_refinement"

        # mixed or unstable update cases
        if uncertainty in {"medium", "high"} or route in {"shadow_refine", "topology_refine", "context_refine"}:
            return "review", "update_but_mixed_evidence"

        return "modified", "default_update_case"

    return "review", "fallback"


def classify_reference(row, ref_cfg):
    if not ref_cfg["enabled"]:
        return None
    iou_orig = float(row["iou_orig2018_vs_osm2025"])
    return "unchanged" if iou_orig >= ref_cfg["ref_unchanged_iou_min"] else "modified"


def main():
    if len(sys.argv) != 2:
        print("Usage: python scripts/urban_classify_change_types.py <config.json>")
        sys.exit(1)

    ROOT = Path(__file__).resolve().parents[1]
    cfg = json.loads((ROOT / sys.argv[1]).read_text())
    exp_name = cfg["experiment_name"]
    thr = cfg["thresholds"]

    pred_path = ROOT / "outputs" / exp_name / "berlin_predictions.gpkg"
    report_path = ROOT / "outputs" / exp_name / "berlin_update_report.csv"
    routing_path = ROOT / cfg["routing_table_csv"]
    uncertainty_path = ROOT / cfg["uncertainty_csv"]
    external_eval_path = ROOT / cfg["external_eval_csv"]

    preds = load_layer(pred_path, "predictions")
    crs_ref = preds.crs

    reports = pd.read_csv(report_path)
    routing = pd.read_csv(routing_path)
    uncertainty = pd.read_csv(uncertainty_path)
    external = pd.read_csv(external_eval_path) if external_eval_path.exists() else None

    pred_cols = ["id", "geometry"]
    for c in ["routing_decision", "selected_source", "second_pass_accepted", "shadow_second_pass_accepted"]:
        if c in preds.columns:
            pred_cols.append(c)
    pred_df = preds[pred_cols].copy()

    df = reports.merge(pred_df, on="id", how="left")
    df = df.merge(routing[["id", "routing_decision", "pass1_source"]], on="id", how="left", suffixes=("", "_route"))
    if "routing_decision_route" in df.columns:
        df["routing_decision"] = df["routing_decision"].fillna(df["routing_decision_route"])
        df = df.drop(columns=["routing_decision_route"])
    df = df.merge(uncertainty[["id", "uncertainty_level"]], on="id", how="left")
    if external is not None:
        df = df.merge(external[["id", "iou_orig2018_vs_osm2025", "iou_final_vs_osm2025", "delta_iou_vs_osm2025", "improved_vs_2018"]], on="id", how="left")

    runtime_types = []
    runtime_reasons = []
    ref_types = []
    matches = []

    for _, row in df.iterrows():
        pred_type, pred_reason = classify_runtime(row, thr)
        runtime_types.append(pred_type)
        runtime_reasons.append(pred_reason)

        ref_type = classify_reference(row, cfg["reference_eval"]) if external is not None else None
        ref_types.append(ref_type)
        matches.append((pred_type == ref_type) if ref_type is not None else None)

    df["predicted_change_type"] = runtime_types
    df["change_type_reason"] = runtime_reasons
    df["reference_change_type"] = ref_types
    df["reference_match"] = matches

    out_dir = ROOT / "outputs" / "urban_change_types"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_csv = out_dir / "urban_change_type_report.csv"
    out_gpkg = out_dir / "urban_change_type_report.gpkg"

    df.drop(columns=["geometry"]).to_csv(out_csv, index=False)
    gdf = gpd.GeoDataFrame(df[[c for c in df.columns if c != "geometry"]].copy(), geometry=pred_df["geometry"], crs=crs_ref)
    if out_gpkg.exists():
        out_gpkg.unlink()
    gdf.to_file(out_gpkg, layer="change_types", driver="GPKG")

    print("Saved CSV :", out_csv)
    print("Saved GPKG:", out_gpkg)
    print()
    show_cols = [
        "id", "decision", "final_source", "routing_decision", "uncertainty_level",
        "predicted_change_type", "change_type_reason"
    ]
    if external is not None:
        show_cols += ["reference_change_type", "reference_match"]
    print(df[show_cols])
    print()
    print("Predicted change types:")
    print(df["predicted_change_type"].value_counts(dropna=False))
    if external is not None:
        print()
        print("Reference change types:")
        print(df["reference_change_type"].value_counts(dropna=False))
        print()
        print("Reference match counts:")
        print(df["reference_match"].value_counts(dropna=False))

if __name__ == "__main__":
    main()
