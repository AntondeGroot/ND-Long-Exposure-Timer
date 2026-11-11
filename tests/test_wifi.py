"""Whether the Pi boots with Wi-Fi, read from config.txt rather than remembered.

config.txt is what the firmware acts on at boot, so it is the one honest answer: a
setting saved anywhere else could say ON while the Pi boots without a radio.
"""

from nd_timer.wifi import boots_with_wifi


def test_only_an_active_disable_wifi_line_means_the_pi_boots_without_wifi():
    # The line the switch writes, the same line commented out, and no line at all.
    assert not boots_with_wifi("dtparam=i2c_arm=on\ndtoverlay=disable-wifi\n")
    assert boots_with_wifi("dtparam=i2c_arm=on\n#dtoverlay=disable-wifi\n")
    assert boots_with_wifi("dtparam=i2c_arm=on\n")
