"""Build features without coupling the C++ lattice to image formats."""
from __future__ import annotations

import numpy as np
from numpy.typing import ArrayLike, NDArray

from ._validation import rgb_image
from .config import LatticeConfig


def image_features(image: ArrayLike, config: LatticeConfig) -> NDArray[np.float64]:
    """Return row-major (N, D) float64 features, using pixel centers x+0.5/y+0.5."""
    rgb = rgb_image(image)
    height, width = rgb.shape[:2]
    dimension = {"xy": 2, "rgb": 3, "xyrgb": 5}[config.mode]
    features = np.empty((height * width, dimension), dtype=np.float64)
    if config.mode != "rgb":
        yy, xx = np.indices((height, width), dtype=np.float64)
        features[:, 0] = config.spatial_scale * (xx.ravel() + 0.5)
        features[:, 1] = config.spatial_scale * (yy.ravel() + 0.5)
    if config.mode != "xy":
        start = 0 if config.mode == "rgb" else 2
        features[:, start:] = config.color_scale * rgb.reshape(-1, 3)
    return features
