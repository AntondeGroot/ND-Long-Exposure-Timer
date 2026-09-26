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
| 2026-09-25 (hardware trimmed) | **53.1s** | 10.9s | 42.2s | `--no-unused-hardware` applied: ~15 fewer modules, **no measurable change**. Inside the boot-to-boot variance. |
| 2026-09-26 (firmware trimmed) | **49.7s** | **3.09s** | 46.6s | Initramfs dropped, probes off, `quiet`. Kernel phase 10.9s -> 3.09s. Splash frame on the panel at **~20.7s**, was ~28.5s. |

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

## The kernel's 11.2s is mostly hardware this device has not got, 2026-09-25

Asked whether a slim kernel would help. It would, but it is the wrong tool: the
cost is not the size of the kernel, it is what gets probed and loaded. The largest
gaps between consecutive kernel messages on this card:

```
+7.08s  bcm2835-codec: Loaded V4L2 encode_image
+1.05s  rpi-gpiomem: initialised 1 regions
+0.53s  videodev: Linux video capture interface
+0.42s  snd_bcm2835: module is from the staging directory
+0.35s  bcm2835_mmal_vchiq
+0.30s  bcm2835_isp
+0.27s  bcm2835-codec: Loaded V4L2 decode
+0.24s  vc4-drm soc:gpu: bound 20c00000.v3d
```

A V4L2 image encoder, an ISP, an HDMI input and a DRM stack, on a timer whose
camera is a DSLR on USB and which has no screen or speaker. `lsmod` carries about
forty modules for them. Four lines in `config.txt` are responsible:

```
camera_auto_detect=1        -> bcm2835_codec, bcm2835_isp, mmal_vchiq, v4l2, videodev, videobuf2_*, mc
display_auto_detect=1       -> drm, drm_kms_helper, cec, backlight
dtoverlay=vc4-kms-v3d       -> vc4, the DRM stack, snd_soc_hdmi_codec
dtparam=audio=on            -> snd_bcm2835, snd_pcm, snd_soc_core, snd_timer
```

`speed-up-boot.sh --no-unused-hardware` now comments those out in place - in place
rather than overridden, because a `dtoverlay=` earlier in the file wins whatever
follows it - marked with `#nd-timer-off# ` so anyone reading the file in a card
reader can see what did it. `--restore` strips the marker back off; the round trip
is byte-exact. It costs the HDMI console, which is why it is behind its own flag
rather than in the default set.

Not measured yet. Cross-compiling a trimmed kernel remains an option afterwards,
but it means redoing it on every kernel update, and it would be trimming code that
is mostly not what costs the time.

### Where the wait actually is now

`nd-timer.service` does not start until **43.9s** - it waits for
`multi-user.target` (41.4s), and as `pi` it could not start before udev has chowned
the GPIO and SPI nodes anyway (~32-41s). So the splash at ~28s is papering over a
45s wait for the real screen, and the ordering of the application is the next
thing worth attacking after the hardware trim.

### And a better idea than drawing faster

E-paper is bistable, which the splash already relies on. So the frame that says the
device is starting does not have to be written after power-on: write it as the last
thing before power-off and it is on the panel at t=0, for free. Two catches - there
is no `gpio-shutdown` configured on this card, so a yanked power cable never gets
to write it (`setup-pi.sh --shutdown-pin 3` exists for that), and the application is
stopped with SIGINT, which is where the drawing would go. The boot splash stays as
the recovery path for an unclean shutdown.

Note the ACT LED is deliberately off (`act_led_trigger=none`, `act_led_activelow=on`)
- presumably light discipline for long exposures - so it is not available as an
instant "starting" indicator.

## The trim bought nothing, and the reason matters, 2026-09-25

`--no-unused-hardware` worked - all five lines commented, modules down from ~58 to
42 - and the boot did not move: 53.1s against 52.6s, well inside variance. Those
module loads were never on the critical path; they happened alongside work that
gated the boot anyway.

Two corrections to what I assumed earlier:

- **Removing an *enable* is not a *disable*.** `bcm2835_codec`, `bcm2835_isp`,
  `snd_bcm2835` and friends still load, with use-count 0, because those devices come
  from the base device tree rather than from `camera_auto_detect`. Stopping them
  needs `dtparam=audio=off` and `modprobe.d` blacklists - which, given the above, is
  not worth doing.
