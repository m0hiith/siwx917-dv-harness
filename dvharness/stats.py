"""
stats.py — the rule of the harness: NEVER report one number. Report the spread,
and never claim more precision than the meter can actually deliver.

PLAIN ENGLISH
-------------
If you measure your height once you get one number.  If you measure it ten
times you get ten slightly different numbers — that's normal.  "mean" is the
usual value, "std" (standard deviation) is how much it wobbles.
A DV engineer writes "1.82 µA ± 0.05", never just "1.82 µA".

Two numbers describe the wobble and they answer different questions:
  std  — how much a SINGLE run bounces around.  Does not shrink with more runs.
  sem  — standard error of the mean, std / sqrt(n).  How well we know the
         AVERAGE.  Shrinks as you take more runs.  This is the one that
         belongs next to a pass/fail limit.

And the part that is easy to get wrong: neither of them knows anything about
the METER.  Take five readings of a 1.8 uA sleep current on a meter that
resolves 1 uA and they may agree to four decimal places — that agreement is
the meter repeating itself, not evidence the value is known that precisely.
So every verdict floors its uncertainty at the instrument's own resolution
(`instrument_floor_mA` in config.yaml), and when the limit falls inside that
band the answer is INCONCLUSIVE — not a lucky PASS.
"""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass, asdict

PASS = "PASS"
FAIL = "FAIL"
INCONCLUSIVE = "INCONCLUSIVE"


@dataclass
class Summary:
    n: int
    mean: float
    std: float
    sem: float
    min: float
    max: float

    def as_dict(self) -> dict:
        return asdict(self)

    def pretty(self, unit: str = "") -> str:
        return (f"n={self.n}  mean={self.mean:.4f}{unit}  "
                f"std={self.std:.4f}{unit}  sem={self.sem:.4f}{unit}  "
                f"min={self.min:.4f}  max={self.max:.4f}")


def summarize(values: list[float]) -> Summary:
    if not values:
        raise ValueError("no values to summarize")
    n = len(values)
    std = statistics.stdev(values) if n > 1 else 0.0
    return Summary(n=n, mean=statistics.mean(values), std=std,
                   sem=std / math.sqrt(n) if n > 1 else 0.0,
                   min=min(values), max=max(values))


@dataclass
class Verdict:
    """PASS / FAIL / INCONCLUSIVE, plus the arithmetic that produced it."""

    verdict: str
    mean: float
    limit: float
    uncertainty: float
    uncertainty_source: str
    instrument_floor: float
    reason: str

    def as_dict(self) -> dict:
        return asdict(self)

    @property
    def ok(self) -> bool:
        return self.verdict == PASS


def judge(summary: Summary, limit: float, instrument_floor: float) -> Verdict:
    """Compare a mean against a limit, honestly.

    The band is mean ± u, where u is the LARGER of the statistical error
    (sem) and what the meter can actually resolve (instrument_floor):

      limit above the band  -> PASS
      limit below the band  -> FAIL
      limit inside the band -> INCONCLUSIVE, because this measurement cannot
                               tell the two apart, and saying PASS here would
                               be reporting the meter's noise as a result.
    """
    if instrument_floor is None:
        raise ValueError(
            "no instrument_floor_mA configured for this mode; refusing to "
            "judge a limit without knowing what the meter can resolve"
        )
    if instrument_floor < 0:
        raise ValueError(f"instrument_floor_mA must not be negative: {instrument_floor}")

    uncertainty = max(summary.sem, instrument_floor)
    source = ("instrument floor" if instrument_floor >= summary.sem
              else "standard error of the mean")
    low, high = summary.mean - uncertainty, summary.mean + uncertainty

    if high < limit:
        verdict = PASS
        reason = (f"mean {summary.mean:.6g} mA + {uncertainty:.3g} mA "
                  f"({source}) is still below the {limit:.6g} mA limit")
    elif low > limit:
        verdict = FAIL
        reason = (f"mean {summary.mean:.6g} mA - {uncertainty:.3g} mA "
                  f"({source}) is still above the {limit:.6g} mA limit")
    else:
        verdict = INCONCLUSIVE
        reason = (f"the {limit:.6g} mA limit falls inside {summary.mean:.6g} "
                  f"± {uncertainty:.3g} mA ({source}), so this run cannot tell "
                  f"pass from fail")

    return Verdict(verdict=verdict, mean=summary.mean, limit=limit,
                   uncertainty=uncertainty, uncertainty_source=source,
                   instrument_floor=instrument_floor, reason=reason)
