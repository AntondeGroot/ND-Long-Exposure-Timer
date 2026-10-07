# ND Long Exposure Timer

Taking long exposure photos can be cumbersome.

This module will make the whole process "shutter priority", and tell you which filters you need, it will take care of the camera settings like ISO and aperture for small adjustments.

Working based on the exposure time you desire is much more user friendly.
This way you only need to think about the intended effect you want to create.

For an interactive preview see: https://antondegroot.github.io/ND-Long-Exposure-Timer/

Before:
- you first need to determine the correct exposure
- then guess which filters you would need
- then calculate how much the total exposure time will be in seconds, and convert that to mm:ss.
- maybe pick different filters and calculate again
- and then backsolve how to adjust:  iso / aperture so your base shutter speed will result in the total exposure time you wanted.

Now:
- you sync with your camera when you have your exposure set correctly
- you choose the total exposure time
- it will tell you what filters you need to put on
- it will automatically determine the ISO and aperture settings needed for the long exposure within a given range.

No calculations or iterative backsolving required!

## What it looks like
<details>
<summary>Show the screens</summary>


### The recipe

The time is at the top because it is the one thing you choose. Under it, a band saying
who is choosing everything else. Then **base**, the shutter the camera was reading when
you pressed SYNC - a measurement, which nothing the device does moves - and the answer
to your time, read down the column: the ISO and aperture to set, the filters to screw
on, and how close that lands. 

![The main screen](docs/screens/main-waterfall@3x.png)

Past 30 seconds the shot has to run on bulb, and the panel says so - the Pi is the timer
from that point on.

![The main screen showing a bulb exposure](docs/screens/main-bulb@3x.png)

Before the first SYNC there is no scene to work back from, and the device says that
rather than printing a recipe it cannot stand behind.

![The main screen before syncing](docs/screens/main-not-synced@3x.png)

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

![A device with no battery gauge](docs/screens/main-no-battery@3x.png)

### When the bag cannot get there

Filters come in coarse jumps, so the time asked for is often not reachable with glass
alone. ISO in thirds is the trim that closes the gap - the ISO on screen is simply the
one that makes your time the correct exposure for what was metered, not a change to the
reading itself. The **DEV** row is the deviation in stops of what it thinks a perfect exposure would be. It can be overruled in **manual** mode.

Aperture is moved last and least, because it is the one thing on the list the photograph
itself can see - and it moves in thirds, so when it has to move it moves by f/11 to f/13
rather than by a whole stop.

![The main screen with a filter bag that cannot reach](docs/screens/main-out-of-reach@3x.png)

### Taking the settings over

**AUTO** is the device choosing: the ISO, the aperture and the filters are all worked
back from your time. Press the five-way's centre on the band - or push it left or right
- and it says **MANUAL**, which hands you the ISO and the aperture. The five-way then
stops on those two rows, because on AUTO they were answers and now they are not.

It starts from whatever AUTO had chosen, so nothing jumps under the press. The filters
do not move: whatever is screwed on stays screwed on, and the ISO and the aperture are
what you turn around it. What changes is the **off** row, which is the whole point of
the mode - the device stops solving and starts telling you where you have got to.

![The settings taken over by hand](docs/screens/main-manual@3x.png)

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

When the camera refuses - unplugged, asleep, or busy with something else - the countdown
does not start. A device counting down a shutter that never opened is the one screen a
photographer walks away from, so the status bar takes the news instead and says which
kind of refusal it was. The words gphoto2 used are in the journal.

![The camera did not answer](docs/screens/main-no-camera@3x.png)

Then the exposure itself. Remaining time gets the whole column, because it is read from
wherever the camera is standing. A progress bar and the elapsed/total sit beneath it.

The countdown changes every 10 seconds rather than every second: e-paper wears with every
refresh and takes about a second to do one, and on a five-minute exposure the extra ticks
buy nothing. The bar and the elapsed come off that same stepped clock, so the whole frame
holds still between steps rather than one part of it creeping. The step rounds the elapsed
down, which rounds what is left up - better to be told a little more is coming than to
watch it sit at zero with the shutter still open.

