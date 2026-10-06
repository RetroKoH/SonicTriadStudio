"""Tilemap Editor UI skeleton.

Based on the Sprite Editor's UI: palette preview and file manager.
The left panel's canvas is an 8x8-tile painter. The right panel contains
only the palette preview, art tile viewer and tile data controls.
File operations, rendering, tile selection and painting are not wired.
Editing controls are disabled; the splitter and collapsible file tabs work.
"""

import PyQt6.QtWidgets as QtW
from PyQt6.QtCore import Qt

from UI.collapse_panel import CollapsiblePanel
from UI.file_toolbar import create_file_toolbar
from UI.widgets import (
    create_combobox,
    create_label,
    create_pushbutton,
    create_scrollarea,
    create_splitter,
    create_spinbox,
)


class TilemapEditor(QtW.QWidget):
    def __init__(self, project=None):
        super().__init__()
        self.project = project
        self.palette_boxes = []

        # Placeholder canvas dimensions in tiles; each tile is 8x8 pixels.
        self.tilemap_width = 40
        self.tilemap_height = 28
        self.tilemap_zoom = 2

        # "Dirty flag" - Cleared if current state matches last saved state
        self._unsaved_changes = False

        # ui_init()
        self.content_splitter = None

        # ui_build_file_toolbar()
        self.tilemap_dropdown = create_combobox(
            tooltip="Select a tilemap from the active project")
        self.unsaved_label = create_label("Unsaved Changes")

        self.ui_init()

    # --------------------------------------------------
    # UI Setup
    # --------------------------------------------------
    def ui_init(self):
        """Build the tile painter/file panel and the art placement panel."""
        layout = QtW.QVBoxLayout(self)

        # TOP PANEL TOOLBAR
        toolbar = create_file_toolbar(self.tilemap_dropdown, self.unsaved_label,
            resource_name="tilemap", unsaved_changes=self._unsaved_changes,
            on_new=None, on_load=None,
            on_save=None, on_save_as=None,
            on_remove=None)
        layout.addLayout(toolbar)

        tilemap_panel = self.ui_build_tilemap_panel()   # LEFT PANEL: Tilemap View and File Manager
        editing_panel = self.ui_build_editing_panel()   # RIGHT PANEL: Editing Controls

        # Horizontal splitter between the sprite viewer and editor
        self.content_splitter = create_splitter(
            (tilemap_panel, editing_panel),
            orientation=Qt.Orientation.Horizontal,
            stretch_factors=(1, 1), sizes=(664, 336))
        layout.addWidget(self.content_splitter, stretch=1)

        self.btn_toggle_filemanager.setChecked(False)

        # Keep UI navigation active; all editing actions are placeholders.
        for widget_type in (QtW.QPushButton, QtW.QComboBox, QtW.QSpinBox,
                QtW.QLineEdit, QtW.QCheckBox):
            for widget in self.findChildren(widget_type):
                if widget is not self.btn_toggle_filemanager:
                    widget.setEnabled(False)
        for table in (self.art_file_table, self.map_file_table, self.pal_file_table):
            table.setEditTriggers(QtW.QAbstractItemView.EditTrigger.NoEditTriggers)

    def ui_build_tilemap_panel(self):
        panel = QtW.QWidget()
        layout = QtW.QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.ui_build_tilemap_viewer(), stretch=2)
        layout.addWidget(self.ui_build_file_manager(), stretch=1)
        return panel

    def ui_build_tilemap_viewer(self):
        box = QtW.QGroupBox("Tilemap Editor")
        layout = QtW.QVBoxLayout(box)

        edit_toolbar = QtW.QHBoxLayout()
        edit_toolbar.setSpacing(4)

        btn_undo = create_pushbutton("Undo", tooltip="Undo the last change made",
            width=55, layout=edit_toolbar)
        btn_redo = create_pushbutton("Redo", tooltip="Redo the last undone change",
            width=55, layout=edit_toolbar)
        btn_copy = create_pushbutton("Copy", tooltip="Copy selected tile cells to the clipboard",
            width=55, layout=edit_toolbar)
        btn_paste = create_pushbutton("Paste", tooltip="Paste over the selected cell(s)",
            width=55, layout=edit_toolbar)
        btn_clear = create_pushbutton("Clear", tooltip="Clear selected cells to tile 0",
            width=55, layout=edit_toolbar)

        create_pushbutton("Resize Tilemap", tooltip="Resize the tilemap", width=85, layout=edit_toolbar)

        edit_toolbar.addStretch()
        layout.addLayout(edit_toolbar)

        canvas_row = QtW.QHBoxLayout()

        # Keep the Sprite Editor's scrollable label structure for now.
        # Drawing will render tilemap cells here, not sprite pieces.
        self.tilemap_label = QtW.QLabel("Tilemap Grid")
        self.tilemap_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.tilemap_label.setMargin(0)
        self.tilemap_label.setFrameShape(QtW.QFrame.Shape.NoFrame)
        self.tilemap_label.setFixedSize(
            self.tilemap_width * 8 * self.tilemap_zoom,
            self.tilemap_height * 8 * self.tilemap_zoom)
        self.tilemap_scroll = create_scrollarea(self.tilemap_label, resizable=False)
        self.tilemap_scroll.setAlignment(Qt.AlignmentFlag.AlignCenter)
        canvas_row.addWidget(self.tilemap_scroll, stretch=1)
        layout.addLayout(canvas_row, stretch=1)
        return box

    def ui_build_file_manager(self):
        self.tilemap_file_group = CollapsiblePanel(
            "Tilemap Data and Files", tooltip="Expand or collapse the file manager")
        self.btn_toggle_filemanager = self.tilemap_file_group.toggle_button
        header = self.tilemap_file_group.header_layout
        create_label("VRAM Address:", layout=header)
        self.vram_spinbox = create_spinbox(
            minimum=0, maximum=2047, display_base=16, prefix="$", width=60,
            tooltip="Base VRAM tile index", layout=header)

        # These are file-management tabs, separate from the tab-free right panel.
        self.filemanager_tabs = QtW.QTabWidget()
        self.filemanager_tabs.addTab(self.ui_build_tilemap_tab(), "Tilemap")
        self.filemanager_tabs.addTab(self.ui_build_art_tab(), "Art")
        self.filemanager_tabs.addTab(self.ui_build_palettes_tab(), "Palettes")
        self.tilemap_file_group.content_layout.addWidget(self.filemanager_tabs)
        return self.tilemap_file_group

    def ui_build_tilemap_tab(self):
        tab = QtW.QWidget()
        layout = QtW.QVBoxLayout(tab)

        # File toolbar
        toolbar = QtW.QHBoxLayout()
        toolbar.setSpacing(4)
        toolbar.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)

        # File actions remain disabled placeholders
        self.btn_map_add = create_pushbutton("Add", tooltip="Add tilemap",
            width=50, layout=toolbar)
        self.btn_map_load = create_pushbutton("Load", tooltip="Load added tilemap",
            width=50, enabled=False, layout=toolbar)
        self.btn_map_save = create_pushbutton("Save", tooltip="Save tilemap data",
            width=50, enabled=False, layout=toolbar)
        self.btn_map_remove = create_pushbutton("Remove", tooltip="Remove the tilemap entry",
            width=50, enabled=False, layout=toolbar)

        layout.addLayout(toolbar)

        # Tilemap data has no sprite frame labels or DPLC rows.
        self.map_file_table = QtW.QTableWidget(0, 3)
        table = self.map_file_table
        table.setHorizontalHeaderLabels(["File", "Compression", "Size (tiles)"])
        table.setSelectionBehavior(QtW.QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QtW.QAbstractItemView.SelectionMode.SingleSelection)
        table.setSortingEnabled(False)
        table.verticalHeader().setDefaultSectionSize(20)
        table.verticalHeader().setSectionResizeMode(QtW.QHeaderView.ResizeMode.Fixed)
        table.horizontalHeader().setSectionResizeMode(0, QtW.QHeaderView.ResizeMode.Stretch)
        table.setColumnWidth(1, 120)
        table.setColumnWidth(2, 110)
        layout.addWidget(table, stretch=1)
        return tab

    def ui_build_art_tab(self):
        tab = QtW.QWidget()
        layout = QtW.QVBoxLayout(tab)

        # File toolbar
        toolbar = QtW.QHBoxLayout()
        toolbar.setSpacing(4)
        toolbar.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)

        # File actions remain disabled placeholders
        self.btn_art_add = create_pushbutton("Add", tooltip="Add art tiles",
            width=50, layout=toolbar)
        self.btn_art_load = create_pushbutton("Load", tooltip="Load added art tiles",
            width=50, enabled=False, layout=toolbar)
        self.btn_art_save = create_pushbutton("Save", tooltip="Save art tile data",
            width=50, enabled=False, layout=toolbar)
        self.btn_art_remove = create_pushbutton("Remove", tooltip="Remove the selected art tile entry",
            width=50, enabled=False, layout=toolbar)

        layout.addLayout(toolbar)

        # Table: initially zero rows, four columns
        self.art_file_table = QtW.QTableWidget(0, 4)
        table = self.art_file_table

        table.setHorizontalHeaderLabels(["File", "Compression", "VRAM location", "Tile count"])

        table.setSelectionBehavior(QtW.QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QtW.QAbstractItemView.SelectionMode.SingleSelection)
        table.setSortingEnabled(False)

        header = table.verticalHeader()
        header.setDefaultSectionSize(20)
        header.setSectionResizeMode(QtW.QHeaderView.ResizeMode.Fixed)

        # Let the filename column take the remaining space
        header = table.horizontalHeader()
        header.setSectionResizeMode(0, QtW.QHeaderView.ResizeMode.Stretch)
        table.setColumnWidth(1, 120)
        table.setColumnWidth(2, 110)
        table.setColumnWidth(3, 90)

        layout.addWidget(table, stretch=1)

        return tab

    def ui_build_palettes_tab(self):
        tab = QtW.QWidget()
        layout = QtW.QVBoxLayout(tab)

        # File buttons
        toolbar = QtW.QHBoxLayout()
        toolbar.setSpacing(4)
        toolbar.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)

        self.btn_pal_add = create_pushbutton("Add", tooltip="Add color palettes",
            width=50, layout=toolbar)
        self.btn_pal_load = create_pushbutton("Load", tooltip="Load added palettes",
            width=50, enabled=False, layout=toolbar)
        self.btn_pal_save = create_pushbutton("Save", tooltip="Save palette data",
            width=50, enabled=False, layout=toolbar)
        self.btn_pal_remove = create_pushbutton("Remove", tooltip="Remove the selected palette entry",
            width=50, enabled=False, layout=toolbar)

        layout.addLayout(toolbar)

        # Table: initially zero rows, two columns
        self.pal_file_table = QtW.QTableWidget(0, 2)
        table = self.pal_file_table

        table.setHorizontalHeaderLabels(["File", "Lines"])

        table.setSelectionBehavior(QtW.QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QtW.QAbstractItemView.SelectionMode.SingleSelection)
        table.setSortingEnabled(False)

        header = table.verticalHeader()
        header.setDefaultSectionSize(20)
        header.setSectionResizeMode(QtW.QHeaderView.ResizeMode.Fixed)
        header.setSectionsMovable(False)

        # Let the filename column take the remaining space
        header = table.horizontalHeader()
        header.setSectionResizeMode(0, QtW.QHeaderView.ResizeMode.Stretch)
        table.setColumnWidth(1, 75)
        table.verticalHeader().setDefaultSectionSize(30)

        layout.addWidget(table, stretch=1)

        return tab

    def ui_build_editing_panel(self):
        panel = QtW.QWidget()
        layout = QtW.QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.ui_build_palette_preview())
        layout.addWidget(self.ui_build_art_viewer(), stretch=1)
        return panel

    def ui_build_palette_preview(self):
        tilemap_palette_group = QtW.QGroupBox("Palette")
        tilemap_palette_layout = QtW.QVBoxLayout(tilemap_palette_group)

        # 64-Color VDP Palette Grid (4 Lines x 16 Swatches)
        pal_grid_container = QtW.QWidget()
        pal_grid_layout = QtW.QGridLayout(pal_grid_container)
        pal_grid_layout.setSpacing(0)
        pal_grid_layout.setContentsMargins(0, 0, 0, 0)
        pal_grid_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)

        for _i in range(64):
            row = _i // 16
            col = _i % 16
            # No palette-editor dependency or click handler
            box = QtW.QFrame()
            box.setFixedSize(16, 16)
            box.setStyleSheet("background-color: black; border: 1px solid #444;")
            box.setToolTip(f"Palette line {row}, color {col}")
            pal_grid_layout.addWidget(box, row, col)
            self.palette_boxes.append(box)

        tilemap_palette_layout.addWidget(pal_grid_container,
            alignment=Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        tilemap_palette_layout.addStretch()

        return tilemap_palette_group

    def ui_build_art_viewer(self):
        self.vram_box = QtW.QGroupBox("Art Tiles")
        layout = QtW.QVBoxLayout(self.vram_box)

        # Preview palette only changes how the art browser displays tiles.
        preview_row = QtW.QHBoxLayout()
        create_label("Preview Palette Line:", layout=preview_row)
        self.viewer_line_combo = create_combobox(
            items=["Line 0", "Line 1", "Line 2", "Line 3"],
            tooltip="Palette line used to preview art tiles", layout=preview_row)
        preview_row.addStretch()
        layout.addLayout(preview_row)

        self.vram_label = QtW.QLabel("Art tile preview")
        self.vram_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.vram_label.setMinimumSize(256, 192)
        self.vram_scroll = create_scrollarea(self.vram_label)
        self.vram_scroll.setAlignment(Qt.AlignmentFlag.AlignRight)
        layout.addWidget(self.vram_scroll, stretch=1)
        self.art_selection_label = create_label("Tile —  ·  0 tiles", layout=layout)

        # Attributes to apply when placing a tile in the tilemap.
        placement_box = QtW.QGroupBox("Placement")
        placement_layout = QtW.QVBoxLayout(placement_box)
        palette_row = QtW.QHBoxLayout()
        create_label("Palette:", layout=palette_row)
        self.placement_palette_combo = create_combobox(
            items=["Line 0", "Line 1", "Line 2", "Line 3"],
            tooltip="Palette line assigned to placed tiles", layout=palette_row)
        palette_row.addStretch()
        placement_layout.addLayout(palette_row)

        flags_row = QtW.QHBoxLayout()
        self.placement_xflip_checkbox = QtW.QCheckBox("Flip H")
        self.placement_yflip_checkbox = QtW.QCheckBox("Flip V")
        self.placement_priority_checkbox = QtW.QCheckBox("Priority")
        flags_row.addWidget(self.placement_xflip_checkbox)
        flags_row.addWidget(self.placement_yflip_checkbox)
        flags_row.addWidget(self.placement_priority_checkbox)
        flags_row.addStretch()
        placement_layout.addLayout(flags_row)
        layout.addWidget(placement_box)
        return self.vram_box
