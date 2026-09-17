"""Where everything sits on the panel, in its native pixel space.

The panel is mounted upright, so screens are drawn 122 wide by 250 tall, which is
the panel's own native orientation - Waveshare's landscape examples are the ones
doing the rotating, not us.

One bit deep: no grey, no antialiasing, and any "highlight" has to be an
inversion. The numbers here started from the build spec's landscape layout and
were refitted for the narrow column, which is the binding constraint - 122px does
not leave room for a label and its value side by side at a readable size.
"""

from __future__ import annotations

from pathlib import Path

WIDTH = 122
HEIGHT = 250

# The panel's own buffer, which is portrait: Waveshare's landscape examples pass
# a 250 x 122 image and let the library rotate it. Mounted upright, the screens
# are drawn in the panel's native orientation and nothing has to be rotated.
PANEL_WIDTH = 122
PANEL_HEIGHT = 250

BLACK = 0
WHITE = 1

FONT_DIR = Path(__file__).resolve().parent.parent.parent / "assets" / "fonts"
REGULAR_FONT = FONT_DIR / "DejaVuSans.ttf"
BOLD_FONT = FONT_DIR / "DejaVuSans-Bold.ttf"

TINY = 9
SMALL = 11
MEDIUM = 14
HERO = 34

# Sizes the answer may shrink through, largest first, so a long time still fits.
HERO_SIZES = (34, 30, 26, 22, 18)
ANSWER_MAX_WIDTH = WIDTH - 8

# The countdown has a whole screen for one number and is read at a distance, so
# it gets the biggest type the column will carry.
COUNTDOWN_HERO = 46

STATUS_BAR_HEIGHT = 15

# The answer comes first and takes the top third: it is what the device is for,
# and the only thing that needs reading at arm's length.
ANSWER_TOP = STATUS_BAR_HEIGHT
ANSWER_CENTRE_Y = 40

# The target the subject wants, directly under the answer so the two read together.
TARGET_Y = 60

# BULB only appears when it applies, so it sits below the target rather than
# displacing it.
PILL_HEIGHT = 14
PILL_TOP = 72
ANSWER_BOTTOM = 88

# The parameters below are a reference list, scanned rather than read, so one
# line each: label left, value right.
ROW_HEIGHT = 18
FIRST_ROW_TOP = ANSWER_BOTTOM + 2

# Six rows. Two of them are derived rather than edited: the base shutter comes
# from the camera and the ISO/aperture shift, and the stops follow from whichever
# filter combination is chosen. Giving the stops their own line is what lets the
# filter names stay legible - "8+64+1000 19st" on one line has to shrink to 8pt.
SELECTABLE = True
DERIVED = False

ROW_PLAN = (
    ("base", DERIVED),
    ("ISO", SELECTABLE),
    ("APER", SELECTABLE),
    ("ND", SELECTABLE),
    ("stops", DERIVED),
    ("MODE", SELECTABLE),
)
ROW_COUNT = len(ROW_PLAN)

CENTRE_X = WIDTH // 2
LABEL_X = 4
VALUE_RIGHT_X = WIDTH - 4

# Space between a row's label and its value. Below this they read as one string.
LABEL_VALUE_GAP = 6

# Row values shrink to fit rather than overrun the label: a stack of three
# filters is "ND8+ND64+ND1000 +19", which is far wider than "100".
ROW_VALUE_SIZES = (11, 10, 9, 8)

# The footer is two bands: the quiet buttons share a row, and SHOOT gets its own
# inverted bar because it is the one with consequences.
FOOTER_TOP = 200
SHOOT_TOP = 222


def row_top(index: int) -> int:
    return FIRST_ROW_TOP + index * ROW_HEIGHT