![Countdown screen](docs/screens/countdown-bulb@3x.png)

</details>

## Controls

On AUTO the five-way lands on four things - the time, the AUTO/MANUAL band, the scenario
and settings - because the rows between them are answers rather than controls. On MANUAL
it stops on the ISO and the aperture too.

| Control | Does |
|---------|------|
| Five-way | navigation |
| Five-way centre | select |
| SYNC | read the current exposure settings from the camera |
| SHOOT | start the shot, hold to cancel it |

## Development
<details>
<summary>Show the development setup</summary>

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

</details>

## Installing on a Pi
<details>
<summary>Show the install steps</summary>

From a blank SD card to a running device. Every step is a script, and the notes say why
each exists - most of them exist to work around something that is not obvious until it
has cost you an evening.

### 1. Flash the card, on the Mac

```bash 
sudo ./scripts/flash-sd.sh ~/Downloads/raspios-lite.img.xz
```

It asks for a password for the `pi` account and writes it as a SHA-512 hash, because Pi
OS ships no default user at all - without this you cannot log in, and the Pi will tell
you so over ssh while refusing every key you own. It also enables sshd and puts the USB
port into gadget mode, so a Zero with no wifi is reachable over the same cable that
powers it.

The script refuses to write to anything that looks like a real disk rather than a card,
and will not touch a write-protected one.

### 2. Get a key onto it

Boot the Pi with the cable in the **middle** micro-USB port, the one marked `USB`. The
outer one is `PWR IN` and carries power but no data: the Pi boots happily and never
appears on the network. It comes up as `10.55.0.1`.

```bash
ssh-copy-id -i ~/.ssh/pi_deploy_key.pub pi@10.55.0.1
```

This needs the password from step 1, so it is typed by hand exactly once. Everything
after it is key-based.

### 3. Lend the Pi your internet, on the Mac

```bash
sudo ./scripts/share-internet-macos.sh
```

The next step installs packages and a Zero has no network of its own. macOS Internet
Sharing cannot be used here: it takes over the gadget interface, renumbers it and runs a
DHCP server the Pi would never take a lease from, so this does the same job with `pf`
and keeps the addressing we already have.

### 4. Copy the code over, on the Mac

```bash
./scripts/deploy-to-pi.sh
```

It will warn that the service does not exist yet. That is expected - it is not installed
until the next step.

### 5. Provision the Pi

```bash
ssh -t pi@10.55.0.1 'cd ~/ND-Long-Exposure-Timer && sudo ./scripts/setup-pi.sh'
```

Expect 15-30 minutes; it is a full apt install on an ARMv6. It builds the venv, installs
the Python and GPIO stack, enables **SPI** for the panel and **I2C** for the battery
gauge, installs the systemd unit, and hands off to `install-gphoto2.sh` and
`install-boot-splash.sh`. The `-t` matters: `sudo` needs a real terminal to prompt for a
password.

It also hands off to `speed-up-boot.sh`. A stock card here took **1m44s** to a login,
with `sysinit.target` waiting on cloud-init until 59s and NetworkManager another 21s on
the critical path. cloud-init configures machines from a cloud provider's metadata
service; this is a camera timer. Only the safe set is applied - `--aggressive` also drops
avahi, and with it `raspberrypi.local`, which is a way back in when the USB link
misbehaves.

That step has to happen here rather than at flash time, because a freshly flashed card
still needs cloud-init for its own first boot: Pi OS seeds it from the boot partition.

The splash matters more than it sounds for the same reason: a blank panel for a minute
and a half reads as a device that did not switch on. If a card was provisioned before
either was part of setup, `sudo ./scripts/install-boot-splash.sh` and
`sudo ./scripts/speed-up-boot.sh` add them on their own; `--restore` and `--remove` undo
them.

