# The screens

What each screen shows, and why it looks the way it does.

### The recipe

The time is at the top because it is the one thing you choose. Under it, a band saying
who is choosing everything else. Then **base**, the shutter the camera was reading when
you pressed SYNC - a measurement, which nothing the device does moves - and the answer
to your time, read down the column: the ISO and aperture to set, the filters to screw
on, and how close that lands. 

![The main screen](screens/main-waterfall@3x.png)

Past 30 seconds the shot has to run on bulb, and the panel says so - the Pi is the timer
from that point on.

![The main screen showing a bulb exposure](screens/main-bulb@3x.png)

Before the first SYNC there is no scene to work back from, and the device says that
rather than printing a recipe it cannot stand behind.

![The main screen before syncing](screens/main-not-synced@3x.png)

### The battery

The UPS HAT carries an INA219, which measures volts and amps rather than a percentage. That is a cruder thing than it looks: a lithium cell sits near
3.7V for most of its life and then falls off a cliff, and it sags under load and
recovers after.

So it is treated as an estimate. The reading is smoothed and reported in steps of
five, which keeps a wandering last digit from costing a panel refresh, and stops
the device claiming 73% when it knows no such thing.

When nothing answers on the bus - no UPS fitted, or I2C never enabled - the
battery is drawn hatched rather than empty. An empty outline says the cell is
dead and sends you home; hatching says the number is not known.

![A device with no battery gauge](screens/main-no-battery@3x.png)

### When the bag cannot get there

Filters come in coarse jumps, so the time asked for is often not reachable with glass
alone. ISO in thirds is the trim that closes the gap - the ISO on screen is simply the
one that makes your time the correct exposure for what was metered, not a change to the
reading itself. The **DEV** row is the deviation in stops of what it thinks a perfect exposure would be. It can be overruled in **manual** mode.

Aperture is moved last and least, because it is the one thing on the list the photograph
itself can see - and it moves in thirds, so when it has to move it moves by f/11 to f/13
rather than by a whole stop.

![The main screen with a filter bag that cannot reach](screens/main-out-of-reach@3x.png)

### Taking the settings over

**AUTO** is the device choosing: the ISO, the aperture and the filters are all worked
back from your time. Press the five-way's centre on the band - or push it left or right
- and it says **MANUAL**, which hands you the ISO and the aperture. The five-way then
stops on those two rows, because on AUTO they were answers and now they are not.

It starts from whatever AUTO had chosen, so nothing jumps under the press. The filters
do not move: whatever is screwed on stays screwed on, and the ISO and the aperture are
what you turn around it. What changes is the **off** row, which is the whole point of
the mode - the device stops solving and starts telling you where you have got to.

![The settings taken over by hand](screens/main-manual@3x.png)

The ceiling and the lens ends from settings still hold: MANUAL is the photographer
choosing within the kit, not the kit being forgotten.

### Setting the time

A scenario is a shortcut to a time rather than a mode of its own: choosing CLOUDS puts
the dial in the middle of what clouds want and the recipe follows. From there the time
is yours. Press the five-way's centre on it and left and right walk the camera's own
third-stop ladder, up and down move a second for the times the ladder skips. Below a
second the screen stops offering them - a second added to 1/8 is three stops, which is a
jump rather than an adjustment - but the press still works, and is often how you leave
the fast end.

While the time is being set the answer is inverted and written as a clock, so a second on
or off moves a digit rather than reflowing the whole number.

![The main screen with the time being set](screens/main-setting-time@3x.png)

The ladder runs from 1/125 to 15s, then 00:16 and whole minutes to an hour - well past what
long exposure needs at the fast end, because waves want 1/8 and a dial that reaches 1/125 is
one a self-timer can be built on later.

![The main screen dialling a fast shutter](screens/main-setting-waves@3x.png)

A time dialled away from the scenario's own says SET in the status bar. The rows
underneath always agree with the time, so the tag is not about them: it says this time is
yours, and choosing a scenario is how you hand it back.

![The main screen with a hand-set time](screens/main-time-set@3x.png)

### Settings

The device can only answer out of the kit it has been told about, so most of settings is
that kit: which filters are in the bag, how far the ISO may be pushed, and the two ends
of the lens. A filter left out of the bag is never asked for and an aperture past either
end is never named - the device would rather miss the time and say so on the **off** row
than tell you to use glass you did not bring. **DELAY** is the exception, and is about
the tripod rather than the camera.

The two ends run in thirds, like the camera's own dial, so an f/3.5-6.3 zoom can be
described exactly rather than rounded to the nearest whole stop. It starts describing
every lens, f/1.4 to f/22, and the whole common filter set, so it is useful before it is
configured rather than empty.

![Settings](screens/settings@3x.png)

The filter list is the same screen one level down. The centre press is what puts a
filter in the bag or takes it out, so its rows go without the carets that would promise
left and right do something.

![The filter list](screens/settings-filters@3x.png)

### Exposing

The shutter does not open on the press. A finger coming off a button is the worst
vibration a tripod sees all evening, and a long exposure records every bit of it, so
SHOOT starts a delay and the exposure is counted from the shutter rather than from the
button. Eight seconds by default, which is long enough for the thing to stop ringing and
short enough not to be something you work around; **DELAY** in settings takes it from
`off` to thirty seconds.

The panel says so once and then leaves it alone. Nothing on it counts down: a refresh
takes about a second and wears the panel a little each time, so a ticking number would
spend the delay flashing - through the very seconds the delay exists to keep still - and
would be out of date by the time it had finished drawing itself.

![The delay before the exposure](screens/delay@3x.png)

Nothing has been recorded yet at that point, so it is also the cheapest moment to change
your mind - the same press that stops a running exposure calls this off.

When the camera refuses - unplugged, asleep, or busy with something else - the countdown
does not start. A device counting down a shutter that never opened is the one screen a
photographer walks away from, so the status bar takes the news instead and says which
kind of refusal it was. The words gphoto2 used are in the journal.

![The camera did not answer](screens/main-no-camera@3x.png)

Then the exposure itself. Remaining time gets the whole column, because it is read from
wherever the camera is standing. A progress bar and the elapsed/total sit beneath it.

The countdown changes every 10 seconds rather than every second: e-paper wears with every
refresh and takes about a second to do one, and on a five-minute exposure the extra ticks
buy nothing. The bar and the elapsed come off that same stepped clock, so the whole frame
holds still between steps rather than one part of it creeping. The step rounds the elapsed
down, which rounds what is left up - better to be told a little more is coming than to
watch it sit at zero with the shutter still open.

![Countdown screen](screens/countdown-bulb@3x.png)

## Navigation

On AUTO the five-way lands on four things - the time, the AUTO/MANUAL band, the scenario
and settings - because the rows between them are answers rather than controls. On MANUAL
it stops on the ISO and the aperture too.
