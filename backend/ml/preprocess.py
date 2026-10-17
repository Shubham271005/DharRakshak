"""
Leaf-photo preprocessing with OpenCV (accuracy upgrade).

The image models were trained on PlantVillage: ONE leaf, centred, on a plain
background, evenly lit. Farmers' photos are the opposite (clutter, shadows,
several leaves, odd framing, sideways phone photos). These steps move a real
photo closer to what the model expects — but each one is switchable and was
MEASURED (scripts/eval_pipeline.py); only steps that improved real-field
accuracy are enabled by default (see DEFAULT_STEPS and docs/MODEL_CARD.md).

Steps (in order):
  exif        rotate phone photos the right way up (EXIF orientation)
  quality     blur (Laplacian variance), darkness, flatness, tiny-size checks
  leaf_crop   find the leaf with colour segmentation and crop to it
              (green + yellow/brown so diseased areas are KEPT); falls back
              to the full image if no plausible leaf is found
  background  grey out pixels far from the leaf (reduces clutter)
  white_bal   grey-world white balance (removes colour casts)
  clahe       local contrast on the lightness channel only (keeps lesion colour)
  denoise     light edge-preserving smoothing (bilateral filter)
"""

from __future__ import annotations

from dataclasses import dataclass, field

import cv2
import numpy as np
from PIL import Image, ImageOps

ALL_STEPS = ("exif", "quality", "leaf_crop", "background", "white_bal", "clahe", "denoise")
# Chosen from measured results — update together with docs/MODEL_CARD.md.
DEFAULT_STEPS = ("exif", "quality", "leaf_crop")

# Quality thresholds (on a 512 px-wide grey copy of the photo).
BLUR_MIN_VARIANCE = 40.0   # Laplacian variance below this = very blurry
DARK_MEAN_MAX = 25.0       # mean grey level below this = far too dark
FLAT_STD_MIN = 12.0        # grey-level spread below this = blank / flat photo
MIN_SIDE_PX = 64

# Leaf segmentation (OpenCV HSV: H 0–179, S/V 0–255).
GREEN_HUE = (25, 95)       # healthy leaf tissue
LESION_HUE = (5, 30)       # yellow / brown lesions and chlorosis
MIN_SAT, MIN_VAL = 40, 35
MIN_LEAF_FRACTION = 0.04   # leaf must cover at least 4% of the photo…
MAX_LEAF_FRACTION = 0.97   # …and not literally everything (then crop is pointless)
CROP_MARGIN = 0.08         # keep 8% context around the leaf


@dataclass
class PreprocessResult:
    image: Image.Image                     # RGB image to feed the model
    poor_quality: bool = False
    quality_issues: list[str] = field(default_factory=list)  # e.g. ["blurry"]
    blur_score: float = 0.0
    leaf_found: bool = False
    leaf_fraction: float = 0.0             # share of the photo that looks like leaf
    crop_box: tuple[int, int, int, int] | None = None


def _quality(rgb: np.ndarray) -> tuple[list[str], float]:
    h, w = rgb.shape[:2]
    issues = []
    if min(h, w) < MIN_SIDE_PX:
        issues.append("too_small")
    scale = 512 / max(w, 1)
    small = cv2.resize(rgb, (512, max(1, int(h * scale)))) if w > 512 else rgb
    grey = cv2.cvtColor(small, cv2.COLOR_RGB2GRAY)
    blur = float(cv2.Laplacian(grey, cv2.CV_64F).var())
    if blur < BLUR_MIN_VARIANCE:
        issues.append("blurry")
    if grey.mean() < DARK_MEAN_MAX:
        issues.append("too_dark")
    if grey.std() < FLAT_STD_MIN:
        issues.append("blank")
    return issues, blur


def leaf_mask(rgb: np.ndarray) -> np.ndarray:
    """Binary mask of leaf-like pixels: green tissue PLUS yellow/brown lesions,
    so infected regions are never cut away."""
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    h, s, v = cv2.split(hsv)
    sat_ok = (s >= MIN_SAT) & (v >= MIN_VAL)
    green = sat_ok & (h >= GREEN_HUE[0]) & (h <= GREEN_HUE[1])
    lesion = sat_ok & (h >= LESION_HUE[0]) & (h < LESION_HUE[0] + 25) & (s >= 60)
    mask = (green | lesion).astype(np.uint8) * 255
    k = max(3, (min(rgb.shape[:2]) // 100) | 1)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k))
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)                # drop specks
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=3)  # fill lesion holes
    return mask