Reboot afterwards. `/dev/spidev0.0` and `/dev/i2c-1` only appear then, and without them
the panel and the gauge are both dead.

### 6. Start it, on the Mac

```bash
./scripts/deploy-to-pi.sh
ssh -t pi@10.55.0.1 'sudo systemctl enable --now nd-timer'
```

From here `deploy-to-pi.sh` is the only one you rerun; the service is enabled once and
restarts itself on each deploy.

### When the panel looks wrong

```bash
ssh pi@10.55.0.1 'cd ~/ND-Long-Exposure-Timer && ./.venv/bin/python scripts/panel-orientation.py'
```

Run it with the service stopped, since the service holds the SPI bus. Solid black and
white frames contain no fonts, no layout and nothing of ours, so anything other than a
uniform block means the bytes are not arriving - the wiring, not the code. The letter F
that follows is asymmetric in both axes, so where its arms land says whether the image
is mirrored or flipped, which a solid frame cannot tell you.

A panel that flashes through a refresh and then settles back to the *old* image is
showing stale RAM: commands are arriving and image data is not, which is the DC line's
job and nothing else's.

Flashing a fresh card fixes none of this. It is worth doing only to rule software out.

</details>

## Circuit diagrams
<details>
<summary>Show the circuit diagrams</summary>

