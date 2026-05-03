from pathlib import Path
import sys
import json
import itertools
import numpy as np
import pandas as pd
import geopandas as gpd
import fiona


def iou(a, b):
    if a is None or b is None or a.is_empty or b.is_empty:
        return 0.0
    inter = a.intersection(b).area
    union = a.union(b).area
    return 0.0 if union == 0 else float(inter / union)


def load_layer(path, preferred_layer):
    layers = fiona.listlayers(path)
    layer = preferred_layer if preferred_layer in layers else layers[0]
    return gpd.read_file(path, layer=layer)


def main():
    if len(sys.argv) != 2:
        print("Usage: python scripts/urban_phaseA_uncertainty_from_existing.py <config.json>")
        sys.exit(1)

    ROOT = Path(__file__).resolve().parents[1]
    cfg = json.loads((ROOT / sys.argv[1]).read_text())

    taxonomy_path = ROOT / cfg["taxonomy_csv"]
    exp_names = cfg["experiments"]
    thr = cfg["thresholds"]

    out_dir = ROOT / "outputs" / "urban_phaseA"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_csv = out_dir / "urban_uncertainty_summary.csv"
    out_gpkg = out_dir / "urban_uncertainty_summary.gpkg"

    tax = pd.read_csv(taxonomy_path)

    pred_tables = {}
    decision_tables = {}

    crs_ref = None

    for exp in exp_names:
        pred_path = ROOT / "outputs" / exp / "berlin_predictions.gpkg"
        upd_path = ROOT / "outputs" / exp / "berlin_update_proposals.gpkg"

        preds = load_layer(pred_path, "predictions")[["id", "geometry", "sam_score"]].copy()
        preds = preds.rename(columns={
            "geometry": f"geom_{exp}",
            "sam_score": f"sam_score_{exp}"
        })

        upd = load_layer(upd_path, "update_product")[["id", "decision", "final_source"]].copy()
        upd = upd.rename(columns={
            "decision": f"decision_{exp}",
            "final_source": f"final_source_{exp}"
        })

        pred_tables[exp] = preds
        decision_tables[exp] = upd

        if crs_ref is None:
            crs_ref = load_layer(pred_path, "predictions").crs

    merged = tax.copy()

    for exp in exp_names:
        merged = merged.merge(pred_tables[exp], on="id", how="left")
        merged = merged.merge(decision_tables[exp], on="id", how="left")

    rows = []
    geom_rows = []

    pairs = list(itertools.combinations(exp_names, 2))

    for _, r in merged.iterrows():
        obj_id = int(r["id"])

        geoms = {exp: r[f"geom_{exp}"] for exp in exp_names}
        decisions = [r[f"decision_{exp}"] for exp in exp_names]
        scores = [float(r[f"sam_score_{exp}"]) for exp in exp_names if pd.notna(r[f"sam_score_{exp}"])]

        pairwise_ious = []
        areas = []
        centroids = []

        for exp in exp_names:
            g = geoms[exp]
            if g is not None and not g.is_empty:
                areas.append(float(g.area))
                c = g.centroid
                centroids.append((c.x, c.y))

        for a, b in pairs:
            pairwise_ious.append(iou(geoms[a], geoms[b]))

        mean_pairwise_iou = float(np.mean(pairwise_ious)) if pairwise_ious else np.nan

        if len(areas) > 1 and np.mean(areas) > 0:
            area_cv = float(np.std(areas) / np.mean(areas))
        else:
            area_cv = 0.0

        if len(centroids) > 1:
            centroid_arr = np.array(centroids, dtype=float)
            center = centroid_arr.mean(axis=0)
            dists = np.linalg.norm(centroid_arr - center, axis=1)
            centroid_spread = float(np.mean(dists))
        else:
            centroid_spread = 0.0

        decision_disagreement = len(set([d for d in decisions if pd.notna(d)])) > 1

        # simple uncertainty scoring
        uncertainty_points = 0

        if mean_pairwise_iou < thr["pairwise_iou_low"]:
            uncertainty_points += 2
        elif mean_pairwise_iou < thr["pairwise_iou_medium"]:
            uncertainty_points += 1

        if area_cv > thr["area_cv_high"]:
            uncertainty_points += 2
        elif area_cv > thr["area_cv_medium"]:
            uncertainty_points += 1

        if centroid_spread > thr["centroid_spread_high_m"]:
            uncertainty_points += 2
        elif centroid_spread > thr["centroid_spread_medium_m"]:
            uncertainty_points += 1

        if decision_disagreement:
            uncertainty_points += 1

        if uncertainty_points >= 4:
            uncertainty_level = "high"
        elif uncertainty_points >= 2:
            uncertainty_level = "medium"
        else:
            uncertainty_level = "low"

        primary_error = r.get("primary_error_type", "")
        secondary_error = r.get("secondary_error_type", "")

        if uncertainty_level == "low" or primary_error == "stable_case":
            suggested_refinement = "no_refine"
        elif primary_error in {"shadow_roof"}:
            suggested_refinement = "shadow_refine"
        elif primary_error in {"courtyard_structure", "multi_level_roof", "multi_part_roof"}:
            suggested_refinement = "topology_refine"
        elif primary_error in {"neighbor_merge", "wrong_building_focus"}:
            suggested_refinement = "context_refine"
        elif primary_error in {"oversegmentation", "undersegmentation", "polygon_geometry"}:
            suggested_refinement = "geometry_refine"
        else:
            suggested_refinement = "manual_review"

        best_exp = r.get("best_experiment_so_far", None)

        row = {
            "id": obj_id,
            "primary_error_type": primary_error,
            "secondary_error_type": secondary_error,
            "best_experiment_so_far": best_exp,
            "mean_pairwise_iou": mean_pairwise_iou,
            "area_cv": area_cv,
            "centroid_spread_m": centroid_spread,
            "decision_disagreement": bool(decision_disagreement),
            "uncertainty_points": uncertainty_points,
            "uncertainty_level": uncertainty_level,
            "suggested_refinement": suggested_refinement,
        }

        for exp in exp_names:
            row[f"sam_score_{exp}"] = r.get(f"sam_score_{exp}", np.nan)
            row[f"decision_{exp}"] = r.get(f"decision_{exp}", None)

        rows.append(row)

        # geometry for gpkg: use geometry from best experiment if available, else first non-empty
        chosen_geom = None
        if best_exp in geoms and geoms[best_exp] is not None and not geoms[best_exp].is_empty:
            chosen_geom = geoms[best_exp]
        else:
            for exp in exp_names:
                if geoms[exp] is not None and not geoms[exp].is_empty:
                    chosen_geom = geoms[exp]
                    break

        geom_rows.append({
            "id": obj_id,
            "uncertainty_level": uncertainty_level,
            "suggested_refinement": suggested_refinement,
            "geometry": chosen_geom
        })

    df_out = pd.DataFrame(rows)
    gdf_out = gpd.GeoDataFrame(geom_rows, geometry="geometry", crs=crs_ref)

    df_out.to_csv(out_csv, index=False)
    gdf_out.to_file(out_gpkg, layer="urban_uncertainty", driver="GPKG")

    print("Saved CSV :", out_csv)
    print("Saved GPKG:", out_gpkg)
    print()
    print(df_out[[
        "id",
        "primary_error_type",
        "best_experiment_so_far",
        "mean_pairwise_iou",
        "area_cv",
        "centroid_spread_m",
        "decision_disagreement",
        "uncertainty_level",
        "suggested_refinement"
    ]])
    print()
    print("Uncertainty counts:")
    print(df_out["uncertainty_level"].value_counts(dropna=False))
    print()
    print("Suggested refinements:")
    print(df_out["suggested_refinement"].value_counts(dropna=False))


if __name__ == "__main__":
    main()