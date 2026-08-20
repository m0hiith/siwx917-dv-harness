#!/usr/bin/env python3
"""
fake_commander.py — a CARDBOARD BOARD.

PLAIN ENGLISH
-------------
You can't always have the real kit with you (it's in the college lab).  This
script pretends to be Simplicity Commander driving a SiWx917 kit: it accepts
the same commands and prints the same shaped output, with made-up numbers.
That lets you write and test the Python harness on the bus, then swap in the
real `commander` on PATH when you are in the lab.  NOTHING here is a real
measurement.

It remembers what firmware was "flashed" to each serial number (in a small
file in /tmp) so that the pretend current depends on the pretend firmware,
which is what the real chip does too:
    *ps1*  -> a few microamps (PS1 ULP sleep, CPU off, RAM retained)
    *adv*  -> tens of microamps average (BLE advertising)
    *ps4*  -> a few milliamps (PS4 active, CPU running)

Note it only answers to `rps load`, not `flash`.  That is deliberate: the
SiWx917 bootloader accepts RPS images only, so a harness that still called
`commander flash foo.s37` would fail here exactly as it would on the bench.
"""

import json
import random
import sys
import time
from pathlib import Path

STATE_DIR = Path("/tmp/fake_siwx917")
STATE_DIR.mkdir(exist_ok=True)

# (mean mA, std mA) for each pretend firmware type — ILLUSTRATIVE ONLY
PROFILES = {
    "ps1": (0.0018, 0.00020),
    "adv": (0.0450, 0.00400),
    "ps4": (2.6000, 0.02000),
}


def state_file(serial: str) -> Path:
    return STATE_DIR / f"{serial}.json"


def load(serial: str) -> dict:
    p = state_file(serial)
    return json.loads(p.read_text()) if p.exists() else {"firmware": "ps4"}


def save(serial: str, st: dict) -> None:
    state_file(serial).write_text(json.dumps(st))


def profile_for(firmware_name: str):
    for key, prof in PROFILES.items():
        if key in firmware_name.lower():
            return prof
    return PROFILES["ps4"]


def main(argv):
    # pull out --serialno and the option values, keep positional words
    serial = "000000000"
    opts, words = {}, []
    i = 0
    while i < len(argv):
        a = argv[i]
        if a.startswith("--"):
            opts[a[2:]] = argv[i + 1] if i + 1 < len(argv) else ""
            i += 2
        else:
            words.append(a)
            i += 1
    serial = opts.get("serialno", serial)
    st = load(serial)

    if words[:2] == ["adapter", "probe"]:
        print("Kit Information:")
        print("=" * 39)
        print("Kit Name        : SiWx917 Wi-Fi 6 and Bluetooth LE Pro Kit (FAKE)")
        print("Kit Part Number : SiWx917-PK6031A")
        print("Radio Board     : BRD4338A")
        print(f"J-Link Serial   : {serial}")
        print("Debug Mode      : MCU")
        print("AEM Supported   : 1")
        print("VCOM Supported  : 1")
        print("DONE")
        return 0

    if words[:2] == ["rps", "load"]:
        fw = words[2] if len(words) > 2 else "unknown"
        st["firmware"] = Path(fw).name
        save(serial, st)
        print(f"Parsing RPS file {fw}...")
        print("RPS header OK, image type M4, 65536 bytes")
        print("Erasing flash...")
        print("Writing image to flash...")
        print("DONE")
        return 0

    if words[:2] == ["device", "reset"]:
        print("Resetting...")
        print("DONE")
        return 0

    mean, std = profile_for(st.get("firmware", "ps4"))

    if words[:2] == ["aem", "measure"]:
        w = int(opts.get("windowlength", "100"))
        time.sleep(w / 1000.0)
        cur = max(0.0, random.gauss(mean, std))
        v = 3.314
        print(f"Averaged over {w} ms:")
        print(f"Current [mA]: {cur:.4f}")
        print(f"Power [mW]  : {cur * v:.4f}")
        print(f"Voltage [V] : {v:.3f}")
        print("DONE")
        return 0

    if words[:2] == ["aem", "dump"]:
        out = Path(opts.get("outfile", "aem.csv"))
        dur = float(opts.get("duration", "1"))
        rate = int(opts.get("datarate", "1000"))
        n = int(dur * rate)
        t0 = int(time.time() * 1e6)
        with out.open("w") as fh:
            fh.write("timestamp_us,current_mA,voltage_V\n")
            for k in range(n):
                cur = max(0.0, random.gauss(mean, std))
                fh.write(f"{t0 + int(k * 1e6 / rate)},{cur:.5f},3.3140\n")
        print("Logging...")
        print(f"Closed file '{out}',")
        print(f"{n} measurements written to file.")
        print("DONE")
        return 0

    print(f"fake_commander: unknown command {words}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
