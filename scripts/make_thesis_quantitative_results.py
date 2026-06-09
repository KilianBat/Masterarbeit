#!/usr/bin/env python3
"""
Create quantitative thesis results from already produced experiment CSV files.

The script is intentionally lightweight: it does not rerun SAM/SAM2 inference.
It aggregates the existing evaluation outputs into ablation tables and figures
that can be included directly in the thesis.

Run from the repository root, for example:
    python scripts/make_thesis_quantitative_results.py \
        --config configs/thesis_quantitative_results.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt


REQUIRED_EXTERNAL_COLUMNS = {
    "id",
    "decision",
    "iou_final_vs_osm2025",
    "iou_orig2018_vs_osm2025",
    "delta_iou_vs_osm2025",
    "improved_vs_2018",
}


def load_config(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def read_external_eval(repo_root: Path, exp: dict) -> pd.DataFrame:
    path = repo_root / exp["external_eval_csv"]
    if not path.exists():
        raise FileNotFoundError(f"Missing external evaluation file for {exp['key']}: {path}")
    df = pd.read_csv(path)
    missing = REQUIRED_EXTERNAL_COLUMNS - set(df.columns)
    if missing:
        raise ValueError(f"External eval file {path} is missing columns: {sorted(missing)}")
    df = df.copy()
    df["experiment_key"] = exp["key"]
    df["experiment_name"] = exp["name"]
    df["module_step"] = exp.get("module_step", "")
    return df


def read_decision_counts(repo_root: Path, exp: dict) -> Dict[str, int]:
    path = repo_root / exp.get("update_report_csv", "")
    if not path.exists():
        return {"keep": 0, "update": 0, "flag_review": 0}
    df = pd.read_csv(path)
    if "decision" not in df.columns:
        return {"keep": 0, "update": 0, "flag_review": 0}
    counts = df["decision"].value_counts(dropna=False).to_dict()
    return {
        "keep": int(counts.get("keep", 0)),
        "update": int(counts.get("update", 0)),
        "flag_review": int(counts.get("flag_review", 0)),
    }


def make_ablation_summary(repo_root: Path, experiments: List[dict]) -> Tuple[pd.DataFrame, pd.DataFrame]:
    rows = []
    per_object_frames = []

    for order, exp in enumerate(experiments):
        df = read_external_eval(repo_root, exp)
        decision_counts = read_decision_counts(repo_root, exp)
        per_object_frames.append(
            df[
                [
                    "id",
                    "experiment_key",
                    "experiment_name",
                    "module_step",
                    "iou_final_vs_osm2025",
                    "iou_orig2018_vs_osm2025",
                    "delta_iou_vs_osm2025",
                    "improved_vs_2018",
                ]
            ].copy()
        )

        mean_final = float(df["iou_final_vs_osm2025"].mean())
        mean_orig = float(df["iou_orig2018_vs_osm2025"].mean())
        rows.append(
            {
                "order": order,
                "experiment_key": exp["key"],
                "experiment_name": exp["name"],
                "module_step": exp.get("module_step", ""),
                "n_objects": int(len(df)),
                "mean_iou_final_vs_osm2025": mean_final,
                "mean_iou_orig2018_vs_osm2025": mean_orig,
                "mean_delta_vs_2018": float(df["delta_iou_vs_osm2025"].mean()),
                "improved_objects": int(df["improved_vs_2018"].sum()),
                "keep": decision_counts["keep"],
                "update": decision_counts["update"],
                "flag_review": decision_counts["flag_review"],
                "mean_centroid_shift_final_m": float(df.get("centroid_shift_final_vs_osm2025_m", pd.Series(dtype=float)).mean()) if "centroid_shift_final_vs_osm2025_m" in df.columns else np.nan,
                "mean_abs_area_diff_final_frac": float(df.get("area_diff_final_vs_osm2025_frac", pd.Series(dtype=float)).abs().mean()) if "area_diff_final_vs_osm2025_frac" in df.columns else np.nan,
            }
        )

    summary = pd.DataFrame(rows).sort_values("order").reset_index(drop=True)
    summary["delta_iou_vs_previous_step"] = summary["mean_iou_final_vs_osm2025"].diff()
    summary.loc[0, "delta_iou_vs_previous_step"] = 0.0
    baseline = float(summary.loc[0, "mean_iou_final_vs_osm2025"])
    summary["delta_iou_vs_first_baseline"] = summary["mean_iou_final_vs_osm2025"] - baseline
    per_object = pd.concat(per_object_frames, ignore_index=True)
    return summary, per_object


def make_latex_ablation_table(summary: pd.DataFrame, out_path: Path) -> None:
    rows = []
    for _, r in summary.iterrows():
        rows.append(
            f"{r['experiment_name']} & {r['mean_iou_final_vs_osm2025']:.3f} & "
            f"{r['delta_iou_vs_previous_step']:+.3f} & {r['delta_iou_vs_first_baseline']:+.3f} & "
            f"{int(r['improved_objects'])}/{int(r['n_objects'])} & "
            f"{int(r['keep'])}/{int(r['update'])}/{int(r['flag_review'])} \\\\"
        )

    tex = r"""\begin{table}[htbp]
