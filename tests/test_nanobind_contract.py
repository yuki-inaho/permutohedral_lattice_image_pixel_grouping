"""Tests that MUST run on nanobind; the offline test adapter cannot validate them."""
import gc
import numpy as np
import pytest
from permutohedral_segmentation import _native

pytestmark = pytest.mark.skipif(
    hasattr(_native, "__test_backend__"),
    reason="nanobind was not installed; the test-only C ABI cannot validate this contract",
)


def test_capsule_owns_result_after_call():
    labels, count = _native.label_features(np.arange(60, dtype=np.float64).reshape(20,3))
    expected = labels.copy()
    for _ in range(10):
        _native.label_features(np.zeros((50,3)))
    gc.collect()
    np.testing.assert_array_equal(labels, expected)
    assert count > 0


@pytest.mark.parametrize("value", [np.zeros((3,2), np.float32), np.zeros((3,4))[:,::2], np.zeros((2,2,2))])
def test_native_noconvert_rejects_wrong_arrays(value):
    with pytest.raises(TypeError): _native.label_features(value)


def test_native_readonly_input():
    features = np.zeros((4,2))
    features.flags.writeable = False
    labels, count = _native.label_features(features)
    assert count == 1
    np.testing.assert_array_equal(labels, 0)


def test_native_shape_mismatch():
    with pytest.raises(ValueError):
        _native.merge_regions(np.zeros((2,2,3), np.uint8), np.zeros((3,3), np.int32), 1, 0.3, 48)


def test_native_geometry_owner():
    vertices, weights, elevated = _native.locate_simplices(np.ones((5,2)))
    gc.collect()
    np.testing.assert_allclose(np.einsum("ni,nij->nj", weights, vertices), elevated)


def test_native_rejects_nonfinite():
    with pytest.raises(ValueError): _native.label_features(np.array([[np.inf]]))
