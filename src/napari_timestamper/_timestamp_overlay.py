"""
This module contains the TimestampOverlay class and the VispyTimestampOverlay class.

The TimestampOverlay class is a canvas overlay that displays a timestamp on a napari viewer.
It has several customizable properties such as color, size, prefix, suffix, time, start_time, step_size,
time_format, y_position_offset, x_position_offset, and time_axis.

The VispyTimestampOverlay class is a vispy canvas overlay that displays the TimestampOverlay on a napari viewer.
It inherits from the ViewerOverlayMixin and VispyCanvasOverlay classes.

This structure is adapted from the napari dev example.
"""
import contextlib
import warnings
from typing import Union

from napari._vispy.overlays.base import (
    ViewerOverlayMixin,
    VispySceneOverlay,
)
from napari.components._viewer_constants import CanvasPosition
from napari.components.overlays import SceneOverlay
from napari.utils.color import ColorValue
from napari.utils.events import disconnect_events
from vispy.color import ColorArray
from vispy.visuals.transforms import STTransform

from napari_timestamper.text_visual import TextWithBoxVisual
from napari_timestamper.utils import _find_grid_offsets


class TimestampOverlay(SceneOverlay):
    """
    Timestamp Overlay.
    """

    color: ColorValue = (0, 1, 0, 1)
    size: int = 10
    bold: bool = False
    italic: bool = False
    prefix: str = ""
    custom_suffix: Union[str, None] = None
    time: int = 0
    start_time: int = 0
    step_size: float = 1
    time_format: str = "MM:SS"
    bg_color: ColorArray = ColorArray("black")
    show_outline: bool = False
    outline_color: ColorArray = ColorArray("white")
    outline_thickness: float = 1
    show_background: bool = True
    y_spacer: int = 0
    x_spacer: int = 0
    time_axis: int = 0
    position: CanvasPosition = CanvasPosition.BOTTOM_RIGHT
    scale_with_zoom: bool = True
    display_on_scene: bool = True

    def _timestamp_string(self):
        """
        Returns the formatted timestamp string.

        Returns
        -------
        str
            The formatted timestamp string.
        """
        timestamp = self._format_timestamp(self.time, self.time_format)
        suffix = self.custom_suffix if self.custom_suffix else self.time_format
        return f"{self.prefix} {timestamp} {suffix}"

    def _format_timestamp(self, total_time, format_specifier):
        """
        Formats the timestamp string based on the format specifier.

        Parameters
        ----------
        total_time : int
            The total time in seconds.
        format_specifier : str
            The format specifier for the timestamp text.

        Returns
        -------
        str
            The formatted timestamp string.
        """
        time = float(self.start_time + self.time * self.step_size)
        hours = int(time // 3600)
        minutes = int((time % 3600) // 60)
        seconds = time % 60

        if format_specifier == "HH:MM:SS":
            return f"{hours:02}:{minutes:02}:{seconds:02.0f}"
        if format_specifier == "HH:MM:SS.ss":
            return f"{hours:02}:{minutes:02}:{seconds:05.2f}"
        elif format_specifier == "HH:MM":
            return f"{hours:02}:{minutes:02}"
        elif format_specifier == "H:M:S":
            return f"{hours}:{minutes}:{seconds:.0f}"
        elif format_specifier == "H:M":
            return f"{hours}:{minutes}"
        elif format_specifier == "H:M:S.ss":
            return f"{hours}:{minutes}:{seconds:.2f}"
        elif format_specifier == "MM:SS":
            return f"{minutes:02}:{seconds:02.0f}"
        elif format_specifier == "MM:SS.ss":
            return f"{minutes:02}:{seconds:05.2f}"
        elif format_specifier == "M:S":
            return f"{minutes}:{seconds:.0f}"
        elif format_specifier == "M:S.ss":
            return f"{minutes}:{seconds:.2f}"
        elif format_specifier == "SS":
            return f"{total_time:02.0f}"
        elif format_specifier == "SS.ss":
            return f"{total_time:05.2f}"
        elif format_specifier == "F":
            return f"{total_time:.0f}"
        else:
            raise ValueError(f"Unknown format specifier: {format_specifier}")

    def _get_allowed_format_specifiers():
        """
        Returns a list of allowed format specifiers.

        Returns
        -------
        list of str
            A list of allowed format specifiers.
        """
        return [
            "HH:MM:SS",
            "HH:MM:SS.ss",
            "HH:MM",
            "H:M:S",
            "H:M",
            "H:M:S.ss",
            "MM:SS",
            "MM:SS.ss",
            "M:S",
            "M:S.ss",
            "SS",
            "SS.ss",
            "F",
        ]

    @property
    def text(self):
        """
        Returns the formatted timestamp string.

        Returns
        -------
        str
            The formatted timestamp string.
        """
        return self._timestamp_string()


class VispyTimestampOverlay(ViewerOverlayMixin, VispySceneOverlay):
    """
    Vispy Timestamp Overlay.
    """

    def __init__(self, *, viewer, overlay, parent=None):
        super().__init__(
            node=TextWithBoxVisual(
                text=overlay.text,
                color=overlay.color,
                font_size=overlay.size,
                pos=(0, 0),
            ),
            viewer=viewer,
            overlay=overlay,
            parent=parent,
        )
        self.y_spacer = self.overlay.y_spacer
        self.x_spacer = self.overlay.x_spacer
        self.x_size = 0
        self.y_size = 0
        self.camera_scaling_factor = 1
        self.node.transform = STTransform()
        self.overlay.events.position.connect(self._on_position_change)

        # setup callbacks
        self.overlay.events.color.connect(self._on_color_change)
        self.overlay.events.size.connect(self._on_size_change)
        self.overlay.events.bold.connect(self._on_text_change)
        self.overlay.events.italic.connect(self._on_text_change)
        self.overlay.events.bg_color.connect(self._on_text_change)
        self.overlay.events.show_background.connect(self._on_text_change)
        self.overlay.events.show_outline.connect(self._on_text_change)
        self.overlay.events.outline_color.connect(self._on_text_change)
        self.overlay.events.outline_thickness.connect(self._on_text_change)

        self.overlay.events.text.connect(self._on_text_change)
        self.overlay.events.y_spacer.connect(self._update_offsets)
        self.overlay.events.x_spacer.connect(self._update_offsets)
        self.overlay.events.time_format.connect(self._on_text_change)
        self.overlay.events.start_time.connect(self._on_time_change)
        self.overlay.events.step_size.connect(self._on_time_change)
        self.overlay.events.prefix.connect(self._on_text_change)
        self.overlay.events.custom_suffix.connect(self._on_text_change)
        self.overlay.events.time_axis.connect(self._on_text_change)
        self.overlay.events.scale_with_zoom.connect(self._on_size_change)
        self.overlay.events.display_on_scene.connect(self._on_position_change)
        self.viewer.dims.events.current_step.connect(self._on_time_change)
        self.viewer.camera.events.zoom.connect(self._on_viewer_zoom_change)
        self.viewer.dims.events.ndisplay.connect(self._on_text_change)
        self.node.events.parent_change.connect(self._on_parent_change)
        self.reset()

    def _update_offsets(self, event=None):
        """
        Callback function for when the offsets of the overlay are changed.
        """
        self.x_spacer = self.overlay.x_spacer
        self.y_spacer = self.overlay.y_spacer
        self._on_position_change()

    def _on_parent_change(self, event):
        if event.old is not None:
            with contextlib.suppress(AttributeError):
                disconnect_events(self, event.old.canvas)

        if event.new is not None and self.node.canvas is not None:
            # connect the canvas resize to recalculating the position
            event.new.canvas.events.resize.connect(self._on_position_change)

        self._on_viewer_zoom_change()
        self._on_text_change()

    def _on_viewer_zoom_change(self, event=None):
        """
        Callback function for when the viewer is zoomed.
        """
        self.camera_scaling_factor = self.viewer.camera.zoom
        self._on_size_change()

    def _on_color_change(self, event=None):
        """
        Callback function for when the color of the overlay is changed.
        """
        self.node.color = self.overlay.color

    def _on_position_change(self, event=None):
        """
        Callback function for when the position of the overlay is changed.
        """
        # filter FutureWarnings from napari
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            position = self.overlay.position
            if self.node.canvas is None:
                return

            if not self.overlay.display_on_scene:
                x_max, y_max = list(self.node.canvas.size)
                self.node.parent = (
                    self.viewer.window.qt_viewer.view
                )  # this is a bit ugly and circumvents the overlay system which is not ideal but it works
            else:
                x_max, y_max = (
                    self.viewer.dims.range[-2][-2] + 1,
                    self.viewer.dims.range[-1][-2] + 1,
                )
                if self.viewer.grid.enabled:
                    layer_translations = _find_grid_offsets(self.viewer)
                    # find maximum x and y translation
                    x_max_offset = max(
                        [translation[-1] for translation in layer_translations]
                    )
                    y_max_offset = max(
                        [translation[-2] for translation in layer_translations]
                    )
                    x_max += x_max_offset
                    y_max += y_max_offset

                self.node.parent = (
                    self.viewer.window.qt_viewer.view.scene
                )  # this is a bit ugly and circumvents the overlay system which is not ideal but it works

        if position == CanvasPosition.TOP_LEFT:
            anchors = ("left", "bottom")
            transform = [self.x_spacer - 0.5, self.y_spacer - 0.5, 0, 0]

        elif position == CanvasPosition.TOP_RIGHT:
            anchors = ("right", "bottom")
            transform = [
                x_max - self.x_size - self.x_spacer - 0.5,
                self.y_spacer - 0.5,
                0,
                0,
            ]
        elif position == CanvasPosition.TOP_CENTER:
            transform = [
                x_max / 2 - self.x_size / 2 - 0.5,
                self.y_spacer - 0.5,
                0,
                0,
            ]
            anchors = ("center", "bottom")

        elif position == CanvasPosition.BOTTOM_RIGHT:
            anchors = ("right", "top")
            transform = [
                x_max - self.x_size - self.x_spacer - 0.5,
                y_max - self.y_size - self.y_spacer - 0.5,
                0,
                0,
            ]
        elif position == CanvasPosition.BOTTOM_LEFT:
            anchors = ("left", "top")
            transform = [
                self.x_spacer - 0.5,
                y_max - self.y_size - self.y_spacer - 0.5,
                0,
                0,
            ]
        elif position == CanvasPosition.BOTTOM_CENTER:
            anchors = ("center", "top")
            transform = [
                x_max / 2 - self.x_size / 2 - 0.5,
                y_max - self.y_size - self.y_spacer - 0.5,
                0,
                0,
            ]
        self.node.transform.translate = transform
        self.node.anchors = anchors
        self.node._rectagles_visual.spacer = self.overlay.x_spacer

        self.node.update_data(
            [self.overlay.text],
            [self.overlay.color],
            self.overlay.bg_color.rgba.tolist(),
            self.overlay.size,
            (0, 0),
            [x_max],
        )

    def _on_size_change(self, event=None):
        """
        Callback function for when the size of the overlay is changed.
        """
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            if (
                self.overlay.scale_with_zoom
                and self.node.parent is self.viewer.window.qt_viewer.view.scene
            ):
                self.node.font_scale_factor = self.camera_scaling_factor
                self.node.font_size = self.overlay.size
                self.node.outline_thickness = self.overlay.outline_thickness
                self.node.rectangles_scale_factor = 1

            elif (
                not self.overlay.scale_with_zoom
                and self.node.parent is self.viewer.window.qt_viewer.view
            ):
                self.node.font_scale_factor = 1
                self.node.font_size = self.overlay.size
                self.node.outline_thickness = self.overlay.outline_thickness
                self.node.rectangles_scale_factor = 1

            elif (
                not self.overlay.scale_with_zoom
                and self.node.parent is self.viewer.window.qt_viewer.view.scene
            ):
                self.node.font_scale_factor = 1
                self.node.rectangles_scale_factor = (
                    1 / self.camera_scaling_factor
                )
                self.node.outline_thickness = self.overlay.outline_thickness
                self.node.font_size = self.overlay.size

            elif (
                self.overlay.scale_with_zoom
                and self.node.parent is self.viewer.window.qt_viewer.view
            ):
                self.node.font_scale_factor = self.camera_scaling_factor
                self.node.rectangles_scale_factor = self.camera_scaling_factor
                self.node.outline_thickness = self.overlay.outline_thickness
                self.node.font_size = self.overlay.size

        self._on_position_change()

    def _on_text_change(self, event=None):
        """
        Callback function for when the text of the overlay is changed.
        """
        if self.viewer.dims.ndisplay == 3 and self.overlay.display_on_scene:
            self.node.show_background = False
            self.node.show_outline = False
        else:
            self.node.show_background = self.overlay.show_background
            self.node.show_outline = self.overlay.show_outline

        self.node.text = self.overlay.text
        self.node.bold = self.overlay.bold
        self.node.italic = self.overlay.italic
        self.node.bgcolor = self.overlay.bg_color.rgba.tolist()
        self.node.outline_color = self.overlay.outline_color.rgba.tolist()
        self.node.outline_thickness = self.overlay.outline_thickness

    def _on_time_change(self, event=None):
        """
        Callback function for when the time of the overlay is changed.
        """
        self.overlay.time = self.viewer.dims.current_step[
            self.overlay.time_axis
        ]
        self.node.text = self.overlay.text

    def reset(self):
        """
        Resets the overlay to its initial state.
        """
        super().reset()
        self._on_color_change()
        self._on_size_change()
        self._on_position_change()
        self._on_text_change()
        self._on_time_change()
