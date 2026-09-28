"""A thin command-line adapter to the same API used by notebooks."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Sequence

from .api import segment
from .config import LatticeConfig, MergeConfig
from .datasets import load_example
from .io import load_image, save_result


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Permutohedral simplex image segmentation")
    inputs = parser.add_mutually_exclusive_group(required=True)
    inputs.add_argument("--input", type=Path, help="Input image path")
    inputs.add_argument("--example", choices=("peppers", "cow"), help="Bundled example")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--mode", choices=("xy", "rgb", "xyrgb"), default="xy")
    parser.add_argument("--spatial-scale", type=float, default=0.025)
    parser.add_argument("--color-scale", type=float, default=0.01)
    parser.add_argument("--target-regions", type=int, default=None)
    parser.add_argument("--compactness", type=float, default=0.3)
    parser.add_argument("--color-sigma", type=float, default=48)
    args = parser.parse_args(argv)
    try:
        lattice = LatticeConfig(args.mode, args.spatial_scale, args.color_scale)
        merge = None if args.target_regions is None else MergeConfig(
            args.target_regions, args.compactness, args.color_sigma
        )
        image = load_example(args.example) if args.example else load_image(args.input)
        result = segment(image, lattice=lattice, merge=merge)
        save_result(args.output, image, result)
        print(json.dumps(result.to_metadata(), indent=2))
    except (OSError, ValueError, TypeError, RuntimeError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    return 0
