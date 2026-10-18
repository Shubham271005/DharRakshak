"""
Deploy the DharRakshak backend to a Hugging Face Space (Docker).

One-time setup: log in to Hugging Face in your terminal (token with "write" access,
from https://huggingface.co/settings/tokens):
    .venv/bin/hf auth login            # or: huggingface-cli login

Then, from the repository root:
    python scripts/deploy_hf_space.py                    # creates/updates <you>/dharrakshak-api
    python scripts/deploy_hf_space.py --space my-name
    python scripts/deploy_hf_space.py --dry-run          # only assemble build/hf-space (for a local docker build)

What it uploads: deploy/hf-space/{Dockerfile,README.md}, backend/, shared/,
requirements.txt. Never .env, data/, models/ or test photos. GROQ_API_KEY
(from your environment or .env) is stored as a private Space *secret*, not a file.
"""

import argparse
import os
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BUILD = REPO_ROOT / "build" / "hf-space"
sys.path.insert(0, str(REPO_ROOT))


def assemble() -> Path:
    if BUILD.exists():
        shutil.rmtree(BUILD)
    BUILD.mkdir(parents=True)
    for f in ("Dockerfile", "README.md"):
        shutil.copy(REPO_ROOT / "deploy" / "hf-space" / f, BUILD / f)
    ignore = shutil.ignore_patterns("__pycache__", "*.pyc")
    shutil.copytree(REPO_ROOT / "backend", BUILD / "backend", ignore=ignore)
    shutil.copytree(REPO_ROOT / "shared", BUILD / "shared", ignore=ignore)
    # pytest is only for development.
    reqs = [l for l in (REPO_ROOT / "requirements.txt").read_text().splitlines() if not l.startswith("pytest")]
    (BUILD / "requirements.txt").write_text("\n".join(reqs) + "\n")
    return BUILD


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--space", default="dharrakshak-api")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    folder = assemble()
    print(f"Assembled {folder}")
    if args.dry_run:
        return 0

    from huggingface_hub import HfApi

    from backend import config  # loads .env so GROQ_API_KEY is available

    api = HfApi()
    try:
        user = api.whoami()["name"]
    except Exception:  # noqa: BLE001 - any auth failure means "not logged in"
        print("Not logged in to Hugging Face. Run:  .venv/bin/hf auth login   (token with write access)")
        return 1
    repo_id = f"{user}/{args.space}"
    api.create_repo(repo_id, repo_type="space", space_sdk="docker", exist_ok=True)
    key = config.groq_api_key()
    if key:
        api.add_space_secret(repo_id, "GROQ_API_KEY", key)
        print("GROQ_API_KEY stored as a Space secret")
    else:
        print("No GROQ_API_KEY found — the chatbot will use saved answers until you add it in the Space settings.")
    api.upload_folder(folder_path=str(folder), repo_id=repo_id, repo_type="space",
                      commit_message="Deploy DharRakshak backend")
    host = f"{user}-{args.space}".lower().replace("_", "-").replace(".", "-")
    print(f"\nSpace:  https://huggingface.co/spaces/{repo_id}  (build takes a few minutes)")
    print(f"API:    https://{host}.hf.space   → set this as VITE_API_BASE for the frontend")
    return 0


if __name__ == "__main__":
    sys.exit(main())
