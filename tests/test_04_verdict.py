"""
test_04_verdict.py — does the harness refuse to over-claim?

PLAIN ENGLISH
-------------
The point of these tests is the INCONCLUSIVE case. A run against the fake
board always lands comfortably inside its limits, so nothing in the normal
suite ever exercises the branch that matters: what happens when a reading
sits so close to the limit that the meter cannot tell which side it is on.
These build that situation on purpose, with numbers instead of hardware.
"""

from __future__ import annotations

import math

import pytest

from dvharness.stats import (FAIL, INCONCLUSIVE, PASS, Summary, judge,
                             summarize)


def _summary(mean: float, sem: float) -> Summary:
    """A Summary with the mean and sem we want to reason about."""
    n = 5
    std = sem * math.sqrt(n)
    return Summary(n=n, mean=mean, std=std, sem=sem, min=mean, max=mean)


# --------------------------------------------------------------------- #
# standard error of the mean
# --------------------------------------------------------------------- #
def test_sem_is_std_over_sqrt_n():
    s = summarize([1.0, 2.0, 3.0, 4.0, 5.0])
    assert s.n == 5
    assert s.sem == pytest.approx(s.std / math.sqrt(5))
    assert s.sem < s.std, "sem must be tighter than std for n > 1"


def test_single_value_has_no_spread():
    s = summarize([2.5])
    assert s.std == 0.0 and s.sem == 0.0


def test_summarize_still_rejects_nothing_to_summarize():
    with pytest.raises(ValueError):
        summarize([])


# --------------------------------------------------------------------- #
# the three verdicts
# --------------------------------------------------------------------- #
def test_comfortably_below_the_limit_passes():
    v = judge(_summary(mean=1.0, sem=0.001), limit=5.0, instrument_floor=0.1)
    assert v.verdict == PASS and v.ok


def test_comfortably_above_the_limit_fails():
    v = judge(_summary(mean=9.0, sem=0.001), limit=5.0, instrument_floor=0.1)
    assert v.verdict == FAIL and not v.ok


def test_sitting_on_the_limit_is_inconclusive_not_a_pass():
    """A hair under the limit, but well inside what the meter can resolve."""
    v = judge(_summary(mean=4.99, sem=0.001), limit=5.0, instrument_floor=0.1)
    assert v.verdict == INCONCLUSIVE
    assert not v.ok, "INCONCLUSIVE must never read as OK"
    assert "cannot tell pass from fail" in v.reason


def test_a_tiny_spread_cannot_buy_a_pass_the_meter_never_earned():
    """The simulator artifact, made into a test.

    A 1.8 uA sleep reading with a 0.004 uA spread looks precise enough to
    pass a 1.85 uA limit. The AEM resolves 1 uA, so that PASS would be
    reporting the meter repeating itself.
    """
    sim = _summary(mean=0.0018, sem=0.000004)      # what the fake board gives
    tight_limit = 0.00185

    assert judge(sim, limit=tight_limit, instrument_floor=0.0).verdict == PASS, (
        "with no instrument floor the tiny spread wins -- the old behaviour"
    )
    honest = judge(sim, limit=tight_limit, instrument_floor=0.001)
    assert honest.verdict == INCONCLUSIVE
    assert honest.uncertainty == 0.001
    assert honest.uncertainty_source == "instrument floor"


def test_uncertainty_is_the_larger_of_sem_and_floor():
    noisy = judge(_summary(mean=1.0, sem=0.5), limit=5.0, instrument_floor=0.001)
    assert noisy.uncertainty == 0.5
    assert noisy.uncertainty_source == "standard error of the mean"

    quiet = judge(_summary(mean=1.0, sem=0.0001), limit=5.0, instrument_floor=0.1)
    assert quiet.uncertainty == 0.1
    assert quiet.uncertainty_source == "instrument floor"


def test_verdict_explains_itself():
    v = judge(_summary(mean=1.0, sem=0.001), limit=5.0, instrument_floor=0.1)
    d = v.as_dict()
    for key in ("verdict", "mean", "limit", "uncertainty",
                "uncertainty_source", "instrument_floor", "reason"):
        assert key in d, f"verdict is missing {key!r}"
    assert f"{v.limit:.6g}" in v.reason, "the reason must quote the limit it used"
    assert f"{v.uncertainty:.3g}" in v.reason, "and the uncertainty it allowed"


# --------------------------------------------------------------------- #
# refusing to judge without knowing the meter
# --------------------------------------------------------------------- #
def test_refuses_to_judge_without_an_instrument_floor():
    with pytest.raises(ValueError, match="instrument_floor_mA"):
        judge(_summary(mean=1.0, sem=0.001), limit=5.0, instrument_floor=None)


def test_rejects_a_negative_floor():
    with pytest.raises(ValueError, match="negative"):
        judge(_summary(mean=1.0, sem=0.001), limit=5.0, instrument_floor=-1.0)


# --------------------------------------------------------------------- #
# config must actually carry a floor for every mode it sets a limit on
# --------------------------------------------------------------------- #
def test_every_limited_mode_has_an_instrument_floor(cfg):
    pw = cfg["power"]
    missing = set(pw["limits_mA"]) - set(pw.get("instrument_floor_mA", {}))
    assert not missing, f"modes with a limit but no instrument floor: {sorted(missing)}"
