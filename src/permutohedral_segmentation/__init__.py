"""Permutohedral simplex segmentation, with an explicit optional merge stage."""
from .api import (
    SegmentationResult, connected_components, label_features, locate_simplices,
    merge_regions, segment,
)
from .config import LatticeConfig, MergeConfig
from .features import image_features

__all__ = [
    "LatticeConfig", "MergeConfig", "SegmentationResult", "connected_components",
    "image_features", "label_features", "locate_simplices", "merge_regions", "segment",
]
