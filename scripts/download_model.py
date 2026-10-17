"""
Download the image model selected in .env (DHARRAKSHAK_MODEL, default
linkanjarad-mobilenetv2) at its pinned revision.

Run from the repository root:
    python scripts/download_model.py               # the selected model
    python scripts/download_model.py --all         # every model in MODELS (for evaluation)

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
    for name in names:
        spec = clf.MODELS[name]
        print(f"Downloading {name}: {spec['repo']} @ {spec['revision'][:8]} (license: {spec['license']})")
        for attempt in range(1, 6):
            try:
                print(f"  OK -> {clf.download_model(name)}")
                break
            except OSError as err:
                print(f"  attempt {attempt} interrupted ({err}); retrying…")
        else:
            print("  Download failed after 5 attempts. Check your internet and run again.")
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
