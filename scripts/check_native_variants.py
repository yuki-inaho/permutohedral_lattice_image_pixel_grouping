"""Record independent GNU/Clang native builds, optionally with sanitizers.

This checks C++ code only. It neither installs nor validates nanobind.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import shutil
import subprocess
from time import perf_counter
from _project import ROOT


def main() -> None:
    reports = ROOT / "reports"
    logs = reports / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    checks = []
    variants = [("gcc-sanitizers", "g++", True), ("clang-release", "clang++", False)]
    for name, compiler, sanitize in variants:
        executable = shutil.which(compiler)
        if executable is None:
            checks.append({"variant": name, "status": "skipped", "reason": "compiler unavailable"})
            continue
        build = "build/" + name
        commands = [
            ["cmake", "-S", ".", "-B", build, "-DPERMUTOHEDRAL_BUILD_PYTHON=OFF",
             "-DPERMUTOHEDRAL_BUILD_TESTS=ON", f"-DCMAKE_CXX_COMPILER={executable}",
             "-DCMAKE_BUILD_TYPE=" + ("Debug" if sanitize else "Release"),
             "-DPERMUTOHEDRAL_SANITIZERS=" + ("ON" if sanitize else "OFF")],
            ["cmake", "--build", build, "--parallel", "2"],
            ["ctest", "--test-dir", build, "-V", "--output-on-failure"],
        ]
        record = {"variant": name, "started_at_utc": datetime.now(timezone.utc).isoformat(), "steps": []}
        for index, command in enumerate(commands):
            start = perf_counter()
            completed = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=False)
            log = f"{name}-{index}.txt"
            (logs / log).write_text(
                "$ " + subprocess.list2cmdline(command) + "\n" + completed.stdout + completed.stderr,
                encoding="utf-8",
            )
            record["steps"].append({"command": command, "exit_code": completed.returncode,
                                     "seconds": perf_counter()-start, "log": "logs/"+log})
            if completed.returncode:
                record["status"] = "failed"
                break
        else:
            record["status"] = "passed"
        checks.append(record)
        print(name + ": " + record["status"], flush=True)
    (reports / "native-variants.json").write_text(json.dumps(checks, indent=2)+"\n", encoding="utf-8")
    if any(check["status"] == "failed" for check in checks):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
