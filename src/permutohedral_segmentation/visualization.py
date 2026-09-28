"""Deterministic rendering, independent of the segmentation algorithm."""
from __future__ import annotations

import numpy as np
from numpy.typing import ArrayLike, NDArray

from ._validation import label_image, rgb_image


def boundary_mask(labels: ArrayLike) -> NDArray[np.bool_]:
    """One-sided right/down raster boundaries; no artificial image-frame border."""
    array = label_image(labels)
    mask = np.zeros(array.shape, dtype=bool)
    mask[:, :-1] |= array[:, :-1] != array[:, 1:]
    mask[:-1, :] |= array[:-1, :] != array[1:, :]
    return mask


def render_labels(labels: ArrayLike) -> NDArray[np.uint8]:
    """Color IDs using the legacy deterministic hash. Colors have no semantics."""
    array = label_image(labels)
    ids, inverse = np.unique(array, return_inverse=True)
    z = ids.astype(np.uint64) + np.uint64(0x9E3779B97F4A7C15 + 20260927)
    z = (z ^ (z >> np.uint64(30))) * np.uint64(0xBF58476D1CE4E5B9)
    z = (z ^ (z >> np.uint64(27))) * np.uint64(0x94D049BB133111EB)
    z ^= z >> np.uint64(31)
    palette = np.stack([
        40 + ((z >> np.uint64(shift)) & 255) * 200 // 255 for shift in (0, 8, 16)
    ], axis=1).astype(np.uint8)
    return palette[inverse.reshape(array.shape)]


def overlay_boundaries(image: ArrayLike, labels: ArrayLike) -> NDArray[np.uint8]:
    rgb = rgb_image(image)
    mask = boundary_mask(labels)
    if rgb.shape[:2] != mask.shape:
        raise ValueError("Image and label shapes must match.")
    output = rgb.copy()
    output[mask] = 0
    return output


def mean_colors(image: ArrayLike, labels: ArrayLike) -> NDArray[np.uint8]:
    rgb, array = rgb_image(image), label_image(labels)
    if rgb.shape[:2] != array.shape:
        raise ValueError("Image and label shapes must match.")
    _, inverse = np.unique(array, return_inverse=True)
    flat = inverse.ravel()
    counts = np.bincount(flat)
    means = np.stack([
        np.bincount(flat, weights=rgb[..., channel].ravel()) / counts for channel in range(3)
    ], axis=1)
    # RGB is nonnegative: floor(v + 0.5) matches the old C++ std::lround.
    palette = np.floor(means + 0.5).astype(np.uint8)
    return palette[flat].reshape(rgb.shape)
