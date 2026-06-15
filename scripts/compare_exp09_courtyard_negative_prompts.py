#!/usr/bin/env python3
"""Compare targeted Exp09 courtyard negative prompts with earlier urban variants.

Usage:
    python scripts/compare_exp09_courtyard_negative_prompts.py \
        --config configs/urban_berlin/exp09_courtyard_negative_prompts.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


def load_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def load_eval(path: Path, label: str, target_ids: List[int]) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Missing external evaluation CSV for {label}: {path}")
    df = pd.read_csv(path)
    df = df[df["id"].astype(int).isin(target_ids)].copy()
    df["id"] = df["id"].astype(int)
    df = df[["id", "iou_final_vs_osm2025", "delta_iou_vs_osm2025", "improved_vs_2018"]].copy()
    df = df.rename(columns={
        "iou_final_vs_osm2025": f"iou_{label}",
        "delta_iou_vs_osm2025": f"delta_{label}",
        "improved_vs_2018": f"improved_{label}",
    })
    return df


def latex_escape(s: str) -> str:
    return str(s).replace("_", r"\_")


def write_latex_table(df: pd.DataFrame, out_path: Path) -> None:
    rows = []
    for _, r in df.iterrows():
        rows.append(
            f"{int(r['id'])} & {r['iou_exp04']:.3f} & {r['iou_exp08b']:.3f} & {r['iou_exp09']:.3f} & {r['delta_exp09_vs_exp04']:+.3f} & {r['delta_exp09_vs_exp08b']:+.3f} \\\\"
        )
    content = r"""\begin{table}[htbp]
\centering
\caption{Targeted comparison of courtyard negative prompts in Exp09.}
\label{tab:exp09_courtyard_negative_prompts}
\small
\begin{tabular}{rrrrrr}
\toprule
ID & Exp04 & Exp08b & Exp09 & Exp09--Exp04 & Exp09--Exp08b \\
\midrule
""" + "\n".join(rows) + r"""
\bottomrule
\end{tabular}
\end{table}
"""
    out_path.write_text(content, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    args = parser.parse_args()

    root = Path.cwd().resolve()
    cfg = load_json(root / args.config)
    target_ids = [int(c["id"]) for c in cfg["target_cases"]]
    out_dir = root / cfg["output_dir"] / "comparison"
    fig_dir = out_dir / "figures"
    table_dir = out_dir / "tables"
    fig_dir.mkdir(parents=True, exist_ok=True)
    table_dir.mkdir(parents=True, exist_ok=True)

    exp04_path = root / cfg["baseline_external_eval_csv"]
    exp08b_path = root / cfg["reference_external_eval_csv"]
    exp09_path = root / cfg["future_exp09_external_eval_csv"]

    exp04 = load_eval(exp04_path, "exp04", target_ids)
    exp08b = load_eval(exp08b_path, "exp08b", target_ids)
    exp09 = load_eval(exp09_path, "exp09", target_ids)

    merged = exp04.merge(exp08b, on="id", how="outer").merge(exp09, on="id", how="outer").sort_values("id")
    merged["delta_exp09_vs_exp04"] = merged["iou_exp09"] - merged["iou_exp04"]
    merged["delta_exp09_vs_exp08b"] = merged["iou_exp09"] - merged["iou_exp08b"]

    summary = pd.DataFrame([
        {
            "experiment": "Exp04 baseline",
            "mean_iou_target_ids": merged["iou_exp04"].mean(),
            "improved_objects_target_ids": int(exp04[f"improved_exp04"].sum()),
            "n_objects": len(merged),
        },
        {
            "experiment": "Exp08b current best",
            "mean_iou_target_ids": merged["iou_exp08b"].mean(),
            "improved_objects_target_ids": int(exp08b[f"improved_exp08b"].sum()),
            "n_objects": len(merged),
        },
        {
            "experiment": "Exp09 courtyard negative prompts",
            "mean_iou_target_ids": merged["iou_exp09"].mean(),
            "improved_objects_target_ids": int(exp09[f"improved_exp09"].sum()),
            "n_objects": len(merged),
        },
    ])

    merged.to_csv(out_dir / "exp09_per_object_comparison.csv", index=False)
    summary.to_csv(out_dir / "exp09_targeted_summary.csv", index=False)
    write_latex_table(merged, table_dir / "tab_exp09_courtyard_negative_prompts.tex")

    # Figure 1: per-object IoU grouped bars.
    ids = merged["id"].astype(str).tolist()
    x = np.arange(len(ids))
    width = 0.25
    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.bar(x - width, merged["iou_exp04"], width, label="Exp04")
    ax.bar(x, merged["iou_exp08b"], width, label="Exp08b")
    ax.bar(x + width, merged["iou_exp09"], width, label="Exp09")
    ax.set_xticks(x)
    ax.set_xticklabels(ids)
    ax.set_ylim(0, 1.0)
    ax.set_ylabel("IoU vs. OSM 2025")
    ax.set_xlabel("Object ID")
    ax.set_title("Targeted Exp09 comparison on courtyard/topology cases")
    ax.legend()
    fig.tight_layout()
    fig.savefig(fig_dir / "exp09_per_object_iou.png", dpi=220, bbox_inches="tight")
    plt.close(fig)

    # Figure 2: mean IoU on targeted IDs.
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.bar(summary["experiment"], summary["mean_iou_target_ids"])
    ax.set_ylim(0, 1.0)
    ax.set_ylabel("Mean IoU vs. OSM 2025")
    ax.set_title("Mean IoU on Exp09 target cases")
    ax.tick_params(axis="x", rotation=20)
    for i, v in enumerate(summary["mean_iou_target_ids"]):
        ax.text(i, v + 0.015, f"{v:.3f}", ha="center", va="bottom", fontsize=9)
    fig.tight_layout()
    fig.savefig(fig_dir / "exp09_targeted_mean_iou.png", dpi=220, bbox_inches="tight")
    plt.close(fig)

    print("Saved:", out_dir / "exp09_per_object_comparison.csv")
    print("Saved:", out_dir / "exp09_targeted_summary.csv")
    print("Saved figures:", fig_dir)
    print()
    print(summary)
    print()
    print(merged[["id", "iou_exp04", "iou_exp08b", "iou_exp09", "delta_exp09_vs_exp04", "delta_exp09_vs_exp08b"]])


if __name__ == "__main__":
    main()