def _largest_component(mask: np.ndarray) -> np.ndarray | None:
    count, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    if count <= 1:
        return None
    biggest = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    comp = (labels == biggest).astype(np.uint8) * 255
    # Fill interior holes (dark lesions inside the leaf outline).
    contours, _ = cv2.findContours(comp, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    filled = np.zeros_like(comp)
    cv2.drawContours(filled, contours, -1, 255, thickness=cv2.FILLED)
    return filled


def _gray_world(rgb: np.ndarray) -> np.ndarray:
    means = rgb.reshape(-1, 3).mean(axis=0) + 1e-6
    gain = means.mean() / means
    return np.clip(rgb * gain, 0, 255).astype(np.uint8)


def _clahe(rgb: np.ndarray) -> np.ndarray:
    lab = cv2.cvtColor(rgb, cv2.COLOR_RGB2LAB)
    l, a, b = cv2.split(lab)
    l = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(l)  # lightness only: colours unchanged
    return cv2.cvtColor(cv2.merge((l, a, b)), cv2.COLOR_LAB2RGB)


def preprocess(image: Image.Image, steps: tuple[str, ...] = DEFAULT_STEPS) -> PreprocessResult:
    """Run the enabled steps. Never fails: any step that can't help is skipped
    and the (partly processed) image is returned."""
    unknown = set(steps) - set(ALL_STEPS)
    if unknown:
        raise ValueError(f"unknown preprocessing steps: {unknown}")

    if "exif" in steps:
        image = ImageOps.exif_transpose(image)
    rgb = np.asarray(image.convert("RGB"))
    result = PreprocessResult(image=image.convert("RGB"))

    if "quality" in steps:
        result.quality_issues, result.blur_score = _quality(rgb)
        result.poor_quality = bool(result.quality_issues)

    if "leaf_crop" in steps or "background" in steps:
        mask = leaf_mask(rgb)
        component = _largest_component(mask)
        if component is not None:
            fraction = float((component > 0).mean())
            result.leaf_fraction = fraction
            if MIN_LEAF_FRACTION <= fraction <= MAX_LEAF_FRACTION:
                result.leaf_found = True
                if "background" in steps:
                    # Grey out everything well outside the leaf (soft edge).
                    near = cv2.dilate(component, np.ones((15, 15), np.uint8))
                    soft = cv2.GaussianBlur(near, (31, 31), 0).astype(np.float32)[..., None] / 255.0
                    rgb = (rgb * soft + 128 * (1 - soft)).astype(np.uint8)
                if "leaf_crop" in steps:
                    x, y, w, h = cv2.boundingRect(component)
                    mx, my = int(w * CROP_MARGIN), int(h * CROP_MARGIN)
                    x0, y0 = max(0, x - mx), max(0, y - my)
                    x1, y1 = min(rgb.shape[1], x + w + mx), min(rgb.shape[0], y + h + my)
                    # Make the crop square-ish so the 224×224 resize doesn't squash the leaf.
                    side = max(x1 - x0, y1 - y0)
                    cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
                    x0 = max(0, min(cx - side // 2, rgb.shape[1] - side))
                    y0 = max(0, min(cy - side // 2, rgb.shape[0] - side))
                    x1, y1 = min(rgb.shape[1], x0 + side), min(rgb.shape[0], y0 + side)
                    rgb = rgb[y0:y1, x0:x1]
                    result.crop_box = (x0, y0, x1, y1)

    if "white_bal" in steps:
        rgb = _gray_world(rgb)
    if "clahe" in steps:
        rgb = _clahe(rgb)
    if "denoise" in steps:
        rgb = cv2.bilateralFilter(rgb, d=5, sigmaColor=40, sigmaSpace=40)

    result.image = Image.fromarray(np.ascontiguousarray(rgb))
    return result
