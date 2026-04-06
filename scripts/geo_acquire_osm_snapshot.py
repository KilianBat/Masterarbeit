from pathlib import Path
import sys
import json
import geopandas as gpd
import osmnx as ox

def main():
    if len(sys.argv) != 3:
        print("Usage: python scripts/geo_acquire_osm_snapshot.py <config.json> <historic|current>")
        sys.exit(1)

    ROOT = Path(__file__).resolve().parents[1]
    cfg = json.loads((ROOT / sys.argv[1]).read_text())
    mode = sys.argv[2].strip().lower()

    if mode not in {"historic", "current"}:
        raise ValueError("Mode must be 'historic' or 'current'")

    area_name = cfg["area_name"]
    left, bottom, right, top = cfg["bbox_4326"]
    osm_date = cfg.get("osm_date_historic") if mode == "historic" else None

    tags = {"building": True}

    old_overpass_settings = ox.settings.overpass_settings
    try:
        if osm_date:
            ox.settings.overpass_settings = f'[out:json][timeout:{{timeout}}]{{maxsize}}[date:"{osm_date}"]'
            print("Using historical OSM snapshot date:", osm_date)
        else:
            print("Using current OSM snapshot")

        gdf = ox.features_from_bbox(
            bbox=(left, bottom, right, top),
            tags=tags,
        ).reset_index()

    finally:
        ox.settings.overpass_settings = old_overpass_settings

    gdf = gdf[gdf.geometry.notnull()].copy()
    gdf = gdf[gdf.geom_type.isin(["Polygon", "MultiPolygon"])].copy()

    if gdf.crs is None:
        gdf = gdf.set_crs("EPSG:4326")
    else:
        gdf = gdf.to_crs("EPSG:4326")

    keep_cols = [c for c in ["element", "id", "building", "name", "geometry"] if c in gdf.columns]
    gdf = gdf[keep_cols].copy()

    out_dir = ROOT / "data" / "raw"
    out_dir.mkdir(parents=True, exist_ok=True)

    if mode == "historic":
        suffix = "_" + cfg["osm_date_historic"][:10].replace("-", "")
    else:
        suffix = ""

    geojson_path = out_dir / f"{area_name}_buildings{suffix}.geojson"
    gpkg_path = out_dir / f"{area_name}_buildings{suffix}.gpkg"

    gdf.to_file(geojson_path, driver="GeoJSON")
    gdf.to_file(gpkg_path, layer="buildings", driver="GPKG")

    print("Saved:", geojson_path)
    print("Saved:", gpkg_path)
    print("Buildings:", len(gdf))
    print(gdf.head(3))

if __name__ == "__main__":
    main()