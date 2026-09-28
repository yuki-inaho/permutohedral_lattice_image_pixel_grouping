"""Public API. Numerical kernels are implemented once, in the C++ core."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from importlib.metadata import PackageNotFoundError, version
from time import perf_counter
from types import MappingProxyType
from typing import Any, Mapping

import numpy as np
from numpy.typing import ArrayLike, NDArray

from . import _native
from ._validation import feature_matrix, label_image, rgb_image
from .config import LatticeConfig, MergeConfig
from .features import image_features


def package_version() -> str:
    try:
        return version("permutohedral-segmentation")
    except PackageNotFoundError:
        return "uninstalled-source"


def _readonly(array: NDArray[Any]) -> NDArray[Any]:
    array.flags.writeable = False
    return array


@dataclass(frozen=True, slots=True)
class SegmentationResult:
    labels: NDArray[np.int32]
    simplex_count: int
    component_count: int
    region_count: int
    lattice: LatticeConfig
    merge: MergeConfig | None
    timings_ms: Mapping[str, float]

    def to_metadata(self) -> dict[str, Any]:
        """JSON-compatible metadata; timing excludes file I/O and rendering."""
        return {
            "schema_version": 1,
            "package_version": package_version(),
            "shape": list(self.labels.shape),
            "dtype": "int32",
            "label_order": "row-major, zero-based, dense",
            "coordinate_convention": "pixel centers x+0.5,y+0.5; RGB 0..255",
            "lattice_normalization": "sqrt(2/3)*(D+1)",
            "lattice": asdict(self.lattice),
            "merge": asdict(self.merge) if self.merge is not None else None,
            "simplex_count": self.simplex_count,
            "component_count": self.component_count,
            "region_count": self.region_count,
            "timings_ms": dict(self.timings_ms),
            "timing_excludes": "file I/O, rendering, final connectivity verification",
        }


def label_features(features: ArrayLike) -> NDArray[np.int32]:
    """Assign each feature to its enclosing simplex; support dimensions 1..8.

    IDs use first-seen row order. Equal IDs need not be spatially connected.
    Non-contiguous arrays and real numeric dtypes are explicitly converted.
    Do not mutate input arrays concurrently while this function is running.
    """
    array = feature_matrix(features)
    labels, _ = _native.label_features(array)
    return _readonly(labels)


def locate_simplices(features: ArrayLike) -> tuple[NDArray[np.int32], NDArray[np.float64], NDArray[np.float64]]:
    """Return vertices (N,D+1,D+1), weights (N,D+1), elevated positions (N,D+1).

    Intended for inspection/tests, limited to 100,000 points. Vertex coordinates
    sum to zero. Barycentric weights reconstruct the elevated positions.
    """
    array = feature_matrix(features)
    if array.shape[0] > 100_000:
        raise ValueError("Geometry inspection is limited to 100,000 points.")
    vertices, weights, elevated = _native.locate_simplices(array)
    return _readonly(vertices), _readonly(weights), _readonly(elevated)


def connected_components(labels: ArrayLike) -> NDArray[np.int32]:
    """Split every label into 4-connected components and densely renumber them."""
    output, _ = _native.connected_components(label_image(labels))
    return _readonly(output)


def merge_regions(image: ArrayLike, labels: ArrayLike, config: MergeConfig) -> NDArray[np.int32]:
    """Split labels into connected components, then merge adjacent regions only."""
    rgb, initial = rgb_image(image), label_image(labels)
    if rgb.shape[:2] != initial.shape:
        raise ValueError("Image and label shapes must match.")
    output, _, _ = _native.merge_regions(
        rgb, initial, config.target_regions, config.compactness, config.color_sigma
    )
    return _readonly(output)


def segment(
    image: ArrayLike,
    *,
    lattice: LatticeConfig | None = None,
    merge: MergeConfig | None = None,
) -> SegmentationResult:
    """Partition an 8-bit RGB image; never merge unless MergeConfig is provided.

    The output labels are read-only. Use result.labels.copy() for writable data.
    Spatial and color scales are multipliers, not desired region counts.
    """
    if lattice is None:
        lattice = LatticeConfig()
    if not isinstance(lattice, LatticeConfig):
        raise TypeError("lattice must be a LatticeConfig.")
    if merge is not None and not isinstance(merge, MergeConfig):
        raise TypeError("merge must be a MergeConfig or None.")
    t0 = perf_counter()
    rgb = rgb_image(image)
    features = image_features(rgb, lattice)
    t1 = perf_counter()
    labels, simplex_count = _native.label_features(features)
    labels = labels.reshape(rgb.shape[:2])
    t2 = perf_counter()
    if merge is None:
        _, component_count = _native.connected_components(labels)
        output, region_count = labels, simplex_count
    else:
        output, region_count, component_count = _native.merge_regions(
            rgb, labels, merge.target_regions, merge.compactness, merge.color_sigma
        )
    t3 = perf_counter()
    timings = MappingProxyType({
        "features": (t1 - t0) * 1000,
        "partition": (t2 - t1) * 1000,
        "components_and_merge": (t3 - t2) * 1000,
        "total": (t3 - t0) * 1000,
    })
    return SegmentationResult(
        _readonly(output), int(simplex_count), int(component_count), int(region_count),
        lattice, merge, timings,
    )
