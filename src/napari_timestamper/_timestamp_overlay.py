"""Timestamp labels with an optional Fiji-style time bar.

The timestamp is attached to layers like the layer names: by default it is
drawn once on the topmost selected layer, or on every selected layer when
grid mode is on (one per grid cell).  Fixed on screen it uses
:class:`TimestampTextOverlay`, napari's text overlay plus the time bar.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal, get_args

from napari._vispy.overlays.text import _VispyLayerTextOverlay
from napari._vispy.utils.gl import BLENDING_MODES
from napari._vispy.utils.visual import overlay_to_visual
from napari.components._viewer_constants import CanvasPosition
from napari.components.overlays import TextOverlay
from napari.utils.color import ColorValue
from pydantic import ConfigDict
from vispy.scene.visuals import Mesh

from napari_timestamper._label import (
    LabelManager,
    LabelStyle,
    VispyLabelOverlay,
    rects_mesh_data,
)

if TYPE_CHECKING:
    from napari.components import ViewerModel
    from napari.layers import Layer

TimeFormat = Literal[
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
TIME_FORMATS: tuple[str, ...] = get_args(TimeFormat)


def format_time(seconds: float, time_format: str) -> str:
    """Format ``seconds`` according to one of :data:`TIME_FORMATS`.

    Negative times (e.g. relative to a stimulus) get a leading minus sign.
    Minutes in the ``MM``/``M`` formats are total minutes, so they do not
    wrap after an hour.
    """
    if time_format not in TIME_FORMATS:
        raise ValueError(f"Unknown time format: {time_format!r}")
    fractional = time_format.endswith(".ss")
    t = round(abs(seconds), 2 if fractional else 0)
    sign = "-" if seconds < 0 and t > 0 else ""
    hours, rest = divmod(t, 3600)
    minutes, secs = divmod(rest, 60)
    hours, minutes, total_minutes = int(hours), int(minutes), int(t // 60)
    sec_padded = f"{secs:05.2f}" if fractional else f"{int(secs):02d}"
    sec_plain = f"{secs:.2f}" if fractional else f"{int(secs)}"

    if time_format.startswith("HH:MM:SS"):
        body = f"{hours:02d}:{minutes:02d}:{sec_padded}"
    elif time_format == "HH:MM":
        body = f"{hours:02d}:{minutes:02d}"
    elif time_format.startswith("H:M:S"):
        body = f"{hours}:{minutes}:{sec_plain}"
    elif time_format == "H:M":
        body = f"{hours}:{minutes}"
    elif time_format.startswith("MM:SS"):
        body = f"{total_minutes:02d}:{sec_padded}"
    elif time_format.startswith("M:S"):
        body = f"{total_minutes}:{sec_plain}"
    elif time_format == "SS":
        body = f"{t:02.0f}"
    elif time_format == "SS.ss":
        body = f"{t:05.2f}"
    else:  # "F"
        body = f"{t:.0f}"
    return sign + body


def current_frame(viewer: ViewerModel, axis: int) -> tuple[int, int]:
    """Return ``(frame, n_frames)`` along ``axis``, or ``(0, 1)`` if the axis
    does not exist or is currently displayed (i.e. not a slider)."""
    dims = viewer.dims
    if 0 <= axis < dims.ndim and axis in dims.not_displayed:
        return int(dims.current_step[axis]), int(dims.nsteps[axis])
    return 0, 1


class TimestampOverlay(LabelStyle):
    """Timestamp settings.

    Offsets (``x_spacer``/``y_spacer``) and ``bar_thickness`` are in image
    pixels when attached to the image, screen pixels for the bar otherwise.
    """

    position: CanvasPosition = CanvasPosition.BOTTOM_RIGHT
    prefix: str = ""
    suffix: str = ""
    start_time: float = 0
    step_size: float = 1
    time_format: TimeFormat = "HH:MM:SS"
    time_axis: int = 0
    x_spacer: float = 0
    y_spacer: float = 0
    show_bar: bool = False
    bar_color: ColorValue = "white"
    bar_thickness: float = 4

    def format_text(self, frame: int) -> str:
        seconds = self.start_time + frame * self.step_size
        parts = (self.prefix, format_time(seconds, self.time_format))
        return " ".join(p for p in (*parts, self.suffix) if p)

    def progress(self, frame: int, n_frames: int) -> float:
        return frame / (n_frames - 1) if n_frames > 1 else 0.0


class VispyTimestampOverlay(VispyLabelOverlay):
    overlay: TimestampOverlay

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.viewer.dims.events.current_step.connect(self._update)

    def _text(self) -> str:
        frame, _ = current_frame(self.viewer, self.overlay.time_axis)
        return self.overlay.format_text(frame)

    def _bar(self):
        ov = self.overlay
        if not ov.show_bar:
            return None
        progress = ov.progress(*current_frame(self.viewer, ov.time_axis))
        return progress, ov.bar_thickness, ov.bar_color

    def _offset(self) -> tuple[float, float]:
        return self.overlay.x_spacer, self.overlay.y_spacer


overlay_to_visual[TimestampOverlay] = VispyTimestampOverlay


class TimestampTextOverlay(TextOverlay):
    """napari's text overlay with an optional progress bar under the text."""

    model_config = TextOverlay.model_config | ConfigDict(validate_default=True)
    bar_progress: float | None = None
    bar_thickness: float = 4
    bar_color: ColorValue = "white"


