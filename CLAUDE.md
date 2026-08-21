# SiWx917 DV Harness
Purpose: automated design-validation style measurements on Silicon Labs SiWx917 kits
(power, radio link, reliability), runnable unattended, reporting mean ± std.

Hardware on the bench: one SiWx917 Wi-Fi 6 + BLE Dev Kit, DK2605A (board
BRD2605A, chip SiWG917M111MGTBA). `commander adapter probe` reports
"AEM Supported: False" — this kit has NO on-board current meter, so power
measurement is impossible here, not merely inaccurate. Power numbers need a
BRD4338A radio board on a BRD4002A Wireless Pro Kit mainboard (kit
SiWx917-PK6031A; that mainboard carries the AEM) or an external meter such as
a Nordic PPK2 wired into Device.dump_current(). Board "dut" = device under
test, board "peer" = second radio for future link tests (in config.yaml, not
connected). Serial numbers and the Simplicity Commander path live in
config.yaml. Firmware images are RPS (.rps) and Commander loads them with
`rps load` — SiWx917 does not boot a raw .s37/.hex.
Practice mode: config.yaml commander = "python3 tools/fake_commander.py".

Rules for any code you write here:
- Read serial numbers, firmware paths and limits from config.yaml. Never hardcode.
- Every measurement reports mean and std over N independent runs (flash->reset->measure each time).
- Every test must run unattended; no input(), no manual steps.
- Save raw data to the results/<timestamp>/ folder the fixture provides.
- Parse tool output with explicit regexes and raise a clear error with the full output if parsing fails.
- Keep Commander calls inside dvharness/device.py; tests call Device methods only.
- For each new module add a short PLAIN ENGLISH docstring a teammate can read.
