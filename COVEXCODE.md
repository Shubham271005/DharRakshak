# Notes for future sessions

## Running the backend tests

The system Python has **no pytest and no venv** by default. Create one and install
only this subset — the full `requirements.txt` (torch/torchvision) is not needed:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install pytest pytest-cov fastapi "uvicorn[standard]" python-multipart \
  httpx python-dotenv pillow numpy opencv-python-headless pydantic
.venv/bin/python -m pytest -q
```

Baseline after the audit + test phases: **904 passed, 1 skipped**.
`tests/test_classifier.py` skips because torch is absent — that is expected, not a failure.

Frontend has no test suite. Verify JSX changes with:

```bash
cd frontend && npm install && npm run build
```

## Testing the services that conftest fakes

`tests/conftest.py` replaces these for **every** test (autouse), so no test touches the network or
needs an API key:

| Patched | By fixture |
|---|---|
| `backend.services.llm.chat_complete`, `llm.transcribe` | `fake_llm` |
| `backend.services.weather.fetch_daily` | `fake_open_meteo` |
| `backend.services.geocoding.search` | `fake_open_meteo` |
| `backend.ml.classifier.get_classifier` | `fake_model` (via `client`) |
| `backend.services.ratelimit` counters | `reset_rate_limits` |

A test that wants to exercise the **real** function must capture a reference at import, before any
fixture runs — patching `llm.chat_complete` does not change a module-level alias taken earlier:

```python
from backend.services import llm
real_chat_complete = llm.chat_complete       # captured before the fake_llm fixture runs
```

`tests/test_llm_client.py` and `tests/test_services_network.py` both do this. Calling
`llm.chat_complete(...)` inside such a test silently gets the fake and asserts nothing.

## Coverage

`pytest --cov=backend --cov=shared --cov-report=term-missing`. Baseline after Phase 2:
**93%**. The uncovered remainder is `backend/ml/models.py` (torch/onnxruntime session code), which
cannot run without those packages. `.coveragerc` excludes the runtime `import torch` lines.

## Scripts: `download_model.py` and `run_demo.sh` (fixed)

These two used to be the one known broken path. `DEFAULT_MODEL` is `daksh-mobilenetv2`, a `legacy`
entry with **no `repo` key**, so `download_model.py` without `--all` raised `KeyError: 'repo'`, and
`run_demo.sh` looked for a `mobilenetv2_plant.pth` that no longer exists (the committed weights are
`mobilenetv2_plant.onnx`). Because `run_demo.sh` runs under `set -euo pipefail`, that aborted the
one-command demo on a clean clone.

Both are fixed: the script reports that the legacy model needs no download, names the committed
`.onnx`, and exits 0; the shell script accepts either extension and only downloads when neither
file is present. `tests/test_scripts_and_guards.py` guards this — **do not** reintroduce an
unconditional `spec["repo"]` lookup in `download_model.py`, because `--all` skips legacy entries but
the no-argument path does not.
