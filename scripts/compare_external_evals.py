from pathlib import Path
import sys
import pandas as pd

def summarize(df, name):
    print(f"\n=== {name} ===")
    print(df[[
        "iou_orig2018_vs_osm2025",
        "iou_final_vs_osm2025",
        "delta_iou_vs_osm2025",
        "centroid_shift_orig2018_vs_osm2025_m",
        "centroid_shift_final_vs_osm2025_m"
    ]].describe())
    print("\nImproved objects:")
    print(df["improved_vs_2018"].value_counts(dropna=False))

def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/compare_external_evals.py <exp1> [<exp2> <exp3> ...]")
        sys.exit(1)

    ROOT = Path(__file__).resolve().parents[1]
    exp_names = sys.argv[1:]

    all_means = []

    for exp in exp_names:
        csv_path = ROOT / "outputs" / exp / "external_eval_osm2025.csv"
        df = pd.read_csv(csv_path)
        summarize(df, exp)

        all_means.append({
            "experiment": exp,
            "mean_iou_orig2018_vs_osm2025": df["iou_orig2018_vs_osm2025"].mean(),
            "mean_iou_final_vs_osm2025": df["iou_final_vs_osm2025"].mean(),
            "mean_delta_iou_vs_osm2025": df["delta_iou_vs_osm2025"].mean(),
            "n_improved": int(df["improved_vs_2018"].sum()),
            "n_total": len(df),
        })

    summary_df = pd.DataFrame(all_means).sort_values(
        "mean_delta_iou_vs_osm2025", ascending=False
    )

    print("\n=== Cross-experiment summary ===")
    print(summary_df)

if __name__ == "__main__":
    main()