from pathlib import Path
import importlib.util
import pytest


def pytest_addoption(parser):
    parser.addoption("--offline-native", action="store_true",
                     help="Use test-only C ABI bridge; DOES NOT validate nanobind")


def pytest_configure(config):
    if config.getoption("--offline-native"):
        path = Path(__file__).resolve().parents[1] / "scripts" / "_project.py"
        spec = importlib.util.spec_from_file_location("project_test_helpers", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        module.activate_test_bridge()


def pytest_report_header(config):
    return ("Backend: ctypes-test-adapter; nanobind NOT validated" if
            config.getoption("--offline-native") else "Backend: nanobind")


@pytest.fixture
def sample():
    import numpy as np
    yy, xx = np.indices((24, 32))
    return np.stack([xx * 7, yy * 10, (xx + yy) * 4], axis=-1).astype(np.uint8)
