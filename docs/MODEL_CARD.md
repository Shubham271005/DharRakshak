# Model card: plant-disease image classifier (F1)

## Summary

The first model scored 95% on lab photos but only **12%** on real field photos. After evaluating 4 models and 8 preprocessing settings on real photos, the app now uses a different model plus a crop-aware pipeline. That reaches **60% top-1 and 85% top-3** on the same field photos.

All numbers below were measured with `scripts/eval_pipeline.py` and `scripts/eval_model.py`. None come from model cards.

## Current setup (default)

| | |
|---|---|
| Model | [`linkanjarad/mobilenet_v2_1.0_224-plant-disease-identification`](https://huggingface.co/linkanjarad/mobilenet_v2_1.0_224-plant-disease-identification), pinned to `c1861579` |
| Architecture | MobileNetV2 (9 MB), fine-tuned from `google/mobilenet_v2_1.0_224` on the Kaggle "New Plant Diseases" (PlantVillage) dataset |
| Classes | 38 (14 crops). Mapped onto `shared/content/labels.json` by crop and disease words, with a strict one-to-one check |
| **License** | **Not stated by the author ("other").** Fine for a hackathon demo, but check before any commercial use. Licensed alternatives are one setting away (below). |
| Preprocessing | Fix photo rotation (EXIF) + quality checks (blur, dark, blank, tiny). Then the model's own processor: resize 256, centre-crop 224, normalise 0.5/0.5. |
| Inference | Average of the photo and its mirror image (flip test-time augmentation). CPU, about 50 ms per photo including preprocessing. |
| Ranking | **Crop-aware:** only the farmer's registered crop's classes are ranked, renormalised within that crop. |
| Uncertainty | Flagged *uncertain* if the photo is poor (blurry, dark, blank, tiny), or the top-2 gap within the crop is under 0.30, or the crop has only one class in the model. A "may not be your crop" note appears if the photo puts under 0.1% of its probability on the registered crop. |

To choose another model, set `DHARRAKSHAK_MODEL=…` in `.env`, then run `python scripts/download_model.py`.

## Evaluation data

| Set | Photos | What it is | Source |
|---|---|---|---|
| Lab | 38 (19 classes) | PlantVillage test split: one leaf, plain background | `BrandonFors/Plant-Diseases-PlantVillage-Dataset` (`scripts/fetch_eval_images.py`) |
| **Field** | **89 (23 classes)** | **PlantDoc: real photos with clutter, shadows, several leaves** | `Project-AgML/plant_doc_classification` (`scripts/fetch_field_images.py`) |

None of the candidate models was trained on PlantDoc, so the field set is a fair test. **It is small (89 photos), so differences of a few points are within noise.** The chosen setup was checked on two random halves (52% and 71%), and beats the alternatives on both.

## Results: models (field photos, crop-aware ranking, no extra preprocessing)

| Model | Size | License | Lab top-1 | Field top-1 | Field top-3 | Field F1 | ms/photo |
|---|---|---|---|---|---|---|---|
| Original: Daksh159 MobileNetV2 | 9 MB | Apache-2.0 | 95% | 45% | 81% | 0.45 | 17 |
| **linkanjarad MobileNetV2** | 9 MB | not stated | 95% | **60%** | **85%** | **0.59** | 19 |
| DINOv2-small | 88 MB | CC-BY-SA-4.0 | 97% | 49% | 84% | 0.47 | 41 |
| ConvNeXt-tiny | 111 MB | Apache-2.0 | 92% | 49% | 82% | 0.47 | 32 |

- **Without crop-aware ranking** (all 38 classes, as the app did before), field top-1 was 12% for the original model and 29% for linkanjarad. This was the main reason for wrong-crop answers like "apple black rot" on a tomato.
- **Combining models** (2, 3 or 4 averaged) did **not** beat linkanjarad alone (best combination 57%).
- **Flip averaging** added +2 points (60% to 62% in the experiment script), so it's on.

## Results: preprocessing (best model, field photos)

| Setting | Field top-1 | Verdict |
|---|---|---|
| None / EXIF fix | 60% | ✅ EXIF fix kept (needed for phone photos, harmless here) |
| + leaf crop (OpenCV segmentation, keeps yellow and brown lesions) | 58% | ❌ off (no gain) |
| + leaf crop + background removal | 56% | ❌ off |
| + CLAHE (lightness-only contrast) | 52% | ❌ off (hurts; also hurt lab accuracy, 95% to 79%) |
| + grey-world white balance | 57% | ❌ off |
| + denoise (bilateral) | 61% | ➖ off (+1 point is within noise) |

All of these steps are implemented in `backend/ml/preprocess.py` and can be switched on. They're off because they didn't improve real-world accuracy for this model, which was trained on unprocessed photos.

## Final pipeline, as the app runs it (`scripts/eval_model.py`)

| | Lab (38) | Field (89) |
|---|---|---|
| **Before** (original model, all 38 classes) | 95% top-1 | **12% top-1** |
| Original model + new pipeline | 97% top-1 | 45% top-1, 81% top-3, F1 0.43 |
| **After** (new model + new pipeline) | 95% top-1, 100% top-3, F1 0.96 | **60% top-1, 85% top-3, F1 0.60** |

How the uncertainty flags behave on field photos (calibrated on this set):

| Result | Photos | Accuracy |
|---|---|---|
| Not flagged | 49 | 55% |
| Flagged: close top-2 (gap under 0.3) | 23 | 43% |
| Flagged: may not be the registered crop | 4 | 75% |
| Single-class crop (blueberry, raspberry, soybean, squash, orange) | 13 | 100% (trivial: only one possible answer) |

The thresholds were calibrated on the same 89 photos they're reported on, so expect slightly weaker separation on new photos.

## Known limitations (say these to judges)

- **60% on real photos means 4 in 10 field photos get the wrong top answer.** The right answer is in the top 3 for 85%. That's why the app always shows 3 possibilities, calls them "possible", and asks the farmer to verify.
- **Telling crops apart is weak on field photos.** The "may not be your crop" check catches only about 31% of wrong-crop photos, in exchange for about 4.5% false alarms. The app relies on the crop the farmer registered.
- **Only 38 PlantVillage classes.** Nutrient deficiencies, pests other than spider mites, and crops like rice, wheat, cotton or sugarcane aren't covered.
- **Non-leaf photos** (faces, walls) can still get a disease label if they pass the quality checks.
- **The license of the default model isn't stated.** DINOv2-small (CC-BY-SA) and ConvNeXt-tiny (Apache-2.0) are licensed alternatives at about 49–52% field accuracy.

## What would improve it most (post-hackathon)

1. **Fine-tune on field photos** (PlantDoc plus photos from local farms). This is the single biggest lever, since all public models here were trained only on lab photos.
2. Add crops and conditions that matter in India: rice, wheat, cotton, sugarcane, and nutrient deficiencies.
3. Add a small "is this a leaf?" check before the disease model.

## Commands

```bash
python scripts/download_model.py            # selected model (--all for every candidate)
python scripts/fetch_eval_images.py         # lab photos
python scripts/fetch_field_images.py        # field photos (PlantDoc)
python scripts/eval_model.py                # the app's pipeline: top-1/top-3/F1/flags/speed
python scripts/eval_pipeline.py             # model × preprocessing grid
```
