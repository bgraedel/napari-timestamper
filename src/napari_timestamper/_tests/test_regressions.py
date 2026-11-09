"""Regression tests for issues found in code review."""

import warnings

import numpy as np
import pytest
from pydantic import ValidationError
from qtpy.QtCore import Qt
from vispy.scene.subscene import SubScene

from napari_timestamper._layer_annotator_overlay import LayerAnnotatorManager
from napari_timestamper._timestamp_overlay import (
    TimestampManager,
    TimestampOverlay,
)
from napari_timestamper._widget import (
    AxisComboBox,
    LayerAnnotationsWidget,
    RenderRGBWidget,
    SplitStackWidget,
    TimestampWidget,
)

NAMES = LayerAnnotatorManager.KEY
STAMP = TimestampManager.KEY


@pytest.fixture
def viewer(make_napari_viewer):
    viewer = make_napari_viewer()
    viewer.add_image(np.zeros((5, 20, 30)), name="a")
    viewer.dims.axis_labels = ("t", "y", "x")
    return viewer


def _visual(viewer, layer, key):
    canvas = viewer.window._qt_viewer.canvas
    return canvas._layer_overlay_to_visual[layer][layer._overlays[key]]


def _text_x(viewer, layer, key) -> float:
    return float(_visual(viewer, layer, key).node.text.pos[0][0])


def test_label_follows_layer_geometry(viewer):
    layer = viewer.layers["a"]
    manager = LayerAnnotatorManager.for_viewer(viewer)
    manager.update_settings(position="bottom_right")
    manager.visible = True
    x = _text_x(viewer, layer, NAMES)
    layer.scale = (1, 2, 2)  # right pixel edge: 29.5 -> 29 * 2 + 1
    assert _text_x(viewer, layer, NAMES) == pytest.approx(x + 29.5)
    layer.translate = (0, 0, 100)
    assert _text_x(viewer, layer, NAMES) == pytest.approx(x + 129.5)
    layer.data = np.zeros((5, 20, 40))
    assert _text_x(viewer, layer, NAMES) == pytest.approx(x + 149.5)


def test_label_stays_in_view_scene_after_3d(viewer):
    viewer.add_image(np.zeros((5, 20, 30)), name="b")
    manager = LayerAnnotatorManager.for_viewer(viewer)
    manager.visible = True
    viewer.dims.ndisplay = 3  # napari swaps the layer's vispy node
    viewer.layers["b"].visible = False  # napari re-parents the overlays
    viewer.layers["b"].visible = True
    node = _visual(viewer, viewer.layers["a"], NAMES).node
    assert isinstance(node.parent, SubScene)


def test_grid_changes_relayout_without_errors(viewer, capsys):
    viewer.add_image(np.zeros((5, 20, 30)), name="b")
    manager = TimestampManager.for_viewer(viewer)
    manager.visible = True
    viewer.canvas.grid.enabled = True
    viewer.scene.camera.zoom = 4
    visual = _visual(viewer, viewer.layers["b"], STAMP)
    viewer.canvas.grid.shape = (2, 1)
    assert "Error" not in capsys.readouterr().err
    assert isinstance(visual.node.parent, SubScene)
    # the layout is already current
    pos = visual.node.text.pos.copy()
    visual._update()
    np.testing.assert_allclose(visual.node.text.pos, pos)


def test_axis_combobox_follows_axis_when_dims_grow(viewer, qtbot):
    combo = AxisComboBox(viewer)
    qtbot.addWidget(combo)
    changes = []
    combo.currentIndexChanged.connect(changes.append)
    viewer.add_image(np.zeros((2, 5, 20, 30)))
    assert combo.currentText() == "t"
    assert combo.currentData() == viewer.dims.axis_labels.index("t")
    assert changes  # the new axis index was announced


def test_3d_round_trip_keeps_user_values(viewer, qtbot):
    stamp = TimestampWidget(viewer)
    export = RenderRGBWidget(viewer)
    qtbot.addWidget(stamp)
    qtbot.addWidget(export)
    stamp.step_time.setValue(7.5)
    export.first_frame.setValue(2)
    export.last_frame.setValue(3)
    viewer.dims.ndisplay = 3
    viewer.dims.ndisplay = 2
    assert stamp.step_time.value() == 7.5
    assert (export.first_frame.value(), export.last_frame.value()) == (2, 3)


