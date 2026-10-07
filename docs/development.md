# Development

The exposure maths, the screens and the camera commands are all testable without any
hardware attached - which matters, because the Pi's only USB port cannot carry both the
camera and an ssh session.

**Use Python 3.13** - the version in `.python-version`, and the one the Pi runs. It is
not a preference: the device gets Pillow, numpy and lgpio from apt, compiled against
3.13, and moving it means building CPython on an ARMv6. Code that needs a different
version passes here and fails on the device, where the symptom is a blank panel rather
than a stack trace. The test suite refuses to run on anything else, with an override for
when you mean it.

```bash
brew install python@3.13                                  # once
$(brew --prefix python@3.13)/bin/python3.13 -m venv .venv
./.venv/bin/pip install -r requirements-dev.txt

./.venv/bin/python -m pytest -q --cov   # tests, golden images and the coverage floor
./.venv/bin/ruff check .                # the same lint CI runs, zero tolerance
./scripts/render-screens.py             # after a deliberate UI change, then commit the images
```

Both gates are what CI enforces, so a green run here is a green run there. The settings
live in `pyproject.toml` rather than in the workflow for exactly that reason.

### Trying it without the hardware

The whole device runs on a laptop, with the panel in a browser and the camera faked:

```bash
./scripts/simulator.py                # then open http://localhost:8000
```

Or with nothing installed at all, at
[antondegroot.github.io/ND-Long-Exposure-Timer](https://antondegroot.github.io/ND-Long-Exposure-Timer/):
the same page, with the same Python running in the browser through Pyodide. It is
rebuilt from `main` on every push by `.github/workflows/pages.yml`.
