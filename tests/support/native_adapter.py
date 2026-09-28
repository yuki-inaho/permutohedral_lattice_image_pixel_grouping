"""Explicit test adapter to the real C++ core, not a nanobind emulation claim.

Only enabled by --offline-native. This module is excluded from installed wheels.
It validates Python orchestration and C++ algorithms, NOT nanobind build/ownership.
"""
from __future__ import annotations

import ctypes as ct
from pathlib import Path
import numpy as np

__test_backend__ = "ctypes-test-adapter (nanobind not validated)"
ROOT = Path(__file__).resolve().parents[2]
CANDIDATES = sorted((ROOT / "build" / "native").rglob("*permutohedral_test_bridge*"))
LIBRARY = next((path for path in CANDIDATES if path.suffix in (".so", ".dylib", ".dll")), None)
if LIBRARY is None:
    raise ImportError("Build the test bridge: cmake --build build/native --config Release")
lib = ct.CDLL(str(LIBRARY))
ptr = ct.c_void_p
iptr = ct.POINTER(ct.c_int)
lib.ps_error.argtypes = []
lib.ps_error.restype = ct.c_char_p
lib.ps_label.argtypes = [ptr, ct.c_size_t, ct.c_int, ptr, iptr]
lib.ps_geometry.argtypes = [ptr, ct.c_size_t, ct.c_int, ptr, ptr, ptr]
lib.ps_components.argtypes = [ptr, ct.c_int, ct.c_int, ptr, iptr]
lib.ps_merge.argtypes = [ptr, ptr, ct.c_int, ct.c_int, ct.c_int, ct.c_double,
                        ct.c_double, ptr, iptr, iptr]
for name in ("ps_label", "ps_geometry", "ps_components", "ps_merge"):
    getattr(lib, name).restype = ct.c_int


def _check(code):
    if code:
        raise ValueError(lib.ps_error().decode("utf-8"))


def _array(value, dtype, ndim):
    if not isinstance(value, np.ndarray) or value.dtype != dtype or value.ndim != ndim:
        raise TypeError("Native test adapter received an incompatible array.")
    if not value.flags.c_contiguous:
        raise TypeError("Native test adapter requires C-contiguous arrays.")


def label_features(features):
    _array(features, np.float64, 2)
    output = np.empty(features.shape[0], dtype=np.int32)
    count = ct.c_int()
    _check(lib.ps_label(features.ctypes.data, features.shape[0], features.shape[1],
                        output.ctypes.data, ct.byref(count)))
    return output, count.value


def locate_simplices(features):
    _array(features, np.float64, 2)
    n, d = features.shape
    if n > 100_000 or not 1 <= d <= 8:
        raise ValueError("Invalid geometry input size.")
    vertices = np.empty((n, d + 1, d + 1), dtype=np.int32)
    weights = np.empty((n, d + 1), dtype=np.float64)
    elevated = np.empty_like(weights)
    _check(lib.ps_geometry(features.ctypes.data, n, d, vertices.ctypes.data,
                          weights.ctypes.data, elevated.ctypes.data))
    return vertices, weights, elevated


def connected_components(labels):
    _array(labels, np.int32, 2)
    output = np.empty_like(labels)
    count = ct.c_int()
    _check(lib.ps_components(labels.ctypes.data, labels.shape[1], labels.shape[0],
                             output.ctypes.data, ct.byref(count)))
    return output, count.value


def merge_regions(image, labels, target, compactness=0.3, color_sigma=48.0):
    _array(image, np.uint8, 3)
    _array(labels, np.int32, 2)
    if image.shape[2] != 3 or image.shape[:2] != labels.shape:
        raise ValueError("Image and label shapes must match.")
    output = np.empty_like(labels)
    count, components = ct.c_int(), ct.c_int()
    _check(lib.ps_merge(image.ctypes.data, labels.ctypes.data, labels.shape[1],
                        labels.shape[0], target, compactness, color_sigma,
                        output.ctypes.data, ct.byref(count), ct.byref(components)))
    return output, count.value, components.value
