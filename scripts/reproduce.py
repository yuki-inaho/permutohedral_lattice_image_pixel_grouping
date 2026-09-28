"""Run the configured experiments using the public API, and compare golden labels."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import tomllib
from _project import ROOT, activate_test_bridge


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "experiments.toml")
    parser.add_argument("--output", type=Path, default=ROOT / "results")
    parser.add_argument("--offline-native", action="store_true")
    args = parser.parse_args()
    if args.offline_native:
        activate_test_bridge()
    import numpy as np
    from permutohedral_segmentation import LatticeConfig, MergeConfig, segment, _native
    from permutohedral_segmentation.datasets import load_example
    from permutohedral_segmentation.io import save_result

    config = tomllib.loads(args.config.read_text(encoding="utf-8"))
    if config.get("schema_version") != 1:
        raise ValueError("Unsupported experiment configuration schema.")
    report = {
        "started_at_utc": datetime.now(timezone.utc).isoformat(),
        "backend": getattr(_native, "__test_backend__", "nanobind"),
        "experiments": [],
    }
    for name in config["images"]:
        image = load_example(name)
        for entry in config["experiments"]:
            tag = entry["name"]
            # Names become directory names. Reject traversal instead of normalizing it.
            if Path(tag).name != tag or tag in ("", ".", "..") or "/" in tag or "\\" in tag:
                raise ValueError(f"Invalid experiment name: {tag!r}")
            lattice = LatticeConfig(entry["mode"], entry["spatial_scale"], entry["color_scale"])
            merge = None if "target_regions" not in entry else MergeConfig(
                entry["target_regions"], entry.get("compactness", 0.3), entry.get("color_sigma", 48)
            )
            result = segment(image, lattice=lattice, merge=merge)
            experiment_id = f"{name}_{tag}"
            destination = save_result(args.output / experiment_id, image, result)
            golden = ROOT / "reference" / "golden" / f"{experiment_id}.npz"
            matches = None
            if golden.is_file():
                with np.load(golden, allow_pickle=False) as archive:
                    matches = bool(np.array_equal(archive["labels"], result.labels))
                if not matches:
                    raise RuntimeError(f"Regression mismatch: {experiment_id}")
            report["experiments"].append({
                "id": experiment_id, "golden_labels_exact": matches,
                "output": destination.name, **result.to_metadata(),
            })
            print(f"{experiment_id}: {result.simplex_count} -> {result.region_count}; exact={matches}")
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "manifest.json").write_text(json.dumps(report, indent=2)+"\n", encoding="utf-8")


if __name__ == "__main__":
    main()
