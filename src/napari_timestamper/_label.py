"""Shared machinery for labels drawn on layers (timestamps and layer names).

Every label has two display modes, selected with ``display_on_scene``:

* **attached to image** — a per-layer scene overlay (:class:`LabelStyle` model,
  :class:`VispyLabelOverlay` visual) drawn in world units inside the layer, so
  it grows with the image and looks the same in exports;
* **fixed on screen** — one of napari's canvas text overlays, provided by the
  concrete :class:`LabelManager`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar
from weakref import WeakKeyDictionary, WeakSet, ref

import numpy as np
from napari._vispy.overlays.base import LayerOverlayMixin, VispySceneOverlay
from napari._vispy.visuals.text import Text
from napari.components._viewer_constants import CanvasPosition
from napari.components.overlays import SceneOverlay
from napari.layers.base._base_constants import Blending
from napari.utils.color import ColorValue
from pydantic import ConfigDict
from vispy.scene.subscene import SubScene
from vispy.scene.visuals import Compound, Mesh

if TYPE_CHECKING:
    from napari.components import ViewerModel
    from napari.components.overlays import CanvasOverlay
    from napari.layers import Layer
    from psygnal import EventedModel

# padding above and below the text, in line heights
PAD = 0.1


def batched_update(model: EventedModel, values: dict[str, Any]) -> None:
    """``model.update(values)`` emitting ``events.all`` at most once."""
    with model.events.all.paused(lambda _old, new: new):
        model.update(values)


def split_position(position: str) -> tuple[str, str]:
    """``"top_left"`` -> ``("top", "left")``."""
    vertical, horizontal = str(position).split("_")
    return vertical, horizontal


def rects_mesh_data(rects):
    """Vertices, faces and colors for ``(x, y, width, height, rgba)`` rects."""
    vertices, faces, colors = [], [], []
    for i, (x, y, w, h, rgba) in enumerate(rects):
        vertices += [[x, y], [x + w, y], [x + w, y + h], [x, y + h]]
        faces += [[4 * i, 4 * i + 1, 4 * i + 2], [4 * i, 4 * i + 2, 4 * i + 3]]
        colors += [rgba] * 4
    return (
        np.array(vertices, dtype=np.float32),
        np.array(faces, dtype=np.uint32),
        np.array(colors, dtype=np.float32),
    )


def _frame(x, y, w, h, t, rgba):
    """Four rects outlining a box, ``t`` thick, drawn inside its edges."""
    t = min(t, w / 2, h / 2)
    return [
        (x, y, w, t, rgba),
        (x, y + h - t, w, t, rgba),
        (x, y + t, t, h - 2 * t, rgba),
        (x + w - t, y + t, t, h - 2 * t, rgba),
    ]


class LabelStyle(SceneOverlay):
    """Style shared by all labels.

    ``size`` is a font size in points at 100% zoom (text is ``size * 4/3``
    image pixels tall); ``outline_thickness`` is in image pixels.
    """

    # validate defaults so colors are always RGBA arrays
    model_config = SceneOverlay.model_config | ConfigDict(
        validate_default=True
    )
    # no depth test: always on top, and resets a preceding layer's
    # additive/minimum blend function
    blending: Blending = Blending.TRANSLUCENT_NO_DEPTH
    display_on_scene: bool = True
    position: CanvasPosition = CanvasPosition.TOP_LEFT
    size: float = 12
    color: ColorValue = "white"
    bold: bool = False
    italic: bool = False
    show_background: bool = False
    bg_color: ColorValue = "black"
    show_outline: bool = False
    outline_color: ColorValue = "white"
    outline_thickness: float = 1
    # set by the manager: labels of layers sharing a view are stacked
    stack_index: int = 0
    stack_count: int = 1

    def native_style(self) -> dict[str, Any]:
        """Equivalent settings for napari's canvas text overlays."""
        return {
            "color": self.color,
            "font_size": self.size,
            "position": self.position,
            "box": self.show_background,
            "box_color": self.bg_color,
        }


