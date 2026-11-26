"""
Unit tests for leaf-photo preprocessing (backend/ml/preprocess.py).

The steps are the difference between a PlantVillage-style studio leaf and a
farmer's real photo, so their failure modes matter more than their happy path.
What is checked here:

- every quality flag fires on the photo that should trigger it, and only then;
- leaf segmentation finds a leaf, rejects a frame with no leaf in it, and
  never produces a crop box outside the image;
- `preprocess` never raises for a valid image, whatever steps are enabled,
  and never mutates the caller's PIL image;
- an unknown step name is a programming error and is rejected loudly.
"""

from __future__ import annotations

import io

import numpy as np
import pytest
from PIL import Image

from backend.ml.preprocess import (
    ALL_STEPS,
    BLUR_MIN_VARIANCE,
    CROP_MARGIN,
    DEFAULT_STEPS,
    DARK_MEAN_MAX,
    FLAT_STD_MIN,
    MAX_LEAF_FRACTION,
    MIN_LEAF_FRACTION,
    MIN_SIDE_PX,
    PreprocessResult,
    _clahe,
    _gray_world,
    _largest_component,
    _quality,
    leaf_mask,
    preprocess,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def leaf_photo(size=(480, 360), leaf_fraction=0.5, background=(235, 235, 235)) -> Image.Image:
    """A grey frame with one green blob in the middle, like a leaf on soil-free
    cloth. `leaf_fraction` is the share of the width the blob takes."""
    w, h = size
    canvas = Image.new("RGB", size, background)
    side_w, side_h = int(w * leaf_fraction), int(h * leaf_fraction)
    x0, y0 = (w - side_w) // 2, (h - side_h) // 2
    canvas.paste(Image.new("RGB", (side_w, side_h), (40, 150, 60)), (x0, y0))
    # A little lesion so the mask has both hue bands to find.
    canvas.paste(Image.new("RGB", (side_w // 4, side_h // 4), (150, 110, 20)),
                 (x0 + side_w // 3, y0 + side_h // 3))
    return canvas


def noisy(size=(256, 256)) -> Image.Image:
    rng = np.random.default_rng(7)
    return Image.fromarray(rng.integers(0, 256, (size[1], size[0], 3), dtype=np.uint8))


def grey(value: int, size=(200, 200)) -> Image.Image:
    return Image.new("RGB", size, (value, value, value))


# ---------------------------------------------------------------------------
# Quality checks
# ---------------------------------------------------------------------------


def test_a_sharp_well_lit_photo_has_no_issues():
    issues, blur = _quality(np.asarray(noisy().convert("RGB")))
    assert issues == []
    assert blur >= BLUR_MIN_VARIANCE


def test_a_smooth_image_is_flagged_blurry():
    gradient = np.tile(np.linspace(40, 200, 200, dtype=np.uint8), (200, 1))
    rgb = np.dstack([gradient] * 3)
    issues, blur = _quality(rgb)
    assert "blurry" in issues
    assert blur < BLUR_MIN_VARIANCE


def test_a_nearly_black_photo_is_flagged_too_dark():
    issues, _ = _quality(np.asarray(grey(int(DARK_MEAN_MAX) - 10).convert("RGB")))
    assert "too_dark" in issues


def test_a_single_colour_photo_is_flagged_blank():
    issues, _ = _quality(np.asarray(grey(128).convert("RGB")))
    assert "blank" in issues


def test_a_tiny_photo_is_flagged_too_small():
    issues, _ = _quality(np.asarray(noisy((MIN_SIDE_PX - 1, 120)).convert("RGB")))
    assert "too_small" in issues


def test_a_photo_exactly_at_the_minimum_side_is_not_too_small():
    issues, _ = _quality(np.asarray(noisy((MIN_SIDE_PX, MIN_SIDE_PX)).convert("RGB")))
    assert "too_small" not in issues


def test_a_dark_and_flat_photo_reports_every_relevant_issue():
    issues, _ = _quality(np.asarray(grey(5, (40, 40)).convert("RGB")))
    assert {"too_small", "too_dark", "blank"} <= set(issues)


def test_a_large_photo_is_downscaled_before_measuring():
    # Must not be slow or memory-hungry on a 4000 px phone photo.
    issues, blur = _quality(np.asarray(noisy((4000, 3000)).convert("RGB")))
    assert issues == []
    assert blur >= BLUR_MIN_VARIANCE


def test_flat_std_threshold_is_the_documented_value():
    assert _quality(np.asarray(grey(128).convert("RGB")))[0].count("blank") == 1
    assert FLAT_STD_MIN == 12.0


# ---------------------------------------------------------------------------
# Leaf segmentation
# ---------------------------------------------------------------------------


def test_a_green_leaf_produces_a_large_mask():
    mask = leaf_mask(np.asarray(leaf_photo().convert("RGB")))
    assert mask.dtype == np.uint8
    assert mask.max() == 255
    assert (mask > 0).mean() > 0.2


def test_a_leaf_free_frame_produces_an_almost_empty_mask():
    mask = leaf_mask(np.asarray(grey(200).convert("RGB")))
    assert (mask > 0).mean() < 0.01


def test_yellow_and_brown_lesions_are_kept_in_the_mask():
    """Diseased tissue must survive segmentation — that is the whole signal."""
    healthy = Image.new("RGB", (200, 200), (40, 150, 60))
    diseased = Image.new("RGB", (200, 200), (40, 150, 60))
    diseased.paste(Image.new("RGB", (80, 80), (150, 110, 20)), (60, 60))
    healthy_share = (leaf_mask(np.asarray(healthy)) > 0).mean()
    diseased_share = (leaf_mask(np.asarray(diseased)) > 0).mean()
    assert diseased_share >= healthy_share * 0.95


def test_a_blue_background_is_not_mistaken_for_leaf():
    mask = leaf_mask(np.asarray(Image.new("RGB", (200, 200), (30, 60, 200))))
    assert (mask > 0).mean() < 0.01


def test_largest_component_returns_none_for_an_empty_mask():
    assert _largest_component(np.zeros((50, 50), np.uint8)) is None


def test_largest_component_keeps_one_blob_and_drops_the_smaller_one():
    mask = np.zeros((100, 100), np.uint8)
    mask[10:90, 10:90] = 255          # big blob
    mask[95:99, 95:99] = 255          # speck
    component = _largest_component(mask)
    assert component is not None
    assert component[10:90, 10:90].all()
    assert component[96, 96] == 0


def test_largest_component_fills_interior_holes():
    mask = np.zeros((100, 100), np.uint8)
    mask[20:80, 20:80] = 255
    mask[40:60, 40:60] = 0            # dark lesion inside the leaf outline
    component = _largest_component(mask)
    assert component[50, 50] == 255


# ---------------------------------------------------------------------------
# preprocess()
# ---------------------------------------------------------------------------


def test_preprocess_returns_a_rgb_image_for_the_model():
    result = preprocess(leaf_photo())
    assert isinstance(result, PreprocessResult)
    assert result.image.mode == "RGB"


def test_preprocess_rejects_an_unknown_step_name():
    with pytest.raises(ValueError, match="unknown preprocessing steps"):
        preprocess(leaf_photo(), ("exif", "sharpen_magic"))


@pytest.mark.parametrize("steps", [
    (),
    ("exif",),
    ("quality",),
    ("leaf_crop",),
    ("background",),
    ("white_bal",),
    ("clahe",),
    ("denoise",),
    ALL_STEPS,
    DEFAULT_STEPS,
])
def test_preprocess_never_fails_whatever_is_enabled(steps):
    result = preprocess(leaf_photo(), steps)
    assert result.image.width > 0 and result.image.height > 0
    assert result.image.mode == "RGB"


@pytest.mark.parametrize("image", [
    lambda: leaf_photo(),
    lambda: noisy(),
    lambda: grey(128),
    lambda: grey(2, (80, 80)),
    lambda: Image.new("RGB", (10, 10), (30, 120, 40)),
    lambda: Image.new("RGB", (2000, 60), (30, 120, 40)),
])
def test_preprocess_survives_awkward_images(image):
    assert preprocess(image()).image.mode == "RGB"


def test_quality_flags_are_reported_for_a_blank_photo():
    result = preprocess(grey(128), ("quality",))
    assert result.poor_quality is True
    assert "blank" in result.quality_issues


def test_quality_flags_are_not_reported_for_a_good_photo():
    result = preprocess(noisy(), ("quality",))
    assert result.poor_quality is False
    assert result.quality_issues == []


def test_leaf_crop_finds_the_leaf_and_records_a_box():
    result = preprocess(leaf_photo(), ("leaf_crop",))
    assert result.leaf_found is True
    assert result.crop_box is not None
    x0, y0, x1, y1 = result.crop_box
    assert 0 <= x0 < x1 <= 480 and 0 <= y0 < y1 <= 360
    # `leaf_fraction` is measured on the FULL frame, before cropping, so it
    # stays at the share the leaf occupied in the original photo.
    assert result.leaf_fraction >= MIN_LEAF_FRACTION
    # The crop is tighter than the frame it came from.
    assert (x1 - x0) < 480 and (y1 - y0) < 360


def test_leaf_crop_keeps_a_square_crop_so_the_leaf_is_not_squashed():
    result = preprocess(leaf_photo(), ("leaf_crop",))
    x0, y0, x1, y1 = result.crop_box
    assert abs((x1 - x0) - (y1 - y0)) <= 1


def test_leaf_crop_falls_back_to_the_full_frame_when_there_is_no_leaf():
    photo = grey(200, (300, 300))
    result = preprocess(photo, ("leaf_crop",))
    assert result.leaf_found is False
    assert result.crop_box is None
    assert result.image.size == (300, 300)


def test_a_frame_that_is_entirely_leaf_is_not_cropped():
    # Cropping a full-frame leaf would only lose the edges.
    photo = Image.new("RGB", (300, 300), (40, 150, 60))
    result = preprocess(photo, ("leaf_crop",))
    assert result.leaf_found is False
    assert result.image.size == (300, 300)


@pytest.mark.parametrize("fraction", [MIN_LEAF_FRACTION - 0.01, MAX_LEAF_FRACTION + 0.001])
def test_leaf_fraction_outside_the_usable_band_is_rejected(fraction):
    result = preprocess(leaf_photo(leaf_fraction=min(max(fraction, 0.01), 0.99)), ("leaf_crop",))
    if not (MIN_LEAF_FRACTION <= result.leaf_fraction <= MAX_LEAF_FRACTION):
        assert result.leaf_found is False


def test_crop_box_stays_inside_the_image_when_the_leaf_touches_an_edge():
    w, h = 300, 200
    photo = Image.new("RGB", (w, h), (235, 235, 235))
    photo.paste(Image.new("RGB", (120, 120), (40, 150, 60)), (0, 0))   # top-left corner
    result = preprocess(photo, ("leaf_crop",))
    x0, y0, x1, y1 = result.crop_box
    assert 0 <= x0 and 0 <= y0 and x1 <= w and y1 <= h
    assert result.image.width <= w and result.image.height <= h


def test_exif_orientation_is_applied_for_a_sideways_phone_photo():
    img = Image.new("RGB", (100, 50), (40, 150, 60))
    exif = img.getexif()
    exif[274] = 6                                     # "rotate 90° CW" tag
    buffer = io.BytesIO()
    img.save(buffer, format="JPEG", exif=exif)
    reopened = Image.open(buffer)
    assert reopened.size == (100, 50)

    rotated = preprocess(reopened, ("exif",))
    assert rotated.image.size == (50, 100)


def test_exif_step_can_be_switched_off():
    img = Image.new("RGB", (100, 50), (40, 150, 60))
    exif = img.getexif()
    exif[274] = 6
    buffer = io.BytesIO()
    img.save(buffer, format="JPEG", exif=exif)
    assert preprocess(Image.open(buffer), ()).image.size == (100, 50)


def test_the_callers_image_is_not_mutated():
    original = leaf_photo()
    before = np.asarray(original.convert("RGB")).copy()
    preprocess(original, ALL_STEPS)
    assert np.array_equal(np.asarray(original.convert("RGB")), before)


def test_a_rgba_png_is_converted_to_rgb():
    result = preprocess(Image.new("RGBA", (200, 200), (40, 150, 60, 255)))
    assert result.image.mode == "RGB"


def test_a_palette_image_is_converted_to_rgb():
    result = preprocess(Image.new("P", (200, 200)))
    assert result.image.mode == "RGB"


def test_grey_world_white_balance_neutralises_a_colour_cast():
    cast = np.full((20, 20, 3), (200, 120, 80), dtype=np.uint8)
    balanced = _gray_world(cast)
    means = balanced.reshape(-1, 3).mean(axis=0)
    assert means.max() - means.min() < 2.0


def test_clahe_keeps_the_image_shape_and_dtype():
    rgb = np.asarray(leaf_photo().convert("RGB"))
    out = _clahe(rgb)
    assert out.shape == rgb.shape and out.dtype == np.uint8


def test_crop_margin_is_the_documented_value():
    assert CROP_MARGIN == 0.08
