import PyQt6.QtWidgets as QtW
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor

class LevelEditor(QtW.QWidget):
    def __init__(self, project):
        super().__init__()

        # Reference to the Project Manager
        self.project = project

        # Palette Storage (64 colors)
        self.colors = [QColor(0, 0, 0) for _i in range(64)]
        self.boxes = []

        self.ui_init()

    def ui_init(self):
        """Top-level UI constructor"""
        layout = QtW.QVBoxLayout()

        # TOP PANEL TOOLBAR
        layout.addLayout(self.ui_build_file_toolbar())


    def ui_build_file_toolbar(self):
        """
        File toolbar constructor (Dropdown and file buttons)

        Returns:
            QtW.QHBoxLayout (file_toolbar; Contains ComboBox and PushButtons)
        """
        toolbar = QtW.QHBoxLayout()
        toolbar.setSpacing(4)
        toolbar.setAlignment(Qt.AlignmentFlag.AlignLeft)

        toolbar.addStretch()
        return toolbar
