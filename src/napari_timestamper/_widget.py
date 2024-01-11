"""
Dock widget for napari-timestamper
"""
from __future__ import annotations

import warnings

import napari
from napari._vispy.utils.visual import overlay_to_visual
from napari.components._viewer_constants import CanvasPosition
from qtpy import QtCore, QtGui, QtWidgets
from superqt import QLabeledSlider

from napari_timestamper._layer_annotator_overlay import (
    LayerAnnotatorOverlay,
    ScenePosition,
    VispyLayerAnnotatorOverlay,
)
from napari_timestamper._timestamp_overlay import (
    TimestampOverlay,
    VispyTimestampOverlay,
)


class TimestampWidget(QtWidgets.QWidget):
    """
    A widget that provides options for the timestamp overlay in napari viewer.

    Parameters
    ----------
    viewer : napari.Viewer
        The napari viewer instance.
    parent : QWidget, optional
        The parent widget, by default None.
    """

    overlay_set: bool = False

    def __init__(self, viewer: napari.viewer.Viewer, parent=None):
        """
        Initialize the timestamp_options widget.

        Parameters
        ----------
        viewer : napari.Viewer
            The napari viewer instance.
        parent : QWidget, optional
            The parent widget, by default None.
        """
        super().__init__(parent)
        self.chosen_color = "white"
        self.viewer = viewer
        self._setupUi()
        self._connect_all_changes()
        self._setup_overlay()

    def _setup_overlay(self):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            try:
                self.viewer._overlays["timestamp"]
            except KeyError:
                self.viewer._overlays["timestamp"] = TimestampOverlay(
                    visible=True
                )
                overlay_to_visual[TimestampOverlay] = VispyTimestampOverlay
                self.viewer.window._qt_viewer._add_overlay(
                    self.viewer._overlays["timestamp"]
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

    def _setupUi(self):
        self.setObjectName("Timestamp Options")
        self.gridLayout = QtWidgets.QGridLayout()

        self.time_axis_label = QtWidgets.QLabel("Time Axis")
        self.time_axis = QtWidgets.QSpinBox()
        self.time_axis.setRange(-10, 10)

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
        self.suffix.setText("HH:MM:SS")

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

        self.color = QtWidgets.QPushButton("Choose Color")
        self.color_display = QtWidgets.QFrame()

        self.toggle_timestamp = QtWidgets.QPushButton("Add Timestamp")

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
        self.gridLayout.addWidget(self.color, 9, 1)
        self.gridLayout.addWidget(self.color_display, 9, 0)
        self.gridLayout.addWidget(self.toggle_timestamp, 10, 0, 1, 2)
        self.setLayout(self.gridLayout)

        self.spacer = QtWidgets.QSpacerItem(
            20,
            40,
            QtWidgets.QSizePolicy.Minimum,
            QtWidgets.QSizePolicy.Expanding,
        )
        self.gridLayout.addItem(self.spacer, 11, 0, 1, 2)

        self.color_display.setStyleSheet(
            "QWidget {background-color: %s}" % self.chosen_color
        )

    def _open_color_dialog(self):
        self.color_dialog = QtWidgets.QColorDialog(parent=self)
        self.color_dialog.open(self._set_colour)

    def _set_colour(self):
        color = self.color_dialog.selectedColor()
        if color.isValid():
            self.color_display.setStyleSheet(
                "QWidget {background-color: %s}" % color.name()
            )
            self.chosen_color = color.name()
            self._set_timestamp_overlay_options()

    def _set_timestamp_overlay_options(self):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            timestamp_overlay = self.viewer._overlays["timestamp"]
        timestamp_overlay.color = self.chosen_color
        timestamp_overlay.size = self.ts_size.value()
        timestamp_overlay.position = self.position.currentText()
        timestamp_overlay.prefix = self.prefix.text()
        timestamp_overlay.suffix = self.suffix.text()
        timestamp_overlay.start_time = self.start_time.value()
        timestamp_overlay.step_size = self.step_time.value()
        timestamp_overlay.time_format = self.time_format.currentText()
        timestamp_overlay.x_position_offset = self.x_shift.value()
        timestamp_overlay.y_position_offset = self.y_shift.value()
        timestamp_overlay.time_axis = self.time_axis.value()

    def _connect_all_changes(self):
        for i in [
            self.time_axis,
            self.start_time,
            self.step_time,
            self.ts_size,
            self.x_shift,
            self.y_shift,
        ]:
            i.valueChanged.connect(self._set_timestamp_overlay_options)
        for i in [self.prefix, self.suffix]:
            i.textChanged.connect(self._set_timestamp_overlay_options)
        for i in [self.position, self.time_format]:
            i.currentTextChanged.connect(self._set_timestamp_overlay_options)
        self.toggle_timestamp.clicked.connect(self._toggle_overlay)

        self.color.clicked.connect(self._open_color_dialog)
        self.color.clicked.connect(self._set_timestamp_overlay_options)


class LayerAnnotationsWidget(QtWidgets.QWidget):
    """
    A widget that provides options for the layer annotator overlay in napari viewer.

    Parameters
    ----------
    viewer : napari.Viewer
        The napari viewer instance.
    parent : QWidget, optional
        The parent widget, by default None.
    """

    overlay_set: bool = False

    def __init__(self, viewer: napari.viewer.Viewer, parent=None):
        super().__init__(parent)
        self.viewer = viewer
        self.chosen_color = "grey"  # Default color
        self._setupUi()
        self._connect_all_changes()
        self._setup_overlay()
        self._set_layer_annotator_overlay_options()
        self._on_color_combobox_change()

    def _setup_overlay(self):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            try:
                self.viewer._overlays["LayerAnnotator"]
            except KeyError:
                self.viewer._overlays[
                    "LayerAnnotator"
                ] = LayerAnnotatorOverlay(visible=True)
                overlay_to_visual[
                    LayerAnnotatorOverlay
                ] = VispyLayerAnnotatorOverlay
                self.viewer.window._qt_viewer._add_overlay(
                    self.viewer._overlays["LayerAnnotator"]
                )
            self.layer_annotator_overlay = self.viewer._overlays[
                "LayerAnnotator"
            ]
            self._set_layer_annotator_overlay_options()
            self.overlay_set = True

    def _setupUi(self):
        self.setObjectName("Layer Annotator Options")
        self.gridLayout = QtWidgets.QGridLayout(self)

        # Size Slider
        self.size_label = QtWidgets.QLabel("Size")
        self.size_slider = QLabeledSlider(QtCore.Qt.Horizontal)
        self.size_slider.setRange(1, 100)
        self.size_slider.setValue(12)

        # Position Selector
        self.position_label = QtWidgets.QLabel("Position")
        self.position_combobox = QtWidgets.QComboBox()
        self.position_combobox.addItems(ScenePosition)

        # X and Y Position Offset
        self.xy_offset_label = QtWidgets.QLabel("XY Position Offset")
        self.x_offset_spinbox = QtWidgets.QSpinBox()
        self.x_offset_spinbox.setRange(-1000, 1000)
        self.x_offset_spinbox.setValue(5)
        self.y_offset_spinbox = QtWidgets.QSpinBox()
        self.y_offset_spinbox.setRange(-1000, 1000)
        self.y_offset_spinbox.setValue(5)
        self.offset_layout = QtWidgets.QHBoxLayout()
        self.offset_layout.addWidget(self.x_offset_spinbox)
        self.offset_layout.addWidget(self.y_offset_spinbox)

        # Toggle Visibility Button
        self.toggle_visibility_button = QtWidgets.QPushButton(
            "Toggle Visibility"
        )
        self.toggle_visibility_button.setCheckable(True)
        self.toggle_visibility_button.setChecked(True)

        # Adding Widgets to Layout
        self.gridLayout.addWidget(self.size_label, 0, 0)
        self.gridLayout.addWidget(self.size_slider, 0, 1)

        self.gridLayout.addWidget(self.position_label, 1, 0)
        self.gridLayout.addWidget(self.position_combobox, 1, 1)

        self.gridLayout.addWidget(self.xy_offset_label, 2, 0)
        self.gridLayout.addLayout(self.offset_layout, 2, 1)

        self.gridLayout.addWidget(self.toggle_visibility_button, 3, 0, 1, 2)

        # Choose wether to use layer color or custom color by ticking the checkbox
        self.color_checkbox = QtWidgets.QCheckBox("Use Layer Colormapr")
        self.color_checkbox.setChecked(True)
        self.gridLayout.addWidget(self.color_checkbox, 4, 0)

        # Color Picker
        self.color = QtWidgets.QPushButton("Choose Color")
        self._update_color_button_icon(self.chosen_color)  # Update button icon

        # Adding Color Picker to Layout
        self.gridLayout.addWidget(self.color, 4, 1)

        self.spacer = QtWidgets.QSpacerItem(
            20,
            40,
            QtWidgets.QSizePolicy.Minimum,
            QtWidgets.QSizePolicy.Expanding,
        )
        self.gridLayout.addItem(self.spacer, 5, 0, 1, 2)

        # Set the layout to the widget
        self.setLayout(self.gridLayout)

        # Connect the toggle visibility button to its slot
        self.size_slider.valueChanged.connect(self._on_size_slider_change)
        self.toggle_visibility_button.clicked.connect(self._toggle_visibility)
        self.color_checkbox.stateChanged.connect(
            self._on_color_combobox_change
        )

    def _update_color_button_icon(self, color_str):
        pixmap = QtGui.QPixmap(20, 20)  # Create a QPixmap of size 20x20
        pixmap.fill(
            QtGui.QColor(color_str)
        )  # Fill the pixmap with the chosen color
        icon = QtGui.QIcon(pixmap)  # Convert pixmap to QIcon
        self.color.setIcon(icon)  # Set the icon for the button

    def _on_color_combobox_change(self):
        """
        Slot function to handle changes in the color combobox.
        """
        if self.color_checkbox.isChecked():
            self.color.setEnabled(False)
            self._update_color_button_icon("grey")  # Update button icon
            self.layer_annotator_overlay.use_layer_color = True

        else:
            self.color.setEnabled(True)
            self._update_color_button_icon(self.chosen_color)
            self.layer_annotator_overlay.use_layer_color = False

        self._set_layer_annotator_overlay_options()

    def _open_color_dialog(self):
        self.color_dialog = QtWidgets.QColorDialog(parent=self)
        self.color_dialog.open(self._set_colour)

    def _set_colour(self):
        color = self.color_dialog.selectedColor()
        if color.isValid():
            self.chosen_color = color.name()
            self._update_color_button_icon(self.chosen_color)
            self._set_layer_annotator_overlay_options()

    def _toggle_visibility(self):
        self.layer_annotator_overlay.visible = (
            not self.layer_annotator_overlay.visible
        )
        self.toggle_visibility_button.setText(
            "Hide Overlay"
            if self.layer_annotator_overlay.visible
            else "Show Overlay"
        )

    def _on_size_slider_change(self):
        """
        Slot function to handle changes in the size slider.
        """
        new_size = self.size_slider.value()
        # Update the overlay size
        if self.overlay_set:
            self.layer_annotator_overlay.size = new_size

    def _set_layer_annotator_overlay_options(self):
        """
        Set options for LayerAnnotatorOverlay based on the widget inputs.
        """
        if self.overlay_set:
            # Update the overlay properties
            self.layer_annotator_overlay.position = (
                self.position_combobox.currentText()
            )
            self.layer_annotator_overlay.x_spacer = (
                self.x_offset_spinbox.value()
            )
            self.layer_annotator_overlay.y_spacer = (
                self.y_offset_spinbox.value()
            )
            # get the color from the color picker
            self.layer_annotator_overlay.color = (
                self.chosen_color
            )  # Set color for overlay

    def _connect_all_changes(self):
        """
        Connects all the widget changes to their respective slots.
        """
        self.position_combobox.currentTextChanged.connect(
            self._set_layer_annotator_overlay_options
        )
        self.x_offset_spinbox.valueChanged.connect(
            self._set_layer_annotator_overlay_options
        )
        self.y_offset_spinbox.valueChanged.connect(
            self._set_layer_annotator_overlay_options
        )
        self.color.clicked.connect(self._open_color_dialog)
        self.color.clicked.connect(self._set_layer_annotator_overlay_options)
