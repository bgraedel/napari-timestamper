"""
Dock widget for napari-timestamper
"""

from __future__ import annotations

import warnings
from pathlib import Path

import napari
from napari._vispy.utils.visual import overlay_to_visual
from napari.components._viewer_constants import CanvasPosition
from napari.layers import labels
from qtpy import QtCore, QtGui, QtWidgets
from qtpy.QtCore import Slot
from qtpy.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)
from superqt import QLabeledSlider
from vispy.color import ColorArray

from napari_timestamper._layer_annotator_overlay import (
    LayerAnnotatorManager,
)
from napari_timestamper._timestamp_overlay import (
    TimestampOverlay,
    VispyTimestampOverlay,
)
from napari_timestamper.render_as_rgb import render_as_rgb, save_image_stack


class TimestampWidget(QtWidgets.QWidget):
    """
    A widget that provides options for the timestamp overlay in napari viewer.
    """

    overlay_set: bool = False

    def __init__(self, viewer: napari.viewer.Viewer, parent=None):
        super().__init__(parent)
        self.chosen_color = "white"
        self.chosen_bgcolor = "black"
        self.chosen_outline_color = "white"
        self.viewer = viewer
        self._setupUi()
        self._connect_all_changes()
        self._setup_overlay()
        # Reflect current grid state immediately on open
        self._on_grid_mode_change()

    def _setup_overlay(self):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            try:
                self.viewer._overlays["timestamp"]
            except KeyError:
                overlay_to_visual[TimestampOverlay] = VispyTimestampOverlay
                self.viewer._overlays["timestamp"] = TimestampOverlay(
                    visible=True
                )
            self.timestamp_overlay = self.viewer._overlays["timestamp"]
            self._set_timestamp_overlay_options()
            self.overlay_set = True

    def _toggle_overlay(self):
        if not self.overlay_set:
            self._setup_overlay()
            self.toggle_timestamp.setText("Remove Timestamp")
            return

        if self.timestamp_overlay.visible:
            self.timestamp_overlay.visible = False
            self.toggle_timestamp.setText("Add Timestamp")
        else:
            self.timestamp_overlay.visible = True
            self.toggle_timestamp.setText("Remove Timestamp")

    def _on_grid_mode_change(self, event=None):
        """
        Enable / disable scene-specific controls based on grid mode.

        In grid mode the overlay ignores display_on_scene and scale_with_zoom
        (it always uses canvas-space positioning with a fixed scale).
        We grey those controls out so the user can see they're inactive,
        but their Qt values are preserved — re-enabling them when grid mode
        turns off automatically "recalls" the previous settings.
        """
        grid_on = self.viewer.grid.enabled

        for widget in (self.display_on_scene, self.scale_with_zoom):
            widget.setEnabled(not grid_on)

        self.grid_mode_label.setVisible(grid_on)

        if self.overlay_set:
            self._set_timestamp_overlay_options()

    def _setupUi(self):
        self.setObjectName("Timestamp Options")
        self.gridLayout = QtWidgets.QGridLayout()

        self.time_axis_label = QtWidgets.QLabel("Time Axis")
        self.time_axis = QtWidgets.QComboBox()
        self._update_time_axis_combobox()

        self.start_time_label = QtWidgets.QLabel("Start Time")
        self.start_time = QtWidgets.QSpinBox()
        self.start_time.setRange(0, 10000)
        self.start_time.setValue(0)

        self.step_time_label = QtWidgets.QLabel("Step Time")
        self.step_time = QtWidgets.QDoubleSpinBox()
        self.step_time.setRange(0, 10000)
        self.step_time.setValue(1)

        self.prefix_label = QtWidgets.QLabel("Prefix")
        self.prefix = QtWidgets.QLineEdit()
        self.prefix.setText("")

        self.suffix_label = QtWidgets.QLabel("Suffix")
        self.suffix = QtWidgets.QLineEdit()
        self.suffix.setText("")

        self.position_label = QtWidgets.QLabel("Position")
        self.position = QtWidgets.QComboBox()
        self.position.addItems(CanvasPosition)
        self.position.setCurrentIndex(1)

        self.size_label = QtWidgets.QLabel("Size")
        self.ts_size = QtWidgets.QSpinBox()
        self.ts_size.setRange(0, 1000)
        self.ts_size.setValue(12)

        self.shift_label = QtWidgets.QLabel("XY Shift")
        self.shiftlayout = QtWidgets.QHBoxLayout()
        self.x_shift = QtWidgets.QSpinBox()
        self.x_shift.setRange(-1000, 1000)
        self.x_shift.setValue(0)
        self.y_shift = QtWidgets.QSpinBox()
        self.y_shift.setRange(-1000, 1000)
        self.y_shift.setValue(0)
        self.shiftlayout.addWidget(self.x_shift)
        self.shiftlayout.addWidget(self.y_shift)

        self.time_format_label = QtWidgets.QLabel("Time Format")
        self.time_format = QtWidgets.QComboBox()
        self.time_format.addItems(
            TimestampOverlay._get_allowed_format_specifiers()
        )

        self.color_label = QtWidgets.QLabel("Set Timestamp Color")
        self.color = QtWidgets.QPushButton("Choose Color")

        self.bgcolor_checkbox = QtWidgets.QCheckBox("Background Color")
        self.bgcolor_checkbox.setChecked(False)
        self.bgcolor = QtWidgets.QPushButton("Choose Color")
        self.bgcolor.setEnabled(False)

        self.opacity_label = QtWidgets.QLabel("Background Opacity")
        self.opacity_slider = QLabeledSlider(QtCore.Qt.Horizontal)
        self.opacity_slider.setRange(0, 100)
        self.opacity_slider.setValue(100)
        self.opacity_label.setEnabled(False)

        self.outline_checkbox = QtWidgets.QCheckBox("Outline")
        self.outline_checkbox.setChecked(False)

        self.outline_color = QtWidgets.QPushButton("Choose Outline Color")
        self.outline_color.setEnabled(False)

        self.outline_size_label = QtWidgets.QLabel("Outline Size")
        self.outline_size = QtWidgets.QDoubleSpinBox()
        self.outline_size.setRange(0, 100)
        self.outline_size.setValue(0.2)

        self.bold_checkbox = QtWidgets.QCheckBox("Bold")
        self.bold_checkbox.setChecked(False)
        self.italic_checkbox = QtWidgets.QCheckBox("Italic")
        self.italic_checkbox.setChecked(False)

        self.display_on_scene = QtWidgets.QCheckBox("Display on Scene")
        self.display_on_scene.setChecked(True)

        self.scale_with_zoom = QtWidgets.QCheckBox("Scale with Zoom")
        self.scale_with_zoom.setChecked(True)

        # Grid mode info label — hidden when grid is off
        self.grid_mode_label = QtWidgets.QLabel(
            "Grid mode active: 'Display on Scene' and\n"
            "'Scale with Zoom' are ignored."
        )
        self.grid_mode_label.setStyleSheet(
            "color: orange; font-style: italic;"
        )
        self.grid_mode_label.setVisible(False)
        self.grid_mode_label.setWordWrap(True)

        self.toggle_timestamp = QtWidgets.QPushButton("Add Timestamp")

        # Layout
        self.gridLayout.addWidget(self.time_axis_label, 0, 0)
        self.gridLayout.addWidget(self.time_axis, 0, 1)
        self.gridLayout.addWidget(self.start_time_label, 1, 0)
        self.gridLayout.addWidget(self.start_time, 1, 1)
        self.gridLayout.addWidget(self.step_time_label, 2, 0)
        self.gridLayout.addWidget(self.step_time, 2, 1)
        self.gridLayout.addWidget(self.prefix_label, 3, 0)
        self.gridLayout.addWidget(self.prefix, 3, 1)
        self.gridLayout.addWidget(self.suffix_label, 4, 0)
        self.gridLayout.addWidget(self.suffix, 4, 1)
        self.gridLayout.addWidget(self.position_label, 5, 0)
        self.gridLayout.addWidget(self.position, 5, 1)
        self.gridLayout.addWidget(self.size_label, 6, 0)
        self.gridLayout.addWidget(self.ts_size, 6, 1)
        self.gridLayout.addWidget(self.shift_label, 7, 0)
        self.gridLayout.addLayout(self.shiftlayout, 7, 1)
        self.gridLayout.addWidget(self.time_format_label, 8, 0)
        self.gridLayout.addWidget(self.time_format, 8, 1)
        self.gridLayout.addWidget(self.color_label, 9, 0)
        self.gridLayout.addWidget(self.color, 9, 1)
        self.gridLayout.addWidget(self.outline_checkbox, 10, 0)
        self.gridLayout.addWidget(self.outline_color, 10, 1)
        self.gridLayout.addWidget(self.outline_size_label, 11, 0)
        self.gridLayout.addWidget(self.outline_size, 11, 1)
        self.gridLayout.addWidget(self.bgcolor_checkbox, 12, 0)
        self.gridLayout.addWidget(self.bgcolor, 12, 1)
        self.gridLayout.addWidget(self.opacity_label, 13, 0)
        self.gridLayout.addWidget(self.opacity_slider, 13, 1)
        self.gridLayout.addWidget(self.bold_checkbox, 14, 0)
        self.gridLayout.addWidget(self.italic_checkbox, 14, 1)
        self.gridLayout.addWidget(self.scale_with_zoom, 15, 0)
        self.gridLayout.addWidget(self.display_on_scene, 15, 1)
        # Grid mode info label spans both columns
        self.gridLayout.addWidget(self.grid_mode_label, 16, 0, 1, 2)
        self.gridLayout.addWidget(self.toggle_timestamp, 17, 0, 1, 2)
        self.setLayout(self.gridLayout)

        self.spacer = QtWidgets.QSpacerItem(
            20,
            40,
            QtWidgets.QSizePolicy.Minimum,
            QtWidgets.QSizePolicy.Expanding,
        )
        self.gridLayout.addItem(self.spacer, 18, 0, 1, 2)

        self._update_color_button_icon(self.color, self.chosen_color)
        self._update_color_button_icon(self.bgcolor, self.chosen_bgcolor)
        self._update_color_button_icon(
            self.outline_color, self.chosen_outline_color
        )

    def _update_color_button_icon(self, color_button, color_str):
        pixmap = QtGui.QPixmap(20, 20)
        pixmap.fill(QtGui.QColor(color_str))
        color_button.setIcon(QtGui.QIcon(pixmap))

    def _toggle_bgcolor(self):
        if self.bgcolor_checkbox.isChecked():
            self.bgcolor.setEnabled(True)
            self.opacity_label.setEnabled(True)
            self.opacity_slider.setEnabled(True)
            self._set_timestamp_overlay_options()
        else:
            self.bgcolor.setEnabled(False)
            self.opacity_label.setEnabled(False)
            self.opacity_slider.setEnabled(False)
            self._update_color_button_icon(self.bgcolor, "grey")
            self._set_timestamp_overlay_options()

    def _on_outline_color_combobox_change(self):
        if not self.outline_checkbox.isChecked():
            self.outline_color.setEnabled(False)
            self._update_color_button_icon(self.outline_color, "grey")
            self.timestamp_overlay.show_outline = False
        else:
            self.outline_color.setEnabled(True)
            self._update_color_button_icon(
                self.outline_color, self.chosen_outline_color
            )
            self.timestamp_overlay.show_outline = True
            self.timestamp_overlay.outline_color = ColorArray(
                self.chosen_outline_color
            )

    def _open_color_dialog(self):
        self.color_dialog = QtWidgets.QColorDialog(parent=self)
        self.color_dialog.open(self._set_colour)

    def _open_background_color_dialog(self):
        self.bg_color_dialog = QtWidgets.QColorDialog(parent=self)
        self.bg_color_dialog.open(self._set_background_colour)

    def _open_outline_color_dialog(self):
        self.color_dialog = QtWidgets.QColorDialog(parent=self)
        self.color_dialog.open(self._set_outline_colour)

    def _set_colour(self):
        color = self.color_dialog.selectedColor()
        if color.isValid():
            self.chosen_color = color.name()
            self._update_color_button_icon(self.color, self.chosen_color)
            self._set_timestamp_overlay_options()

    def _set_background_colour(self):
        color = self.bg_color_dialog.selectedColor()
        if color.isValid():
            self.chosen_bgcolor = color.name()
            self._update_color_button_icon(self.bgcolor, self.chosen_color)
            self._set_timestamp_overlay_options()

    def _set_outline_colour(self):
        color = self.color_dialog.selectedColor()
        if color.isValid():
            self.chosen_outline_color = color.name()
            self._update_color_button_icon(
                self.outline_color, self.chosen_outline_color
            )
            self._set_timestamp_overlay_options()

    def _set_timestamp_overlay_options(self):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            timestamp_overlay = self.viewer._overlays["timestamp"]
        timestamp_overlay.color = self.chosen_color
        timestamp_overlay.bold = self.bold_checkbox.isChecked()
        timestamp_overlay.italic = self.italic_checkbox.isChecked()
        timestamp_overlay.size = self.ts_size.value()
        timestamp_overlay.position = self.position.currentText()
        timestamp_overlay.prefix = self.prefix.text()
        timestamp_overlay.custom_suffix = (
            self.suffix.text() if self.suffix else None
        )
        timestamp_overlay.start_time = self.start_time.value()
        timestamp_overlay.step_size = self.step_time.value()
        timestamp_overlay.time_format = self.time_format.currentText()
        timestamp_overlay.x_spacer = self.x_shift.value()
        timestamp_overlay.y_spacer = self.y_shift.value()
        time_axis = self.time_axis.currentData()
        if time_axis is not None:
            timestamp_overlay.time_axis = time_axis
        timestamp_overlay.display_on_scene = self.display_on_scene.isChecked()
        timestamp_overlay.scale_with_zoom = self.scale_with_zoom.isChecked()
        timestamp_overlay.bg_color = ColorArray(
            self.chosen_bgcolor, alpha=self.opacity_slider.value() / 100
        )
        timestamp_overlay.show_background = self.bgcolor_checkbox.isChecked()
        timestamp_overlay.show_outline = self.outline_checkbox.isChecked()
        timestamp_overlay.outline_color = ColorArray(self.chosen_outline_color)
        timestamp_overlay.outline_thickness = self.outline_size.value()

    def _update_time_axis_combobox(self, event=None):
        self.time_axis.clear()
        for i, axis in enumerate(self.viewer.dims.axis_labels[:-2]):
            if axis is not None:
                self.time_axis.addItem(axis, i)
        if self.time_axis.count() > 0:
            self.time_axis.setCurrentIndex(0)

    def _connect_all_changes(self):
        for w in (
            self.start_time,
            self.step_time,
            self.ts_size,
            self.x_shift,
            self.y_shift,
        ):
            w.valueChanged.connect(self._set_timestamp_overlay_options)
        for w in (self.prefix, self.suffix):
            w.textChanged.connect(self._set_timestamp_overlay_options)
        for w in (self.position, self.time_format, self.time_axis):
            w.currentTextChanged.connect(self._set_timestamp_overlay_options)

        self.viewer.layers.events.inserted.connect(
            self._update_time_axis_combobox
        )
        self.viewer.layers.events.removed.connect(
            self._update_time_axis_combobox
        )
        self.toggle_timestamp.clicked.connect(self._toggle_overlay)

        self.color.clicked.connect(self._open_color_dialog)
        self.color.clicked.connect(self._set_timestamp_overlay_options)
        self.display_on_scene.stateChanged.connect(
            self._set_timestamp_overlay_options
        )
        self.scale_with_zoom.stateChanged.connect(
            self._set_timestamp_overlay_options
        )
        self.bold_checkbox.stateChanged.connect(
            self._set_timestamp_overlay_options
        )
        self.italic_checkbox.stateChanged.connect(
            self._set_timestamp_overlay_options
        )
        self.bgcolor_checkbox.stateChanged.connect(self._toggle_bgcolor)
        self.bgcolor.clicked.connect(self._open_background_color_dialog)
        self.opacity_slider.valueChanged.connect(
            self._set_timestamp_overlay_options
        )
        self.outline_checkbox.stateChanged.connect(
            self._on_outline_color_combobox_change
        )
        self.outline_color.clicked.connect(self._open_outline_color_dialog)
        self.outline_size.valueChanged.connect(
            self._set_timestamp_overlay_options
        )

        # Grid mode: update widget state whenever grid changes
        self.viewer.grid.events.enabled.connect(self._on_grid_mode_change)
        self.viewer.grid.events.shape.connect(self._on_grid_mode_change)
        self.viewer.grid.events.stride.connect(self._on_grid_mode_change)


