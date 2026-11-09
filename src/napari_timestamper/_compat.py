"""Fail early, with a clear message, on unsupported napari versions."""

import re
from importlib.metadata import version

NAPARI_VERSION = version("napari")

if tuple(int(n) for n in re.findall(r"\d+", NAPARI_VERSION)[:2]) < (0, 10):
    raise ImportError(
        f"napari-timestamper requires napari >= 0.10 (found {NAPARI_VERSION}); "
        "upgrade napari or install napari-timestamper<0.7"
    )
