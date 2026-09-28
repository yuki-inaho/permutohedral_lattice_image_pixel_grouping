import json
import numpy as np
from PIL import Image
import pytest
from permutohedral_segmentation import segment
from permutohedral_segmentation.io import load_image, save_result, load_result
from permutohedral_segmentation.visualization import boundary_mask, mean_colors, overlay_boundaries, render_labels
from permutohedral_segmentation.datasets import load_example
from permutohedral_segmentation.cli import main


def test_roundtrip(sample, tmp_path):
    result = segment(sample)
    destination = save_result(tmp_path / "space and 日本語", sample, result)
    labels, metadata = load_result(destination)
    np.testing.assert_array_equal(labels, result.labels)
    assert metadata["region_count"] == result.region_count
    assert len(list(destination.glob("*.png"))) == 4


def test_alpha_compositing(tmp_path):
    path = tmp_path / "alpha.png"
    Image.new("RGBA", (1,1), (0,0,0,0)).save(path)
    np.testing.assert_array_equal(load_image(path), [[[255,255,255]]])


def test_grayscale_load(tmp_path):
    path = tmp_path / "gray.png"
    Image.new("L", (2,2), 123).save(path)
    assert load_image(path).shape == (2,2,3)


def test_boundary_convention():
    np.testing.assert_array_equal(boundary_mask([[0,1],[0,1]]), [[True,False],[True,False]])
    assert not boundary_mask([[1]]).any()


def test_mean_rounding_and_sparse_labels():
    image = np.array([[[0,0,0], [1,3,5]]], dtype=np.uint8)
    labels = np.array([[2**30,2**30]], dtype=np.int32)
    np.testing.assert_array_equal(mean_colors(image, labels), [[[1,2,3],[1,2,3]]])
    assert render_labels(labels).shape == image.shape


def test_render_is_deterministic():
    labels = np.array([[0,1,0]], np.int32)
    colors = render_labels(labels)
    np.testing.assert_array_equal(colors[0,0], colors[0,2])
    np.testing.assert_array_equal(colors, render_labels(labels))


def test_bad_image_label_shape(sample, tmp_path):
    labels = np.zeros((3,3), np.int32)
    for render in (mean_colors, overlay_boundaries):
        with pytest.raises(ValueError): render(sample, labels)
    with pytest.raises(ValueError): save_result(tmp_path, sample[:3], segment(sample))


def test_bad_metadata(sample, tmp_path):
    save_result(tmp_path, sample, segment(sample))
    path = tmp_path / "metadata.json"
    metadata = json.loads(path.read_text())
    for key, invalid in [("schema_version",999), ("shape",[1,1]), ("region_count",0)]:
        edited = dict(metadata)
        edited[key] = invalid
        path.write_text(json.dumps(edited))
        with pytest.raises(ValueError): load_result(tmp_path)


def test_example_names():
    assert load_example("peppers").shape == (512,512,3)
    assert load_example("cow").shape == (235,418,3)
    with pytest.raises(ValueError): load_example("../bad")


def test_cli(tmp_path, capsys):
    status = main(["--example","cow","--output",str(tmp_path),"--mode","xy"])
    assert status == 0
    assert json.loads(capsys.readouterr().out)["region_count"] > 0
    assert (tmp_path / "labels.npz").is_file()


def test_cli_failure(tmp_path, capsys):
    assert main(["--input",str(tmp_path / "missing.png"),"--output",str(tmp_path)]) == 1
    assert "Error:" in capsys.readouterr().err


def test_metadata_requires_object(tmp_path):
    (tmp_path / "metadata.json").write_text("[]", encoding="utf-8")
    with pytest.raises(ValueError, match="JSON object"):
        load_result(tmp_path)


def test_image_pixel_limit_before_decode(tmp_path, monkeypatch):
    import permutohedral_segmentation._validation as validation
    path = tmp_path / "over-limit.png"
    Image.new("RGB", (3, 3)).save(path)
    monkeypatch.setattr(validation, "MAX_PIXELS", 4)
    with pytest.raises(ValueError, match="pixels"):
        load_image(path)
