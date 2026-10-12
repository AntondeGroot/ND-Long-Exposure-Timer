"""Tests for the gphoto2 integration."""

import subprocess

import pytest

from nd_timer.camera import (
    Camera,
    CameraError,
    CameraSettings,
    MeteredExposure,
    nearest_timed_shutter,
    parse_aperture,
    parse_shutter_speed,
)

# What `gphoto2 --get-config iso --get-config aperture --get-config shutterspeed`
# prints: one block per setting, each with the value it is on in its Current: line.
METERED_OUTPUT = """Label: ISO Speed
Readonly: 0
Type: RADIO
Current: 800
Choice: 0 100
END
Label: Aperture
Readonly: 0
Type: RADIO
Current: f/5.6
Choice: 0 f/5.6
END
Label: Shutter Speed
Readonly: 0
Type: RADIO
Current: 1/60
Choice: 0 1/60
END
"""


def answering(stdout: str, ran: list):
    """A gphoto2 that succeeds with this output, noting each command it was given."""

    def fake_run(command, **options):
        ran.append((command, options))
        return subprocess.CompletedProcess(command, returncode=0, stdout=stdout, stderr="")

    return fake_run


def failing(stderr: str, stdout: str = ""):
    """A gphoto2 that exits with an error, saying this."""

    def fake_run(command, **_options):
        return subprocess.CompletedProcess(command, returncode=1, stdout=stdout, stderr=stderr)

    return fake_run


class FakeProcess:
    """Stands in for a gphoto2 process that is still running."""

    def __init__(self):
        self.returncode = None

    def poll(self):
        return None


def test_a_bulb_exposure_is_a_single_gphoto2_invocation():
    # Splitting this across processes is what breaks the camera: each gphoto2
    # exits closing the PTP session, so the shutter is opened and then abandoned,
    # and capturetarget set in another process is not in force for this one.
    launched = []

    def fake_popen(command, **_kwargs):
        launched.append(command)
        return FakeProcess()

    Camera(popen=fake_popen).start_bulb_exposure(seconds=256)

    assert len(launched) == 1, "the exposure must not be split across processes"
    command = launched[0]
    assert command[:1] == ["gphoto2"]
    # Open, wait, close and the card target all ride in this one command.
    assert "capturetarget=1" in command
    assert command.index("bulb=1") < command.index("256s") < command.index("bulb=0")


def test_the_settings_go_in_the_same_gphoto2_call_as_the_bulb_exposure():
    # NO FILTERS sets the ISO and aperture itself. A setting made in one gphoto2
    # session is not in force in the next, so they have to ride in the exposure's own
    # command - and come before the shutter opens, or the frame is taken without them.
    launched = []

    def fake_popen(command, **_kwargs):
        launched.append(command)
        return FakeProcess()

    Camera(popen=fake_popen).start_bulb_exposure(seconds=240, settings=CameraSettings(iso=1600, aperture=2.8))

    assert len(launched) == 1
    command = launched[0]
    assert command.index("iso=1600") < command.index("bulb=1")
    assert command.index("aperture=f/2.8") < command.index("bulb=1")


def test_a_timed_shot_sends_the_settings_too():
    # Thirty seconds and under the camera times itself, through a different call -
    # and the settings have to ride in that one as well, ahead of the trigger.
    ran = []

    def fake_run(command, **_kwargs):
        ran.append(command)
        return subprocess.CompletedProcess(command, returncode=0, stdout="", stderr="")

    Camera(runner=fake_run).capture_timed("25", settings=CameraSettings(iso=800, aperture=4.0))

    command = ran[0]
    assert command.index("iso=800") < command.index("--trigger-capture")
    assert command.index("aperture=f/4") < command.index("--trigger-capture")


