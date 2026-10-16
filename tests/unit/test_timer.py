"""Unit tests for Timer formatting and countdown logic."""

from linux_game_bar.widgets.timer import TimerWidget


def test_timer_formatting(qapp):
    widget = TimerWidget()
    assert widget._format_time(0) == "00:00"
    assert widget._format_time(59) == "00:59"
    assert widget._format_time(60) == "01:00"
    assert widget._format_time(1500) == "25:00"


def test_timer_preset(qapp):
    widget = TimerWidget()
    widget._set_preset(10)
    assert widget._total_duration_secs == 600
    assert widget.lbl_digits.text() == "10:00"
