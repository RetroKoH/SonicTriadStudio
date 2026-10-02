import PyQt6.QtWidgets as QtW
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor

from UI.collapse_panel import CollapsiblePanel
from UI.widgets import (
    create_combobox,
    create_label,
    create_lineedit,
    create_pushbutton,
    create_radiobutton,
    create_scrollarea,
    create_separator,
    create_slider,
    create_splitter
)

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
        layout = QtW.QVBoxLayout(self)

        # TOP PANEL TOOLBAR
        layout.addLayout(self.ui_build_file_toolbar())

        palette_panel = self.ui_build_palette_panel()  # LEFT PANEL: Palette and Clipboard
        editing_panel = self.ui_build_editing_panel()  # RIGHT PANEL: Editing Controls

        # Horizontal splitter between the palette and editing controls
        self.content_splitter = create_splitter((palette_panel, editing_panel),
            orientation=Qt.Orientation.Horizontal, stretch_factors=(1, 1), sizes=(664, 336))
        layout.addWidget(self.content_splitter, stretch=1)

    def ui_build_file_toolbar(self):
        """
        File toolbar constructor (Dropdown and file buttons)

        Returns:
            QtW.QHBoxLayout (file_toolbar; Contains ComboBox and PushButtons)
        """
        toolbar = QtW.QHBoxLayout()
        toolbar.setSpacing(4)
        toolbar.setAlignment(Qt.AlignmentFlag.AlignLeft)

        # Palette File Dropdown
        self.pal_dropdown = create_combobox(
            tooltip="Select a palette file from the active project",
            layout=toolbar)

        # File Buttons
        create_pushbutton("New", tooltip="Create a new palette",
                          layout=toolbar)
        create_pushbutton("Load", tooltip="Load an existing palette",
                          layout=toolbar)
        create_pushbutton("Save", tooltip="Save the current palette",
                          layout=toolbar)
        create_pushbutton("Save As...", tooltip="Save the current palette under a new name",
                          layout=toolbar)
        create_pushbutton("Remove", tooltip="Remove the current palette from the project",
                          layout=toolbar)

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

        self.btn_undo = create_pushbutton("Undo", tooltip="Undo the last change made",
            width=55, layout=edit_layout)
        self.btn_redo = create_pushbutton("Redo", tooltip="Redo the last undone change",
            width=55, layout=edit_layout)
        self.btn_copy = create_pushbutton("Copy", tooltip="Copy selected colors to the clipboard",
            width=55, layout=edit_layout)
        self.btn_cut = create_pushbutton("Cut", tooltip="Cut selected colors to the clipboard",
            width=55, layout=edit_layout)
        self.btn_paste = create_pushbutton("Paste", tooltip="Paste clipboard colors over the selected color(s)",
            width=55, layout=edit_layout)
        create_pushbutton("Resize Palette", tooltip="Resize the palette",
            width=85, layout=edit_layout)

        edit_layout.addStretch()
        layout.addLayout(edit_layout)

        # Palette Selection Instructions
        instruction_label = create_label(
            "Click to select | Shift-click for range | "
            "Ctrl-click to toggle | Right-click for options",
            layout=layout)

        # To-Do: add this to QSS
        instruction_font = instruction_label.font()
        instruction_font.setPointSizeF(max(8.0, instruction_font.pointSizeF() - 1.0))
        instruction_label.setFont(instruction_font)

        # Scrollable palette grid (w/ resizing ColorBox)
        scroll_content = QtW.QWidget()

        # Palette grid aligns to the top-left corner
        self.grid_layout = QtW.QGridLayout(scroll_content)
        self.grid_layout.setSpacing(5)
        self.grid_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)

        self.palette_scroll = create_scrollarea(scroll_content,
            vertical_policy=Qt.ScrollBarPolicy.ScrollBarAlwaysOn, layout=layout)

        # Palette Clipboard
        self.clipboard_group = CollapsiblePanel("Clipboard",
            tooltip="Expand or collapse the palette clipboard")

        self.btn_toggle_clipboard = self.clipboard_group.toggle_button

        self.btn_clear_clipboard = create_pushbutton("Clear",
            tooltip="Clear out the clipboard",
            layout=self.clipboard_group.header_layout)

        # Scrollable clipboard grid
        clipboard = QtW.QWidget()

        self.clipboard_empty_label = None

        self.clipboard_grid_layout = QtW.QGridLayout(clipboard)
        self.clipboard_grid_layout.setSpacing(6)
        self.clipboard_grid_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)

        self.clipboard_scroll = create_scrollarea(clipboard, layout=self.clipboard_group.content_layout)

        # Draggable divider between the palette and the clipboard
        self.palette_splitter = create_splitter((group, self.clipboard_group),
            orientation=Qt.Orientation.Vertical, stretch_factors=(2, 1), sizes=(400, 200))

        self.clipboard_group.set_splitter(self.palette_splitter)

        return self.palette_splitter

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
        # Preserve the space required by the controls and their spacing
        layout.setSizeConstraint(QtW.QLayout.SizeConstraint.SetMinimumSize)

        # Selected Index Label
        self.index_label = create_label("Selected Color: #0", object_name="infoLabel", layout=layout)

        # Keep all editing sections together at the top
        layout.addStretch()

        # Enable scrolling for the sidebar, disable BG color, and return widget
        self.controls_scroll = create_scrollarea(group,
            frame_shape=QtW.QFrame.Shape.NoFrame, fill_background=False)

        return self.controls_scroll