- **The 7s "variance" is not noise about nothing.** It is page cache and card luck,
  which is the same finding as everything below.

### What actually gates the boot: the card

```
4k direct reads     ~1040 IOPS (0.96 ms each)
16k                 10.8 MB/s
sequential          17.6 MB/s
read during boot    174 MB          <- at 10-17 MB/s, that is 10-17s of pure I/O
card                SK32G
```

And the shape of the boot agrees: `init.scope` - the scope holding PID 1 - does not
start until **22.8s**, so ~11s is kernel and ~12s is systemd's own startup, before
one service has run. Both are reading from this card. `dev-mmcblk0p2.device` being
the largest entry in `blame` is the same fact from another angle.

**So software tuning has reached diminishing returns.** 1m44s -> ~53s came from
cloud-init, NetworkManager, the swap resize and the unit ordering. What is left is
I/O: 174MB read at ~1000 IOPS. The levers that remain are a faster card (an A2-rated
card is 3-5x on random reads, where this is slow), or reading less - which means a
materially smaller root filesystem, not a shorter unit list.

### Which makes the shutdown frame the real answer

The original complaint was "show me it is starting", and no amount of this gets the
panel painted before ~11s, because that is when the kernel hands over. Writing the
frame *before power-off* answers it completely: the panel is bistable, so the image
is there at t=0, with no boot cost at all. That is the next thing to build, and it
makes the boot's absolute length a separate, lower-stakes question.

## What two published write-ups add, 2026-09-26

Read KittenLabs' "Extreme Pi Boot Optimization" (Zero 2 W, 12s -> 3.5s, every claim
measured with a power profiler and an SD-card mux) and Himesh's "Fast boot with
Raspberry Pi" (Pi 3B, ~60s -> 1.9s by systemd-analyze).

**We have been measuring the wrong window.** `systemd-analyze`'s "kernel" figure
starts when the kernel starts. The firmware stage - `start.elf`, reading config.txt,
probing HDMI and the HAT EEPROM, loading the kernel and DTB off the FAT partition -
is invisible to it. So every number in this document understates what you see when
you flick the switch, and that stage is where two of KittenLabs' larger wins are:

| Their finding | Measured | Our state |
|---|---|---|
| `hdmi_ignore_edid=0xa5000080`, `hdmi_blanking=2` | ~1.5s | neither set |
| `force_eeprom_read=0`, `disable_poe_fan=1`, `ignore_lcd=1` | ~0.5s | none set; we do have a HAT, which may have no ID EEPROM to find |
| remove the initramfs (`auto_initramfs=1`) | ~0.28s | `auto_initramfs=1` is set; whether a file exists to load is unverified |
| custom 8.5MB kernel vs stock 25MB | ~1.5s | stock |
| uncompressed rather than gzipped kernel | net positive | stock (compressed) |
| `dtoverlay=sdtweak,overclock_50=100` | **no difference** | not set - and now will not be |

**A correction to this document.** Earlier it says a slim kernel "would be trimming
code that is mostly not what costs the time". That was wrong. KittenLabs' 1.5s comes
from reading and decompressing 16MB less, which is exactly the constraint measured
here (17.6 MB/s, ~1000 IOPS). And ARM1176 decompresses far slower than their A53, so
the uncompressed-kernel trick probably pays better on this board than on theirs.

Himesh confirms two things already on our list, with numbers: not remounting /boot
saved him 0.2s (ours is worse - `systemd-fsck` on the boot partition is 2.35s, on the
critical chain at 27.9s), and `quiet` in cmdline.txt, which matters here because every
kernel message goes to a 115200 serial console.

**Their targets are not ours.** KittenLabs boots to "take a picture and shut down";
Himesh disabled networking, ssh and NTP. This device runs a Python app with PIL from
a venv on ARMv6. Low 20s looks like the realistic floor for this approach - about
what a stock Zero 2 W gives without any of it.

**The method is worth copying though:** measure power-on to the event you care about.
For us that is power-on to frame-on-panel, wall-clock, which nothing on the Pi can
report - and which the shutdown frame reduces to zero regardless.