For checking the design, not for building it: everything needed to solder the board is in
[Building the exposure timer](#building-the-exposure-timer).

### Button ring

![Button ring schematic](docs/ring-circuit.svg)

### Soft latch

![Soft latch schematic](docs/soft-latch-circuit.svg)

</details>

## Building the exposure timer
<details>
<summary>Show the build steps</summary>

You need a 3D printer for the enclosure, a soldering iron and a multimeter.

### 1. Solder the breakout board

Both circuits go on the Breakout Pi Zero in the BOM, in two separate regions: the ring
under the GP22 pad, the soft latch against the GND rail under GP12 (sense) and GP16
(hold). The strips run vertically in threes - rows A-C and D-F of each column - so parts
sit across columns, never along one. On the board itself it takes one jumper (the ring's
emitter to GND) and one solder bridge (21C to 21D, joining the gate's two strips, made
after the transistor that sits in 21C).

The seven buttons need no strips at all: each wire goes straight into its GPIO pad, on the
pins in `main.py`'s `PINS`, and one ground wire from the GND rail is daisy-chained to the
common leg of every button.

Holes are written column then row: `21C` is column 21, row C. This is the finished board:

![The whole build](docs/breakout/overview.svg)

The overview and the five steps below are drawn from one description of the build,
`scripts/breakout_drawing/layout.py`. To change the layout, change that file and run
`./scripts/draw-breakout.py` - never edit the SVGs. The test suite fails if they drift
apart. Each step shows what is already on the board faded, and only its own parts in
full.

Low parts first, so the board still lies flat on the bench for the next ones. Check each
step with a multimeter on continuity before starting the next: a short found now costs a
blob of solder, found later it costs a UPS HAT.

#### 1.1 Resistors and BAT85s

![Step 1](docs/breakout/step-1.svg)

The four resistors and two diodes, stood up. The GPIO legs go straight into the pads - no
wire. Stripe towards column 18 on both diodes.

Check: 20F to 21F and 19C to 21B do not beep (a resistor is not a short); 21C does not
beep to 21D yet.

#### 1.2 The AO3401

![Step 2](docs/breakout/step-2.svg)

Before soldering, put the meter on the adapter: confirm that the SIP pin going in 21E is
the gate and the middle one the source. Solder the adapter's middle leg first, check it
stands straight, then the outer two.

Check: no beep between any two of 19E, 20E and 21E.

#### 1.3 The two BC337s and the solder bridge

![Step 3](docs/breakout/step-3.svg)

Check the pinout on the part in hand first (see
[the ring wiring](#wiring-the-buttons-led-ring-as-an-indicator) below). Emitter to the
right on both: 10B for the ring, 23C - in the GND rail - for the soft latch. Leave a few
millimetres of leg so the iron does not cook them.

Then the bridge, on the underside, now that the collector is soldered in 21C: the
simplest bridge is that collector leg itself, bent over onto the 21D pad and soldered
there - or an offcut of resistor leg. Solder alone across two pads tends to ball up
rather than span them.

Check: 21C beeps to 21D; 23C beeps to the GND rail; 8B, 9B and 10B beep to nothing
around them.

#### 1.4 The GND jumper and the wires that leave the board

![Step 4](docs/breakout/step-4.svg)

Before the wires to the power button, find its terminals and the ring's polarity - steps
1 and 2 of [Order of work](#order-of-work) below. The jumper runs below row F, from 10C to
23D. Then the six wires: ① and ② to the ring,
③ and ⑥ to the power button's switch, ④ and ⑤ to the UPS switch pads. **④ and ⑤ are the
thick ones** - up to 1.5A from an unfused cell. Heat-shrink both ends of every wire.

Check: 10C beeps to the GND rail. ④ to ⑤ must not beep. On the diode range they read
about 0.5V one way: that is the MOSFET's body diode, and is expected.

#### 1.5 The button wires

![Step 5](docs/breakout/step-5.svg)

One wire per pad, ⑦ to ⑬, and ⑭ from the GND rail daisy-chained to the common leg of
every button.

Check: no pad beeps to its neighbours or to GND; each one beeps to GND while its button
is held.

### The power button

The 16mm button is momentary and does two jobs, wired separately: two terminals are the
soft latch's button (below), two more light the ring. The ring is the only thing on this
device that can say "starting" - the panel cannot be written until Linux is up, about
seventeen seconds in. See `docs/boot-time.md` for how that conclusion was arrived at.

### What the ring is for

`config.txt` carries `gpio=22=op,dh`, written by `setup-pi.sh --status-led-pin 22`. The
**firmware** applies that about a second after the button is pressed - before the kernel,
let alone the application - so the ring lights almost immediately. `main.py` then drives
the pin low once the first real screen is on the panel.

**Lit means starting. Dark means ready.** Which also keeps the enclosure dark while the
shutter is open, the same reason the Pi's own ACT LED is disabled. With the soft latch the
ring also says when to let go: it lights at the same moment the firmware takes over the
hold line.

### Wiring the button's LED ring as an indicator

The ring in the BOM is rated 3-6V (5V nominal), and a GPIO is 3.3V logic that should not
be asked for more than about 16mA. So the GPIO switches a transistor and the transistor
switches the ring (the schematic is under [Circuit diagrams](#circuit-diagrams)).

| Part | Value | Why |
|------|-------|-----|
| NPN transistor | BC337 or 2N3904 | Switches the 5V ring from a 3.3V pin. Either is far over-rated for ~20mA, which is what you want. |
| Base resistor | 1kΩ | ~2.5mA into the base. With any hFE over about 40 the transistor is fully on, and the GPIO stays well inside its limit. |
| Series resistor | 220-330Ω, **only if the ring has no built-in resistor** | Not needed for the ring in the BOM: a 3-6V rating is only possible with a resistor already inside. Putting a second one in series dims it; leaving one out of a bare LED destroys it. |

**Check the transistor's pinout before soldering, on the part you actually have.** This is
the mistake to make, and it cannot be answered from the part number alone: a 2N3904 in
TO-92 is Emitter-Base-Collector left to right with the flat face towards you, a BC547 is
Collector-Base-Emitter - the reverse - and BC337 datasheets disagree with each other
depending on who made it. Getting it backwards gives a ring that never lights and a
transistor that gets warm.

Two minutes with a multimeter settles it. On the diode range, the **base** is the one pin
that reads a junction to both of the others (about 0.7V). On an NPN the base is the
positive probe for both of those readings; the pin that reads slightly *higher* from the
base is the emitter.

### Order of work

1. **Identify the button's terminals** before anything is soldered. The two LED terminals
   are usually marked `+` and `-`; the switch terminals are `COM`, `NO` and `NC`. Put a
   multimeter on continuity across `COM` and `NO` and press the button: closed only while
   it is held. That is the pair the soft latch uses; `NC` stays unconnected.
2. **Test the ring on the bench** before it is in the circuit, to find its polarity. The
   3-6V ring in the BOM can take 5V straight across it. A ring without a rating goes
   through 330Ω first: bright means it has no resistor of its own, dim means it does.
3. **Solder the button first**, while it is loose and you can turn it over. Tin each wire,
   heat the terminal rather than the solder, and heat-shrink each joint: these are the
   joints that take the strain of the switch being pressed.
4. **The transistor lives on the breakout board** (step 1), not in mid-air: a dead bug of
   components hanging off a button will fail in a camera bag. Only the four wires ① ② ③ ⑥
   go to the button.

### Checking it

With the ring wired and nothing else changed:

```bash
# Lit from about a second after switch-on, until the first screen is drawn.
ssh nd-timer 'journalctl -u nd-timer -b | grep -i "status led"'
```

No output means the pin was claimed and the ring is being driven. A line saying
`status led on pin 22 unavailable:` means the app could not claim it - the ring will stay
lit, which is harmless but wrong, and the message says why.

To see the pin state directly, `raspi-gpio get 22` (from the `raspi-gpio` package). Note
the application holds that pin while it runs, so a second process reading it gets
`GPIO busy`.

### Not built yet: switching the power in software

The latching switch cuts the rail, so the Pi is never told it is about to lose power. That
is why there is no "shutting down" frame on the panel, and why the panel holds a stale
screen from the last session.

A soft latch fixes it: a momentary button starts the Pi, a P-channel MOSFET holds the rail
up, and the Pi drops it when it has finished writing to the panel. The momentary 16mm
button in the BOM replaces the latching one for this, so the ring stays on the same button.

It is one button on two GPIOs: a **hold** line the Pi drives to keep the rail up, and a
**sense** line it reads to know the button was pressed again. `setup-pi.sh
--shutdown-pin` is the sense half of this circuit, not a separate way of doing it.

**Where it goes.** On the Waveshare UPS HAT (C) the on-board ON/OFF slide switch - the
one the latching button replaced - does not switch the 5V. It switches the battery side
(SYS, about 3.0-4.2V, a little more while charging) into the TPS61088 boost converter that
makes the 5V. Its three pads, from Waveshare's schematic:

| Switch pad | Connects to | In the soft latch |
|------------|-------------|-------------------|
| **ON pin** (end) | SYS, the battery side | MOSFET Source, and the 100k |
| **Middle pin** | the boost converter's input | MOSFET Drain |
| **OFF pin** (other end) | the boost input too, same as the middle | nothing |

Sliding to ON joins the middle pin to the ON pin; sliding to OFF joins it to the OFF pin,
which is already the same wire, so nothing is powered. The latching button is across the
ON and middle pins now, and the soft latch goes on the same two. That leaves the pogo pins
alone, and with the boost converter unpowered it stops drawing from the cell while stored.

**The OFF pin is not used - leave it unconnected.** It has no job: the switch has three
legs and the circuit only needs two, which is presumably why Waveshare tied the spare one
to the middle pin.
Charging does not go through it either. The charger sits before the switch, between the
micro-USB and the battery, so the cell still charges with the Pi off.

The schematic does not say which end of the board is which, so measure before soldering:
with the latching button released, the ON pin reads battery voltage to GND, and the
middle and OFF pins read about 0V. The schematic is under [Circuit diagrams](#circuit-diagrams).

- **Starting:** the button pulls the gate low through its diode and the rail comes up.
  The hold line gets `gpio=16=op,dh`, so the firmware asserts it about a second in and you
  let go then - a hold-to-start of roughly a second, which is normal for this kind of
  circuit.
- **Stopping:** a second press pulls the sense GPIO low through the other diode, and
  `gpio-shutdown` starts a clean poweroff - which is when the shutdown frame gets drawn.
  At the very end `dtoverlay=gpio-poweroff,gpiopin=16,active_low=1` drops the hold line
  and the rail goes with it.
- **The two diodes** both point at the button: stripe (cathode) on the button side. It
  needs two. While the Pi runs, the BC337 holds the gate at about 0V; with one diode the
  button's side would sit there too, and hold the sense GPIO near its threshold the whole
  time. With two, the released button's side is connected to nothing, so the sense GPIO
  stays high until the button is actually pressed. The sense diode also keeps SYS, up to
  about 4.4V, off a 3.3V pin while the Pi is off.
- **Schottky, not silicon.** A pressed button leaves the sense GPIO at the diode's forward
  voltage: about 0.2-0.3V through a BAT85, 0.5-0.6V through a 1N4148 or 1N4001. The Pi
  reads below about 0.8V as low, so both work, but the Schottky leaves the margin.
- **Gate drive and heat.** The gate sees SYS, not 5V, so the MOSFET is driven with only
  3.0-4.2V. The AO3401 is specified down to 2.5V (about 85mΩ there), which is why it is
  the one to buy. Current is also higher on this side of the boost: about 0.4A
  typically, up to about 1.5A for a 1A load on a nearly flat cell. That is about 0.2W,
  some 25°C over ambient on a SOT-23 - no heatsink, and the adapter's copper helps.

The sense pin is not pin 3 on this build, for the reason in `setup-pi.sh --help`: it is
I2C SCL, which the UPS HAT's fuel gauge needs. Pin 3's wake-from-halt is no use here
anyway, because the soft latch removes power rather than halting. `setup-pi.sh` does not
write the `gpio-poweroff` line yet.

The latching button comes off the ON and middle pins and the soft latch is the only switch.
Off, the MOSFET leaks microamps, so storage drain is about what a hard switch gives.

</details>

# Bill of Materials
<details>
<summary>Show the parts list</summary>

- five way button\
  <img width="200" alt="17849727845893738776011421435184" src="https://github.com/user-attachments/assets/b6a12755-35c8-49f5-8064-88f008445e4b" />

- Raspberry Pi Zero 2 W, it needs linux for gphoto2. A plain Pi Zero works too, on the same card, but is ready in ~25s against ~11.5s: the boot is CPU-bound, and the Zero 2 W has four cores to the Zero's one (see `docs/boot-time.md`)
- 2.13'' E-paper display
- UPS HAT for Raspberry Pi Zero with 1000mah battery\
  <img width="200" alt="image" src="https://github.com/user-attachments/assets/cb306792-c2a6-40d5-bd81-8b63f4ea3967" />

- power button 16mm diameter (momentary 1NO1NC, LED ring 3-6V, 5V nominal), for the soft latch\
  <img width="200" alt="powerbutton" src="https://github.com/user-attachments/assets/a33f7c25-f148-4ec7-9226-96dd3c6ffadc" />

- 2x BC337 NPN transistor (TO-92): one for the power button ring, one for the soft latch
- AO3401 P-channel MOSFET (SOT-23-3), for the soft latch (not built yet)
- SOT23-3 to DIP SIP3 adapter, so the MOSFET fits on perfboard
- resistors: 1x 1kΩ (ring transistor base), 2x 10kΩ and 1x 100kΩ (soft latch)
- 2x BAT85 Schottky diode (DO-35), for the soft latch
- Pi Zero Breakout board\
  <img width="200" alt="KW-1815_0-1400x1050h" src="https://github.com/user-attachments/assets/e4e68370-e5f6-4e82-ae2e-4a0d5db21cb6" />

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

</details>
