#!/usr/bin/env python3
"""Create thesis-ready visual result figures from existing experiment reports.

The script does not run SAM inference. It only visualises geometries already stored in
experiment CSV files (`orig_wkt`, `pred_wkt`) together with the current orthophoto and
matched OSM 2025 reference polygons.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, Iterable, Optional

import matplotlib.pyplot as plt
import pandas as pd
from PIL import Image
from shapely.geometry import shape, Polygon, MultiPolygon, GeometryCollection
from shapely.ops import transform
from shapely import wkt
from pyproj import Transformer


STYLE = {
    "historic": {"color": "#1f77b4", "linewidth": 2.0, "linestyle": "--", "label": "OSM 2018"},
    "prediction": {"color": "#d62728", "linewidth": 2.0, "linestyle": "-", "label": "SAM2 proposal"},
    "final": {"color": "#2ca02c", "linewidth": 2.5, "linestyle": "-", "label": "Final update product"},
    "reference": {"color": "#111111", "linewidth": 2.0, "linestyle": ":", "label": "OSM 2025 reference"},
}


def read_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def load_report(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    if "id" in df.columns:
        df["id"] = df["id"].astype(int)
    return df


def geom_from_wkt(value) -> Optional[object]:
    if value is None or pd.isna(value):
        return None
    try:
        return wkt.loads(str(value))
    except Exception:
        return None


def load_current_reference_by_id(path: Path) -> Dict[int, object]:
    """Load OSM 2025 GeoJSON and transform CRS84 coordinates to EPSG:25833."""
    data = read_json(path)
    transformer = Transformer.from_crs("EPSG:4326", "EPSG:25833", always_xy=True)
    out = {}
    for feat in data.get("features", []):
        props = feat.get("properties", {})
        osm_id = props.get("id")
        if osm_id is None:
            continue
        geom = shape(feat.get("geometry"))
        geom_proj = transform(transformer.transform, geom)
        out[int(osm_id)] = geom_proj
    return out


def iter_polygons(geom):
    if geom is None or geom.is_empty:
        return
    if isinstance(geom, Polygon):
        yield geom
    elif isinstance(geom, MultiPolygon):
        for g in geom.geoms:
            yield g
    elif isinstance(geom, GeometryCollection):
        for g in geom.geoms:
            yield from iter_polygons(g)


def plot_geom(ax, geom, style: dict, label_once: bool = True, fill_alpha: float = 0.0):
    label = style.get("label")
    first = True
    for poly in iter_polygons(geom):
        x, y = poly.exterior.xy
        ax.plot(x, y, color=style["color"], linewidth=style["linewidth"], linestyle=style["linestyle"], label=label if first else None)
        if fill_alpha > 0:
            ax.fill(x, y, color=style["color"], alpha=fill_alpha)
        for interior in poly.interiors:
            xi, yi = interior.xy
            ax.plot(xi, yi, color=style["color"], linewidth=max(1.0, style["linewidth"] - 0.5), linestyle=style["linestyle"])
        first = False


def union_bounds(geoms: Iterable[object], pad_frac: float = 0.25, min_pad: float = 12.0):
    bounds = [g.bounds for g in geoms if g is not None and not g.is_empty]
    if not bounds:
        raise ValueError("No geometry bounds available")
    minx = min(b[0] for b in bounds); miny = min(b[1] for b in bounds)
    maxx = max(b[2] for b in bounds); maxy = max(b[3] for b in bounds)
    dx = max(maxx - minx, min_pad)
    dy = max(maxy - miny, min_pad)
    pad = max(dx, dy) * pad_frac
    return minx - pad, maxx + pad, miny - pad, maxy + pad


def setup_axis(ax, img, meta, extent=None, title: Optional[str] = None):
    minx, miny, maxx, maxy = meta["bbox_proj"]
    ax.imshow(img, extent=[minx, maxx, miny, maxy], origin="upper")
    if extent:
        xmin, xmax, ymin, ymax = extent
        ax.set_xlim(xmin, xmax)
        ax.set_ylim(ymin, ymax)
    ax.set_aspect("equal")
    ax.set_xticks([])
    ax.set_yticks([])
    if title:
        ax.set_title(title, fontsize=11)


def row_by_id(df: pd.DataFrame, obj_id: int) -> pd.Series:
    rows = df[df["id"] == int(obj_id)]
    if rows.empty:
        raise KeyError(f"ID {obj_id} not found")
    return rows.iloc[0]


def prediction_geom(df: pd.DataFrame, obj_id: int):
    row = row_by_id(df, obj_id)
    return geom_from_wkt(row.get("pred_wkt"))


def original_geom(df: pd.DataFrame, obj_id: int):
    row = row_by_id(df, obj_id)
    return geom_from_wkt(row.get("orig_wkt"))


def final_geom(df: pd.DataFrame, obj_id: int):
    row = row_by_id(df, obj_id)
    final_source = str(row.get("final_source", "sam2")).lower()
    if final_source in {"osm", "orig", "original", "keep"}:
        return geom_from_wkt(row.get("orig_wkt"))
    return geom_from_wkt(row.get("pred_wkt"))


def ref_geom(external_df: pd.DataFrame, refs: Dict[int, object], obj_id: int):
    row = row_by_id(external_df, obj_id)
    ref_id = row.get("matched_ref_id")
    if pd.isna(ref_id):
        return None
    return refs.get(int(ref_id))


def draw_case_panel(ax, img, meta, title, orig=None, proposal=None, final=None, ref=None, extent=None):
    setup_axis(ax, img, meta, extent=extent, title=title)
    if orig is not None: plot_geom(ax, orig, STYLE["historic"])
    if proposal is not None: plot_geom(ax, proposal, STYLE["prediction"])
    if final is not None: plot_geom(ax, final, STYLE["final"])
    if ref is not None: plot_geom(ax, ref, STYLE["reference"])


def dedup_legend(fig, axes, ncol=4):
    handles, labels = [], []
    for ax in axes:
        h, l = ax.get_legend_handles_labels()
        for hh, ll in zip(h, l):
            if ll and ll not in labels:
                handles.append(hh); labels.append(ll)
    if handles:
        fig.legend(handles, labels, loc="lower center", ncol=ncol, frameon=False, fontsize=10)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/thesis_visual_results.json")
    args = parser.parse_args()

    repo = Path.cwd()
    cfg = read_json(repo / args.config)
    out_dir = repo / cfg["output_dir"]
    fig_dir = out_dir / "figures"
    tbl_dir = out_dir / "tables"
    fig_dir.mkdir(parents=True, exist_ok=True)
    tbl_dir.mkdir(parents=True, exist_ok=True)

    img = Image.open(repo / cfg["urban_ortho"]).convert("RGB")
    meta = read_json(repo / cfg["urban_meta"])
    refs = load_current_reference_by_id(repo / cfg["urban_current_geojson"])

    reports = {k: load_report(repo / v) for k, v in cfg["reports"].items()}
    ext = reports["external_eval"]
    best = reports["shadow_exp08b"]
    change = reports["change_type"]

    # Figure 1: final urban update product overview for all evaluated urban objects.
    evaluated_ids = list(best["id"].astype(int))
    geoms_for_extent = []
    for oid in evaluated_ids:
        geoms_for_extent.extend([original_geom(best, oid), final_geom(best, oid), ref_geom(ext, refs, oid)])
    overview_extent = union_bounds(geoms_for_extent, pad_frac=0.18, min_pad=30)
    fig, ax = plt.subplots(figsize=(8.5, 8.5))
    setup_axis(ax, img, meta, extent=overview_extent, title="Final urban update product (Exp08b shadow refinement)")
    for oid in evaluated_ids:
        plot_geom(ax, original_geom(best, oid), STYLE["historic"])
        plot_geom(ax, final_geom(best, oid), STYLE["final"])
        rg = ref_geom(ext, refs, oid)
        if rg is not None:
            plot_geom(ax, rg, STYLE["reference"])
    dedup_legend(fig, [ax], ncol=3)
    fig.tight_layout(rect=[0, 0.08, 1, 1])
    fig.savefig(fig_dir / "fig_final_urban_update_product.png", dpi=240, bbox_inches="tight")
    plt.close(fig)

    # Case figure helper.
    def case_extent(obj_id, extra_reports):
        gs = [original_geom(best, obj_id), ref_geom(ext, refs, obj_id)]
        for df in extra_reports:
            gs.append(prediction_geom(df, obj_id))
            gs.append(final_geom(df, obj_id))
        return union_bounds(gs, pad_frac=0.45, min_pad=20)

    # Figure 2: topology success case ID32.
    oid = int(cfg["case_ids"]["topology_success"])
    extent = case_extent(oid, [reports["baseline_exp04"], reports["topology_raw_exp08a"], reports["selective_exp08a"], best])
    fig, axes = plt.subplots(1, 4, figsize=(15, 4.4))
    draw_case_panel(axes[0], img, meta, "Baseline Exp04", orig=original_geom(best, oid), proposal=prediction_geom(reports["baseline_exp04"], oid), ref=ref_geom(ext, refs, oid), extent=extent)
    draw_case_panel(axes[1], img, meta, "Raw topology pass", orig=original_geom(best, oid), proposal=prediction_geom(reports["topology_raw_exp08a"], oid), ref=ref_geom(ext, refs, oid), extent=extent)
    draw_case_panel(axes[2], img, meta, "Selective output", orig=original_geom(best, oid), final=final_geom(reports["selective_exp08a"], oid), ref=ref_geom(ext, refs, oid), extent=extent)
    draw_case_panel(axes[3], img, meta, "Final Exp08b", orig=original_geom(best, oid), final=final_geom(best, oid), ref=ref_geom(ext, refs, oid), extent=extent)
    fig.suptitle(f"Topology refinement example (ID {oid})", fontsize=14)
    dedup_legend(fig, axes, ncol=4)
    fig.tight_layout(rect=[0, 0.12, 1, 0.93])
    fig.savefig(fig_dir / "fig_topology_refinement_id32.png", dpi=240, bbox_inches="tight")
    plt.close(fig)

    # Figure 3: review/failure case ID21.
    oid = int(cfg["case_ids"]["review_case"])
    extent = case_extent(oid, [reports["baseline_exp04"], reports["topology_raw_exp08a"], reports["selective_exp08a"], best])
    fig, axes = plt.subplots(1, 4, figsize=(15, 4.4))
    draw_case_panel(axes[0], img, meta, "Baseline Exp04", orig=original_geom(best, oid), proposal=prediction_geom(reports["baseline_exp04"], oid), ref=ref_geom(ext, refs, oid), extent=extent)
    draw_case_panel(axes[1], img, meta, "Raw topology pass", orig=original_geom(best, oid), proposal=prediction_geom(reports["topology_raw_exp08a"], oid), ref=ref_geom(ext, refs, oid), extent=extent)
    draw_case_panel(axes[2], img, meta, "Selective output", orig=original_geom(best, oid), final=final_geom(reports["selective_exp08a"], oid), ref=ref_geom(ext, refs, oid), extent=extent)
    draw_case_panel(axes[3], img, meta, "Change-type: review", orig=original_geom(best, oid), final=final_geom(best, oid), ref=ref_geom(ext, refs, oid), extent=extent)
    fig.suptitle(f"Review case after refinement (ID {oid})", fontsize=14)
    dedup_legend(fig, axes, ncol=4)
    fig.tight_layout(rect=[0, 0.12, 1, 0.93])
    fig.savefig(fig_dir / "fig_review_case_id21.png", dpi=240, bbox_inches="tight")
    plt.close(fig)

    # Figure 4: shadow refinement case ID16.
    oid = int(cfg["case_ids"]["shadow_case"])
    extent = case_extent(oid, [reports["selective_exp08a"], best])
    fig, axes = plt.subplots(1, 3, figsize=(12, 4.5))
    draw_case_panel(axes[0], img, meta, "Before shadow refine", orig=original_geom(best, oid), final=final_geom(reports["selective_exp08a"], oid), ref=ref_geom(ext, refs, oid), extent=extent)
    draw_case_panel(axes[1], img, meta, "Shadow pass proposal", orig=original_geom(best, oid), proposal=prediction_geom(best, oid), ref=ref_geom(ext, refs, oid), extent=extent)
    draw_case_panel(axes[2], img, meta, "Final Exp08b", orig=original_geom(best, oid), final=final_geom(best, oid), ref=ref_geom(ext, refs, oid), extent=extent)
    fig.suptitle(f"Shadow refinement example (ID {oid})", fontsize=14)
    dedup_legend(fig, axes, ncol=4)
    fig.tight_layout(rect=[0, 0.14, 1, 0.92])
    fig.savefig(fig_dir / "fig_shadow_refinement_id16.png", dpi=240, bbox_inches="tight")
    plt.close(fig)

    # Figure 5: change-type overlay examples.
    examples = [
        (int(cfg["case_ids"]["unchanged_example"]), "unchanged"),
        (int(cfg["case_ids"]["modified_example"]), "modified"),
        (int(cfg["case_ids"]["review_example"]), "review"),
    ]
    extents = [case_extent(oid, [best]) for oid, _ in examples]
    fig, axes = plt.subplots(1, 3, figsize=(13, 4.6))
    for ax, (oid, cls), ex in zip(axes, examples, extents):
        draw_case_panel(ax, img, meta, f"ID {oid}: {cls}", orig=original_geom(best, oid), final=final_geom(best, oid), ref=ref_geom(ext, refs, oid), extent=ex)
    fig.suptitle("Urban change-type overlay examples", fontsize=14)
    dedup_legend(fig, axes, ncol=3)
    fig.tight_layout(rect=[0, 0.14, 1, 0.92])
    fig.savefig(fig_dir / "fig_change_type_overlay_examples.png", dpi=240, bbox_inches="tight")
    plt.close(fig)

    # Case metadata table for reproducibility.
    rows = []
    for oid in sorted(set([int(v) for v in cfg["case_ids"].values()])):
        c_row = row_by_id(change, oid) if oid in set(change["id"].astype(int)) else None
        e_row = row_by_id(ext, oid)
        rows.append({
            "id": oid,
            "decision": row_by_id(best, oid).get("decision"),
            "final_source": row_by_id(best, oid).get("final_source"),
            "selected_source": c_row.get("selected_source") if c_row is not None else "",
            "predicted_change_type": c_row.get("predicted_change_type") if c_row is not None else "",
            "reference_change_type": c_row.get("reference_change_type") if c_row is not None else "",
            "iou_orig2018_vs_osm2025": e_row.get("iou_orig2018_vs_osm2025"),
            "iou_final_vs_osm2025": e_row.get("iou_final_vs_osm2025"),
        })
    pd.DataFrame(rows).to_csv(out_dir / "visual_case_metadata.csv", index=False)

    # LaTeX snippet for chapter 5.
    snippet = r"""
