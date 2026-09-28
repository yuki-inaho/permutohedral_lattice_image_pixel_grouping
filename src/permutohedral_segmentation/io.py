"""Image and result persistence; no image I/O dependency exists in the C++ core."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import ArrayLike, NDArray
from PIL import Image, ImageOps

from ._validation import _shape, label_image, rgb_image
from .api import SegmentationResult
from .visualization import mean_colors, overlay_boundaries, render_labels


def load_image(path: str | Path) -> NDArray[np.uint8]:
    """Apply EXIF orientation and composite transparency over white."""
    with Image.open(path) as source:
        _shape(source.height, source.width)
        oriented = ImageOps.exif_transpose(source)
        rgba = oriented.convert("RGBA")
        white = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
        rgb = Image.alpha_composite(white, rgba).convert("RGB")
        return rgb_image(np.array(rgb))


def save_result(directory: str | Path, image: ArrayLike, result: SegmentationResult) -> Path:
    """Write self-describing NPZ labels, metadata and four PNG visualizations.

    Existing result files are replaced, but unrelated files are not deleted.
    Use a new output directory to preserve a previous experiment unchanged.
    """
    destination = Path(directory)
    rgb = rgb_image(image)
    if rgb.shape[:2] != result.labels.shape:
        raise ValueError("Image and label shapes must match.")
    destination.mkdir(parents=True, exist_ok=True)
    mean = mean_colors(rgb, result.labels)
    pictures = {
        "regions": render_labels(result.labels),
        "overlay": overlay_boundaries(rgb, result.labels),
        "mean": mean,
        "mean_boundaries": overlay_boundaries(mean, result.labels),
    }
    np.savez_compressed(destination / "labels.npz", labels=result.labels)
    for name, picture in pictures.items():
        Image.fromarray(picture).save(destination / f"{name}.png")
    (destination / "metadata.json").write_text(
        json.dumps(result.to_metadata(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return destination


def load_result(directory: str | Path) -> tuple[NDArray[np.int32], dict[str, Any]]:
    """Read NPZ without pickle and verify the recorded dimensions and count."""
    source = Path(directory)
    metadata = json.loads((source / "metadata.json").read_text(encoding="utf-8"))
    if not isinstance(metadata, dict):
        raise ValueError("Result metadata must be a JSON object.")
    if metadata.get("schema_version") != 1:
        raise ValueError("Unsupported result schema_version.")
    with np.load(source / "labels.npz", allow_pickle=False) as archive:
        labels = label_image(archive["labels"])
    if list(labels.shape) != metadata.get("shape"):
        raise ValueError("Label shape disagrees with metadata.")
    if len(np.unique(labels)) != metadata.get("region_count"):
        raise ValueError("Region count disagrees with metadata.")
    labels.flags.writeable = False
    return labels, metadata
