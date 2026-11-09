from __future__ import annotations

import itertools
import warnings
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Literal

import napari
import numpy as np


class RenderCancelled(Exception):
    """Raised when the progress callback of :func:`render_as_rgb` aborts."""


def render_as_rgb(
    viewer: napari.Viewer,
    axis: int | Sequence[int] | None = None,
    upsample_factor: float = 1,
    frames: Sequence[int] | None = None,
    callback: Callable[[int, int], bool | None] | None = None,
    **kwargs,
) -> np.ndarray:
    """Render the viewer (with all overlays) as RGBA images.

    Parameters
    ----------
    viewer : napari.Viewer
        Viewer to render.
    axis : int or sequence of int, optional
        Slider axis (or axes) to step through.  ``None`` renders the current
        view only.  With several axes every combination is rendered and the
        result has one leading dimension per axis.
    upsample_factor : float
        Resolution multiplier passed to ``viewer.export_figure``.
    frames : sequence of int, optional
        Frame indices to render along a single ``axis`` (default: all).
    callback : callable, optional
        Called as ``callback(done, total)`` after each frame; returning
        ``False`` aborts with :class:`RenderCancelled`.

    Returns
    -------
    np.ndarray
        ``(h, w, 4)`` for a single view, otherwise ``(*n_frames, h, w, 4)``.
        The viewer is returned to its original position afterwards.
    """
    if kwargs.pop("size", None):
        warnings.warn(
            "The size parameter is deprecated and will be removed in a future release. "
            "Please use the upsample_factor parameter instead.",
            DeprecationWarning,
            stacklevel=2,
        )

    def snap() -> np.ndarray:
        return viewer.export_figure(scale_factor=upsample_factor, flash=False)

    if axis is None:
        return snap()

    axes = [int(a) for a in np.atleast_1d(axis)]
    if frames is not None and len(axes) != 1:
        raise ValueError("`frames` can only be used with a single axis")
    ranges = [
        list(frames) if frames is not None else range(viewer.dims.nsteps[a])
        for a in axes
    ]
    shape = tuple(len(r) for r in ranges)
    total = int(np.prod(shape))

    original_step = viewer.dims.current_step
    rgb = None
    try:
        for n, steps in enumerate(itertools.product(*ranges)):
            for ax, step in zip(axes, steps, strict=False):
                viewer.dims.set_current_step(ax, step)
            image = snap()
            if rgb is None:
                rgb = np.zeros((*shape, *image.shape), dtype=np.uint8)
            rgb[np.unravel_index(n, shape)] = image
            if callback is not None and callback(n + 1, total) is False:
                raise RenderCancelled
    finally:
        viewer.dims.current_step = original_step
    return rgb


def save_image_stack(
    image: np.ndarray,
    directory: Path | str = ".",
    name: str = "out",
    output_type: Literal["tif", "mp4", "gif", "png", "jpeg"] = "mp4",
    fps: int = 12,
) -> Path:
    """Save an RGBA image or image stack.

    Parameters
    ----------
    image : np.ndarray
        ``(h, w, 4)`` image or ``(..., h, w, 4)`` stack.  Extra leading
        dimensions are flattened into frames for movies and image series.
    directory : Path | str, optional
        Output directory.
    name : str, optional
        File name without extension.
    output_type : {"tif", "mp4", "gif", "png", "jpeg"}, optional
        ``tif`` keeps the full stack in one file; ``png``/``jpeg`` write one
        file per frame into ``directory/name/``.
    fps : int, optional
        Frames per second for mp4 and gif files.

    Returns
    -------
    Path
        The written file (or folder for png/jpeg series).
    """
    import imageio.v3 as iio

    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    outpath = directory / f"{name}.{output_type}"
    single = image.ndim == 3
    frames = image.reshape(-1, *image.shape[-3:])

    if output_type == "tif":
        iio.imwrite(outpath, image)
    elif output_type in ("mp4", "gif") and single:
        raise ValueError(f"{output_type} export needs more than one frame")
    elif output_type == "mp4":
        # H.264 (plays in browsers and slide software) needs even sizes
        h, w = frames.shape[1:3]
        rgb = np.pad(
            frames[..., :3],
            ((0, 0), (0, h % 2), (0, w % 2), (0, 0)),
            mode="edge",
        )
        iio.imwrite(outpath, rgb, plugin="pyav", codec="libx264", fps=fps)
    elif output_type == "gif":
        iio.imwrite(outpath, frames, duration=1000 / fps, loop=0)
    elif output_type in ("png", "jpeg"):
        if output_type == "jpeg":  # JPEG has no alpha channel
            frames = frames[..., :3]
        if single:
            iio.imwrite(outpath, frames[0])
        else:
            outpath = directory / name
            outpath.mkdir(exist_ok=True)
            for i, frame in enumerate(frames):
                iio.imwrite(outpath / f"{name}_{i}.{output_type}", frame)
    else:
        raise ValueError(f"Unknown output type: {output_type!r}")
    return outpath
