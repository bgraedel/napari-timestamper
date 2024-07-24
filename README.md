# napari-timestamper

[![License BSD-3](https://img.shields.io/pypi/l/napari-timestamper.svg?color=green)](https://github.com/bgraedel/napari-timestamper/raw/main/LICENSE)
[![PyPI](https://img.shields.io/pypi/v/napari-timestamper.svg?color=green)](https://pypi.org/project/napari-timestamper)
[![Python Version](https://img.shields.io/pypi/pyversions/napari-timestamper.svg?color=green)](https://python.org)
[![tests](https://github.com/bgraedel/napari-timestamper/workflows/tests/badge.svg)](https://github.com/bgraedel/napari-timestamper/actions)
[![codecov](https://codecov.io/gh/bgraedel/napari-timestamper/branch/main/graph/badge.svg)](https://codecov.io/gh/bgraedel/napari-timestamper)
<!-- [![napari hub](https://img.shields.io/endpoint?url=https://api.napari-hub.org/shields/napari-timestamper)](https://napari-hub.org/plugins/napari-timestamper) -->

A collection of useful widgets to annotate images with overlays and export them as rgb images/movies.

With this plugin you can:
- Annotate Layers with their respective names and colors
- Annotate Layers with a timestamp
- Export the annotated layers as an RGB image or a movie
- Convert Layers to RGB stacks and add them back to the viewer

uses some private overlay functionality, so may break in the future

## Demos
### Annotate Layers with their respective names and colors
![](https://github.com/user-attachments/assets/7108a3e1-6bd5-4a55-838f-9359b6f3a78b)

### Annotate Layers with a timestamp
![](https://github.com/user-attachments/assets/7108a3e1-6bd5-4a55-838f-9359b6f3a78b)

----------------------------------

This [napari] plugin was generated with [Cookiecutter] using [@napari]'s [cookiecutter-napari-plugin] template.

## Installation

You can install `napari-timestamper` via [pip]:

    pip install napari-timestamper



To install latest development version :

    pip install git+https://github.com/bgraedel/napari-timestamper.git


## Contributing

Contributions are very welcome. Tests can be run with [tox], please ensure
the coverage at least stays the same before you submit a pull request.

## License

Distributed under the terms of the [BSD-3] license,
"napari-timestamper" is free and open source software

## Issues

If you encounter any problems, please [file an issue] along with a detailed description.

[napari]: https://github.com/napari/napari
[Cookiecutter]: https://github.com/audreyr/cookiecutter
[@napari]: https://github.com/napari
[MIT]: http://opensource.org/licenses/MIT
[BSD-3]: http://opensource.org/licenses/BSD-3-Clause
[GNU GPL v3.0]: http://www.gnu.org/licenses/gpl-3.0.txt
[GNU LGPL v3.0]: http://www.gnu.org/licenses/lgpl-3.0.txt
[Apache Software License 2.0]: http://www.apache.org/licenses/LICENSE-2.0
[Mozilla Public License 2.0]: https://www.mozilla.org/media/MPL/2.0/index.txt
[cookiecutter-napari-plugin]: https://github.com/napari/cookiecutter-napari-plugin

[file an issue]: https://github.com/bgraedel/napari-timestamper/issues

[napari]: https://github.com/napari/napari
[tox]: https://tox.readthedocs.io/en/latest/
[pip]: https://pypi.org/project/pip/
[PyPI]: https://pypi.org/
