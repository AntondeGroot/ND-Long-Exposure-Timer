# Boot time

A running log of what the boot costs, what we changed, and what we learned chasing
the failures we found on the way. Kept as we go so the eventual write-up does not
have to be reconstructed from memory.

Measured with `systemd-analyze` on the device over the USB link (`ssh nd-timer`),
or `scripts/speed-up-boot.sh --measure`, which prints the same three views.

## Measurements

| Date | Total | Kernel | Userspace | Notes |
|---|---|---|---|---|
| (baseline, stock card) | **1m44s** | - | - | `sysinit.target` waited on cloud-init until 59s; NetworkManager another 21s on the critical path. Recorded in `README.md`. |
| 2026-09-24 | **58.4s** | 11.6s | 46.8s | `multi-user.target` at 43.7s. Safe set of `speed-up-boot.sh` applied (state file dated 18:50). cloud-init and NetworkManager gone from the critical chain. |
| 2026-09-24 (reboot) | **1m5.2s** | 11.2s | 54.0s | Same card, nothing changed but `StandardError=journal`. `multi-user.target` at 43.3s. **Boot-to-boot variance is about 7s in userspace, so a single measurement means little** - compare medians, not runs. |
| 2026-09-24 (early splash) | **52.5s** | 11.1s | 41.4s | First boot on the new ordering. `multi-user.target` at 41.3s. The splash started at **24.8s** instead of 40.4s - and failed, so its 18s is not in this number. |
| 2026-09-25 (splash as root) | **52.6s** | 11.2s | 41.5s | The splash works: 9.10s as a unit, 5.75s inside `main()`, frame on the panel at ~28.5s. `multi-user.target` 41.4s. |

## What we changed

- **`speed-up-boot.sh`, safe set** - disables the wait-online units, Bluetooth,
  ModemManager and triggerhappy, masks `rpi-resize-swap-file` (19s measured, for a
  swap file nothing on this image ever uses), disables cloud-init via its flag file
  and sets `boot_delay=0`. Roughly 1m44s -> 58s. `--restore` puts it all back.
- **Boot splash** (`install-boot-splash.sh`) - pushes a buffer packed at build time
  as soon as SPI exists, importing the panel driver and nothing else. It does not
  make the boot faster; it removes the blank panel that reads as a dead device.
- **2026-09-24: `StandardError=journal` on `nd-timer-splash.service`** - the unit
  logged stdout only, so a driver traceback reached the journal as its first line
  and nothing more. See below.
- **2026-09-24: `Storage=persistent` for journald** (drop-in) - the card shipped
  `Storage=volatile`, so each reboot destroyed the evidence of the boot before it.
  Nothing intermittent at boot was diagnosable until this. Consider capping it with
  `SystemMaxUse=` so a log cannot grow into the card.
- **2026-09-24: stage timings in `boot_splash.py`** - `timed()` prints what the
  driver import, the pin claim, `init()`, `display()` and `sleep()` each cost, to
  stderr and so to the journal. Diagnostic, not a speed-up: 18s of the boot had no
  breakdown at all.
- **2026-09-24: the splash starts early** - the unit already had
  `DefaultDependencies=no`, but `After=local-fs.target` held it to 40.4s, because
  that target waits for every fstab mount and the `/boot/firmware` fsck alone runs
  to 26s. It is now ordered on `-.mount` and `systemd-journald.socket` only: the
  root filesystem, which systemd is already running from, and somewhere to log.
  `ConditionPathExists=/dev/spidev0.0` had to go with it - that early the node may
  not exist, and as a condition it would silently skip the splash - so
  `boot_splash.py` waits up to 20s for it instead.
- **2026-09-24: `nd_timer/fast_panel.py`** - the same command sequence as
  `waveshare_epd.epd2in13_V4`, over the same SPI settings, with the four pins driven
  through `lgpio` directly. Worth ~9s of the splash: the vendor driver's
  `epdconfig` imports *and instantiates* `gpiozero` at import time. `main.py` had
  already declined gpiozero for the buttons, for a different reason (its lgpio
  backend busy-loops), so this is the same trade a second time. Pinned by a
  transcript test, because saying exactly what the vendor said is the only thing
  that makes it safe.
- **2026-09-24: `TimeoutStartSec` 20s -> 60s** - 1.45s of margin against a unit
  measured at 18.55s, and a oneshot that times out is logged as a failure. Nothing
  is ordered after the splash, so a generous timeout costs the boot nothing.

## Open: the splash is the largest unit in the boot, and it intermittently throws

Found 2026-09-24 while measuring.

