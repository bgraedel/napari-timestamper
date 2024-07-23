import numpy as np

from napari_timestamper.render_as_rgb import render_as_rgb


def test_render_as_rgb(make_napari_viewer):
    viewer = make_napari_viewer()
    viewer.add_image(np.random.random((10, 10, 10)))

    # Test with default parameters
    result = render_as_rgb(viewer)
    assert result.shape == (10, 10, 4)
    assert result.dtype == np.uint8

    # Test with specified axis
    result = render_as_rgb(viewer, axis=0)
    assert result.shape == (10, 10, 10, 4)

    # Test with specified upsample_factor
    result = render_as_rgb(viewer, upsample_factor=2)
    assert result.shape == (20, 20, 4)
    viewer.close()
