# SiWx917 DV Harness
Purpose: automated design-validation style measurements on Silicon Labs SiWx917 kits
(power, radio link, reliability), runnable unattended, reporting mean ± std.

Hardware: two Silicon Labs SiWx917 boards over USB — BRD4338A radio board on a
BRD4002A Wireless Pro Kit mainboard (kit SiWx917-PK6031A; the mainboard carries
the AEM). Board "dut" = device under test, board "peer" = second radio for link
tests. Serial numbers live in config.yaml. Firmware images are RPS (.rps) and
Commander loads them with `rps load` — SiWx917 does not boot a raw .s37/.hex.
Tools on PATH: commander (Simplicity Commander), python3.
Practice mode: config.yaml commander = "python3 tools/fake_commander.py".

Rules for any code you write here:
- Read serial numbers, firmware paths and limits from config.yaml. Never hardcode.
- Every measurement reports mean and std over N independent runs (flash->reset->measure each time).
- Every test must run unattended; no input(), no manual steps.
- Save raw data to the results/<timestamp>/ folder the fixture provides.
- Parse tool output with explicit regexes and raise a clear error with the full output if parsing fails.
- Keep Commander calls inside dvharness/device.py; tests call Device methods only.
- For each new module add a short PLAIN ENGLISH docstring a teammate can read.
