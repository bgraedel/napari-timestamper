import tempfile
from pathlib import Path

import numpy as np
import pytest
from qtpy import QtCore

from napari_timestamper._widget import (
    LayerAnnotationsWidget,
    LayertoRGBWidget,
    RenderRGBWidget,
    TimestampWidget,
)


@pytest.fixture
def timestamp_options(make_napari_viewer, qtbot):
    viewer = make_napari_viewer()
    widget = TimestampWidget(viewer)
    viewer.window.add_dock_widget(widget)
    return widget


@pytest.fixture
def layer_annotations_widget(make_napari_viewer, qtbot):
    viewer = make_napari_viewer()
    widget = LayerAnnotationsWidget(viewer)
    viewer.window.add_dock_widget(widget)
    return widget


@pytest.fixture
def render_rgb_widget(make_napari_viewer, qtbot):
    viewer = make_napari_viewer()
    widget = RenderRGBWidget(viewer)
    viewer.window.add_dock_widget(widget)
    return widget, viewer


@pytest.fixture
def layer_to_rgb_widget(make_napari_viewer, qtbot):
    viewer = make_napari_viewer()
    widget = LayertoRGBWidget(viewer)
    qtbot.addWidget(widget)
    viewer.window.add_dock_widget(widget)
    return widget, viewer, qtbot


def test_initial_values(timestamp_options):
    assert timestamp_options.time_axis.value() == 0
    assert timestamp_options.start_time.value() == 0
    assert timestamp_options.step_time.value() == 1
    assert timestamp_options.prefix.text() == ""
    assert timestamp_options.suffix.text() == ""
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
    assert timestamp_options.viewer._overlays["timestamp"].custom_suffix == "s"
    assert (
        timestamp_options.viewer._overlays["timestamp"].position == "top_right"
    )
    assert timestamp_options.viewer._overlays["timestamp"].size == 20
    assert timestamp_options.viewer._overlays["timestamp"].x_spacer == 5
    assert timestamp_options.viewer._overlays["timestamp"].y_spacer == -5
    assert (
        timestamp_options.viewer._overlays["timestamp"].time_format
        == "HH:MM:SS.ss"
    )


def test_init(layer_annotations_widget):
    widget = layer_annotations_widget
    assert widget.size_slider.value() == 12
    assert widget.position_combobox.currentText() == "top_left"
    assert widget.x_offset_spinbox.value() == 0
    assert widget.y_offset_spinbox.value() == 0
    assert widget.toggle_visibility_button.isChecked() is True
    assert widget.color_checkbox.isChecked() is True


def test_on_size_slider_change(layer_annotations_widget, qtbot):
    widget = layer_annotations_widget
    initial_value = widget.size_slider.value()
    assert widget.layer_annotator_overlay.size == initial_value
    widget.size_slider.setValue(15)
    assert widget.size_slider.value() == 15
    assert widget.layer_annotator_overlay.size == 15


def test_on_x_offset_change(layer_annotations_widget, qtbot):
    widget = layer_annotations_widget
    initial_value = widget.x_offset_spinbox.value()
    assert widget.layer_annotator_overlay.x_spacer == initial_value
    widget.x_offset_spinbox.setValue(10)
    assert widget.x_offset_spinbox.value() == 10
    assert widget.layer_annotator_overlay.x_spacer == 10


def test_on_y_offset_change(layer_annotations_widget, qtbot):
    widget = layer_annotations_widget
    initial_value = widget.y_offset_spinbox.value()
    assert widget.layer_annotator_overlay.y_spacer == initial_value
    widget.y_offset_spinbox.setValue(20)
    assert widget.y_offset_spinbox.value() == 20
    assert widget.layer_annotator_overlay.y_spacer == 20


def test_on_toggle_visibility(layer_annotations_widget, qtbot):
    widget = layer_annotations_widget
    initial_value = widget.toggle_visibility_button.isChecked()
    assert widget.layer_annotator_overlay.visible == initial_value
    widget.toggle_visibility_button.click()
    assert widget.toggle_visibility_button.isChecked() is not initial_value
    assert widget.layer_annotator_overlay.visible is not initial_value


def test_layer_to_rgb_widget(render_rgb_widget):
    widget, viewer = render_rgb_widget
    viewer.add_image(np.random.random((10, 10, 10)))
    # create a temporary directory
    with tempfile.TemporaryDirectory() as tmpdirname:
        widget.directory = Path(tmpdirname)
        widget.axis_combobox.setCurrentIndex(1)
        widget.export_type_combobox.setCurrentText("png")
        widget.render_button.click()
        assert widget.directory.exists()
        assert (
            len(
                list(
                    widget.directory.joinpath(
                        widget.name_lineedit.text()
                    ).glob("*.png")
                )
            )
            == 10
        )


def test_layer_to_rgb_widget_single(render_rgb_widget):
    widget, viewer = render_rgb_widget
    viewer.add_image(np.random.random((10, 10, 10)))
    # create a temporary directory
    with tempfile.TemporaryDirectory() as tmpdirname:
        widget.directory = Path(tmpdirname)
        widget.axis_combobox.setCurrentIndex(0)
        widget.export_type_combobox.setCurrentText("png")
        widget.render_button.click()
        assert widget.directory.exists()
        assert len(list(widget.directory.glob("*.png"))) == 1


def test_convert_layer_to_rgb(layer_to_rgb_widget):
    widget, viewer, qtbot = layer_to_rgb_widget
    viewer.add_image(np.random.random((10, 800, 800)))
    for i in range(widget.layer_selector.count()):
        widget.layer_selector.item(i).setCheckState(QtCore.Qt.Checked)

    with qtbot.waitSignal(viewer.layers.events.inserted):
        widget.render_button.click()
    assert viewer.layers[1].name == widget.name_lineedit.text()
    assert viewer.layers[1].data.shape == (10, 800, 800, 4)