class VispyTimestampTextOverlay(_VispyLayerTextOverlay):
    """Draws the bar like napari draws its box: as a sibling of the text
    node sharing its transform, and makes room for it in the tile size."""

    overlay: TimestampTextOverlay

    def __init__(self, **kwargs: Any) -> None:
        self._bar = Mesh()
        super().__init__(**kwargs)

    def _connect_events(self) -> None:
        events = self.overlay.events
        events.text.connect(self._on_text_change)
        for event in (
            events.bar_progress,
            events.bar_thickness,
            events.bar_color,
        ):
            event.connect(self._on_position_change)

    def _on_position_change(self, event=None) -> None:
        super()._on_position_change()  # sizes the text and the box
        ov = self.overlay
        if ov.bar_progress is None:
            self._bar.visible = False
            return
        self._bar.visible = True
        y = self.y_size + 2
        track = (*ov.bar_color[:3], ov.bar_color[3] * 0.35)
        rects = [
            (0, y, self.x_size, ov.bar_thickness, track),
            (
                0,
                y,
                self.x_size * ov.bar_progress,
                ov.bar_thickness,
                ov.bar_color,
            ),
        ]
        vertices, faces, colors = rects_mesh_data(rects)
        self._bar.set_data(
            vertices=vertices, faces=faces, vertex_colors=colors
        )
        self.y_size += 2 + ov.bar_thickness
        # resize the box and re-tile with the bar included
        self._on_box_change()
        self.viewer.canvas.events._overlay_positions_changed()

    def _on_box_change(self) -> None:
        super()._on_box_change()
        self._bar.parent = (
            self.node.parent if self._should_be_visible() else None
        )
        self._bar.transform = self.node.transform
        self._bar.order = self.node.order

    def _on_blending_change(self) -> None:
        super()._on_blending_change()
        self._bar.set_gl_state(**BLENDING_MODES[self.overlay.blending])

    def close(self) -> None:
        super().close()
        self._bar.parent = None


overlay_to_visual[TimestampTextOverlay] = VispyTimestampTextOverlay


class TimestampManager(LabelManager):
    """Timestamp on the topmost selected layer (every selected layer in grid
    mode), attached to the image or fixed on screen."""

    KEY = "timestamp"
    SCREEN_KEY = "timestamp_screen"
    style_class = TimestampOverlay
    style: TimestampOverlay

    def __init__(self, viewer: ViewerModel, **settings: Any) -> None:
        super().__init__(viewer, **settings)
        viewer.dims.events.current_step.connect(self._on_step)

    @property
    def overlay(self) -> TimestampOverlay:
        return self.style

    def text(self) -> str:
        frame, _ = current_frame(self.viewer, self.style.time_axis)
        return self.style.format_text(frame)

    def _shown(self) -> list[Layer]:
        # once per view (grid cell): on its topmost selected visible layer
        shown = [ly for ly in super()._shown() if ly.visible]
        return [cell[-1] for cell in self.cells(shown)]

    def _attach(self, layer: Layer) -> None:
        super()._attach(layer)
        layer._overlays[self.SCREEN_KEY] = TimestampTextOverlay()

    def _detach(self, layer: Layer) -> None:
        super()._detach(layer)
        layer._overlays.pop(self.SCREEN_KEY, None)

    def _native(self, layer: Layer) -> TimestampTextOverlay:
        return layer._overlays[self.SCREEN_KEY]

    def _native_values(self, layer: Layer) -> dict[str, Any]:
        style = self.style
        frame, n_frames = current_frame(self.viewer, style.time_axis)
        return {
            **style.native_style(),
            "text": style.format_text(frame),
            "bar_progress": (
                style.progress(frame, n_frames) if style.show_bar else None
            ),
            "bar_thickness": style.bar_thickness,
            "bar_color": style.bar_color,
        }

    def _on_step(self, event=None) -> None:
        for layer in list(self._native_saved):  # natives currently shown
            self._native(layer).update(self._native_values(layer))

    def close(self) -> None:
        self.viewer.dims.events.current_step.disconnect(self._on_step)
        super().close()
