"""
conftest.py — pytest "fixtures": things every test can ask for by name.

PLAIN ENGLISH
-------------
Instead of every test file re-reading config.yaml and re-creating a Device,
we do it once here.  A test just writes `def test_x(dut, results_dir):` and
pytest hands it a ready-made board object and a folder to save results in.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest
import yaml

from dvharness.device import Device

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def cfg() -> dict:
    with (ROOT / "config.yaml").open() as fh:
        return yaml.safe_load(fh)


@pytest.fixture(scope="session")
def dut(cfg) -> Device:
    """Device Under Test — the board we measure."""
    return Device(serial=cfg["boards"]["dut"]["serial"], commander=cfg["commander"])


@pytest.fixture(scope="session")
def results_dir() -> Path:
    """results/2026-08-19_14-05-33/  — one folder per run, never overwritten."""
    stamp = dt.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    d = ROOT / "results" / stamp
    d.mkdir(parents=True, exist_ok=True)
    return d
