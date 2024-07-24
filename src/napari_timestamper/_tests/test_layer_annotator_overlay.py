import warnings
from unittest.mock import patch

import numpy as np
import pytest
from napari._vispy.utils.visual import overlay_to_visual
from vispy.color import ColorArray

from napari_timestamper._layer_annotator_overlay import (
    LayerAnnotatorOverlay,
    VispyLayerAnnotatorOverlay,
)


@pytest.fixture
def overlay():
    return LayerAnnotatorOverlay()


@pytest.fixture
def vispy_overlay(overlay, make_napari_viewer):
    viewer = make_napari_viewer()
    return VispyLayerAnnotatorOverlay(viewer=viewer, overlay=overlay)


def test_init(vispy_overlay):
    assert vispy_overlay.x_spacer == 0
    assert vispy_overlay.y_spacer == 0
    assert vispy_overlay.x_size == 0
    assert vispy_overlay.y_size == 0


def test_update_offsets(vispy_overlay):
    vispy_overlay.overlay.x_spacer = 10
    vispy_overlay.overlay.y_spacer = 20
    vispy_overlay._update_offsets()
    assert vispy_overlay.x_spacer == 10
    assert vispy_overlay.y_spacer == 20


def test_on_size_change(vispy_overlay):
    vispy_overlay.overlay.size = 15
    vispy_overlay._on_size_change()
    assert vispy_overlay.node.font_size == 15


def test_on_property_change(vispy_overlay):
    vispy_overlay.viewer.add_image(np.random.random((10, 10)), name="Layer1")
    # vispy_overlay.overlay.layers_to_annotate["layer_names"] = ["Layer1"]
    assert vispy_overlay.node.color != ColorArray("red")
    vispy_overlay.overlay.color = "red"
    vispy_overlay._on_property_change()
    assert vispy_overlay.node.text == ["Layer1"]
    assert vispy_overlay.node.color == ColorArray("red")


def test_reset(vispy_overlay):
    with patch.object(
        vispy_overlay, "_on_property_change"
    ) as mock_property_change, patch.object(
        vispy_overlay, "_on_size_change"
    ) as mock_size_change, patch.object(
        vispy_overlay, "_on_position_change"
    ) as mock_position_change, patch.object(
        vispy_overlay, "_on_viewer_zoom_change"
    ) as mock_zoom_change, patch.object(
        vispy_overlay, "_update_annotations"
    ) as mock_update_annotations:
        vispy_overlay.reset()
    mock_property_change.assert_called_once()
    mock_size_change.assert_called_once()
    mock_position_change.assert_called_once()
    mock_zoom_change.assert_called_once()
    mock_update_annotations.assert_called_once()


def test_add_overlay_to_viewer(make_napari_viewer):
    viewer = make_napari_viewer()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        try:
            viewer._overlays["LayerAnnotator"]
        except KeyError:
            viewer._overlays["LayerAnnotator"] = LayerAnnotatorOverlay(
                visible=True
            )
            overlay_to_visual[
                LayerAnnotatorOverlay
            ] = VispyLayerAnnotatorOverlay
            viewer.window._qt_viewer.canvas._add_overlay_to_visual(
                viewer._overlays["LayerAnnotator"]
            )
        layer_annotator_overlay = viewer._overlays["LayerAnnotator"]

    assert isinstance(layer_annotator_overlay, LayerAnnotatorOverlay)
