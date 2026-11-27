"""
Regression tests for the maintenance scripts and for the guards that live
INSIDE the upload endpoints.

Both areas were previously untested, which is how two defects survived:

1. `scripts/download_model.py` crashed with a bare `KeyError: 'repo'` when run
   without arguments, because the DEFAULT model (`daksh-mobilenetv2`) is the
   legacy entry and has no `repo` key. That also aborted
   `scripts/run_demo.sh` on a clean clone (it runs the script under
   `set -euo pipefail`).
2. `scripts/run_demo.sh` waited for `mobilenetv2_plant.pth`, but the committed
   weights are `mobilenetv2_plant.onnx`, so the check always fired.

The endpoint size guards are tested here as well: they are a second line of
defence behind the Content-Length middleware, and a bad edit can nest them
somewhere unreachable while the module still imports and the middleware test
still passes.
"""

import importlib.util
import sys
from pathlib import Path

import pytest

from backend.ml import classifier as clf
from tests.conftest import PNG_SIGNATURE

REPO_ROOT = Path(__file__).resolve().parent.parent

DEMO_CROP = "crop-demo-001"


# ---------------------------------------------------------------------------
# Scripts
# ---------------------------------------------------------------------------

def _load_script(name: str):
    """Import a file from scripts/ (which is not a package)."""
    path = REPO_ROOT / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"dharrakshak_script_{name}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_download_script_explains_the_legacy_model_instead_of_crashing(monkeypatch, capsys):
    """`python scripts/download_model.py` must not raise KeyError.

    The default model has no Hugging Face repo, so there is nothing to fetch:
    the script should say so, point at the committed weights, and exit 0.
    """
    script = _load_script("download_model")
    monkeypatch.delenv("DHARRAKSHAK_MODEL", raising=False)
    monkeypatch.setattr(sys, "argv", ["download_model.py"])

    assert clf.selected_model() == "daksh-mobilenetv2", "this test assumes the legacy model is the default"

    assert script.main() == 0  # used to raise KeyError

    printed = capsys.readouterr().out
    assert "daksh-mobilenetv2" in printed
    assert "nothing to download" in printed
    assert "--all" in printed, "the script should point at the way to fetch a real model"


def test_download_script_reports_the_committed_onnx_weights(monkeypatch, capsys):
    """The message names the file that actually ships, so a new contributor
    is not sent looking for a .pth that no longer exists."""
    script = _load_script("download_model")
    monkeypatch.delenv("DHARRAKSHAK_MODEL", raising=False)
    monkeypatch.setattr(sys, "argv", ["download_model.py"])
    script.main()
    assert "mobilenetv2_plant.onnx" in capsys.readouterr().out


@pytest.mark.parametrize("model_name", [n for n, m in clf.MODELS.items() if not m.get("legacy")])
def test_every_downloadable_model_declares_what_the_script_needs(model_name):
    """`download_model.main()` reads spec["repo"], spec["revision"] and
    spec["license"] for every model it tries to fetch. `--all` must not hit a
    KeyError on any of them."""
    spec = clf.MODELS[model_name]
    assert spec.get("repo"), f"{model_name} is not marked legacy but has no repo"
    assert spec.get("revision"), f"{model_name} has no pinned revision"
    assert spec.get("license"), f"{model_name} has no license note"


def test_the_legacy_model_is_the_only_one_without_a_repo():
    """Guards the invariant the script fix relies on: a `legacy` entry is
    exactly an entry that cannot be downloaded."""
    for name, spec in clf.MODELS.items():
        if spec.get("legacy"):
            assert "repo" not in spec
        else:
            assert spec.get("repo")


def test_run_demo_accepts_the_onnx_weights():
    """The one-command demo must not look only for the removed .pth file."""
    text = (REPO_ROOT / "scripts" / "run_demo.sh").read_text(encoding="utf-8")
    check = next(line for line in text.splitlines() if "mobilenetv2_plant" in line and "[ ! -f" in line)
    assert "mobilenetv2_plant.onnx" in check, "run_demo.sh must accept the committed .onnx weights"
    # And the .pth may appear too (older checkouts), but must not be the only option.
    assert "||" in text or "&&" in text


# ---------------------------------------------------------------------------
# The in-endpoint size guards (defence in depth behind the middleware)
# ---------------------------------------------------------------------------

def test_the_photo_size_guard_inside_the_endpoint_still_fires(client):
    """A file just over 8 MB passes the middleware (which allows 64 KB of
    multipart overhead) and must then be refused by the endpoint itself.

    The detail string identifies WHICH guard answered: the middleware says
    "The uploaded file is too large.", the endpoint says "Photo is larger than
    8 MB.". Without this assertion the endpoint guard could be dead code and
    the middleware would keep the test green.
    """
    oversized = PNG_SIGNATURE + b"\x00" * (8 * 1024 * 1024)
    response = client.post(f"/api/crops/{DEMO_CROP}/analyze",
                           files={"image": ("big.png", oversized, "image/png")})
    assert response.status_code == 413
    assert response.json()["detail"] == "Photo is larger than 8 MB."


def test_a_photo_exactly_at_the_limit_is_not_refused_for_size(client):
    """8 MB exactly is allowed; only `>` is rejected. (The fake classifier
    still refuses the bytes as a non-image, which proves the size check
    passed.)"""
    at_limit = PNG_SIGNATURE + b"\x00" * (8 * 1024 * 1024 - len(PNG_SIGNATURE))
    response = client.post(f"/api/crops/{DEMO_CROP}/analyze",
                           files={"image": ("edge.png", at_limit, "image/png")})
    assert response.status_code != 413


def test_the_recording_size_guard_inside_the_endpoint_still_fires(client):
    """Same defence-in-depth check for /api/voice/transcribe (10 MB)."""
    oversized = b"\x00" * (10 * 1024 * 1024 + 1)
    response = client.post("/api/voice/transcribe",
                           files={"audio": ("q.webm", oversized, "audio/webm")},
                           data={"lang": "hi"})
    assert response.status_code == 413
    assert response.json()["detail"] == "Recording is too long."


# ---------------------------------------------------------------------------
# /api/health
# ---------------------------------------------------------------------------

def test_health_reports_a_current_milestone(client):
    """`stage` used to be pinned to "component-9-chat-voice" long after
    Component 10 and Upgrade 1 had shipped."""
    from backend.main import app

    body = client.get("/api/health").json()
    assert body["stage"] == "upgrade-1-field-accuracy"
    assert body["stage"] != "component-9-chat-voice"
    # The value should track the app version rather than rot silently.
    assert app.version
