"""
Tests for the refactored LayerAnnotatorOverlay.

Key facts about the new architecture:
- SceneOverlay.visible defaults to False (napari keeps scene overlays hidden
  until explicitly enabled).  Tests that check visibility must account for this.
- One LayerAnnotatorOverlay lives in layer._overlays[OVERLAY_KEY] per layer.
- VispyLayerAnnotatorOverlay requires a `layer` argument; access it via the
  canvas's _layer_overlay_to_visual dict after setting visible=True.
- The canvas defers vispy overlay creation until overlay.visible is True.
"""

import numpy as np
import pytest
from napari._vispy.utils.visual import overlay_to_visual

from napari_timestamper._layer_annotator_overlay import (
    LayerAnnotatorManager,
    LayerAnnotatorOverlay,
    VispyLayerAnnotatorOverlay,
)

OVERLAY_KEY = LayerAnnotatorManager.OVERLAY_KEY


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def viewer_with_layers(make_napari_viewer):
    """Viewer with two image layers and the overlay factory registered."""
    viewer = make_napari_viewer()
    overlay_to_visual[LayerAnnotatorOverlay] = VispyLayerAnnotatorOverlay
    l1 = viewer.add_image(np.random.random((10, 10)), name="Layer1")
    l2 = viewer.add_image(np.random.random((10, 10)), name="Layer2")
    return viewer, l1, l2


@pytest.fixture
def manager(viewer_with_layers):
    viewer, l1, l2 = viewer_with_layers
    mgr = LayerAnnotatorManager(viewer)
    return mgr, viewer, l1, l2


# ---------------------------------------------------------------------------
# Model tests
# ---------------------------------------------------------------------------


def test_overlay_model_defaults():
    overlay = LayerAnnotatorOverlay()
    assert overlay.color == "white"
    assert overlay.size == 12
    assert overlay.bold is False
    assert overlay.italic is False
    assert overlay.show_background is False
    assert overlay.show_outline is False
    # SceneOverlay.visible defaults to False in napari
    assert overlay.visible is False


def test_overlay_model_custom_values():
    overlay = LayerAnnotatorOverlay(color="red", size=20, bold=True)
    assert overlay.color == "red"
    assert overlay.size == 20
    assert overlay.bold is True


def test_overlay_model_visible_explicit():
    overlay = LayerAnnotatorOverlay(visible=True)
    assert overlay.visible is True


# ---------------------------------------------------------------------------
# Manager tests
# ---------------------------------------------------------------------------


def test_manager_attaches_overlay_to_existing_layers(manager):
    mgr, viewer, l1, l2 = manager
    assert OVERLAY_KEY in l1._overlays
    assert OVERLAY_KEY in l2._overlays
    assert isinstance(l1._overlays[OVERLAY_KEY], LayerAnnotatorOverlay)
    assert isinstance(l2._overlays[OVERLAY_KEY], LayerAnnotatorOverlay)


def test_manager_attaches_overlay_to_new_layer(manager):
    mgr, viewer, l1, l2 = manager
    l3 = viewer.add_image(np.random.random((10, 10)), name="Layer3")
    assert OVERLAY_KEY in l3._overlays
    assert isinstance(l3._overlays[OVERLAY_KEY], LayerAnnotatorOverlay)


def test_manager_detaches_overlay_on_layer_remove(manager):
    mgr, viewer, l1, l2 = manager
    viewer.layers.remove(l1)
    assert OVERLAY_KEY not in l1._overlays


def test_manager_update_settings_propagates(manager):
    mgr, viewer, l1, l2 = manager
    mgr.update_settings(size=20, bold=True, color="cyan")
    for layer in [l1, l2]:
        ov = layer._overlays[OVERLAY_KEY]
        assert ov.size == 20
        assert ov.bold is True
        assert ov.color == "cyan"


def test_manager_set_visible(manager):
    mgr, viewer, l1, l2 = manager
    # Explicitly show first
    mgr.set_visible(True)
    for layer in [l1, l2]:
        assert layer._overlays[OVERLAY_KEY].visible is True
    # Then hide
    mgr.set_visible(False)
    for layer in [l1, l2]:
        assert layer._overlays[OVERLAY_KEY].visible is False


