"""Checks that run before a single test is collected.

The suite is fast and the gates are strict, which is only worth anything if the
interpreter running them is the one the code ships to.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

# Set this to run the suite on a different Python on purpose - checking whether
# the code is ready for a version the Pi has not moved to yet, say. It has to be
# a decision: the drift this guards against went unnoticed for months precisely
# because nothing objected.
OVERRIDE = "ND_TIMER_ALLOW_PYTHON_MISMATCH"

# One declaration, read by everything. actions/setup-python reads this file
# natively, so CI and this check cannot disagree, and pyenv and uv honour it too.
VERSION_FILE = Path(__file__).resolve().parent.parent / ".python-version"


def _required_version() -> tuple[int, int] | None:
    """The major and minor the project ships on, or None if unreadable."""
    try:
        parts = VERSION_FILE.read_text().strip().split(".")
        return int(parts[0]), int(parts[1])
    except (OSError, IndexError, ValueError):
        return None


def _check_python_version() -> None:
    if os.environ.get(OVERRIDE):
        return

    required = _required_version()
    if required is None:
        return  # Nothing to compare against; not a reason to block the suite.

    running = sys.version_info[:2]
    if running == required:
        return

    want = ".".join(str(part) for part in required)
    have = ".".join(str(part) for part in running)
    raise pytest.UsageError(
        f"this project runs on Python {want}; you are on {have}.\n"
        f"\n"
        f"The Raspberry Pi runs {want} and cannot practically be moved - its "
        f"Pillow, numpy and lgpio come from apt, compiled against it. Code that "
        f"only runs on another version passes here and fails on the device, "
        f"where the symptom is a blank panel rather than a stack trace.\n"
        f"\n"
        f"    brew install python@{want}\n"
        f"    rm -rf .venv && $(brew --prefix python@{want})/bin/python{want} -m venv .venv\n"
        f"    ./.venv/bin/pip install -r requirements-dev.txt\n"
        f"\n"
        f"To run on {have} deliberately: {OVERRIDE}=1 pytest"
    )


def pytest_configure(config: pytest.Config) -> None:
    """Run the check through pytest's own hook.

    Calling it at import time works, but pytest wraps whatever a conftest raises
    on import in an ImportError traceback - so the instruction that matters
    arrives buried under a stack. From the hook it prints on its own.
    """
    del config  # the hook's signature, not something we need
    _check_python_version()
