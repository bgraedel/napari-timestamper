"""
This module contains the LayerAnnotatorOverlay and VispyLayerAnnotatorOverlay classes.

The LayerAnnotatorOverlay class is the napari layer annotator overlay. It contains the
properties of the overlay. The VispyLayerAnnotatorOverlay class is the vispy layer
annotator overlay. It contains the functionality of the overlay
and the vispy visual that is drawn in the canvas. The vispy visual is a TextWithBoxVisual
that contains the text and box visuals that are drawn in the canvas
and the properties of the visuals.

This structure is adapted from the napari dev example.
"""
import contextlib
from collections import defaultdict
from typing import Literal

from napari._vispy.overlays.base import ViewerOverlayMixin, VispySceneOverlay
from napari.components.overlays import SceneOverlay
from napari.layers import Image, labels
from vispy.color import ColorArray
from vispy.visuals.transforms import STTransform

from napari_timestamper.text_visual import TextWithBoxVisual
from napari_timestamper.utils import _find_grid_offsets

try:
    from napari.utils.compat import StrEnum
except ImportError:
    import enum

    class StrEnum(str, enum.Enum):
        """Enum where members are also (and must be) strings"""

        def _generate_next_value_(name, start, count, last_values):
            """Generate an enum member."""
            return name


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
    bold: bool = False
    italic: bool = False
    position: ScenePosition = ScenePosition.TOP_LEFT
    bg_color: ColorArray = ColorArray(["black"])
    show_outline: bool = False
    outline_color: ColorArray = ColorArray(["white"])
    outline_thickness: float = 1
    show_background: bool = False
    y_spacer: int = 0
    x_spacer: int = 0
    layers_to_annotate: dict = {
        "layer_names": ["None"],
        "y_offsets": [0],
        "x_offsets": [0],
        "layer_widths": [0],
        "colors": ColorArray(["white"]),
    }


