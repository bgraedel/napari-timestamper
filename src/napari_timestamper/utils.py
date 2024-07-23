import numpy as np


def _find_grid_offsets(viewer):
    """
    Finds the offsets for the grid.
    """
    layer_translations = []
    extent = viewer._sliced_extent_world_augmented
    n_layers = len(viewer.layers)
    for i, layer in enumerate(viewer.layers):
        i_row, i_column = viewer.grid.position(n_layers - 1 - i, n_layers)
        # viewer._subplot(layer, (i_row, i_column), extent)
        scene_shift = extent[1] - extent[0]
        translate_2d = np.multiply(scene_shift[-2:], (i_row, i_column))
        translate = [0] * layer.ndim
        translate[-2:] = translate_2d
        layer_translations.append(translate)
    return layer_translations
