"""
test_01_smoke.py — "is anyone home?"

Before measuring anything, prove the plumbing works:
  1. the kit answers to its serial number
  2. it tells us whether it has the AEM current meter
  3. we can flash a firmware image and reset the chip
"""

import pytest

from dvharness.firmware import is_practice_mode, resolve_firmware


def test_kit_answers(dut):
    info = dut.probe()
    assert "J-Link Serial" in info, f"probe returned nothing useful: {info}"
    assert info["J-Link Serial"].strip() == dut.serial


def test_kit_has_current_meter(dut):
    # If this fails on your kit, power tests need an external meter (e.g. PPK2)
    assert dut.has_aem(), "This kit has no AEM — see README 'no AEM' section"


def test_flash_and_reset(dut, firmware):
    fw = firmware("ps4_active")
    dut.flash(fw)
    dut.reset()


def test_refuses_to_fabricate_firmware_for_real_hardware(tmp_path):
    """The guard that matters: a missing image on a REAL kit must raise.

    Without this, a missing .rps silently became b"placeholder" and got
    flashed into the chip.
    """
    missing = tmp_path / "not_built_yet.rps"
    cfg = {"commander": "commander", "firmware": {"ps4_active": str(missing)}}

    with pytest.raises(FileNotFoundError) as exc:
        resolve_firmware(cfg, "ps4_active")

    assert str(missing) in str(exc.value), "error must name the missing path"
    assert not missing.exists(), "must NOT have fabricated an image"


def test_practice_mode_detection_fails_closed():
    """Only the bundled fake commander counts as practice mode."""
    assert is_practice_mode("python3 tools/fake_commander.py")
    for real in ("commander", "/opt/silabs/commander", "python3 tools/my_stub.py"):
        assert not is_practice_mode(real), f"{real!r} must be treated as real hardware"