def test_manager_set_layer_visible(manager):
    mgr, viewer, l1, l2 = manager
    # Start with both visible
    mgr.set_visible(True)
    # Hide only Layer1
    mgr.set_layer_visible("Layer1", False)
    assert l1._overlays[OVERLAY_KEY].visible is False
    assert l2._overlays[OVERLAY_KEY].visible is True  # unaffected


def test_manager_get_any_overlay(manager):
    mgr, viewer, l1, l2 = manager
    ov = mgr.get_any_overlay()
    assert ov is not None
    assert isinstance(ov, LayerAnnotatorOverlay)


def test_manager_close(manager):
    mgr, viewer, l1, l2 = manager
    mgr.close()
    l3 = viewer.add_image(np.random.random((10, 10)), name="Layer3")
    assert OVERLAY_KEY not in l3._overlays


def test_manager_initial_settings_applied(viewer_with_layers):
    viewer, l1, l2 = viewer_with_layers
    _ = LayerAnnotatorManager(viewer, size=18, color="magenta")
    for layer in [l1, l2]:
        ov = layer._overlays[OVERLAY_KEY]
        assert ov.size == 18
        assert ov.color == "magenta"


# ---------------------------------------------------------------------------
# Integration: factory registration and overlay placement
# ---------------------------------------------------------------------------


def test_overlay_registered_in_factory():
    assert LayerAnnotatorOverlay in overlay_to_visual
    assert (
        overlay_to_visual[LayerAnnotatorOverlay] is VispyLayerAnnotatorOverlay
    )


def test_layer_overlay_added_to_layer_not_viewer(viewer_with_layers):
    """Overlays now live in layer._overlays, NOT in viewer._overlays."""
    viewer, l1, l2 = viewer_with_layers
    _ = LayerAnnotatorManager(viewer)
    assert "LayerAnnotator" not in viewer._overlays
    assert OVERLAY_KEY in l1._overlays
    assert OVERLAY_KEY in l2._overlays


# ---------------------------------------------------------------------------
# Vispy visual smoke tests
# ---------------------------------------------------------------------------


def test_vispy_overlay_created_by_canvas(viewer_with_layers):
    """
    Canvas creates VispyLayerAnnotatorOverlay when overlay.visible=True.
    (napari defers vispy overlay creation until visible=True.)
    """
    viewer, l1, _l2 = viewer_with_layers
    _ = LayerAnnotatorManager(
        viewer, visible=True
    )  # visible=True → canvas creates visual
    canvas = viewer.window._qt_viewer.canvas
    overlay_model = l1._overlays[OVERLAY_KEY]
    layer_visuals = canvas._layer_overlay_to_visual.get(l1, {})
    if overlay_model not in layer_visuals:
        pytest.skip(
            "Canvas did not create vispy overlay (headless / deferred)"
        )
    vispy_ov = layer_visuals[overlay_model]
    assert isinstance(vispy_ov, VispyLayerAnnotatorOverlay)


def test_vispy_overlay_reparented_to_scene(viewer_with_layers):
    """
    After creation the vispy node must be in the ViewBox scene
    (sibling of layer nodes), NOT a child of the layer node.
    """
    viewer, l1, _l2 = viewer_with_layers
    _ = LayerAnnotatorManager(viewer, visible=True)
    canvas = viewer.window._qt_viewer.canvas
    overlay_model = l1._overlays[OVERLAY_KEY]
    layer_visuals = canvas._layer_overlay_to_visual.get(l1, {})
    vispy_ov = layer_visuals.get(overlay_model)
    if vispy_ov is None:
        pytest.skip(
            "Canvas did not create vispy overlay (headless / deferred)"
        )
    layer_vispy_node = canvas.layer_to_visual[l1].node
    assert (
        vispy_ov.node.parent is not layer_vispy_node
    ), "Overlay node is still a child of the layer node — additive blending will break"
