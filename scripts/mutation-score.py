#!/usr/bin/env python3
"""Fail when the mutation score drops below the floor in pyproject.toml.

Run after mutmut has done its work:

    ./.venv/bin/mutmut run
    ./.venv/bin/mutmut export-cicd-stats
    ./.venv/bin/python scripts/mutation-score.py

Coverage says a line ran; the mutation score says a test would notice if it were
wrong. mutmut changes the code one small way at a time - a < for a <=, a 1 for a
0 - and runs the suite against each change. A change the suite still passes is a
mutant that survived: a place where the code could be wrong and nothing would say so.

Caught means killed or timed out: a mutant that turns a loop infinite has been
noticed, just slowly. Lines no test reaches count against the score too - the
suite cannot notice a change in code it never runs.
"""

from __future__ import annotations

import json
import sys
import tomllib
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
STATS = REPO / "mutants" / "mutmut-cicd-stats.json"
PYPROJECT = REPO / "pyproject.toml"


def score(stats: dict[str, int]) -> float:
    """The share of all mutants the suite caught, as a percentage."""
    if not stats["total"]:
        return 100.0
    return 100 * (stats["killed"] + stats["timeout"]) / stats["total"]


def main() -> int:
    stats = json.loads(STATS.read_text())
    floor = tomllib.loads(PYPROJECT.read_text())["tool"]["mutation"]["fail_under"]
    measured = score(stats)
    print(
        f"Mutation score {measured:.1f}% (floor {floor}%): "
        f"{stats['killed'] + stats['timeout']} of {stats['total']} caught, "
        f"{stats['survived']} survived, {stats['no_tests']} in code no test runs."
    )
    if measured < floor:
        print("Run ./.venv/bin/mutmut browse to see the survivors.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
