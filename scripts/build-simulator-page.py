#!/usr/bin/env python3
"""The simulator as a static site, for GitHub Pages.

simulator.py needs a Python server, which Pages does not have, so the site runs
the same Python in the browser instead: simulator.html as the page, with
simulator-browser.js in front of it starting Pyodide, and the device's own code
in a zip for Pyodide to unpack. Nothing is rewritten for the browser - the page
and the Python are the files the local simulator serves.

    ./scripts/build-simulator-page.py           # writes _site/
    python3 -m http.server -d _site             # to look at it before pushing

Only tracked files go in the zip, so a stray __pycache__ or a local experiment
in nd_timer cannot end up on the public page.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRIPTS = REPO / "scripts"

# What the simulator imports, and the fonts the panel is drawn with.
DEVICE_CODE = ("main.py", "nd_timer/", "assets/fonts/", "scripts/simulator.py", "scripts/simulator.html")

# The bridge has to be in place before the page's own script reads it.
PAGE_SCRIPT = "<script>\n"
BRIDGE = '<script src="simulator-browser.js"></script>\n'


def tracked(prefixes: tuple[str, ...]) -> list[str]:
    listed = subprocess.run(
        ["git", "ls-files", "--", *prefixes], cwd=REPO, check=True, capture_output=True, text=True
    )
    return listed.stdout.split()


def page() -> str:
    html = (SCRIPTS / "simulator.html").read_text()
    if html.count(PAGE_SCRIPT) != 1:
        raise SystemExit("simulator.html no longer has exactly one inline <script>; update build-simulator-page.py")
    return html.replace(PAGE_SCRIPT, BRIDGE + PAGE_SCRIPT)


def build(site: Path) -> None:
    shutil.rmtree(site, ignore_errors=True)
    site.mkdir(parents=True)
    (site / "index.html").write_text(page())
    shutil.copy(SCRIPTS / "simulator-browser.js", site)
    with zipfile.ZipFile(site / "device.zip", "w", zipfile.ZIP_DEFLATED) as archive:
        for name in tracked(DEVICE_CODE):
            archive.write(REPO / name, name)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("site", nargs="?", type=Path, default=REPO / "_site")
    arguments = parser.parse_args()
    build(arguments.site)
    print(f"built {arguments.site}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
