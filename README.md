# ND Long Exposure Timer

A small box on your camera's hot shoe for long exposures with ND filters. You pick the
exposure time you want; it tells you which filters to put on and sets the ISO and
aperture to match. No maths, no guessing.

**Try it in your browser:** https://antondegroot.github.io/ND-Long-Exposure-Timer/

![The main screen](docs/screens/main-waterfall@3x.png)

How it works:
1. Meter the scene on your camera as usual and press **SYNC**.
2. Pick the total exposure time.
3. Screw on the filters it lists and press **SHOOT**.

## Controls

| Control | Does |
|---------|------|
| Five-way | move |
| Five-way centre | select |
| SYNC | read the exposure from the camera |
| SHOOT | start the shot; hold to cancel |

What every screen means: [docs/screens.md](docs/screens.md).

## 1. Buy

<details>
<summary>Show the parts list</summary>

| Part | Qty |
|------|-----|
| Raspberry Pi Zero 2 W (a plain Zero works, but boots in ~25s instead of ~11s) | 1 |
| 2.13" e-paper display HAT | 1 |
| UPS HAT for Pi Zero, with 1000mAh cell | 1 |
| Breakout Pi Zero (AB Electronics) | 1 |
| Five-way navigation button | 1 |
| 16mm momentary power button with LED ring (1NO1NC, 3-6V ring) | 1 |
| 12x12mm momentary tactile button (TLYCRQJXF), for SYNC and SHOOT | 2 |
| BC337 NPN transistor (TO-92) | 2 |
| AO3401 P-channel MOSFET (SOT-23) + SOT-23 to SIP3 adapter | 1 |
| BAT85 Schottky diode | 2 |
| Resistors: 1kΩ, 10kΩ, 10kΩ, 100kΩ | 4 |
| USB-C power-only socket | 1 |
| Micro-USB solder plug, 5 pin | 1 |
| USB-A socket, 4 pin | 1 |
| USB-A to camera cable (UC-E6 / UC-E16 / UC-E17) | 1 |
| 1/4" hot shoe mount | 1 |
| Clear acrylic sheet, 1mm thick, at least 55x30mm | 1 |

Five-way button\
<img width="160" alt="five-way button" src="https://github.com/user-attachments/assets/b6a12755-35c8-49f5-8064-88f008445e4b" />

UPS HAT\
<img width="160" alt="UPS HAT" src="https://github.com/user-attachments/assets/cb306792-c2a6-40d5-bd81-8b63f4ea3967" />

Power button\
<img width="160" alt="power button" src="https://github.com/user-attachments/assets/a33f7c25-f148-4ec7-9226-96dd3c6ffadc" />

Breakout board\
<img width="160" alt="Breakout Pi Zero" src="https://github.com/user-attachments/assets/e4e68370-e5f6-4e82-ae2e-4a0d5db21cb6" />

USB-C socket\
<img width="160" alt="USB-C socket" src="https://github.com/user-attachments/assets/645d8d48-21d6-4195-a56d-52074ed21b96" />

Micro-USB plug\
<img width="160" alt="micro-USB plug" src="https://github.com/user-attachments/assets/4b83c40a-3927-49ab-8324-e03e0da98926" />

USB-A socket\
<img width="160" alt="USB-A socket" src="https://github.com/user-attachments/assets/32fce523-0029-4b52-a5a5-c7ed3eab73d9" />

Tactile button\
<img width="160" alt="tactile button" src="https://github.com/user-attachments/assets/a8823ef3-7dc4-4e2d-9e30-258b56376464" />

Hot shoe mount\
<img width="160" alt="hot shoe mount" src="https://github.com/user-attachments/assets/daab8fbc-d2e3-43ca-9c25-478450506ead" />

Acrylic sheet\
<img width="160" alt="clear acrylic sheets" src="https://github.com/user-attachments/assets/01a9c53f-c7d5-4f04-ac88-26bfdfb01c78" />

</details>

Tools: soldering iron, multimeter, 3D printer.

## 2. Print

The enclosure files are not in the repo yet.

