"""Smoke check to be run against an installed wheel, outside the source checkout."""
import numpy as np
from permutohedral_segmentation import LatticeConfig, MergeConfig, segment
from permutohedral_segmentation.datasets import load_example
from permutohedral_segmentation import _native

assert not hasattr(_native, "__test_backend__"), "A wheel must use nanobind, never the test bridge"
image = load_example("peppers")
result = segment(image, lattice=LatticeConfig("xy", 0.025, 0.01))
assert result.region_count == 405
merged = segment(image, lattice=LatticeConfig("xyrgb", 0.025, 0.01), merge=MergeConfig(100))
assert np.unique(merged.labels).size == 100
print("Installed nanobind wheel smoke check passed")
