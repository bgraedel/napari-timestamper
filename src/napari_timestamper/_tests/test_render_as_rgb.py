import napari
import numpy as np

from napari_timestamper.render_as_rgb import render_as_rgb


def test_render_as_rgb():
    viewer = napari.Viewer()  # doesn't work with make_napari_viewer
    viewer.add_image(np.random.random((10, 10, 10)))

    # Test with default parameters
    result = render_as_rgb(viewer)
    assert result.shape == (10, 10, 3)
    assert result.dtype == np.uint8

    # Test with specified axis
    result = render_as_rgb(viewer, axis=0)
    assert result.shape == (10, 10, 10, 3)

    # Test with specified size
    result = render_as_rgb(viewer, size=(20, 20))
    assert result.shape == (20, 20, 3)

    # Test with specified upsample_factor
    result = render_as_rgb(viewer, upsample_factor=2)
    assert result.shape == (20, 20, 3)
    viewer.close()
