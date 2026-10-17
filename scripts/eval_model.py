"""
Measure the image model EXACTLY as the app runs it (preprocessing, flip
averaging, crop-aware ranking, uncertainty rules).

Run from the repository root:
    python scripts/eval_model.py                              # lab + field photos, selected model
    python scripts/eval_model.py --dir data/eval_field
    DHARRAKSHAK_MODEL=daksh-mobilenetv2 python scripts/eval_model.py   # the original model

Each file name starts with its true class index, and the farmer's
registered crop is taken to be the photo's true crop (as in real use).
Prints top-1, top-3, macro-F1, how many results were flagged uncertain
(and how accurate flagged vs. unflagged results were), every mistake, and
the average time per photo.
"""

import argparse
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from backend import config  # noqa: E402,F401
from backend.ml import classifier as clf  # noqa: E402
from eval_pipeline import macro_f1  # noqa: E402


def evaluate(model, folder: Path, show_mistakes: bool) -> None:
    files = sorted(folder.glob("*.jpg"))
    if not files:
        print(f"{folder}: no photos (see the fetch_*_images.py scripts)")
        return
    labels = model.labels
    truth, preds, top3, flagged, flagged_right, times, mistakes = [], [], 0, 0, 0, [], []
    by_reason: dict[str, list[int]] = {}  # reason -> [count, correct]
    for f in files:
        true_idx = int(f.name.split("__")[0])
        true = labels[true_idx]
        t0 = time.perf_counter()
        out = model.classify(f.read_bytes(), registered_crop=true.crop)
        times.append(time.perf_counter() - t0)
        predicted = [p.label for p in out.predictions]
        idx = next(i for i, l in enumerate(labels) if l.label == predicted[0])
        truth.append(true_idx)
        preds.append(idx)
        top3 += true.label in predicted
        right = predicted[0] == true.label
        if out.uncertain:
            flagged += 1
            flagged_right += right
        if out.quality_issues:
            reason = "poor photo"
        elif out.crop_mismatch:
            reason = "may not be registered crop"
        elif out.uncertain and "only one condition" in out.uncertainty_message.en:
            reason = "single-class crop (limited)"
        elif out.uncertain:
            reason = "close top-2 (low confidence)"
        else:
            reason = "not flagged"
        stats = by_reason.setdefault(reason, [0, 0])
        stats[0] += 1
        stats[1] += right
        if not right:
            mistakes.append(f"    {f.name}: predicted {predicted[0]} ({out.predictions[0].confidence:.0%})"
                            f"{'  [flagged uncertain]' if out.uncertain else ''}")
    n = len(files)
    correct = sum(t == p for t, p in zip(truth, preds))
    unflagged = n - flagged
    print(f"\n{folder.relative_to(REPO_ROOT)}: {n} photos, {len(set(truth))} classes  [model: {model.model_name}]")
    print(f"  top-1 {correct / n:.1%}   top-3 {top3 / n:.1%}   macro-F1 {macro_f1(truth, preds):.2f}")
    print(f"  flagged uncertain: {flagged} ({flagged / n:.0%}) — accuracy when flagged "
          f"{(flagged_right / flagged) if flagged else 0:.0%}, when not flagged "
          f"{((correct - flagged_right) / unflagged) if unflagged else 0:.0%}")
    for reason, (count, ok) in sorted(by_reason.items(), key=lambda x: -x[1][0]):
        print(f"    {reason:30} {count:3} photos, accuracy {ok / count:.0%}")
    print(f"  average time: {1000 * sum(times) / n:.0f} ms per photo (CPU, incl. preprocessing + flip)")
    if show_mistakes and mistakes:
        print("  mistakes:")
        print("\n".join(mistakes))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dir", action="append", help="folder(s) of labelled photos")
    parser.add_argument("--mistakes", action="store_true", help="list every wrong prediction")
    args = parser.parse_args()
    folders = [REPO_ROOT / d for d in args.dir] if args.dir else [REPO_ROOT / "data" / "eval", REPO_ROOT / "data" / "eval_field"]
    model = clf.PlantDiseaseClassifier()
    for folder in folders:
        evaluate(model, folder, args.mistakes)
    return 0


if __name__ == "__main__":
    sys.exit(main())
