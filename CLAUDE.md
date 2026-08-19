# EFR32 DV Harness
Purpose: automated design-validation style measurements on Silicon Labs EFR32 kits
(power, radio link, reliability), runnable unattended, reporting mean ± std.

Hardware: two Silicon Labs xG24 boards over USB. Board "dut" = device under test,
board "peer" = second radio for link tests. Serial numbers live in config.yaml.
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