# probably should make this as a layer overlay.... no time at the moment tho :(
class VispyLayerAnnotatorOverlay(ViewerOverlayMixin, VispySceneOverlay):
    """
    Vispy Timestamp Overlay.
    """

    def __init__(self, *, viewer, overlay, parent=None):
        super().__init__(
            node=TextWithBoxVisual(
                text=overlay.layers_to_annotate["layer_names"],
                color=overlay.layers_to_annotate["colors"],
                font_size=overlay.size,
                pos=(0, 0),
                bold=overlay.bold,
                italic=overlay.italic,
            ),
            viewer=viewer,
            overlay=overlay,
            parent=parent,
        )
        self.camera_scale_factor = 1
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
        self.overlay.events.bold.connect(self._on_property_change)
        self.overlay.events.italic.connect(self._on_property_change)
        self.overlay.events.bg_color.connect(self._on_property_change)
        self.overlay.events.show_background.connect(self._on_property_change)
        self.overlay.events.show_outline.connect(self._on_property_change)
        self.overlay.events.outline_color.connect(self._on_property_change)
        self.overlay.events.outline_thickness.connect(self._on_property_change)
        self.viewer.camera.events.zoom.connect(self._on_viewer_zoom_change)
        self.viewer.layers.events.inserted.connect(self._on_new_layer_added)
        self.viewer.layers.events.reordered.connect(self._update_annotations)
        self.viewer.layers.events.removed.connect(self._update_annotations)
        self.viewer.grid.events.shape.connect(self._update_annotations)
        self.viewer.grid.events.stride.connect(self._update_annotations)
        self.viewer.grid.events.enabled.connect(self._update_annotations)
        self.viewer.dims.events.ndisplay.connect(self._on_property_change)

        self.reset()
        self._connect_iniial_layers()

    def _update_offsets(self, event=None):
        """
        Callback function for when the offsets of the overlay are changed.
        """
        self.x_spacer = self.overlay.x_spacer
        self.y_spacer = self.overlay.y_spacer
        self._on_position_change()

    def _connect_iniial_layers(self):
        """
        Connects the initial layers to the overlay.
        """
        for layer in self.viewer.layers:
            layer.events.visible.connect(self._update_annotations)
            layer.events.name.connect(self._update_annotations)
            with contextlib.suppress(AttributeError):
                layer.events.colormap.connect(self._update_annotations)

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
        layer_translations = _find_grid_offsets(
            self.viewer
        )  # Get grid offsets
        layer_translations.reverse()  # Reverse order to match layer order

        for i, layer in enumerate(self.viewer.layers[::-1]):
            if layer.visible:
                layers_to_annotate["layer_names"].append(layer.name)
                if isinstance(layer, labels.Labels):
                    layers_to_annotate["colors"].append(self.overlay.color)
                else:
                    try:
                        layers_to_annotate["colors"].append(
                            layer.colormap.colors[-1]
                        )
                    except AttributeError:
                        layers_to_annotate["colors"].append(self.overlay.color)

                # Update offsets based on grid position
                grid_offset = layer_translations[i]
                layers_to_annotate["y_offsets"].append(grid_offset[-2])

                layers_to_annotate["x_offsets"].append(grid_offset[-1])
                if not isinstance(layer, (Image, labels.Labels)):
                    extent = self.viewer._sliced_extent_world
                    layers_to_annotate["layer_widths"].append(
                        extent[1][-2] - extent[0][-2]
                    )
                else:
                    layers_to_annotate["layer_widths"].append(
                        layer.data.shape[-2:][0]
                    )

        try:
            layers_to_annotate["colors"] = ColorArray(
                layers_to_annotate["colors"]
            )
        except ValueError:
            layers_to_annotate["colors"] = ColorArray(["white"])

        self.overlay.layers_to_annotate = layers_to_annotate

    def _on_viewer_zoom_change(self, event=None):
        """
        Callback function for when the viewer is zoomed.
        """
        self.camera_scale_factor = self.viewer.camera.zoom
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
        if len(self.overlay.layers_to_annotate["layer_widths"]) < 1:
            self.overlay.layers_to_annotate["layer_widths"] = [0]

        if position == ScenePosition.TOP_LEFT:
            y_offsets, x_offsets = self.correct_offsets_for_overlap("down")
            anchors = ("left", "bottom")
            transform = [self.x_spacer - 0.5, self.y_spacer - 0.5, 0, 0]

        elif position == ScenePosition.TOP_RIGHT:
            y_offsets, x_offsets = self.correct_offsets_for_overlap("down")
            anchors = ("right", "bottom")
            transform = [
                x_max - self.x_size - self.x_spacer + 0.5,
                self.y_spacer - 0.5,
                0,
                0,
            ]
        elif position == ScenePosition.TOP_CENTER:
            y_offsets, x_offsets = self.correct_offsets_for_overlap("down")
            transform = [
                x_max / 2 - self.x_size / 2,
                self.y_spacer - 0.5,
                0,
                0,
            ]
            anchors = ("center", "bottom")

        elif position == ScenePosition.BOTTOM_RIGHT:
            y_offsets, x_offsets = self.correct_offsets_for_overlap("up")
            anchors = ("right", "top")
            transform = [
                x_max - self.x_size - self.x_spacer + 0.5,
                y_max - self.y_size - self.y_spacer + 0.5,
                0,
                0,
            ]
        elif position == ScenePosition.BOTTOM_LEFT:
            y_offsets, x_offsets = self.correct_offsets_for_overlap("up")
            anchors = ("left", "top")
            transform = [
                self.x_spacer - 0.5,
                y_max - self.y_size - self.y_spacer + 0.5,
                0,
                0,
            ]
        elif position == ScenePosition.BOTTOM_CENTER:
            y_offsets, x_offsets = self.correct_offsets_for_overlap("up")
            anchors = ("center", "top")
            transform = [
                x_max / 2 - self.x_size / 2,
                y_max - self.y_size - self.y_spacer + 0.5,
                0,
                0,
            ]
        self.node.transform.translate = transform
        self.node.anchors = anchors
        self.node._rectagles_visual.spacer = self.x_spacer

        self.node.update_data(
            text=self.overlay.layers_to_annotate["layer_names"],
            color=self.overlay.layers_to_annotate["colors"]
            if self.overlay.use_layer_color
            else self.overlay.color,
            font_size=self.overlay.size,
            pos=list(zip(x_offsets, y_offsets)),
            box_width=self.overlay.layers_to_annotate["layer_widths"],
            bgcolor=self.overlay.bg_color.rgba.tolist(),
        )

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
                        1.75
                        * self.overlay.size
                        * existing_offsets.count((y, x))
                    )
                    # y_offsets[idx] -= self.overlay.outline_thickness
                elif movement_direction == "up":
                    y_offsets[idx] -= (
                        1.75
                        * self.overlay.size
                        * existing_offsets.count((y, x))
                    )
                    # y_offsets[idx] += self.overlay.outline_thickness
            existing_offsets.append((y, x))
        return y_offsets, x_offsets

    def _on_size_change(self, event=None):
        """
        Callback function for when the size of the overlay is changed.
        """
        # self.node.font_size = self.overlay.size * self.camera_scale_factor
        self.node.font_scale_factor = self.camera_scale_factor
        self.node.font_size = self.overlay.size
        self.node.outline_thickness = self.overlay.outline_thickness
        self._on_position_change()

    def _on_property_change(self, event=None):
        """
        Callback function for when properties of the overlay are changed.
        """
        # self._update_annotations()
        if self.viewer.dims.ndisplay == 3:
            self.node.show_outline = False
            self.node._rectagles_visual.visible = False
        else:
            self.node.show_outline = self.overlay.show_outline
            self.node._rectagles_visual.visible = self.overlay.show_background

        self.node.text = self.overlay.layers_to_annotate["layer_names"]
        self.node.bold = self.overlay.bold
        self.node.italic = self.overlay.italic
        self.node.outline_color = self.overlay.outline_color
        self.node.outline_thickness = self.overlay.outline_thickness
        self.node.bgcolor = self.overlay.bg_color.rgba.tolist()
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
        self._update_annotations()