class LayerAnnotationsWidget(QtWidgets.QWidget):
    """
    A widget that provides options for the layer annotator overlay in napari viewer.
    """

    overlay_set: bool = False

    def __init__(self, viewer: napari.viewer.Viewer, parent=None):
        super().__init__(parent)
        self.viewer = viewer
        self.chosen_color = "white"
        self.chosen_bgcolor = "black"
        self.chosen_outline_color = "white"
        self._annotator_manager: LayerAnnotatorManager | None = None
        self._setupUi()
        self._connect_all_changes()
        self._setup_overlay()
        self._set_layer_annotator_overlay_options()
        self._on_color_combobox_change()
        self._on_background_color_combobox_change()

    # ------------------------------------------------------------------
    # Setup
    # ------------------------------------------------------------------

    def _setup_overlay(self):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            if self._annotator_manager is None:
                self._annotator_manager = LayerAnnotatorManager(
                    self.viewer, visible=True
                )
            self._set_layer_annotator_overlay_options()
            self.overlay_set = True

    @property
    def layer_annotator_overlay(self):
        """Return the first managed overlay for inspection / testing.

        Returns None if no layers exist yet.
        """
        if self._annotator_manager is None:
            return None
        return self._annotator_manager.get_any_overlay()

    # ------------------------------------------------------------------
    # UI construction  (unchanged)
    # ------------------------------------------------------------------

    def _setupUi(self):
        self.setObjectName("Layer Annotator Options")
        self.gridLayout = QtWidgets.QGridLayout(self)

        self.size_label = QtWidgets.QLabel("Size")
        self.size_slider = QLabeledSlider(QtCore.Qt.Horizontal)
        self.size_slider.setRange(1, 100)
        self.size_slider.setValue(12)

        self.position_label = QtWidgets.QLabel("Position")
        self.position_combobox = QtWidgets.QComboBox()
        self.position_combobox.addItems(CanvasPosition)

        self.toggle_visibility_button = QtWidgets.QPushButton(
            "Toggle Visibility"
        )
        self.toggle_visibility_button.setCheckable(True)
        self.toggle_visibility_button.setChecked(True)

        self.layer_selector_label = QtWidgets.QLabel("Annotate Layers")
        self.layer_selector = QListWidget()
        self._update_layer_selector()

        self.gridLayout.addWidget(self.layer_selector_label, 0, 0)
        self.gridLayout.addWidget(self.layer_selector, 0, 1)
        self.gridLayout.addWidget(self.size_label, 1, 0)
        self.gridLayout.addWidget(self.size_slider, 1, 1)
        self.gridLayout.addWidget(self.position_label, 2, 0)
        self.gridLayout.addWidget(self.position_combobox, 2, 1)
        self.gridLayout.addWidget(self.toggle_visibility_button, 11, 0, 1, 2)

        self.color_checkbox = QtWidgets.QCheckBox(
            "Use Colormap for Image Layers"
        )
        self.color_checkbox.setChecked(True)
        self.gridLayout.addWidget(self.color_checkbox, 5, 0)

        self.color = QtWidgets.QPushButton("Choose Color")
        self._update_color_button_icon(self.color, self.chosen_color)
        self.gridLayout.addWidget(self.color, 5, 1)

        self.bold_checkbox = QtWidgets.QCheckBox("Bold")
        self.bold_checkbox.setChecked(False)
        self.gridLayout.addWidget(self.bold_checkbox, 6, 0)

        self.italic_checkbox = QtWidgets.QCheckBox("Italic")
        self.italic_checkbox.setChecked(False)
        self.gridLayout.addWidget(self.italic_checkbox, 6, 1)

        self.bgcolor_checkbox = QtWidgets.QCheckBox("Show Background Color")
        self.bgcolor_checkbox.setChecked(False)
        self.gridLayout.addWidget(self.bgcolor_checkbox, 7, 0)

        self.bgcolor = QtWidgets.QPushButton("Choose Color")
        self._update_color_button_icon(self.bgcolor, self.chosen_bgcolor)
        self.gridLayout.addWidget(self.bgcolor, 7, 1)

        self.opacity_label = QtWidgets.QLabel("Background Opacity")
        self.opacity_slider = QLabeledSlider(QtCore.Qt.Horizontal)
        self.opacity_slider.setRange(0, 100)
        self.opacity_slider.setValue(100)
        self.gridLayout.addWidget(self.opacity_label, 8, 0)
        self.gridLayout.addWidget(self.opacity_slider, 8, 1)

        self.outline_checkbox = QtWidgets.QCheckBox("Show Outline")
        self.outline_checkbox.setChecked(False)
        self.outline_color = QtWidgets.QPushButton("Choose Outline Color")
        self.outline_color.setEnabled(False)
        self._update_color_button_icon(
            self.outline_color, self.chosen_outline_color
        )
        self.gridLayout.addWidget(self.outline_checkbox, 9, 0)
        self.gridLayout.addWidget(self.outline_color, 9, 1)

        self.outline_size_label = QtWidgets.QLabel("Outline Size")
        self.outline_size = QtWidgets.QDoubleSpinBox()
        self.outline_size.setRange(0, 100)
        self.outline_size.setValue(0.2)
        self.gridLayout.addWidget(self.outline_size_label, 10, 0)
        self.gridLayout.addWidget(self.outline_size, 10, 1)

        self.spacer = QtWidgets.QSpacerItem(
            20,
            40,
            QtWidgets.QSizePolicy.Minimum,
            QtWidgets.QSizePolicy.Expanding,
        )
        self.gridLayout.addItem(self.spacer, 12, 0, 1, 2)
        self.setLayout(self.gridLayout)

        self.size_slider.valueChanged.connect(self._on_size_slider_change)
        self.toggle_visibility_button.clicked.connect(self._toggle_visibility)
        self.color_checkbox.stateChanged.connect(
            self._on_color_combobox_change
        )
        self.bgcolor_checkbox.stateChanged.connect(
            self._on_background_color_combobox_change
        )
        self.viewer.layers.events.inserted.connect(self._update_layer_selector)
        self.viewer.layers.events.removed.connect(self._update_layer_selector)
        self.layer_selector.itemChanged.connect(
            self._on_layer_selection_changed
        )

    # ------------------------------------------------------------------
    # Layer selector
    # ------------------------------------------------------------------

    def _update_layer_selector(self, event=None):
        self.layer_selector.blockSignals(True)
        selected = self._get_selected_layer_names()
        self.layer_selector.clear()
        for layer in self.viewer.layers:
            item = QListWidgetItem(layer.name)
            if layer.name in selected or not selected:
                item.setCheckState(QtCore.Qt.Checked)
            else:
                item.setCheckState(QtCore.Qt.Unchecked)
            self.layer_selector.addItem(item)
        self.layer_selector.blockSignals(False)
        self._on_layer_selection_changed()

    def _get_selected_layer_names(self) -> set[str]:
        return {
            self.layer_selector.item(i).text()
            for i in range(self.layer_selector.count())
            if self.layer_selector.item(i).checkState() == QtCore.Qt.Checked
        }

    def _on_layer_selection_changed(self, item=None):
        """Show the overlay only for checked layers."""
        if not self.overlay_set or self._annotator_manager is None:
            return
        selected = self._get_selected_layer_names()
        for layer in self.viewer.layers:
            # visible = selected if anything is ticked, otherwise show all
            should_show = (layer.name in selected) if selected else True
            self._annotator_manager.set_layer_visible(layer.name, should_show)

    # ------------------------------------------------------------------
    # Color helpers
    # ------------------------------------------------------------------

    def _update_color_button_icon(self, color_button, color_str):
        pixmap = QtGui.QPixmap(20, 20)
        pixmap.fill(QtGui.QColor(color_str))
        color_button.setIcon(QtGui.QIcon(pixmap))

    def _on_color_combobox_change(self):
        use_layer_color = self.color_checkbox.isChecked()
        self._update_color_button_icon(self.color, self.chosen_color)
        if self.overlay_set:
            self._annotator_manager.update_settings(
                use_layer_color=use_layer_color
            )
        self._set_layer_annotator_overlay_options()

    def _on_background_color_combobox_change(self):
        if not self.bgcolor_checkbox.isChecked():
            self.bgcolor.setEnabled(False)
            self._update_color_button_icon(self.bgcolor, "grey")
            self.opacity_label.setEnabled(False)
            self.opacity_slider.setEnabled(False)
            if self.overlay_set:
                self._annotator_manager.update_settings(show_background=False)
        else:
            self.bgcolor.setEnabled(True)
            self._update_color_button_icon(self.bgcolor, self.chosen_bgcolor)
            self.opacity_label.setEnabled(True)
            self.opacity_slider.setEnabled(True)
            if self.overlay_set:
                self._annotator_manager.update_settings(
                    show_background=True,
                    bg_color=ColorArray(
                        self.chosen_bgcolor,
                        alpha=self.opacity_slider.value() / 100,
                    ),
                )

    def _on_outline_color_combobox_change(self):
        if not self.outline_checkbox.isChecked():
            self.outline_color.setEnabled(False)
            self._update_color_button_icon(self.outline_color, "grey")
            if self.overlay_set:
                self._annotator_manager.update_settings(show_outline=False)
        else:
            self.outline_color.setEnabled(True)
            self._update_color_button_icon(
                self.outline_color, self.chosen_outline_color
            )
            if self.overlay_set:
                self._annotator_manager.update_settings(
                    show_outline=True,
                    outline_color=ColorArray(self.chosen_outline_color),
                )

    # ------------------------------------------------------------------
    # Color dialogs
    # ------------------------------------------------------------------

    def _open_color_dialog(self):
        self.color_dialog = QtWidgets.QColorDialog(parent=self)
        self.color_dialog.open(self._set_colour)

    def _open_background_color_dialog(self):
        self.color_dialog = QtWidgets.QColorDialog(parent=self)
        self.color_dialog.open(self._set_background_colour)

    def _open_outline_color_dialog(self):
        self.color_dialog = QtWidgets.QColorDialog(parent=self)
        self.color_dialog.open(self._set_outline_colour)

    def _set_colour(self):
        color = self.color_dialog.selectedColor()
        if color.isValid():
            self.chosen_color = color.name()
            self._update_color_button_icon(self.color, self.chosen_color)
            self._set_layer_annotator_overlay_options()

    def _set_background_colour(self):
        color = self.color_dialog.selectedColor()
        if color.isValid():
            self.chosen_bgcolor = color.name()
            self._update_color_button_icon(self.bgcolor, self.chosen_bgcolor)
            self._set_layer_annotator_overlay_options()
            self._on_background_color_combobox_change()

    def _set_outline_colour(self):
        color = self.color_dialog.selectedColor()
        if color.isValid():
            self.chosen_outline_color = color.name()
            self._update_color_button_icon(
                self.outline_color, self.chosen_outline_color
            )
            self._set_layer_annotator_overlay_options()

    # ------------------------------------------------------------------
    # Overlay state
    # ------------------------------------------------------------------

    def _set_opacity(self):
        if self.overlay_set:
            self._annotator_manager.update_settings(
                bg_color=ColorArray(
                    self.chosen_bgcolor,
                    alpha=self.opacity_slider.value() / 100,
                )
            )

    def _toggle_visibility(self):
        if self._annotator_manager is None:
            return
        # Derive the new state from the button's checked state.
        visible = self.toggle_visibility_button.isChecked()
        self._annotator_manager.set_visible(visible)
        self.toggle_visibility_button.setText(
            "Hide Overlay" if visible else "Show Overlay"
        )

    def _on_size_slider_change(self):
        if self.overlay_set:
            self._annotator_manager.update_settings(
                size=self.size_slider.value()
            )

    def _set_layer_annotator_overlay_options(self):
        """Push all current widget values to every managed overlay at once."""
        if not self.overlay_set or self._annotator_manager is None:
            return
        self._annotator_manager.update_settings(
            position=self.position_combobox.currentText(),
            color=self.chosen_color,
            bold=self.bold_checkbox.isChecked(),
            italic=self.italic_checkbox.isChecked(),
            show_background=self.bgcolor_checkbox.isChecked(),
            bg_color=ColorArray(
                self.chosen_bgcolor,
                alpha=self.opacity_slider.value() / 100,
            ),
            show_outline=self.outline_checkbox.isChecked(),
            outline_color=ColorArray(self.chosen_outline_color),
            outline_thickness=self.outline_size.value(),
            size=self.size_slider.value(),
            use_layer_color=self.color_checkbox.isChecked(),
        )

    # ------------------------------------------------------------------
    # Signal connections
    # ------------------------------------------------------------------

    def _connect_all_changes(self):
        self.position_combobox.currentTextChanged.connect(
            self._set_layer_annotator_overlay_options
        )
        self.color.clicked.connect(self._open_color_dialog)
        self.color.clicked.connect(self._set_layer_annotator_overlay_options)
        self.bgcolor.clicked.connect(self._open_background_color_dialog)
        self.bgcolor.clicked.connect(self._set_layer_annotator_overlay_options)
        self.bold_checkbox.stateChanged.connect(
            self._set_layer_annotator_overlay_options
        )
        self.italic_checkbox.stateChanged.connect(
            self._set_layer_annotator_overlay_options
        )
        self.opacity_slider.valueChanged.connect(self._set_opacity)
        self.outline_checkbox.stateChanged.connect(
            self._on_outline_color_combobox_change
        )
        self.outline_color.clicked.connect(self._open_outline_color_dialog)
        self.outline_color.clicked.connect(
            self._set_layer_annotator_overlay_options
        )
        self.outline_size.valueChanged.connect(
            self._set_layer_annotator_overlay_options
        )

    # ------------------------------------------------------------------
    # Teardown
    # ------------------------------------------------------------------

    def closeEvent(self, event):
        if self._annotator_manager is not None:
            self._annotator_manager.close()
        super().closeEvent(event)


