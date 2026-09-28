"""Run reproducible checks and save actual commands, exit codes and complete logs."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import subprocess
import sys
from time import perf_counter
from _project import ROOT


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--offline-native", action="store_true",
                        help="Test C++/Python via explicit C ABI; do not claim nanobind verification")
    parser.add_argument("--notebooks", action="store_true")
    args = parser.parse_args()
    reports = ROOT / "reports"
    logs = reports / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    commands = [
        ("native-configure", ["cmake", "-S", ".", "-B", "build/native", "-DPERMUTOHEDRAL_BUILD_PYTHON=OFF",
                              "-DPERMUTOHEDRAL_BUILD_TESTS=ON", "-DCMAKE_BUILD_TYPE=Release"]),
        ("native-build", ["cmake", "--build", "build/native", "--config", "Release", "--parallel", "2"]),
        ("native-ctest", ["ctest", "--test-dir", "build/native", "-C", "Release", "-V", "--output-on-failure"]),
        ("python-compile", [sys.executable, "-m", "compileall", "-q", "src", "scripts", "tests"]),
        ("pytest", [sys.executable, "-m", "pytest", "--cov=permutohedral_segmentation", "--cov-report=term-missing",
                    "--cov-report=xml:reports/coverage.xml", "--junitxml=reports/pytest.xml"]),
        ("reproduce", [sys.executable, "scripts/reproduce.py"]),
    ]
    if args.offline_native:
        for name, command in commands:
            if name in ("pytest", "reproduce"):
                command.append("--offline-native")
    if args.notebooks:
        commands.append(("notebooks", [sys.executable, "scripts/run_notebooks.py"] +
                         (["--offline-native"] if args.offline_native else [])))
    commands.append(("environment", [sys.executable, "scripts/record_environment.py"]))
    record = {"backend": "ctypes-test-adapter; nanobind unverified" if args.offline_native else "nanobind",
              "steps": []}
    for name, command in commands:
        start = perf_counter()
        timestamp = datetime.now(timezone.utc).isoformat()
        completed = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=False)
        (logs / f"{name}.txt").write_text(
            "$ " + subprocess.list2cmdline(command) + "\n" + completed.stdout + completed.stderr,
            encoding="utf-8",
        )
        record["steps"].append({"step": name, "started_at_utc": timestamp, "command": command,
                                 "exit_code": completed.returncode, "seconds": perf_counter()-start,
                                 "log": f"logs/{name}.txt"})
        (reports / "verification.json").write_text(json.dumps(record, indent=2)+"\n", encoding="utf-8")
        print(f"{name}: exit {completed.returncode}", flush=True)
        if completed.returncode:
            print(completed.stdout + completed.stderr)
            raise SystemExit(completed.returncode)


if __name__ == "__main__":
    main()
