"""Create a deterministic source/results .tar.zst; exclude environments and binaries.

Requires Python >=3.11 and the zstd command-line program. No Python dependencies.
Tar timestamps/owners/modes and file order are normalized. Bitwise reproducibility
also requires identical input files and the same zstd version/options.
"""
from __future__ import annotations

import argparse
from io import BytesIO
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile
from _project import ROOT
from verify_manifest import file_digest

ROOT_FILES = {
    "README.md", "LICENSE", "THIRD_PARTY_NOTICES.md", "pyproject.toml", "uv.lock",
    ".python-version", ".gitignore", ".gitattributes", "CMakeLists.txt", "experiments.toml",
}
ROOT_DIRECTORIES = {".github", "cpp", "src", "tests", "scripts", "notebooks", "docs",
                    "LICENSES", "reference", "reports", "results"}
IGNORED_PARTS = {"__pycache__", ".ipynb_checkpoints", ".pytest_cache", ".ruff_cache", ".mypy_cache"}
EXCLUDED_SUFFIXES = {".pyc", ".pyo", ".so", ".pyd", ".dll", ".dylib", ".o", ".obj", ".a", ".lib", ".exe",
                     ".tar", ".zst", ".zip", ".ttf", ".otf", ".ttc", ".woff", ".woff2"}


def bundle_files(root: Path) -> list[Path]:
    selected = []
    for path in root.rglob("*"):
        relative = path.relative_to(root)
        if not (relative.parts[0] in ROOT_DIRECTORIES or relative.as_posix() in ROOT_FILES):
            continue
        if IGNORED_PARTS.intersection(relative.parts) or path.suffix.lower() in EXCLUDED_SUFFIXES:
            continue
        if path.is_symlink():
            raise ValueError("Symbolic links are not packaged: " + str(relative))
        if path.is_file():
            if "\n" in relative.as_posix() or "\r" in relative.as_posix() or "\\" in relative.as_posix():
                raise ValueError("Unsupported archive filename: " + str(relative))
            selected.append(path)
    return sorted(selected, key=lambda path: path.relative_to(root).as_posix())


def add_bytes(archive: tarfile.TarFile, name: str, data: bytes, epoch: int) -> None:
    info = tarfile.TarInfo(name)
    info.size = len(data)
    info.mtime = epoch
    info.mode = 0o644
    info.uid = info.gid = 0
    info.uname = info.gname = ""
    archive.addfile(info, BytesIO(data))


def package(output: Path, epoch: int) -> tuple[str, int]:
    zstd = shutil.which("zstd")
    if zstd is None:
        raise RuntimeError("zstd executable is required.")
    if output.suffixes[-2:] != [".tar", ".zst"]:
        raise ValueError("Output must end in .tar.zst.")
    selected = bundle_files(ROOT)
    manifest = "".join(f"{file_digest(path)}  {path.relative_to(ROOT).as_posix()}\n" for path in selected)
    manifest_bytes = manifest.encode("utf-8")
    (ROOT / "MANIFEST.sha256").write_bytes(manifest_bytes)
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="permutohedral-release-") as temporary:
        tar_path = Path(temporary) / "bundle.tar"
        with tarfile.open(tar_path, "w", format=tarfile.PAX_FORMAT) as archive:
            entries = [(path.relative_to(ROOT).as_posix(), path) for path in selected]
            entries.append(("MANIFEST.sha256", None))
            for name, path in sorted(entries):
                data = manifest_bytes if path is None else path.read_bytes()
                add_bytes(archive, "permutohedral-lab/"+name, data, epoch)
        compressed = Path(temporary) / "bundle.tar.zst"
        subprocess.run([zstd, "-q", "-19", "-T1", "--check", "-f", str(tar_path), "-o", str(compressed)], check=True)
        subprocess.run([zstd, "--test", str(compressed)], check=True)
        shutil.copyfile(compressed, output)
    digest = file_digest(output)
    output.with_name(output.name+".sha256").write_text(f"{digest}  {output.name}\n", encoding="utf-8")
    return digest, len(selected)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT.parent / "permutohedral-lab-0.2.0.tar.zst")
    parser.add_argument("--epoch", type=int, default=int(os.environ.get("SOURCE_DATE_EPOCH", "1790467200")))
    args = parser.parse_args()
    if args.epoch < 0:
        parser.error("--epoch must be nonnegative.")
    digest, count = package(args.output.resolve(), args.epoch)
    print(f"Packaged {count} files plus MANIFEST.sha256: {args.output}")
    print(f"SHA-256: {digest}")


if __name__ == "__main__":
    main()
