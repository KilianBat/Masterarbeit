from pathlib import Path
import sys
import json
import numpy as np
import pandas as pd
import cv2
from shapely import wkt
from shapely.ops import transform as shp_transform
from rasterio.transform import from_bounds


def main():
    if len(sys.argv) != 2:
        print("Usage: python scripts/geo_make_tightchips_experiment.py <config.json>")
        sys.exit(1)

    ROOT = Path(__file__).resolve().parents[1]
    cfg_path = ROOT / sys.argv[1]
    cfg = json.loads(cfg_path.read_text())

    exp_name = cfg["experiment_name"]
    source_manifest_path = ROOT / cfg["source_manifest_path"]
    out_manifest_path = ROOT / cfg["manifest_path"]

    ortho_img_path = ROOT / cfg["ortho_image"]
    ortho_meta_path = ROOT / cfg["ortho_meta"]

    chip_cfg = cfg["chip_generation"]
    CHIP_SIZE = chip_cfg["chip_size_px"]
    CONTEXT_FACTOR = chip_cfg["context_factor"]
    PADDING_M = chip_cfg["padding_m"]
    MIN_SIDE_M = chip_cfg["min_side_m"]
    MAX_SIDE_M = chip_cfg["max_side_m"]

    out_dir = out_manifest_path.parent
    chips_dir = out_dir / "chips"
    out_dir.mkdir(parents=True, exist_ok=True)

    # wichtig: alter chips-ordner sauber löschen, damit nichts verwechselt wird
    if chips_dir.exists():
        for p in chips_dir.glob("*"):
            p.unlink()
    else:
        chips_dir.mkdir(parents=True, exist_ok=True)

    src_df = pd.read_csv(source_manifest_path)

    meta = json.loads(ortho_meta_path.read_text())
    target_crs = meta["crs"]
    minx, miny, maxx, maxy = meta["bbox_proj"]
    width = meta["width"]
    height = meta["height"]

    ortho_bgr = cv2.imread(str(ortho_img_path))
    assert ortho_bgr is not None, ortho_img_path

    src_transform = from_bounds(minx, miny, maxx, maxy, width, height)
    inv = ~src_transform

    def world_to_pixel(x, y, z=None):
        x = np.asarray(x)
        y = np.asarray(y)
        cols = inv.a * x + inv.b * y + inv.c
        rows = inv.d * x + inv.e * y + inv.f
        return cols, rows

    rows = []

    for _, r in src_df.iterrows():
        obj_id = str(r["id"]).zfill(4)
        geom = wkt.loads(r["orig_wkt"])
        gx0, gy0, gx1, gy1 = geom.bounds

        width_m = gx1 - gx0
        height_m = gy1 - gy0

        side_m = max(width_m, height_m) * CONTEXT_FACTOR + 2.0 * PADDING_M
        side_m = max(side_m, MIN_SIDE_M)
        side_m = min(side_m, MAX_SIDE_M)

        cx, cy = geom.centroid.x, geom.centroid.y
        chip_bounds = (
            cx - side_m / 2.0,
            cy - side_m / 2.0,
            cx + side_m / 2.0,
            cy + side_m / 2.0,
        )

        # skip chips that would leave the ortho extent
        if (
            chip_bounds[0] < minx or chip_bounds[1] < miny or
            chip_bounds[2] > maxx or chip_bounds[3] > maxy
        ):
            continue

        c0, r0 = world_to_pixel(chip_bounds[0], chip_bounds[3])  # top-left
        c1, r1 = world_to_pixel(chip_bounds[2], chip_bounds[1])  # bottom-right

        x0 = max(0, int(np.floor(min(c0, c1))))
        x1 = min(width, int(np.ceil(max(c0, c1))))
        y0 = max(0, int(np.floor(min(r0, r1))))
        y1 = min(height, int(np.ceil(max(r0, r1))))

        crop = ortho_bgr[y0:y1, x0:x1]
        if crop.size == 0:
            continue

        chip_bgr = cv2.resize(crop, (CHIP_SIZE, CHIP_SIZE), interpolation=cv2.INTER_LINEAR)

        chip_path = chips_dir / f"{obj_id}.png"
        cv2.imwrite(str(chip_path), chip_bgr)

        chip_transform = from_bounds(*chip_bounds, CHIP_SIZE, CHIP_SIZE)
        chip_inv = ~chip_transform

        def world_to_chip_pixel(x, y, z=None):
            x = np.asarray(x)
            y = np.asarray(y)
            cols = chip_inv.a * x + chip_inv.b * y + chip_inv.c
            rows = chip_inv.d * x + chip_inv.e * y + chip_inv.f
            return cols, rows

        poly_px = shp_transform(world_to_chip_pixel, geom)

        rows.append({
            "id": int(r["id"]),
            "chip_path": str(chip_path),
            "orig_wkt": geom.wkt,
            "poly_px_wkt": poly_px.wkt,
            "chip_left": chip_bounds[0],
            "chip_bottom": chip_bounds[1],
            "chip_right": chip_bounds[2],
            "chip_top": chip_bounds[3],
            "chip_crs": target_crs,
            "area_m2": float(geom.area),
            "source_experiment": exp_name,
            "source_manifest_path": str(source_manifest_path),
        })

    out_df = pd.DataFrame(rows)
    out_df.to_csv(out_manifest_path, index=False)

    print("Saved manifest:", out_manifest_path)
    print("Num chips:", len(out_df))
    if len(out_df) > 0:
        print(out_df.head(3))


if __name__ == "__main__":
    main()