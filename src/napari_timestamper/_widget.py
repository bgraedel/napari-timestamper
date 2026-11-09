"""Dock widgets for napari-timestamper."""

from __future__ import annotations

from collections.abc import Iterable
from contextlib import suppress
from pathlib import Path
from typing import ClassVar
from weakref import WeakKeyDictionary

import napari
import numpy as np
from napari.components._viewer_constants import CanvasPosition
from napari.layers import Image, Labels
from napari.layers.utils.stack_utils import stack_to_images
from napari.utils.notifications import show_info
from pint import DimensionalityError
from qtpy.QtCore import Qt, Signal
from qtpy.QtGui import QColor, QIcon, QPixmap
from qtpy.QtWidgets import (
    QApplication,
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QProgressDialog,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)
from superqt import QLabeledSlider

from napari_timestamper._label import LabelManager, LabelStyle
from napari_timestamper._layer_annotator_overlay import LayerAnnotatorManager
from napari_timestamper._timestamp_overlay import (
    TIME_FORMATS,
    TimestampManager,
)
from napari_timestamper.render_as_rgb import (
    RenderCancelled,
    render_as_rgb,
    save_image_stack,
)

SCENE_ONLY_TIP = "Only available when attached to the image."


def _unwrap(viewer):
    """The real viewer behind napari's ``PublicOnlyProxy``.

    The labels deliberately use private napari API (layer overlays); through
    the proxy every such access would warn.
    """
    return getattr(viewer, "__wrapped__", viewer)


def _connect_layer_names(viewer, slot) -> None:
    """Call ``slot`` when layers are added, removed, reordered or renamed."""

    def connect(layer):
        layer.events.name.connect(slot)

    def on_inserted(event):
        connect(event.value)
        slot()

    for layer in viewer.layers:
        connect(layer)
    events = viewer.layers.events
    events.inserted.connect(on_inserted)
    events.removed.connect(slot)
    events.reordered.connect(slot)


# ---------------------------------------------------------------------------
# Reusable controls
# ---------------------------------------------------------------------------


class ColorButton(QPushButton):
    """Button showing a color swatch; opens a color dialog when clicked."""

    colorChanged = Signal(str)

    def __init__(self, color="white", parent: QWidget | None = None):
        super().__init__(parent)
        self.dialog: QColorDialog | None = None
        self._color = _qcolor(color)
        self._refresh()
        self.clicked.connect(self._open_dialog)

    def color(self) -> str:
        return self._color.name()

    def setColor(self, color) -> None:
        color = _qcolor(color)
        if color.isValid() and color != self._color:
            self._color = color
            self._refresh()
            self.colorChanged.emit(self.color())

    def rgba(self, alpha: float = 1.0) -> tuple[float, float, float, float]:
        return (*self._color.getRgbF()[:3], alpha)

    def _refresh(self) -> None:
        pixmap = QPixmap(16, 16)
        pixmap.fill(self._color)
        self.setIcon(QIcon(pixmap))
        self.setText(self._color.name())

    def _open_dialog(self) -> None:
        self.dialog = QColorDialog(self._color, self)
        self.dialog.colorSelected.connect(self.setColor)
        self.dialog.finished.connect(self.dialog.deleteLater)
        self.dialog.open()


def _qcolor(color) -> QColor:
    """QColor from a name, QColor or RGB(A) floats (alpha dropped)."""
    if isinstance(color, (str, QColor)):
        return QColor(color)
    r, g, b = (float(c) for c in list(color)[:3])
    return QColor.fromRgbF(r, g, b)