# =============================================================================
# Remaining widgets — unchanged
# =============================================================================


class RenderRGBWidget(QWidget):
    def __init__(self, viewer: napari.viewer.Viewer, parent=None):
        super().__init__(parent)
        self.viewer = viewer
        self.layout = QVBoxLayout(self)
        self.filepath_label = QLabel("Output Directory:", self)
        self.layout.addWidget(self.filepath_label)
        self.filepath_button = QPushButton("Select Directory", self)
        self.layout.addWidget(self.filepath_button)
        self.export_type_label = QLabel("Export Type:", self)
        self.layout.addWidget(self.export_type_label)
        self.export_type_combobox = QComboBox(self)
        self.export_type_combobox.addItems(
            ["mp4", "tif", "png", "jpeg", "gif"]
        )
        self.layout.addWidget(self.export_type_combobox)
        self.axis_label = QLabel("Viewer Axis:", self)
        self.layout.addWidget(self.axis_label)
        self.axis_combobox = QComboBox(self)
        self.axis_combobox.addItem("None", None)
        self.layout.addWidget(self.axis_combobox)
        self.name_label = QLabel("Name:", self)
        self.layout.addWidget(self.name_label)
        self.name_lineedit = QLineEdit(self)
        self.name_lineedit.setText("output")
        self.layout.addWidget(self.name_lineedit)
        self.scale_label = QLabel("Scale Factor:", self)
        self.layout.addWidget(self.scale_label)
        self.scale_spinbox = QDoubleSpinBox(self)
        self.scale_spinbox.setRange(0, 100)
        self.scale_spinbox.setValue(1)
        self.layout.addWidget(self.scale_spinbox)
        self.frame_interval = QLabel("FPS:", self)
        self.layout.addWidget(self.frame_interval)
        self.frame_interval_spinbox = QSpinBox(self)
        self.frame_interval_spinbox.setRange(1, 1000)
        self.frame_interval_spinbox.setValue(10)
        self.layout.addWidget(self.frame_interval_spinbox)
        self.render_button = QPushButton("Render and Save", self)
        self.layout.addWidget(self.render_button)
        self.spacer = QtWidgets.QSpacerItem(
            20,
            40,
            QtWidgets.QSizePolicy.Minimum,
            QtWidgets.QSizePolicy.Expanding,
        )
        self.layout.addItem(self.spacer)
        self.directory = Path()
        self.update_axis_combobox()
        self.connect_slots()

    def connect_slots(self):
        self.viewer.layers.events.inserted.connect(self.update_axis_combobox)
        self.viewer.layers.events.removed.connect(self.update_axis_combobox)
        self.filepath_button.clicked.connect(self.on_filepath_button_clicked)
        self.render_button.clicked.connect(self.on_render_button_clicked)

    def update_axis_combobox(self):
        self.axis_combobox.clear()
        self.axis_combobox.addItem("None", None)
        choices = []
        for i, axis in enumerate(self.viewer.dims.axis_labels[:-2]):
            if axis is not None:
                choices.append(i)
                self.axis_combobox.addItem(axis, i)
        if len(choices) > 0:
            self.axis_combobox.setCurrentIndex(1)

    @Slot()
    def on_filepath_button_clicked(self):
        self.directory = Path(
            QFileDialog.getExistingDirectory(self, "Select Directory")
        )
        self.filepath_label.setText(f"Output Directory: {self.directory}")

    @Slot()
    def on_render_button_clicked(self):
        rendered_image = render_as_rgb(
            self.viewer,
            self.axis_combobox.currentData(),
            upsample_factor=self.scale_spinbox.value(),
        )
        save_image_stack(
            rendered_image,
            self.directory,
            self.name_lineedit.text(),
            self.export_type_combobox.currentText(),
            self.frame_interval_spinbox.value(),
        )