## 3. Solder

<details>
<summary>Show the soldering steps</summary>

Everything goes on the breakout board. Holes are column then row: `21C` is column 21,
row C. Each column has two separate strips, rows A-C and D-F. Numbered circles are wires
that leave the board.

![The whole build](docs/breakout/overview.svg)

Before you start, find the power button's terminals with the multimeter: `+`/`-` for the
ring, and the `COM`/`NO` pair that closes only while pressed. `NC` is not used.

Check each step with the multimeter before the next one.

### 3.1 Resistors and diodes

![Step 1](docs/breakout/step-1.svg)

Stand them up. The GPIO legs go straight into the pads. Diode stripes face column 18.

Check: 21C does not beep to 21D yet.

### 3.2 MOSFET

![Step 2](docs/breakout/step-2.svg)

Check on the adapter that the pin in 21E is the gate and the middle one the source.

Check: 19E, 20E and 21E don't beep to each other.

### 3.3 Transistors and the bridge

![Step 3](docs/breakout/step-3.svg)

Measure each BC337's pinout first; makers differ. On the diode range the base reads about
0.7V to both other legs, and the emitter reads slightly higher than the collector.
Emitters go right. Then, underneath, bend the collector leg from 21C onto 21D and solder
it.

Check: 21C beeps to 21D, and 23C beeps to GND.

### 3.4 Wires

![Step 4](docs/breakout/step-4.svg)

The green jumper runs under row F. ④ and ⑤ go to the UPS HAT's old power switch pads and
carry up to 1.5A: use thick wire. With the switch off, the ON pad reads battery voltage,
the middle pad 0V. Heat-shrink every joint.

Check: 10C beeps to GND; ④ and ⑤ don't beep to each other.

### 3.5 Buttons

![Step 5](docs/breakout/step-5.svg)

One wire per pad, and one ground wire from ⑭ chained to every button's common leg.

Check: each pad beeps to GND only while its button is pressed.

How the circuits work, with schematics: [docs/power-button.md](docs/power-button.md).
The drawings are generated: edit `scripts/breakout_drawing/layout.py` and run
`./scripts/draw-breakout.py`.

</details>

## 4. Install

<details>
<summary>Show the install steps</summary>

On a Mac, with a blank SD card. Plug the Pi into the **middle** micro-USB port (`USB`),
not `PWR IN`: that one carries no data.

```bash
sudo ./scripts/flash-sd.sh ~/Downloads/raspios-lite.img.xz   # asks for a password for `pi`
# put the card in the Pi and plug it in; it shows up as 10.55.0.1
ssh-copy-id -i ~/.ssh/pi_deploy_key.pub pi@10.55.0.1
sudo ./scripts/share-internet-macos.sh                       # the Pi has no network of its own
./scripts/deploy-to-pi.sh
ssh -t pi@10.55.0.1 'cd ~/ND-Long-Exposure-Timer && sudo ./scripts/setup-pi.sh --status-led-pin 22 --shutdown-pin 12'
ssh pi@10.55.0.1 'sudo systemctl reboot'
./scripts/deploy-to-pi.sh
ssh -t pi@10.55.0.1 'sudo systemctl enable --now nd-timer'
```

`setup-pi.sh` takes 15-30 minutes. After that, `deploy-to-pi.sh` is the only thing to
rerun when the code changes.

With the soft latch built, the reboot switches the device off. Press the power button to
start it again.

What each step does, and what to do if the panel looks wrong: [docs/installing.md](docs/installing.md).

</details>

## Development

Run it on a laptop with `./scripts/simulator.py`, or use the browser link above. Tests,
lint and the rest: [docs/development.md](docs/development.md).

<img width="1200" height="909" alt="st" src="https://github.com/user-attachments/assets/fd1fa2b8-39ee-4ffa-a240-2bdcc5c6d658" />
<img width="679" height="559" alt="71zk6QDncoL _AC_SX679_" src="https://github.com/user-attachments/assets/0335222b-765e-4fe0-838f-ae89e64db8e9" />

