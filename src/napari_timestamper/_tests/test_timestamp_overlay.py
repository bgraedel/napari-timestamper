import numpy as np
import pytest
from napari.components._viewer_constants import CanvasPosition

from napari_timestamper._timestamp_overlay import (
    TimestampManager,
    TimestampOverlay,
    TimestampTextOverlay,
    VispyTimestampOverlay,
    VispyTimestampTextOverlay,
    format_time,
)


@pytest.mark.parametrize(
    ("seconds", "fmt", "expected"),
    [
        (3725, "HH:MM:SS", "01:02:05"),
        (3725.5, "HH:MM:SS.ss", "01:02:05.50"),
        (3725, "HH:MM", "01:02"),
        (3725, "H:M:S", "1:2:5"),
        (3725, "H:M", "1:2"),
        (65.25, "H:M:S.ss", "0:1:5.25"),
        (3725, "MM:SS", "62:05"),  # total minutes, no wrap after 1 h
        (65.5, "MM:SS.ss", "01:05.50"),
        (125, "M:S", "2:5"),
        (125.5, "M:S.ss", "2:5.50"),
        (7, "SS", "07"),
        (7.25, "SS.ss", "07.25"),
        (7, "F", "7"),
        (59.6, "MM:SS", "01:00"),  # rounds instead of showing "00:60"
        (-90, "MM:SS", "-01:30"),
        (-0.001, "SS", "00"),  # no "-0"
    ],
)
def test_format_time(seconds, fmt, expected):
    assert format_time(seconds, fmt) == expected


def test_format_time_unknown():
    with pytest.raises(ValueError, match="Unknown time format"):
        format_time(1, "nope")


def test_format_text_joins_non_empty_parts():
    overlay = TimestampOverlay(step_size=30, time_format="MM:SS")
    assert overlay.format_text(3) == "01:30"
    overlay.prefix = "t ="
    overlay.suffix = "min"
    assert overlay.format_text(3) == "t = 01:30 min"


@pytest.fixture
def viewer(make_napari_viewer):
    viewer = make_napari_viewer()
    viewer.add_image(np.zeros((11, 20, 30)), name="bottom")
    viewer.add_image(np.zeros((11, 20, 30)), name="top")
    return viewer


def _scene(layer) -> TimestampOverlay:
    return layer._overlays[TimestampManager.KEY]


def _screen(layer) -> TimestampTextOverlay:
    return layer._overlays[TimestampManager.SCREEN_KEY]


def _visual(viewer, layer, overlay):
    canvas = viewer.window._qt_viewer.canvas
    return canvas._layer_overlay_to_visual[layer][overlay]


def test_manager_shows_on_topmost_layer(viewer):
    bottom, top = viewer.layers
    manager = TimestampManager(viewer)
    assert not _scene(top).visible
    manager.visible = True
    assert _scene(top).visible
    assert not _scene(bottom).visible

    top.visible = False  # falls back to the next visible layer
    assert _scene(bottom).visible
    top.visible = True
    manager.hidden_layers = {top}
    assert _scene(bottom).visible
    assert not _scene(top).visible


def test_manager_grid_shows_on_every_layer(viewer):
    manager = TimestampManager(viewer)
    manager.visible = True
    viewer.canvas.grid.enabled = True
    assert all(_scene(layer).visible for layer in viewer.layers)


def test_manager_screen_mode(viewer):
    bottom, top = viewer.layers
    manager = TimestampManager(viewer, step_size=2)
    manager.visible = True
    manager.update_settings(display_on_scene=False, show_bar=True)
    assert _screen(top).visible
    assert not _screen(bottom).visible
    viewer.dims.set_current_step(0, 5)
    assert _screen(top).text == "00:00:10"
    assert _screen(top).bar_progress == pytest.approx(0.5)

    manager.visible = False
    assert not _screen(top).visible
    manager.close()
    assert TimestampManager.KEY not in top._overlays
    assert TimestampManager.SCREEN_KEY not in top._overlays


def test_vispy_overlay_all_positions(viewer):
    top = viewer.layers["top"]
    manager = TimestampManager(viewer, show_bar=True, show_outline=True)
    manager.visible = True
    visual = _visual(viewer, top, _scene(top))
    assert isinstance(visual, VispyTimestampOverlay)
    for position in CanvasPosition:
        manager.update_settings(position=position)
        assert visual.node.visible
    viewer.dims.ndisplay = 3
    viewer.dims.ndisplay = 2


def test_vispy_time_bar_under_text(viewer):
    top = viewer.layers["top"]
    manager = TimestampManager(viewer, show_bar=True, position="top_left")
    manager.visible = True
    node = _visual(viewer, top, _scene(top)).node
    viewer.dims.set_current_step(0, 5)  # frame 5 of 0..10

    vertices = node.shapes.mesh_data.get_vertices()
    track, fill = vertices[-8:-4], vertices[-4:]
    assert np.ptp(track[:, 0]) == pytest.approx(node.text_width)
    assert np.ptp(fill[:, 0]) == pytest.approx(node.text_width / 2)
    text_x, text_y = node.text.pos[0][:2]
    assert track[:, 0].min() == pytest.approx(text_x)  # left-aligned
    assert track[:, 1].min() > text_y  # below the text

    manager.update_settings(show_bar=False)
    assert not node.shapes.visible


def test_vispy_screen_bar(viewer):
    top = viewer.layers["top"]
    manager = TimestampManager(viewer, display_on_scene=False)
    manager.visible = True
    visual = _visual(viewer, top, _screen(top))
    assert isinstance(visual, VispyTimestampTextOverlay)
    height = visual.y_size
    manager.update_settings(show_bar=True, bar_thickness=6)
    assert visual._bar.visible
    assert visual.y_size == pytest.approx(height + 8)  # bar + gap
    manager.update_settings(show_bar=False)
    assert not visual._bar.visible
    assert visual.y_size == pytest.approx(height)


def test_label_stays_above_layers(viewer):
    """Labels must not be children of the layer node, or later additive
    layers would blend over them; napari resets the parent on many events,
    including another layer's visibility change."""
    bottom, top = viewer.layers
    manager = TimestampManager(viewer)
    manager.visible = True
    canvas = viewer.window._qt_viewer.canvas
    visual = _visual(viewer, top, _scene(top))
    layer_node = canvas.layer_to_visual[top].node
    assert visual.node.parent is layer_node.parent
    bottom.visible = False
    bottom.visible = True
    assert visual.node.parent is layer_node.parent
