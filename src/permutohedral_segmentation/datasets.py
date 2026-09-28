"""Access user-provided demonstration images without checkout-relative paths."""
from __future__ import annotations
from importlib.resources import as_file, files
import numpy as np
from numpy.typing import NDArray
from .io import load_image


def load_example(name: str = "peppers") -> NDArray[np.uint8]:
    if name not in ("peppers", "cow"):
        raise ValueError("Example name must be 'peppers' or 'cow'.")
    resource = files("permutohedral_segmentation").joinpath("data", name + ".png")
    with as_file(resource) as path:
        return load_image(path)
