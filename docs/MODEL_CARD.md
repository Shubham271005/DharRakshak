# Model card: plant-disease image classifier (F1)

## Summary

The first model scored 95% on lab photos but only **12%** on real field photos. After evaluating 4
models and 8 preprocessing settings on real photos, accuracy improved — but far less than the
headline figures suggest.

**Read this before quoting a number.** The app ranks **all 38 conditions** for every photo
(`classifier.classify()`). On the 89-photo PlantDoc field set, that gives **12% top-1 / 26% top-3**
for the default model and **26% / 42%** for the best Hugging Face candidate. A *higher* set of
figures — **60% top-1 / 85% top-3** — appears further down; those were scored with **only the
registered crop's classes**, which discards every wrong-crop answer. They describe a ranking method
the app deliberately does **not** use. Do not present them as the app's field accuracy.

All numbers below were measured with `scripts/eval_pipeline.py` and `scripts/eval_model.py`, and the
raw grid is committed as `data/eval_results.json`. None come from model cards.

## Current setup (the default)

| | |
|---|---|
| Model | `daksh-mobilenetv2` — the original Component 4 model ([`Daksh159/plant-disease-mobilenetv2`](https://huggingface.co/Daksh159/plant-disease-mobilenetv2)), shipped as a committed **ONNX** export |
| Architecture | torchvision MobileNetV2 (9 MB) fine-tuned on PlantVillage; 38-way classifier head |
| Runtime | **ONNX Runtime** (`DHARRAKSHAK_RUNTIME=onnx`, the default) — no PyTorch, ~15 MB, fits a 512 MB free server. `DHARRAKSHAK_RUNTIME=torch` uses the `.pth` weights instead |
| Classes | 38 (14 crops / 19 fungal, 12 healthy, 3 bacterial, 2 insect-spread, 1 pest, 1 viral) |
| **License** | **Apache-2.0** |
| Preprocessing | EXIF rotation + quality checks (blur, dark, blank, tiny) + leaf crop (falls back to the full frame when no plausible leaf is found) — `backend/ml/preprocess.py → DEFAULT_STEPS` |
| Inference | The photo and its mirror image are both run and averaged (flip test-time augmentation). CPU; ~17 ms per photo for the default model, plus preprocessing |
| Ranking | **All 38 classes**, real (never re-normalised) probabilities, top 3 shown. The registered crop is used **only** to raise a "may not be your crop" warning |
| Uncertainty | Flagged *uncertain* if the photo is poor (blurry, dark, blank, tiny) **or** the top-1 probability is below **0.50** (`UNCERTAIN_THRESHOLD`). That is the complete set of rules |

The Hugging Face candidates below are selected with `DHARRAKSHAK_MODEL=…` in `.env`, then
`python scripts/download_model.py`. They need `torch` + `transformers` and a one-time download; the
default model needs neither.

**Why the default is the less accurate model:** it is the only one whose weights are committed to
this repository, so a fresh clone runs with no download and the free Render plan needs no PyTorch.
Switching `DEFAULT_MODEL` to a Hugging Face candidate would break both of those. If you want the
better model in a real deployment, set `DHARRAKSHAK_MODEL` and add `torch` to the deployed
`requirements` — it is a deployment decision, not a one-line change.

## Evaluation data

| Set | Photos | What it is | Source |
|---|---|---|---|
| Lab | 38 (19 classes) | PlantVillage test split: one leaf, plain background | `BrandonFors/Plant-Diseases-PlantVillage-Dataset` (`scripts/fetch_eval_images.py`) |
| **Field** | **89 (23 classes)** | **PlantDoc: real photos with clutter, shadows, several leaves** | `Project-AgML/plant_doc_classification` (`scripts/fetch_field_images.py`) |

None of the candidate models was trained on PlantDoc, so the field set is a fair test. **It is small
(89 photos), so differences of a few points are within noise.**

Neither image set is committed (they are git-ignored), so the committed `data/eval_results.json` is
the only reproducible record of these measurements. Re-running requires the fetch scripts.

## Results: models on field photos

Ranking basis matters, so both are shown. `exif` + leaf-crop preprocessing; the stored grid does not
include flip averaging.

| Model | Size | License | Lab top-1 | Field top-1 (all 38 — **what the app does**) | Field top-3 (all 38) | Field top-1 (crop-restricted) | Field top-3 (crop-restricted) |
|---|---|---|---|---|---|---|---|
| Original: `daksh-mobilenetv2` — **default** | 9 MB | Apache-2.0 | 95% | **12%** | **26%** | 45% | 81% |
| `linkanjarad-mobilenetv2` | 9 MB | not stated | 92% | **26%** | **42%** | 58% | 85% |
| `dinov2-small` | 88 MB | CC-BY-SA-4.0 | 97% | **32%** | **57%** | 51% | 84% |
| `convnext-tiny` | 111 MB | Apache-2.0 | 84% | **16%** | **29%** | 49% | 80% |

- **Crop-restricted ranking is not used.** It looks much better (45% vs 12%) because a photo of the
  wrong crop is scored as a miss only if the restricted list happens to contain the truth — in
  practice the wrong-crop answers that a farmer would notice simply stop being counted. The app
  shows the model's real answer instead, and warns that it may be a different crop.
- **Combining models** (2, 3 or 4 averaged) did not beat the best single model.
- **Flip averaging** is on. It was worth about +2 points in the experiment script.

## Results: preprocessing (best model, field photos, crop-restricted scoring)

| Setting | Field top-1 | Verdict |
|---|---|---|
| None / EXIF fix | 60% | ✅ EXIF fix kept (needed for phone photos, harmless here) |
| + leaf crop (OpenCV segmentation, keeps yellow and brown lesions) | 58% | ⚠️ **on, despite being neutral** — see note |
| + leaf crop + background removal | 56% | ❌ off |
| + CLAHE (lightness-only contrast) | 52% | ❌ off (hurts; also hurt lab accuracy, 95% to 79%) |
| + grey-world white balance | 57% | ❌ off |
| + denoise (bilateral) | 61% | ➖ off (+1 point is within noise) |

**Note on leaf crop:** `DEFAULT_STEPS` in `backend/ml/preprocess.py` **enables** `leaf_crop`, so the
"58%" column is what ships. The measurement above shows no gain for the default model (12% either
way) and a small loss for `linkanjarad`. It was left on and the comment in `classifier.py` that
described it as off has been corrected. Whether to switch it off is an open question — see
"What would improve it most".

## Uncertainty flags on field photos

The only rules are "poor photo" and "top-1 below 0.50". The earlier *close top-2 gap* and
*single-class crop* rules were removed from `classifier.py`, so their rows are gone from this table
(they described behaviour that no longer exists).

The 0.50 threshold was calibrated on the same 89 photos it is reported on, so expect slightly weaker
separation on new photos.

## Known limitations (say these to judges)

- **The default model gets roughly 1 in 8 field photos right at top-1** (26% within the top 3). The
  best Hugging Face candidate reaches 32% / 57%. That is why the app shows three possibilities, calls
  them "possible", and always asks the farmer to verify.
- **Telling crops apart is weak on field photos.** The registered crop is used only for a warning,
  not for filtering, so a wrong-crop answer is visible rather than hidden.
- **Only 38 PlantVillage classes.** Nutrient deficiencies, pests other than spider mites, and crops
  like rice, wheat, cotton or sugarcane are not covered.
- **Non-leaf photos** (faces, walls) can still get a disease label if they pass the quality checks.
- **The default model is Apache-2.0.** The highest-accuracy candidate (`linkanjarad`) does **not**
  state a license, so it is not suitable for anything beyond a hackathon demo.

## What would improve it most (post-hackathon)

1. **Fine-tune on field photos** (PlantDoc plus photos from local farms). This is the single biggest
   lever, since all public models here were trained only on lab photos.
2. **Ship the better model.** Set `DHARRAKSHAK_MODEL=dinov2-small` (CC-BY-SA-4.0, 32%/57%) and add
   `torch` to the deployment — roughly triples top-1 versus the default.
3. Add crops and conditions that matter in India: rice, wheat, cotton, sugarcane, and nutrient
   deficiencies.
4. Add a small "is this a leaf?" check before the disease model.

## Commands

```bash
python scripts/download_model.py            # the model named by DHARRAKSHAK_MODEL (--all for every candidate)
                                           # the DEFAULT model is not downloadable: its ONNX is committed
python scripts/fetch_eval_images.py         # lab photos
python scripts/fetch_field_images.py        # field photos (PlantDoc)
python scripts/eval_model.py                # the app's pipeline: top-1/top-3/F1/flags/speed
python scripts/eval_pipeline.py             # model × preprocessing grid
```
