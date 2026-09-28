from concurrent.futures import ThreadPoolExecutor
import gc
from dataclasses import FrozenInstanceError
import numpy as np
import pytest

from permutohedral_segmentation import (
    LatticeConfig, MergeConfig, connected_components, image_features,
    label_features, locate_simplices, merge_regions, segment,
)


def reference_components(labels):
    """Small independent flood-fill oracle; no production C++ code is reused."""
    h, w = labels.shape
    output = np.full((h, w), -1, dtype=np.int32)
    count = 0
    for y in range(h):
        for x in range(w):
            if output[y, x] >= 0:
                continue
            stack = [(y, x)]
            output[y, x] = count
            while stack:
                py, px = stack.pop()
                for qy, qx in ((py-1, px), (py+1, px), (py, px-1), (py, px+1)):
                    if 0 <= qy < h and 0 <= qx < w and output[qy, qx] < 0 and labels[qy, qx] == labels[py, px]:
                        output[qy, qx] = count
                        stack.append((qy, qx))
            count += 1
    return output


@pytest.mark.parametrize("mode", ["xy", "rgb", "xyrgb"])
def test_shape_dense_ids_no_mutation(sample, mode):
    original = sample.copy()
    result = segment(sample, lattice=LatticeConfig(mode, 0.1, 0.02))
    assert result.labels.shape == sample.shape[:2]
    assert result.labels.dtype == np.int32
    assert not result.labels.flags.writeable
    np.testing.assert_array_equal(np.unique(result.labels), np.arange(result.region_count))
    np.testing.assert_array_equal(original, sample)
    assert result.simplex_count == result.region_count
    assert result.merge is None
    assert result.to_metadata()["shape"] == [24, 32]


def test_xy_ignores_color(sample):
    np.testing.assert_array_equal(segment(sample).labels, segment(255-sample).labels)


def test_rgb_ignores_spatial_scale(sample):
    a = segment(sample, lattice=LatticeConfig("rgb", 0.1, 0.02))
    b = segment(sample, lattice=LatticeConfig("rgb", 100, 0.02))
    np.testing.assert_array_equal(a.labels, b.labels)


def test_feature_convention():
    image = np.array([[[10, 20, 30], [40, 50, 60]]], dtype=np.uint8)
    expected = [[0.125, 0.125, 1, 2, 3], [0.375, 0.125, 4, 5, 6]]
    np.testing.assert_allclose(image_features(image, LatticeConfig("xyrgb", 0.25, 0.1)), expected)


@pytest.mark.parametrize("dimension", range(1, 9))
def test_geometry_reconstruction(dimension):
    points = np.random.default_rng(127+dimension).uniform(-25, 25, size=(250, dimension))
    vertices, weights, elevated = locate_simplices(points)
    np.testing.assert_array_equal(vertices.sum(axis=2), 0)
    np.testing.assert_allclose(weights.sum(axis=1), 1, atol=1e-12)
    assert weights.min() >= -1e-12
    np.testing.assert_allclose(np.einsum("ni,nij->nj", weights, vertices), elevated, atol=1e-11)


@pytest.mark.parametrize("dimension", range(1, 9))
def test_repeated_features_have_same_id(dimension):
    points = np.random.default_rng(dimension).normal(size=(20, dimension))
    output = label_features(np.repeat(points, 2, axis=0))
    np.testing.assert_array_equal(output[::2], output[1::2])


@pytest.mark.parametrize("seed", range(6))
def test_connected_components_against_independent_reference(seed):
    labels = np.random.default_rng(seed).integers(0, 4, size=(16, 21), dtype=np.int32)
    np.testing.assert_array_equal(connected_components(labels), reference_components(labels))


def test_diagonals_do_not_connect():
    labels = np.array([[7, 9], [9, 7]], dtype=np.int32)
    np.testing.assert_array_equal(connected_components(labels), [[0, 1], [2, 3]])


@pytest.mark.parametrize("target", [1, 7, 20])
def test_merge_has_exact_connected_target(sample, target):
    result = segment(sample, lattice=LatticeConfig("xyrgb", 0.2, 0.1), merge=MergeConfig(target))
    assert result.region_count == target
    np.testing.assert_array_equal(result.labels, reference_components(result.labels))


def test_merge_rejects_impossible_target(sample):
    with pytest.raises(ValueError, match="Target"):
        merge_regions(sample, np.zeros(sample.shape[:2], np.int32), MergeConfig(2))


def test_noncontiguous_image(sample):
    view = sample[:, ::2, :]
    np.testing.assert_array_equal(segment(view).labels, segment(view.copy()).labels)


