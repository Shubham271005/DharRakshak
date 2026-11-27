"""
Download a Hugging Face image model at its pinned revision.

Run from the repository root:
    python scripts/download_model.py               # the model named by DHARRAKSHAK_MODEL
    python scripts/download_model.py --all         # every downloadable candidate (for evaluation)

The DEFAULT model (`daksh-mobilenetv2`) is not downloadable: it has no
Hugging Face repo, and its ONNX export is already committed to the repo
(models/plant-disease-mobilenetv2/mobilenetv2_plant.onnx). Point
DHARRAKSHAK_MODEL at one of the Hugging Face candidates first, e.g.

    DHARRAKSHAK_MODEL=linkanjarad-mobilenetv2 python scripts/download_model.py

or fetch every candidate at once with --all.

Files go to models/<name>/ (git-ignored). Run once per laptop BEFORE the
demo, while you still have good internet. Downloads resume if interrupted.
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from backend import config  # noqa: E402,F401  (reads DHARRAKSHAK_MODEL from .env)
from backend.ml import classifier as clf  # noqa: E402


def main() -> int:
    names = [n for n, m in clf.MODELS.items() if not m.get("legacy")] if "--all" in sys.argv else [clf.selected_model()]
    failed = False
    for name in names:
        spec = clf.MODELS[name]
        if spec.get("legacy"):
            # This model has no Hugging Face repo to fetch. Its ONNX export is
            # committed instead, so a fresh clone already has usable weights.
            # (Before this check, reading spec["repo"] below raised a bare
            # KeyError, which also aborted scripts/run_demo.sh on a clean clone.)
            folder = clf.model_folder(name)
            present = sorted(p.name for p in folder.glob("mobilenetv2_plant.*")) if folder.exists() else []
            print(f"{name}: nothing to download — it is the legacy model with no Hugging Face repo.")
            if present:
                print(f"  Weights already in {folder}: {', '.join(present)}")
            else:
                print(f"  Expected {folder}/mobilenetv2_plant.onnx (committed to the repository).")
            print("  To fetch a Hugging Face candidate instead: python scripts/download_model.py --all")
            continue
        print(f"Downloading {name}: {spec['repo']} @ {spec['revision'][:8]} (license: {spec['license']})")
        for attempt in range(1, 6):
            try:
                print(f"  OK -> {clf.download_model(name)}")
                break
            except OSError as err:
                print(f"  attempt {attempt} interrupted ({err}); retrying…")
        else:
            print("  Download failed after 5 attempts. Check your internet and run again.")
            failed = True
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
