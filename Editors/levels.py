import PyQt6.QtWidgets as QtW
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor

from UI.file_toolbar import create_file_toolbar
from UI.widgets import (
    create_combobox,
    create_label,
    create_pushbutton
)

class LevelEditor(QtW.QWidget):
    def __init__(self, project):
        super().__init__()

        # Reference to the Project Manager
        self.project = project

        # Palette Storage (64 colors)
        self.colors = [QColor(0, 0, 0) for _i in range(64)]
        self.boxes = []

        # "Dirty flag" - Cleared if current state matches last saved state
        self._unsaved_changes = False

        # ui_build_file_toolbar()
        self.level_dropdown = create_combobox(
            tooltip="Select level from the active project")
        self.unsaved_label = create_label("Unsaved Changes")

        self.ui_init()

    def ui_init(self):
        """Top-level UI constructor"""
        layout = QtW.QVBoxLayout(self)

        # TOP PANEL TOOLBAR
        toolbar = create_file_toolbar(self.level_dropdown, self.unsaved_label,
            resource_name="level", unsaved_changes=self._unsaved_changes,
            on_new=None, on_load=None,
            on_save=None, on_save_as=None,
            on_remove=None)
        layout.addLayout(toolbar)

        # Disable everything for now
        for widget_type in (QtW.QPushButton, QtW.QComboBox, QtW.QSpinBox,
                            QtW.QLineEdit, QtW.QCheckBox):
            for widget in self.findChildren(widget_type):
                widget.setEnabled(False)
