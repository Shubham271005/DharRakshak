"""
Try the image model on one or more photos from the command line.

Run from the repository root:
    python scripts/try_model.py data/samples/tomato_early_blight.jpg
    python scripts/try_model.py data/samples/*.jpg

Prints the top-3 possibilities, confidence, and whether the result counts
as uncertain. Use it to sanity-check the model on real field photos and to
tune UNCERTAIN_THRESHOLD in backend/ml/classifier.py.
"""

import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from backend.ml import classifier as clf  # noqa: E402


def main(paths: list[str]) -> int:
    if not paths:
        print(__doc__)
        return 1
    started = time.perf_counter()
    model = clf.get_classifier()
    print(f"Model loaded in {time.perf_counter() - started:.1f}s\n")

    for p in paths:
        try:
            t0 = time.perf_counter()
            out = model.classify(Path(p).read_bytes())
            ms = (time.perf_counter() - t0) * 1000
        except (OSError, clf.InvalidImage) as err:
            print(f"{p}: could not analyze ({err})\n")
            continue
        flag = "  ⚠ UNCERTAIN" if out.uncertain else ""
        print(f"{p}  ({ms:.0f} ms){flag}")
        for pred in out.predictions:
            print(f"   {pred.confidence:6.1%}  {pred.display_name.en}")
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
