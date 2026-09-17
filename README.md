# ND Long Exposure Timer

A hot-shoe mounted long-exposure calculator and shutter timer for a DSLR, built on a
Raspberry Pi Zero.

Fit a strong ND filter and your camera's meter is useless: it cannot see through ten
stops of glass, and the exposure you need is minutes rather than fractions of a second.
This device reads what the camera metered *before* the filter went on, adds up the stops
of the filters you are using, and works out how long the shutter must stay open. Then it
holds it open for you and counts down, because past 30 seconds the camera cannot time
itself.

- **SYNC** reads ISO, aperture and shutter speed from the camera over USB
- Shift ISO or aperture and the base shutter recomputes to hold the same exposure
- Pick a filter or a stack; the final time and whether it needs BULB update as you go
- **SHOOT** fires it - the camera times anything up to 30s, the Pi times the rest

## What it looks like

The display is a 2.13" e-paper panel mounted upright: 122 x 250 pixels as the screens
are drawn, one bit deep. No grey, no antialiasing, so "selected" is shown by inverting.
The panel's own buffer is 250 x 122 and the driver rotates a quarter turn on the way
out, which nothing above that layer needs to know about.

These images are rendered from the real drawing code and byte-compared by the test
suite, so they cannot drift out of date without a test failing.

### Calculator

The parameter list sits above the arithmetic, which reads down to its answer. The
selected row is inverted and grows carets to show that left and right change it. At 122
pixels wide there is no room for a label beside its value, so each row stacks them.

![Calculator screen](docs/screens/main-waterfall@3x.png)

Past 30 seconds the shot has to run on bulb, and the panel says so - the Pi is the timer
from that point on.

![Calculator screen showing a bulb exposure](docs/screens/main-bulb@3x.png)

Before the first SYNC there is nothing to calculate from, and the device says that
rather than showing a confident wrong number.

![Calculator screen before syncing](docs/screens/main-not-synced@3x.png)

### Exposing

Remaining time gets the whole column, because it is read from wherever the camera is
standing. A progress bar and the elapsed/total sit beneath it. The countdown redraws
every 10 seconds rather than every second: e-paper wears with every refresh, and on a
five-minute exposure the extra ticks buy nothing.

![Countdown screen](docs/screens/countdown-bulb@3x.png)

## Controls

| Control | Does |
|---------|------|
| Five-way up / down | move between rows |
| Five-way left / right | change the selected value |
| Five-way centre | open the menu |
| SYNC | read the current exposure from the camera |
| SHOOT | start the exposure; hold to cancel a running one |

## Development

The exposure maths, the screens and the camera commands are all testable without any
hardware attached - which matters, because the Pi's only USB port cannot carry both the
camera and an ssh session.

```bash
python3 -m venv .venv && ./.venv/bin/pip install pytest pillow
./.venv/bin/python -m pytest          # includes the golden-image checks
./scripts/render-screens.py           # after a deliberate UI change, then commit the images
```

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

- micro-usb soldering plug 5 poles\
  <img width="200"  alt="image" src="https://github.com/user-attachments/assets/4b83c40a-3927-49ab-8324-e03e0da98926" />

- usb-A port with 4 pole\
  <img width="200" alt="image" src="https://github.com/user-attachments/assets/32fce523-0029-4b52-a5a5-c7ed3eab73d9" />


- 2x TLYCRQJXF Momentary Tactile Push Button, 12 x 12 x 7,3 mm\
  <img width="200" height="200" alt="image" src="https://github.com/user-attachments/assets/a8823ef3-7dc4-4e2d-9e30-258b56376464" />


- USB A ==> UC-E6 UC-E16 UC-E17 cable 
- 1/4" Camera Hot shoe Mount\
  <img width="200" alt="image" src="https://github.com/user-attachments/assets/daab8fbc-d2e3-43ca-9c25-478450506ead" />

