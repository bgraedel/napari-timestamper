"""
LayerAnnotatorOverlay for napari >= 0.6.2 (ViewBox-based grid mode).

BLENDING / DFS DRAW ORDER FIX
-------------------------------
vispy._generate_draw_order is a DFS. Children always render inside their
parent's bracket:

    (Layer1, True) → (OurOverlay, True/False) → (Layer1, False)
    (Layer2, True) ...

Layer2 renders after OurOverlay even though OurOverlay.order=1000000,
because order only sorts SIBLINGS at each DFS level.  Layer2's additive
blending then composites on top of OurOverlay's black background.

Fix: re-parent from the layer node to the ViewBox scene (its sibling level).
OurOverlay then becomes a sibling of all layer nodes and, with order=1000000,
renders after every layer.

_update_scenegraph (triggered by grid.enabled/shape/stride/spacing,
layers.reordered, layer add/remove) calls _update_layer_overlays which
always resets node.parent back to layer_node.  We fix this by:

  1. Saving self._layer_node = parent at creation time.
  2. Calling _reparent_to_viewbox_scene() — which uses
     self._layer_node.parent as the reliable, always-current target —
     at the start of every _on_position_change and _on_visible_change.
  3. Connecting to ALL events that trigger _update_scenegraph.

EVENT CONNECTIONS
-----------------
Events that trigger _update_scenegraph → _update_layer_overlays (resets parent):
  viewer.grid.events.enabled   ← was connected, now also re-parents
  viewer.grid.events.shape     ← NEW
  viewer.grid.events.stride    ← NEW
  viewer.grid.events.spacing   ← NEW
  viewer.layers.events.reordered  ← was connected, now also re-parents
  viewer.layers.events.inserted   ← was connected, now also re-parents
  viewer.layers.events.removed    ← was connected, now also re-parents
  layer.events.visible            ← handled in _on_visible_change override

VISIBILITY FIX
--------------
Previously node.visible was only restored inside `if grid.enabled:`, so
switching grid off left the node hidden if the image had scrolled out of
view.  We now reset visibility at the TOP of _on_position_change so it is
always correct before any branch runs.

LAYOUT
------
anchor_y = "bottom" everywhere; rect extends DOWNWARD from pos_y.
TOP:    y_base = y_min + idx * step   (inside image, stacks down)
BOTTOM: y_base = y_max - (idx+1)*step (inside image, stacks up)
Width from shape×scale (avoids pixel-centre 1-px shortfall).
"""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING, Any

from napari._vispy.overlays.base import LayerOverlayMixin, VispySceneOverlay
from napari._vispy.utils.gl import BLENDING_MODES
from napari._vispy.utils.visual import overlay_to_visual
from napari.components.overlays import SceneOverlay
from napari.layers import labels
from pydantic import ConfigDict
from vispy.color import ColorArray

from napari_timestamper.text_visual import TextWithBoxVisual

if TYPE_CHECKING:
    from napari.components import ViewerModel
    from napari.layers import Layer
    from vispy.scene import Node


# ---------------------------------------------------------------------------
# Position enum
# ---------------------------------------------------------------------------
try:
    from napari.components._viewer_constants import (
        CanvasPosition as ScenePosition,
    )
except ImportError:
    import enum

    class ScenePosition(str, enum.Enum):
        TOP_LEFT = "top_left"
        TOP_CENTER = "top_center"
        TOP_RIGHT = "top_right"
        BOTTOM_RIGHT = "bottom_right"
        BOTTOM_CENTER = "bottom_center"
        BOTTOM_LEFT = "bottom_left"


CanvasPosition = ScenePosition


# ---------------------------------------------------------------------------
# Anchor map (anchor_y always "bottom" → rect extends DOWNWARD)
# ---------------------------------------------------------------------------
_ANCHOR_MAP: dict[str, tuple[str, str]] = {
    "top_left": ("left", "bottom"),
    "top_center": ("center", "bottom"),
    "top_right": ("right", "bottom"),
    "bottom_left": ("left", "bottom"),
    "bottom_center": ("center", "bottom"),
    "bottom_right": ("right", "bottom"),
}


# ---------------------------------------------------------------------------
# Overlay model
# ---------------------------------------------------------------------------


