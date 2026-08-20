"""
test_03_manifest.py — does every results folder carry its own paper trail?

PLAIN ENGLISH
-------------
The manifest is what lets someone re-check a result months later: which
firmware, which Commander, which commit, which machine, when. These tests
prove the file is actually written and that the fields inside it mean what
they claim -- especially the "was the tree dirty" one, which is the field a
reviewer leans on hardest.
"""

from __future__ import annotations

import hashlib
import json

from dvharness.manifest import build, parse_porcelain, sha256_file


def test_manifest_written_at_session_start(session_manifest, results_dir):
    """The opening write must land before any test runs, so a crash still logs."""
    assert session_manifest == results_dir / "manifest.json"
    assert session_manifest.exists(), "no manifest.json in the results folder"

    m = json.loads(session_manifest.read_text())
    for key in ("schema_version", "session", "host", "git",
                "commander", "config_snapshot", "firmware_flashed"):
        assert key in m, f"manifest is missing {key!r}"
    assert m["session"]["started_utc"], "no start timestamp"


def test_manifest_records_the_config_actually_used(session_manifest, cfg):
    """The snapshot must be the config as read, not a re-read from disk."""
    m = json.loads(session_manifest.read_text())
    assert m["config_snapshot"] == cfg
    assert m["commander"]["configured"] == cfg["commander"]


def test_manifest_names_this_commit(session_manifest):
    m = json.loads(session_manifest.read_text())
    git = m["git"]
    if not git.get("available"):
        return                      # running from a tarball, not a clone
    assert len(git["commit"]) == 40, f"not a full sha: {git['commit']}"
    assert isinstance(git["dirty"], bool)


def test_sha256_matches_the_file_on_disk(tmp_path):
    p = tmp_path / "image.rps"
    p.write_bytes(b"some firmware bytes")
    got = sha256_file(p)
    assert got["exists"] is True
    assert got["bytes"] == len(b"some firmware bytes")
    assert got["sha256"] == hashlib.sha256(b"some firmware bytes").hexdigest()


def test_sha256_reports_a_missing_file_instead_of_inventing_one(tmp_path):
    got = sha256_file(tmp_path / "never_built.rps")
    assert got["exists"] is False
    assert "sha256" not in got


def test_porcelain_parsing_keeps_the_whole_path():
    """Regression: a .strip() on git output used to eat the leading space of
    the first ' M path' line, silently truncating it to 'vharness/device.py'."""
    status = " M dvharness/device.py\n?? TODO.md\nA  staged.py\nR  old.py -> new.py"
    assert parse_porcelain(status) == [
        "TODO.md", "dvharness/device.py", "new.py", "staged.py",
    ]
    assert parse_porcelain("") == []
    assert parse_porcelain(None) == []


def test_open_manifest_is_marked_in_progress(cfg, dut):
    """A manifest with no end timestamp must say so, not look complete."""
    opening = build(root=".", cfg=cfg, device=dut, started_utc="2026-08-20T00:00:00+00:00")
    assert opening["session"]["ended_utc"] is None
    assert "in progress" in opening["session"]["note"]

    closing = build(root=".", cfg=cfg, device=dut,
                    started_utc="2026-08-20T00:00:00+00:00",
                    ended_utc="2026-08-20T00:01:00+00:00")
    assert closing["session"]["ended_utc"] == "2026-08-20T00:01:00+00:00"
    assert "note" not in closing["session"]
