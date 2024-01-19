from __future__ import annotations

import warnings
from pathlib import Path
from typing import Literal, Optional, Union

import napari
import numpy as np
from skimage import io


class CameraSetter:
    """A context manager to adjust viewer camera settings before rendering."""

    def __init__(
        self, viewer, upsample_factor=1, size: tuple(int, int) | None = None
    ):
        self.viewer = viewer
        # get initial settings
        self.center = viewer.camera.center
        self.zoom = viewer.camera.zoom
        self.angles = viewer.camera.angles

        self.input_canvas_size = viewer.window.qt_viewer.canvas.size

        extent = viewer._sliced_extent_world[:, -2:]
        scene_size = (
            (extent[1] - extent[0])
            / viewer.window.qt_viewer.canvas.pixel_scale
            * upsample_factor
        )  # adjust for pixel scaling
        grid_size = list(viewer.grid.actual_shape(len(viewer.layers)))

        # Adjust grid_size if necessary
        if len(scene_size) > len(grid_size):
            grid_size = [1] * (len(scene_size) - len(grid_size)) + grid_size

        # calculate target size i.e the size the canvas should be to fit the whole scene
        if size is None:
            self.target_size = tuple(
                (scene_size[::-1] * grid_size[::-1]).astype(int)
            )
        else:
            self.target_size = size
        self.center = viewer.camera.center
        self.zoom = viewer.camera.zoom
        self.angles = viewer.camera.angles

    # copied from viewer.reset_view and modified without padding
    def _center_on_canvas(self):
        """Reset the camera view."""
        extent = self.viewer._sliced_extent_world
        scene_size = extent[1] - extent[0]
        corner = extent[0]
        grid_size = list(
            self.viewer.grid.actual_shape(len(self.viewer.layers))
        )
        if len(scene_size) > len(grid_size):
            grid_size = [1] * (len(scene_size) - len(grid_size)) + grid_size
        size = np.multiply(scene_size, grid_size)
        center = np.add(corner, np.divide(size, 2))[
            -self.viewer.dims.ndisplay :
        ]
        center = [0] * (self.viewer.dims.ndisplay - len(center)) + list(center)
        self.viewer.camera.center = center

        if np.max(size) == 0:
            self.viewer.camera.zoom = np.min(self.viewer._canvas_size)
        else:
            scale = np.array(size[-2:])
            scale[np.isclose(scale, 0)] = 1
            self.viewer.camera.zoom = 1 * np.min(
                np.array(self.viewer._canvas_size) / scale
            )
        self.viewer.camera.angles = (0, 0, 90)

    def __enter__(self):
        """Set up the viewer for rendering."""
        self.viewer.window.qt_viewer.canvas.size = self.target_size
        self._center_on_canvas()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Reset the viewer after rendering."""
        self.viewer.window.qt_viewer.canvas.size = self.input_canvas_size
        self.viewer.camera.center = self.center
        self.viewer.camera.zoom = self.zoom
        self.viewer.camera.angles = self.angles


def render_as_rgb(
    viewer: napari.Viewer,
    axis: Optional[Union[int, list, np.array]] = None,
    size: tuple(int, int) | None = None,
    upsample_factor: int = 1,
):
    """Render the viewer for a single timepoint."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        with CameraSetter(viewer, upsample_factor, size) as setter:
            if axis is not None:
                try:
                    iter(axis)  # check if axis is iterable
                except TypeError:
                    axis = [axis]
                # calculate array output size
                arr_out_size = [len(np.arange(*r)) for r in viewer.dims.range]
                arr_out_size[-2:] = (
                    np.array(setter.target_size)[::-1]
                    * viewer.window.qt_viewer.canvas.pixel_scale
                )
                # convert to int
                arr_out_size = [int(i) for i in arr_out_size]
                # create an empty array matching the size of the expected output
                rgb = np.zeros(
                    (
                        *tuple(arr_out_size),
                        3,
                    ),
                    dtype=np.uint8,
                )
                if len(axis) == 1:
                    axis = axis[0]
                    for j in range(viewer.dims.range[axis][1].astype(int)):
                        viewer.dims.set_current_step(axis, j)
                        rendered_img = viewer.window.qt_viewer.canvas.render(
                            alpha=False
                        )
                        rgb[j] = rendered_img
                else:
                    for ax in axis:
                        for j in range(viewer.dims.range[ax][1].astype(int)):
                            viewer.dims.set_current_step(ax, j)
                            rendered_img = (
                                viewer.window.qt_viewer.canvas.render(
                                    alpha=False
                                )
                            )
                            rgb[ax, j] = rendered_img

            else:
                rgb = viewer.window.qt_viewer.canvas.render(alpha=False)
    return rgb


def save_image_stack(
    image,
    directory=Path(),
    name: str = "out",
    output_type: Literal["tif", "mp4", "gif", "png", "jpeg"] = "mp4",
    fps: int = 12,
):
    outpath = directory.joinpath(f"{name}.{output_type}").as_posix()
    if output_type == "tif":
        io.imsave(outpath, image)
    elif output_type == "mp4":
        try:
            import cv2
        except ImportError as e:
            raise ImportError(
                "You must install opencv to export as mp4, try `pip install opencv-python`"
            ) from e

        if image.ndim == 3:
            raise ValueError("Mp4 export only works for 3D+ data")

        # Read the first image to get the width, height
        frame = image[0]
        h, w, layers = frame.shape

        # Define the codec and create a VideoWriter object
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        out = cv2.VideoWriter(outpath, fourcc, fps, (w, h))

        for i in image:
            out.write(
                cv2.cvtColor(i, cv2.COLOR_RGBA2BGR)
            )  # Write out frame to video

        # Release everything when the job is finished
        out.release()
        try:
            cv2.destroyAllWindows()
        except cv2.error:
            print("could not close cv2 windows")

    elif output_type == "gif":
        try:
            import imageio
        except ImportError as e:
            raise ImportError(
                "You must install imageio to export as gif, try `pip install imageio`"
            ) from e
        if image.ndim == 3:
            raise ValueError("Gif export only works for 3D+ data")
        imageio.mimsave(outpath, image, duration=1000 * 1 / fps)

    elif output_type in ["png", "jpeg"]:
        try:
            import imageio
        except ImportError as e:
            raise ImportError(
                "You must install imageio to export as png or jpeg, try `pip install imageio`"
            ) from e
        if image.ndim == 3:
            imageio.imwrite(outpath, image)
        else:
            # create a new directory
            directory = directory.joinpath(name)
            directory.mkdir(exist_ok=True)

            for i, current_image in enumerate(image):
                outpath = directory.joinpath(
                    f"{name}_{i}.{output_type}"
                ).as_posix()
                imageio.imwrite(outpath, current_image)
