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

Baseline after the audit + test phases: **893 passed, 1 skipped**.
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

## Known pre-existing bug (not yet fixed)

`scripts/download_model.py` and `scripts/run_demo.sh` still assume the legacy
`.pth` weights, but `backend/ml/classifier.py` sets `DEFAULT_MODEL = "daksh-mobilenetv2"`,
a `legacy` entry with **no `repo` key**. So `download_model.py` without `--all`
raises `ModelNotAvailable`/`KeyError`, and `run_demo.sh` looks for a
`mobilenetv2_plant.pth` that no longer exists. The committed `.onnx` is what the
app actually loads, so a fresh clone runs without downloading anything.
