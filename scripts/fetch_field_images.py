"""
Download a labelled set of REAL FIELD photos (PlantDoc) to test the image
model on the kind of photo farmers actually take.

Source: Hugging Face dataset "Project-AgML/plant_doc_classification"
(PlantDoc: real-world leaf photos with clutter, shadows, multiple leaves).
Its 28 labels are mapped below onto our model's PlantVillage classes.

Run from the repository root:
    python scripts/fetch_field_images.py                 # 3 per class
    python scripts/fetch_field_images.py --per-class 6

Saves to data/eval_field/<our_class_index>__<label>__<n>.jpg (git-ignored).
Then:  python scripts/eval_model.py --dir data/eval_field
"""

import argparse
import json
from concurrent.futures import ThreadPoolExecutor
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = REPO_ROOT / "data" / "eval_field"
DATASET = "Project-AgML/plant_doc_classification"
API = "https://datasets-server.huggingface.co/filter"

# PlantDoc label index -> our model's class label (shared/content/labels.json)
PLANTDOC_TO_OURS = {
    0: "Apple___Apple_scab", 1: "Apple___healthy", 2: "Apple___Cedar_apple_rust",
    3: "Pepper___healthy", 4: "Pepper___Bacterial_spot", 5: "Blueberry___healthy",
    6: "Cherry___healthy", 7: "Corn___Cercospora_leaf_spot", 8: "Corn___Northern_Leaf_Blight",
    9: "Corn___Common_rust", 10: "Peach___healthy", 11: "Potato___Early_blight",
    12: "Potato___Late_blight", 13: "Raspberry___healthy", 14: "Soybean___healthy",
    15: "Squash___Powdery_mildew", 16: "Strawberry___healthy", 17: "Tomato___Early_blight",
    18: "Tomato___Septoria_leaf_spot", 19: "Tomato___healthy", 20: "Tomato___Bacterial_spot",
    21: "Tomato___Late_blight", 22: "Tomato___Tomato_mosaic_virus", 23: "Tomato___Yellow_Leaf_Curl_Virus",
    24: "Tomato___Leaf_Mold", 25: "Tomato___Spider_mites", 26: "Grape___healthy", 27: "Grape___Black_rot",
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--per-class", type=int, default=3)
    args = parser.parse_args()
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    ours = [c["label"] for c in json.loads((REPO_ROOT / "shared/content/labels.json").read_text(encoding="utf-8"))["classes"]]

    def fetch_class(item):
        """List one class's rows, then download its images (runs in a thread)."""
        pd_index, our_label = item
        our_index = ours.index(our_label)
        query = urllib.parse.urlencode({"dataset": DATASET, "config": "default", "split": "train",
                                        "where": f'"label"={pd_index}', "offset": 0, "length": args.per_class})
        for _ in range(4):
            try:
                with urllib.request.urlopen(f"{API}?{query}", timeout=120) as resp:
                    rows = json.load(resp)["rows"]
                break
            except OSError as err:
                print(f"  retry {our_label}: {err}")
                time.sleep(2)
        else:
            return 0
        new = 0
        for n, row in enumerate(rows, start=1):
            target = OUT_DIR / f"{our_index:02d}__{our_label}__{n}.jpg"
            if target.exists():
                continue
            for _ in range(3):
                try:
                    with urllib.request.urlopen(row["row"]["image"]["src"], timeout=180) as resp:
                        target.write_bytes(resp.read())
                    new += 1
                    break
                except OSError:
                    time.sleep(2)
        print(f"  {our_index:02d} {our_label}: {len(rows)}")
        return new

    # 8 classes at a time — the image server is slow per request, not per byte.
    with ThreadPoolExecutor(max_workers=8) as pool:
        saved = sum(pool.map(fetch_class, PLANTDOC_TO_OURS.items()))
    print(f"Done — {saved} new field photo(s) in {OUT_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
