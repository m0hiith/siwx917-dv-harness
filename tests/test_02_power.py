"""
test_02_power.py — Level 1 of the harness: how much electricity does the chip drink?

For each firmware mode (PS4 active, PS1 ULP sleep, BLE advertising):
  flash -> reset -> wait to settle -> record 2 s of current at 1000 samples/s
  ... repeat that whole cycle 5 times (5 INDEPENDENT runs, not 5 slices of one run)
  -> mean, std, sem, min, max of the per-run means
  -> save CSV of every run + one summary line
  -> PASS / FAIL / INCONCLUSIVE against the limit in config.yaml, where the
     uncertainty is floored at what the AEM can actually resolve
At the end one bar chart with error bars is written to the results folder.
"""

from __future__ import annotations

import csv
import json
import time

import pytest

from dvharness.stats import INCONCLUSIVE, PASS, judge, summarize

MODES = ["ps4_active", "ps1_sleep", "ble_adv"]


@pytest.mark.parametrize("mode", MODES)
def test_current_in_mode(dut, cfg, results_dir, mode, record_property, firmware):
    pw = cfg["power"]
    # Refuses to invent an image unless we are on the fake board -- see
    # dvharness/firmware.py. Never flash a fabricated .rps into real silicon.
    fw = firmware(mode)

    run_means: list[float] = []
    rows: list[dict] = []

    for run in range(pw["repeats"]):
        dut.flash(fw)
        dut.reset()
        time.sleep(pw["settle_s"])
        raw_csv = results_dir / f"raw_{mode}_run{run}.csv"
        samples = dut.dump_current(pw["duration_s"], pw["datarate_hz"], raw_csv)
        s = summarize(samples)
        run_means.append(s.mean)
        rows.append({"mode": mode, "run": run, **s.as_dict()})

    overall = summarize(run_means)

    # ---- save everything (raw already on disk; now per-run table + summary) ----
    with (results_dir / f"power_{mode}.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=rows[0].keys())
        w.writeheader()
        w.writerows(rows)
    verdict = judge(
        overall,
        limit=pw["limits_mA"][mode],
        instrument_floor=pw["instrument_floor_mA"][mode],
    )

    summary_path = results_dir / "power_summary.json"
    summary = json.loads(summary_path.read_text()) if summary_path.exists() else {}
    summary[mode] = overall.as_dict()
    summary[mode]["verdict"] = verdict.as_dict()
    summary_path.write_text(json.dumps(summary, indent=2))

    # shows up in the JUnit XML / pytest report
    record_property("mean_mA", overall.mean)
    record_property("std_mA", overall.std)
    record_property("sem_mA", overall.sem)
    record_property("verdict", verdict.verdict)
    print(f"\n[{mode}] {overall.pretty(' mA')}")
    print(f"[{mode}] {verdict.verdict}: {verdict.reason}")

    if verdict.verdict == INCONCLUSIVE:
        raise AssertionError(
            f"{mode}: INCONCLUSIVE — {verdict.reason}.\n"
            f"This is not a failure of the chip, it is a failure of the "
            f"measurement to answer the question. Tighten the setup, take "
            f"more runs, or move the limit away from the meter's resolution "
            f"({verdict.instrument_floor} mA) before quoting a result."
        )
    assert verdict.verdict == PASS, f"{mode}: {verdict.reason}"


def test_99_make_plot(results_dir, cfg, practice_mode):
    """Runs last: turn power_summary.json into a bar chart with error bars."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    summary = json.loads((results_dir / "power_summary.json").read_text())
    modes = list(summary)
    means = [summary[m]["mean"] for m in modes]
    # Error bars show the uncertainty the VERDICT used -- the larger of the
    # standard error and what the AEM can resolve. Plotting the raw std here
    # would draw an invisible error bar on the 1.8 uA sleep reading and tell
    # the viewer the opposite of the truth.
    errs = [summary[m]["verdict"]["uncertainty"] for m in modes]
    verdicts = [summary[m]["verdict"]["verdict"] for m in modes]
    is_fake = practice_mode

    # On a log axis a bar cannot reach mean-err if that is <= 0, so keep the
    # lower whisker just inside the positive range.
    lower = [min(e, m * 0.999) for m, e in zip(means, errs)]

    fig, ax = plt.subplots(figsize=(6.5, 4.5))
    ax.bar(modes, means, yerr=[lower, errs], capsize=6)
    ax.set_yscale("log")
    ax.set_ylabel("Average current (mA, log scale)")
    ax.set_title("SiWx917 current by mode — mean ± measurement uncertainty"
                 "\n(uncertainty = max of standard error and AEM resolution)"
                 + ("\n(FAKE BOARD — practice data, not a measurement)" if is_fake else ""),
                 fontsize=10)
    for i, (m, e, v) in enumerate(zip(means, errs, verdicts)):
        label = f"{m*1000:.1f} µA" if m < 1 else f"{m:.2f} mA"
        ax.text(i, m + e, f"{label}\n{v}", ha="center", va="bottom", fontsize=9)
    ax.set_ylim(top=max(m + e for m, e in zip(means, errs)) * 6)
    fig.tight_layout()
    out = results_dir / "power_by_mode.png"
    fig.savefig(out, dpi=150)
    assert out.exists()