% --- Thesis visual result figures generated by scripts/make_thesis_visual_results.py ---

\begin{figure}[htbp]
\centering
\includegraphics[width=0.95\textwidth]{Figures/Results/Visual/fig_final_urban_update_product.png}
\caption{Final urban update product for the evaluated Berlin objects. The figure overlays the historical OSM geometry, the final Exp08b update product, and the retrospective OSM 2025 reference on the 2025 orthophoto.}
\label{fig:final_urban_update_product}
\end{figure}
\FloatBarrier

\begin{figure}[htbp]
\centering
\includegraphics[width=\textwidth]{Figures/Results/Visual/fig_topology_refinement_id32.png}
\caption{Topology refinement example for object ID~32. The specialised topology pass is shown as an intermediate candidate, while the final workflow uses selective acceptance to decide which proposal enters the update product.}
\label{fig:topology_refinement_id32}
\end{figure}
\FloatBarrier

\begin{figure}[htbp]
\centering
\includegraphics[width=\textwidth]{Figures/Results/Visual/fig_review_case_id21.png}
\caption{Review case for object ID~21. The example illustrates why geometrically difficult urban objects should be escalated instead of being overwritten automatically.}
\label{fig:review_case_id21}
\end{figure}
\FloatBarrier

\begin{figure}[htbp]
\centering
\includegraphics[width=\textwidth]{Figures/Results/Visual/fig_shadow_refinement_id16.png}
\caption{Shadow-specific refinement example for object ID~16. The figure compares the output before shadow refinement, the shadow-pass proposal, and the final Exp08b update product.}
\label{fig:shadow_refinement_id16}
\end{figure}
\FloatBarrier

\begin{figure}[htbp]
\centering
\includegraphics[width=\textwidth]{Figures/Results/Visual/fig_change_type_overlay_examples.png}
\caption{Overlay examples for the urban change-type layer, covering unchanged, modified, and review decisions.}
\label{fig:change_type_overlay_examples}
\end{figure}
\FloatBarrier
""".strip() + "\n"
    (out_dir / "chapter5_visual_insertions.tex").write_text(snippet, encoding="utf-8")

    print(f"Wrote visual result figures to {fig_dir}")
    print(f"Wrote insertion snippet to {out_dir / 'chapter5_visual_insertions.tex'}")


if __name__ == "__main__":
    main()
