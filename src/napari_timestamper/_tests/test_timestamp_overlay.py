import warnings

from napari._vispy.utils.visual import overlay_to_visual

from napari_timestamper._timestamp_overlay import (
    TimestampOverlay,
    VispyTimestampOverlay,
)


def test_timestamp_overlay():
    overlay = TimestampOverlay()
    assert overlay is not None


def test_text_instantiation(make_napari_viewer):
    viewer = make_napari_viewer()
    model = TimestampOverlay()
    VispyTimestampOverlay(overlay=model, viewer=viewer)
    # add overlay to viewer
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        try:
            viewer._overlays["timestamp"]
        except KeyError:
            viewer._overlays["timestamp"] = TimestampOverlay(visible=True)
            overlay_to_visual[TimestampOverlay] = VispyTimestampOverlay
            viewer.window._qt_viewer.canvas._add_overlay_to_visual(
                viewer._overlays["timestamp"]
            )
        timestamp_overlay = viewer._overlays["timestamp"]

    assert isinstance(timestamp_overlay, TimestampOverlay)
