from pathlib import Path
import sys
import json
import math
from io import BytesIO

import numpy as np
import requests
from PIL import Image
from pyproj import Transformer
from owslib.wms import WebMapService

def pick_layer(wms_obj):
    scored = []
    for name, layer in wms_obj.contents.items():
        blob = f"{name} {getattr(layer, 'title', '')}".lower()
        score = 0
        if "rgb" in blob:
            score += 3
        if "dop" in blob or "ortho" in blob:
            score += 2
        if "2025" in blob:
            score += 1
        scored.append((score, name, getattr(layer, "title", "")))
    scored.sort(reverse=True)
    return scored[0][1], scored[:10]

def main():
    if len(sys.argv) != 2:
        print("Usage: python scripts/geo_acquire_ortho_from_config.py <config.json>")
        sys.exit(1)

    ROOT = Path(__file__).resolve().parents[1]
    cfg = json.loads((ROOT / sys.argv[1]).read_text())

    area_name = cfg["area_name"]
    WMS_URL = cfg["wms_url"]
    left, bottom, right, top = cfg["bbox_4326"]

    out_dir = ROOT / "data" / "raw"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_img = out_dir / f"{area_name}_ortho_2025.png"
    out_meta = out_dir / f"{area_name}_ortho_2025_meta.json"

    wms = WebMapService(WMS_URL, version="1.3.0")
    layer_name, top_layers = pick_layer(wms)
    layer = wms[layer_name]

    print("Chosen layer:", layer_name)
    print("Top layer candidates:")
    for item in top_layers[:10]:
        print("  ", item)

    preferred_crs = ["EPSG:25833", "EPSG:3857"]
    target_crs = next((c for c in preferred_crs if c in layer.crsOptions), None)
    if target_crs is None:
        raise RuntimeError(f"No suitable projected CRS found. Available: {layer.crsOptions}")

    print("Chosen CRS:", target_crs)

    transformer = Transformer.from_crs("EPSG:4326", target_crs, always_xy=True)
    minx, miny = transformer.transform(left, bottom)
    maxx, maxy = transformer.transform(right, top)

    target_res = 0.20 if target_crs == "EPSG:25833" else max((maxx - minx) / 1800, (maxy - miny) / 1800)
    width = max(512, min(4096, math.ceil((maxx - minx) / target_res)))
    height = max(512, min(4096, math.ceil((maxy - miny) / target_res)))

    print("Projected bbox:", (minx, miny, maxx, maxy))
    print("Output size:", width, "x", height)

    params = {
        "SERVICE": "WMS",
        "VERSION": "1.3.0",
        "REQUEST": "GetMap",
        "LAYERS": layer_name,
        "STYLES": "",
        "CRS": target_crs,
        "BBOX": f"{minx},{miny},{maxx},{maxy}",
        "WIDTH": str(width),
        "HEIGHT": str(height),
        "FORMAT": "image/png",
        "TRANSPARENT": "FALSE",
    }

    resp = requests.get(WMS_URL, params=params, timeout=180)
    resp.raise_for_status()

    content_type = resp.headers.get("Content-Type", "")
    if "xml" in content_type.lower() or resp.content[:5] == b"<?xml":
        raise RuntimeError(f"WMS returned XML/error instead of image:\n{resp.text[:1000]}")

    img = Image.open(BytesIO(resp.content)).convert("RGB")
    arr = np.array(img)
    Image.fromarray(arr).save(out_img)

    meta = {
        "crs": target_crs,
        "bbox_proj": [minx, miny, maxx, maxy],
        "width": width,
        "height": height,
        "layer_name": layer_name,
        "wms_url": WMS_URL
    }
    out_meta.write_text(json.dumps(meta, indent=2))

    print("Saved image:", out_img)
    print("Saved meta :", out_meta)
    print("Raster shape:", arr.shape)

if __name__ == "__main__":
    main()