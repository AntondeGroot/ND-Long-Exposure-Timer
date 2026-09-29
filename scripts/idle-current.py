#!/usr/bin/env python3
"""Log what the device draws from its battery, to compare one Pi against another.

RUNS ON THE PI, with the timer running as normal - "idle" here means the device
sitting on its main screen waiting for a press, which is how it spends most of
a session. The reading comes from the UPS HAT's INA219, on the cell side of the
HAT, so it is what the battery actually gives up.

Unplug the USB cable while it measures. On a Pi Zero the data port powers the
board too, so with the Mac attached part of the load comes from the Mac and the
battery looks better than it is. That is why this logs to a file and runs on
its own: start it, unplug, wait, plug back in, read the file.

    nohup ./.venv/bin/python scripts/idle-current.py --minutes 10 </dev/null >/dev/null 2>&1 &
    # unplug the USB cable, wait ten minutes and a bit, plug it back in
    cat ~/idle-current.txt

Started over ssh, all three redirections matter, and so does keeping the & on
this command alone:

    ssh nd-timer 'cd ~/ND-Long-Exposure-Timer; nohup ./.venv/bin/python \
        scripts/idle-current.py --minutes 10 </dev/null >/dev/null 2>&1 &'

A ; after the cd, not &&: "cd && nohup ... &" puts the whole pair in a
background shell of its own, which keeps the ssh session open waiting for the
script, whatever the script's own redirections say.

The charging lead must be out as well: a charging cell reads as current going
in, not out.
"""

from __future__ import annotations

import argparse
import statistics
import sys
import time
from dataclasses import dataclass
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from nd_timer.battery import Battery  # noqa: E402

# The cell the UPS HAT ships with. Only used to turn a draw into hours.
CELL_MAH = 1000

# Where a board says what it is. Recorded so two logs cannot be mixed up.
MODEL = Path("/proc/device-tree/model")


@dataclass(frozen=True)
class Summary:
    """What a run of readings comes to."""

    samples: int
    mean_ma: float
    lowest_ma: float
    highest_ma: float
    hours_on_a_full_cell: float


def summarised(discharge_ma: list[float], cell_mah: float = CELL_MAH) -> Summary:
    """The readings as a draw and a runtime. Positive is out of the cell.

    The runtime is the cell's rating over the mean draw - generous, because a
    lithium cell never gives its whole rating and the protection circuit cuts
    in before empty. Good for comparing two boards, not for promising hours.
    """
    if not discharge_ma:
        raise ValueError("no readings to summarise - is the UPS HAT's I2C bus enabled?")
    mean = statistics.fmean(discharge_ma)
    return Summary(
        samples=len(discharge_ma),
        mean_ma=mean,
        lowest_ma=min(discharge_ma),
        highest_ma=max(discharge_ma),
        hours_on_a_full_cell=cell_mah / mean if mean > 0 else float("inf"),
    )


def board() -> str:
    try:
        return MODEL.read_text().rstrip("\0").strip()
    except OSError:
        return "unknown board"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--minutes", type=float, default=10.0)
    parser.add_argument("--interval", type=float, default=1.0, help="seconds between readings")
    parser.add_argument("--out", type=Path, default=Path.home() / "idle-current.txt")
    args = parser.parse_args()

    battery = Battery()
    readings: list[float] = []
    deadline = time.monotonic() + args.minutes * 60

    with args.out.open("w") as log:
        log.write(f"# {board()}, every {args.interval:g}s for {args.minutes:g} min\n")
        log.write("# seconds,milliamps_out_of_cell,cell_volts\n")
        started = time.monotonic()
        while time.monotonic() < deadline:
            current = battery.milliamps()
            volts = battery.volts()
            if current is not None:
                # The chip counts into the cell as positive; a draw is the reverse.
                readings.append(-current)
                log.write(f"{time.monotonic() - started:.1f},{-current:.1f},{volts or 0:.3f}\n")
                log.flush()
            time.sleep(args.interval)

        try:
            summary = summarised(readings)
        except ValueError as exc:
            log.write(f"# {exc}\n")
            print(exc, file=sys.stderr)
            return 1

        lines = [
            f"board:     {board()}",
            f"readings:  {summary.samples}",
            f"draw:      {summary.mean_ma:.0f}mA mean ({summary.lowest_ma:.0f} to {summary.highest_ma:.0f})",
            f"full cell: ~{summary.hours_on_a_full_cell:.1f}h at that draw ({CELL_MAH}mAh, an upper bound)",
        ]
        if summary.mean_ma < 0:
            lines.append("NOTE: the cell was charging - unplug the charger and measure again")
        for line in lines:
            log.write(f"# {line}\n")
            print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
