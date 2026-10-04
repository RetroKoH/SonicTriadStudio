from pathlib import Path

import PyQt6.QtWidgets as QtW
from PyQt6.QtCore import pyqtSignal, Qt, QEvent, QObject, QSize, QTimer
from PyQt6.QtGui import QColor

from constants import MDCOLOR_VALUES, PALLINE_COLORS, PALEDIT_MAXCOLORS, QCOL_BLACK
from AssetIO.palettes import decode_palette, encode_palette
from Dialogs.palettes import (
    ColorBlendDialog,
    GreyscaleDialog,
    GradientBuilderDialog,
    PaletteExtractDialog
)
from UI.collapse_panel import CollapsiblePanel
from UI.md_color import snap_to_md_color, ColorLibrary
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
from UI.color_box import *

# Edit toolbar button IDs
EDIT_UNDO, EDIT_REDO, EDIT_COPY, EDIT_CUT, EDIT_PASTE = 0, 1, 2, 3, 4

class PaletteEditor(QtW.QWidget):
    # Signals for advanced editing preview sync
    selection_changed = pyqtSignal()
    palette_changed = pyqtSignal()

    def __init__(self, project):
        super().__init__()

        # Reference to the Project Manager
        self.project = project

        # File and Project paths
        self.active_palette_path = None
        self.project_palette_paths = []

        # Palette Storage (1 to 256 colors)
        self.colors = [QCOL_BLACK for _i in range(64)]  # Default 64 colors
        self.boxes = []

        # Clipboard Storage
        self.clip_colors = []
        self.clip_boxes = []

        # Selection indices
        self.selected_indices = []
        self.active_index = 0

        # Dropdown selection index
        self.current_dropdown_index = -1

        # Advanced Editing window handler
        self.active_advanced_dialog = None

        # "Dirty flag" - Cleared if current state matches last saved state
        self._unsaved_changes = False
        self._clean_palette = [QColor(color) for color in self.colors]

        # Undo/Redo stacks
        self.undo_stack = []
        self.redo_stack = []
        self.max_history = 50

        # UI Widget handlers
        # ui_init()
        self.content_splitter = None
        # ui_build_file_toolbar()
        self.pal_dropdown = None
        self.unsaved_label = create_label("Unsaved Changes")
        # ui_build_palette_panel()
        self.btn_edit_group = QtW.QButtonGroup(self)
        self.grid_layout = None
        self.palette_scroll = None
        self.palette_resize_timer = QTimer(self)
        self.clipboard_group = CollapsiblePanel("Clipboard", tooltip="Expand or collapse the palette clipboard")
        self.btn_toggle_clipboard = self.clipboard_group.toggle_button
        self.btn_clear_clipboard = None
        self.clipboard_empty_label = None
        self.clipboard_grid_layout = None
        self.clipboard_scroll = None
        self.palette_splitter = None
        # ui_build_editing_panel()
        self.index_label = create_label("Selected Color: #0", object_name="infoLabel")
        self.large_preview = PreviewColorBox()
        self.hex_input = create_lineedit("#000000", max_length=7, tooltip="Enter a color as #RRGGBB",
            on_editing_finished=self._on_hex_color_edited)

        self.btn_shift_L = create_pushbutton("<< Left",
            tooltip="Rotate selected colors left, wrapping the first to the end",
            on_clicked=lambda: self.edit_palette_shift("left"))
        self.btn_shift_R = create_pushbutton(">> Right",
            tooltip="Rotate selected colors right, wrapping the last to the start",
            on_clicked=lambda: self.edit_palette_shift("right"))

        self.r_slider = self.create_rgb_slider(self._on_rgb_sliders_changed)
        self.g_slider = self.create_rgb_slider(self._on_rgb_sliders_changed)
        self.b_slider = self.create_rgb_slider(self._on_rgb_sliders_changed)
        for slider in (self.r_slider, self.g_slider, self.b_slider):
            slider.sliderPressed.connect(lambda: self.history_push_state())
            # Track when value changes start via track-click or wheel
            slider.valueChanged.connect(self._on_slider_value_changed)

        self.r_val_label = create_label("0")
        self.g_val_label = create_label("0")
        self.b_val_label = create_label("0")
        self.batch_scope_group = QtW.QButtonGroup(self)
        self.opt_mass_all = create_radiobutton("Full Palette",
            checked=True, group=self.batch_scope_group, button_id=0)
        self.opt_mass_selected = create_radiobutton("Selected Color(s)",
            group=self.batch_scope_group, button_id=1)

        self.controls_scroll = None

        self.ui_init()

        self.project.project_loaded.connect(self._on_project_loaded)

    # --------------------------------------------------
    # UI Setup
    # --------------------------------------------------
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

        # Build initial grid UI and set selection to color 0
        self.palette_set_colors(self.colors)

        # Initialize palette clipboard
        self.clipboard_refresh()
        self.btn_toggle_clipboard.setChecked(False)

    def ui_build_file_toolbar(self):
        """
        File toolbar constructor (Dropdown and file buttons)

        Returns:
            QtW.QHBoxLayout (file_toolbar; Contains ComboBox and PushButtons)
        """
        toolbar = QtW.QHBoxLayout()
        toolbar.setSpacing(4)
        toolbar.setAlignment(Qt.AlignmentFlag.AlignLeft)

        create_label("Palette:", layout=toolbar)
        # Palette File Dropdown
        self.pal_dropdown = create_combobox(
            tooltip="Select a palette file from the active project",
            on_index_changed=self._on_pal_dropdown_changed, layout=toolbar)

        # File Buttons
        create_pushbutton("New", tooltip="Create a new palette",
            on_clicked=lambda: self.check_unsaved_changes(self.file_palette_new), layout=toolbar)
        create_pushbutton("Load", tooltip="Load an existing palette",
            on_clicked=lambda: self.check_unsaved_changes(self.file_palette_load), layout=toolbar)
        create_pushbutton("Save", tooltip="Save the current palette",
            on_clicked=self.file_palette_save, layout=toolbar)
        create_pushbutton("Save As...", tooltip="Save the current palette under a new name",
            on_clicked=self.file_palette_save_as, layout=toolbar)
        create_pushbutton("Remove", tooltip="Remove the current palette from the project",
            on_clicked=self.file_palette_remove, layout=toolbar)

        toolbar.addWidget(self.unsaved_label)
        self.unsaved_label.setVisible(self._unsaved_changes)

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

        # Set-up Edit Group (Created in __init__)
        self.btn_edit_group.setExclusive(False)

        btn_undo = create_pushbutton("Undo", tooltip="Undo the last change made", width=55,
            on_clicked=self.history_undo)
        btn_redo = create_pushbutton("Redo", tooltip="Redo the last undone change", width=55,
            on_clicked=self.history_redo)
        btn_copy = create_pushbutton("Copy", tooltip="Copy selected colors to the clipboard", width=55,
            on_clicked=lambda _: self.clipboard_copy(cut=False))
        btn_cut = create_pushbutton("Cut", tooltip="Cut selected colors to the clipboard", width=55,
            on_clicked=lambda _: self.clipboard_copy(cut=True))
        btn_paste = create_pushbutton("Paste", tooltip="Paste over the selected color(s)", width=55,
            on_clicked=lambda _: self.clipboard_paste("over", self.active_index))

        self.btn_edit_group.addButton(btn_undo, id=0)
        self.btn_edit_group.addButton(btn_redo, id=1)
        self.btn_edit_group.addButton(btn_copy, id=2)
        self.btn_edit_group.addButton(btn_cut, id=3)
        self.btn_edit_group.addButton(btn_paste, id=4)

        for button in self.btn_edit_group.buttons():
            edit_layout.addWidget(button)

        create_pushbutton("Resize Palette", tooltip="Resize the palette",
            width=85, on_clicked=self.edit_palette_resize, layout=edit_layout)

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

        # Defer resizing until Qt has updated the viewport geometry
        self.palette_resize_timer.setSingleShot(True)
        self.palette_resize_timer.timeout.connect(self.palette_resize_boxes)

        # This is for the resizing
        self.palette_scroll.viewport().installEventFilter(self)

        # Palette Clipboard (Within a collapsible panel)
        self.btn_clear_clipboard = create_pushbutton("Clear",
            tooltip="Clear out the clipboard", on_clicked=self.clipboard_clear,
            layout=self.clipboard_group.header_layout)

        # Scrollable clipboard grid
        clipboard = QtW.QWidget()

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
        layout.addWidget(self.index_label)

        # Hex Preview & Large Color Box
        preview_layout = QtW.QHBoxLayout()
        self.large_preview.clicked.connect(self.edit_open_color_library)
        preview_layout.addWidget(self.large_preview)

        # Hex Input Line
        preview_layout.addLayout(self.create_form_row("Hex Value:", self.hex_input))

        layout.addLayout(preview_layout)

        layout.addSpacing(15)

        # RGB sliders
        layout.addLayout(self.create_rgb_slider_row("Red:", self.r_slider, self.r_val_label))
        layout.addLayout(self.create_rgb_slider_row("Green:", self.g_slider, self.g_val_label))
        layout.addLayout(self.create_rgb_slider_row("Blue:", self.b_slider, self.b_val_label))

        # Separate individual color controls from batch editing
        create_separator(layout=layout)

        # Batch Editing
        create_label("Batch Editing", object_name="infoLabel", layout=layout)

        batch_scope_layout = QtW.QHBoxLayout()
        batch_scope_layout.addWidget(self.opt_mass_all)
        batch_scope_layout.addWidget(self.opt_mass_selected)

        layout.addLayout(batch_scope_layout)

        # Batch Channel Editing
        batch_edit_layout = QtW.QGridLayout()
        batch_edit_layout.setHorizontalSpacing(6)
        batch_edit_layout.setVerticalSpacing(4)

        channels = [("Red", 'r'), ("Green", 'g'), ("Blue", 'b')]
        for idx, (label_text, ch) in enumerate(channels):
            label = create_label(f"{label_text} Channel:")

            # lambdas have an unused parameter so channel doesn't get overwritten by button's 'checked' bool
            btn_minus = create_pushbutton("-",
                tooltip=f"Decrease {label_text.lower()} by one step for all chosen colors",
                width=40, on_clicked=lambda _, channel=ch: self.batch_shift_color(-1, channel))
            btn_plus = create_pushbutton("+",
                tooltip=f"Increase {label_text.lower()} by one step for all chosen colors",
                width=40, on_clicked=lambda _, channel=ch: self.batch_shift_color(1, channel))
            btn_invert = create_pushbutton("Invert",
                tooltip=f"Invert the {label_text.lower()} channel for all chosen colors",
                width=60, on_clicked=lambda _, channel=ch: self.batch_invert_color(channel))
            btn_clear = create_pushbutton("Clear",
                tooltip=f"Clear the {label_text.lower()} channel to 0 for all chosen colors",
                width=55, on_clicked=lambda _, channel=ch: self.batch_clear_color(channel))

            batch_edit_layout.addWidget(label, idx, 0)
            batch_edit_layout.addWidget(btn_minus, idx, 1)
            batch_edit_layout.addWidget(btn_plus, idx, 2)
            batch_edit_layout.addWidget(btn_invert, idx, 3)
            batch_edit_layout.addWidget(btn_clear, idx, 4)

        rows = len(channels)
        batch_edit_layout.addWidget(create_label("All Channels:"), rows, 0)

        # These effect all three channels within the chosen batch scope
        btn_minus_all = create_pushbutton("-", tooltip="Decrease RGB channels for all chosen colors",
            width=40, on_clicked=lambda _: self.batch_shift_color(-1))
        btn_plus_all = create_pushbutton("+", tooltip="Increase RGB channels for all chosen colors",
            width=40, on_clicked=lambda _: self.batch_shift_color(1))
        btn_invert_all = create_pushbutton("Invert", tooltip="Invert RGB channels for all chosen colors",
            width=60, on_clicked=lambda _: self.batch_invert_color())
        btn_clear_all = create_pushbutton("Clear", tooltip="Clear RGB channels to 0 for all chosen colors",
            width=55, on_clicked=lambda _: self.batch_clear_color())

        batch_edit_layout.addWidget(btn_minus_all, rows, 1)
        batch_edit_layout.addWidget(btn_plus_all, rows, 2)
        batch_edit_layout.addWidget(btn_invert_all, rows, 3)
        batch_edit_layout.addWidget(btn_clear_all, rows, 4)

        # Keep the controls together, with spare space on the right
        batch_edit_layout.setColumnStretch(5, 1)

        layout.addLayout(batch_edit_layout)

        # Shift Selected Colors
        shift_layout = QtW.QHBoxLayout()
        shift_layout.setSpacing(4)

        create_label("Shift selected colors:", layout=shift_layout)
        shift_layout.addWidget(self.btn_shift_L)
        shift_layout.addWidget(self.btn_shift_R)

        shift_layout.addStretch()

        layout.addLayout(shift_layout)

        # Advanced Color Editing
        create_separator(layout=layout)

        # Advanced Editing options
        create_label("Advanced Color Editing", object_name="infoLabel", layout=layout)

        # Advanced Option Buttons
        btn_grid_adv = QtW.QGridLayout()
        btn_grid_adv.setHorizontalSpacing(6)
        btn_grid_adv.setVerticalSpacing(6)
        btn_grid_adv.setColumnStretch(0, 1)
        btn_grid_adv.setColumnStretch(1, 1)

        btn_blend = create_pushbutton("Color Blending", width=None,
            tooltip="Blend the palette with selected color(s)", on_clicked=self.adv_blend_colors)
        btn_grey = create_pushbutton("Greyscaling", width=None,
            tooltip="Apply greyscale effects to the palette", on_clicked=self.adv_greyscale_colors)
        btn_gradient = create_pushbutton("Build Color Gradient", width=None,
            tooltip="Build a color gradient within the palette", on_clicked=self.adv_build_gradient)
        btn_extract = create_pushbutton("Extract Palette from Image", width=None,
            tooltip="Extract palette colors from a loaded image", on_clicked=self.adv_extract_palette)

        btn_grid_adv.addWidget(btn_blend, 0, 0, 1, 1)
        btn_grid_adv.addWidget(btn_grey, 0, 1, 1, 1)
        btn_grid_adv.addWidget(btn_gradient, 1, 0, 1, 2)
        btn_grid_adv.addWidget(btn_extract, 2, 0, 1, 2)

        layout.addLayout(btn_grid_adv)

        # Keep all editing sections together at the top
        layout.addStretch()

        # Enable scrolling for the sidebar, disable BG color, and return widget
        self.controls_scroll = create_scrollarea(group,
            frame_shape=QtW.QFrame.Shape.NoFrame, fill_background=False)

        return self.controls_scroll

    @staticmethod
    def create_rgb_slider(callback):
        """
        Creates sliders for RGB component editing.

        Returns:
            QtW.QSlider
        """
        return create_slider(minimum=0, maximum=7,
            single_step=1, page_step=1, tick_position=QtW.QSlider.TickPosition.TicksBelow,
            tick_interval=1, on_value_changed=callback)

    @staticmethod
    def create_rgb_slider_row(label_text, slider, val_label):
        """
        RBG slider row constructor (Premade slider and labels)

        Returns:
            QtW.QHBoxLayout (Name label, slider, value label)
        """
        layout = QtW.QHBoxLayout()

        # Insert Color label (Red, Green, Blue)
        create_label(label_text, width=50, layout=layout)

        # Insert RGB slider
        layout.addWidget(slider)

        # Insert value label
        val_label.setFixedWidth(30)
        layout.addWidget(val_label)

        return layout

    @staticmethod
    def create_form_row(label_text, widget):
        """
        Line edit form row constructor (Input field with a label above it).

        Returns:
            QtW.QVBoxLayout (Text label, Widget (Expected: LineEdit))
        """
        layout = QtW.QVBoxLayout()

        create_label(label_text, layout=layout)
        layout.addWidget(widget)

        return layout


    # --------------------------------------------------
    # File Operations
    # --------------------------------------------------
    def file_palette_new(self):
        """
        Creates and saves a new palette.
        Registers it and activates it for use.

        Returns:
            True if creation succeeded, False otherwise.
        """
        count, ok = QtW.QInputDialog.getInt(self, "New Palette",
            "Number of colors:", 16, 1, PALEDIT_MAXCOLORS, 1)

        # Exit if the user cancels
        if not ok:
            return False

        # Access project directory
        project_dir = self.project.root_dir
        start_dir = str(project_dir) if project_dir else ""

        # Save dialog for new palette file
        file_path, _ = QtW.QFileDialog.getSaveFileName(self, "Create Palette File",
            start_dir, "Palette Files (*.bin *.pal);;All Files (*)")

        # If no filepath, stop here
        if not file_path:
            return False

        path = self.project.resolve_asset_path(file_path)

        # Init new palette as all black
        new_pal = [QCOL_BLACK for _i in range(count)]

        # Write new palette to file, stop here if failed
        if not self.file_pal_data_write(path, new_pal):
            return False

        # Project exclusive block
        try:
            self.proj_add_palette(path)

        except (OSError, TypeError, ValueError) as e:
            QtW.QMessageBox.warning(self, "Project Update Error",
                "The palette file was created, but it could not "
                f"be added to the project:\n{e}",
            )
            return False

        # Activate the created palette
        self.palette_set_colors(new_pal)
        self.proj_register_palette(path)
        self.record_clean_palette()

        # Successful creation
        return True

    def file_palette_load(self):
        """
        Loads a palette file.
        Registers and activates it for use.

        Returns:
            True if creation succeeded, False otherwise.
        """
        # Access project directory
        project_dir = self.project.root_dir
        start_dir = str(project_dir) if project_dir else ""

        # Load dialog for palette file
        file_path, _ = QtW.QFileDialog.getOpenFileName(self, "Load Palette",
            start_dir, "Palette Files (*.bin *.pal);;All Files (*)")

        # If no filepath, stop here
        if not file_path:
            return False

        path = self.project.resolve_asset_path(file_path)

        # Validate palette file and load data into a buffer
        loaded_colors = self.file_pal_data_read(path)

        # If load failed, stop here
        if loaded_colors is None:
            return False

        # Project exclusive block
        try:
            self.proj_add_palette(path)

        except (OSError, TypeError, ValueError) as e:
            QtW.QMessageBox.warning(self, "Project Update Error",
                f"Could not add the palette to the project:\n{e}",
            )
            return False

        # Activate the loaded palette
        self.palette_set_colors(loaded_colors)
        self.proj_register_palette(path)
        self.record_clean_palette()

        # Successful load
        return True

    def file_palette_save(self):
        """
        Saves the active palette data to file.
        If no active path, Save As is called instead.

        Returns:
            True if save was successful, False otherwise.
        """
        if not (self.active_palette_path and self.active_palette_path.parent.exists()):
            return self.file_palette_save_as()

        if not self.file_pal_data_write(self.active_palette_path, self.colors):
            return False

        self.record_clean_palette()
        return True

    def file_palette_save_as(self):
        """
        Writes current palette data to a chosen path.
        Registers it with the active project under the new path.
        Activates it for use.

        Returns:
            True if save was successful, False otherwise.
        """
        # Access project directory
        project_dir = self.project.root_dir
        start_dir = str(project_dir) if project_dir else ""

        # Save dialog for new palette file
        file_path, _ = QtW.QFileDialog.getSaveFileName(self, "Save Palette As",
            start_dir,"Palette Files (*.bin *.pal);;All Files (*)")

        # If no filepath, stop here
        if not file_path:
            return False

        path = self.project.resolve_asset_path(file_path)

        # Attempt to write palette to file first
        if not self.file_pal_data_write(path, self.colors):
            return False

        # Project exclusive block
        try:
            self.proj_add_palette(path)

        except (OSError, TypeError, ValueError) as e:
            QtW.QMessageBox.warning(self, "Project Update Error",
                "The palette file was saved, but it could not "
                f"be added to the project:\n{e}",
            )
            return False

        # Activate the newly saved palette
        self.proj_register_palette(path)
        self.record_clean_palette()

        # Successful save
        return True

    def file_palette_remove(self):
        """
        Removes the active palette from the project, discarding pending edits.
        Does not delete the actual file from disk.

        Returns:
            True if removal was successful, False otherwise.
        """
        path = self.active_palette_path

        # If no filepath, stop here
        if path is None:
            return False

        message = f"Are you sure you want to remove '{path.name}' from the project?"

        if self.unsaved_changes:
            message += "\n\nUnsaved changes will be discarded."

        message += "\n\nThe palette file on disk will remain unchanged."

        # Confirm removal
        reply = QtW.QMessageBox.question(self, "Remove Palette", message,
            QtW.QMessageBox.StandardButton.Yes | QtW.QMessageBox.StandardButton.No,
            QtW.QMessageBox.StandardButton.No)

        # If confirmation fails, stop here
        if reply != QtW.QMessageBox.StandardButton.Yes:
            return False

        try:
            self.proj_remove_palette(path)

        except (OSError, TypeError, ValueError) as e:
            QtW.QMessageBox.warning(
                self,
                "Project Update Error",
                f"Could not remove the palette from the project:\n{e}",
            )
            return False

        # Remove path from the list of palettes
        remaining_paths = [p for p in self.project_palette_paths if p != path]

        # Discard the removed palette
        self.active_palette_path = None
        self.current_dropdown_index = -1
        self.palette_set_colors([QCOL_BLACK for _ in range(64)])
        self.record_clean_palette()
        self.palette_refresh_highlighting()

        # Refresh the dropdown and load the first remaining palette, if any
        self.proj_populate_pal_list(remaining_paths)

        return True

    @staticmethod
    def file_pal_data_read(path):
        """
        Validate and read palette file.

        Returns:
            loaded_colors (list) if read was successful.
            None if read failed.
        """
        try:
            # Read up to 256 colors (512 bytes)
            with open(path, "rb") as f:
                data = f.read(512)

            if not data:
                raise ValueError("The palette file is empty.")

            # Successful read
            return decode_palette(data)

        # Failed read
        except (OSError, ValueError) as e:
            print(f"Error loading palette {path.name}: {e}")
            return None

    @staticmethod
    def file_pal_data_write(path, colors):
        """
        Write palette color data to file.

        Returns:
            True if writing succeeded.
            False if writing failed.
        """
        binary_data = encode_palette(colors)

        try:
            # Write binary data to file (creates file if it doesn't exist)
            with open(path, "wb") as f:
                f.write(binary_data)

            # Successful Save
            return True

        # Failed write
        except OSError as e:
            print(f"Error saving palette {path.name}: {e}")
            return False


    # --------------------------------------------------
    # Project File Selection
    # --------------------------------------------------
    def proj_register_palette(self, path):
        """
        Activate a palette path and register it in the editor's dropdown.
        """
        # Update the current palette file reference
        self.active_palette_path = path

        # Add it to the project if needed
        if path not in self.project_palette_paths:
            self.project_palette_paths.append(path)

        # Repopulate the dropdown list
        self.proj_populate_pal_list(self.project_palette_paths)

        # Set dropdown selection to newly added palette
        target_index = -1
        for i in range(self.pal_dropdown.count()):
            item_data = self.pal_dropdown.itemData(i)
            if item_data and Path(item_data) == path:
                target_index = i
                break

        # Set selection to the new palette
        if target_index >= 0:
            was_blocked = self.pal_dropdown.blockSignals(True)

            try:
                self.pal_dropdown.setCurrentIndex(target_index)
                self.current_dropdown_index = target_index
            finally:
                self.pal_dropdown.blockSignals(was_blocked)

    def proj_populate_pal_list(self, palette_paths):
        self.project_palette_paths = list(palette_paths)

        self.pal_dropdown.blockSignals(True)
        self.pal_dropdown.clear()

        if not palette_paths:
            self.pal_dropdown.addItem("No Palettes Found", userData=None)
            self.pal_dropdown.setEnabled(False)
            self.pal_dropdown.blockSignals(False)
            return

        self.pal_dropdown.setEnabled(True)
        for path in self.project_palette_paths:
            # Display relative filename to user, store full Path object in itemData
            self.pal_dropdown.addItem(path.name, userData=path)

        # Silently reset the selection
        self.pal_dropdown.setCurrentIndex(-1)
        self.pal_dropdown.blockSignals(False)

        # Only auto-load index 0 if we aren't currently targeting a specific file
        if not self.active_palette_path and self.pal_dropdown.count() > 0:
            self.pal_dropdown.setCurrentIndex(0)

    def proj_add_palette(self, path):
        """
        Add a palette to the active project and save the project.

        Does nothing when no project is loaded or the palette is
        already registered. Raises an exception if saving fails.
        """
        project = self.project

        if not project.is_loaded:
            return

        path = project.resolve_asset_path(path)
        proposed = project.snapshot()
        palette_paths = proposed.get("palettes", [])

        # Compare resolved paths so different spellings of the same
        # path do not create duplicate entries.
        already_registered = any(project.resolve_asset_path(existing)
            == path for existing in palette_paths)

        if already_registered:
            return

        proposed["palettes"] = [
            *palette_paths,
            project.store_asset_path(path),
        ]

        project.save(proposed)

    def proj_remove_palette(self, path):
        """
        Remove a palette from the active project and save the project.

        Does nothing when no project is loaded or the palette is
        not registered. Raises an exception if saving fails.
        """
        project = self.project

        if not project.is_loaded:
            return

        path = project.resolve_asset_path(path)
        proposed = project.snapshot()
        palette_paths = proposed.get("palettes", [])

        remaining_paths = [
            existing
            for existing in palette_paths
            if project.resolve_asset_path(existing) != path
        ]

        if len(remaining_paths) == len(palette_paths):
            return

        proposed["palettes"] = remaining_paths
        project.save(proposed)

    # File Toolbar Dropdown function
    def _on_pal_dropdown_changed(self, index):
        # Ignore if only reverting/resetting UI
        if index < 0:
            return

        # Capture the requested palette before any save prompt
        path = self.pal_dropdown.itemData(index)

        if not isinstance(path, Path):
            return

        # No switch is needed if this palette is already active
        if path == self.active_palette_path:
            self.current_dropdown_index = index
            return

        def revert_selection():
            # Find the currently active palette. Save As may have
            # changed its path and dropdown position during the prompt.
            restore_index = -1

            for i in range(self.pal_dropdown.count()):
                if self.pal_dropdown.itemData(i) == self.active_palette_path:
                    restore_index = i
                    break

            # Silently revert dropdown, don't replace palette
            was_blocked = self.pal_dropdown.blockSignals(True)

            try:
                self.pal_dropdown.setCurrentIndex(restore_index)
                self.current_dropdown_index = restore_index
            finally:
                self.pal_dropdown.blockSignals(was_blocked)

        def load_new_selection():
            # Read without replacing the current palette
            loaded_colors = self.file_pal_data_read(path)

            if loaded_colors is None:
                revert_selection()
                return

            # Activate only after reading succeeds
            self.palette_set_colors(loaded_colors)
            self.proj_register_palette(path)
            self.record_clean_palette()

        self.check_unsaved_changes(load_new_selection, revert_selection)

    def _on_project_loaded(self):
        """Reset the palette document and read the active project's list."""
        project = self.project

        palette_paths = [
            project.resolve_asset_path(path)
            for path in project.data.get("palettes", [])
        ]

        # Discard the previous project's document association
        self.active_palette_path = None
        self.current_dropdown_index = -1

        # Establish a blank document before selecting a new palette
        self.palette_set_colors([
            QColor(0, 0, 0) for _ in range(64)
        ])
        self.record_clean_palette()

        # The existing population method selects the first palette, if any
        self.proj_populate_pal_list(palette_paths)


    # --------------------------------------------------
    # Unsaved Change Handling
    # --------------------------------------------------
    @property
    def unsaved_changes(self):
        return self._unsaved_changes

    @unsaved_changes.setter
    def unsaved_changes(self, value=True):
        self._unsaved_changes = value
        self.unsaved_label.setVisible(value)

    def check_unsaved_changes(self, pending_action_callback, cancel_callback=None):
        if not self.unsaved_changes:
            pending_action_callback()
            return

        user_choice = self.show_save_prompt_dialog()

        if user_choice == "Save":
            if self.file_palette_save():
                pending_action_callback()
            elif cancel_callback is not None:
                cancel_callback()
        elif user_choice == "Save As":
            if self.file_palette_save_as():
                pending_action_callback()
            elif cancel_callback is not None:
                cancel_callback()
        elif user_choice == "Don't Save":
            pending_action_callback()
        elif user_choice == "Cancel":
            # Revert UI state if needed
            if cancel_callback:
                cancel_callback()
            return

    def show_save_prompt_dialog(self):
        prompt = QtW.QMessageBox(self)
        prompt.setWindowTitle("Unsaved Changes")
        prompt.setText("You have unsaved changes in the current palette. What would you like to do?")

        btn_save = prompt.addButton("Save", QtW.QMessageBox.ButtonRole.AcceptRole)
        btn_save_as = prompt.addButton("Save As...", QtW.QMessageBox.ButtonRole.AcceptRole)
        btn_dont_save = prompt.addButton("Don't Save", QtW.QMessageBox.ButtonRole.DestructiveRole)
        btn_cancel = prompt.addButton("Cancel", QtW.QMessageBox.ButtonRole.RejectRole)

        prompt.exec()

        clicked_btn = prompt.clickedButton()
        if clicked_btn == btn_save:
            return "Save"
        elif clicked_btn == btn_save_as:
            return "Save As"
        elif clicked_btn == btn_dont_save:
            return "Don't Save"
        else:
            return "Cancel"

    def record_clean_palette(self):
        """
        Record the current palette as the baseline for unsaved changes.
        """
        self._clean_palette = [QColor(color) for color in self.colors]
        self.unsaved_changes = False

    def update_unsaved_changes(self):
        """
        Update the unsaved flag by comparing colors with the clean baseline.
        """
        self.unsaved_changes = self.colors != self._clean_palette


    # --------------------------------------------------
    # Palette Data Grid
    # --------------------------------------------------
    def palette_set_colors(self, colors):
        # Constrain to range [1, 256]; To-Do: Make the first line optional if palette_colors is already defined
        self.colors = colors[:PALEDIT_MAXCOLORS] if colors else [QCOL_BLACK]

        self.palette_rebuild_grid()
        self.selected_indices = [0]
        self.active_index = 0
        self.palette_refresh_highlighting()
        self.history_clear()

    def palette_rebuild_grid(self, index=0):
        # Use index to tell Triad how much to rebuild (avoid unnecessary work)
        index = max(0, min(index, len(self.boxes)))

        # Clear color boxes, starting with [index]
        for box in self.boxes[index:]:
            box.deleteLater()

        # Remove deleted references
        self.boxes = self.boxes[:index]

        # Build grid (only the missing portion)
        for idx in range(index, len(self.colors)):
            color = self.colors[idx]
            row, col = idx // PALLINE_COLORS, idx % PALLINE_COLORS

            box = ColorBox(idx, color)
            box.editor = self
            self.grid_layout.addWidget(box, row, col)
            self.boxes.append(box)

        # Emit signal so open dialogs know palette size changed
        self.palette_resize_timer.start(0)
        self.palette_changed.emit()

    def palette_select_colors(self, index, modifiers):
        if modifiers & Qt.KeyboardModifier.ControlModifier:
            # CTRL+CLICK: Toggle selection
            if index in self.selected_indices:
                self.selected_indices.remove(index)
                # Make sure we don't end up with zero selections
                if not self.selected_indices:
                    self.selected_indices = [self.active_index]
            else:
                self.selected_indices.append(index)
                self.active_index = index  # Make the newly toggled item the active index

        elif modifiers & Qt.KeyboardModifier.ShiftModifier:
            # SHIFT+CLICK: Select a range, starting from the active index
            start, end = self.active_index, index
            step = 1 if start <= end else -1

            for i in range(start, end + step, step):
                if i not in self.selected_indices:
                    self.selected_indices.append(i)
            self.active_index = index

        else:
            # NORMAL CLICK: Clear group selection (if any), and pick a single color
            self.selected_indices = [index]
            self.active_index = index

        self.palette_refresh_highlighting()

    # Tied to ColorBox resizing
    def eventFilter(self, a0: QObject|None, a1: QEvent|None) -> bool:
        if (
            a0 is self.palette_scroll.viewport()
            and a1.type() == QEvent.Type.Resize
        ):
            self.palette_resize_timer.start(0)

        return super().eventFilter(a0, a1)

    def palette_resize_boxes(self):
        if not self.boxes:
            return

        columns = PALLINE_COLORS
        margins = self.grid_layout.contentsMargins()
        spacing = self.grid_layout.horizontalSpacing()

        # Subtract the grid margins and gaps between columns
        available_width = (
            self.palette_scroll.viewport().width()
            - margins.left()
            - margins.right()
            - spacing * (columns - 1)
        )

        box_size = max(32, available_width // columns)
        target_size = QSize(box_size, box_size)

        for box in self.boxes:
            if box.minimumSize() != target_size:
                box.setFixedSize(target_size)

    def palette_check_selection(self):
        # Filter out-of-bounds selected indices
        self.selected_indices = [
            idx for idx in self.selected_indices
            if 0 <= idx < len(self.colors)
        ]

        # Adjust the active index if out-of-bounds
        self.active_index = max(0, min(self.active_index, len(self.colors) - 1))

        # Always retain at least one selected color
        if not self.selected_indices:
            self.selected_indices = [self.active_index]

        # The active color should belong to the selection
        elif self.active_index not in self.selected_indices:
            self.active_index = self.selected_indices[-1]

    def palette_refresh_highlighting(self):
        # Update active selection highlighting for all boxes
        for idx, box in enumerate(self.boxes):
            box.set_selected(idx in self.selected_indices)

        # Dynamic elements based on color selection count
        count = len(self.selected_indices)
        # Shifting requires at least two selected colors
        self.btn_shift_L.setEnabled(count > 1)
        self.btn_shift_R.setEnabled(count > 1)
        # Set selected color text
        if count > 1:
            self.index_label.setText(f"Selected: {count} Colors (Active: #{self.active_index})")
        else:
            self.index_label.setText(f"Selected Color: #{self.active_index}")

        # Editing panel will still reflect the active index color
        active_color = self.colors[self.active_index]

        # Block input signals
        self.r_slider.blockSignals(True)
        self.g_slider.blockSignals(True)
        self.b_slider.blockSignals(True)
        self.hex_input.blockSignals(True)

        # Now, update sliders and preview safely
        _r = snap_to_md_color(active_color.red())
        _g = snap_to_md_color(active_color.green())
        _b = snap_to_md_color(active_color.blue())

        self.r_slider.setValue(_r)
        self.g_slider.setValue(_g)
        self.b_slider.setValue(_b)

        self.r_val_label.setText(f"0x{MDCOLOR_VALUES[_r]:02X}")
        self.g_val_label.setText(f"0x{MDCOLOR_VALUES[_g]:02X}")
        self.b_val_label.setText(f"0x{MDCOLOR_VALUES[_b]:02X}")

        self.hex_input.setText(active_color.name().upper())
        self.palette_update_preview(active_color)

        # Unblock input signals
        self.r_slider.blockSignals(False)
        self.g_slider.blockSignals(False)
        self.b_slider.blockSignals(False)
        self.hex_input.blockSignals(False)

        # Emit signal so open dialogs know selection or active colors changed
        self.selection_changed.emit()

    def palette_update_preview(self, color):
        self.large_preview.setStyleSheet(f"""
            QFrame {{
                background-color: {color.name()};
                border: 2px solid #555555;
                border-radius: 6px;
            }}
        """)


    # --------------------------------------------------
    # Individual Color Editing Functions
    # --------------------------------------------------
    def edit_set_active_color(self, color):
        """Updates the actively selected color"""
        self.colors[self.active_index] = color
        self.boxes[self.active_index].set_color(color)
        self.palette_update_preview(color)

    def edit_open_color_library(self):
        # Get active color from the main editor
        active_color = self.colors[self.active_index]

        # Unlike the other mini-windows, this one runs modally
        dialog = ColorLibrary(active_color, self)
        if dialog.exec():
            self.history_push_state()  # Record state before applying chosen color

            # Apply picked color to active index
            new_color = dialog.get_color()
            self.edit_set_active_color(new_color)
            self.palette_refresh_highlighting()
            self.update_unsaved_changes()

    # RGB Slider function
    def _on_slider_value_changed(self):
        """
        Push state once when needed to avoid polluting undo stack.
        """
        # If the user isn't actively dragging with mouse, push state once on discrete click/wheel step
        dragging = any(s.isSliderDown() for s in (self.r_slider, self.g_slider, self.b_slider))
        if not dragging:
            self.history_push_state()

    def _on_rgb_sliders_changed(self):
        """
        Updates RGB color values and UI preview without pushing history states directly.
        """
        _r = MDCOLOR_VALUES[self.r_slider.value()]
        _g = MDCOLOR_VALUES[self.g_slider.value()]
        _b = MDCOLOR_VALUES[self.b_slider.value()]

        self.r_val_label.setText(f"0x{_r:02X}")
        self.g_val_label.setText(f"0x{_g:02X}")
        self.b_val_label.setText(f"0x{_b:02X}")

        new_color = QColor(_r, _g, _b)

        self.hex_input.blockSignals(True)
        self.hex_input.setText(new_color.name().upper())
        self.hex_input.blockSignals(False)

        self.edit_set_active_color(new_color)
        self.update_unsaved_changes()

    # Color input edit function
    def _on_hex_color_edited(self):
        hex_text = self.hex_input.text()
        color = QColor(hex_text)
        if color.isValid():
            self.history_push_state()      # Record state before editing

            _r = snap_to_md_color(color.red())
            _g = snap_to_md_color(color.green())
            _b = snap_to_md_color(color.blue())

            snapped_color = QColor(
                MDCOLOR_VALUES[_r],
                MDCOLOR_VALUES[_g],
                MDCOLOR_VALUES[_b]
            )

            self.edit_set_active_color(snapped_color)
            self.palette_refresh_highlighting()

            self.update_unsaved_changes()


    # --------------------------------------------------
    # Palette Structure Functions
    # --------------------------------------------------
    def edit_palette_resize(self):
        current_size = len(self.colors)
        new_size, ok = QtW.QInputDialog.getInt(self, "Resize Palette",
            "Number of colors:", current_size, 1, PALEDIT_MAXCOLORS, 1)

        # Exit if the user cancels or doesn't change the size
        if not ok or new_size == current_size:
            return

        self.history_push_state()  # Record state before resizing palette

        # Extending palette size
        if new_size > current_size:
            # Append black colors
            self.colors.extend(QColor(0, 0, 0) for _ in range(new_size - current_size))

            # Rebuild starting from the first newly added index
            self.palette_rebuild_grid(current_size)

        # Retracting palette size
        else:
            self.colors = self.colors[:new_size]
            self.palette_check_selection()
            self.palette_rebuild_grid(new_size)
            self.palette_refresh_highlighting()

        self.update_unsaved_changes()

    def edit_palette_shift(self, direction):
        # Do nothing if multiple colors aren't selected
        if len(self.selected_indices) <= 1:
            return

        self.history_push_state()  # Record state before shifting palette

        # Sort indices to maintain sequential order
        sorted_indices = sorted(self.selected_indices)
        colors = [self.colors[i] for i in sorted_indices]

        # Perform rotating shift
        if direction == "left":
            rotated = colors[1:] + colors[:1]
        elif direction == "right":
            rotated = colors[-1:] + colors[:-1]
        else:
            return

        # Update palette array and visual box widgets
        for idx, color in zip(sorted_indices, rotated):
            self.colors[idx] = color
            self.boxes[idx].set_color(color)

        self.palette_refresh_highlighting()
        self.update_unsaved_changes()

    def edit_remove_colors(self, indices):
        self.history_push_state()  # Record state before removing color(s)

        lowest = indices[-1]     # for palette_rebuild_grid
        clear_last = False

        # Delete colors unless we are at the final color
        for idx in indices:
            if len(self.colors) <= 1:
                QtW.QMessageBox.warning(
                    self, "Palette Size Restriction", "Palette must have at least 1 color."
                )
                clear_last = True
                break
            self.colors.pop(idx)

        # If all colors were deleted, leave behind a single black color
        if clear_last:
            self.colors = [QCOL_BLACK]

        # Rebuild starting from the lowest (earliest) index
        rebuild_start = 0 if clear_last else lowest
        self.palette_rebuild_grid(rebuild_start)

        # Prevent out-of-bounds crashes by clamping to the new palette length
        safe_index = min(rebuild_start, len(self.colors) - 1)

        # Adjust selection index
        self.selected_indices = [safe_index]
        self.active_index = safe_index
        self.palette_refresh_highlighting()

        self.update_unsaved_changes()

    def edit_swap_colors(self, src_indices, target_start):
        if not src_indices:
            return

        self.history_push_state()  # Record state before swapping

        # Prevent swapping out of bounds
        count = len(src_indices)
        if target_start + count > len(self.colors):
            target_start = len(self.colors) - count

        # Single-item swap shortcut
        if count == 1:
            src_idx = src_indices[0]
            dst_idx = target_start
            self.colors[src_idx], self.colors[dst_idx] = (
                self.colors[dst_idx], self.colors[src_idx])
            self.boxes[src_idx].set_color(self.colors[src_idx])
            self.boxes[dst_idx].set_color(self.colors[dst_idx])
            self.active_index = dst_idx
            self.selected_indices = [dst_idx]
        else:
            # Multi-item contiguous swap
            dst_indices = list(range(target_start, target_start + count))

            # Extract source and target color blocks
            src_colors = [QColor(self.colors[_i]) for _i in src_indices]
            dst_colors = [QColor(self.colors[_i]) for _i in dst_indices]

            # Exchange block colors
            for _i, idx in enumerate(src_indices):
                self.colors[idx] = dst_colors[_i]
                self.boxes[idx].set_color(dst_colors[_i])

            for _i, idx in enumerate(dst_indices):
                self.colors[idx] = src_colors[_i]
                self.boxes[idx].set_color(src_colors[_i])

            # Set highlighted selection to the destination
            self.active_index = target_start
            self.selected_indices = dst_indices

        self.palette_refresh_highlighting()
        self.update_unsaved_changes()

        # Emit signal for open dialogs (Resizing shouldn't occur here though)
        self.palette_changed.emit()


    # --------------------------------------------------
    # Batch Color Editing Functions
    # --------------------------------------------------
    def batch_shift_color(self, direction, channel=None):
        def shift_color(color):
            if channel in (None, "r"):
                _r = snap_to_md_color(color.red())
                _r = max(0, min(7, _r + direction))
                color.setRed(MDCOLOR_VALUES[_r])

            if channel in (None, "g"):
                _g = snap_to_md_color(color.green())
                _g = max(0, min(7, _g + direction))
                color.setGreen(MDCOLOR_VALUES[_g])

            if channel in (None, "b"):
                _b = snap_to_md_color(color.blue())
                _b = max(0, min(7, _b + direction))
                color.setBlue(MDCOLOR_VALUES[_b])

        # Run the above function for the whole batch (Remembering channel and direction)
        self.batch_apply_edit(shift_color)

    def batch_invert_color(self, channel=None):
        def invert_color(color):
            # Reverse selected color channels (None = all)
            if channel in (None, 'r'):
                step = snap_to_md_color(color.red())
                color.setRed(MDCOLOR_VALUES[7 - step])

            if channel in (None, 'g'):
                step = snap_to_md_color(color.green())
                color.setGreen(MDCOLOR_VALUES[7 - step])

            if channel in (None, 'b'):
                step = snap_to_md_color(color.blue())
                color.setBlue(MDCOLOR_VALUES[7 - step])

        # Run the above function for the whole batch (Remembering channel)
        self.batch_apply_edit(invert_color)

    def batch_clear_color(self, channel=None):
        def clear_color(color):
            # Clear selected color channels (None = all)
            if channel in (None, 'r'):
                color.setRed(0)

            if channel in (None, 'g'):
                color.setGreen(0)

            if channel in (None, 'b'):
                color.setBlue(0)

        # Run the above function for the whole batch (Remembering channel)
        self.batch_apply_edit(clear_color)

    def batch_target_scope(self):
        if self.opt_mass_all.isChecked():
            return range(len(self.colors))
        return tuple(self.selected_indices)

    def batch_apply_edit(self, edit_color):
        target_indices = self.batch_target_scope()

        if not target_indices:
            return

        changes = []    # Buffer palette

        for _i in target_indices:
            original_color = self.colors[_i]
            new_color = QColor(original_color)

            # Call invert, clear, or +/- adjust here
            edit_color(new_color)

            if new_color != original_color:
                changes.append((_i, new_color))

        # Stop if nothing changed
        if not changes:
            return

        self.history_push_state()  # Record state before applying changes

        # Modify only what's actually changed
        for idx, new_color in changes:
            self.colors[idx] = new_color
            self.boxes[idx].set_color(new_color)

        self.palette_refresh_highlighting()
        self.update_unsaved_changes()


    # --------------------------------------------------
    # Advanced Color Editing Functions
    # --------------------------------------------------
    def adv_check_dialog(self):
        # If an advanced dialog is open, bring it to focus
        if self.active_advanced_dialog is not None and self.active_advanced_dialog.isVisible():
            self.active_advanced_dialog.raise_()
            self.active_advanced_dialog.activateWindow()
            return True
        return False

    def adv_open_dialog(self, dialog_class, signal_name=None, callback=None):
        # Focus the existing dialog instead of opening another (to prevent duplication)
        if self.adv_check_dialog():
            return

        # Opens new window
        dialog = dialog_class(self)

        # Set up callback command (Applies to all but adv_extract_palette)
        if signal_name is not None:
            getattr(dialog, signal_name).connect(callback)

        # Keep a reference for the duplication check at the start
        self.active_advanced_dialog = dialog
        dialog.show()

    def adv_blend_colors(self):
        self.adv_open_dialog(ColorBlendDialog, "colors_applied", self.adv_apply_effect)

    def adv_greyscale_colors(self):
        self.adv_open_dialog(GreyscaleDialog, "colors_applied", self.adv_apply_effect)

    def adv_build_gradient(self):
        self.adv_open_dialog(GradientBuilderDialog, "gradient_applied", self.adv_apply_gradient)

    def adv_extract_palette(self):
        self.adv_open_dialog(PaletteExtractDialog)

    def adv_apply_effect(self, new_colors):
        # Effect is only applied if the user selects "Apply"
        self.history_push_state()  # Record state before applying chosen color
        self.colors = new_colors
        self.palette_rebuild_grid()
        self.palette_refresh_highlighting()
        self.update_unsaved_changes()

    def adv_apply_gradient(self, gradient_colors):
        # Effect is only applied if the user selects "Apply"
        self.history_push_state()  # Record state before applying gradient
        start = self.active_index

        # Inject gradient colors, expanding palette up to the limit if necessary
        for i, color in enumerate(gradient_colors):
            idx = start + i
            if idx < len(self.colors):
                self.colors[idx] = color
            elif idx < PALEDIT_MAXCOLORS:
                self.colors.append(color)
            else:
                break

        self.palette_rebuild_grid(start)

        # Mass select the newly placed gradient colors to visually confirm placement
        end = min(start + len(gradient_colors), len(self.colors))
        self.selected_indices = list(range(start, end))
        self.active_index = start

        self.palette_refresh_highlighting()
        self.update_unsaved_changes()


    # --------------------------------------------------
    # Clipboard Functionality
    # --------------------------------------------------
    def clipboard_copy(self, cut=False):
        if not self.selected_indices:
            return

        # Sort colors to keep them in visual order when pasting
        sorted_indices = sorted(self.selected_indices)
        self.clip_colors = [QColor(self.colors[idx]) for idx in sorted_indices]
        self.clipboard_refresh()

        # If only Copying, stop here. Otherwise, remove copied colors
        if cut:
            # Delete in reverse order to avoid issues with index shifting
            sorted_indices.reverse()
            # Unsaved flag and undo state recording handled here
            self.edit_remove_colors(sorted_indices)

    def clipboard_paste(self, mode, target_index):
        if not self.clip_colors:
            return

        clipboard_length = len(self.clip_colors)

        # Determine where to paste and how many colors will fit.
        if mode == "over":
            # Capacity depends on the starting index because slots get overwritten
            start = target_index
            available = max(0, PALEDIT_MAXCOLORS - start)
        else:
            # Capacity depends on the current palette length because pasted colors adds new slots
            start = target_index if mode == "before" else target_index + 1
            available = max(0, PALEDIT_MAXCOLORS - len(self.colors))

        # Final number of colors to paste
        pasted_count = min(clipboard_length, available)

        # If nothing changes, don't record state or change selection
        if pasted_count == 0:
            return

        elif pasted_count < clipboard_length:
            QtW.QMessageBox.warning(
                self,"Palette Size Restriction",
                f"Only {pasted_count} of {clipboard_length} clipboard "
                "colors can be pasted without exceeding the color limit."
            )

        self.history_push_state()  # Record state before pasting colors

        # Isolate actual colors that will be pasted (if not all)
        colors_to_paste = self.clip_colors[:pasted_count]

        # Overwrite existing slots, extending the palette if needed
        if mode == "over":
            for _i, color in enumerate(colors_to_paste):
                idx = start + _i

                if idx < len(self.colors):
                    self.colors[idx] = QColor(color)
                else:
                    self.colors.append(QColor(color))

        # Paste before or after the current index, shifting colors accordingly
        else:
            for _i, color in enumerate(colors_to_paste):
                self.colors.insert(start + _i, QColor(color))

        # Select pasted colors
        end = start + pasted_count
        self.active_index = start
        self.selected_indices = list(range(start, end))

        # Refresh palette
        self.palette_rebuild_grid(start)
        self.palette_refresh_highlighting()
        self.update_unsaved_changes()

    def clipboard_clear(self):
        self.clip_colors.clear()
        self.clipboard_refresh()

    def clipboard_refresh(self):
        # Update clipboard header
        count = len(self.clip_colors)
        color_text = "color" if count == 1 else "colors"

        self.btn_toggle_clipboard.setText(f"Clipboard: {count} {color_text}")
        self.btn_clear_clipboard.setEnabled(count > 0)

        # Clear clipboard boxes
        for box in self.clip_boxes:
            box.deleteLater()
        self.clip_boxes.clear()

        if self.clipboard_empty_label:
            self.clipboard_empty_label.deleteLater()
            self.clipboard_empty_label = None

        # Display placeholder text when empty (To-Do: Add style to QSS)
        if not self.clip_colors:
            self.clipboard_empty_label = create_label("Clipboard is empty (Right-click grid colors to Copy or Cut)")
            self.clipboard_empty_label.setStyleSheet("color: #777777; font-style: italic;")
            self.clipboard_grid_layout.addWidget(self.clipboard_empty_label, 0, 0)
            return

        # Render copied swatches
        MAX_COLUMNS = 16
        for idx, color in enumerate(self.clip_colors):
            row, col = idx // MAX_COLUMNS, idx % MAX_COLUMNS

            box = QtW.QFrame()
            box.setFixedSize(28, 28)
            box.setToolTip(f"Clipboard #{idx}: {color.name().upper()}")
            box.setStyleSheet(f"""
                QFrame {{
                    background-color: {color.name()};
                    border: 1px solid #555555;
                }}
            """)
            self.clipboard_grid_layout.addWidget(box, row, col)
            self.clip_boxes.append(box)

    def clipboard_toggle(self, expanded):
        # Collapse handler
        if expanded:
            # Allow the clipboard panel to grow again
            self.clipboard_group.setMinimumHeight(0)
            self.clipboard_group.setMaximumHeight(16777215)
            self.clipboard_scroll.show()
            self.clipboard_group.layout().activate()

            self.btn_toggle_clipboard.setArrowType(Qt.ArrowType.DownArrow)

            # Restore the divider position from before collapsing
            if self.clipboard_splitter_sizes is not None:
                self.palette_splitter.setSizes(self.clipboard_splitter_sizes)

        else:
            # Remember the user's divider position
            self.clipboard_splitter_sizes = self.palette_splitter.sizes()

            self.clipboard_scroll.hide()
            self.btn_toggle_clipboard.setArrowType(Qt.ArrowType.RightArrow)

            # Shrink the panel to its header
            self.clipboard_group.layout().activate()
            self.clipboard_group.setFixedHeight(self.clipboard_group.sizeHint().height())


    # --------------------------------------------------
    # Undo/Redo History
    # --------------------------------------------------
    def history_undo(self):
        if not self.undo_stack:
            return

        # Push palette state to redo stack
        self.redo_stack.append([QColor(c) for c in self.colors])

        # Restore previous state and validate selection
        self.colors = self.undo_stack.pop()
        self.palette_check_selection()

        # Refresh palette
        self.palette_rebuild_grid()
        self.palette_refresh_highlighting()
        self.history_update()
        self.update_unsaved_changes()

    def history_redo(self):
        if not self.redo_stack:
            return

        # Push palette state to undo stack
        self.undo_stack.append([QColor(c) for c in self.colors])

        # Restore next state and validate selection
        self.colors = self.redo_stack.pop()
        self.palette_check_selection()

        self.palette_rebuild_grid()
        self.palette_refresh_highlighting()
        self.history_update()
        self.update_unsaved_changes()

    def history_push_state(self):
        # Snapshot current palette colors
        state = [QColor(c) for c in self.colors]
        self.undo_stack.append(state)
        if len(self.undo_stack) > self.max_history:
            self.undo_stack.pop(0)

        # Clear redo stack when we have something new to undo
        self.redo_stack.clear()
        self.history_update()

    def history_update(self):
        btn_undo = self.btn_edit_group.button(EDIT_UNDO)
        btn_redo = self.btn_edit_group.button(EDIT_REDO)

        if btn_undo:
            btn_undo.setEnabled(bool(self.undo_stack))
        if btn_redo:
            btn_redo.setEnabled(bool(self.redo_stack))

    def history_clear(self):
        self.undo_stack.clear()
        self.redo_stack.clear()
        self.history_update()
