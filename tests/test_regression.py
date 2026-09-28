import json
from pathlib import Path
import numpy as np
import pytest
from permutohedral_segmentation import LatticeConfig, MergeConfig, segment, connected_components
from permutohedral_segmentation.datasets import load_example

ROOT = Path(__file__).resolve().parents[1]
GOLDEN = ROOT / "reference" / "golden"
MANIFEST = json.loads((GOLDEN / "manifest.json").read_text()) if GOLDEN.exists() else []


@pytest.mark.regression
@pytest.mark.parametrize("item", MANIFEST, ids=[item["image"]+"_"+item["tag"] for item in MANIFEST])
def test_exact_legacy_labels(item):
    name = item["image"] + "_" + item["tag"]
    image = load_example(item["image"])
    lattice = LatticeConfig(item["mode"], item["spatial_scale"], item["color_scale"])
    merge = None if not item["target"] else MergeConfig(item["target"], item["compactness"], item["merge_color_sigma"])
    result = segment(image, lattice=lattice, merge=merge)
    with np.load(GOLDEN / f"{name}.npz", allow_pickle=False) as archive:
        np.testing.assert_array_equal(result.labels, archive["labels"])
    assert result.simplex_count == item["unique_simplex_ids"]
    assert result.component_count == item["raw_connected_components"]
    assert result.region_count == item["output_labels"]
    if merge is not None:
        assert len(np.unique(connected_components(result.labels))) == merge.target_regions
