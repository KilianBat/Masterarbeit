#!/usr/bin/env python3
"""Run SAM2 for Exp09: targeted courtyard negative point prompts.

This script is the actual inference counterpart to
`prepare_exp09_courtyard_negative_prompts.py`. It uses the manually checked
prompt positions from either the Exp09 config or the generated prompt plan and
runs SAM2 only for the targeted urban objects.

Usage:
    python scripts/urban_berlin/geo_run_sam2_exp09_courtyard_negative_prompts.py \
        --config configs/urban_berlin/exp09_courtyard_negative_prompts.json

Expected previous step:
    python scripts/urban_berlin/prepare_exp09_courtyard_negative_prompts.py \
        --config configs/urban_berlin/exp09_courtyard_negative_prompts.json

Outputs:
    outputs/urban_exp09_courtyard_negative_prompts/berlin_predictions.gpkg
    outputs/urban_exp09_courtyard_negative_prompts/experiment_config.json
    outputs/urban_exp09_courtyard_negative_prompts/exp09_prompted_predictions.csv
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import cv2
import geopandas as gpd
import numpy as np
import pandas as pd
import torch
from rasterio.features import shapes
from rasterio.transform import from_bounds
from shapely import wkt
from shapely.geometry import shape
from shapely.ops import unary_union

from sam2.build_sam import build_sam2
from sam2.sam2_image_predictor import SAM2ImagePredictor


def load_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def parse_points(value: Any) -> List[Tuple[float, float]]:
    """Parse points stored either as list or JSON string."""
    if value is None:
        return []
    if isinstance(value, float) and np.isnan(value):
        return []
    if isinstance(value, str):
        value = json.loads(value)
    return [(float(x), float(y)) for x, y in value]


def expand_bbox(bounds: Iterable[float], pad_px: float, img_w: int, img_h: int) -> np.ndarray:
    x1, y1, x2, y2 = map(float, bounds)
    x1 = max(0.0, x1 - pad_px)
    y1 = max(0.0, y1 - pad_px)
    x2 = min(float(img_w - 1), x2 + pad_px)
    y2 = min(float(img_h - 1), y2 + pad_px)
    return np.array([x1, y1, x2, y2], dtype=np.float32)


def mask_to_largest_polygon(mask01: np.ndarray, transform):
    geoms = []
    for geom, val in shapes(mask01.astype(np.uint8), mask=mask01.astype(bool), transform=transform):
        if int(val) == 1:
            geoms.append(shape(geom))
    if not geoms:
        return None
    merged = unary_union(geoms)
    if merged.geom_type == "Polygon":
        return merged
    if merged.geom_type == "MultiPolygon":
        return max(merged.geoms, key=lambda g: g.area)
    return None


def resolve_repo_path(root: Path, raw_path: Any) -> Path:
    """Resolve paths robustly even if manifest contains old absolute paths."""
    p = Path(str(raw_path))
    if p.exists():
        return p
    if not p.is_absolute():
        q = root / p
        if q.exists():
            return q
    # Common case: old absolute path contains '/Masterarbeit/' or '/Masterarbeit-main/'.
    s = str(raw_path).replace("\\", "/")
    for token in ["/Masterarbeit-main/", "/Masterarbeit/"]:
        if token in s:
            rel = s.split(token, 1)[1]
            q = root / rel
            if q.exists():
                return q
    raise FileNotFoundError(f"Could not resolve path: {raw_path}")


def load_prompt_plan(root: Path, cfg: Dict[str, Any]) -> pd.DataFrame:
    out_dir = root / cfg["output_dir"]
    prompt_plan_path = root / cfg.get(
        "prompt_plan_csv",
        str(Path(cfg["output_dir"]) / "prompt_plan.csv"),
    )
    if prompt_plan_path.exists():
        pp = pd.read_csv(prompt_plan_path)
        pp["id"] = pp["id"].astype(int)
        return pp

    # Fallback: build from config target_cases if prepare script was not run.
    rows = []
    for case in cfg["target_cases"]:
        rows.append({
            "id": int(case["id"]),
            "chip_path": None,
            "positive_points_px": json.dumps(case.get("positive_points_px", [])),
            "negative_points_px": json.dumps(case.get("negative_points_px", [])),
            "reason": case.get("reason", ""),
            "manual_review_required": bool(case.get("manual_review_required", True)),
        })
    return pd.DataFrame(rows)


def get_base_config(root: Path, cfg: Dict[str, Any]) -> Dict[str, Any]:
    base_config_path = root / cfg.get(
        "base_config_path",
        "configs/urban_berlin/exp04_tightchip_baseline.json",
    )
    if not base_config_path.exists():
        raise FileNotFoundError(f"Base config not found: {base_config_path}")
    return load_json(base_config_path)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, help="Path to Exp09 config JSON")
    args = parser.parse_args()

    root = Path.cwd().resolve()
    cfg_path = (root / args.config).resolve() if not Path(args.config).is_absolute() else Path(args.config)
    cfg = load_json(cfg_path)
    base_cfg = get_base_config(root, cfg)

    exp_name = cfg["experiment_name"]
    out_dir = root / cfg["output_dir"]
    out_dir.mkdir(parents=True, exist_ok=True)
    out_gpkg = out_dir / "berlin_predictions.gpkg"
    out_csv = out_dir / "exp09_prompted_predictions.csv"

    manifest_path = root / cfg.get("manifest_path", base_cfg["manifest_path"])
    manifest = pd.read_csv(manifest_path)
    manifest["id"] = manifest["id"].astype(int)

    prompt_plan = load_prompt_plan(root, cfg)
    target_ids = [int(c["id"]) for c in cfg["target_cases"]]

    manifest_target = manifest[manifest["id"].isin(target_ids)].copy()
    if manifest_target.empty:
        raise ValueError(f"No target IDs {target_ids} found in manifest {manifest_path}")

    merged = manifest_target.merge(
        prompt_plan[["id", "chip_path", "positive_points_px", "negative_points_px", "reason"]],
        on="id",
        how="left",
        suffixes=("", "_prompt"),
    )

    ckpt = root / cfg.get("checkpoint", base_cfg["checkpoint"])
    config_name = cfg.get("config_name", base_cfg["config_name"])
    use_box = bool(cfg.get("use_box", base_cfg.get("use_box", True)))
    box_expand_px = float(cfg.get("box_expand_px", base_cfg.get("box_expand_px", 0)))

    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Loading SAM2 model on device={device}")
    model = build_sam2(config_name, str(ckpt), device=device)
    predictor = SAM2ImagePredictor(model)

    rows = []

    for _, r in merged.iterrows():
        obj_id = int(r["id"])
        orig_geom = wkt.loads(r["orig_wkt"])
        poly_px = wkt.loads(r["poly_px_wkt"])

        # Prefer the checked chip path from prompt_plan if available; otherwise manifest path.
        raw_chip = r.get("chip_path_prompt")
        if raw_chip is None or (isinstance(raw_chip, float) and np.isnan(raw_chip)):
            raw_chip = r["chip_path"]
        chip_path = resolve_repo_path(root, raw_chip)

        chip_bgr = cv2.imread(str(chip_path))
        if chip_bgr is None:
            raise FileNotFoundError(f"Could not read chip image: {chip_path}")
        chip_rgb = cv2.cvtColor(chip_bgr, cv2.COLOR_BGR2RGB)
        h, w = chip_rgb.shape[:2]

        chip_transform = from_bounds(
            float(r["chip_left"]),
            float(r["chip_bottom"]),
            float(r["chip_right"]),
            float(r["chip_top"]),
            w,
            h,
        )

        pos_pts = parse_points(r.get("positive_points_px"))
        neg_pts = parse_points(r.get("negative_points_px"))
        if not pos_pts:
            raise ValueError(f"ID {obj_id} has no positive prompt points. Check Exp09 config/prompt_plan.")

        point_coords = [[x, y] for x, y in pos_pts] + [[x, y] for x, y in neg_pts]
        point_labels = [1] * len(pos_pts) + [0] * len(neg_pts)
        point_coords_arr = np.array(point_coords, dtype=np.float32)
        point_labels_arr = np.array(point_labels, dtype=np.int32)

        bbox = None
        if use_box:
            bbox = expand_bbox(poly_px.bounds, box_expand_px, w, h)

        print(f"Running ID {obj_id}: n_pos={len(pos_pts)}, n_neg={len(neg_pts)}, chip={chip_path}")
        with torch.inference_mode():
            if device == "cuda":
                with torch.autocast("cuda", dtype=torch.bfloat16):
                    predictor.set_image(chip_rgb)
                    masks, scores, _ = predictor.predict(
                        box=bbox,
                        point_coords=point_coords_arr,
                        point_labels=point_labels_arr,
                    )
            else:
                predictor.set_image(chip_rgb)
                masks, scores, _ = predictor.predict(
                    box=bbox,
                    point_coords=point_coords_arr,
                    point_labels=point_labels_arr,
                )

        best = int(np.argmax(scores))
        pred_mask = (masks[best] > 0).astype(np.uint8)
        pred_geom = mask_to_largest_polygon(pred_mask, chip_transform)

        rows.append({
            "id": obj_id,
            "orig_wkt": orig_geom.wkt,
            "sam_score": float(scores[best]),
            "chip_path": str(chip_path),
            "n_pos": len(pos_pts),
            "n_neg": len(neg_pts),
            "positive_points_px": json.dumps(pos_pts),
            "negative_points_px": json.dumps(neg_pts),
            "reason": r.get("reason", ""),
            "selected_mask_index": best,
            "geometry": pred_geom,
        })

    gdf = gpd.GeoDataFrame(rows, geometry="geometry", crs=manifest["chip_crs"].iloc[0])
    if out_gpkg.exists():
        out_gpkg.unlink()
    gdf.to_file(out_gpkg, layer="predictions", driver="GPKG")
    pd.DataFrame(gdf.drop(columns="geometry")).to_csv(out_csv, index=False)

    # Save expanded reproducibility config.
    exp_copy = dict(cfg)
    exp_copy["base_config_path_used"] = cfg.get("base_config_path", "configs/urban_berlin/exp04_tightchip_baseline.json")
    exp_copy["manifest_path_used"] = str(manifest_path.relative_to(root)) if manifest_path.is_relative_to(root) else str(manifest_path)
    exp_copy["checkpoint_used"] = str(ckpt.relative_to(root)) if ckpt.is_relative_to(root) else str(ckpt)
    exp_copy["config_name_used"] = config_name
    (out_dir / "experiment_config.json").write_text(json.dumps(exp_copy, indent=2), encoding="utf-8")

    print("Saved:", out_gpkg)
    print("Saved:", out_csv)
    print(gdf[["id", "sam_score", "n_pos", "n_neg"]])


if __name__ == "__main__":
    main()