\centering
\caption{Urban ablation summary of the main refinement steps.}
\label{tab:urban_ablation_summary}
\small
\setlength{\tabcolsep}{5pt}
\begin{tabularx}{\textwidth}{>{\raggedright\arraybackslash}p{3.5cm} >{\centering\arraybackslash}p{1.7cm} >{\centering\arraybackslash}p{1.7cm} >{\centering\arraybackslash}p{1.7cm} >{\centering\arraybackslash}p{1.7cm} >{\centering\arraybackslash}p{2.0cm}}
\toprule
Experiment & Mean IoU & $\Delta$ prev. & $\Delta$ base & Improved & Keep/Update/Review \\
\midrule
"""
    tex += "\n".join(rows)
    tex += r"""
\bottomrule
\end{tabularx}

\vspace{0.35em}
\parbox{0.97\textwidth}{\footnotesize \textit{Note.} Mean IoU is measured against the retrospective OSM 2025 reference. $\Delta$ prev. denotes the change relative to the previous row, while $\Delta$ base denotes the change relative to the first baseline row. Keep/Update/Review reports the number of objects assigned to each decision state.}
\end{table}
"""
    out_path.write_text(tex, encoding="utf-8")


def plot_ablation(summary: pd.DataFrame, out_path: Path) -> None:
    labels = summary["experiment_name"].tolist()
    values = summary["mean_iou_final_vs_osm2025"].to_numpy()
    orig_ref = float(summary["mean_iou_orig2018_vs_osm2025"].iloc[0])

    fig, ax = plt.subplots(figsize=(10.5, 5.2))
    ax.bar(range(len(labels)), values)
    ax.axhline(orig_ref, linestyle="--", linewidth=1.3, label="Historic OSM 2018 reference")
    ax.set_ylabel("Mean IoU against OSM 2025")
    ax.set_title("Urban ablation: effect of refinement steps")
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, rotation=25, ha="right")
    ax.set_ylim(0.58, max(orig_ref, values.max()) + 0.05)
    ax.legend(loc="upper left")
    for i, value in enumerate(values):
        ax.text(i, value + 0.004, f"{value:.3f}", ha="center", va="bottom", fontsize=9)
    fig.tight_layout()
    fig.savefig(out_path, dpi=220, bbox_inches="tight")
    plt.close(fig)


def plot_delta(summary: pd.DataFrame, out_path: Path) -> None:
    labels = summary["experiment_name"].tolist()
    values = summary["delta_iou_vs_first_baseline"].to_numpy()
    fig, ax = plt.subplots(figsize=(10.5, 4.8))
    ax.bar(range(len(labels)), values)
    ax.axhline(0, linewidth=1)
    ax.set_ylabel("Mean IoU gain over first baseline")
    ax.set_title("Urban ablation: improvement relative to baseline")
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, rotation=25, ha="right")
    for i, value in enumerate(values):
        ax.text(i, value + (0.002 if value >= 0 else -0.006), f"{value:+.3f}", ha="center", va="bottom" if value >= 0 else "top", fontsize=9)
    fig.tight_layout()
    fig.savefig(out_path, dpi=220, bbox_inches="tight")
    plt.close(fig)


def plot_improved_objects(summary: pd.DataFrame, out_path: Path) -> None:
    labels = summary["experiment_name"].tolist()
    values = summary["improved_objects"].to_numpy()
    n = int(summary["n_objects"].iloc[0])
    fig, ax = plt.subplots(figsize=(10.5, 4.6))
    ax.bar(range(len(labels)), values)
    ax.set_ylabel(f"Objects improved vs. 2018 OSM (out of {n})")
    ax.set_title("Urban ablation: objects with IoU improvement")
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, rotation=25, ha="right")
    ax.set_ylim(0, max(2, values.max() + 1))
    for i, value in enumerate(values):
        ax.text(i, value + 0.05, f"{int(value)}/{n}", ha="center", va="bottom", fontsize=9)
    fig.tight_layout()
    fig.savefig(out_path, dpi=220, bbox_inches="tight")
    plt.close(fig)


def plot_per_object(per_object: pd.DataFrame, experiments: List[dict], out_path: Path) -> None:
    selected_keys = [exp["key"] for exp in experiments]
    plot_df = per_object[per_object["experiment_key"].isin(selected_keys)].copy()
    ids = sorted(plot_df["id"].unique())

    fig, ax = plt.subplots(figsize=(11, 5.8))
    for exp in experiments:
        part = plot_df[plot_df["experiment_key"] == exp["key"]].sort_values("id")
        ax.plot(part["id"], part["iou_final_vs_osm2025"], marker="o", label=exp["name"])
    # Historic OSM line per object from first experiment
    ref = plot_df[plot_df["experiment_key"] == selected_keys[0]].sort_values("id")
    ax.plot(ref["id"], ref["iou_orig2018_vs_osm2025"], linestyle="--", marker="x", label="Historic OSM 2018")
    ax.set_xticks(ids)
    ax.set_xlabel("Urban object ID")
    ax.set_ylabel("IoU against OSM 2025")
    ax.set_title("Per-object IoU across urban ablation steps")
    ax.set_ylim(0, 1.05)
    ax.legend(loc="lower right", fontsize=8)
    fig.tight_layout()
    fig.savefig(out_path, dpi=220, bbox_inches="tight")
    plt.close(fig)


def make_change_type_outputs(repo_root: Path, cfg: dict, out_dir: Path) -> None:
    path = repo_root / cfg["change_type_report_csv"]
    if not path.exists():
        print(f"Warning: change-type report not found: {path}")
        return
    df = pd.read_csv(path)
    required = {"predicted_change_type", "reference_change_type", "reference_match"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Change-type report is missing columns: {sorted(missing)}")

    labels_pred = cfg.get("change_type_predicted_labels", ["unchanged", "modified", "review"])
    labels_ref = cfg.get("change_type_reference_labels", ["unchanged", "modified"])
    confusion = pd.crosstab(
        df["reference_change_type"],
        df["predicted_change_type"],
    ).reindex(index=labels_ref, columns=labels_pred, fill_value=0)
    confusion.to_csv(out_dir / "change_type_confusion_matrix.csv")

    # Exact multi-class agreement with the simplified reference.
    exact_accuracy = float(df["reference_match"].mean())

    # Review-aware binary interpretation: review is treated as a change/review alert.
    pred_binary = df["predicted_change_type"].map(lambda x: "changed_or_review" if x in {"modified", "review"} else "unchanged")
    ref_binary = df["reference_change_type"].map(lambda x: "changed_or_review" if x == "modified" else "unchanged")
    binary_conf = pd.crosstab(ref_binary, pred_binary).reindex(
        index=["unchanged", "changed_or_review"],
        columns=["unchanged", "changed_or_review"],
        fill_value=0,
    )
    binary_conf.to_csv(out_dir / "change_type_binary_review_aware_confusion.csv")
    tp = int(binary_conf.loc["changed_or_review", "changed_or_review"])
    fn = int(binary_conf.loc["changed_or_review", "unchanged"])
    fp = int(binary_conf.loc["unchanged", "changed_or_review"])
    tn = int(binary_conf.loc["unchanged", "unchanged"])
    precision = tp / (tp + fp) if tp + fp else np.nan
    recall = tp / (tp + fn) if tp + fn else np.nan
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else np.nan
    binary_accuracy = (tp + tn) / len(df)

    metrics = pd.DataFrame(
        [
            {"metric": "exact_multiclass_accuracy", "value": exact_accuracy, "interpretation": "predicted class equals simplified reference class"},
            {"metric": "review_aware_binary_accuracy", "value": binary_accuracy, "interpretation": "modified and review are treated as change/review alerts"},
            {"metric": "review_aware_precision", "value": precision, "interpretation": "share of predicted alerts that correspond to modified reference objects"},
            {"metric": "review_aware_recall", "value": recall, "interpretation": "share of modified reference objects captured as modified or review"},
            {"metric": "review_aware_f1", "value": f1, "interpretation": "harmonic mean of review-aware precision and recall"},
            {"metric": "n_objects", "value": len(df), "interpretation": "number of evaluated urban objects"},
        ]
    )
    metrics.to_csv(out_dir / "change_type_metrics.csv", index=False)

    plot_change_type_confusion(confusion, out_dir / "change_type_confusion_matrix.png")
    plot_binary_change_confusion(binary_conf, out_dir / "change_type_review_aware_binary_confusion.png")
    make_latex_change_type_metrics(metrics, out_dir / "change_type_metrics_table.tex")


def plot_change_type_confusion(confusion: pd.DataFrame, out_path: Path) -> None:
    fig, ax = plt.subplots(figsize=(6.2, 4.6))
    matrix = confusion.to_numpy()
    im = ax.imshow(matrix)
    ax.set_xticks(range(len(confusion.columns)))
    ax.set_xticklabels(confusion.columns)
    ax.set_yticks(range(len(confusion.index)))
    ax.set_yticklabels(confusion.index)
    ax.set_xlabel("Predicted change type")
    ax.set_ylabel("Reference change type")
    ax.set_title("Urban change-type confusion matrix")
    for i in range(matrix.shape[0]):
        for j in range(matrix.shape[1]):
            ax.text(j, i, str(int(matrix[i, j])), ha="center", va="center")
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04, label="Number of urban objects")
    fig.tight_layout()
    fig.savefig(out_path, dpi=220, bbox_inches="tight")
    plt.close(fig)


def plot_binary_change_confusion(confusion: pd.DataFrame, out_path: Path) -> None:
    fig, ax = plt.subplots(figsize=(6.4, 4.6))
    matrix = confusion.to_numpy()
    im = ax.imshow(matrix)
    ax.set_xticks(range(len(confusion.columns)))
    ax.set_xticklabels(["unchanged", "changed/review"])
    ax.set_yticks(range(len(confusion.index)))
    ax.set_yticklabels(["unchanged", "modified"])
    ax.set_xlabel("Predicted operational state")
    ax.set_ylabel("Reference state")
    ax.set_title("Review-aware change detection view")
    for i in range(matrix.shape[0]):
        for j in range(matrix.shape[1]):
            ax.text(j, i, str(int(matrix[i, j])), ha="center", va="center")
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04, label="Number of urban objects")
    fig.tight_layout()
    fig.savefig(out_path, dpi=220, bbox_inches="tight")
    plt.close(fig)


def make_latex_change_type_metrics(metrics: pd.DataFrame, out_path: Path) -> None:
    wanted = [
        ("exact_multiclass_accuracy", "Exact class accuracy"),
        ("review_aware_binary_accuracy", "Review-aware binary accuracy"),
        ("review_aware_precision", "Review-aware precision"),
        ("review_aware_recall", "Review-aware recall"),
        ("review_aware_f1", "Review-aware F1"),
    ]
    rows = []
    for key, name in wanted:
        value = float(metrics.loc[metrics["metric"] == key, "value"].iloc[0])
        rows.append(f"{name} & {value:.3f} " + r"\\")
    tex = r"""\begin{table}[htbp]
