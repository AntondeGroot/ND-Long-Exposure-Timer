"""Tests for the gphoto2 integration."""

from nd_timer.camera import Camera


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
