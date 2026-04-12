from pathlib import Path
import sys
import json
import pandas as pd
import geopandas as gpd
import fiona

def load_buildings(path):
    layers = fiona.listlayers(path)
    layer = "buildings" if "buildings" in layers else layers[0]
    gdf = gpd.read_file(path, layer=layer)
    gdf = gdf[gdf.geometry.notnull()].copy()
    gdf = gdf[gdf.geom_type.isin(["Polygon", "MultiPolygon"])].copy()
    return gdf

def main():
    if len(sys.argv) != 2:
        print("Usage: python scripts/rural_select_new_subset.py <config.json>")
        sys.exit(1)

    ROOT = Path(__file__).resolve().parents[1]
    cfg = json.loads((ROOT / sys.argv[1]).read_text())

    subset_name = cfg["subset_name"]
    src_path = ROOT / cfg["source_new_candidates_path"]
    sample_n = int(cfg["selection"]["sample_n"])
    random_seed = int(cfg["selection"]["random_seed"])

    out_dir = ROOT / "data" / "processed" / subset_name
    out_dir.mkdir(parents=True, exist_ok=True)

    out_subset_gpkg = out_dir / "current_subset.gpkg"
    out_subset_geojson = out_dir / "current_subset.geojson"
    out_summary_csv = out_dir / "subset_summary.csv"

    gdf = load_buildings(src_path).reset_index(drop=True).copy()

    if "id" in gdf.columns:
        gdf["current_osm_id"] = gdf["id"]
    else:
        gdf["current_osm_id"] = gdf.index

    if len(gdf) > sample_n:
        gdf = gdf.sample(n=sample_n, random_state=random_seed).copy()

    gdf["subset_id"] = range(1, len(gdf) + 1)

    if out_subset_gpkg.exists():
        out_subset_gpkg.unlink()
    if out_subset_geojson.exists():
        out_subset_geojson.unlink()
    if out_summary_csv.exists():
        out_summary_csv.unlink()

    gdf.to_file(out_subset_gpkg, layer="buildings", driver="GPKG")
    gdf.to_file(out_subset_geojson, driver="GeoJSON")
    pd.DataFrame(gdf.drop(columns="geometry")).to_csv(out_summary_csv, index=False)

    print("Saved subset GPKG   :", out_subset_gpkg)
    print("Saved subset GeoJSON:", out_subset_geojson)
    print("Saved summary CSV   :", out_summary_csv)
    print()
    print("Num new candidates in subset:", len(gdf))
    print(gdf[["subset_id", "current_osm_id"]].head(10))

if __name__ == "__main__":
    main()