```
17.409s nd-timer-splash.service     <- largest unit in the boot
```

Two separate problems behind that number.

**1. It runs too late to do its job.** The unit is `WantedBy=basic.target`, which is
reached at 32.0s, so it is not on the critical path and costs the boot nothing. But
it starts at 40.9s and exits at 58.4s, so the frame reaches the panel at about 58s -
after the boot it exists to cover. `nd-timer.service` itself starts at 44.2s.

**2. The splash and the app fight over the GPIOs.** Those two windows overlap by
about 14 seconds, and both processes claim the same pins through `gpiozero`
(RST 17, DC 25, PWR 18, BUSY 24 - `waveshare_epd/epdconfig.py`). Only one process
can hold them. Reproduced from the Mac while the app was running:

```
$ ssh nd-timer '.venv/bin/python -c "import gpiozero; gpiozero.LED(17)"'
lgpio.error: 'GPIO busy'
```

`boot_splash.py` also never closes the devices - it calls `panel.sleep()` and lets
the process exit - and `gpiozero.Button(BUSY)` runs a background thread, which is
the `Thread-1` in the journal line. Whether the boot-time exception is the same
`GPIO busy` or the teardown race is the next thing to confirm.

**3. It did not reproduce.** With `StandardError=journal` in place, the next boot
logged no exception at all - the splash ran clean, `Result=success`, and the app
started at 43.4s inside the same 40.1s-58.5s splash window as before. So it is a
race, not a deterministic failure, and it loses a coin flip somewhere between the
two processes claiming the pins.

**The evidence from the first occurrence is gone**, because the journal on this card
is volatile: `journalctl --list-boots` lists only the current boot. Nothing about an
intermittent *boot* failure can be diagnosed under that, so the next step is
`Storage=persistent` in `/etc/systemd/journald.conf`, and then boots can be
compared.

**Urgent, independent of the race:** `TimeoutStartSec=20` against a run that took
17.4s on one boot and **18.35s** on the next. That is 1.65s of margin. A oneshot
that hits its timeout is reported as a *failure*, not the harmless skip the comment
above it promises - and on a slower card or a colder start it will hit it.

The application logs nothing but `Started nd-timer.service`, so there is currently
no way to see when it initialises the panel relative to the splash. Timing the
splash's own stages (import, `init`, `display`, `sleep`) is the cheapest way to find
out where the 18s actually goes; nothing yet says which stage dominates.

## Where the rest of the 58s goes

The critical chain is dominated by waiting for the SD card, not by services:

```
local-fs.target @29.254s
  boot-firmware.mount @28.928s +313ms
    systemd-fsck@...partuuid-1fd4e3ab-01.service @26.442s +2.361s
      dev-disk-by-partuuid-1fd4e3ab-01.device @26.406s
```

Roughly half the boot elapses before userspace has a filesystem
(`dev-mmcblk0p2.device` alone is 14.1s in `blame`). After that,
`usb0-static.service` costs 5.2s inside `network-pre.target`, which pushes
`multi-user.target` back by about the same - and it exists for a cable that is
usually not attached.

Not yet investigated: whether the card wait is the card itself, the fsck, or
kernel-side probing, and whether `usb0-static` can come up without blocking
`network-pre.target`.

## Measured breakdown of the splash, 2026-09-24

From the stage timings, before any of the above landed:

```
    import driver: 9.20s      <- gpiozero (2.97s idle), spidev, pin claims,
    claim pins: 0.01s            two forked shells for board detection
    init: 0.08s
    display: 2.37s            <- the actual panel refresh
    sleep: 2.02s              <- the controller's own settling time
splash on the panel in 13.69s
```

The unit took 18.55s against main()'s 13.69s, so ~4.9s is interpreter start,
`python -m` import machinery and process teardown. `nd_timer/__init__.py` is empty,
so none of it is the application's own weight.

**Only 4.5s of 18.5s was the panel.** The rest was Python and gpiozero - and it cost
9.2s at boot against ~4s on an idle Pi, because this is a single core competing with
every other service starting.

## Still to do

- Verify the two changes above on a real boot: expected start ~10s rather than 40.4s,
  and the splash's own cost down from 18.5s to roughly 5-6s.
- The SD card and `/boot/firmware` remain the largest thing in the boot: about half
  of it elapses before `local-fs.target`. `x-systemd.automount` in fstab would stop
  everything waiting on a partition nothing needs at runtime. Measure first.
- `usb0-static.service` costs ~5s inside `network-pre.target`, for a cable that is
  usually not attached.
