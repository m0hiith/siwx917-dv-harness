"""
device.py  —  the "remote control" for one Silicon Labs SiWx917 board.

PLAIN ENGLISH
-------------
Silicon Labs gives you a command-line tool called Simplicity Commander.
You type things like:

    commander rps load app.rps --serialno 440123456
    commander device reset --serialno 440123456
    commander aem measure --windowlength 100 --serialno 440123456

and it talks to the board over USB.  The --serialno is the board's NAME TAG
(the J-Link serial number printed on the kit) so Commander knows WHICH board
you mean when two are plugged in.

This file is a robot that types those commands for you and READS the answer
back into Python numbers, so a test can say:

    dut.flash("firmware/ps1_sleep.rps")
    dut.reset()
    amps = dut.measure_current(window_ms=100)["current_mA"]

Nothing here is clever.  It is deliberately boring, because boring code is
what you want under a measurement.
"""

from __future__ import annotations

import csv
import re
import shlex
import subprocess
from pathlib import Path
from dataclasses import dataclass


class CommanderError(RuntimeError):
    """Raised when Commander exits with an error or does not print DONE."""


@dataclass
class Device:
    """One board, identified by its J-Link serial number.

    serial    : the J-Link serial printed on the kit, e.g. "440123456"
    commander : how to launch Commander.  Normally just "commander" (on PATH).
                For practice without hardware: "python3 tools/fake_commander.py"
    timeout_s : give up if a single command hangs longer than this
    """

    serial: str
    commander: str = "commander"
    timeout_s: int = 120

    # ------------------------------------------------------------------ #
    # The one low-level function every other method uses.
    # ------------------------------------------------------------------ #
    def _run(self, *args: str, expect_done: bool = True) -> str:
        """Run `commander <args> --serialno <serial>` and return its stdout.

        Commander prints the word DONE on success.  If it is missing, or the
        exit code is non-zero, we raise CommanderError with the full output so
        the failure is visible in the test report instead of silently passing.
        """
        cmd = shlex.split(self.commander) + list(args) + ["--serialno", self.serial]
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=self.timeout_s
        )
        out = proc.stdout + proc.stderr
        if proc.returncode != 0 or (expect_done and "DONE" not in out):
            raise CommanderError(
                f"Command failed: {' '.join(cmd)}\n--- output ---\n{out}"
            )
        return out

    # ------------------------------------------------------------------ #
    # Things you can ask the board to do.
    # ------------------------------------------------------------------ #
    def probe(self) -> dict[str, str]:
        """Ask the kit who it is.  Returns a dict of 'Key': 'Value' lines.

        The interesting key is 'AEM Supported' — '1' means this kit has the
        built-in current meter and measure_current() will work.
        """
        out = self._run("adapter", "probe")
        info: dict[str, str] = {}
        for line in out.splitlines():
            # lines look like:   "AEM Supported : 1"
            m = re.match(r"^\s*([A-Za-z][A-Za-z0-9 .\-/]*?)\s*:\s*(.+?)\s*$", line)
            if m:
                info[m.group(1)] = m.group(2)
        return info

    def has_aem(self) -> bool:
        return self.probe().get("AEM Supported", "0").strip() == "1"

    def flash(self, firmware: str | Path) -> None:
        """Put a new program into the chip.  Wraps `commander rps load`.

        SiWx917 parts boot from an RPS image (.rps), not a raw .s37/.hex —
        the bootloader reads an RPS header to check the image before running
        it.  Build the app in Studio/VS Code, convert it with
        `commander rps create`, and point config.yaml at the .rps.
        """
        firmware = Path(firmware)
        if not firmware.exists():
            raise FileNotFoundError(firmware)
        self._run("rps", "load", str(firmware))

    def reset(self) -> None:
        """Switch the chip off and on again (hardware reset via the debugger)."""
        self._run("device", "reset")

    def measure_current(self, window_ms: int = 100) -> dict[str, float]:
        """One averaged reading.  Wraps `commander aem measure`.

        Commander prints:
            Averaged over 200 ms:
            Current [mA]: 5.359
            Power [mW]  : 17.763
            Voltage [V] : 3.314
            DONE
        We pull the three numbers out with a regex and return them as floats.
        """
        out = self._run("aem", "measure", "--windowlength", str(window_ms))
        reading: dict[str, float] = {}
        for key, label in (
            ("current_mA", r"Current \[mA\]"),
            ("power_mW", r"Power \[mW\]"),
            ("voltage_V", r"Voltage \[V\]"),
        ):
            m = re.search(label + r"\s*:\s*([-+0-9.eE]+)", out)
            if not m:
                raise CommanderError(f"Could not parse {key} from:\n{out}")
            reading[key] = float(m.group(1))
        return reading

    def dump_current(
        self, duration_s: float, datarate_hz: int, outfile: str | Path
    ) -> list[float]:
        """Many raw readings over time.  Wraps `commander aem dump`.

        This is the better tool for statistics: instead of ONE averaged number
        you get thousands of samples (timestamp_us, current_mA, voltage_V) in a
        CSV, so you can compute mean, standard deviation, min and max yourself.
        Returns the list of current samples in mA.
        """
        outfile = Path(outfile)
        outfile.parent.mkdir(parents=True, exist_ok=True)
        self._run(
            "aem", "dump",
            "--outfile", str(outfile),
            "--duration", str(duration_s),
            "--datarate", str(datarate_hz),
        )
        samples: list[float] = []
        with outfile.open() as fh:
            for row in csv.reader(fh):
                # skip headers / blank lines; keep rows whose 2nd column is a number
                if len(row) < 2:
                    continue
                try:
                    samples.append(float(row[1]))
                except ValueError:
                    continue
        if not samples:
            raise CommanderError(f"aem dump produced no samples in {outfile}")
        return samples
