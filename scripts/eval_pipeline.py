"""
Compare image models × preprocessing × ranking on labelled photos.

Run from the repository root:
    python scripts/eval_pipeline.py                          # default grid
    python scripts/eval_pipeline.py --models mobilenetv2-daksh hf:candidates/plant-disease-dinov2-small

Datasets (download first):
    data/eval/        PlantVillage-style lab photos  (scripts/fetch_eval_images.py)
    data/eval_field/  real field photos, PlantDoc     (scripts/fetch_field_images.py)

Ranking methods:
    global      top class among all 38 (what the app did before)
    crop        only the farmer's registered crop's classes (here: the true
                crop of the photo, as a farmer would register it)

Metrics: top-1 accuracy, top-3 accuracy, macro-F1 over the classes present,
and average milliseconds per photo. Results are printed as tables and
saved to data/eval_results.json.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np
from PIL import Image

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from backend.ml.classifier_labels import load_labels  # noqa: E402
from backend.ml.models import load_backend  # noqa: E402
from backend.ml.preprocess import preprocess  # noqa: E402

DEFAULT_MODELS = [
    "mobilenetv2-daksh",
    "hf:candidates/mobilenet_v2_1.0_224-plant-disease-identification",
    "hf:candidates/plant-disease-dinov2-small",
    "hf:candidates/convnext-tiny-plantvillage",
]
# name -> preprocessing steps ("raw" = no processing at all, as before)
PREPROCESSING = {
    "raw": (),
    "exif": ("exif",),
    "exif+crop": ("exif", "leaf_crop"),
    "exif+crop+bg": ("exif", "leaf_crop", "background"),
    "exif+clahe": ("exif", "clahe"),
    "exif+wb": ("exif", "white_bal"),
    "exif+crop+clahe": ("exif", "leaf_crop", "clahe"),
    "exif+denoise": ("exif", "denoise"),
}


def macro_f1(true: list[int], pred: list[int]) -> float:
    classes = sorted(set(true))
    scores = []
    for c in classes:
        tp = sum(1 for t, p in zip(true, pred) if t == c and p == c)
        fp = sum(1 for t, p in zip(true, pred) if t != c and p == c)
        fn = sum(1 for t, p in zip(true, pred) if t == c and p != c)
        prec = tp / (tp + fp) if tp + fp else 0.0
        rec = tp / (tp + fn) if tp + fn else 0.0
        scores.append(2 * prec * rec / (prec + rec) if prec + rec else 0.0)
    return float(np.mean(scores)) if scores else 0.0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--models", nargs="*", default=DEFAULT_MODELS)
    parser.add_argument("--prep", nargs="*", default=list(PREPROCESSING))
    args = parser.parse_args()

    labels = load_labels()
    crop_of = np.array([l.crop for l in labels])
    datasets = {name: sorted((REPO_ROOT / "data" / folder).glob("*.jpg"))
                for name, folder in (("lab", "eval"), ("field", "eval_field"))}
    images = {name: [(int(f.name.split("__")[0]), Image.open(f)) for f in files] for name, files in datasets.items()}
    for name, items in images.items():
        for _, img in items:
            img.load()
        print(f"{name}: {len(items)} photos, {len({t for t, _ in items})} classes")

    results = []
    for spec in args.models:
        backend = load_backend(spec)
        for prep_name in args.prep:
            steps = PREPROCESSING[prep_name]
            for ds_name, items in images.items():
                if not items:
                    continue
                truth, pred_g, pred_c, top3_g, top3_c, times = [], [], [], 0, 0, []
                for true_idx, img in items:
                    t0 = time.perf_counter()
                    prepared = preprocess(img, steps).image if steps else img.convert("RGB")
                    p = backend.probs(prepared)
                    times.append(time.perf_counter() - t0)
                    truth.append(true_idx)
                    order = np.argsort(-p)
                    pred_g.append(int(order[0]))
                    top3_g += true_idx in order[:3]
                    masked = np.where(crop_of == crop_of[true_idx], p, -1.0)
                    order_c = np.argsort(-masked)
                    pred_c.append(int(order_c[0]))
                    top3_c += true_idx in order_c[:3]
                n = len(truth)
                row = {
                    "model": spec, "prep": prep_name, "data": ds_name, "n": n,
                    "global_top1": sum(t == p for t, p in zip(truth, pred_g)) / n,
                    "global_top3": top3_g / n,
                    "global_f1": macro_f1(truth, pred_g),
                    "crop_top1": sum(t == p for t, p in zip(truth, pred_c)) / n,
                    "crop_top3": top3_c / n,
                    "crop_f1": macro_f1(truth, pred_c),
                    "ms": 1000 * float(np.mean(times)),
                }
                results.append(row)
                print(f"  {spec.split('/')[-1][:34]:34} {prep_name:16} {ds_name:5} "
                      f"global top1 {row['global_top1']:5.0%} F1 {row['global_f1']:.2f} | "
                      f"crop top1 {row['crop_top1']:5.0%} F1 {row['crop_f1']:.2f} | {row['ms']:.0f} ms", flush=True)

    (REPO_ROOT / "data" / "eval_results.json").write_text(json.dumps(results, indent=2))
    print("\nBest on FIELD photos (crop-aware ranking):")
    field = sorted((r for r in results if r["data"] == "field"), key=lambda r: (-r["crop_f1"], r["ms"]))
    for r in field[:8]:
        print(f"  {r['model'].split('/')[-1][:34]:34} {r['prep']:16} top1 {r['crop_top1']:.0%}  top3 {r['crop_top3']:.0%}  F1 {r['crop_f1']:.2f}  {r['ms']:.0f} ms")
    return 0


if __name__ == "__main__":
    sys.exit(main())