\centering
\caption{Quantitative evaluation of the urban change-type classification layer.}
\label{tab:change_type_metrics}
\small
\begin{tabular}{lr}
\toprule
Metric & Value \\
\midrule
"""
    tex += "\n".join(rows)
    tex += r"""
\bottomrule
\end{tabular}

\vspace{0.35em}
\parbox{0.88\textwidth}{\footnotesize \textit{Note.} In the review-aware binary view, both \texttt{modified} and \texttt{review} are treated as operational change/review alerts. This reflects the intended use of \texttt{review} as a conservative escalation state rather than as an automatic overwrite decision.}
\end{table}
"""
    out_path.write_text(tex, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, help="Path to the JSON configuration file.")
    args = parser.parse_args()

    config_path = Path(args.config).resolve()
    repo_root = config_path.parents[1] if config_path.parent.name == "configs" else Path.cwd()
    cfg = load_config(config_path)
    if "repo_root" in cfg:
        repo_root = Path(cfg["repo_root"]).resolve()
    else:
        repo_root = Path.cwd().resolve()

    out_dir = repo_root / cfg.get("output_dir", "outputs/thesis_quantitative_results")
    fig_dir = out_dir / "figures"
    table_dir = out_dir / "tables"
    ensure_dir(out_dir)
    ensure_dir(fig_dir)
    ensure_dir(table_dir)

    experiments = cfg["urban_ablation_experiments"]
    summary, per_object = make_ablation_summary(repo_root, experiments)
    summary.to_csv(out_dir / "urban_ablation_summary.csv", index=False)
    per_object.to_csv(out_dir / "urban_per_object_iou.csv", index=False)

    make_latex_ablation_table(summary, table_dir / "urban_ablation_summary_table.tex")
    plot_ablation(summary, fig_dir / "urban_ablation_mean_iou.png")
    plot_delta(summary, fig_dir / "urban_ablation_delta_vs_baseline.png")
    plot_improved_objects(summary, fig_dir / "urban_ablation_improved_objects.png")

    per_object_exps = cfg.get("per_object_plot_experiments", experiments)
    # Resolve keys in the same order as the main experiment list.
    key_to_exp = {exp["key"]: exp for exp in experiments}
    selected_for_per_object = [key_to_exp[key] if isinstance(key, str) else key for key in per_object_exps]
    plot_per_object(per_object, selected_for_per_object, fig_dir / "urban_per_object_iou.png")

    make_change_type_outputs(repo_root, cfg, out_dir)

    print(f"Wrote quantitative thesis outputs to: {out_dir}")
    print("Main files:")
    for path in [
        out_dir / "urban_ablation_summary.csv",
        out_dir / "urban_per_object_iou.csv",
        table_dir / "urban_ablation_summary_table.tex",
        fig_dir / "urban_ablation_mean_iou.png",
        fig_dir / "urban_per_object_iou.png",
        out_dir / "change_type_metrics.csv",
        out_dir / "change_type_confusion_matrix.csv",
    ]:
        print(f"  - {path.relative_to(repo_root)}")


if __name__ == "__main__":
    main()
