"""The committed soft latch schematic must still be what scripts/draw-soft-latch.py draws.

The circuit lives in that script; docs/soft-latch-circuit.svg is its output. A schematic
edited by hand, or a circuit changed without rerunning the script, shows up here rather
than as a board built from a stale picture.
"""

import importlib.util
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
_SCRIPT = REPO / "scripts" / "draw-soft-latch.py"
_spec = importlib.util.spec_from_file_location("draw_soft_latch", _SCRIPT)
_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_module)


def test_the_committed_schematic_is_what_the_script_draws():
    # A bool rather than `==` on the strings, so a failure says what to do instead of
    # dumping the whole SVG.
    matches = _module.OUTPUT.read_text() == _module.svg()
    assert matches, "docs/soft-latch-circuit.svg differs from the script - rerun scripts/draw-soft-latch.py"
