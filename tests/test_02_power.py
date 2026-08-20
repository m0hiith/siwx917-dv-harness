"""
test_02_power.py — Level 1 of the harness: how much electricity does the chip drink?

For each firmware mode (PS4 active, PS1 ULP sleep, BLE advertising):
  flash -> reset -> wait to settle -> record 2 s of current at 1000 samples/s
  ... repeat that whole cycle 5 times (5 INDEPENDENT runs, not 5 slices of one run)
  -> mean, std, min, max of the per-run means
  -> save CSV of every run + one summary line
  -> PASS if mean < limit in config.yaml
At the end one bar chart with error bars is written to the results folder.
"""

from __future__ import annotations

import csv
import json
import time

import pytest

from dvharness.stats import summarize

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
    summary_path = results_dir / "power_summary.json"
    summary = json.loads(summary_path.read_text()) if summary_path.exists() else {}
    summary[mode] = overall.as_dict()
    summary_path.write_text(json.dumps(summary, indent=2))

    # shows up in the JUnit XML / pytest report
    record_property("mean_mA", overall.mean)
    record_property("std_mA", overall.std)
    print(f"\n[{mode}] {overall.pretty(' mA')}")

    limit = pw["limits_mA"][mode]
    assert overall.mean < limit, (
        f"{mode}: mean current {overall.mean:.4f} mA exceeds limit {limit} mA"
    )


def test_99_make_plot(results_dir, cfg, practice_mode):
    """Runs last: turn power_summary.json into a bar chart with error bars."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    summary = json.loads((results_dir / "power_summary.json").read_text())
    modes = list(summary)
    means = [summary[m]["mean"] for m in modes]
    stds = [summary[m]["std"] for m in modes]
    is_fake = practice_mode

    fig, ax = plt.subplots(figsize=(6, 4))
    ax.bar(modes, means, yerr=stds, capsize=6)
    ax.set_yscale("log")
    ax.set_ylabel("Average current (mA, log scale)")
    ax.set_title("SiWx917 current by mode — mean ± std over runs"
                 + ("\n(FAKE BOARD — practice data, not a measurement)" if is_fake else ""))
    for i, (m, s) in enumerate(zip(means, stds)):
        ax.text(i, m, f"{m*1000:.1f} µA" if m < 1 else f"{m:.2f} mA",
                ha="center", va="bottom", fontsize=9)
    fig.tight_layout()
    out = results_dir / "power_by_mode.png"
    fig.savefig(out, dpi=150)
    assert out.exists()
