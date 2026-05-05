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

def main():
    if len(sys.argv) != 2:
        print("Usage: python scripts/urban_exp08a_selective_acceptance.py <config.json>")
        sys.exit(1)

    ROOT = Path(__file__).resolve().parents[1]
    cfg = json.loads((ROOT / sys.argv[1]).read_text())

    exp_name = cfg["experiment_name"]
    routing_csv = ROOT / cfg["routing_table_csv"]
    topo_exp = cfg["topology_pass_experiment"]
    pass1_map = cfg["pass1_experiments"]
    rules = cfg["acceptance_rules"]

    out_dir = ROOT / "outputs" / exp_name
    out_dir.mkdir(parents=True, exist_ok=True)
    out_gpkg = out_dir / "berlin_predictions.gpkg"

    routing = pd.read_csv(routing_csv)

    # load pass1 predictions and reports
    pass1_preds = {}
    pass1_reports = {}
    crs_ref = None

    for short_name, folder in pass1_map.items():
        pred_path = ROOT / "outputs" / folder / "berlin_predictions.gpkg"
        rep_path = ROOT / "outputs" / folder / "berlin_update_report.csv"

        preds = load_layer(pred_path, "predictions")[["id", "orig_wkt", "geometry", "sam_score"]].copy()
        preds = preds.rename(columns={
            "geometry": f"geom_{short_name}",
            "sam_score": f"sam_score_{short_name}",
            "orig_wkt": f"orig_wkt_{short_name}"
        })
        pass1_preds[short_name] = preds

        rep = pd.read_csv(rep_path)[["id", "decision", "iou_map_vs_sam", "sam_score", "area_diff_frac"]].copy()
        rep = rep.rename(columns={
            "decision": f"decision_{short_name}",
            "iou_map_vs_sam": f"iou_map_vs_sam_{short_name}",
            "sam_score": f"sam_score_eval_{short_name}",
            "area_diff_frac": f"area_diff_frac_{short_name}"
        })
        pass1_reports[short_name] = rep

        if crs_ref is None:
            crs_ref = load_layer(pred_path, "predictions").crs

    # load topology pass predictions and report
    topo_pred_path = ROOT / "outputs" / topo_exp / "berlin_predictions.gpkg"
    topo_rep_path = ROOT / "outputs" / topo_exp / "berlin_update_report.csv"

    topo_preds = load_layer(topo_pred_path, "predictions")[["id", "orig_wkt", "geometry", "sam_score"]].copy()
    topo_preds = topo_preds.rename(columns={
        "orig_wkt": "orig_wkt_pass2",
        "geometry": "geom_pass2",
        "sam_score": "sam_score_pass2"
    })

    topo_rep = pd.read_csv(topo_rep_path)[["id", "decision", "iou_map_vs_sam", "sam_score", "area_diff_frac"]].copy()
    topo_rep = topo_rep.rename(columns={
        "decision": "decision_pass2",
        "iou_map_vs_sam": "iou_map_vs_sam_pass2",
        "sam_score": "sam_score_eval_pass2",
        "area_diff_frac": "area_diff_frac_pass2"
    })

    merged = routing.copy()
    for short_name in pass1_map.keys():
        merged = merged.merge(pass1_preds[short_name], on="id", how="left")
        merged = merged.merge(pass1_reports[short_name], on="id", how="left")

    merged = merged.merge(topo_preds, on="id", how="left")
    merged = merged.merge(topo_rep, on="id", how="left")

    rows = []

    for _, r in merged.iterrows():
        obj_id = int(r["id"])
        pass1_source = r["pass1_source"]
        route = r["routing_decision"]

        # select pass1 columns dynamically
        geom_pass1 = r[f"geom_{pass1_source}"]
        orig_wkt = r[f"orig_wkt_{pass1_source}"]
        sam_score_pass1 = float(r[f"sam_score_{pass1_source}"])
        decision_pass1 = r[f"decision_{pass1_source}"]
        iou_pass1 = float(r[f"iou_map_vs_sam_{pass1_source}"])
        area_diff_pass1 = float(r[f"area_diff_frac_{pass1_source}"])

        use_pass2 = False
        acceptance_reason = "not_applicable"

        if route in rules["enabled_routes"]:
            sam_score_pass2 = float(r["sam_score_pass2"])
            decision_pass2 = r["decision_pass2"]
            iou_pass2 = float(r["iou_map_vs_sam_pass2"])
            area_diff_pass2 = float(r["area_diff_frac_pass2"])

            cond_score = sam_score_pass2 >= rules["min_sam_score"]
            cond_iou_drop = iou_pass2 >= (iou_pass1 - rules["max_iou_drop_vs_pass1"])
            cond_area = abs(area_diff_pass2) <= (abs(area_diff_pass1) + rules["max_abs_area_diff_increase_vs_pass1"])
            cond_review = not (rules["reject_if_flag_review"] and decision_pass2 == "flag_review")

            use_pass2 = bool(cond_score and cond_iou_drop and cond_area and cond_review)

            acceptance_reason = (
                f"score={cond_score};"
                f"iou_drop={cond_iou_drop};"
                f"area={cond_area};"
                f"review={cond_review}"
            )

        if use_pass2:
            final_geom = r["geom_pass2"]
            final_sam_score = float(r["sam_score_pass2"])
            selected_source = "pass2_topology"
            second_pass_accepted = True
        else:
            final_geom = geom_pass1
            final_sam_score = sam_score_pass1
            selected_source = f"pass1_{pass1_source}"
            second_pass_accepted = False

        rows.append({
            "id": obj_id,
            "orig_wkt": orig_wkt,
            "sam_score": final_sam_score,
            "routing_decision": route,
            "pass1_source": pass1_source,
            "selected_source": selected_source,
            "second_pass_candidate_available": route in rules["enabled_routes"],
            "second_pass_accepted": second_pass_accepted,
            "acceptance_reason": acceptance_reason,
            "geometry": final_geom
        })

    gdf = gpd.GeoDataFrame(rows, geometry="geometry", crs=crs_ref)
    gdf.to_file(out_gpkg, layer="predictions", driver="GPKG")
    (out_dir / "experiment_config.json").write_text(json.dumps(cfg, indent=2))

    print("Saved:", out_gpkg)
    print("Saved config copy:", out_dir / "experiment_config.json")
    print()
    print(gdf[[
        "id",
        "routing_decision",
        "pass1_source",
        "selected_source",
        "second_pass_candidate_available",
        "second_pass_accepted"
    ]])
    print()
    print("Accepted second pass count:", int(gdf["second_pass_accepted"].sum()))

if __name__ == "__main__":
    main()