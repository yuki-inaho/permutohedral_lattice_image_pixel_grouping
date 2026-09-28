"""Record an allowlisted environment snapshot, without tokens or environment secrets."""
from datetime import datetime, timezone
from importlib import metadata
import json
import platform
import shutil
import subprocess
import sys
from _project import ROOT


def main() -> None:
    packages = {}
    for name in ("numpy", "pillow", "nanobind", "scikit-build-core", "pytest", "pytest-cov",
                 "nbclient", "nbformat", "ipykernel", "jupyterlab", "ruff", "mypy"):
        try: packages[name] = metadata.version(name)
        except metadata.PackageNotFoundError: packages[name] = None
    tools = {}
    for name in ("uv", "cmake", "g++", "clang++", "zstd"):
        executable = shutil.which(name)
        if executable:
            result = subprocess.run([executable, "--version"], capture_output=True, text=True, check=False)
            tools[name] = (result.stdout or result.stderr).splitlines()[0]
    report = {
        "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
        "platform": platform.platform(), "machine": platform.machine(),
        "python": sys.version, "interpreter": sys.executable,
        "packages": packages, "tools": tools,
        "uv_lock_exists": (ROOT / "uv.lock").is_file(),
        "note": "Observed environment, not a resolved uv dependency lock or a portability guarantee.",
    }
    destination = ROOT / "reports" / "environment.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report, indent=2)+"\n", encoding="utf-8")
    print(destination)


if __name__ == "__main__":
    main()
