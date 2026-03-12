from pathlib import Path
import json
import geopandas as gpd
import osmnx as ox

ROOT = Path(__file__).resolve().parents[1]
cfg = json.loads((ROOT / "configs" / "berlin_mvp.json").read_text())

left, bottom, right, top = cfg["bbox_4326"]

tags = {"building": True}

gdf = ox.features_from_bbox(
    bbox=(left, bottom, right, top),
    tags=tags,
).reset_index()

# keep only polygonal building geometries
gdf = gdf[gdf.geometry.notnull()].copy()
gdf = gdf[gdf.geom_type.isin(["Polygon", "MultiPolygon"])].copy()

# normalize CRS
if gdf.crs is None:
    gdf = gdf.set_crs("EPSG:4326")
else:
    gdf = gdf.to_crs("EPSG:4326")

# keep a compact set of useful columns
keep_cols = [c for c in ["element", "id", "building", "name", "geometry"] if c in gdf.columns]
gdf = gdf[keep_cols].copy()

out_dir = ROOT / "data" / "raw"
out_dir.mkdir(parents=True, exist_ok=True)

geojson_path = out_dir / "berlin_buildings.geojson"
gpkg_path = out_dir / "berlin_buildings.gpkg"

gdf.to_file(geojson_path, driver="GeoJSON")
gdf.to_file(gpkg_path, layer="buildings", driver="GPKG")

print("Saved:", geojson_path)
print("Saved:", gpkg_path)
print("Buildings:", len(gdf))
print(gdf.head(3))