- The `Thread-1` exception has not recurred. The persistent journal will catch it if
  it does - though `fast_panel.py` removes the gpiozero thread that raised it, so it
  may already be gone.

## The early start exposed a permissions race, 2026-09-24

The first boot on the new ordering did start early - 24.8s, against 40.4s before -
and then died with the traceback the logging change was added to catch:

```
    wait for spi: 0.00s
    open panel: 1.05s
lgpio.error: 'can not open gpiochip'
```

`/dev/gpiochip0` is `crw-rw---- root gpio` and `pi` is in the `gpio` group, so this
works perfectly at any normal time. But the node is created root-only and only then
chowned by `99-com.rules`, and at 24.8s the splash arrives in between. The
application never saw it because it starts at 43s.

The fix is not to start later - that was the whole problem - but to keep asking:
`_open_chip_when_ready()` retries `gpiochip_open` for up to 20s. A first attempt
failing is the normal case at this point in the boot, not a fault. Pinned by a test
with a fake lgpio that refuses a given number of times.

Worth remembering as a general shape: **everything this unit needs, it may now
arrive before.** `/dev/spidev0.0` was already waited for; the GPIO chip's
*permissions* were the second. A third may be lurking.

## Why it ran as `pi` at all, and the noise on the panel, 2026-09-24

The second boot on the new ordering got past the GPIO chip and died on the bus:

```
    wait for spi: 0.00s
    open panel: 15.98s
PermissionError: [Errno 13] Permission denied     <- spi.open(0, 0)
```

Two things came out of that.

**The wait told us when udev actually lands.** The chip retry succeeded after 16s,
from a 24.8s start - so the group ownership of `/dev/gpiochip0` and `/dev/spidev0.0`
arrives around 41s, applied by `systemd-udev-trigger`'s coldplug pass. As `pi` this
unit therefore *cannot* run before ~41s however it is ordered, which is the whole
thing we were trying to fix. So the splash now runs as **root**, which has both
devices from the moment the nodes exist. It is one oneshot pushing a fixed buffer
down SPI; the application keeps its own user.

**The half-opened splash garbled the panel.** Before dying it had claimed RESET, DC
and POWER as outputs at level 0 - RESET is active low, so that asserted reset - and
held them from ~41s until it exited at 46.1s. The application started at 43.7s,
inside that window, and initialised a controller that was being held in reset:
random RAM, then a refresh of it. Random black and white pixels, exactly as
reported. Three changes follow from it:

- the bus is opened *before* any pin is claimed, so a splash that cannot proceed has
  touched nothing;
- RESET is claimed **high** - idle - rather than low;
- any failure part-way through calls `abandon()`, which closes the chip and returns
  the pins to inputs instead of leaving them asserted. Pinned by a test.

Lesson worth keeping: on a shared panel, *claiming* a pin is already an action the
other process can see. Failing safe means failing without having claimed anything.

## Where it got to, 2026-09-25

The splash runs clean, as root, on the direct transport:

```
    wait for spi: 0.00s
    open panel: 1.25s
    init: 0.06s
    display: 2.33s
    sleep: 2.10s
splash on the panel in 5.75s
```

| | before | now |
|---|---|---|
| splash unit | 18.55s | 9.10s |
| inside `main()` | 13.69s | 5.75s |
| opening the panel | 9.20s vendor import, then 21.13s waiting for udev as `pi` | 1.25s |
| splash window | 40.4s - 58.5s | 24.9s - 34.1s |
| frame on the panel | ~52s | ~28.5s |
| boot | 59.99s | 52.6s |

**The overlap is gone.** The application starts at 43.8s, 9.8s after the splash has
finished and let the pins go, so the two processes no longer contend for the panel
at all - which also means the intermittent `Thread-1` exception has had its cause
removed rather than merely not recurring.

Note the unit is 9.10s against 5.75s inside `main()`: ~3.3s of interpreter start and
teardown. Some of that was this boot only - running as root, Python had to write
fresh `__pycache__` - so it is worth re-measuring before treating it as fixed cost.

### The next thing to understand

The splash starts at 24.9s, but `systemd-analyze critical-chain` says everything it
waits for is ready at 12.2s:

```
nd-timer-splash.service +9.099s
└─systemd-journald.socket @12.171s
  └─-.mount @11.731s
```

Nothing explains that 12.7s gap in ordering terms. The likely answer is simply that
one ARMv6 core is saturated between 12s and 25s - udev, journald and the fsck are all
in flight - so the job is runnable but not run. If that is it, the frame cannot move
much earlier without taking work *away* from that window, which points back at the
`/boot/firmware` mount and `usb0-static` rather than at the splash.
