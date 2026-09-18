# ND Long Exposure Timer

Taking long exposure photos can be cumbersome. You work forward based on the filters you might want to put on your camera. However working backwards based on the exposure time you desire is much more user friendly.
This way you only need to think about the intended effect you want to create.

Normally
- you first need to determine the correct exposure
- then guess which filters you would need
- then calculate how much the total exposure time will be
- maybe pick different filters and calculate again
- and then backsolve how to adjust:  iso / aperture so your base shutter speed will result in the total exposure time you wanted.

This module will make the whole process shutter priority, and tell you which filters you need, it will take care of the camera settings.
- sync with your camera when you have your exposure set correctly
- let you chose the total exposure time
- it will tell you what filters you need to put on
- it will automatically determine the settings for the long exposure.

no calculations or iterative backsolving required!


It is shutter priority, with the filters in the loop. A camera in that mode balances
the shutter you chose against the one variable it has; this one has your filter bag as
well, and a stop of ND buys time without touching the photograph at all.

- **SYNC** reads ISO, aperture and shutter speed from the camera over USB
- Choose the time you want, or a scenario that knows what it wants
- The panel names the filters to screw on and the ISO and aperture to set

## What it looks like

The display is a 2.13" e-paper panel mounted upright: 122 x 250 pixels. "selected" is shown by inverting the colors.

### The recipe

The time is at the top because it is the one thing you choose. Under it, **base** is
the shutter the camera was reading when you pressed SYNC - a measurement, which nothing
the device does moves. The rest is the answer to your time, read down the column: the
ISO and aperture to set, the filters to screw on, and how close that lands. At 122
pixels wide there is no room for a label beside its value, so each row stacks them.

![The main screen](docs/screens/main-waterfall@3x.png)

Past 30 seconds the shot has to run on bulb, and the panel says so - the Pi is the timer
from that point on.

![The main screen showing a bulb exposure](docs/screens/main-bulb@3x.png)

Before the first SYNC there is no scene to work back from, and the device says that
rather than printing a recipe it cannot stand behind.

![The main screen before syncing](docs/screens/main-not-synced@3x.png)

### When the bag cannot get there

Filters come in coarse jumps, so the time asked for is often not reachable with glass
alone. ISO in thirds is the trim that closes the gap - the ISO on screen is simply the
one that makes your time the correct exposure for what was metered, not a change to the
reading itself. The **off** row is what is left over: a signed number of stops, where
positive is brighter than metered, so shoot that time anyway and the frame is over by
that much. It says `exact` only when there is nothing left worth reading.

Aperture is moved last and least, because it is the one thing on the list the photograph
itself can see - and it moves in thirds, so when it has to move it moves by f/11 to f/13
rather than by a whole stop.

The row keeps speaking below the point where the device stops working. A third of a stop
is the finest step a camera has, so one recipe serves every time within half a step of
it: ask for nine minutes or for ten and the filters, the ISO and the aperture are the
same, because nothing on the camera could tell those two apart. They are not the same
photograph though - the second is a minute more cloud - so the row reads `exact` at one
and `+0.1st` at the other, and the difference between the two screens is visible rather
than implied.

![The main screen with a filter bag that cannot reach](docs/screens/main-out-of-reach@3x.png)

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

![The main screen with the time being set](docs/screens/main-setting-time@3x.png)

The ladder runs from 1/125 to 15s, then 00:16 and whole minutes to an hour - well past what
long exposure needs at the fast end, because waves want 1/8 and a dial that reaches 1/125 is
one a self-timer can be built on later.

![The main screen dialling a fast shutter](docs/screens/main-setting-waves@3x.png)

A time dialled away from the scenario's own says SET in the status bar. The rows
underneath always agree with the time, so the tag is not about them: it says this time is
yours, and choosing a scenario is how you hand it back.

![The main screen with a hand-set time](docs/screens/main-time-set@3x.png)

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

![Settings](docs/screens/settings@3x.png)

The filter list is the same screen one level down. The centre press is what puts a
filter in the bag or takes it out, so its rows go without the carets that would promise
left and right do something.

![The filter list](docs/screens/settings-filters@3x.png)

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

![The delay before the exposure](docs/screens/delay@3x.png)

