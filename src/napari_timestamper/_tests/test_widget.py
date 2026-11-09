import numpy as np
import pytest
from qtpy.QtCore import Qt

from napari_timestamper import _widget
from napari_timestamper._widget import (
    AxisComboBox,
    ColorButton,
    LayerAnnotationsWidget,
    LayertoRGBWidget,
    RenderRGBWidget,
    SplitStackWidget,
    TimestampWidget,
)


@pytest.fixture
def viewer(make_napari_viewer):
    viewer = make_napari_viewer()
    viewer.add_image(
        np.random.random((6, 10, 10)),
        name="cells",
        scale=(0.5, 1, 1),
        units=("min", "um", "um"),
    )
    viewer.dims.axis_labels = ("t", "y", "x")
    return viewer


# ---------------------------------------------------------------------------
# Shared controls
# ---------------------------------------------------------------------------


def test_color_button(qtbot):
    button = ColorButton("white")
    qtbot.addWidget(button)
    with qtbot.waitSignal(button.colorChanged):
        button.click()
        button.dialog.setCurrentColor(Qt.GlobalColor.red)
        button.dialog.accept()
    assert button.color() == "#ff0000"
    assert button.rgba(0.5) == (1.0, 0.0, 0.0, 0.5)


def test_axis_combobox_follows_dims(viewer, qtbot):
    combo = AxisComboBox(viewer, none_label="none")
    qtbot.addWidget(combo)
    assert combo.currentData() == 0  # defaults to the first slider
    viewer.dims.axis_labels = ("time", "y", "x")
    assert combo.itemText(1) == "time"
    assert combo.currentData() == 0
    viewer.dims.ndisplay = 3  # no sliders left
    assert combo.count() == 1
    assert combo.currentData() is None


# ---------------------------------------------------------------------------
# Timestamp
# ---------------------------------------------------------------------------


@pytest.fixture
def timestamp_widget(viewer, qtbot):
    widget = TimestampWidget(viewer)
    qtbot.addWidget(widget)
    return widget


def test_timestamp_starts_hidden(timestamp_widget, viewer):
    overlay = viewer.layers["cells"]._overlays["timestamp"]
    assert not timestamp_widget.show_checkbox.isChecked()
    assert not overlay.visible
    timestamp_widget.show_checkbox.setChecked(True)
    assert overlay.visible


def test_timestamp_step_from_units(timestamp_widget):
    # 0.5 min per frame -> 30 s
    assert timestamp_widget.step_time.value() == 30
    timestamp_widget.step_time.setValue(1)
    timestamp_widget.from_data_button.click()
    assert timestamp_widget.step_time.value() == 30


def test_timestamp_options_propagate(timestamp_widget, viewer):
    w = timestamp_widget
    style = w.style_controls
    w.start_time.setValue(-60)
    w.time_format.setCurrentText("MM:SS")
    w.prefix.setText("t =")
    w.suffix.setText("min")
    style.position.setCurrentText("middle_left")
    style.font_size.setValue(20)
    style.background.setChecked(True)
    style.opacity.setValue(50)
    w.bar_group.setChecked(True)
    w.bar_thickness.setValue(8)

    ts = w.timestamp_overlay
    assert ts.time_axis == 0
    assert ts.step_size == 30
    assert ts.position == "middle_left"
    assert ts.size == 20
    assert ts.show_background
    assert ts.bg_color[3] == pytest.approx(0.5)
    assert ts.show_bar
    assert ts.bar_thickness == 8
    # copied to the per-layer overlay
    assert viewer.layers["cells"]._overlays["timestamp"].size == 20

    viewer.dims.set_current_step(0, 3)
    assert w.preview.text() == "t = 00:30 min"


def test_timestamp_show_on_layers(timestamp_widget, viewer):
    other = viewer.add_image(np.zeros((6, 10, 10)), name="other")
    w = timestamp_widget
    w.show_checkbox.setChecked(True)
    assert other._overlays["timestamp"].visible  # topmost
    w.layer_selector.item(0).setCheckState(Qt.CheckState.Unchecked)
    assert not other._overlays["timestamp"].visible
    assert viewer.layers["cells"]._overlays["timestamp"].visible


