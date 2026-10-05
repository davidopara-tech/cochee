"""Shared helpers for advisor scoring."""


def min_max(values: list[float]) -> tuple[float, float]:
    """Returns (min, max). Handles the case where all values are equal."""
    lo, hi = min(values), max(values)
    if hi == lo:
        return lo, lo + 1.0
    return lo, hi


def scale(value: float, lo: float, hi: float) -> float:
    """Scales a value into [0, 1] using min-max. Clamped."""
    scaled = (value - lo) / (hi - lo)
    return max(0.0, min(1.0, scaled))


def weighted_score(features: dict[str, float], weights: dict[str, float]) -> float:
    """Weighted average. Keys must match between features and weights."""
    return sum(features[k] * weights[k] for k in weights)