class LayerAnnotatorOverlay(SceneOverlay):
    """Scene overlay that draws the layer name at a corner of the layer image."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    color: str = "white"
    use_layer_color: bool = False
    size: int = 12
    bold: bool = False
    italic: bool = False
    position: ScenePosition = ScenePosition.TOP_LEFT
    bg_color: ColorArray = ColorArray(["black"])
    show_outline: bool = False
    outline_color: ColorArray = ColorArray(["white"])
    outline_thickness: float = 1.0
    show_background: bool = False


# ---------------------------------------------------------------------------
# Vispy backend
# ---------------------------------------------------------------------------


class VispyLayerAnnotatorOverlay(LayerOverlayMixin, VispySceneOverlay):
    """
    Renders a layer-name label in world/scene space for one layer.

    Normally napari parents SceneOverlays to the layer's vispy node, but we
    immediately re-parent to the ViewBox scene (one level up) so our
    order=1000000 puts us after ALL layer nodes in vispy's DFS draw order.
    """

    overlay: LayerAnnotatorOverlay

    def __init__(
        self,
        *,
        viewer: ViewerModel,
        overlay: LayerAnnotatorOverlay,
        layer: Layer,
        parent: Node | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            node=TextWithBoxVisual(
                text=[layer.name],
                color=self._layer_color(layer, overlay),
                font_size=overlay.size,
                pos=(0, 0),
                bold=overlay.bold,
                italic=overlay.italic,
            ),
            layer=layer,
            viewer=viewer,
            overlay=overlay,
            parent=parent,
            **kwargs,
        )

        # Save the layer's vispy node reference.  _reparent_to_viewbox_scene()
        # uses self._layer_node.parent as the target, which napari keeps
        # up-to-date as the layer moves between ViewBoxes on grid changes.
        self._layer_node: Node | None = parent

        # spacer=0: box edges align exactly with image boundary
        self.node._rectagles_visual.spacer = 0

        # Zoom scale: text grows with image
        self._camera_zoom: float = max(self.viewer.camera.zoom, 1e-6)
        self.node.scale_factor = self._camera_zoom

        # --- layer events ---
        self.layer.events.name.connect(self._on_property_change)
        with contextlib.suppress(AttributeError):
            self.layer.events.colormap.connect(self._on_property_change)
        with contextlib.suppress(AttributeError):
            self.layer.events.scale.connect(self._on_position_change)
        with contextlib.suppress(AttributeError):
            self.layer.events.translate.connect(self._on_position_change)

        # --- overlay events ---
        self.overlay.events.size.connect(self._on_size_change)
        self.overlay.events.position.connect(self._on_position_change)
        self.overlay.events.color.connect(self._on_property_change)
        self.overlay.events.use_layer_color.connect(self._on_property_change)
        self.overlay.events.bold.connect(self._on_property_change)
        self.overlay.events.italic.connect(self._on_property_change)
        self.overlay.events.bg_color.connect(self._on_property_change)
        self.overlay.events.show_background.connect(self._on_property_change)
        self.overlay.events.show_outline.connect(self._on_property_change)
        self.overlay.events.outline_color.connect(self._on_property_change)
        self.overlay.events.outline_thickness.connect(self._on_property_change)

        # --- viewer events (all events that trigger _update_scenegraph) ---
        self.viewer.camera.events.zoom.connect(self._on_zoom_change)
        self.viewer.camera.events.center.connect(self._on_position_change)
        self.viewer.dims.events.ndisplay.connect(self._on_property_change)

        # Grid events — ALL of these trigger _update_scenegraph
        self.viewer.grid.events.enabled.connect(self._on_position_change)
        self.viewer.grid.events.shape.connect(self._on_position_change)
        self.viewer.grid.events.stride.connect(self._on_position_change)
        self.viewer.grid.events.spacing.connect(self._on_position_change)

        # Layer list events — also trigger _update_scenegraph
        self.viewer.layers.events.reordered.connect(self._on_position_change)
        self.viewer.layers.events.inserted.connect(self._on_position_change)
        self.viewer.layers.events.removed.connect(self._on_position_change)

        self.reset()

        # Re-parent AFTER reset().  Must be last in __init__ so napari hasn't
        # had a chance to reset the parent back to layer_node yet.
        self._reparent_to_viewbox_scene()

    # ------------------------------------------------------------------
    # Re-parenting
    # ------------------------------------------------------------------

    def _reparent_to_viewbox_scene(self) -> None:
        """
        Move our node to be a sibling of the layer node (child of ViewBox scene).

        Target = self._layer_node.parent, which napari keeps current:
          - non-grid: self._layer_node.parent = self.view.scene
          - grid:     self._layer_node.parent = specific_viewbox.scene

        Using self._layer_node (saved at creation) instead of
        self.node.parent avoids the "walk one level too high" bug that
        occurs when we're already correctly parented.
        """
        try:
            if self._layer_node is None:
                return
            target = self._layer_node.parent
            if target is None:
                return
            if self.node.parent is not target:
                self.node.parent = target
        except Exception:  # noqa: BLE001
            pass

    # ------------------------------------------------------------------
    # GL state
    # ------------------------------------------------------------------

    def _apply_subvisual_gl_state(self) -> None:
        """
        Force translucent_no_depth on all sub-visuals.

        Previously the background rect used blend=False (truly opaque) to
        survive additive-layer blending.  That is no longer needed because
        re-parenting to the ViewBox scene ensures we render AFTER all layer
        nodes in vispy's DFS, so no subsequent layer can overwrite us.

        Using translucent_no_depth for the rect:
        - depth_test=False  → always drawn on top
        - standard src_alpha blending → background opacity works correctly
        - resets the active GL blend function → not affected by a layer's
          additive/minimum blend mode that ran just before us
        """
        _tnd = BLENDING_MODES["translucent_no_depth"]
        for sv in (
            self.node._rectagles_visual,
            self.node._textvisual,
            self.node._outline_visual,
            self.node._corner_markers,
        ):
            sv.set_gl_state(**_tnd)

    def _on_blending_change(self, event=None) -> None:
        # super() propagates translucent_no_depth to all sub-visuals via
        # CompoundVisual.set_gl_state(); _apply_subvisual_gl_state reaffirms
        # the same state so both paths stay consistent.
        super()._on_blending_change()
        self._apply_subvisual_gl_state()

    # ------------------------------------------------------------------
    # Visible change (re-parent after napari resets parent)
    # ------------------------------------------------------------------

    def _on_visible_change(self, event=None) -> None:
        """
        layer.events.visible triggers _update_layer_overlays (canvas, first)
        which resets node.parent = layer_node.  Our handler fires second
        (canvas connected earlier) and re-parents back to ViewBox scene.
        """
        super()._on_visible_change()
        self._reparent_to_viewbox_scene()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _layer_color(layer: Layer, overlay: LayerAnnotatorOverlay) -> Any:
        if not overlay.use_layer_color:
            return overlay.color
        if isinstance(layer, labels.Labels):
            return overlay.color
        try:
            return layer.colormap.colors[-1]
        except AttributeError:
            return overlay.color

    def _get_layer_extent(self) -> tuple[float, float, float, float, float]:
        """Return (x_min, y_min, x_max, y_max, width) in world/scene space."""
        try:
            ext = self.layer.extent.world
            y_min = float(ext[0][-2])
            x_min = float(ext[0][-1])
            y_max = float(ext[1][-2])
            x_max = float(ext[1][-1])
        except Exception:  # noqa: BLE001
            shape = self.layer.data.shape
            scale = list(getattr(self.layer, "scale", [1.0] * len(shape)))
            translate = list(
                getattr(self.layer, "translate", [0.0] * len(shape))
            )
            y_min = float(translate[-2])
            x_min = float(translate[-1])
            y_max = y_min + shape[-2] * float(scale[-2])
            x_max = x_min + shape[-1] * float(scale[-1])
        try:
            width = self.layer.data.shape[-1] * float(self.layer.scale[-1])
        except Exception:  # noqa: BLE001
            width = x_max - x_min
        return x_min, y_min, x_max, y_max, width

    def _get_camera_rect(
        self, layer_width: float, layer_height: float
    ) -> tuple[float, float, float, float] | None:
        """
        Visible world rect of the current ViewBox camera.

        Uses r.left/right/top/bottom (not r.pos/size) for y-up/y-down safety.
        Rejects the vispy default (0,0,1,1) before first render via the
        1%-of-layer-size sanity check.
        """
        try:
            # We're in viewbox_scene; one level up is the ViewBox (has camera)
            node = self.node.parent  # viewbox_scene
            if node is not None:
                node = node.parent  # ViewBox
            for _ in range(20):
                if node is None:
                    break
                cam = getattr(node, "camera", None)
                if cam is not None and hasattr(cam, "rect"):
                    r = cam.rect
                    vx0 = min(float(r.left), float(r.right))
                    vx1 = max(float(r.left), float(r.right))
                    vy0 = min(float(r.bottom), float(r.top))
                    vy1 = max(float(r.bottom), float(r.top))
                    if (vx1 - vx0) < layer_width * 0.01:
                        return None
                    if (vy1 - vy0) < layer_height * 0.01:
                        return None
                    return vx0, vy0, vx1, vy1
                node = node.parent
        except Exception:  # noqa: BLE001
            pass
        return None

    def _label_height_world(self) -> float:
        return self.overlay.size * TextWithBoxVisual.RECTANGLE_SCALER

    def _stack_index(self) -> int:
        """0 = topmost visible layer.  Always 0 in grid mode."""
        if self.viewer.grid.enabled:
            return 0
        visible = [
            layer for layer in reversed(self.viewer.layers) if layer.visible
        ]
        try:
            return visible.index(self.layer)
        except ValueError:
            return 0

    # ------------------------------------------------------------------
    # Event callbacks
    # ------------------------------------------------------------------

    def _on_zoom_change(self, event=None) -> None:
        self._camera_zoom = max(self.viewer.camera.zoom, 1e-6)
        self.node.scale_factor = self._camera_zoom
        self._on_size_change()

    def _on_property_change(self, event=None) -> None:
        in_3d = self.viewer.dims.ndisplay == 3
        self.node.show_outline = False if in_3d else self.overlay.show_outline
        self.node._rectagles_visual.visible = (
            False if in_3d else self.overlay.show_background
        )
        self.node.text = [self.layer.name]
        self.node.bold = self.overlay.bold
        self.node.italic = self.overlay.italic
        self.node.outline_color = self.overlay.outline_color
        self.node.outline_thickness = self.overlay.outline_thickness
        self.node.bgcolor = self.overlay.bg_color.rgba.tolist()
        self.node.color = self._layer_color(self.layer, self.overlay)
        self._on_size_change()
        self.node.update()

    def _on_size_change(self, event=None) -> None:
        self.node.font_size = self.overlay.size
        self.node.outline_thickness = self.overlay.outline_thickness
        self._on_position_change()

    def _on_position_change(self, event=None) -> None:
        """
        Recompute and apply label position.

        Called for ALL events that might reset our parent (grid changes,
        layer reorder, etc.).  The first two steps handle the side effects
        of those resets before doing any positioning work.
        """
        # 1. Re-parent in case _update_scenegraph reset us to layer_node.
        self._reparent_to_viewbox_scene()

        # 2. Restore correct visibility (node may have been hidden by a
        #    previous grid-mode clamp; must reset before any early-return).
        self.node.visible = self._should_be_visible()

        x_min, y_min, x_max, y_max, width = self._get_layer_extent()
        if width <= 0:
            return

        layer_h = y_max - y_min

        # 3. Grid sticky: clamp to visible viewport ∩ layer_extent
        if self.viewer.grid.enabled:
            cam = self._get_camera_rect(width, layer_h)
            if cam is not None:
                vx0, vy0, vx1, vy1 = cam
                x_min = max(x_min, vx0)
                y_min = max(y_min, vy0)
                x_max = min(x_max, vx1)
                y_max = min(y_max, vy1)
                width = max(x_max - x_min, 0)
                if width <= 0 or y_max <= y_min:
                    self.node.visible = False
                    return

        position = str(self.overlay.position)
        step = self._label_height_world()
        idx = self._stack_index()

        if "top" in position:
            y_base = y_min - 0.5 + idx * step
        else:
            y_base = y_max + 0.5 - (idx + 1) * step

        if "left" in position:
            px = x_min - 0.5
        elif "right" in position:
            px = x_max + 0.5
        else:
            px = (x_min + x_max) / 2

        anchors = _ANCHOR_MAP.get(position, ("left", "bottom"))
        self.node.anchors = anchors
        self.node.update_data(
            text=[self.layer.name],
            color=self._layer_color(self.layer, self.overlay),
            font_size=self.overlay.size,
            pos=[(px, y_base)],
            box_width=[width],
            bgcolor=self.overlay.bg_color.rgba.tolist(),
            hide_parial_outline=None,
        )
        self.node.update()

    # ------------------------------------------------------------------
    # Reset / teardown
    # ------------------------------------------------------------------

    def reset(self) -> None:
        super().reset()
        self._on_property_change()

    def close(self) -> None:
        _disconnects = [
            (self._on_zoom_change, self.viewer.camera.events.zoom),
            (self._on_position_change, self.viewer.camera.events.center),
            (self._on_position_change, self.viewer.grid.events.enabled),
            (self._on_position_change, self.viewer.grid.events.shape),
            (self._on_position_change, self.viewer.grid.events.stride),
            (self._on_position_change, self.viewer.grid.events.spacing),
            (self._on_position_change, self.viewer.layers.events.reordered),
            (self._on_position_change, self.viewer.layers.events.inserted),
            (self._on_position_change, self.viewer.layers.events.removed),
        ]
        for cb, event in _disconnects:
            with contextlib.suppress(Exception):
                event.disconnect(cb)
        super().close()


# ---------------------------------------------------------------------------
# Register with napari's overlay factory
# ---------------------------------------------------------------------------
overlay_to_visual[LayerAnnotatorOverlay] = VispyLayerAnnotatorOverlay


# ---------------------------------------------------------------------------
# Manager
# ---------------------------------------------------------------------------


class LayerAnnotatorManager:
    """Attaches a LayerAnnotatorOverlay to every layer and keeps them in sync."""

    OVERLAY_KEY = "layer_annotator"

    def __init__(
        self,
        viewer: ViewerModel,
        overlay_key: str = OVERLAY_KEY,
        **settings: Any,
    ) -> None:
        self.viewer = viewer
        self.overlay_key = overlay_key
        self._settings: dict[str, Any] = settings

        for layer in self.viewer.layers:
            self._attach(layer)

        self.viewer.layers.events.inserted.connect(self._on_layer_inserted)
        self.viewer.layers.events.removed.connect(self._on_layer_removed)

    def _attach(self, layer: Layer) -> None:
        if self.overlay_key not in layer._overlays:
            layer._overlays[self.overlay_key] = LayerAnnotatorOverlay(
                **self._settings
            )

    def _detach(self, layer: Layer) -> None:
        layer._overlays.pop(self.overlay_key, None)

    def _on_layer_inserted(self, event) -> None:
        self._attach(event.value)

    def _on_layer_removed(self, event) -> None:
        self._detach(event.value)

    def update_settings(self, **settings: Any) -> None:
        """Apply *settings* to every managed overlay."""
        self._settings.update(settings)
        for layer in self.viewer.layers:
            overlay = layer._overlays.get(self.overlay_key)
            if overlay is not None:
                for key, value in settings.items():
                    setattr(overlay, key, value)

    def get_any_overlay(self) -> LayerAnnotatorOverlay | None:
        for layer in self.viewer.layers:
            overlay = layer._overlays.get(self.overlay_key)
            if overlay is not None:
                return overlay
        return None

    def set_visible(self, visible: bool) -> None:
        self._settings["visible"] = visible
        for layer in self.viewer.layers:
            overlay = layer._overlays.get(self.overlay_key)
            if overlay is not None:
                overlay.visible = visible

    def set_layer_visible(self, layer_name: str, visible: bool) -> None:
        for layer in self.viewer.layers:
            if layer.name == layer_name:
                overlay = layer._overlays.get(self.overlay_key)
                if overlay is not None:
                    overlay.visible = visible

    def close(self) -> None:
        self.viewer.layers.events.inserted.disconnect(self._on_layer_inserted)
        self.viewer.layers.events.removed.disconnect(self._on_layer_removed)
        for layer in self.viewer.layers:
            self._detach(layer)
