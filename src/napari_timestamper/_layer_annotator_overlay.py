"""
This module contains the TimestampOverlay class and the VispyTimestampOverlay class.

The TimestampOverlay class is a canvas overlay that displays a timestamp on a napari viewer.
It has several customizable properties such as color, size, prefix, suffix, time, start_time, step_size,
time_format, y_position_offset, x_position_offset, and time_axis.

The VispyTimestampOverlay class is a vispy canvas overlay that displays the TimestampOverlay on a napari viewer.
It inherits from the ViewerOverlayMixin and VispyCanvasOverlay classes.

This structure is adapted from the napari dev example.
"""
from typing import TYPE_CHECKING

from napari._vispy.overlays.base import ViewerOverlayMixin, VispySceneOverlay
from napari.components.overlays import SceneOverlay

try:
    from napari.utils.compat import StrEnum
except ImportError:
    from enum import StrEnum
import contextlib
from collections import defaultdict
from typing import Literal

import numpy as np
from vispy.color import ColorArray
from vispy.scene.visuals import Text
from vispy.visuals.transforms import STTransform

if TYPE_CHECKING:
    pass


class ScenePosition(StrEnum):
    """Canvas overlay position.

    Sets the position of an object in the canvas
            * top_left: Top left of the canvas
            * top_right: Top right of the canvas
            * top_center: Top center of the canvas
            * bottom_right: Bottom right of the canvas
            * bottom_left: Bottom left of the canvas
            * bottom_center: Bottom center of the canvas
    """

    TOP_LEFT = "top_left"
    TOP_CENTER = "top_center"
    TOP_RIGHT = "top_right"
    BOTTOM_RIGHT = "bottom_right"
    BOTTOM_CENTER = "bottom_center"
    BOTTOM_LEFT = "bottom_left"


class LayerAnnotatorOverlay(SceneOverlay):
    """
    Timestamp Overlay.
    """

    color: str = "white"
    use_layer_color: bool = False
    size: int = 12
    scale_factor: float = 1
    position: ScenePosition = ScenePosition.TOP_LEFT
    y_spacer: int = 0
    x_spacer: int = 0
    layers_to_annotate: dict = {
        "layer_names": ["None"],
        "y_offsets": [0],
        "x_offsets": [0],
        "colors": ColorArray(["white"]),
    }


