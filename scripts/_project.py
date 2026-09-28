"""Shared development helpers. No automatic substitution of the native binding."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]


def activate_test_bridge() -> None:
    """Explicitly select a C ABI test adapter, never a production fallback."""
    module_name = "permutohedral_segmentation._native"
    if module_name in sys.modules:
        raise RuntimeError("Select the test bridge before importing the package.")
    spec = importlib.util.spec_from_file_location(
        module_name, ROOT / "tests" / "support" / "native_adapter.py"
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("Cannot load the native test adapter.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    sys.modules[module_name] = module
    sys.path.insert(0, str(ROOT / "src"))
