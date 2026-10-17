"""
Download a small labelled evaluation set (N images per class) from the
TEST split of the Hugging Face dataset
"BrandonFors/Plant-Diseases-PlantVillage-Dataset" (same 38 classes, same
order as our model).

Run from the repository root:
    python scripts/fetch_eval_images.py            # 2 per class -> 76 images
    python scripts/fetch_eval_images.py --per-class 5

Saves to data/eval/<class_index>__<label>__<n>.jpg (git-ignored).
Then measure accuracy with:  python scripts/eval_model.py

NOTE: these are PlantVillage-style lab photos, the same kind the model was
trained on. Good accuracy here proves the model is wired correctly; it does
NOT prove real-field accuracy (see docs/MODEL_CARD.md).
"""

import argparse
import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = REPO_ROOT / "data" / "eval"
DATASET = "BrandonFors/Plant-Diseases-PlantVillage-Dataset"
API = "https://datasets-server.huggingface.co/filter"


def get_json(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=120) as resp:
        return json.load(resp)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--per-class", type=int, default=2)
    args = parser.parse_args()
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    labels = json.loads((REPO_ROOT / "shared" / "content" / "labels.json").read_text(encoding="utf-8"))["classes"]
    saved = 0
    for index, cls in enumerate(labels):
        query = urllib.parse.urlencode({
            "dataset": DATASET, "config": "default", "split": "test",
            "where": f'"label"={index}', "offset": 0, "length": args.per_class,
        })
        for attempt in range(3):
            try:
                rows = get_json(f"{API}?{query}")["rows"]
                break
            except OSError as err:
                print(f"  class {index}: retry ({err})")
                time.sleep(2)
        else:
            print(f"  class {index}: skipped")
            continue

        for n, row in enumerate(rows, start=1):
            target = OUT_DIR / f"{index:02d}__{cls['label']}__{n}.jpg"
            if target.exists():
                continue
            src = row["row"]["image"]["src"]
            with urllib.request.urlopen(src, timeout=120) as resp:
                target.write_bytes(resp.read())
            saved += 1
        print(f"  {index:02d} {cls['label']}: {len(rows)} image(s)")
    print(f"Done — {saved} new image(s) in {OUT_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
