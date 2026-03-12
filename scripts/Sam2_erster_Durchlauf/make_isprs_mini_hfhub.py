from pathlib import Path
import random
import shutil
import pandas as pd
from huggingface_hub import HfApi, hf_hub_download


def pick_subdir(files, preferred=("potsdam", "vaihingen")):
    """
    Try to pick a dataset subdir that contains both img_dir and ann_dir.
    Many repos use: <subdir>/img_dir and <subdir>/ann_dir
    """
    candidates = set()
    for f in files:
        parts = Path(f).parts
        if len(parts) >= 2 and parts[0] != ".":
            candidates.add(parts[0])  # top-level folder
    # preference order
    for p in preferred:
        if p in candidates:
            return p
    # fallback: first candidate
    return sorted(candidates)[0] if candidates else None


def main():
    ROOT = Path(__file__).resolve().parents[1]
    out_dir = ROOT / "data" / "processed" / "isprs_mini"
    img_out = out_dir / "images"
    msk_out = out_dir / "masks"
    img_out.mkdir(parents=True, exist_ok=True)
    msk_out.mkdir(parents=True, exist_ok=True)

    repo_id = "wsdwJohn1231/Geo_dataset"
    n_samples = 50
    seed = 42

    rng = random.Random(seed)
    api = HfApi()

    print("Listing repo files (dataset)...")
    files = api.list_repo_files(repo_id=repo_id, repo_type="dataset")

    # find a usable subdir automatically (potsdam or vaihingen)
    subdir = pick_subdir(files, preferred=("potsdamRGB", "potsdam", "vaihingen"))
    if subdir is None:
        raise RuntimeError("Could not detect a subdir in repo.")

    img_prefix = f"{subdir}/img_dir/"
    ann_prefix = f"{subdir}/ann_dir/"

    img_files = [f for f in files if f.startswith(img_prefix)]
    ann_files = [f for f in files if f.startswith(ann_prefix)]

    # If auto subdir guess is wrong, show hints
    print(f"Detected subdir: {subdir}")
    print(f"Found {len(img_files)} images under {img_prefix}")
    print(f"Found {len(ann_files)} masks under {ann_prefix}")

    if len(img_files) == 0 or len(ann_files) == 0:
        # print a few file prefixes to help debugging
        print("Top-level dirs detected:", sorted({Path(f).parts[0] for f in files})[:20])
        raise RuntimeError("No img_dir/ann_dir found in detected subdir. Dataset layout may differ.")

    # map masks by stem
    ann_map = {Path(f).stem: f for f in ann_files}

    paired = []
    for f in img_files:
        stem = Path(f).stem
        if stem in ann_map:
            paired.append((f, ann_map[stem]))

    print(f"Found {len(paired)} paired image/mask candidates.")
    if len(paired) == 0:
        # Sometimes naming differs slightly; show a few examples
        print("Example image names:", [Path(f).name for f in img_files[:5]])
        print("Example mask names:", [Path(f).name for f in ann_files[:5]])
        raise RuntimeError("No pairs found by stem matching.")

    rng.shuffle(paired)
    paired = paired[:n_samples]

    rows = []
    for i, (img_path, ann_path) in enumerate(paired, start=1):
        sid = f"{i:04d}"
        img_name = Path(img_path).name
        ann_name = Path(ann_path).name

        img_cached = hf_hub_download(repo_id=repo_id, repo_type="dataset", filename=img_path)
        ann_cached = hf_hub_download(repo_id=repo_id, repo_type="dataset", filename=ann_path)

        img_dst = img_out / f"{sid}_{img_name}"
        ann_dst = msk_out / f"{sid}_{ann_name}"

        shutil.copyfile(img_cached, img_dst)
        shutil.copyfile(ann_cached, ann_dst)

        rows.append({
            "id": sid,
            "image_path": str(img_dst),
            "mask_path": str(ann_dst),
            "orig_image_file": img_path,
            "orig_mask_file": ann_path,
            "subdir": subdir
        })

        if i % 10 == 0:
            print(f"Downloaded {i}/{n_samples}")

    manifest = out_dir / "manifest.csv"
    pd.DataFrame(rows).to_csv(manifest, index=False)
    print("Wrote:", manifest)
    print("Example row:", rows[0])


if __name__ == "__main__":
    main()