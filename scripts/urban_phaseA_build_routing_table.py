from pathlib import Path
import sys
import json
import pandas as pd

def assign_route(row):
    primary = row["primary_error_type"]
    uncertainty = row["uncertainty_level"]
    disagreement = bool(row["decision_disagreement"])

    if primary == "stable_case":
        if disagreement or uncertainty == "medium":
            return "review_keep"
        return "no_refine"

    if primary == "shadow_roof":
        return "shadow_refine"

    if primary in {"courtyard_structure", "multi_level_roof", "multi_part_roof"}:
        return "topology_refine"

    if primary in {"neighbor_merge", "wrong_building_focus"}:
        return "context_refine"

    if primary in {"oversegmentation", "undersegmentation", "polygon_geometry"}:
        return "geometry_refine"

    if uncertainty == "high":
        return "manual_review"

    return "manual_review"

def main():
    if len(sys.argv) != 2:
        print("Usage: python scripts/urban_phaseA_build_routing_table.py <config.json>")
        sys.exit(1)

    ROOT = Path(__file__).resolve().parents[1]
    cfg = json.loads((ROOT / sys.argv[1]).read_text())

    tax = pd.read_csv(ROOT / cfg["taxonomy_csv"])
    unc = pd.read_csv(ROOT / cfg["uncertainty_csv"])

    merged = tax.merge(
        unc[[
            "id",
            "mean_pairwise_iou",
            "area_cv",
            "centroid_spread_m",
            "decision_disagreement",
            "uncertainty_points",
            "uncertainty_level",
            "suggested_refinement"
        ]],
        on="id",
        how="left"
    )

    merged["routing_decision"] = merged.apply(assign_route, axis=1)

    # recommended pass-1 source
    def pass1_source(best_exp):
        if pd.isna(best_exp):
            return "exp04"
        return best_exp

    merged["pass1_source"] = merged["best_experiment_so_far"].apply(pass1_source)

    out_dir = ROOT / "outputs" / "urban_phaseA"
    out_dir.mkdir(parents=True, exist_ok=True)

    out_csv = out_dir / "urban_routing_table.csv"
    merged.to_csv(out_csv, index=False)

    print("Saved CSV :", out_csv)
    print()
    print(merged[[
        "id",
        "primary_error_type",
        "best_experiment_so_far",
        "uncertainty_level",
        "suggested_refinement",
        "routing_decision",
        "pass1_source"
    ]])
    print()
    print("Routing counts:")
    print(merged["routing_decision"].value_counts(dropna=False))

if __name__ == "__main__":
    main()