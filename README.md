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
- let you choose the total exposure time
- it will tell you what filters you need to put on
- it will automatically determine the ISO and aperture settings needed for the long exposure within a given range.

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

The time is at the top because it is the one thing you choose. Under it, a band saying
who is choosing everything else. Then **base**, the shutter the camera was reading when
you pressed SYNC - a measurement, which nothing the device does moves - and the answer
to your time, read down the column: the ISO and aperture to set, the filters to screw
on, and how close that lands. At 122 pixels wide there is no room for a label beside its
value, so each row stacks them.

Nothing on screen says SHOOT. It is a button under your thumb, and a panel that drew it
would be spending its own space saying what the hardware already says.

![The main screen](docs/screens/main-waterfall@3x.png)

Past 30 seconds the shot has to run on bulb, and the panel says so - the Pi is the timer
from that point on.

![The main screen showing a bulb exposure](docs/screens/main-bulb@3x.png)

Before the first SYNC there is no scene to work back from, and the device says that
rather than printing a recipe it cannot stand behind.

![The main screen before syncing](docs/screens/main-not-synced@3x.png)

### The battery

The UPS HAT carries an INA219, which measures volts and amps rather than charge -
there is no gauge on the board modelling the cell - so the percentage is inferred
from cell voltage. That is a cruder thing than it looks: a lithium cell sits near
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

The five-way, SYNC and SHOOT are on the page and on the keyboard, and the picture
served is the exact 122 x 250 buffer the panel would be holding. The three values
SYNC reads sit beside it, so a scene can be metered with no camera on the desk,
and the clock can be run fast while the shutter is open - a six-minute exposure
is worth watching at 60x rather than in real time.

What the buttons drive is `nd_timer/device.py`, the state machine the Pi runs:
presses arrive as method calls and the clock arrives as an argument, so the panel
driver and gphoto2 are the only parts the simulator stands in for. The solving
itself is `nd_timer/recipe.py`, which is where the time becomes a filter stack.

## Installing on a Pi

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

## Wiring the power button

The 16mm button does two jobs and they are wired separately: three terminals switch the
power, two more light the ring. The ring is the only thing on this device that can say
"starting" - the panel cannot be written until Linux is up, about seventeen seconds in,
and a latching switch cuts the rail so nothing runs at power-off to leave a message
either. See `docs/boot-time.md` for how that conclusion was arrived at.

### What the ring is for

`config.txt` carries `gpio=22=op,dh`, written by `setup-pi.sh --status-led-pin 22`. The
**firmware** applies that about a second after the switch is flipped - before the kernel,
let alone the application - so the ring lights almost immediately. `main.py` then drives
the pin low once the first real screen is on the panel.

**Lit means starting. Dark means ready.** Which also keeps the enclosure dark while the
shutter is open, the same reason the Pi's own ACT LED is disabled.

### Wiring the button's LED ring as an indicator

The ring in the BOM is rated 3-6V (5V nominal), and a GPIO is 3.3V logic that should not
be asked for more than about 16mA. So the GPIO switches a transistor and the transistor switches the ring:

```
                      5V (header pin 2)
                              │
                          220-330Ω    optional: not needed for the 3-6V
                              │           ring, only for a bare LED
                              +
                        ┌─────┴─────┐
                        │ LED  ring │
                        └─────┬─────┘
                              -
                              │
                          Collector
                          ┌───┴───┐
     GPIO22 ── 1k ── Base │ BC337 │
     (pin 15)             └───┬───┘
                           Emitter
                              │
                     GND (header pin 6)
```

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
   multimeter on continuity across `COM` and `NO` and press the button: closed when
   latched in, open when out. That is the pair the power goes through.
2. **Test the ring on the bench** before it is in the circuit, to find its polarity. The
   3-6V ring in the BOM can take 5V straight across it. A ring without a rating goes
   through 330Ω first: bright means it has no resistor of its own, dim means it does.
3. **Solder the button first**, while it is loose and you can turn it over. Tin each wire,
   heat the terminal rather than the solder, and heat-shrink each joint: these are the
   joints that take the strain of the switch being pressed.
4. **Build the transistor on a scrap of perfboard**, not in mid-air. Three wires leave it:
   5V, GND, and the GPIO. A dead bug of components hanging off a button will fail in a
   camera bag.
5. **Tap the header last.** GPIO22 is physical pin 15, 5V is pin 2, GND is pin 6. Both
   HATs sit on that header, so take these from the stacking header's pass-through pins or
   from a spare set - do not unsolder anything on the UPS HAT to get at them.

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
up, and the Pi drops it when it has finished writing to the panel. Two of the momentary
buttons in the parts list are already spare.

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
middle and OFF pins read about 0V.

```
                                  (AO3401)
     switch ON pin ──┬──── Source ┌───────┐ Drain ──── switch middle pin
                     │            │ P-FET │
                     │            └───┬───┘
                   100kΩ             Gate
                     │                │
                     └────────────────┤
                                      │
                ┌─────────────────────┤
                │                     │
               10kΩ               Collector
                │                 ┌───┴───┐
                │                 │ BC337 │ Base ── 10kΩ ── hold GPIO
                │                 └───┬───┘                 (gpio=N=op,dh + gpio-poweroff)
                ▼  BAT85           Emitter
               ───                    │
                │                    GND
                │
                ├──|◄── sense GPIO (gpio-shutdown)
                │  BAT85
                │
                └── momentary button ── GND
```

- **Starting:** the button pulls the gate low through its diode and the rail comes up.
  The hold line gets `gpio=N=op,dh`, so the firmware asserts it about a second in and you
  let go then - a hold-to-start of roughly a second, which is normal for this kind of
  circuit.
- **Stopping:** a second press pulls the sense GPIO low through the other diode, and
  `gpio-shutdown` starts a clean poweroff - which is when the shutdown frame gets drawn.
  At the very end `dtoverlay=gpio-poweroff,gpiopin=N,active_low=1` drops the hold line
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

The latching button can stay as a master isolator for storage, in series: ON pin → latching
button → MOSFET → middle pin. Or it can go, and the soft latch is the only switch.

# Bill of Materials
- five way button\
  <img width="200" alt="17849727845893738776011421435184" src="https://github.com/user-attachments/assets/b6a12755-35c8-49f5-8064-88f008445e4b" />

- Raspberry Pi Zero, it needs linux for gphoto2 
- 2.13'' E-paper display
- UPS HAT for Raspberry Pi Zero with 1000mah battery\
  <img width="200" alt="image" src="https://github.com/user-attachments/assets/cb306792-c2a6-40d5-bd81-8b63f4ea3967" />

- power button 16mm diameter (latching 3 pole 1NO1NC, LED ring 3-6V, 5V nominal)\
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

