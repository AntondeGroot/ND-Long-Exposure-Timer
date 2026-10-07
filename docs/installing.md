# Installing on a Pi, in detail

The README has the commands; this is why each step exists, and what to do when the panel looks wrong.

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