def test_timestamp_mode_switch(timestamp_widget, viewer):
    w = timestamp_widget
    w.show_checkbox.setChecked(True)
    assert w.style_controls.bold.isEnabled()
    w.mode.setCurrentIndex(1)  # fixed on screen
    assert not w.style_controls.bold.isEnabled()
    assert not w.x_shift.isEnabled()
    assert w.bar_group.isEnabled()  # the bar works in both modes
    screen = viewer.layers["cells"]._overlays["timestamp_screen"]
    assert screen.visible
    assert screen.text == w.preview.text()


def test_timestamp_without_time_axis(make_napari_viewer, qtbot):
    viewer = make_napari_viewer()
    viewer.add_image(np.zeros((10, 10)))
    widget = TimestampWidget(viewer)
    qtbot.addWidget(widget)
    assert widget.time_axis.count() == 0
    assert widget.timestamp_overlay.time_axis == -1
    assert widget.preview.text() == "00:00:00"


# ---------------------------------------------------------------------------
# Layer names
# ---------------------------------------------------------------------------


@pytest.fixture
def layer_names_widget(viewer, qtbot):
    viewer.add_image(np.random.random((6, 10, 10)), name="nuclei")
    widget = LayerAnnotationsWidget(viewer)
    qtbot.addWidget(widget)
    return widget


def test_layer_names_show_and_select(layer_names_widget, viewer):
    w = layer_names_widget
    cells, nuclei = viewer.layers
    assert not w.layer_annotator_overlay.visible
    w.show_checkbox.setChecked(True)
    assert cells._overlays["layer_annotator"].visible
    assert nuclei._overlays["layer_annotator"].visible

    # the list shows napari's order (top layer first)
    assert w.layer_selector.item(0).text() == "nuclei"
    w.layer_selector.item(0).setCheckState(Qt.CheckState.Unchecked)
    assert not nuclei._overlays["layer_annotator"].visible
    assert cells._overlays["layer_annotator"].stack_index == 0


def test_layer_names_options_propagate(layer_names_widget):
    style = layer_names_widget.style_controls
    style.font_size.setValue(15)
    style.bold.setChecked(True)
    style.position.setCurrentText("bottom_center")
    overlay = layer_names_widget.layer_annotator_overlay
    assert overlay.size == 15
    assert overlay.bold
    assert overlay.position == "bottom_center"


def test_layer_names_native_mode(layer_names_widget, viewer):
    w = layer_names_widget
    w.show_checkbox.setChecked(True)
    w.mode.setCurrentIndex(1)
    for layer in viewer.layers:
        assert layer.name_overlay.visible
        assert layer.name_overlay.color is None  # use layer colormap
        assert not layer._overlays["layer_annotator"].display_on_scene
    assert not w.style_controls.color.isEnabled()
    w.color_checkbox.setChecked(False)
    assert w.style_controls.color.isEnabled()
    w.style_controls.color.setColor("#ff0000")
    assert np.allclose(viewer.layers[0].name_overlay.color, [1, 0, 0, 1])
    w.show_checkbox.setChecked(False)
    assert not any(layer.name_overlay.visible for layer in viewer.layers)


def test_new_layer_gets_overlay(layer_names_widget, viewer):
    layer_names_widget.show_checkbox.setChecked(True)
    new = viewer.add_image(np.random.random((10, 10)), name="new")
    assert new._overlays["layer_annotator"].visible


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------


@pytest.fixture
def export_widget(viewer, qtbot):
    widget = RenderRGBWidget(viewer)
    qtbot.addWidget(widget)
    return widget


def test_export_png_series(export_widget, tmp_path):
    w = export_widget
    assert w.axis_combobox.currentData() == 0
    assert w.last_frame.value() == 5
    w.directory = tmp_path
    w.export_type_combobox.setCurrentText("png")
    w.first_frame.setValue(1)
    w.last_frame.setValue(3)
    w.render_button.click()
    assert len(list((tmp_path / "output").glob("*.png"))) == 3