class LabelVisual(Compound):
    """Text in a box (with optional outline and progress bar), world units."""

    def __init__(self, font_info=None):
        self.shapes = Mesh()
        # scaling=True sizes glyphs in world units, so the text grows with
        # the image; napari's Text handles the screen DPI
        self.text = Text(
            text="",
            font_info=font_info,
            scaling=True,
            anchor_x="left",
            anchor_y="center",
        )
        self.text_width = self.line_height = 0.0
        super().__init__([self.shapes, self.text])  # freezes attributes

    def set_text(self, text: str, style: LabelStyle, color) -> None:
        node = self.text
        node.text = text
        node.color = color
        node.bold = style.bold
        node.italic = style.italic
        node.font_size = style.size
        # measured at the logical font size == world units with scaling
        self.text_width = node.get_width_height()[0]
        self.line_height = node.get_line_height()

    def height(self, bar_thickness: float = 0) -> float:
        return self.line_height * (1 + 2 * PAD) + bar_thickness

    def place(
        self,
        *,
        x0: float,
        x1: float,
        top: float,
        align: str,
        inset: float,
        style: LabelStyle,
        flat: bool,
        offset: float = 0,
        bar: tuple[float, float, Any] | None = None,
    ) -> None:
        """Lay out a label spanning ``x0..x1`` whose top edge is at ``top``.

        The text is aligned left/center/right with ``inset`` padding and
        shifted by ``offset`` (inwards for left/right, rightwards for center).
        ``bar`` is ``(progress, thickness, rgba)``: a progress bar as wide as
        the text, directly under it.
        """
        line, width = self.line_height, self.text_width
        if align == "left":
            left = x0 + inset + offset
        elif align == "right":
            left = x1 - inset - width - offset
        else:
            left = (x0 + x1 - width) / 2 + offset
        text_y = top + PAD * line
        self.text.pos = (left, text_y + line / 2)

        height = self.height(bar[1] if bar else 0)
        rects = []
        if flat and style.show_background:
            rects.append((x0, top, x1 - x0, height, style.bg_color))
        if flat and style.show_outline:
            rects += _frame(
                x0,
                top,
                x1 - x0,
                height,
                style.outline_thickness,
                style.outline_color,
            )
        if bar is not None:
            progress, thickness, rgba = bar
            track = (*rgba[:3], rgba[3] * 0.35)
            bar_y = text_y + line
            rects.append((left, bar_y, width, thickness, track))
            rects.append((left, bar_y, width * progress, thickness, rgba))
        self.shapes.visible = bool(rects)
        if rects:
            vertices, faces, colors = rects_mesh_data(rects)
            self.shapes.set_data(
                vertices=vertices, faces=faces, vertex_colors=colors
            )


