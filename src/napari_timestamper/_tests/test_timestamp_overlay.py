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