def test_renamed_layer_keeps_its_selection(viewer, qtbot):
    b = viewer.add_image(np.zeros((5, 20, 30)), name="b")
    widget = LayerAnnotationsWidget(viewer)
    qtbot.addWidget(widget)
    widget.show_checkbox.setChecked(True)
    widget.layer_selector.item(0).setCheckState(Qt.CheckState.Unchecked)
    b.name = "renamed"
    assert widget.layer_selector.item(0).text() == "renamed"
    viewer.layers["a"].visible = False  # triggers a sync
    viewer.layers["a"].visible = True
    assert not b._overlays[NAMES].visible


def test_reopened_widget_shares_manager_and_settings(viewer, qtbot):
    first = TimestampWidget(viewer)
    qtbot.addWidget(first)
    first.show_checkbox.setChecked(True)
    first.style_controls.font_size.setValue(20)
    first.step_time.setValue(7.5)
    second = TimestampWidget(viewer)
    qtbot.addWidget(second)
    assert second.manager is first.manager
    assert second.show_checkbox.isChecked()
    assert second.style_controls.font_size.value() == 20
    assert second.step_time.value() == 7.5


def test_export_range_follows_new_frames(viewer, qtbot):
    widget = RenderRGBWidget(viewer)
    qtbot.addWidget(widget)
    assert widget.last_frame.value() == 4
    viewer.add_image(np.zeros((20, 20, 30)))
    assert widget.last_frame.value() == 19


def test_native_name_overlay_restored(viewer):
    layer = viewer.layers["a"]
    layer.name_overlay.visible = True  # e.g. from napari's context menu
    layer.name_overlay.font_size = 7
    manager = LayerAnnotatorManager.for_viewer(viewer)
    manager.visible = True
    manager.update_settings(display_on_scene=False, size=30)
    assert layer.name_overlay.font_size == 30
    manager.update_settings(display_on_scene=True)
    assert layer.name_overlay.visible
    assert layer.name_overlay.font_size == 7


def test_invalid_time_format_rejected():
    with pytest.raises(ValidationError):
        TimestampOverlay(time_format="hh:mm")


def test_x_offset_moves_centered_timestamp(viewer):
    manager = TimestampManager.for_viewer(viewer)
    manager.update_settings(position="bottom_center")
    manager.visible = True
    x = _text_x(viewer, viewer.layers["a"], STAMP)
    manager.update_settings(x_spacer=5)
    assert _text_x(viewer, viewer.layers["a"], STAMP) == pytest.approx(x + 5)


def test_split_after_rename(viewer, qtbot):
    widget = SplitStackWidget(viewer)
    qtbot.addWidget(widget)
    viewer.layers["a"].name = "renamed"
    assert widget.layer_combobox.currentText() == "renamed"
    widget.split_button.click()
    assert [ly.name for ly in viewer.layers] == [
        f"renamed_{i}" for i in range(5)
    ]


def test_grid_stride_shares_cells(viewer):
    viewer.add_image(np.zeros((5, 20, 30)), name="b")
    viewer.canvas.grid.stride = 2  # both layers in one cell
    viewer.canvas.grid.enabled = True
    names = LayerAnnotatorManager.for_viewer(viewer)
    names.visible = True
    indices = sorted(ly._overlays[NAMES].stack_index for ly in viewer.layers)
    assert indices == [0, 1]
    stamp = TimestampManager.for_viewer(viewer)
    stamp.visible = True
    assert sum(ly._overlays[STAMP].visible for ly in viewer.layers) == 1


def test_plugin_widgets_avoid_private_access_warnings(make_napari_viewer):
    viewer = make_napari_viewer()
    viewer.add_image(np.zeros((5, 20, 30)))
    with warnings.catch_warnings():
        warnings.simplefilter("error", FutureWarning)
        for name in ("Timestamp", "Layer names"):
            _, widget = viewer.window.add_plugin_dock_widget(
                "napari-timestamper", name
            )
            widget.mode.setCurrentIndex(1)
            widget.show_checkbox.setChecked(True)
            viewer.dims.set_current_step(0, 2)
