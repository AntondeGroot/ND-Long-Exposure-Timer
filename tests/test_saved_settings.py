"""Tests for keeping the settings across a restart."""

from dataclasses import replace

from nd_timer.device import Device
from nd_timer.exposure import COMMON_FILTERS
from nd_timer.filter_bag import FilterBag
from nd_timer.saved_settings import SettingsFile

FILTERS_BY_NAME = {f.name: f for f in COMMON_FILTERS}


def test_the_settings_survive_a_restart(tmp_path):
    # Every setting moved off its default, so a restore that silently fell back to
    # the defaults for any one of them would show here.
    filter_bag = FilterBag((FILTERS_BY_NAME["ND8"], FILTERS_BY_NAME["ND1000"]))
    before = replace(Device(), filter_bag=filter_bag, iso_max=1600, aperture_min=2.8, aperture_max=16.0,
                     delay_seconds=15.0)
    path = tmp_path / "settings.json"
    SettingsFile(path).save_if_changed(before)

    after = SettingsFile(path).restored(Device())

    assert after.filter_bag == filter_bag
    assert (after.iso_max, after.aperture_min, after.aperture_max, after.delay_seconds) == (1600, 2.8, 16.0, 15.0)


def test_a_corrupt_file_starts_from_the_defaults(tmp_path):
    # Half a file is what a power cut mid-write would leave without the atomic rename,
    # and the device must still start - on the defaults, not on a crash.
    path = tmp_path / "settings.json"
    path.write_text('{"iso_max": 16')

    assert SettingsFile(path).restored(Device()) == Device()


def test_an_unknown_value_falls_back_alone(tmp_path):
    # A file written by another version: an ISO no longer on the ladder and a filter
    # renamed since. Each falls back on its own - the rest of the file still counts.
    path = tmp_path / "settings.json"
    path.write_text('{"filters": ["ND8", "ND3000"], "iso_max": 123, "delay_seconds": 15.0}')

    restored = SettingsFile(path).restored(Device())

    assert restored.filter_bag == FilterBag((FILTERS_BY_NAME["ND8"],))
    assert restored.iso_max == Device().iso_max
    assert restored.delay_seconds == 15.0


def test_crossed_lens_ends_fall_back_together(tmp_path):
    # Each end is a valid aperture on its own, but f/16 to f/2.8 describes no lens. Keeping
    # either one alone could still cross the default for the other, so both go back.
    path = tmp_path / "settings.json"
    path.write_text('{"aperture_min": 16.0, "aperture_max": 2.8}')

    restored = SettingsFile(path).restored(Device())

    assert (restored.aperture_min, restored.aperture_max) == (Device().aperture_min, Device().aperture_max)


def test_nothing_is_written_while_the_settings_are_unchanged(tmp_path):
    # The run loop asks twenty times a second. Removing the file after the restore shows
    # any write: it would come back. The last line proves a real change still writes.
    path = tmp_path / "settings.json"
    path.write_text('{"iso_max": 800}')
    settings_file = SettingsFile(path)
    device = settings_file.restored(Device())
    path.unlink()

    settings_file.save_if_changed(device)
    settings_file.save_if_changed(replace(device, dial=replace(device.dial, is_being_set=True)))
    assert not path.exists()

    settings_file.save_if_changed(replace(device, iso_max=1600))
    assert path.exists()


def test_a_failed_write_does_not_stop_the_device(tmp_path, capsys):
    # A folder that does not exist stands in for a read-only or full card: the write
    # fails, the device carries on, and the journal says why.
    settings_file = SettingsFile(tmp_path / "missing" / "settings.json")

    settings_file.save_if_changed(replace(Device(), iso_max=1600))

    assert "could not save the settings" in capsys.readouterr().err


def test_the_scene_is_not_restored(tmp_path):
    # The time and the scenario describe tonight, not the gear: a restart starts them
    # afresh even when the settings saved alongside them come back.
    scene = replace(Device(), subject_index=2, dial=replace(Device().dial, seconds=120.0, is_hand_set=True))
    path = tmp_path / "settings.json"
    SettingsFile(path).save_if_changed(replace(scene, iso_max=1600))

    restored = SettingsFile(path).restored(Device())

    assert restored.iso_max == 1600
    assert (restored.subject_index, restored.dial) == (Device().subject_index, Device().dial)