class AxisComboBox(QComboBox):
    """Lists the viewer's slider axes by label.

    The selected axis is remembered by label, so it survives axes being
    added in front of it, and while no slider is available (e.g. in 3D)
    nothing changes; ``currentIndexChanged`` only fires when the selected
    axis really changes.
    """

    def __init__(
        self,
        viewer: napari.viewer.Viewer,
        none_label: str | None = None,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.viewer = viewer
        self._none_label = none_label
        self._wanted: str | None = None  # label of the selected axis
        self._emitted: tuple = ()  # (label, axis) last announced
        dims = viewer.dims.events
        for event in (dims.axis_labels, dims.ndisplay, dims.order, dims.ndim):
            event.connect(self.refresh)
        self.currentIndexChanged.connect(self._remember)
        self.refresh()

    def _remember(self, *_) -> None:
        self._wanted = self.currentText()
        self._emitted = (self.currentText(), self.currentData())

    def refresh(self, *_) -> None:
        dims = self.viewer.dims
        axes = list(dims.not_displayed)
        self.blockSignals(True)
        self.clear()
        if self._none_label is not None:
            self.addItem(self._none_label, None)
        for axis in axes:
            self.addItem(str(dims.axis_labels[axis]), axis)
        index = self.findText(self._wanted) if self._wanted else -1
        if index < 0:  # default to the first slider axis
            index = int(self._none_label is not None and bool(axes))
        self.setCurrentIndex(index)
        self.blockSignals(False)
        # announce a different axis (or the same one at a new index)
        if axes and (self.currentText(), self.currentData()) != self._emitted:
            self.currentIndexChanged.emit(self.currentIndex())


class LayerChecklist(QListWidget):
    """Checkable list of the viewer's layers.

    Check states belong to the layer objects, so they survive renaming and
    layers being removed and re-added.
    """

    checkedChanged = Signal()

    def __init__(
        self,
        viewer: napari.viewer.Viewer,
        default_checked: bool,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.viewer = viewer
        self._default = default_checked
        self._states: WeakKeyDictionary = WeakKeyDictionary()
        self._rows: list = []
        _connect_layer_names(viewer, self.refresh)
        self.itemChanged.connect(self._on_item_changed)
        self.refresh()

    def refresh(self, *_) -> None:
        self.blockSignals(True)
        self.clear()
        self._rows = list(reversed(self.viewer.layers))  # napari's order
        for layer in self._rows:
            item = QListWidgetItem(layer.name)
            item.setCheckState(
                Qt.CheckState.Checked
                if self.is_checked(layer)
                else Qt.CheckState.Unchecked
            )
            self.addItem(item)
        self.blockSignals(False)

    def _on_item_changed(self, item: QListWidgetItem) -> None:
        layer = self._rows[self.row(item)]
        self._states[layer] = item.checkState() == Qt.CheckState.Checked
        self.checkedChanged.emit()

    def is_checked(self, layer) -> bool:
        return self._states.get(layer, self._default)

    def set_checked(self, layers: Iterable, checked: bool) -> None:
        for layer in layers:
            self._states[layer] = checked
        self.refresh()

    def checked_layers(self) -> list:
        return [ly for ly in self.viewer.layers if self.is_checked(ly)]

    def unchecked_layers(self) -> list:
        return [ly for ly in self.viewer.layers if not self.is_checked(ly)]


def _spinbox(
    low: float,
    high: float,
    value: float,
    suffix: str = "",
    decimals: int | None = None,
) -> QSpinBox | QDoubleSpinBox:
    box = QSpinBox() if decimals is None else QDoubleSpinBox()
    if decimals is not None:
        box.setDecimals(decimals)
    box.setRange(low, high)
    box.setValue(value)
    if suffix:
        box.setSuffix(suffix)
    return box


def _row(*widgets: QWidget) -> QWidget:
    container = QWidget()
    layout = QHBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    for widget in widgets:
        layout.addWidget(widget)
    return container


def _connect(slot, *widgets: QWidget) -> None:
    """Connect the "value changed" signal of each widget to ``slot``."""
    for widget in widgets:
        if isinstance(widget, (QSpinBox, QDoubleSpinBox, QLabeledSlider)):
            widget.valueChanged.connect(slot)
        elif isinstance(widget, QLineEdit):
            widget.textChanged.connect(slot)
        elif isinstance(widget, QComboBox):
            widget.currentIndexChanged.connect(slot)
        elif isinstance(widget, (QCheckBox, QGroupBox)):
            widget.toggled.connect(slot)
        elif isinstance(widget, ColorButton):
            widget.colorChanged.connect(slot)
        elif isinstance(widget, LayerChecklist):
            widget.checkedChanged.connect(slot)


class StyleControls(QWidget):
    """Text style controls shared by the timestamp and layer-name widgets."""

    changed = Signal()

    def __init__(
        self,
        style: LabelStyle,
        color_label: str | QWidget = "Text color",
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.position = QComboBox()
        self.position.addItems([str(p) for p in CanvasPosition])
        self.position.setCurrentText(str(style.position))
        self.font_size = _spinbox(1, 500, int(style.size), " pt")
        self.font_size.setToolTip(
            "Font size at 100% zoom. Attached to the image, text is about "
            "1.33x this many image pixels tall in a 1:1 export."
        )
        self.color = ColorButton(style.color)
        self.bold = QCheckBox("Bold")
        self.bold.setChecked(style.bold)
        self.italic = QCheckBox("Italic")
        self.italic.setChecked(style.italic)
        self.background = QCheckBox("Background")
        self.background.setChecked(style.show_background)
        self.bg_color = ColorButton(style.bg_color)
        self.opacity = QLabeledSlider(Qt.Orientation.Horizontal)
        self.opacity.setRange(0, 100)
        self.opacity.setValue(round(float(style.bg_color[3]) * 100))
        self.outline = QCheckBox("Outline")
        self.outline.setChecked(style.show_outline)
        self.outline_color = ColorButton(style.outline_color)
        self.outline_size = _spinbox(
            0.1, 100, style.outline_thickness, " px", 1
        )

        form = QFormLayout(self)
        form.setContentsMargins(0, 0, 0, 0)
        form.addRow("Position", self.position)
        form.addRow("Size", self.font_size)
        form.addRow(color_label, self.color)
        form.addRow(_row(self.bold, self.italic))
        form.addRow(self.background, self.bg_color)
        form.addRow("Background opacity", self.opacity)
        form.addRow(self.outline, self.outline_color)
        form.addRow("Outline thickness", self.outline_size)

        self._on_scene = style.display_on_scene
        self._scene_only = (self.bold, self.italic, self.outline)
        _connect(
            self._on_change,
            self.position,
            self.font_size,
            self.color,
            self.bold,
            self.italic,
            self.background,
            self.bg_color,
            self.opacity,
            self.outline,
            self.outline_color,
            self.outline_size,
        )
        self._update_enabled()

    def _on_change(self, *_) -> None:
        self._update_enabled()
        self.changed.emit()

    def set_scene_mode(self, on_scene: bool) -> None:
        self._on_scene = on_scene
        self._update_enabled()

    def _update_enabled(self) -> None:
        for widget in self._scene_only:
            widget.setEnabled(self._on_scene)
            widget.setToolTip("" if self._on_scene else SCENE_ONLY_TIP)
        background = self.background.isChecked()
        self.bg_color.setEnabled(background)
        self.opacity.setEnabled(background)
        outline = self._on_scene and self.outline.isChecked()
        self.outline_color.setEnabled(outline)
        self.outline_size.setEnabled(outline)

    def settings(self) -> dict:
        """Values for the ``LabelStyle`` fields (colors as RGBA)."""
        return {
            "position": self.position.currentText(),
            "size": self.font_size.value(),
            "color": self.color.rgba(),
            "bold": self.bold.isChecked(),
            "italic": self.italic.isChecked(),
            "show_background": self.background.isChecked(),
            "bg_color": self.bg_color.rgba(self.opacity.value() / 100),
            "show_outline": self.outline.isChecked(),
            "outline_color": self.outline_color.rgba(),
            "outline_thickness": self.outline_size.value(),
        }


# ---------------------------------------------------------------------------
# Labels
# ---------------------------------------------------------------------------


class _LabelWidget(QWidget):
    """Show toggle, display mode, layer selection and style for a label.

    All widgets of one kind share the viewer's manager, so a re-opened
    widget shows (and keeps) the current settings.
    """

    manager_class: ClassVar[type[LabelManager]]
    show_text: ClassVar[str]
    layers_label: ClassVar[str] = "Layers"

    def __init__(self, viewer: napari.viewer.Viewer, parent=None):
        super().__init__(parent)
        self.viewer = viewer = _unwrap(viewer)
        self.manager = self.manager_class.for_viewer(viewer)
        style = self.manager.style
        self.show_checkbox = QCheckBox(self.show_text)
        self.show_checkbox.setChecked(self.manager.visible)
        self.mode = QComboBox()
        self.mode.addItem("Attached to image (for export)", True)
        self.mode.addItem("Fixed on screen", False)
        self.mode.setCurrentIndex(0 if style.display_on_scene else 1)
        self.mode.setToolTip(
            "Attached to image: drawn inside the image and scaled with it, "
            "so it looks the same in exports.\nFixed on screen: napari's "
            "canvas overlay with a constant screen size."
        )
        self.layer_selector = LayerChecklist(viewer, default_checked=True)
        self.layer_selector.set_checked(self.manager.hidden_layers, False)
        self.style_controls = StyleControls(style, self._color_label())

        top = QFormLayout()
        top.addRow("Mode", self.mode)
        top.addRow(self.layers_label, self.layer_selector)
        self.layout_ = QVBoxLayout(self)
        self.layout_.addWidget(self.show_checkbox)
        self.layout_.addLayout(top)

    def _color_label(self) -> str | QWidget:
        return "Text color"

    def _finish(self, *extra_controls: QWidget) -> None:
        """Connect all controls and push their initial state."""
        self.layout_.addStretch()
        _connect(
            self._apply,
            self.show_checkbox,
            self.mode,
            self.layer_selector,
            *extra_controls,
        )
        self.style_controls.changed.connect(self._apply)
        self._apply()

    def _settings(self) -> dict:
        """Widget-specific model values (besides the style)."""
        return {}

    def _apply(self, *_) -> None:
        on_scene = self.mode.currentData()
        self.style_controls.set_scene_mode(on_scene)
        self.manager.update_settings(
            display_on_scene=on_scene,
            **self.style_controls.settings(),
            **self._settings(),
        )
        self.manager.hidden_layers = self.layer_selector.unchecked_layers()
        self.manager.visible = self.show_checkbox.isChecked()


class TimestampWidget(_LabelWidget):
    """Timestamp with a Fiji-style time bar."""

    manager_class = TimestampManager
    manager: TimestampManager
    show_text = "Show timestamp"
    layers_label = "Show on"

    def __init__(self, viewer: napari.viewer.Viewer, parent=None):
        super().__init__(viewer, parent)
        viewer = self.viewer
        self.layer_selector.setToolTip(
            "Drawn once per view (or grid cell), on its topmost checked layer."
        )
        ov = self.manager.style
        self.time_axis = AxisComboBox(viewer)
        self.start_time = _spinbox(-1e6, 1e6, ov.start_time, " s", 2)
        self.step_time = _spinbox(0, 1e6, ov.step_size, " s", 3)
        self.from_data_button = QPushButton("From data")
        self.from_data_button.setToolTip(
            "Use the time axis scale (and units) of the loaded layers"
        )
        self.time_format = QComboBox()
        self.time_format.addItems(TIME_FORMATS)
        self.time_format.setCurrentText(ov.time_format)
        self.prefix = QLineEdit(ov.prefix)
        self.suffix = QLineEdit(ov.suffix)
        self.preview = QLabel()
        self.x_shift = _spinbox(-10000, 10000, int(ov.x_spacer), " px")
        self.y_shift = _spinbox(-10000, 10000, int(ov.y_spacer), " px")

        self.bar_group = QGroupBox("Time bar (Fiji style)")
        self.bar_group.setCheckable(True)
        self.bar_group.setChecked(ov.show_bar)
        self.bar_color = ColorButton(ov.bar_color)
        self.bar_thickness = _spinbox(0.5, 1000, ov.bar_thickness, " px", 1)
        bar_form = QFormLayout(self.bar_group)
        bar_form.addRow("Color", self.bar_color)
        bar_form.addRow("Thickness", self.bar_thickness)

        time_group = QGroupBox("Time")
        time_form = QFormLayout(time_group)
        time_form.addRow("Time axis", self.time_axis)
        time_form.addRow("Start time", self.start_time)
        time_form.addRow(
            "Frame interval", _row(self.step_time, self.from_data_button)
        )
        time_form.addRow("Format", self.time_format)
        time_form.addRow("Prefix", self.prefix)
        time_form.addRow("Suffix", self.suffix)
        time_form.addRow("Preview", self.preview)

        look_group = QGroupBox("Appearance")
        look_layout = QVBoxLayout(look_group)
        look_layout.addWidget(self.style_controls)
        offsets = QFormLayout()
        offsets.addRow("Offset (x, y)", _row(self.x_shift, self.y_shift))
        look_layout.addLayout(offsets)

        for group in (time_group, look_group, self.bar_group):
            self.layout_.addWidget(group)

        if not self.manager.visible:  # fresh: use the data's calibration
            self.fill_step_from_data()
        self.time_axis.currentIndexChanged.connect(self.fill_step_from_data)
        self.from_data_button.clicked.connect(self.fill_step_from_data)
        viewer.dims.events.current_step.connect(self._update_preview)
        self._finish(
            self.time_axis,
            self.start_time,
            self.step_time,
            self.time_format,
            self.prefix,
            self.suffix,
            self.x_shift,
            self.y_shift,
            self.bar_group,
            self.bar_color,
            self.bar_thickness,
        )

    @property
    def timestamp_overlay(self):
        return self.manager.style

    def fill_step_from_data(self, *_) -> None:
        """Set the frame interval (in seconds) from the time axis scale."""
        axis = self.time_axis.currentData()
        if axis is None:
            return
        dims = self.viewer.dims
        step = dims.range[axis].step
        # uncalibrated axes (e.g. "pixel") are taken to be in seconds
        with suppress(DimensionalityError):
            step = (step * dims.units[axis]).to("s").magnitude
        self.step_time.setValue(step)

    def _settings(self) -> dict:
        time_axis = self.time_axis.currentData()
        return {
            "time_axis": time_axis if time_axis is not None else -1,
            "start_time": self.start_time.value(),
            "step_size": self.step_time.value(),
            "time_format": self.time_format.currentText(),
            "prefix": self.prefix.text(),
            "suffix": self.suffix.text(),
            "x_spacer": self.x_shift.value(),
            "y_spacer": self.y_shift.value(),
            "show_bar": self.bar_group.isChecked(),
            "bar_color": self.bar_color.rgba(),
            "bar_thickness": self.bar_thickness.value(),
        }

    def _apply(self, *_) -> None:
        on_scene = self.mode.currentData()
        for widget in (self.x_shift, self.y_shift):
            widget.setEnabled(on_scene)
            widget.setToolTip("" if on_scene else SCENE_ONLY_TIP)
        super()._apply()
        self._update_preview()

    def _update_preview(self, *_) -> None:
        self.preview.setText(self.manager.text())


class LayerAnnotationsWidget(_LabelWidget):
    """Layer-name labels."""

    manager_class = LayerAnnotatorManager
    manager: LayerAnnotatorManager
    show_text = "Show layer names"

    def __init__(self, viewer: napari.viewer.Viewer, parent=None):
        super().__init__(viewer, parent)
        self.layout_.addWidget(self.style_controls)
        self.color_checkbox.toggled.connect(
            self.style_controls.color.setDisabled
        )
        self.style_controls.color.setDisabled(self.color_checkbox.isChecked())
        self._finish(self.color_checkbox)

    def _color_label(self) -> QWidget:
        self.color_checkbox = QCheckBox("Use layer colormap")
        self.color_checkbox.setChecked(self.manager.style.use_layer_color)
        return self.color_checkbox

    @property
    def layer_annotator_overlay(self):
        """First per-layer overlay (``None`` if there are no layers)."""
        overlays = self.manager.overlays()
        return overlays[0] if overlays else None

    def _settings(self) -> dict:
        return {"use_layer_color": self.color_checkbox.isChecked()}


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------


class RenderRGBWidget(QWidget):
    """Render the viewer (with overlays) to an image, image series or movie."""

    MOVIE_TYPES = ("mp4", "gif")

    def __init__(self, viewer: napari.viewer.Viewer, parent=None):
        super().__init__(parent)
        self.viewer = viewer = _unwrap(viewer)

        self.axis_combobox = AxisComboBox(viewer, none_label="Current view")
        self.first_frame = QSpinBox()
        self.last_frame = QSpinBox()
        self.export_type_combobox = QComboBox()
        self.export_type_combobox.addItems(
            ["mp4", "gif", "tif", "png", "jpeg"]
        )
        self.frame_interval_spinbox = _spinbox(1, 1000, 10, " fps")
        self.scale_spinbox = _spinbox(0.1, 100, 1, "x", 1)
        self.scale_spinbox.setToolTip("Resolution multiplier for the export")
        self.directory_edit = QLineEdit()
        self.directory_edit.setPlaceholderText("Choose an output folder…")
        self.filepath_button = QPushButton("Browse…")
        self.name_lineedit = QLineEdit("output")
        self.render_button = QPushButton("Render and save")

        form = QFormLayout()
        form.addRow("Animate axis", self.axis_combobox)
        form.addRow(
            "Frames", _row(self.first_frame, QLabel("to"), self.last_frame)
        )
        form.addRow("Format", self.export_type_combobox)
        form.addRow("Frame rate", self.frame_interval_spinbox)
        form.addRow("Upscale", self.scale_spinbox)
        form.addRow("Folder", _row(self.directory_edit, self.filepath_button))
        form.addRow("File name", self.name_lineedit)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self.render_button)
        layout.addStretch()

        self.axis_combobox.currentIndexChanged.connect(self._reset_frames)
        viewer.dims.events.range.connect(self._update_frame_limits)
        self.export_type_combobox.currentTextChanged.connect(
            self._update_enabled
        )
        self.filepath_button.clicked.connect(self.on_filepath_button_clicked)
        self.render_button.clicked.connect(self.on_render_button_clicked)
        self._reset_frames()

    @property
    def directory(self) -> Path | None:
        text = self.directory_edit.text().strip()
        return Path(text) if text else None

    @directory.setter
    def directory(self, path: Path | str | None) -> None:
        self.directory_edit.setText(str(path) if path else "")

    def _n_frames(self) -> int:
        axis = self.axis_combobox.currentData()
        return 1 if axis is None else int(self.viewer.dims.nsteps[axis])

    def _update_frame_limits(self, *_) -> None:
        # a range ending at the last frame keeps doing so when the axis grows
        to_end = self.last_frame.value() == self.last_frame.maximum()
        last = self._n_frames() - 1
        for box in (self.first_frame, self.last_frame):
            box.setMaximum(last)
        if to_end:
            self.last_frame.setValue(last)
        self._update_enabled()

    def _reset_frames(self, *_) -> None:
        self._update_frame_limits()
        self.first_frame.setValue(0)
        self.last_frame.setValue(self.last_frame.maximum())

    def _update_enabled(self, *_) -> None:
        animated = self.axis_combobox.currentData() is not None
        self.first_frame.setEnabled(animated)
        self.last_frame.setEnabled(animated)
        self.frame_interval_spinbox.setEnabled(
            animated
            and self.export_type_combobox.currentText() in self.MOVIE_TYPES
        )

    def on_filepath_button_clicked(self) -> None:
        directory = QFileDialog.getExistingDirectory(
            self, "Select output folder", str(self.directory or "")
        )
        if directory:
            self.directory = directory

    def on_render_button_clicked(self) -> None:
        if self.directory is None:
            self.on_filepath_button_clicked()
            if self.directory is None:
                return
        axis = self.axis_combobox.currentData()
        export_type = self.export_type_combobox.currentText()
        if axis is None and export_type in self.MOVIE_TYPES:
            show_info(f"Choose an axis to animate for {export_type} export")
            return
        frames = None
        if axis is not None:
            first, last = self.first_frame.value(), self.last_frame.value()
            frames = range(min(first, last), max(first, last) + 1)

        progress = QProgressDialog(
            "Rendering frames…", "Cancel", 0, len(frames or [0]), self
        )
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(500)

        def callback(done: int, total: int) -> bool:
            progress.setValue(done)
            QApplication.processEvents()
            return not progress.wasCanceled()

        try:
            image = render_as_rgb(
                self.viewer,
                axis,
                upsample_factor=self.scale_spinbox.value(),
                frames=frames,
                callback=callback,
            )
        except RenderCancelled:
            show_info("Export cancelled")
            return
        finally:
            progress.close()
            progress.deleteLater()
        path = save_image_stack(
            image,
            self.directory,
            self.name_lineedit.text() or "output",
            export_type,
            self.frame_interval_spinbox.value(),
        )
        show_info(f"Saved {path}")


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


class LayertoRGBWidget(QWidget):
    """Render selected layers into a new RGB(A) image layer."""

    def __init__(self, viewer: napari.viewer.Viewer, parent=None):
        super().__init__(parent)
        self.viewer = viewer = _unwrap(viewer)
        self.layer_selector = LayerChecklist(viewer, default_checked=False)
        self.name_lineedit = QLineEdit("output")
        self.render_button = QPushButton("Convert to RGB layer")
        form = QFormLayout()
        form.addRow("Layers", self.layer_selector)
        form.addRow("Name", self.name_lineedit)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self.render_button)
        layout.addStretch()
        self.render_button.clicked.connect(self.on_render_button_clicked)

    def on_render_button_clicked(self) -> None:
        layers = self.layer_selector.checked_layers()
        if not layers:
            show_info("Select at least one layer to convert")
            return
        rendered_image = self.render_layers_as_rgb(layers)
        self.viewer.add_image(
            rendered_image, name=self.name_lineedit.text(), rgb=True
        )

    def render_layers_as_rgb(self, layers: Iterable) -> np.ndarray:
        """Render only ``layers`` through every slider position.

        Other layers are removed while rendering (hidden layers would still
        count towards the exported extent).
        """
        keep = {id(layer) for layer in layers}
        all_layers = self.viewer.layers
        others = [
            (i, ly) for i, ly in enumerate(all_layers) if id(ly) not in keep
        ]
        visibility = {id(ly): ly.visible for ly in all_layers}
        for _, layer in reversed(others):
            all_layers.remove(layer)
        for layer in all_layers:
            layer.visible = True
        try:
            axes = list(self.viewer.dims.not_displayed) or None
            return render_as_rgb(self.viewer, axes)
        finally:
            for index, layer in others:
                all_layers.insert(index, layer)
            for layer in all_layers:
                layer.visible = visibility[id(layer)]


class SplitStackWidget(QWidget):
    """Split a layer along one axis into separate layers."""

    def __init__(self, viewer: napari.viewer.Viewer, parent=None):
        super().__init__(parent)
        self.viewer = viewer = _unwrap(viewer)
        self.layer_combobox = QComboBox()
        self.axis_combobox = QComboBox()
        self.remove_original_checkbox = QCheckBox("Remove original layer")
        self.remove_original_checkbox.setChecked(True)
        self.split_button = QPushButton("Split")
        form = QFormLayout()
        form.addRow("Layer", self.layer_combobox)
        form.addRow("Split axis", self.axis_combobox)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self.remove_original_checkbox)
        layout.addWidget(self.split_button)
        layout.addStretch()

        _connect_layer_names(viewer, self._update_layer_combobox)
        self.layer_combobox.currentIndexChanged.connect(
            self._update_axis_combobox
        )
        self.split_button.clicked.connect(self._on_split)
        self._update_layer_combobox()

    def _current_layer(self):
        layer = self.layer_combobox.currentData()
        return layer if layer in self.viewer.layers else None

    def _update_layer_combobox(self, *_) -> None:
        current = self.layer_combobox.currentData()
        self.layer_combobox.blockSignals(True)
        self.layer_combobox.clear()
        for layer in self.viewer.layers:
            if layer.ndim > 2:
                self.layer_combobox.addItem(layer.name, layer)
        index = self.layer_combobox.findData(current)
        self.layer_combobox.setCurrentIndex(max(index, 0))
        self.layer_combobox.blockSignals(False)
        self._update_axis_combobox()

    def _update_axis_combobox(self, *_) -> None:
        self.axis_combobox.clear()
        layer = self._current_layer()
        if layer is None:
            return
        # layer axes map onto the viewer's last layer.ndim axes
        labels = self.viewer.dims.axis_labels[-layer.ndim :]
        for i, size in enumerate(layer.data.shape[: layer.ndim]):
            self.axis_combobox.addItem(f"{labels[i]} (size {size})", i)

    def _on_split(self) -> None:
        layer = self._current_layer()
        axis = self.axis_combobox.currentData()
        if layer is None or axis is None:
            return
        if isinstance(layer, Image):
            # napari's own splitter keeps the other layer properties
            parts = stack_to_images(
                layer,
                axis,
                colormap=[layer.colormap.name],
                contrast_limits=layer.contrast_limits,
                blending=layer.blending,
            )
        elif isinstance(layer, Labels):
            data, meta, _ = layer.as_layer_data_tuple()
            for key in ("scale", "translate"):
                meta[key] = [v for i, v in enumerate(meta[key]) if i != axis]
            for key in ("rotate", "shear", "affine", "axis_labels", "units"):
                meta.pop(key, None)
            parts = [
                Labels(np.take(data, i, axis=axis), **meta)
                for i in range(data.shape[axis])
            ]
        else:
            show_info(f"Cannot split {type(layer).__name__} layers")
            return
        for i, part in enumerate(parts):
            part.name = f"{layer.name}_{i}"
            self.viewer.add_layer(part)
        if self.remove_original_checkbox.isChecked():
            self.viewer.layers.remove(layer)
