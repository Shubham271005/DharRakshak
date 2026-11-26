# Notes for future sessions

## Running the backend tests

The system Python has **no pytest and no venv** by default. Create one and install
only this subset — the full `requirements.txt` (torch/torchvision) is not needed:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install pytest fastapi "uvicorn[standard]" python-multipart \
  httpx python-dotenv pillow numpy opencv-python-headless pydantic
.venv/bin/python -m pytest -q
```

Baseline at commit `9339fde` + the robustness work: **431 passed, 1 skipped**.
`tests/test_classifier.py` skips because torch is absent — that is expected, not a failure.

Frontend has no test suite. Verify JSX changes with:

```bash
cd frontend && npm install && npm run build
```

## Known pre-existing bug (not yet fixed)

`scripts/download_model.py` and `scripts/run_demo.sh` still assume the legacy
`.pth` weights, but `backend/ml/classifier.py` sets `DEFAULT_MODEL = "daksh-mobilenetv2"`,
a `legacy` entry with **no `repo` key**. So `download_model.py` without `--all`
raises `ModelNotAvailable`/`KeyError`, and `run_demo.sh` looks for a
`mobilenetv2_plant.pth` that no longer exists. The committed `.onnx` is what the
app actually loads, so a fresh clone runs without downloading anything.
