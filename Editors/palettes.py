import PyQt6.QtWidgets as QtW
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor

class PaletteEditor(QtW.QWidget):
    def __init__(self, project):
        super().__init__()

        # Reference to the Project Manager
        self.project = project

        # Palette Storage (1 to 256 colors)
        self.colors = [QColor(0, 0, 0) for _i in range(64)]  # Default 64 colors
        self.boxes = []

        # Clipboard Storage
        self.clip_colors = []
        self.clip_boxes = []

        # Selection indices
        self.selected_indices = []
        self.active_index = 0

        self.ui_init()

    def ui_init(self):
        """Top-level UI constructor"""
        layout = QtW.QVBoxLayout()

        # TOP PANEL TOOLBAR
        layout.addLayout(self.ui_build_file_toolbar())

        palette_panel = self.ui_build_palette_panel()  # LEFT PANEL: Palette and Clipboard
        editing_panel = self.ui_build_editing_panel()  # RIGHT PANEL: Editing Controls

        # Horizontal splitter between the palette and editing controls
        #self.content_splitter = create_splitter((palette_panel, editing_panel),
        #    orientation=Qt.Orientation.Horizontal, stretch_factors=(1, 1), sizes=(664, 336))

        #layout.addWidget(self.content_splitter, stretch=1)

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

    def ui_build_palette_panel(self):
        """
        Left-side panel constructor (Palette and Clipboard).

        Returns:
            QtW.QScrollArea (which contains the palette/clipboard group)
        """
        # Palette Grid
        group = QtW.QGroupBox("Palette")
        layout = QtW.QVBoxLayout(group)

        # Palette Editing Toolbar
        edit_layout = QtW.QHBoxLayout()
        edit_layout.setSpacing(4)

        edit_layout.addStretch()
        layout.addLayout(edit_layout)

        return group

    def ui_build_editing_panel(self):
        """
        Right-side panel constructor (Editing tools).

        Returns:
            QtW.QScrollArea (which contains the editing panel group)
        """
        # Color Editing Tool
        group = QtW.QGroupBox("Color Editing")
        group.setObjectName("ControlsGroup")

        layout = QtW.QVBoxLayout(group)

        return group
