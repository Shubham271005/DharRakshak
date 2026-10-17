"""
Reset the database to a clean demo state.

Run from the repository root (stop the backend first):
    python scripts/reset_db.py

Deletes data/dharrakshak.sqlite3 (or $DHARRAKSHAK_DB), recreates the
tables, and seeds the demo farmer, crop, analysis and MOCK loan.
Use it before a rehearsal or the final demo so test entries don't show up.
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from backend import repository  # noqa: E402
from backend.db import db_path, init_db  # noqa: E402


def main() -> int:
    path = db_path()
    if path.exists():
        answer = input(f"Delete {path} and reseed the demo data? [y/N] ").strip().lower()
        if answer != "y":
            print("Cancelled — nothing changed.")
            return 1
        path.unlink()
    init_db()
    repository.seed_demo_if_empty()
    print(f"Done. Fresh demo database at {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
