"""
Widget tests — updated for the refactored architecture.

Key changes vs. original:
- layer_annotations_widget fixture adds a layer before creating the widget
  so _annotator_manager.get_any_overlay() returns a valid overlay.
- LayerAnnotationsWidget now exposes a `layer_annotator_overlay` property
  (see widget.py) that returns the first managed overlay for convenience.
- x_spacer / y_spacer were removed from LayerAnnotatorOverlay (they were
  canvas-space concepts that don't exist on a SceneOverlay); those tests
  now cover bold / italic instead.
- time_axis is a QComboBox, not a QSpinBox: replaced .value()/.setValue()
  with .currentIndex()/.setCurrentIndex() and added a 3-D image so the
  combobox is populated.
"""

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

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def timestamp_options(make_napari_viewer, qtbot):
    viewer = make_napari_viewer()
    widget = TimestampWidget(viewer)
    viewer.window.add_dock_widget(widget)
    return widget


@pytest.fixture
def layer_annotations_widget(make_napari_viewer, qtbot):
    viewer = make_napari_viewer()
    # A layer must exist so _annotator_manager.get_any_overlay() is non-None
    viewer.add_image(np.random.random((10, 10)), name="test_layer")
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


# ---------------------------------------------------------------------------
# TimestampWidget
# ---------------------------------------------------------------------------


def test_initial_values(timestamp_options):
    # time_axis is a QComboBox — no .value(); use currentIndex()
    assert (
        timestamp_options.time_axis.currentIndex() == -1
    )  # empty (no time dim)
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


def test_set_timestamp_overlay_options(make_napari_viewer, qtbot):
    """Use a 3D image so the time_axis combobox is populated."""
    viewer = make_napari_viewer()
    viewer.add_image(np.random.random((5, 10, 10)))  # 3D: axis 0 is time
    widget = TimestampWidget(viewer)
    viewer.window.add_dock_widget(widget)

    # time_axis is QComboBox — use setCurrentIndex
    widget.time_axis.setCurrentIndex(0)
    widget.start_time.setValue(10)
    widget.step_time.setValue(2)
    widget.prefix.setText("Time =")
    widget.suffix.setText("s")
    widget.position.setCurrentIndex(2)
    widget.ts_size.setValue(20)
    widget.x_shift.setValue(5)
    widget.y_shift.setValue(-5)
    widget.time_format.setCurrentIndex(1)

    widget._set_timestamp_overlay_options()

    ts = viewer._overlays["timestamp"]
    assert ts.time_axis == 0
    assert ts.start_time == 10
    assert ts.step_size == 2
    assert ts.prefix == "Time ="
    assert ts.custom_suffix == "s"
    assert ts.position == "top_right"
    assert ts.size == 20
    assert ts.x_spacer == 5
    assert ts.y_spacer == -5
    assert ts.time_format == "HH:MM:SS.ss"


# ---------------------------------------------------------------------------
# LayerAnnotationsWidget
# ---------------------------------------------------------------------------


def test_init(layer_annotations_widget):
    widget = layer_annotations_widget
    assert widget.size_slider.value() == 12
    assert widget.position_combobox.currentText() == "top_left"
    # assert widget.x_offset_spinbox.value() == 0
    # assert widget.y_offset_spinbox.value() == 0
    assert widget.toggle_visibility_button.isChecked() is True
    assert widget.color_checkbox.isChecked() is True


def test_on_size_slider_change(layer_annotations_widget):
    widget = layer_annotations_widget
    overlay = widget.layer_annotator_overlay
    assert overlay is not None
    initial_value = widget.size_slider.value()
    assert overlay.size == initial_value
    widget.size_slider.setValue(15)
    assert widget.size_slider.value() == 15
    assert widget.layer_annotator_overlay.size == 15


def test_bold_propagates(layer_annotations_widget):
    """bold replaces the removed x_spacer test."""
    widget = layer_annotations_widget
    overlay = widget.layer_annotator_overlay
    assert overlay is not None
    assert overlay.bold is False
    widget.bold_checkbox.setChecked(True)
    assert widget.layer_annotator_overlay.bold is True
    widget.bold_checkbox.setChecked(False)
    assert widget.layer_annotator_overlay.bold is False


def test_italic_propagates(layer_annotations_widget):
    """italic replaces the removed y_spacer test."""
    widget = layer_annotations_widget
    overlay = widget.layer_annotator_overlay
    assert overlay is not None
    assert overlay.italic is False
    widget.italic_checkbox.setChecked(True)
    assert widget.layer_annotator_overlay.italic is True
    widget.italic_checkbox.setChecked(False)
    assert widget.layer_annotator_overlay.italic is False


def test_on_toggle_visibility(layer_annotations_widget):
    widget = layer_annotations_widget
    overlay = widget.layer_annotator_overlay
    assert overlay is not None
    initial = widget.toggle_visibility_button.isChecked()
    assert overlay.visible == initial
    widget.toggle_visibility_button.click()
    assert widget.toggle_visibility_button.isChecked() is not initial
    assert widget.layer_annotator_overlay.visible is not initial


def test_new_layer_gets_overlay(layer_annotations_widget):
    """Layers added after widget creation should also receive an overlay."""
    widget = layer_annotations_widget
    viewer = widget.viewer
    new_layer = viewer.add_image(np.random.random((10, 10)), name="new")
    from napari_timestamper._layer_annotator_overlay import (
        LayerAnnotatorManager,
        LayerAnnotatorOverlay,
    )

    key = LayerAnnotatorManager.OVERLAY_KEY
    assert key in new_layer._overlays
    assert isinstance(new_layer._overlays[key], LayerAnnotatorOverlay)


def test_position_propagates(layer_annotations_widget):
    widget = layer_annotations_widget
    widget.position_combobox.setCurrentText("top_right")
    widget._set_layer_annotator_overlay_options()
    assert str(widget.layer_annotator_overlay.position) == "top_right"


# ---------------------------------------------------------------------------
# RenderRGBWidget
# ---------------------------------------------------------------------------


def test_layer_to_rgb_widget(render_rgb_widget):
    widget, viewer = render_rgb_widget
    viewer.add_image(np.random.random((10, 10, 10)))
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
