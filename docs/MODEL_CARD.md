# Model Card: plant-disease image classifier (F1)

The team chose this model. This page records where it came from, how we use it, and what it can't do, so we can answer judges honestly.

## Source

| | |
|---|---|
| Model | [`Daksh159/plant-disease-mobilenetv2`](https://huggingface.co/Daksh159/plant-disease-mobilenetv2) on Hugging Face |
| Author | Daksh Goyal |
| License | **Apache-2.0**: free to use, modify and redistribute with attribution |
| Pinned revision | `d3fb2afc90da83086eff06e9088a889b6c43d4a6` |
| Weights file | `mobilenetv2_plant.pth` (about 9 MB), state dict only (no pickled code) |
| SHA-256 | `26c97b05ef2caf58bce6f901c725926546a887ee50f0a637a363b644ec17f96e` (checked on load) |
| Architecture | MobileNetV2 (ImageNet-pretrained backbone, frozen) with a new head: `Dropout(0.2) → Linear(1280 → 38)` |
| Training data | "New Plant Diseases Dataset (Augmented)", built from PlantVillage, about 87k images |
| Reported accuracy | 95% validation accuracy, **reported by the author** on a validation split of the same dataset. We have not reproduced it. |

## Classes (38)

The model covers 14 crops: apple, blueberry, cherry, maize (corn), grape, orange, peach, bell pepper, potato, raspberry, soybean, squash, strawberry, tomato.

There are 10 tomato classes: bacterial spot, early blight, late blight, leaf mold, Septoria leaf spot, spider mites, target spot, yellow leaf curl virus, mosaic virus, healthy.

The full ordered list, with crop keys and English/Hindi names, is in `shared/content/labels.json`.

**Where the class order came from:** the model card mentions a `class_names.json`, but the Hugging Face repo doesn't contain it. We took the order from the `labels.json` in the community Space [`Vansh180/daksh159-plant-disease-api`](https://huggingface.co/spaces/Vansh180/daksh159-plant-disease-api). It matches the standard alphabetical PlantVillage folder order that PyTorch `ImageFolder` produces, which is how the model was trained.

## How we run it (`backend/ml/classifier.py`)

1. **Decode:** Pillow opens the image and converts it to RGB. Greyscale, transparent PNG and palette images are handled. Unreadable files return HTTP 400.
2. **Preprocess:** resize to 224×224, convert to a tensor, and normalise with the ImageNet mean `[0.485, 0.456, 0.406]` and std `[0.229, 0.224, 0.225]`. These are the settings from the author's model card.
3. **Infer:** CPU only, in a worker thread so the API stays responsive. The model loads once at server startup.
4. **Rank:** softmax over all 38 classes, keep the top 3.
5. **Word it carefully:** diseases are shown as "Possible …" ("संभावित …") and healthy classes as "Likely healthy …" ("संभवतः स्वस्थ …").
6. **Photo-quality check:** before the model's answer is trusted, the photo is checked. It is marked *uncertain* with a "please retake" message if it is blank or flat (grey-level spread below 12), very dark (mean below 25), or tiny (shorter side below 64 px).
7. **Uncertainty:** if the top confidence is **below 0.50**, the result is marked *uncertain* and the farmer is asked to retake the photo and check with an expert.
8. **Crop mismatch:** if the model is confident but the predicted crop differs from the farmer's registered crop, the result is flagged.

**Safety:**
- Weights load with `torch.load(weights_only=True)`, so no arbitrary code runs from the file.
- The SHA-256 is verified.
- The head is built exactly as in training and loaded with `strict=True`, so a mismatch fails loudly.

The community Space mentioned above uses a plain `Linear` head with `strict=False`. That can silently leave the final layer untrained, and we deliberately don't copy it.

## Known limitations (say these to judges)

- **Lab images, not field photos.** PlantVillage photos show one leaf on a plain background. Accuracy usually drops on real field photos with clutter, shadows, several leaves or other symptoms. **We have not measured field accuracy.**
- **Confidently wrong on non-leaf photos.** In our test, a plain green rectangle scored **92% "Septoria leaf spot"**. Like most classifiers trained on one kind of image, the model has no notion of "this isn't a leaf", so confidence alone can't detect it. The photo-quality check catches blank, dark and tiny photos, but **not** every non-leaf photo (a face or a wall can still get a disease label). A proper fix is a separate "is this a leaf?" model. It's planned, not built.
- **Only 38 classes.** A disease outside this list, or a nutrient deficiency, gets forced into the nearest class. The uncertainty threshold and ranked possibilities soften this but don't remove it.
- **Healthy-vs-disease only per leaf.** It doesn't measure severity or count lesions.
- **95% is the author's number on similar images.** It is not a claim about real-world performance.
- **The threshold (0.50) is a starting guess.** Tune it with `scripts/try_model.py` on real photos.

## Planned evaluation (post-hackathon)

- Top-1 and top-3 accuracy on a field-image set, such as PlantDoc, for the overlapping classes.
- Calibration check: are 0.8-confidence predictions right about 80% of the time?
- Grad-CAM heatmaps to show which part of the leaf drove the prediction (stretch goal).

## Commands

```bash
python scripts/download_model.py                     # download + verify weights (once per laptop)
python scripts/try_model.py data/samples/*.jpg       # try it on photos
pytest tests/test_classifier.py                      # real-model tests
```
