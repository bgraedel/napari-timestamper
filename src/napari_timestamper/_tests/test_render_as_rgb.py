import imageio.v3 as iio
import numpy as np
import pytest

from napari_timestamper.render_as_rgb import (
    RenderCancelled,
    render_as_rgb,
    save_image_stack,
)


@pytest.fixture
def viewer(make_napari_viewer):
    viewer = make_napari_viewer()
    # calibrated time axis: dims.range is in world units (0..330, step 30)
    viewer.add_image(np.random.random((12, 10, 10)), scale=(30, 1, 1))
    viewer.dims.set_current_step(0, 3)
    return viewer


def test_render_single_view(viewer):
    frame_shape = viewer.export_figure(flash=False).shape
    result = render_as_rgb(viewer)
    assert result.shape == frame_shape
    assert result.dtype == np.uint8


def test_render_axis_uses_frame_count_not_world_range(viewer):
    frame_shape = viewer.export_figure(flash=False).shape
    result = render_as_rgb(viewer, axis=0)
    assert result.shape == (12, *frame_shape)
    assert viewer.dims.current_step[0] == 3  # position restored


def test_render_frame_subset(viewer):
    assert render_as_rgb(viewer, axis=0, frames=[2, 5, 7]).shape[0] == 3


def test_render_multiple_axes(make_napari_viewer):
    viewer = make_napari_viewer()
    viewer.add_image(np.random.random((2, 3, 10, 10)))
    result = render_as_rgb(viewer, axis=[0, 1])
    assert result.shape[:2] == (2, 3)
    with pytest.raises(ValueError, match="single axis"):
        render_as_rgb(viewer, axis=[0, 1], frames=[0])


def test_render_upsample(viewer):
    single = render_as_rgb(viewer).shape
    double = render_as_rgb(viewer, upsample_factor=2).shape
    assert double[0] == pytest.approx(2 * single[0], abs=2)


def test_render_cancel_restores_position(viewer):
    calls = []

    def callback(done, total):
        calls.append((done, total))
        return done < 2

    with pytest.raises(RenderCancelled):
        render_as_rgb(viewer, axis=0, callback=callback)
    assert calls == [(1, 12), (2, 12)]
    assert viewer.dims.current_step[0] == 3


# opaque like real renders; random alpha makes GIF frames differ in mode
STACK = np.random.randint(0, 255, (3, 8, 10, 4), dtype=np.uint8)
STACK[..., 3] = 255


@pytest.mark.parametrize("output_type", ["tif", "gif"])
def test_save_stack_single_file(tmp_path, output_type):
    path = save_image_stack(STACK, tmp_path, "movie", output_type, fps=5)
    assert path == tmp_path / f"movie.{output_type}"
    assert iio.imread(path).shape[0] == 3


@pytest.mark.parametrize("output_type", ["png", "jpeg"])
def test_save_stack_series(tmp_path, output_type):
    folder = save_image_stack(STACK, tmp_path, "frames", output_type)
    files = sorted(folder.glob(f"*.{output_type}"))
    assert len(files) == 3
    channels = 4 if output_type == "png" else 3  # JPEG has no alpha
    assert iio.imread(files[0]).shape == (8, 10, channels)


def test_save_single_jpeg(tmp_path):
    path = save_image_stack(STACK[0], tmp_path, "still", "jpeg")
    assert iio.imread(path).shape == (8, 10, 3)


def test_save_movie_needs_frames(tmp_path):
    with pytest.raises(ValueError, match="more than one frame"):
        save_image_stack(STACK[0], tmp_path, "x", "gif")


def test_save_mp4_odd_size(tmp_path):
    # H.264 needs even sizes; napari exports are often odd-sized
    stack = np.random.randint(0, 255, (4, 9, 11, 4), dtype=np.uint8)
    path = save_image_stack(stack, tmp_path, "movie", "mp4", fps=5)
    assert iio.imread(path, plugin="pyav").shape == (4, 10, 12, 3)
