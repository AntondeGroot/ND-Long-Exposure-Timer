"""Tests for the gphoto2 integration."""

from nd_timer.camera import Camera, nearest_timed_shutter


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