Nothing has been recorded yet at that point, so it is also the cheapest moment to change
your mind - the same press that stops a running exposure calls this off.

Then the exposure itself. Remaining time gets the whole column, because it is read from
wherever the camera is standing. A progress bar and the elapsed/total sit beneath it.

The countdown changes every 10 seconds rather than every second: e-paper wears with every
refresh and takes about a second to do one, and on a five-minute exposure the extra ticks
buy nothing. The bar and the elapsed come off that same stepped clock, so the whole frame
holds still between steps rather than one part of it creeping. The step rounds the elapsed
down, which rounds what is left up - better to be told a little more is coming than to
watch it sit at zero with the shutter still open.

![Countdown screen](docs/screens/countdown-bulb@3x.png)

## Controls

The five-way lands on three things only - the time, the scenario, and settings - because
the four rows between them are answers rather than controls.

| Control | Does |
|---------|------|
| Five-way up / down | move between the time, the scenario and settings; while setting the time, a second on or off |
| Five-way left / right | change the scenario, which changes the time; while setting the time, step it |
| Five-way centre | start or stop setting the time when it is selected, otherwise open the menu |
| SYNC | read the current exposure from the camera |
| SHOOT | start the shot; hold to cancel it, waiting or exposing |

## Development

The exposure maths, the screens and the camera commands are all testable without any
hardware attached - which matters, because the Pi's only USB port cannot carry both the
camera and an ssh session.

```bash
python3 -m venv .venv && ./.venv/bin/pip install pytest pillow
./.venv/bin/python -m pytest          # includes the golden-image checks
./scripts/render-screens.py           # after a deliberate UI change, then commit the images
```

### Trying it without the hardware

The whole device runs on a laptop, with the panel in a browser and the camera faked:

```bash
./scripts/simulator.py                # then open http://localhost:8000
```

The five-way, SYNC and SHOOT are on the page and on the keyboard, and the picture
served is the exact 122 x 250 buffer the panel would be holding. The three values
SYNC reads sit beside it, so a scene can be metered with no camera on the desk,
and the clock can be run fast while the shutter is open - a six-minute exposure
is worth watching at 60x rather than in real time.

What the buttons drive is `nd_timer/device.py`, the state machine the Pi runs:
presses arrive as method calls and the clock arrives as an argument, so the panel
driver and gphoto2 are the only parts the simulator stands in for. The solving
itself is `nd_timer/recipe.py`, which is where the time becomes a filter stack.

Provisioning a fresh Pi, flashing a card and driving the camera by hand are covered by
the scripts in `scripts/`.

# Bill of Materials
- five way button\
  <img width="200" alt="17849727845893738776011421435184" src="https://github.com/user-attachments/assets/b6a12755-35c8-49f5-8064-88f008445e4b" />

- Raspberry Pi Zero, it needs linux for gphoto2 
- 2.13'' E-paper display
- UPS HAT for Raspberry Pi Zero with 1000mah battery\
  <img width="200" alt="image" src="https://github.com/user-attachments/assets/cb306792-c2a6-40d5-bd81-8b63f4ea3967" />

- power button 16mm diameter (latching 3 pole 1NO1NC)
- usb-c port with only power cables\
  <img width="200" alt="image" src="https://github.com/user-attachments/assets/645d8d48-21d6-4195-a56d-52074ed21b96" />

- micro-usb soldering plug 5 pins\
  <img width="200"  alt="image" src="https://github.com/user-attachments/assets/4b83c40a-3927-49ab-8324-e03e0da98926" />

- usb-A port with 4 pole\
  <img width="200" alt="image" src="https://github.com/user-attachments/assets/32fce523-0029-4b52-a5a5-c7ed3eab73d9" />


- 2x TLYCRQJXF Momentary Tactile Push Button, 12 x 12 x 7,3 mm\
  <img width="200" height="200" alt="image" src="https://github.com/user-attachments/assets/a8823ef3-7dc4-4e2d-9e30-258b56376464" />


- USB A ==> UC-E6 UC-E16 UC-E17 cable 
- 1/4" Camera Hot shoe Mount\
  <img width="200" alt="image" src="https://github.com/user-attachments/assets/daab8fbc-d2e3-43ca-9c25-478450506ead" />

