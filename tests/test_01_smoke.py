"""
test_01_smoke.py — "is anyone home?"

Before measuring anything, prove the plumbing works:
  1. the kit answers to its serial number
  2. it tells us whether it has the AEM current meter
  3. we can flash a firmware image and reset the chip
"""

from pathlib import Path


def test_kit_answers(dut):
    info = dut.probe()
    assert "J-Link Serial" in info, f"probe returned nothing useful: {info}"
    assert info["J-Link Serial"].strip() == dut.serial


def test_kit_has_current_meter(dut):
    # If this fails on your kit, power tests need an external meter (e.g. PPK2)
    assert dut.has_aem(), "This kit has no AEM — see README 'no AEM' section"


def test_flash_and_reset(dut, cfg):
    fw = Path(cfg["firmware"]["ps4_active"])
    fw.parent.mkdir(exist_ok=True)
    if not fw.exists():
        fw.write_bytes(b"placeholder")   # fake board doesn't care about contents
    dut.flash(fw)
    dut.reset()
