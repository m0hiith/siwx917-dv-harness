"""
manifest.py — the paper trail that makes a results folder re-checkable.

PLAIN ENGLISH
-------------
Six months from now someone finds results/2026-08-20_21-05-11/ and asks the
only question that matters: "can I believe these numbers?"

A folder of CSVs cannot answer that.  It does not say which firmware was
flashed, which build of Commander drove the board, which commit of this
harness produced it, or whether the person running it had uncommitted edits
on their laptop at the time.  Without those, a result is an anecdote.

So every results folder gets a manifest.json recording, for that session:
the full config.yaml as it was actually read, a sha256 of every firmware
image that was flashed, the git commit (and whether the tree was dirty),
the Commander version string, the hostname, and the start and end times.

It is written TWICE: once when the session starts, so a crashed or killed
run still leaves a trail, and once at the end with the closing timestamp and
the firmware hashes.

Nothing in here is a measurement, so nothing in here is allowed to fail the
run.  If git or Commander cannot be reached, the field records WHY it is
missing rather than throwing.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import platform
import socket
import subprocess
import sys
from pathlib import Path

SCHEMA_VERSION = 1


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def _git(root: Path, *args: str) -> str | None:
    """Run a read-only git command, or return None if git will not answer."""
    try:
        proc = subprocess.run(
            ["git", "-C", str(root), *args],
            capture_output=True, text=True, timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    # rstrip only: `status --porcelain` encodes state in the FIRST TWO COLUMNS,
    # so a .strip() here would eat the leading space of " M path" and the
    # path-slicing below would then lose its first character.
    return proc.stdout.rstrip("\n")


def git_provenance(root: Path) -> dict:
    """Which commit produced this, and was the tree clean when it ran?

    `dirty` is the honest half: a result produced from an edited working tree
    is not reproducible from the commit alone, and the manifest should say so
    rather than quietly implying the commit is the whole story.
    """
    commit = _git(root, "rev-parse", "HEAD")
    if commit is None:
        return {"available": False, "reason": "not a git repo, or git unavailable"}
    status = _git(root, "status", "--porcelain")
    return {
        "available": True,
        "commit": commit,
        "branch": _git(root, "rev-parse", "--abbrev-ref", "HEAD"),
        "dirty": bool(status),
        "dirty_files": parse_porcelain(status),
    }


def parse_porcelain(status: str | None) -> list[str]:
    """Pull the paths out of `git status --porcelain` lines.

    Each line is two status columns, a space, then the path:
        " M dvharness/device.py"
        "?? TODO.md"
        "R  old.py -> new.py"
    """
    if not status:
        return []
    paths = []
    for line in status.splitlines():
        if len(line) <= 3:
            continue
        path = line[3:]
        if " -> " in path:          # rename: record where it landed
            path = path.split(" -> ", 1)[1]
        paths.append(path)
    return sorted(paths)


def sha256_file(path: Path) -> dict:
    """Hash one firmware image so a later run can prove it flashed the same bits."""
    p = Path(path)
    if not p.exists():
        return {"path": str(p), "exists": False}
    h = hashlib.sha256()
    with p.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return {
        "path": str(p),
        "exists": True,
        "bytes": p.stat().st_size,
        "sha256": h.hexdigest(),
    }


def host_info() -> dict:
    return {
        "hostname": socket.gethostname(),
        "platform": platform.platform(),
        "python": sys.version.split()[0],
    }


def commander_info(device, configured: str) -> dict:
    """Ask Commander its version; record the failure instead of raising."""
    info = {"configured": configured}
    try:
        info["version"] = device.commander_version()
    except Exception as exc:                      # provenance must never fail a run
        info["version"] = None
        info["version_error"] = f"{type(exc).__name__}: {exc}"
    return info


def build(
    *,
    root: Path,
    cfg: dict,
    device,
    started_utc: str,
    ended_utc: str | None = None,
    firmware_flashed: dict | None = None,
) -> dict:
    """Assemble the manifest dict. `ended_utc` is None on the opening write."""
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "session": {"started_utc": started_utc, "ended_utc": ended_utc},
        "host": host_info(),
        "git": git_provenance(root),
        "commander": commander_info(device, cfg.get("commander", "")),
        "config_snapshot": cfg,
        "firmware_flashed": {
            mode: sha256_file(path)
            for mode, path in sorted((firmware_flashed or {}).items())
        },
    }
    if ended_utc is None:
        manifest["session"]["note"] = "session in progress; rewritten on completion"
    return manifest


def write(path: Path, manifest: dict) -> Path:
    """Write manifest.json, creating the folder if needed."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2, sort_keys=False, default=str))
    return path
