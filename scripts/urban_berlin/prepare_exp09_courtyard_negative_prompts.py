#!/usr/bin/env python3
"""Prepare targeted negative point prompts for urban courtyard cases.

This script does not run SAM2 inference. It creates a checked prompt plan and
annotated chip previews so that negative points can be placed deliberately.
This avoids the main weakness of the earlier ring-negative experiment: applying
exclusion prompts globally instead of only where there is a clear courtyard or
non-building region to exclude.

Usage:
    python scripts/urban_berlin/prepare_exp09_courtyard_negative_prompts.py \
        --config configs/urban_berlin/exp09_courtyard_negative_prompts.json

Outputs:
    outputs/urban_exp09_courtyard_negative_prompts/prompt_plan.csv
    outputs/urban_exp09_courtyard_negative_prompts/figures/prompt_debug_idXXXX.png
    outputs/urban_exp09_courtyard_negative_prompts/figures/prompt_plan_overview.png
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

import pandas as pd
from PIL import Image, ImageDraw, ImageFont


def load_config(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def find_chip(repo_root: Path, candidate_dirs: List[str], object_id: int) -> Path:
    name = f"{object_id:04d}.png"
    for d in candidate_dirs:
        p = repo_root / d / name
        if p.exists():
            return p
    raise FileNotFoundError(
        f"Could not find chip {name} in any configured chip directory: {candidate_dirs}"
    )


def safe_font(size: int = 20):
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    ]
    for c in candidates:
        p = Path(c)
        if p.exists():
            return ImageFont.truetype(str(p), size)
    return ImageFont.load_default()


def draw_prompt_preview(
    image: Image.Image,
    object_id: int,
    reason: str,
    positive_points: List[Tuple[int, int]],
    negative_points: List[Tuple[int, int]],
) -> Image.Image:
    img = image.convert("RGB").copy()
    draw = ImageDraw.Draw(img)
    w, h = img.size

    # Draw coordinate grid to make manual correction easier.
    grid_step = 128 if min(w, h) >= 512 else max(64, min(w, h) // 4)
    for x in range(0, w, grid_step):
        draw.line([(x, 0), (x, h)], fill=(255, 255, 255), width=1)
        draw.text((x + 3, 3), str(x), fill=(0, 0, 0), font=safe_font(12))
    for y in range(0, h, grid_step):
        draw.line([(0, y), (w, y)], fill=(255, 255, 255), width=1)
        draw.text((3, y + 3), str(y), fill=(0, 0, 0), font=safe_font(12))

    # Positive points: green circles.
    for x, y in positive_points:
        r = 10
        draw.ellipse((x - r, y - r, x + r, y + r), outline=(0, 180, 0), width=5)
        draw.line((x - 14, y, x + 14, y), fill=(0, 180, 0), width=3)
        draw.line((x, y - 14, x, y + 14), fill=(0, 180, 0), width=3)

    # Negative points: red crosses.
    for x, y in negative_points:
        r = 12
        draw.line((x - r, y - r, x + r, y + r), fill=(220, 0, 0), width=5)
        draw.line((x - r, y + r, x + r, y - r), fill=(220, 0, 0), width=5)
        draw.ellipse((x - r - 4, y - r - 4, x + r + 4, y + r + 4), outline=(220, 0, 0), width=3)

    # Add title band.
    band_h = 95
    canvas = Image.new("RGB", (w, h + band_h), "white")
    canvas.paste(img, (0, band_h))
    d = ImageDraw.Draw(canvas)
    d.text((12, 10), f"Exp09 prompt plan - ID {object_id}", fill=(0, 0, 0), font=safe_font(24))
    d.text((12, 45), reason[:120], fill=(0, 0, 0), font=safe_font(15))
    d.text((12, 70), "green = positive point, red = negative point", fill=(0, 0, 0), font=safe_font(14))
    return canvas


def make_overview(previews: List[Image.Image], labels: List[str], out_path: Path) -> None:
    if not previews:
        return
    thumb_w = 420
    thumbs = []
    for img in previews:
        scale = thumb_w / img.width
        thumbs.append(img.resize((thumb_w, int(img.height * scale))))
    pad = 18
    total_w = len(thumbs) * thumb_w + (len(thumbs) + 1) * pad
    total_h = max(t.height for t in thumbs) + 80
    canvas = Image.new("RGB", (total_w, total_h), "white")
    draw = ImageDraw.Draw(canvas)
    draw.text((pad, 12), "Exp09 targeted courtyard negative prompts - prompt plan", fill=(0, 0, 0), font=safe_font(24))
    for i, (thumb, label) in enumerate(zip(thumbs, labels)):
        x = pad + i * (thumb_w + pad)
        y = 58
        canvas.paste(thumb, (x, y))
        draw.text((x, y + thumb.height + 4), label, fill=(0, 0, 0), font=safe_font(14))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out_path)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, help="Path to exp09 config JSON")
    args = parser.parse_args()

    cfg_path = Path(args.config)
    cfg = load_config(cfg_path)
    repo_root = Path(cfg.get("repo_root", ".")).resolve()
    out_dir = repo_root / cfg["output_dir"]
    fig_dir = out_dir / "figures"
    out_dir.mkdir(parents=True, exist_ok=True)
    fig_dir.mkdir(parents=True, exist_ok=True)

    rows = []
    previews = []
    labels = []

    for case in cfg["target_cases"]:
        object_id = int(case["id"])
        chip_path = find_chip(repo_root, cfg["candidate_chip_dirs"], object_id)
        img = Image.open(chip_path)
        pos = [tuple(map(int, p)) for p in case.get("positive_points_px", [])]
        neg = [tuple(map(int, p)) for p in case.get("negative_points_px", [])]
        reason = case.get("reason", "")
        preview = draw_prompt_preview(img, object_id, reason, pos, neg)
        preview_path = fig_dir / f"prompt_debug_id{object_id:04d}.png"
        preview.save(preview_path)
        previews.append(preview)
        labels.append(f"ID {object_id}")
        rows.append({
            "id": object_id,
            "chip_path": str(chip_path.relative_to(repo_root)),
            "positive_points_px": json.dumps(pos),
            "negative_points_px": json.dumps(neg),
            "reason": reason,
            "manual_review_required": bool(case.get("manual_review_required", True)),
            "debug_figure": str(preview_path.relative_to(repo_root)),
        })

    df = pd.DataFrame(rows)
    df.to_csv(out_dir / "prompt_plan.csv", index=False)
    make_overview(previews, labels, fig_dir / "prompt_plan_overview.png")

    md = out_dir / "README_EXP09_PROMPT_PLAN.md"
    md.write_text(
        "# Exp09 targeted courtyard negative prompts\n\n"
        "This folder contains a prompt plan for the targeted negative point experiment.\n\n"
        "Before running SAM2 inference, open the debug figures and check whether the red negative points lie inside the courtyard or non-building region that should be excluded. "
        "If not, edit `configs/urban_berlin/exp09_courtyard_negative_prompts.json` and run this preparation script again.\n\n"
        "The experiment should be interpreted as a targeted follow-up to the earlier global ring-negative experiment. It tests whether negative prompts help when applied only to cases where a clear exclusion region exists.\n",
        encoding="utf-8",
    )

    print(f"Wrote prompt plan: {out_dir / 'prompt_plan.csv'}")
    print(f"Wrote debug figures: {fig_dir}")
    print("Next: inspect red negative points and adjust config before running SAM2 inference.")


if __name__ == "__main__":
    main()
