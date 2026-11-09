"""Layer-name labels (attached to the image, or napari's native name overlay)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import numpy as np
from napari._vispy.utils.visual import overlay_to_visual
from napari.layers.intensity_mixin import IntensityVisualizationMixin
from napari.utils.color import _readable_color
from napari.utils.colormaps.colormap_utils import _representative_color

from napari_timestamper._label import (
    LabelManager,
    LabelStyle,
    VispyLabelOverlay,
)

if TYPE_CHECKING:
    from napari.layers import Layer


class LayerAnnotatorOverlay(LabelStyle):
    """Layer-name label."""

    use_layer_color: bool = True


class VispyLayerAnnotatorOverlay(VispyLabelOverlay):
    overlay: LayerAnnotatorOverlay

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.layer.events.name.connect(self._update)
        if isinstance(self.layer, IntensityVisualizationMixin):
            self.layer.events.colormap.connect(self._update)

    def _text(self) -> str:
        return self.layer.name

    def _text_color(self):
        # same rule as napari's native name overlay: the colormap's brightest
        # color, made readable on the background; gray colormaps use `color`
        ov = self.overlay
        if ov.use_layer_color and isinstance(
            self.layer, IntensityVisualizationMixin
        ):
            color = _representative_color(self.layer.colormap, 1.0)
            if np.ptp(color[:3]) > 0.01:
                background = (
                    ov.bg_color
                    if ov.show_background
                    else self.viewer.canvas.background_color
                )
                return _readable_color(color, background)
        return ov.color


overlay_to_visual[LayerAnnotatorOverlay] = VispyLayerAnnotatorOverlay


class LayerAnnotatorManager(LabelManager):
    """Layer names on all selected layers, stacked in layer-list order."""

    KEY = "layer_annotator"
    style_class = LayerAnnotatorOverlay
    style: LayerAnnotatorOverlay

    def _native(self, layer: Layer):
        return layer.name_overlay

    def _native_values(self, layer: Layer) -> dict[str, Any]:
        values = self.style.native_style()
        if self.style.use_layer_color:
            values["color"] = None  # napari picks the colormap color
        return values
