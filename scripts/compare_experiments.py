from pathlib import Path
import sys
import pandas as pd

def summarize(df, name):
    print(f"\n=== {name} ===")
    print(df[["iou_map_vs_sam", "sam_score", "area_diff_frac", "centroid_shift_m"]].describe())
    print("\nDecision counts:")
    print(df["decision"].value_counts(dropna=False))

def main():
    if len(sys.argv) != 3:
        print("Usage: python scripts/compare_experiments.py <exp_a> <exp_b>")
        sys.exit(1)

    ROOT = Path(__file__).resolve().parents[1]
    exp_a = sys.argv[1]
    exp_b = sys.argv[2]

    a = pd.read_csv(ROOT / "outputs" / exp_a / "berlin_update_report.csv")
    b = pd.read_csv(ROOT / "outputs" / exp_b / "berlin_update_report.csv")

    summarize(a, exp_a)
    summarize(b, exp_b)

    # compare on matching ids
    cols = ["id", "iou_map_vs_sam", "sam_score", "area_diff_frac", "centroid_shift_m", "decision"]
    merged = a[cols].merge(
        b[cols],
        on="id",
        suffixes=(f"_{exp_a}", f"_{exp_b}")
    )

    merged["delta_iou"] = merged[f"iou_map_vs_sam_{exp_b}"] - merged[f"iou_map_vs_sam_{exp_a}"]
    merged["delta_score"] = merged[f"sam_score_{exp_b}"] - merged[f"sam_score_{exp_a}"]

    print("\n=== Delta summary ===")
    print(merged[["delta_iou", "delta_score"]].describe())

    print("\nTop improvements by IoU:")
    print(merged.sort_values("delta_iou", ascending=False)[["id", "delta_iou", f"decision_{exp_a}", f"decision_{exp_b}"]].head(10))

    print("\nWorst changes by IoU:")
    print(merged.sort_values("delta_iou", ascending=True)[["id", "delta_iou", f"decision_{exp_a}", f"decision_{exp_b}"]].head(10))

if __name__ == "__main__":
    main()