class LayertoRGBWidget(QWidget):
    def __init__(self, viewer: napari.viewer.Viewer, parent=None):
        super().__init__(parent)
        self.viewer = viewer
        self.layout = QVBoxLayout(self)
        self.layer_selector_label = QLabel("Select Layer(s) to convert", self)
        self.layout.addWidget(self.layer_selector_label)
        self.layer_selector = QListWidget(self)
        self.layout.addWidget(self.layer_selector)
        self.name_label = QLabel("Name:", self)
        self.layout.addWidget(self.name_label)
        self.name_lineedit = QLineEdit(self)
        self.name_lineedit.setText("output")
        self.layout.addWidget(self.name_lineedit)
        self.render_button = QPushButton("Convert to RGB", self)
        self.layout.addWidget(self.render_button)
        self.spacer = QtWidgets.QSpacerItem(
            20,
            40,
            QtWidgets.QSizePolicy.Minimum,
            QtWidgets.QSizePolicy.Expanding,
        )
        self.layout.addItem(self.spacer)
        self.connect_slots()
        self._update_layer_selector()

    def _update_layer_selector(self):
        self.layer_selector.clear()
        for layer in self.viewer.layers:
            item = QListWidgetItem(layer.name)
            item.setCheckState(QtCore.Qt.Unchecked)
            self.layer_selector.addItem(item)

    def _get_selected_layers(self):
        return [
            self.viewer.layers[i]
            for i in range(self.layer_selector.count())
            if self.layer_selector.item(i).checkState() == QtCore.Qt.Checked
        ]

    def on_render_button_clicked(self):
        layers = self._get_selected_layers()
        if not layers:
            return
        rendered_image = self.render_layers_as_rgb(layers)
        self.viewer.add_image(
            rendered_image, name=self.name_lineedit.text(), rgb=True
        )

    def connect_slots(self):
        self.viewer.layers.events.inserted.connect(self._update_layer_selector)
        self.viewer.layers.events.removed.connect(self._update_layer_selector)
        self.render_button.clicked.connect(self.on_render_button_clicked)

    def render_layers_as_rgb(self, layers):
        temporary_removed_layers = {}
        for layer_idx, layer in enumerate(self.viewer.layers):
            if layer in layers:
                layer.visible = True
            else:
                temporary_removed_layers[layer_idx] = self.viewer.layers.pop(
                    layer_idx
                )
        ax = [idx for idx, ax in enumerate(self.viewer.dims.range[:-2])]
        if not ax:
            ax = None
        try:
            rendered_image = render_as_rgb(self.viewer, ax, 1)
        finally:
            for layer_idx, layer in temporary_removed_layers.items():
                self.viewer.layers.insert(layer_idx, layer)
        return rendered_image


