"""
Download and verify the image-model weights (about 9 MB).

Run from the repository root:
    python scripts/download_model.py

Saves to models/plant-disease-mobilenetv2/mobilenetv2_plant.pth (git-ignored),
resumes if interrupted, and checks the SHA-256 against the pinned value in
backend/ml/classifier.py. Run it once on every laptop BEFORE the demo, while
you still have good internet.
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from backend.ml import classifier as clf  # noqa: E402


def main() -> int:
    print(f"Downloading {clf.HF_REPO} @ {clf.HF_REVISION[:8]} …")
    for attempt in range(1, 6):
        try:
            path = clf.download_weights()
            break
        except clf.ModelNotAvailable:
            raise
        except OSError as err:  # network hiccup — the partial file is kept and resumed
            print(f"  attempt {attempt} interrupted ({err}); resuming…")
    else:
        print("Download failed after 5 attempts. Check your internet and run again.")
        return 1
    print(f"OK — verified weights at {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
