from pathlib import Path
import json
import geopandas as gpd
import osmnx as ox

ROOT = Path(__file__).resolve().parents[1]
cfg = json.loads((ROOT / "configs" / "berlin_mvp.json").read_text())

left, bottom, right, top = cfg["bbox_4326"]
osm_date = cfg.get("osm_date")  # optional

tags = {"building": True}

# save old setting so we can restore it afterwards
old_overpass_settings = ox.settings.overpass_settings

if osm_date:
    # historical snapshot via Overpass attic data
    ox.settings.overpass_settings = (
        f'[out:json][timeout:{{timeout}}]{{maxsize}}[date:"{osm_date}"]'
    )
    print("Using historical OSM snapshot date:", osm_date)
else:
    print("Using current OSM snapshot")

gdf = ox.features_from_bbox(
    bbox=(left, bottom, right, top),
    tags=tags,
).reset_index()

# restore default settings
ox.settings.overpass_settings = old_overpass_settings

# keep only polygonal building geometries
gdf = gdf[gdf.geometry.notnull()].copy()
gdf = gdf[gdf.geom_type.isin(["Polygon", "MultiPolygon"])].copy()

# normalize CRS
if gdf.crs is None:
    gdf = gdf.set_crs("EPSG:4326")
else:
    gdf = gdf.to_crs("EPSG:4326")

keep_cols = [c for c in ["element", "id", "building", "name", "geometry"] if c in gdf.columns]
gdf = gdf[keep_cols].copy()

out_dir = ROOT / "data" / "raw"
out_dir.mkdir(parents=True, exist_ok=True)

suffix = ""
if osm_date:
    suffix = "_" + osm_date[:10].replace("-", "")

geojson_path = out_dir / f"berlin_buildings{suffix}.geojson"
gpkg_path = out_dir / f"berlin_buildings{suffix}.gpkg"

gdf.to_file(geojson_path, driver="GeoJSON")
gdf.to_file(gpkg_path, layer="buildings", driver="GPKG")

print("Saved:", geojson_path)
print("Saved:", gpkg_path)
print("Buildings:", len(gdf))
print(gdf.head(3))