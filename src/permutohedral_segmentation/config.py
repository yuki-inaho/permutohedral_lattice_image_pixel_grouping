"""Small immutable parameter objects; no global mutable configuration."""
from __future__ import annotations

from dataclasses import dataclass
import math
from numbers import Integral, Real
from typing import Literal

FeatureMode = Literal["xy", "rgb", "xyrgb"]


def _number(name: str, value: float, low: float, high: float) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise TypeError(f"{name} must be a real number.")
    result = float(value)
    if not math.isfinite(result) or not low <= result <= high:
        raise ValueError(f"{name} must be finite and within [{low}, {high}].")
    return result


@dataclass(frozen=True, slots=True)
class LatticeConfig:
    """Scales multiply pixel centers and 8-bit RGB values, not normalized RGB."""

    mode: FeatureMode = "xy"
    spatial_scale: float = 0.025
    color_scale: float = 0.01

    def __post_init__(self) -> None:
        if self.mode not in ("xy", "rgb", "xyrgb"):
            raise ValueError("mode must be 'xy', 'rgb' or 'xyrgb'.")
        for name in ("spatial_scale", "color_scale"):
            object.__setattr__(self, name, _number(name, getattr(self, name), 1e-12, 1e6))


@dataclass(frozen=True, slots=True)
class MergeConfig:
    """Explicit optional postprocessing; target cannot exceed initial components."""

    target_regions: int
    compactness: float = 0.3
    color_sigma: float = 48.0

    def __post_init__(self) -> None:
        if isinstance(self.target_regions, bool) or not isinstance(self.target_regions, Integral):
            raise TypeError("target_regions must be an integer.")
        if not 1 <= self.target_regions <= 20_000_000:
            raise ValueError("target_regions must be within 1..20,000,000.")
        object.__setattr__(self, "target_regions", int(self.target_regions))
        object.__setattr__(self, "compactness", _number("compactness", self.compactness, 0, 1e6))
        object.__setattr__(self, "color_sigma", _number("color_sigma", self.color_sigma, 1e-6, 1e6))
