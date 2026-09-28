"""Verify the SHA-256 manifest of an extracted source bundle using only stdlib."""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path, PurePosixPath
import re
from _project import ROOT


def file_digest(path: Path) -> str:
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def verify(root: Path) -> int:
    root = root.resolve()
    count = 0
    seen: set[str] = set()
    for line in (root / "MANIFEST.sha256").read_text(encoding="utf-8").splitlines():
        digest, separator, name = line.partition("  ")
        relative = PurePosixPath(name)
        if not separator or not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise ValueError("Malformed manifest entry.")
        if not name or relative.is_absolute() or ".." in relative.parts or "\\" in name:
            raise ValueError("Unsafe manifest path.")
        if name in seen:
            raise ValueError("Duplicate manifest path: " + name)
        seen.add(name)
        path = root.joinpath(*relative.parts)
        if path.is_symlink() or not path.resolve().is_relative_to(root):
            raise ValueError("Symbolic links/out-of-tree paths are not allowed: " + name)
        if file_digest(path) != digest:
            raise ValueError("SHA-256 mismatch: " + name)
        count += 1
    if not count:
        raise ValueError("Empty manifest.")
    return count


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", type=Path, default=ROOT)
    args = parser.parse_args()
    print(f"Verified {verify(args.root)} file digests. Additional local files are not checked.")


if __name__ == "__main__":
    main()
