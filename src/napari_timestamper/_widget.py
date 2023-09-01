"""
Dock widget for napari-timestamper
"""
from __future__ import annotations

import warnings

import napari
from napari._vispy.utils.visual import overlay_to_visual
from napari.components._viewer_constants import CanvasPosition
from qtpy import QtWidgets

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
