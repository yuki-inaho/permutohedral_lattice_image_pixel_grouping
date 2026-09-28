"""Create/check uv.lock, then install all declared dependency groups."""
import shutil
import subprocess
from _project import ROOT


def main() -> None:
    uv = shutil.which("uv")
    if uv is None:
        raise SystemExit("uv is required. See docs/PORTABILITY.md for prerequisites.")
    lock = ROOT / "uv.lock"
    subprocess.run([uv, "lock", "--check"] if lock.exists() else [uv, "lock"], cwd=ROOT, check=True)
    subprocess.run([uv, "sync", "--locked", "--all-groups"], cwd=ROOT, check=True)
    print("Environment ready. Commit uv.lock together with pyproject.toml.")


if __name__ == "__main__":
    main()