def test_export_current_view(export_widget, tmp_path):
    w = export_widget
    w.directory = tmp_path
    w.axis_combobox.setCurrentIndex(0)  # current view
    assert not w.first_frame.isEnabled()
    w.export_type_combobox.setCurrentText("png")
    w.render_button.click()
    assert (tmp_path / "output.png").exists()

    w.export_type_combobox.setCurrentText("gif")  # needs an axis
    w.render_button.click()
    assert not (tmp_path / "output.gif").exists()


def test_export_asks_for_folder(export_widget, monkeypatch, tmp_path):
    asked = []

    def fake_dialog(*args):
        asked.append(args)
        return ""

    monkeypatch.setattr(
        _widget.QFileDialog, "getExistingDirectory", fake_dialog
    )
    monkeypatch.chdir(tmp_path)
    export_widget.render_button.click()
    assert asked
    assert not list(tmp_path.iterdir())  # nothing written to the cwd


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


def test_convert_only_renders_selected_layers(viewer, qtbot, monkeypatch):
    for name in ("a", "b"):
        viewer.add_image(np.random.random((6, 10, 10)), name=name)
    viewer.layers["b"].visible = False
    widget = LayertoRGBWidget(viewer)
    qtbot.addWidget(widget)
    rendered = []

    def fake_render(v, axes):
        rendered.append(([ly.name for ly in v.layers], axes))
        return np.zeros((6, 10, 10, 4), dtype=np.uint8)

    monkeypatch.setattr(_widget, "render_as_rgb", fake_render)
    for row in range(widget.layer_selector.count()):
        item = widget.layer_selector.item(row)
        if item.text() in ("cells", "b"):
            item.setCheckState(Qt.CheckState.Checked)
    widget.render_button.click()

    assert rendered == [(["cells", "b"], [0])]
    assert [ly.name for ly in viewer.layers] == ["cells", "a", "b", "output"]
    assert viewer.layers["output"].rgb
    assert not viewer.layers["b"].visible  # visibility restored
    # selection survives the layers being removed and re-added
    assert [ly.name for ly in widget.layer_selector.checked_layers()] == [
        "cells",
        "b",
    ]


def test_convert_layer_to_rgb_shape(viewer, qtbot):
    widget = LayertoRGBWidget(viewer)
    qtbot.addWidget(widget)
    widget.layer_selector.item(0).setCheckState(Qt.CheckState.Checked)
    widget.render_button.click()
    frame_shape = viewer.export_figure(flash=False).shape
    assert viewer.layers[-1].data.shape == (6, *frame_shape)


def test_split_stack(viewer, qtbot):
    viewer.add_image(np.zeros((3, 10, 10)), name="small")
    widget = SplitStackWidget(viewer)
    qtbot.addWidget(widget)
    widget.layer_combobox.setCurrentText("cells")
    assert widget.axis_combobox.itemText(0) == "t (size 6)"
    widget.split_button.click()
    names = [ly.name for ly in viewer.layers]
    assert "cells" not in names
    assert [f"cells_{i}" for i in range(6)] == names[1:]
    assert viewer.layers["cells_0"].data.shape == (10, 10)


@pytest.mark.parametrize(
    ("name", "cls"),
    [
        ("Timestamp", TimestampWidget),
        ("Layer names", LayerAnnotationsWidget),
        ("Export (image / movie)", RenderRGBWidget),
        ("Convert to RGB layer", LayertoRGBWidget),
        ("Split stack", SplitStackWidget),
    ],
)
def test_dock_widgets_via_plugin_manifest(make_napari_viewer, name, cls):
    # napari injects the viewer based on the constructor's annotation
    viewer = make_napari_viewer()
    _, widget = viewer.window.add_plugin_dock_widget(
        "napari-timestamper", name
    )
    assert isinstance(widget, cls)
