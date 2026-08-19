"""
stats.py — the rule of the harness: NEVER report one number. Report the spread.

PLAIN ENGLISH
-------------
If you measure your height once you get one number.  If you measure it ten
times you get ten slightly different numbers — that's normal.  "mean" is the
usual value, "std" (standard deviation) is how much it wobbles.
A DV engineer writes "1.82 µA ± 0.05", never just "1.82 µA".
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass, asdict


@dataclass
class Summary:
    n: int
    mean: float
    std: float
    min: float
    max: float

    def as_dict(self) -> dict:
        return asdict(self)

    def pretty(self, unit: str = "") -> str:
        return (f"n={self.n}  mean={self.mean:.4f}{unit}  "
                f"std={self.std:.4f}{unit}  min={self.min:.4f}  max={self.max:.4f}")


def summarize(values: list[float]) -> Summary:
    if not values:
        raise ValueError("no values to summarize")
    std = statistics.stdev(values) if len(values) > 1 else 0.0
    return Summary(n=len(values), mean=statistics.mean(values), std=std,
                   min=min(values), max=max(values))