class SplitStackWidget(QWidget):
    def __init__(self, viewer: napari.viewer.Viewer, parent=None):
        super().__init__(parent)
        self.viewer = viewer
        self.layout = QVBoxLayout(self)
        self.layer_label = QLabel("Layer:", self)
        self.layout.addWidget(self.layer_label)
        self.layer_combobox = QComboBox(self)
        self.layout.addWidget(self.layer_combobox)
        self.axis_label = QLabel("Split Axis:", self)
        self.layout.addWidget(self.axis_label)
        self.axis_combobox = QComboBox(self)
        self.layout.addWidget(self.axis_combobox)
        self.remove_original_checkbox = QtWidgets.QCheckBox(
            "Remove original layer"
        )
        self.remove_original_checkbox.setChecked(True)
        self.layout.addWidget(self.remove_original_checkbox)
        self.split_button = QPushButton("Split", self)
        self.layout.addWidget(self.split_button)
        self.spacer = QtWidgets.QSpacerItem(
            20,
            40,
            QtWidgets.QSizePolicy.Minimum,
            QtWidgets.QSizePolicy.Expanding,
        )
        self.layout.addItem(self.spacer)
        self._update_layer_combobox()
        self._connect_slots()

    def _connect_slots(self):
        self.viewer.layers.events.inserted.connect(self._update_layer_combobox)
        self.viewer.layers.events.removed.connect(self._update_layer_combobox)
        self.layer_combobox.currentIndexChanged.connect(
            self._update_axis_combobox
        )
        self.split_button.clicked.connect(self._on_split)

    def _update_layer_combobox(self, event=None):
        self.layer_combobox.clear()
        for layer in self.viewer.layers:
            self.layer_combobox.addItem(layer.name)
        self._update_axis_combobox()

    def _update_axis_combobox(self, event=None):
        self.axis_combobox.clear()
        idx = self.layer_combobox.currentIndex()
        if idx < 0 or idx >= len(self.viewer.layers):
            return
        layer = self.viewer.layers[idx]
        for i in range(layer.data.ndim):
            axis_labels = self.viewer.dims.axis_labels
            axis_name = axis_labels[i] if i < len(axis_labels) else str(i)
            self.axis_combobox.addItem(
                f"{axis_name} (size {layer.data.shape[i]})", i
            )

    def _on_split(self):
        idx = self.layer_combobox.currentIndex()
        if idx < 0 or idx >= len(self.viewer.layers):
            return
        layer = self.viewer.layers[idx]
        axis = self.axis_combobox.currentData()
        if axis is None:
            return
        data = layer.data
        base_name = layer.name
        is_labels = isinstance(layer, labels.Labels)
        scale = [s for i, s in enumerate(layer.scale) if i != axis]
        translate = [t for i, t in enumerate(layer.translate) if i != axis]
        kwargs = {"scale": scale, "translate": translate}
        if not is_labels:
            kwargs["contrast_limits"] = layer.contrast_limits
            kwargs["colormap"] = layer.colormap.name
            kwargs["blending"] = layer.blending
        add_fn = self.viewer.add_labels if is_labels else self.viewer.add_image
        for i in range(data.shape[axis]):
            slicing = tuple(
                slice(None) if a != axis else i for a in range(data.ndim)
            )
            add_fn(data[slicing], name=f"{base_name}_{i}", **kwargs)
        if self.remove_original_checkbox.isChecked():
            self.viewer.layers.remove(layer)


if __name__ == "__main__":
    import numpy as np

    viewer = napari.Viewer()
    widget = LayerAnnotationsWidget(viewer)
    img1 = np.random.randint(0, 255, (10, 100))
    img2 = np.random.randint(0, 255, (10, 100))
    viewer.add_image(img1, scale=(1, 1))
    viewer.add_image(img2, scale=(1, 1))
    viewer.add_image(img1, scale=(1, 1))
    viewer.window.add_dock_widget(widget, area="right")
    napari.run()