Sources: https://kittenlabs.de/blog/2024/09/01/extreme-pi-boot-optimization/ and
http://himeshp.blogspot.com/2018/08/fast-boot-with-raspberry-pi.html

## The answer was never the panel, 2026-09-26

The power switch is a latching 16mm button (3 pole, 1NO1NC) that makes and breaks
the rail - so at power-off nothing runs, and the shutdown-frame idea above cannot
work as it stands. Two consequences that reframe the whole exercise:

- **After a hard cut the panel is not blank, it is stale.** It holds the last screen
  drawn (`main.py` says as much: "after a power cut the panel holds whatever its
  particles were left in"). A stale screen looks like a live one, which is worse
  than blank for telling whether the device is starting.
- **The panel cannot indicate a state change until Linux is up**, which is ~25s on
  this hardware no matter what is trimmed.

So the indicator is the lamp in the power button, not the panel. `config.txt` takes
`gpio=22=op,dh`, which the *firmware* applies about a second after the switch is
flipped - before the kernel, let alone the application. `setup-pi.sh
--status-led-pin N` writes it, and `main.py`'s `StatusLed` drives the pin low once
the first real screen is on the panel. **Lit means starting, dark means ready**, and
the useful feedback arrives at roughly t=1s instead of t=28s.

Also noted while wiring this up: `setup-pi.sh`'s own comment recommends pin 3 for
`gpio-shutdown` because it doubles as wake-from-halt - but pin 3 is I2C SCL, which
the UPS HAT's fuel gauge is on. The help text now says not to use it here.

`Panel.__init__` does two full white refreshes (~4.6s of panel time) to clear
ghosting, which also means the application wipes the boot splash when it starts. The
splash therefore only ever covers the window before the app, which is worth
remembering when judging what it is worth.

## The firmware stage was worth 7.8 seconds, 2026-09-26

`--trim-firmware` applied. The kernel phase went from 10.9s to **3.09s** - the
largest single win of the whole exercise, and it was in the window `systemd-analyze`
cannot see, which is why it took two published write-ups to find.

Almost all of it is the initramfs: the firmware was reading `kernel.img` (7.8MB) plus
`initramfs` (14.3MB) before the kernel started, at a point where the SD clock is
still low. Dropping it leaves 7.8MB.

Everything downstream moved with it:

| | before | after |
|---|---|---|
| kernel phase | 10.9s | **3.09s** |
| `init.scope` (PID 1) | 22.8s | **16.3s** |
| first service execs | 25.0s | **17.3s** |
| splash frame on the panel | ~28.5s | **~20.7s** |
| application starts | 43.8s | 40.3s |
| total | 53.1s | 49.7s |

### The trap it set, and the fix

Dropping the initramfs broke the panel, and not obviously: `spi_bcm2835` and `spidev`
are *modules*, the initramfs was what loaded them, and without it they waited for
udev's coldplug pass. Two boots ran with `wait for spi: 20.05s` and then gave up -
the splash failed, and all you saw was the application's white refreshes and then its
main screen.

The fix is `modules-load=spi_bcm2835,spidev` in cmdline.txt, appended to the
`dwc2,g_ether` that was already there. The kernel handles that itself, earlier than
udev and earlier than the initramfs managed. `wait for spi` is now 0.12s.

Worth keeping as a general shape: **the initramfs is doing work you cannot see until
you remove it.** Anything else that quietly depended on it will fail the same way -
late, and looking like a different problem.

Also, the splash's own failure was clean: it gave up before claiming a pin, so
nothing touched the panel. That is the `abandon()` design from 2026-09-24 earning its
keep on a failure nobody predicted.

### One cosmetic thing left in the journal

```
xCreatePipe: Can't set permissions (436) for .../.lgd-nfy0, Read-only file system
```

lgpio makes a notification pipe in the working directory, and at 17.3s the root
filesystem is still read-only - `systemd-remount-fs` runs later. Harmless (nothing
here uses lgpio notifications) but noisy; `Environment=LG_WD=/run` on the unit would
put the pipe on a tmpfs that is writable that early.
