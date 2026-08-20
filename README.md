# SiWx917 DV Harness — Level 1 (device control + power)

## What this is, in one breath
A laptop is plugged into a Silicon Labs board by USB. This Python program
loads firmware, resets the chip, measures how much current it draws, repeats
that several times, and writes a report with averages, spread and a chart.
Nobody touches the board while it runs.

## Status — read this first

The numbers this repo produces right now come from a **simulated** Simplicity
Commander (`tools/fake_commander.py`), not from a board. Hardware access is
pending a college MOU, so the harness was built and validated against a fake
device that emits the same output format as the real tool. Everything under
`docs/sample-run/` is illustrative: it shows that the measurement flow, the
statistics, the limit checks and the reporting work end to end. It is **not a
measurement of any physical device** and no number here should be quoted as one.

Switching to real hardware is one line in `config.yaml` (`commander: "commander"`)
plus real serial numbers and real `.rps` images. No test code changes.

![Sample output — simulated](docs/sample-run/power_by_mode.png)

*One run against the fake device: PS4 active 2.600 mA, PS1 sleep 1.80 uA, BLE
advertising 45.0 uA, each a mean over five independent flash-reset-settle-measure
cycles. The error bars are the AEM's own resolution, not the simulator's spread
— which is the whole point. See [docs/sample-run/](docs/sample-run/).*

## Folder map
```
config.yaml                 <- your bench: serials, firmware paths, limits, meter resolution
dvharness/device.py         <- the "remote control" around Simplicity Commander
dvharness/stats.py          <- mean / std / sem, and the PASS/FAIL/INCONCLUSIVE rule
dvharness/firmware.py       <- refuses to invent a firmware image for real hardware
dvharness/manifest.py       <- the paper trail written into every results folder
tests/conftest.py           <- gives every test a ready-made board + results folder
tests/test_01_smoke.py      <- can we talk to the kit, flash it, reset it?
tests/test_02_power.py      <- Level 1: current in PS4 / PS1 / BLE-advertising
tests/test_03_manifest.py   <- is each results folder self-describing?
tests/test_04_verdict.py    <- the INCONCLUSIVE cases the fake board never produces
tools/fake_commander.py     <- a pretend board so you can practise without hardware
firmware/                   <- put your built .rps images here
results/<timestamp>/        <- raw CSVs, per-run table, summary JSON, chart, manifest, JUnit XML
```

## Run it with NO hardware (practice mode) — works right now
```
pip install -r requirements.txt
python3 -m pytest
```
`config.yaml` points `commander:` at `tools/fake_commander.py`, which prints the
same shaped output as the real tool with made-up numbers.

## Switch to the REAL board (in the lab)
1. Install Simplicity Studio 6 → it brings Simplicity Commander. Add the folder
   containing `commander` (or `commander.exe`) to your PATH. Use a recent build:
   older Commander versions do not understand SiWx917 RPS images.
2. Plug the kit in. Find its serial: `commander adapter probe` (or read the sticker).
3. Edit `config.yaml`:
   - `commander: "commander"`
   - `boards.dut.serial: "<your J-Link serial>"`
4. Build the three applications in Studio/VS Code against the WiSeConnect 3 SDK,
   convert each to an RPS image (`commander rps create`), and copy the `.rps`
   files to `firmware/` with the names in `config.yaml`. Starting points in the SDK:
   the `mcu_powerstate` demo covers both the PS4 active state and the PS1 ULP
   sleep state, and a Bluetooth LE advertising example covers the third mode.
   **A SiWx917 will not boot a raw `.s37`/`.hex`** — the bootloader checks an RPS
   header first, so the conversion step is not optional.
5. `python3 -m pytest` — same command, real numbers.

## If `adapter probe` says `AEM Supported : 0`
Your kit's on-board debugger has no current meter. On SiWx917 the AEM lives on
the BRD4002A Wireless Pro Kit mainboard, so a bare BRD4338A radio board on a
plain adapter will report `0`. Options: put the radio board on a BRD4002A WPK
(the SiWx917-PK6031A Pro Kit bundles both), or use an external meter such as a
Nordic PPK2 (has a Python API). Then replace `Device.dump_current()` with a
call to that meter; the tests don't change.

## Rules of the harness (these are what a DV reviewer looks for)
- Every number is mean ± spread over independent runs. Never one reading.
- Pass/fail limits live in config, not in code, and start loose until you have
  the datasheet open next to real data.
- Raw samples are always saved, so any summary can be re-checked later.
- A failing test prints WHICH mode, WHAT number, WHAT limit.
- Results folders are timestamped and never overwritten.
- Every results folder carries a `manifest.json`: the config as read, a sha256
  of each image flashed, the git commit and whether the tree was dirty, the
  Commander version, the host, and start/end timestamps.
- The harness will not invent a firmware image. A missing `.rps` is a stub only
  in practice mode; against real hardware it is an error naming the path.

## PASS / FAIL / INCONCLUSIVE
A limit check is only as good as the meter behind it. `config.yaml` carries
`instrument_floor_mA` per mode — the AEM's own resolution from UG573 (1 µA
below 250 µA, 0.1 mA above). Each verdict widens its uncertainty to the larger
of the standard error and that floor, then:

| | |
|---|---|
| limit above `mean ± u` | **PASS** |
| limit below `mean ± u` | **FAIL** |
| limit inside `mean ± u` | **INCONCLUSIVE** |

INCONCLUSIVE is not a soft pass — it fails the run. It says the measurement
cannot answer the question, which is a different problem from the part being
out of spec, and it needs a different fix: more runs, a tighter setup, or a
limit that is not sitting inside the meter's own error.

## Scope: one pillar, finished, on purpose

DV for a wireless part has three pillars — power, RF link quality, and update
reliability. This repo does **one** of them, end to end, and stops.

That was a choice, not a stopping point. The two remaining pillars are each
blocked on something I do not have, and building half of either against a
simulator would produce exactly the thing this README spends its first section
warning about: numbers that look like measurements and are not.

| Pillar | Status | Blocked on |
|---|---|---|
| 1. Power (`test_02_power.py`) | **Done** — this repo | — |
| 2. RF link quality (`test_05_per_sweep.py`) | Designed, not written | A second board — PER vs transmit power needs a transmitter *and* a receiver |
| 3. Update reliability (`test_06_ota_loop.py`) | Designed, not written | Hardware, plus overnight time — 100 OTA cycles with interrupted-update rollback is a soak test, not a demo |

The measurement flow generalises to both: same `Device` wrapper, same
`results/<timestamp>/` layout, same mean-and-spread reporting, same manifest.

## Known gaps, named on purpose

These are real, they are all reproducible, and none of them survives a
one-day budget. Naming them is cheaper than having them found:

- **No Commander retry logic.** `Device._run()` runs a command once. Real
  benches produce transient USB and J-Link failures, and the right fix is a
  bounded retry with backoff around `_run` — not `pytest-rerunfailures` around
  the test, which would also retry genuine measurement failures.
- **`subprocess.TimeoutExpired` escapes `_run` unwrapped.** Every other
  failure path raises `CommanderError` with the full output attached; a hung
  Commander raises the bare subprocess exception instead, so the one failure
  where you most want to see what the tool printed is the one where you don't.
- **`test_99_make_plot` breaks under `pytest -k`.** It reads the
  `power_summary.json` the power tests write, so selecting it alone
  (`pytest -k make_plot`) fails with `FileNotFoundError`. It is an implicit
  dependency between tests, which is a smell; the fix is to make it skip when
  the summary is absent, or to move plotting into a session-teardown fixture
  next to the manifest.