def test_the_shutter_sent_to_the_camera_reaches_the_speeds_past_the_dial():
    # The dial stops at 15s because past it the device's own display becomes a
    # clock, but the camera keeps timing its own exposures to 30. Snapping 25s
    # to the top of the dial instead of to the camera's would be most of a stop,
    # silently, on a shot that looked correct on screen.
    assert nearest_timed_shutter(25.0) == "25"
    assert nearest_timed_shutter(30.0) == "30"
    assert nearest_timed_shutter(20.0) == "20"


def test_the_shutter_is_written_the_way_the_camera_writes_it():
    # gphoto2 takes one of the camera's own choices, and the camera prints a
    # fraction with no unit - so "1/60", never "1/60 s" or "0.0167".
    assert nearest_timed_shutter(1 / 60) == "1/60"
    assert nearest_timed_shutter(0.007) == "1/125"
    assert nearest_timed_shutter(4.2) == "4"


def test_sync_reads_iso_aperture_and_shutter_in_one_call():
    # One gphoto2 call rather than three: each call is a PTP session, several seconds
    # on a Pi Zero. The reading comes from the Current: line of each block, in order.
    ran = []
    metered = Camera(runner=answering(METERED_OUTPUT, ran)).read_metered_exposure()

    assert metered == MeteredExposure(iso=800, aperture=5.6, shutter_seconds=1 / 60)
    assert len(ran) == 1
    command, options = ran[0]
    assert command == ["gphoto2", "--get-config", "iso", "--get-config", "aperture", "--get-config", "shutterspeed"]
    assert options["timeout"] == 45


def test_a_reading_that_is_not_a_metered_exposure_is_a_camera_error():
    # A camera already on Bulb has no shutter speed to report, and a reply missing a
    # block is not a reading at all. Either way SYNC has nothing to work from, and
    # says so with what the camera did send rather than with a stack trace.
    on_bulb = METERED_OUTPUT.replace("Current: 1/60", "Current: Bulb")
    with pytest.raises(CameraError, match="Bulb"):
        Camera(runner=answering(on_bulb, [])).read_metered_exposure()

    missing_one = METERED_OUTPUT.replace("Current: f/5.6", "")
    with pytest.raises(CameraError, match="got 2 values"):
        Camera(runner=answering(missing_one, [])).read_metered_exposure()


def test_shutter_speeds_are_read_however_the_camera_writes_them():
    # A fraction for under a second, a number for whole ones, sometimes with an "s"
    # and stray spaces. Bulb is a setting rather than a duration, and a fraction
    # over nothing is not a speed: both are refused, never read as some number.
    assert parse_shutter_speed("1/250") == 1 / 250
    assert parse_shutter_speed("30") == 30.0
    assert parse_shutter_speed(" 2.5s ") == 2.5
    for unreadable in ("Bulb", "", "1/0", "1/x"):
        with pytest.raises(ValueError):
            parse_shutter_speed(unreadable)


def test_apertures_are_read_however_the_camera_writes_them():
    # Cameras and gphoto2 versions disagree on the prefix: "11", "f/11", "F11", with
    # or without spaces. A lens the camera cannot read reports something that is
    # not a number at all, and that is refused rather than guessed at.
    assert parse_aperture("11") == 11.0
    assert parse_aperture("f/5.6") == 5.6
    assert parse_aperture(" F8 ") == 8.0
    with pytest.raises(ValueError):
        parse_aperture("auto")


def test_a_failed_call_reports_gphoto2s_first_real_error_line():
    # gphoto2 wraps its one useful line in banners of asterisks and debugging advice.
    # The panel has room for that line only, so it is the one kept. Some errors come
    # on stdout instead, and an error with no words at all still has to say something.
    banner = (
        "\n*** Error ***\n"
        "An error occurred in the io-library ('Could not detect any camera'): Unspecified error\n"
        "*** Error (-105: 'Unknown model') ***\n"
    )
    with pytest.raises(CameraError) as raised:
        Camera(runner=failing(banner)).capture_timed("1/60")
    assert str(raised.value) == "An error occurred in the io-library ('Could not detect any camera'): Unspecified error"

    with pytest.raises(CameraError, match=r"^Could not claim the USB device$"):
        Camera(runner=failing("", stdout="Could not claim the USB device\n")).capture_timed("1/60")

    with pytest.raises(CameraError, match=r"^gphoto2 failed$"):
        Camera(runner=failing("*** Error ***\n")).capture_timed("1/60")


