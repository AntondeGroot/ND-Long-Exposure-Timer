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

# A tag in the status bar, right-aligned to clear the battery, which starts at
# WIDTH - 26. It is where the screen says the answer is no longer its own.
STATUS_TAG_RIGHT_X = WIDTH - 30

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
PILL_PADDING = 12
ANSWER_BOTTOM = 88

# Selection on the answer, escalating: an outline says the five-way is pointing
# at the time, the same box filled says it is being set. Inverting the rows is
# how "selected" is said everywhere else, and this is that idiom given a border
# so the biggest thing on the panel is not a solid black third of the screen
# every time the selection passes over it.
ANSWER_BOX = (1, ANSWER_TOP + 2, WIDTH - 2, ANSWER_BOTTOM - 2)

# While the time is being set the arrows live in the margins, so the number keeps
# the middle of the column and most of its size.
SETTING_ARROW_X = 4
SETTING_ARROW_WIDTH = 14
SETTING_MAX_WIDTH = ANSWER_MAX_WIDTH - 2 * SETTING_ARROW_WIDTH

ROW_HEIGHT = 18

# Between the time and the rows, one band saying who is choosing the settings.
# It sits there because that is where the question arises: the time above is
# asked for, the rows below are the answer, and this is who worked them out.
TOGGLE_TOP = ANSWER_BOTTOM + 2
TOGGLE_BOTTOM = TOGGLE_TOP + ROW_HEIGHT

# The parameters below are a reference list, scanned rather than read, so one
# line each: label left, value right.
FIRST_ROW_TOP = TOGGLE_BOTTOM + 2

# Six rows. The first is the shutter the camera metered, which is a measurement
# and never moves. The four after it are the answer to the time above: the ISO,
# the aperture and the filters that would expose for it, and how far the nearest
# thing the bag can do lands from it. The last is the scenario.
#
# Which of them the five-way can land on depends on who is choosing: on AUTO
# none of the middle four, because they are answers; on MANUAL the ISO and the
# aperture, because then they are not.
#
# The miss gets a line of its own rather than sharing ND's, because "8+64+1000"
# is already the width of the column and a filter name that shrinks to 8pt is a
# filter name read wrong in the dark.
BASE = "base"
ISO = "ISO"
APERTURE = "APER"
ND = "ND"
OFF = "off"
MODE = "MODE"

ROWS = (BASE, ISO, APERTURE, ND, OFF, MODE)

# What the five-way can be pointing at, and the order up and down walk them. The
# time leads because it is what the photographer sets and the rest is worked back
# from it, and because the rows below it are answers rather than controls - until
# the toggle says they are not.
TIME = "time"
AUTO = "auto"
SETTINGS = "settings"

AUTO_SELECTIONS = (TIME, AUTO, MODE, SETTINGS)
MANUAL_SELECTIONS = (TIME, AUTO, ISO, APERTURE, MODE, SETTINGS)


def selections(is_auto: bool) -> tuple:
    """The stops the five-way walks, which the toggle adds two of."""
    return AUTO_SELECTIONS if is_auto else MANUAL_SELECTIONS


CENTRE_X = WIDTH // 2
LABEL_X = 4
VALUE_RIGHT_X = WIDTH - 4

# Space between a row's label and its value. Below this they read as one string.
LABEL_VALUE_GAP = 6

# Row values shrink to fit rather than overrun the label: a stack of three
# filters is "ND8+ND64+ND1000 +19", which is far wider than "100".
ROW_VALUE_SIZES = (11, 10, 9, 8)

# One band, because SHOOT is a button under your thumb rather than a thing on
# the screen: a panel that draws it is spending its own space saying what the
# hardware already says.
FOOTER_TOP = 222


# The settings list has no answer above it to make room for, so it starts just
# under the status bar and the whole screen is entries.
SETTINGS_FIRST_ROW_TOP = STATUS_BAR_HEIGHT + 6

# A list longer than the screen scrolls, and says so with a small arrow at the
# end that has more beyond it: the top one sits in the gap under the status bar,
# the bottom one in room kept free above BACK. The filter list is the long one.
SCROLL_HINT_HEIGHT = 4
SCROLL_HINT_HALF_WIDTH = 4
SCROLL_HINT_ROOM = 8
SETTINGS_VISIBLE_ROWS = (FOOTER_TOP - SETTINGS_FIRST_ROW_TOP - SCROLL_HINT_ROOM) // ROW_HEIGHT
SCROLL_HINT_UP_TOP = STATUS_BAR_HEIGHT + 2
SCROLL_HINT_DOWN_TOP = SETTINGS_FIRST_ROW_TOP + SETTINGS_VISIBLE_ROWS * ROW_HEIGHT + 2


def row_top(index: int) -> int:
    return FIRST_ROW_TOP + index * ROW_HEIGHT


def settings_row_top(index: int) -> int:
    return SETTINGS_FIRST_ROW_TOP + index * ROW_HEIGHT