class VispyLabelOverlay(LayerOverlayMixin, VispySceneOverlay):
    """Base visual for a label attached to a layer.

    Subclasses provide the text and may override the color, offset and
    progress bar.
    """

    overlay: LabelStyle
    node: LabelVisual

    def __init__(self, *, layer: Layer, font_info=None, **kwargs: Any):
        super().__init__(
            node=LabelVisual(font_info),
            layer=layer,
            font_info=font_info,
            **kwargs,
        )
        # napari parents layer scene overlays to the layer's node, and vispy
        # draws children inside their parent's bracket: a later additive
        # layer would blend over the label.  Whenever napari (re)sets the
        # parent, move the label up to the view's scene, next to the layers.
        self.node.events.parent_change.connect(self._on_parent_change)
        self._on_parent_change()

        self.overlay.events.all.connect(self._update)
        layer_events = self.layer.events
        for name in (
            "data",
            "scale",
            "translate",
            "rotate",
            "shear",
            "affine",
        ):
            getattr(layer_events, name).connect(self._update)
        self.viewer.dims.events.ndisplay.connect(self._update)
        self.viewer.canvas.grid.events.enabled.connect(self._update)
        grid = self.viewer.canvas.grid.events
        camera = self.viewer.scene.camera.events
        for event in (
            grid.shape,
            grid.stride,
            grid.spacing,
            self.viewer.canvas.events.size,
            camera.center,
            camera.zoom,
        ):
            event.connect(self._on_view_change)
        self.reset()

    def _on_parent_change(self, event=None) -> None:
        parent = self.node.parent
        scene = parent
        while scene is not None and not isinstance(scene, SubScene):
            scene = scene.parent
        if scene is None or scene is parent:
            return
        # vispy forbids re-emitting parent_change from its own handler, so
        # block it, and clear the cached scene node like vispy's handler does
        self.node.on_parent_change(event)
        with self.node.events.parent_change.blocker():
            self.node.parent = scene

    def _should_be_visible(self) -> bool:
        return super()._should_be_visible() and self.overlay.display_on_scene

    def _on_visible_change(self, event=None) -> None:
        super()._on_visible_change()
        if self.node.visible:
            self._layout()

    def _update(self, *_: Any) -> None:
        self._on_visible_change()

    def _on_view_change(self, *_: Any) -> None:
        # in grid mode labels are clipped to the visible part of their cell
        if self.viewer.canvas.grid.enabled:
            self._update()

    # -- hooks -----------------------------------------------------------

    def _text(self) -> str:
        raise NotImplementedError

    def _text_color(self):
        return self.overlay.color

    def _bar(self) -> tuple[float, float, Any] | None:
        return None

    def _offset(self) -> tuple[float, float]:
        """``(x, y)`` shift of the label, inwards from its position."""
        return 0.0, 0.0

    # -- layout ----------------------------------------------------------

    def _bounds(self) -> tuple[float, float, float, float] | None:
        """Pixel-edge ``(x0, y0, x1, y1)`` of the layer, in world units,
        clipped to the visible area in grid mode."""
        extent = self.layer._extent_world_augmented
        y_dim, x_dim = self.layer._slice_input.displayed[-2:]
        x0, y0 = extent[0, x_dim], extent[0, y_dim]
        x1, y1 = extent[1, x_dim], extent[1, y_dim]
        if self.viewer.canvas.grid.enabled:
            viewer = self.viewer
            corners = [
                viewer.canvas_to_world((0, 0)),
                viewer.canvas_to_world(
                    viewer.canvas.viewbox_size(viewer.layers)
                ),
            ]
            vy, vx = viewer.dims.displayed[-2:]
            x0 = max(x0, min(c[vx] for c in corners))
            x1 = min(x1, max(c[vx] for c in corners))
            y0 = max(y0, min(c[vy] for c in corners))
            y1 = min(y1, max(c[vy] for c in corners))
        if x1 <= x0 or y1 <= y0:
            return None
        return x0, y0, x1, y1

    def _layout(self) -> None:
        bounds = self._bounds()
        if bounds is None:
            self.node.visible = False
            return
        x0, y0, x1, y1 = bounds
        ov = self.overlay
        node = self.node
        node.set_text(self._text(), ov, self._text_color())
        bar = self._bar()
        height = node.height(bar[1] if bar else 0)
        dx, dy = self._offset()
        index, count = ov.stack_index, ov.stack_count
        vertical, align = split_position(ov.position)
        if vertical == "top":
            top = y0 + dy + index * height
        elif vertical == "bottom":
            top = y1 - dy - (count - index) * height
        else:
            top = (y0 + y1) / 2 + dy + (index - count / 2) * height
        node.place(
            x0=x0,
            x1=x1,
            top=top,
            align=align,
            inset=0.4 * node.line_height,
            offset=dx,
            style=ov,
            flat=self.viewer.dims.ndisplay == 2,
            bar=bar,
        )
        node.update()

    def reset(self) -> None:
        super().reset()
        self._update()

    def close(self) -> None:
        self.overlay.events.all.disconnect(self._update)
        self.node.events.parent_change.disconnect(self._on_parent_change)
        super().close()