def test_a_missing_or_silent_gphoto2_is_a_camera_error():
    # On a fresh SD card gphoto2 may not be installed yet, and a camera asleep on the
    # cable can leave it hanging. Both become a CameraError the panel can name, rather
    # than an exception that takes the main loop down with it.
    def not_installed(command, **_options):
        raise FileNotFoundError(command[0])

    def hanging(command, **options):
        raise subprocess.TimeoutExpired(command, options["timeout"])

    with pytest.raises(CameraError, match="gphoto2 is not installed"):
        Camera(runner=not_installed).read_metered_exposure()
    with pytest.raises(CameraError, match="did not answer within 45s"):
        Camera(runner=hanging).read_metered_exposure()


def test_the_bulb_command_is_exactly_open_wait_close_settle():
    # Settings first, then the card target, open, the exposure, close, and three
    # seconds for the camera to finish writing before the session closes. The
    # exposure is whole seconds, the only unit --wait-event takes. Output is piped
    # as text, so a failure can be read back in words.
    launched = []

    def fake_popen(command, **options):
        launched.append((command, options))
        return FakeProcess()

    Camera(popen=fake_popen).start_bulb_exposure(seconds=255.6, settings=CameraSettings(iso=1600, aperture=2.8))

    command, options = launched[0]
    assert command == [
        "gphoto2",
        "--set-config", "iso=1600",
        "--set-config", "aperture=f/2.8",
        "--set-config", "capturetarget=1",
        "--set-config", "bulb=1",
        "--wait-event", "256s",
        "--set-config", "bulb=0",
        "--wait-event", "3s",
    ]  # fmt: skip
    assert options == {"stdout": subprocess.PIPE, "stderr": subprocess.PIPE, "text": True}


def test_a_timed_shot_keeps_the_frame_on_the_card_and_sets_the_speed():
    # Without capturetarget=1 the frame goes to the camera's RAM and is gone when
    # the session closes. The speed goes in as the camera writes it, then the
    # trigger. The call waits as long as reading the camera does, and keeps the
    # output as text so an error can be read back.
    ran = []
    Camera(runner=answering("", ran)).capture_timed("1/60")

    command, options = ran[0]
    assert command == [
        "gphoto2",
        "--set-config", "capturetarget=1",
        "--set-config", "shutterspeed=1/60",
        "--trigger-capture",
    ]  # fmt: skip
    assert options == {"capture_output": True, "text": True, "timeout": 45}


def test_one_second_is_written_as_a_whole_number():
    # One second is where the camera stops writing fractions: "1", never "1/1".
    assert nearest_timed_shutter(1.0) == "1"
    assert nearest_timed_shutter(0.98) == "1"


def test_cancelling_stops_only_a_shot_still_running():
    # Ending gphoto2 mid-exposure closes its session, and with it the shutter - which
    # is what cancelling a shot is for. Once gphoto2 has exited on its own there is
    # nothing left to stop.
    class Gphoto2:
        def __init__(self, exit_code):
            self.exit_code = exit_code
            self.terminated = False

        def poll(self):
            return self.exit_code

        def terminate(self):
            self.terminated = True

    running = Gphoto2(exit_code=None)
    Camera(popen=lambda *_args, **_options: running).start_bulb_exposure(seconds=60).cancel()
    assert running.terminated

    finished = Gphoto2(exit_code=0)
    Camera(popen=lambda *_args, **_options: finished).start_bulb_exposure(seconds=60).cancel()
    assert not finished.terminated
