"""Array contracts shared by the API, I/O and visualization layers."""
from __future__ import annotations

import numpy as np
from numpy.typing import ArrayLike, NDArray

MAX_PIXELS = 20_000_000


def _shape(height: int, width: int) -> None:
    if height < 1 or width < 1 or height * width > MAX_PIXELS:
        raise ValueError("Image must contain 1..20,000,000 pixels.")


def rgb_image(image: ArrayLike) -> NDArray[np.uint8]:
    array = np.asarray(image)
    if array.ndim != 3 or array.shape[2] != 3:
        raise ValueError("Expected an RGB image with shape (height, width, 3).")
    _shape(array.shape[0], array.shape[1])
    if array.dtype != np.uint8:
        raise TypeError("RGB images must have dtype uint8 (range 0..255).")
    return np.ascontiguousarray(array)


def label_image(labels: ArrayLike) -> NDArray[np.int32]:
    array = np.asarray(labels)
    if array.ndim != 2:
        raise ValueError("Labels must be a two-dimensional integer array.")
    _shape(array.shape[0], array.shape[1])
    if array.dtype.kind not in "iu":
        raise TypeError("Labels must have an integer dtype; booleans are not labels.")
    if np.min(array) < 0 or np.max(array) > np.iinfo(np.int32).max:
        raise ValueError("Labels must fit nonnegative int32 values.")
    return np.ascontiguousarray(array, dtype=np.int32)


def feature_matrix(features: ArrayLike) -> NDArray[np.float64]:
    array = np.asarray(features)
    if array.ndim != 2 or not 1 <= array.shape[1] <= 8:
        raise ValueError("Features must have shape (N, D), with 1 <= D <= 8.")
    if not 1 <= array.shape[0] <= MAX_PIXELS:
        raise ValueError("Features must contain 1..20,000,000 points.")
    if array.dtype.kind not in "fiu":
        raise TypeError("Features must be real numeric values.")
    array = np.ascontiguousarray(array, dtype=np.float64)
    if not np.all(np.isfinite(array)):
        raise ValueError("Features must contain only finite values.")
    return array
