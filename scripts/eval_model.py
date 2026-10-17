"""
Measure the image model's accuracy on the labelled images in data/eval/
(download them first with scripts/fetch_eval_images.py).

Run from the repository root:
    python scripts/eval_model.py

Each file name starts with its true class index ("29__Tomato___Early_blight__1.jpg"),
so the script can check top-1 and top-3 accuracy, list every mistake, and
report how many correct/incorrect answers fell below the uncertainty
threshold. Use it to tune UNCERTAIN_THRESHOLD.
"""

import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from backend.ml import classifier as clf  # noqa: E402

EVAL_DIR = REPO_ROOT / "data" / "eval"


def main() -> int:
    files = sorted(EVAL_DIR.glob("*.jpg"))
    if not files:
        print("No images in data/eval/. Run: python scripts/fetch_eval_images.py")
        return 1

    model = clf.get_classifier()
    labels = model.labels
    top1 = top3 = uncertain_right = uncertain_wrong = 0
    mistakes, times = [], []

    for f in files:
        true_index = int(f.name.split("__")[0])
        t0 = time.perf_counter()
        out = model.classify(f.read_bytes())
        times.append(time.perf_counter() - t0)
        predicted = [p.label for p in out.predictions]
        correct = predicted[0] == labels[true_index].label
        top1 += correct
        top3 += labels[true_index].label in predicted
        if out.uncertain:
            uncertain_right += correct
            uncertain_wrong += not correct
        if not correct:
            mistakes.append(f"  {f.name}: predicted {predicted[0]} ({out.predictions[0].confidence:.0%})")

    n = len(files)
    print(f"Images: {n}   top-1: {top1}/{n} = {top1 / n:.1%}   top-3: {top3}/{n} = {top3 / n:.1%}")
    print(f"Marked uncertain (< {clf.UNCERTAIN_THRESHOLD:.0%}): {uncertain_right} correct, {uncertain_wrong} wrong")
    print(f"Average inference time: {sum(times) / n * 1000:.0f} ms per image (CPU)")
    if mistakes:
        print("Mistakes:")
        print("\n".join(mistakes))
    return 0


if __name__ == "__main__":
    sys.exit(main())
