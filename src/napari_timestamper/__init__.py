try:
    from ._version import version as __version__
except ImportError:
    __version__ = "unknown"

from . import _compat  # noqa: F401  # clear error on unsupported napari
from ._layer_annotator_overlay import (
    LayerAnnotatorManager,
    LayerAnnotatorOverlay,
    VispyLayerAnnotatorOverlay,
)
from ._timestamp_overlay import (
    TimestampManager,
    TimestampOverlay,
    VispyTimestampOverlay,
    format_time,
)
from ._widget import (
    LayerAnnotationsWidget,
    LayertoRGBWidget,
    RenderRGBWidget,
    SplitStackWidget,
    TimestampWidget,
)
from .render_as_rgb import RenderCancelled, render_as_rgb, save_image_stack

__all__ = (
    "TimestampWidget",
    "LayerAnnotationsWidget",
    "RenderRGBWidget",
    "LayertoRGBWidget",
    "SplitStackWidget",
    "TimestampManager",
    "TimestampOverlay",
    "VispyTimestampOverlay",
    "format_time",
    "LayerAnnotatorManager",
    "LayerAnnotatorOverlay",
    "VispyLayerAnnotatorOverlay",
    "RenderCancelled",
    "render_as_rgb",
    "save_image_stack",
)
