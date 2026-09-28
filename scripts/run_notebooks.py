"""Execute every notebook with the current interpreter and a temporary kernel."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
import tempfile
from time import perf_counter

from jupyter_client import KernelManager
from jupyter_client.kernelspec import KernelSpecManager
from nbclient import NotebookClient
import nbformat
from _project import ROOT


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "reports" / "notebooks")
    parser.add_argument("--offline-native", action="store_true")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    environment = os.environ.copy()
    environment.pop("PERMUTOHEDRAL_TEST_BRIDGE", None)
    if args.offline_native:
        environment["PERMUTOHEDRAL_TEST_BRIDGE"] = "1"
    backend = "ctypes-test-adapter (nanobind not validated)" if args.offline_native else "nanobind"
    runs = []
    # No global or user kernelspec is installed; no absolute interpreter path is saved in notebooks.
    with tempfile.TemporaryDirectory(prefix="permutohedral-kernel-") as temporary:
        kernel_dir = Path(temporary) / "permutohedral-project"
        kernel_dir.mkdir()
        (kernel_dir / "kernel.json").write_text(json.dumps({
            "argv": [sys.executable, "-m", "ipykernel_launcher", "-f", "{connection_file}"],
            "display_name": "Permutohedral project", "language": "python",
        }), encoding="utf-8")
        for source in sorted((ROOT / "notebooks").glob("*.ipynb")):
            notebook = nbformat.read(source, as_version=4)
            manager = KernelManager(
                kernel_name="permutohedral-project",
                kernel_spec_manager=KernelSpecManager(kernel_dirs=[temporary]),
            )
            client = NotebookClient(notebook, km=manager, timeout=180,
                                    resources={"metadata": {"path": str(ROOT)}})
            start = perf_counter()
            try:
                client.execute(env=environment, cwd=str(ROOT))
                errors = [output for cell in notebook.cells for output in cell.get("outputs", [])
                          if output.get("output_type") == "error"]
                if errors:
                    raise RuntimeError(f"Notebook contains errors: {source.name}")
                notebook.metadata["execution_record"] = {
                    "backend": backend, "executed_at_utc": datetime.now(timezone.utc).isoformat(),
                    "python_version": sys.version.split()[0],
                }
                nbformat.write(notebook, args.output / source.name)
                runs.append({"notebook": source.name, "status": "passed", "seconds": perf_counter()-start,
                             "code_cells": sum(cell.cell_type == "code" for cell in notebook.cells)})
                print(f"{source.name}: passed ({backend})")
            finally:
                if manager.has_kernel:
                    manager.shutdown_kernel(now=True)
    (args.output / "execution.json").write_text(json.dumps({
        "backend": backend, "runs": runs,
    }, indent=2)+"\n", encoding="utf-8")


if __name__ == "__main__":
    main()