class VispyLayerAnnotatorOverlay(ViewerOverlayMixin, VispySceneOverlay):
    """
    Vispy Timestamp Overlay.
    """

    def __init__(self, *, viewer, overlay, parent=None):
        super().__init__(
            node=Text(
                text=overlay.layers_to_annotate["layer_names"],
                color=overlay.layers_to_annotate["colors"],
                font_size=overlay.size,
                pos=(0, 0),
            ),
            viewer=viewer,
            overlay=overlay,
            parent=parent,
        )
        self.x_spacer = self.overlay.x_spacer
        self.y_spacer = self.overlay.y_spacer
        self.x_size = 0
        self.y_size = 0
        self.node.transform = STTransform()

        # setup callbacks
        self.overlay.events.layers_to_annotate.connect(
            self._on_property_change
        )
        self.overlay.events.size.connect(self._on_size_change)
        self.overlay.events.position.connect(self._on_position_change)
        self.overlay.events.y_spacer.connect(self._update_offsets)
        self.overlay.events.x_spacer.connect(self._update_offsets)
        self.overlay.events.color.connect(self._on_property_change)
        self.overlay.events.use_layer_color.connect(self._on_property_change)

        self.viewer.camera.events.zoom.connect(self._on_viewer_zoom_change)
        viewer.layers.events.inserted.connect(self._on_new_layer_added)
        viewer.layers.events.reordered.connect(self._update_annotations)
        viewer.layers.events.removed.connect(self._update_annotations)
        viewer.grid.events.shape.connect(self._update_annotations)
        viewer.grid.events.stride.connect(self._update_annotations)
        viewer.grid.events.enabled.connect(self._update_annotations)

        self.reset()

    def _update_offsets(self, event=None):
        """
        Callback function for when the offsets of the overlay are changed.
        """
        self.x_spacer = self.overlay.x_spacer
        self.y_spacer = self.overlay.y_spacer
        self._on_position_change()

    def _on_new_layer_added(self, event=None):
        """
        Callback function for when a new layer is added to the viewer.
        """
        layer = event.value
        layer.events.visible.connect(self._update_annotations)
        layer.events.name.connect(self._update_annotations)
        with contextlib.suppress(AttributeError):
            layer.events.colormap.connect(self._update_annotations)

        self._update_annotations()

    def _update_annotations(self):
        """
        Function for when a layer is added or removed from the viewer.
        """
        layers_to_annotate = defaultdict(list)
        layer_translations = self._find_grid_offsets()  # Get grid offsets
        layer_translations.reverse()  # Reverse order to match layer order

        for i, layer in enumerate(self.viewer.layers[::-1]):
            if layer.visible:
                layers_to_annotate["layer_names"].append(layer.name)
                try:
                    layers_to_annotate["colors"].append(
                        layer.colormap.colors[-1]
                    )
                except AttributeError:
                    layers_to_annotate["colors"].append("white")

                # Update offsets based on grid position
                grid_offset = layer_translations[i]
                layers_to_annotate["y_offsets"].append(grid_offset[-2])

                layers_to_annotate["x_offsets"].append(grid_offset[-1])

        try:
            layers_to_annotate["colors"] = ColorArray(
                layers_to_annotate["colors"]
            )
        except ValueError:
            layers_to_annotate["colors"] = ColorArray(["white"])

        self.overlay.layers_to_annotate = layers_to_annotate

    def _find_grid_offsets(self):
        """
        Finds the offsets for the grid.
        """
        layer_translations = []
        extent = self.viewer._sliced_extent_world
        n_layers = len(self.viewer.layers)
        for i, layer in enumerate(self.viewer.layers):
            i_row, i_column = self.viewer.grid.position(
                n_layers - 1 - i, n_layers
            )
            # viewer._subplot(layer, (i_row, i_column), extent)
            scene_shift = extent[1] - extent[0]
            translate_2d = np.multiply(scene_shift[-2:], (i_row, i_column))
            translate = [0] * layer.ndim
            translate[-2:] = translate_2d
            layer_translations.append(translate)
        return layer_translations

    def _on_viewer_zoom_change(self, event=None):
        """
        Callback function for when the viewer is zoomed.
        """
        self.overlay.scale_factor = self.viewer.camera.zoom
        self._on_size_change()

    def _on_position_change(self, event=None):
        """
        Callback function for when the position of the overlay is changed.
        """
        position = self.overlay.position
        x_max, y_max = (
            self.viewer.dims.range[-2][-2],
            self.viewer.dims.range[-1][-2],
        )

        if len(self.overlay.layers_to_annotate["y_offsets"]) < 1:
            self.overlay.layers_to_annotate["y_offsets"] = [0]
        if len(self.overlay.layers_to_annotate["x_offsets"]) < 1:
            self.overlay.layers_to_annotate["x_offsets"] = [0]

        if position == ScenePosition.TOP_LEFT:
            y_offsets, x_offsets = self.correct_offsets_for_overlap("down")
            anchors = ("left", "bottom")
            transform = [self.x_spacer, self.y_spacer, 0, 0]

        elif position == ScenePosition.TOP_RIGHT:
            y_offsets, x_offsets = self.correct_offsets_for_overlap("down")
            anchors = ("right", "bottom")
            transform = [
                x_max - self.x_size - self.x_spacer,
                self.y_spacer,
                0,
                0,
            ]
        elif position == ScenePosition.TOP_CENTER:
            y_offsets, x_offsets = self.correct_offsets_for_overlap("down")
            transform = [x_max / 2 - self.x_size / 2, self.y_spacer, 0, 0]
            anchors = ("center", "bottom")

        elif position == ScenePosition.BOTTOM_RIGHT:
            y_offsets, x_offsets = self.correct_offsets_for_overlap("up")
            anchors = ("right", "top")
            transform = [
                x_max - self.x_size - self.x_spacer,
                y_max - self.y_size - self.y_spacer,
                0,
                0,
            ]
        elif position == ScenePosition.BOTTOM_LEFT:
            y_offsets, x_offsets = self.correct_offsets_for_overlap("up")
            anchors = ("left", "top")
            transform = [
                self.x_spacer,
                y_max - self.y_size - self.y_spacer,
                0,
                0,
            ]
        elif position == ScenePosition.BOTTOM_CENTER:
            y_offsets, x_offsets = self.correct_offsets_for_overlap("up")
            anchors = ("center", "top")
            transform = [
                x_max / 2 - self.x_size / 2,
                y_max - self.y_size - self.y_spacer,
                0,
                0,
            ]
        self.node.transform.translate = transform
        self.node.anchors = anchors

        self.node.pos = list(zip(x_offsets, y_offsets))

    def correct_offsets_for_overlap(
        self, movement_direction: Literal["up", "down"] = "down"
    ):
        existing_offsets = []
        y_offsets = self.overlay.layers_to_annotate["y_offsets"].copy()
        x_offsets = self.overlay.layers_to_annotate["x_offsets"].copy()
        for idx, (y, x) in enumerate(
            zip(
                self.overlay.layers_to_annotate["y_offsets"],
                self.overlay.layers_to_annotate["x_offsets"],
            )
        ):
            if (y, x) in existing_offsets:
                if movement_direction == "down":
                    y_offsets[idx] += (
                        1.5
                        * self.overlay.size
                        * existing_offsets.count((y, x))
                    )
                elif movement_direction == "up":
                    y_offsets[idx] -= (
                        1.5
                        * self.overlay.size
                        * existing_offsets.count((y, x))
                    )
            existing_offsets.append((y, x))
        return y_offsets, x_offsets

    def _on_size_change(self, event=None):
        """
        Callback function for when the size of the overlay is changed.
        """
        self.node.font_size = self.overlay.size * self.overlay.scale_factor
        self._on_position_change()

    def _on_property_change(self, event=None):
        """
        Callback function for when properties of the overlay are changed.
        """
        self.node.text = self.overlay.layers_to_annotate["layer_names"]
        if self.overlay.use_layer_color:
            self.node.color = self.overlay.layers_to_annotate["colors"]
        else:
            self.node.color = self.overlay.color
        self._on_size_change()

    def reset(self):
        """
        Resets the overlay to its initial state.
        """
        super().reset()
        self._on_property_change()
        self._on_size_change()
        self._on_position_change()
        self._on_viewer_zoom_change()
