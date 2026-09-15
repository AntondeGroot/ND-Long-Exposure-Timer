"""Bridge to the render script, whose filename is not importable as a module."""

import importlib.util
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "render-screens.py"
_spec = importlib.util.spec_from_file_location("render_screens", _SCRIPT)
_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_module)

CASES = _module.CASES
render = _module.render
