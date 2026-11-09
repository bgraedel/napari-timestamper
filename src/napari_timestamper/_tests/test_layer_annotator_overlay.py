import numpy as np
import pytest
from napari.components._viewer_constants import CanvasPosition

from napari_timestamper._layer_annotator_overlay import (
    LayerAnnotatorManager,
    LayerAnnotatorOverlay,
    VispyLayerAnnotatorOverlay,
)

KEY = LayerAnnotatorManager.KEY


@pytest.fixture
def viewer(make_napari_viewer):
    viewer = make_napari_viewer()
    viewer.add_image(np.random.random((10, 10)), name="Layer1")
    viewer.add_image(np.random.random((10, 10)), name="Layer2")
    return viewer


@pytest.fixture
def manager(viewer):
    manager = LayerAnnotatorManager(viewer)
    manager.visible = True
    return manager


def test_model_defaults():
    overlay = LayerAnnotatorOverlay()
    assert overlay.color.tolist() == [1, 1, 1, 1]  # validated to RGBA
    assert overlay.bg_color.tolist() == [0, 0, 0, 1]
    assert overlay.size == 12
    assert not overlay.visible
    assert overlay.display_on_scene


def test_manager_attaches_and_detaches(viewer, manager):
    l1, l2 = viewer.layers
    assert isinstance(l1._overlays[KEY], LayerAnnotatorOverlay)
    l3 = viewer.add_image(np.zeros((10, 10)), name="Layer3")
    assert l3._overlays[KEY].visible
    viewer.layers.remove(l1)
    assert KEY not in l1._overlays
    manager.close()
    assert KEY not in l2._overlays
    assert KEY not in viewer.add_image(np.zeros((5, 5)))._overlays


def test_manager_settings_propagate(viewer, manager):
    manager.update_settings(size=20, bold=True, color="cyan")
    for layer in viewer.layers:
        overlay = layer._overlays[KEY]
        assert overlay.size == 20
        assert overlay.bold
        assert overlay.color.tolist() == [0, 1, 1, 1]
    assert LayerAnnotatorManager(viewer, size=18).style.size == 18


def test_manager_visibility_and_selection(viewer, manager):
    l1, l2 = viewer.layers
    assert l1._overlays[KEY].visible and l2._overlays[KEY].visible
    manager.hidden_layers = {l1}
    assert not l1._overlays[KEY].visible
    assert l2._overlays[KEY].visible
    manager.visible = False
    assert not l2._overlays[KEY].visible


def test_manager_stacks_visible_labels(viewer, manager):
    l1, l2 = viewer.layers
    # topmost layer first
    assert l2._overlays[KEY].stack_index == 0
    assert l1._overlays[KEY].stack_index == 1
    assert l1._overlays[KEY].stack_count == 2
    l2.visible = False
    assert l1._overlays[KEY].stack_index == 0
    assert l1._overlays[KEY].stack_count == 1


def test_manager_native_mode(viewer, manager):
    l1, l2 = viewer.layers
    manager.update_settings(
        size=20, position="bottom_left", display_on_scene=False
    )
    for layer in (l1, l2):
        assert layer.name_overlay.visible
        assert layer.name_overlay.font_size == 20
        assert layer.name_overlay.position == "bottom_left"
    manager.update_settings(use_layer_color=True)
    assert l1.name_overlay.color is None  # napari picks the colormap color
    manager.hidden_layers = {l1}
    assert not l1.name_overlay.visible
    manager.update_settings(display_on_scene=True)
    assert not l2.name_overlay.visible


def test_manager_leaves_user_name_overlays_alone(viewer, manager):
    # name overlays switched on elsewhere (napari's layer context menu)
    l1, _ = viewer.layers
    l1.name_overlay.visible = True
    manager.visible = False
    manager.update_settings(size=30)
    assert l1.name_overlay.visible


def test_vispy_overlay_all_positions(viewer, manager):
    l1, _ = viewer.layers
    manager.update_settings(show_background=True, show_outline=True)
    canvas = viewer.window._qt_viewer.canvas
    visual = canvas._layer_overlay_to_visual[l1][l1._overlays[KEY]]
    assert isinstance(visual, VispyLayerAnnotatorOverlay)
    assert visual.node.parent is canvas.layer_to_visual[l1].node.parent
    for position in CanvasPosition:
        manager.update_settings(position=position)
        assert visual.node.visible
    viewer.canvas.grid.enabled = True
    assert visual.node.visible
    viewer.canvas.grid.enabled = False


def test_vispy_layer_color_matches_native(viewer, manager):
    l1, _ = viewer.layers
    l1.colormap = "green"
    manager.update_settings(use_layer_color=True)
    canvas = viewer.window._qt_viewer.canvas
    node = canvas._layer_overlay_to_visual[l1][l1._overlays[KEY]].node
    color = np.asarray(node.text.color.rgba).ravel()
    assert color[1] > 0.9 and color[0] < 0.1  # green


def test_labels_stack_without_overlapping(viewer, manager):
    canvas = viewer.window._qt_viewer.canvas
    tops = []
    for layer in viewer.layers:
        node = canvas._layer_overlay_to_visual[layer][layer._overlays[KEY]]
        tops.append(node.node.text.pos[0][1])
    height = canvas._layer_overlay_to_visual[viewer.layers[0]][
        viewer.layers[0]._overlays[KEY]
    ].node.height()
    assert abs(tops[0] - tops[1]) == pytest.approx(height)
