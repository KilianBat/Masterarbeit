from pathlib import Path
import json
import numpy as np
import pandas as pd
import geopandas as gpd
import cv2
from shapely.geometry import box
from shapely.ops import transform as shp_transform
from rasterio.transform import from_bounds

ROOT = Path(__file__).resolve().parents[1]
cfg = json.loads((ROOT / "configs" / "berlin_mvp.json").read_text())

ORTHO_IMG = ROOT / "data" / "raw" / "berlin_ortho_2025.png"
ORTHO_META = ROOT / "data" / "raw" / "berlin_ortho_2025_meta.json"

osm_date = cfg.get("osm_date")
suffix = ""
if osm_date:
    suffix = "_" + osm_date[:10].replace("-", "")
BUILDINGS_PATH = ROOT / "data" / "raw" / f"berlin_buildings{suffix}.geojson"

CHIP_SIZE = cfg["chip_size_px"]
SAMPLE_N = cfg["sample_n"]
MIN_AREA = cfg["min_area_m2"]
MAX_AREA = cfg["max_area_m2"]

out_dir = ROOT / "data" / "processed" / "berlin_mvp"
chips_dir = out_dir / "chips"
out_dir.mkdir(parents=True, exist_ok=True)
chips_dir.mkdir(parents=True, exist_ok=True)

meta = json.loads(ORTHO_META.read_text())
target_crs = meta["crs"]
minx, miny, maxx, maxy = meta["bbox_proj"]
width = meta["width"]
height = meta["height"]

img_bgr = cv2.imread(str(ORTHO_IMG))
assert img_bgr is not None, ORTHO_IMG

src_transform = from_bounds(minx, miny, maxx, maxy, width, height)
inv = ~src_transform
ortho_box = box(minx, miny, maxx, maxy)

gdf = gpd.read_file(BUILDINGS_PATH).to_crs(target_crs)
gdf = gdf[gdf.geometry.notnull()].copy()
gdf = gdf[gdf.geom_type.isin(["Polygon", "MultiPolygon"])].copy()
gdf["area_m2"] = gdf.geometry.area
gdf = gdf[(gdf["area_m2"] >= MIN_AREA) & (gdf["area_m2"] <= MAX_AREA)].copy()
gdf = gdf[gdf.geometry.intersects(ortho_box)].copy()

if len(gdf) == 0:
    raise RuntimeError("No buildings remain after filtering.")

gdf = gdf.sample(n=min(SAMPLE_N, len(gdf)), random_state=42)

def world_to_pixel(x, y, z=None):
    x = np.asarray(x)
    y = np.asarray(y)
    cols = inv.a * x + inv.b * y + inv.c
    rows = inv.d * x + inv.e * y + inv.f
    return cols, rows

rows = []

for i, (_, row) in enumerate(gdf.iterrows(), start=1):
    geom = row.geometry
    gx0, gy0, gx1, gy1 = geom.bounds

    width_m = gx1 - gx0
    height_m = gy1 - gy0
    side_m = max(width_m, height_m) * 2.0 + 20.0
    side_m = max(side_m, 60.0)

    cx, cy = geom.centroid.x, geom.centroid.y
    chip_bounds = (
        cx - side_m / 2,
        cy - side_m / 2,
        cx + side_m / 2,
        cy + side_m / 2,
    )

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

    crop = img_bgr[y0:y1, x0:x1]
    if crop.size == 0:
        continue

    chip_bgr = cv2.resize(crop, (CHIP_SIZE, CHIP_SIZE), interpolation=cv2.INTER_LINEAR)

    chip_id = f"{i:04d}"
    chip_path = chips_dir / f"{chip_id}.png"
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
        "id": chip_id,
        "chip_path": str(chip_path),
        "orig_wkt": geom.wkt,
        "poly_px_wkt": poly_px.wkt,
        "chip_left": chip_bounds[0],
        "chip_bottom": chip_bounds[1],
        "chip_right": chip_bounds[2],
        "chip_top": chip_bounds[3],
        "chip_crs": target_crs,
        "area_m2": float(geom.area),
    })

manifest = pd.DataFrame(rows)
manifest_path = out_dir / "manifest.csv"
manifest.to_csv(manifest_path, index=False)

print("Saved manifest:", manifest_path)
print("Num chips:", len(manifest))
print(manifest.head(3))