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
        print("Usage: python scripts/rural_select_status_subset.py <config.json>")
        sys.exit(1)

    ROOT = Path(__file__).resolve().parents[1]
    cfg = json.loads((ROOT / sys.argv[1]).read_text())

    area_name = cfg["area_name"]
    subset_name = cfg["subset_name"]
    hist_date = cfg["osm_date_historic"][:10].replace("-", "")
    include_statuses = set(cfg["selection"]["include_statuses"])
    source_full_status_csv = ROOT / cfg["source_full_status_csv"]
    random_seed = int(cfg["selection"].get("random_seed", 42))
    sample_n_per_status = cfg["selection"].get("sample_n_per_status", {})

    hist_path = ROOT / "data" / "raw" / f"{area_name}_buildings_{hist_date}.gpkg"

    out_dir = ROOT / "data" / "processed" / subset_name
    out_dir.mkdir(parents=True, exist_ok=True)

    out_subset_gpkg = out_dir / "historic_subset.gpkg"
    out_subset_geojson = out_dir / "historic_subset.geojson"
    out_summary_csv = out_dir / "subset_summary.csv"

    hist = load_buildings(hist_path).reset_index(drop=True).copy()
    hist["hist_row_idx"] = hist.index
    hist["hist_osm_id"] = hist["id"] if "id" in hist.columns else hist.index

    full_status = pd.read_csv(source_full_status_csv)

    merged = hist.merge(
        full_status,
        on=["hist_row_idx", "hist_osm_id"],
        how="inner"
    )

    subset_parts = []
    for status in include_statuses:
        part = merged[merged["status"] == status].copy()
        n_sample = sample_n_per_status.get(status, None)

        if n_sample is not None:
            n_sample = min(int(n_sample), len(part))
            if n_sample > 0:
                part = part.sample(n=n_sample, random_state=random_seed)

        subset_parts.append(part)

    subset = pd.concat(subset_parts, ignore_index=True) if subset_parts else merged.iloc[0:0].copy()
    subset = gpd.GeoDataFrame(subset, geometry="geometry", crs=hist.crs)
    subset["subset_id"] = range(1, len(subset) + 1)

    if out_subset_gpkg.exists():
        out_subset_gpkg.unlink()
    if out_subset_geojson.exists():
        out_subset_geojson.unlink()
    if out_summary_csv.exists():
        out_summary_csv.unlink()

    subset.to_file(out_subset_gpkg, layer="buildings", driver="GPKG")
    subset.to_file(out_subset_geojson, driver="GeoJSON")
    pd.DataFrame(subset.drop(columns="geometry")).to_csv(out_summary_csv, index=False)

    print("Saved subset GPKG   :", out_subset_gpkg)
    print("Saved subset GeoJSON:", out_subset_geojson)
    print("Saved summary CSV   :", out_summary_csv)
    print()
    print("Subset status counts:")
    print(subset["status"].value_counts(dropna=False))
    print()
    if len(subset) > 0:
        print(subset[["subset_id", "hist_osm_id", "status", "best_iou_to_2025"]].head(10))

if __name__ == "__main__":
    main()