class LabelManager:
    """Puts a label on every layer and decides where it is shown.

    :attr:`style` is the single source of truth; it is copied to one
    :class:`LabelStyle` per layer (``layer._overlays[KEY]``).  In
    fixed-on-screen mode the manager drives the napari canvas overlay
    returned by :meth:`_native` instead, and restores that overlay's
    previous settings once it no longer needs it.

    Use :meth:`for_viewer` to share one manager per viewer.
    """

    KEY: ClassVar[str]
    style_class: ClassVar[type[LabelStyle]]

    def __init__(self, viewer: ViewerModel, **settings: Any) -> None:
        # weak, so the per-viewer registry does not keep the viewer alive
        self._viewer = ref(viewer)
        self._visible = bool(settings.pop("visible", False))
        self.style = self.style_class(**settings)
        self._hidden: WeakSet[Layer] = WeakSet()
        # settings of native overlays from before this manager took them over
        self._native_saved: WeakKeyDictionary[Layer, dict] = (
            WeakKeyDictionary()
        )

        for layer in viewer.layers:
            self._attach(layer)
        events = viewer.layers.events
        events.inserted.connect(self._on_inserted)
        events.removed.connect(self._on_removed)
        events.reordered.connect(self._sync)
        grid = viewer.canvas.grid.events
        for event in (grid.enabled, grid.shape, grid.stride):
            event.connect(self._sync)
        self.style.events.all.connect(self._sync)
        self._sync()

    @property
    def viewer(self) -> ViewerModel:
        return self._viewer()

    @classmethod
    def for_viewer(cls, viewer: ViewerModel) -> LabelManager:
        """The manager of this class for ``viewer``, created on first use."""
        managers = _MANAGERS.setdefault(cls, WeakKeyDictionary())
        if viewer not in managers:
            managers[viewer] = cls(viewer)
        return managers[viewer]

    @property
    def visible(self) -> bool:
        return self._visible

    @visible.setter
    def visible(self, visible: bool) -> None:
        if visible != self._visible:
            self._visible = visible
            self._sync()

    @property
    def hidden_layers(self) -> set[Layer]:
        """Layers that should not get a label."""
        return set(self._hidden)

    @hidden_layers.setter
    def hidden_layers(self, layers) -> None:
        layers = set(layers)
        if layers != set(self._hidden):
            self._hidden = WeakSet(layers)
            self._sync()

    def update_settings(self, **settings: Any) -> None:
        batched_update(self.style, settings)

    def overlays(self) -> list[LabelStyle]:
        return [
            layer._overlays[self.KEY]
            for layer in self.viewer.layers
            if self.KEY in layer._overlays
        ]

    def cells(self, layers: list[Layer]) -> list[list[Layer]]:
        """``layers`` grouped by the view they are drawn in: their grid cell,
        or one group without grid mode."""
        grid = self.viewer.canvas.grid
        if not grid.enabled:
            return [list(layers)] if layers else []
        all_layers = self.viewer.layers
        groups: dict[tuple[int, int], list[Layer]] = {}
        for layer in layers:
            cell = grid.position(all_layers.index(layer), layers=all_layers)
            groups.setdefault(tuple(cell), []).append(layer)
        return list(groups.values())

    # -- hooks -----------------------------------------------------------

    def _shown(self) -> list[Layer]:
        """Layers whose label is shown (default: all selected layers)."""
        return [ly for ly in self.viewer.layers if ly not in self._hidden]

    def _native(self, layer: Layer) -> CanvasOverlay:
        raise NotImplementedError

    def _native_values(self, layer: Layer) -> dict[str, Any]:
        return self.style.native_style()

    # -- bookkeeping -----------------------------------------------------

    def _attach(self, layer: Layer) -> None:
        layer._overlays[self.KEY] = self.style_class()
        layer.events.visible.connect(self._sync)

    def _detach(self, layer: Layer) -> None:
        layer.events.visible.disconnect(self._sync)
        layer._overlays.pop(self.KEY, None)
        self._release_native(layer)

    def _release_native(self, layer: Layer) -> None:
        saved = self._native_saved.pop(layer, None)
        if saved is not None:
            self._native(layer).update(saved)

    def _on_inserted(self, event) -> None:
        self._attach(event.value)
        self._sync()

    def _on_removed(self, event) -> None:
        self._detach(event.value)
        self._sync()

    def _stacking(self, shown: list[Layer]) -> dict[Layer, dict]:
        """Stack position of each shown, visible layer within its view
        (topmost layer first)."""
        stacks = {}
        for cell in self.cells([ly for ly in shown if ly.visible]):
            for index, layer in enumerate(reversed(cell)):
                stacks[layer] = {
                    "stack_index": index,
                    "stack_count": len(cell),
                }
        return stacks

    def _sync(self, *_: Any) -> None:
        shown = set(self._shown()) if self._visible else set()
        stacks = self._stacking(
            [ly for ly in self.viewer.layers if ly in shown]
        )
        values = {
            **self.style.model_dump(exclude={"visible"}),
            "stack_index": 0,
            "stack_count": 1,
        }
        on_screen = not self.style.display_on_scene
        for layer in self.viewer.layers:
            overlay = layer._overlays.get(self.KEY)
            if overlay is None:
                continue
            on = layer in shown
            batched_update(
                overlay, {**values, **stacks.get(layer, {}), "visible": on}
            )
            if on and on_screen:
                native = self._native(layer)
                native_values = {**self._native_values(layer), "visible": True}
                if layer not in self._native_saved:
                    self._native_saved[layer] = {
                        key: getattr(native, key) for key in native_values
                    }
                native.update(native_values)
            else:
                self._release_native(layer)

    def close(self) -> None:
        events = self.viewer.layers.events
        events.inserted.disconnect(self._on_inserted)
        events.removed.disconnect(self._on_removed)
        events.reordered.disconnect(self._sync)
        grid = self.viewer.canvas.grid.events
        for event in (grid.enabled, grid.shape, grid.stride):
            event.disconnect(self._sync)
        self.style.events.all.disconnect(self._sync)
        for layer in self.viewer.layers:
            self._detach(layer)
        _MANAGERS.get(type(self), {}).pop(self.viewer, None)


_MANAGERS: dict[type, WeakKeyDictionary] = {}