def test_noncontiguous_features():
    features = np.arange(40, dtype=np.float32).reshape(10, 4)[:, ::2]
    np.testing.assert_array_equal(label_features(features), label_features(features.copy()))


def test_output_outlives_input(sample):
    result = segment(sample)
    expected = result.labels.copy()
    del sample
    gc.collect()
    np.testing.assert_array_equal(result.labels, expected)


def test_thread_reentrancy(sample):
    def execute(_):
        return segment(sample, lattice=LatticeConfig("xyrgb", 0.1, 0.01), merge=MergeConfig(8)).labels
    with ThreadPoolExecutor(max_workers=4) as pool:
        outputs = list(pool.map(execute, range(8)))
    for output in outputs:
        np.testing.assert_array_equal(output, outputs[0])


def test_config_is_frozen():
    config = LatticeConfig()
    with pytest.raises(FrozenInstanceError):
        config.mode = "rgb"


@pytest.mark.parametrize("shape", [(1,1,3), (1,17,3), (19,1,3)])
def test_degenerate_image_dimensions(shape):
    image = np.zeros(shape, dtype=np.uint8)
    result = segment(image, merge=MergeConfig(1))
    assert result.region_count == 1
    assert np.all(result.labels == 0)


@pytest.mark.parametrize("value", [0, -1, float("nan"), float("inf"), 1e20])
def test_bad_scale(value):
    with pytest.raises(ValueError):
        LatticeConfig(spatial_scale=value)


@pytest.mark.parametrize("value", [True, "0.1", None, complex(1,2)])
def test_nonreal_scale(value):
    with pytest.raises(TypeError):
        LatticeConfig(color_scale=value)


@pytest.mark.parametrize("value", [0, -1, 20_000_001])
def test_bad_target(value):
    with pytest.raises(ValueError):
        MergeConfig(value)


@pytest.mark.parametrize("value", [True, 1.2, "3", None])
def test_noninteger_target(value):
    with pytest.raises(TypeError):
        MergeConfig(value)


@pytest.mark.parametrize("kwargs", [{"compactness": -1}, {"compactness": float("nan")}, {"color_sigma": 0}, {"color_sigma": 1e-300}])
def test_bad_merge_numbers(kwargs):
    with pytest.raises(ValueError):
        MergeConfig(1, **kwargs)


@pytest.mark.parametrize("array", [np.zeros((0,2,3), np.uint8), np.zeros((2,2), np.uint8), np.zeros((2,2,4), np.uint8)])
def test_bad_image_shape(array):
    with pytest.raises(ValueError):
        segment(array)


@pytest.mark.parametrize("dtype", [np.float32, np.int32, np.bool_])
def test_bad_image_dtype(dtype):
    with pytest.raises(TypeError):
        segment(np.zeros((2,2,3), dtype=dtype))


@pytest.mark.parametrize("array", [np.zeros((0,2)), np.zeros((1,9)), np.zeros((2,)), [[np.nan]], [[np.inf]], [[1e308,1e308]]])
def test_invalid_features(array):
    with pytest.raises(ValueError):
        label_features(array)


@pytest.mark.parametrize("array", [[[True]], [["a"]], [[1j]]])
def test_invalid_feature_dtype(array):
    with pytest.raises(TypeError):
        label_features(array)


@pytest.mark.parametrize("array", [np.array([[-1]]), np.array([[2**32]], np.uint64), np.empty((0,1), np.int32), np.array([1,2])])
def test_invalid_labels(array):
    with pytest.raises(ValueError):
        connected_components(array)


@pytest.mark.parametrize("dtype", [np.float32, np.bool_])
def test_invalid_label_dtype(dtype):
    with pytest.raises(TypeError):
        connected_components(np.zeros((2,2), dtype=dtype))


def test_geometry_memory_limit():
    with pytest.raises(ValueError, match="100,000"):
        locate_simplices(np.zeros((100_001, 1)))


def test_parameter_type_errors(sample):
    with pytest.raises(TypeError):
        segment(sample, lattice={})
    with pytest.raises(TypeError):
        segment(sample, merge=12)
    with pytest.raises(ValueError):
        LatticeConfig(mode="invalid")


def test_merge_mismatched_shapes(sample):
    with pytest.raises(ValueError):
        merge_regions(sample, np.zeros((3,3), np.int32), MergeConfig(1))


def test_standalone_merge_success(sample):
    labels = np.arange(sample.shape[0]*sample.shape[1], dtype=np.int32).reshape(sample.shape[:2])
    output = merge_regions(sample, labels, MergeConfig(5))
    assert len(np.unique(output)) == 5
    np.testing.assert_array_equal(output, reference_components(output))
