import pytest
from qtpy import QtCore

from napari_timestamper._widget import TimestampWidget


@pytest.fixture
def timestamp_options(make_napari_viewer, qtbot):
    viewer = make_napari_viewer()
    widget = TimestampWidget(viewer)
    viewer.window.add_dock_widget(widget)
    return widget


def test_initial_values(timestamp_options):
    assert timestamp_options.time_axis.value() == 0
    assert timestamp_options.start_time.value() == 0
    assert timestamp_options.step_time.value() == 1
    assert timestamp_options.prefix.text() == ""
    assert timestamp_options.suffix.text() == "HH:MM:SS"
    assert timestamp_options.position.currentText() == "top_center"
    assert timestamp_options.ts_size.value() == 12
    assert timestamp_options.x_shift.value() == 0
    assert timestamp_options.y_shift.value() == 0
    assert timestamp_options.time_format.currentText() == "HH:MM:SS"


def test_set_color(timestamp_options, qtbot):
    assert timestamp_options.chosen_color == "white"
    qtbot.mouseClick(timestamp_options.color, QtCore.Qt.LeftButton)
    timestamp_options.color_dialog.done(1)
    assert timestamp_options.chosen_color != "white"


def test_set_timestamp_overlay_options(timestamp_options):
    timestamp_options.time_axis.setValue(1)
    timestamp_options.start_time.setValue(10)
    timestamp_options.step_time.setValue(2)
    timestamp_options.prefix.setText("Time =")
    timestamp_options.suffix.setText("s")
    timestamp_options.position.setCurrentIndex(2)
    timestamp_options.ts_size.setValue(20)
    timestamp_options.x_shift.setValue(5)
    timestamp_options.y_shift.setValue(-5)
    timestamp_options.time_format.setCurrentIndex(1)

    timestamp_options._set_timestamp_overlay_options()

    assert timestamp_options.viewer._overlays["timestamp"].time_axis == 1
    assert timestamp_options.viewer._overlays["timestamp"].start_time == 10
    assert timestamp_options.viewer._overlays["timestamp"].step_size == 2
    assert timestamp_options.viewer._overlays["timestamp"].prefix == "Time ="
    assert timestamp_options.viewer._overlays["timestamp"].suffix == "s"
    assert (
        timestamp_options.viewer._overlays["timestamp"].position == "top_right"
    )
    assert timestamp_options.viewer._overlays["timestamp"].size == 20
    assert (
        timestamp_options.viewer._overlays["timestamp"].x_position_offset == 5
    )
    assert (
        timestamp_options.viewer._overlays["timestamp"].y_position_offset == -5
    )
    assert (
        timestamp_options.viewer._overlays["timestamp"].time_format
        == "HH:MM:SS.ss"
    )
