"""
firmware.py — the rule that stops the harness inventing a firmware image.

PLAIN ENGLISH
-------------
The tests need a firmware file to flash.  When you are practising with the
pretend board (tools/fake_commander.py) the CONTENTS never matter, so if the
file is missing it is convenient to drop a stub there and carry on.

On a real kit that convenience is dangerous.  Writing a few bytes of the word
"placeholder" into a .rps and flashing it means pushing a fabricated image
into a real chip: the bootloader rejects it or, worse, you brick the part and
then spend an afternoon wondering why the numbers look wrong.

So the stub is allowed ONLY when the configured commander is clearly the
bundled fake one.  Anything else counts as real hardware and we refuse, loudly,
naming the file we expected to find.

The check fails CLOSED on purpose: if we cannot prove the commander is the
fake, we treat it as real.
"""

from __future__ import annotations

from pathlib import Path

# What we write into a stub image in practice mode.  Never reaches real silicon.
PLACEHOLDER_BYTES = b"placeholder"

# The only commander string we accept as "not real hardware".
_FAKE_MARKER = "fake_commander"


def is_practice_mode(commander: str) -> bool:
    """True only when config.yaml points at the bundled fake commander.

    Deliberately narrow.  "commander", "/opt/silabs/commander" and a
    hand-rolled "python3 tools/my_stub.py" all read as REAL, because being
    wrong in that direction only costs an error message, while being wrong
    the other way costs a flashed chip.
    """
    return _FAKE_MARKER in str(commander).lower()


def resolve_firmware(cfg: dict, mode: str) -> Path:
    """Return the .rps path for `mode`, creating a stub only in practice mode.

    Raises KeyError if the mode is not in config.yaml, and FileNotFoundError
    (naming the missing path) if the image is absent and the commander is real.
    """
    try:
        path = Path(cfg["firmware"][mode])
    except KeyError as exc:
        known = ", ".join(sorted(cfg.get("firmware", {}))) or "(none)"
        raise KeyError(
            f"config.yaml has no firmware entry for mode {mode!r}. Known modes: {known}"
        ) from exc

    if path.exists():
        return path

    commander = cfg.get("commander", "")
    if not is_practice_mode(commander):
        raise FileNotFoundError(
            f"Firmware image for mode {mode!r} is missing: {path}\n"
            f"config.yaml commander is {commander!r}, which is treated as REAL "
            f"hardware, so this harness will NOT invent an image to flash.\n"
            f"Build the application, convert it with `commander rps create`, and "
            f"put the resulting .rps at exactly that path."
        )

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(PLACEHOLDER_BYTES)
    return path
