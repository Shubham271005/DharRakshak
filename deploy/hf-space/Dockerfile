# DharRakshak backend for Hugging Face Spaces (Docker SDK).
# Built by scripts/deploy_hf_space.py, which copies backend/, shared/ and
# requirements.txt next to this file.
FROM python:3.12-slim

# Spaces run the container as user 1000.
RUN useradd -m -u 1000 user
WORKDIR /app

# CPU-only PyTorch first (much smaller than the default CUDA build).
RUN pip install --no-cache-dir torch torchvision --index-url https://download.pytorch.org/whl/cpu
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# The team's image model: Daksh159/plant-disease-mobilenetv2, pinned + checksum-verified.
RUN mkdir -p models/plant-disease-mobilenetv2 && python - <<'PY'
import hashlib, urllib.request
url = "https://huggingface.co/Daksh159/plant-disease-mobilenetv2/resolve/d3fb2afc90da83086eff06e9088a889b6c43d4a6/mobilenetv2_plant.pth"
path = "models/plant-disease-mobilenetv2/mobilenetv2_plant.pth"
urllib.request.urlretrieve(url, path)
digest = hashlib.sha256(open(path, "rb").read()).hexdigest()
assert digest == "26c97b05ef2caf58bce6f901c725926546a887ee50f0a637a363b644ec17f96e", digest
print("model weights verified")
PY

COPY backend backend
COPY shared shared
RUN chown -R user /app
USER user

# SQLite lives in /tmp: it resets when the Space restarts (demo farmer is re-seeded).
ENV DHARRAKSHAK_DB=/tmp/dharrakshak.sqlite3 \
    DHARRAKSHAK_MODEL=daksh-mobilenetv2 \
    PYTHONUNBUFFERED=1
EXPOSE 7860
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "7860"]
