from __future__ import annotations

import warnings
from pathlib import Path
from typing import Literal, Optional, Union

import napari
import numpy as np
from skimage import io


def render_as_rgb(
    viewer: napari.Viewer,
    axis: Optional[Union[int, list, np.array]] = None,
    upsample_factor: int = 1,
    **kwargs,
):
    """Render the viewer for a single timepoint or for a timelapse along specified axis."""
    size = kwargs.pop("size", None)
    if size:
        warnings.warn(
            "The size parameter is deprecated and will be removed in a future release. "
            "Please use the upsample_factor parameter instead.",
            DeprecationWarning,
            stacklevel=2,
        )
    if axis is not None:
        try:
            iter(axis)  # check if axis is iterable
        except TypeError:
            axis = [axis]
        if len(axis) == 1:
            axis = axis[0]
            target_shape = viewer.export_figure(
                scale_factor=upsample_factor, flash=False
            ).shape
            rgb = np.zeros(
                (viewer.dims.range[axis][1].astype(int) + 1, *target_shape),
                dtype=np.uint8,
            )
            for j in range(viewer.dims.range[axis][1].astype(int) + 1):
                viewer.dims.set_current_step(axis, j)
                rendered_img = viewer.export_figure(
                    scale_factor=upsample_factor, flash=False
                )
                rgb[j] = rendered_img
        else:
            target_shape = viewer.export_figure(
                scale_factor=upsample_factor, flash=False
            ).shape
            rgb = np.zeros(
                (
                    len(axis),
                    viewer.dims.range[axis[0]][1].astype(int) + 1,
                    *target_shape,
                ),
                dtype=np.uint8,
            )
            for ax in axis:
                for j in range(viewer.dims.range[ax][1].astype(int) + 1):
                    viewer.dims.set_current_step(ax, j)
                    rendered_img = viewer.export_figure(
                        scale_factor=upsample_factor, flash=False
                    )
                    rgb[ax, j] = rendered_img

    else:
        rgb = viewer.export_figure(scale_factor=upsample_factor, flash=False)
    return rgb


def save_image_stack(
    image,
    directory: Path | str = ".",
    name: str = "out",
    output_type: Literal["tif", "mp4", "gif", "png", "jpeg"] = "mp4",
    fps: int = 12,
):
    """Save an image stack as a tif, mp4, gif, png, or jpeg file.

    Parameters
    ----------
    image : np.ndarray
        Image stack to save.
    directory : Path | str, optional
        Directory to save the image stack, by default Path.cwd()
    name : str, optional
        Name of the file to save, by default "out"
    output_type : Literal["tif", "mp4", "gif", "png", "jpeg"], optional
        Type of file to save, by default "mp4"
    fps : int, optional
        Frames per second for mp4 and gif files, by default 12
    """
    if isinstance(directory, str):
        directory = Path(directory)
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
        h, w, _ = frame.shape

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
