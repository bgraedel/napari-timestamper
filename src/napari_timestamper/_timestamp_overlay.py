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

from napari._vispy.overlays.base import ViewerOverlayMixin, VispyCanvasOverlay
from napari.components._viewer_constants import CanvasPosition
from napari.components.overlays import CanvasOverlay
from napari.utils.color import ColorValue
from vispy.scene.visuals import Text

if TYPE_CHECKING:
    pass


class TimestampOverlay(CanvasOverlay):
    """
    Timestamp Overlay.
    """

    color: ColorValue = (0, 1, 0, 1)
    size: int = 10
    prefix: str = ""
    suffix: str = "MM:SS"
    time: int = 0
    start_time: int = 0
    step_size: float = 1
    time_format: str = "MM:SS"
    y_position_offset: int = 0
    x_position_offset: int = 0
    time_axis: int = 0

    def _timestamp_string(self):
        """
        Returns the formatted timestamp string.

        Returns
        -------
        str
            The formatted timestamp string.
        """
        timestamp = self._format_timestamp(self.time, self.time_format)
        return f"{self.prefix} {timestamp} {self.suffix}"

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
        elif format_specifier == "H:M:S":
            return f"{hours}:{minutes}:{seconds:.0f}"
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
            "H:M:S",
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


class VispyTimestampOverlay(ViewerOverlayMixin, VispyCanvasOverlay):
    """
    Vispy Timestamp Overlay.
    """

    def __init__(self, *, viewer, overlay, parent=None):
        super().__init__(
            node=Text(
                text=overlay.text,
                color=overlay.color,
                font_size=overlay.size,
                pos=(0, 0),
            ),
            viewer=viewer,
            overlay=overlay,
            parent=parent,
        )

        # setup callbacks
        self.overlay.events.color.connect(self._on_color_change)
        self.overlay.events.size.connect(self._on_size_change)
        self.overlay.events.text.connect(self._on_text_change)
        self.overlay.events.y_position_offset.connect(self._on_position_change)
        self.overlay.events.x_position_offset.connect(self._on_position_change)
        self.overlay.events.time_format.connect(self._on_text_change)
        self.overlay.events.start_time.connect(self._on_time_change)
        self.overlay.events.step_size.connect(self._on_time_change)
        self.overlay.events.prefix.connect(self._on_text_change)
        self.overlay.events.suffix.connect(self._on_text_change)
        self.overlay.events.time_axis.connect(self._on_text_change)
        self.viewer.dims.events.current_step.connect(self._on_time_change)

        self.reset()

    def _on_color_change(self, event=None):
        """
        Callback function for when the color of the overlay is changed.
        """
        self.node.color = self.overlay.color

    def _on_position_change(self, event=None):
        """
        Callback function for when the position of the overlay is changed.
        """
        super()._on_position_change()
        position = self.overlay.position

        if position == CanvasPosition.TOP_LEFT:
            anchors = ("left", "bottom")
        elif position == CanvasPosition.TOP_RIGHT:
            anchors = ("right", "bottom")
        elif position == CanvasPosition.TOP_CENTER:
            anchors = ("center", "bottom")
        elif position == CanvasPosition.BOTTOM_RIGHT:
            anchors = ("right", "top")
        elif position == CanvasPosition.BOTTOM_LEFT:
            anchors = ("left", "top")
        elif position == CanvasPosition.BOTTOM_CENTER:
            anchors = ("center", "top")

        self.node.anchors = anchors
        self.node.pos = (
            self.overlay.x_position_offset,
            self.overlay.y_position_offset,
        )

    def _on_size_change(self, event=None):
        """
        Callback function for when the size of the overlay is changed.
        """
        self.node.font_size = self.overlay.size
        self._on_position_change()

    def _on_text_change(self, event=None):
        """
        Callback function for when the text of the overlay is changed.
        """
        self.node.text = self.overlay.text

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
