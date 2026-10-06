"""Sprite Editor UI skeleton.

Preserves the Sprite Editor layout and the application's UI factories.
File operations, project integration, sprite rendering, palette editing and
mapping edits are not wired. Editing controls are disabled placeholders;
tabs, splitters, the collapsible file panel and DPLC row visibility still work.
"""

import PyQt6.QtWidgets as QtW
from PyQt6.QtCore import Qt, QSize

from UI.collapse_panel import CollapsiblePanel
from UI.file_toolbar import create_file_toolbar
from UI.widgets import (
    create_combobox,
    create_label,
    create_lineedit,
    create_pushbutton,
    create_scrollarea,
    create_splitter,
    create_spinbox,
)

class SpriteEditor(QtW.QWidget):
    def __init__(self, project=None):
        super().__init__()
        self.project = project
        self.palette_boxes = []
        self.sprite_canvas_width = 256
        self.sprite_canvas_height = 256
        self.sprite_zoom = 2

        # "Dirty flag" - Cleared if current state matches last saved state
        self._unsaved_changes = False

        # UI Widget handlers
        # ui_init()
        self.content_splitter = None

        # ui_build_file_toolbar()
        self.spr_dropdown = create_combobox(
            tooltip="Select a sprite build from the active project")
        self.unsaved_label = create_label("Unsaved Changes")

        # ui_build_frame_viewer()
        self.sprite_label = QtW.QLabel("Sprite preview")

        # ui_build_file_manager()
        self.spr_file_group = CollapsiblePanel("Sprite Data and Files",
            tooltip="Expand or collapse the file manager")
        self.btn_toggle_filemanager = self.spr_file_group.toggle_button
        self.vram_spinbox = create_spinbox(minimum=0, maximum=2047,
            display_base=16, prefix="$", width=50, tooltip="Starting VRAM Tile Index (Hex)")
        self.sprpal_spinbox = create_spinbox(minimum=0, maximum=3, width=40, tooltip="Base Palette Line")
        self.btn_clear_spritedata = create_pushbutton("Clear Data", tooltip="Clear the current sprite data")
        self.filemanager_tabs = QtW.QTabWidget()

        # ui_build_art_tab()
        self.btn_art_add = create_pushbutton("Add", tooltip="Add art tiles", width=50)
        self.btn_art_load = create_pushbutton("Load", tooltip="Load added art tiles", width=50, enabled=False)
        self.btn_art_save = create_pushbutton("Save", tooltip="Save art tile data", width=50, enabled=False)
        self.btn_art_remove = create_pushbutton("Remove", tooltip="Remove the selected art tile entry",
            width=50, enabled=False)
        self.art_file_table = QtW.QTableWidget(0, 4)

        # ui_build_mappings_tab()
        self.btn_map_add = create_pushbutton("Add", tooltip="Add sprite mappings", width=50)
        self.btn_map_load = create_pushbutton("Load", tooltip="Load added mappings", width=50, enabled=False)
        self.btn_map_save = create_pushbutton("Save", tooltip="Save mappings data", width=50, enabled=False)
        self.btn_map_remove = create_pushbutton("Remove", tooltip="Remove mappings data", width=50, enabled=False)
        self.map_dropdown = QtW.QComboBox()
        self.macro_cb = QtW.QCheckBox("Save with Macros")
        self.dplc_cb = QtW.QCheckBox("Use DPLCs")
        self.map_file_table = QtW.QTableWidget(2, 3)
        self.map_path_input = QtW.QLineEdit()
        self.map_name_input = QtW.QLineEdit()
        self.dplc_path_input = QtW.QLineEdit()
        self.dplc_name_input = QtW.QLineEdit()

        # ui_build_palettes_tab()
        self.btn_pal_add = create_pushbutton("Add", tooltip="Add color palettes", width=50)
        self.btn_pal_load = create_pushbutton("Load", tooltip="Load added palettes", width=50, enabled=False)
        self.btn_pal_save = create_pushbutton("Save", tooltip="Save palette data", width=50, enabled=False)
        self.btn_pal_remove = create_pushbutton("Remove", tooltip="Remove the selected palette entry",
            width=50, enabled=False)
        self.pal_file_table = QtW.QTableWidget(0, 2)

        # ui_build_editing_panel()
        self.editing_tabs = QtW.QTabWidget()

        # ui_build_art_viewer()
        self.vram_box = QtW.QGroupBox()
        self.viewer_line_combo = create_combobox(
            tooltip="Choose a palette line to view art tiles with",
            items=["Line 0", "Line 1", "Line 2", "Line 3"])
        self.vram_label = QtW.QLabel("Art tile preview")
        self.vram_scroll = create_scrollarea(self.vram_label)
        self.arrange_tiles = create_pushbutton("Arrange Tiles",
            width=90, tooltip="Arrange tiles by sprite usage", enabled=False)
        self.strip_tiles = create_pushbutton("Strip Unused Tiles",
            width=110, tooltip="Remove all unused tiles", enabled=False)

        # ui_build_sprite_viewer()
        self.sprite_frame_list = QtW.QListWidget()

        # ui_build_map_editor()
        self.map_edit_box = QtW.QGroupBox()
        self.frame_spinbox = create_spinbox(minimum=0, maximum=0)
        self.frame_name_input = create_lineedit(tooltip="Name of the mapping frame (in ASM files)")
        self.btn_frame_add = create_pushbutton("Add Frame", tooltip="Add a frame", enabled=False)
        self.btn_frame_remove = create_pushbutton("Remove Frame", width=85, tooltip="Remove the current frame",
            enabled=False)
        self.btn_frame_copy = create_pushbutton("Copy Frame", width=85,
            tooltip="Duplicate the current mapping frame", enabled=False)
        self.btn_frame_clone = create_pushbutton("Clone Frame and Tiles", width=125,
            tooltip="Clone the current frame, and its tiles", enabled=False)
        self.btn_frame_erase = create_pushbutton("Erase Frame and Tiles", width=125,
            tooltip="Delete the current frame, and its tiles", enabled=False)
        self.btn_piece_add = create_pushbutton("Add Piece", tooltip="Add a piece to the current frame",
            enabled=False)
        self.btn_piece_remove = create_pushbutton("Remove Pieces", width=85,
            tooltip="Remove the selected pieces", enabled=False)
        self.index_label = create_label("Piece Properties", object_name="infoLabel")

        # ui_build_piece_list()
        self.piece_list_table = QtW.QTableWidget(0, 1)

        # ui_build_piece_controls()
        self.piece_x_spinbox = create_spinbox(minimum=-128, maximum=127, width=45, keyboard_tracking=False,
            tooltip="Horizontal position relative to the sprite origin")
        self.piece_y_spinbox = create_spinbox(minimum=-128, maximum=127, width=45, keyboard_tracking=False,
            tooltip="Vertical position relative to the sprite origin")
        self.piece_tile_spinbox = create_spinbox(minimum=0, maximum=2047, display_base=16, prefix="$",
            width=55, keyboard_tracking=False, tooltip="Tile index before adding the sprite's base VRAM index")
        self.piece_width_spinbox = create_spinbox(minimum=1, maximum=4, value=1, width=40, keyboard_tracking=False,
            tooltip="Piece Width (tiles)")
        self.piece_height_spinbox = create_spinbox(minimum=1, maximum=4, value=1, width=40, keyboard_tracking=False,
            tooltip="Piece Height (tiles)")
        self.piece_palette_spinbox = create_spinbox(minimum=0, maximum=3, width=40, keyboard_tracking=False,
            tooltip="Palette line before adding the sprite's base palette line")
        self.piece_x_flip_checkbox = QtW.QCheckBox("X-Flip")
        self.piece_y_flip_checkbox = QtW.QCheckBox("Y-Flip")
        self.piece_priority_checkbox = QtW.QCheckBox("Priority")
        # Group widgets by type
        self.piece_spinboxes = {
            "x": self.piece_x_spinbox,
            "y": self.piece_y_spinbox,
            "tile": self.piece_tile_spinbox,
            "width": self.piece_width_spinbox,
            "height": self.piece_height_spinbox,
            "palette": self.piece_palette_spinbox,
        }
        self.piece_checkboxes = {
            "priority": self.piece_priority_checkbox,
            "x_flip": self.piece_x_flip_checkbox,
            "y_flip": self.piece_y_flip_checkbox,
        }

        self.ui_init()

    # --------------------------------------------------
    # UI Setup
    # --------------------------------------------------
    def ui_init(self):
        """Top-level UI constructor"""
        layout = QtW.QVBoxLayout(self)

        # TOP PANEL TOOLBAR
        toolbar = create_file_toolbar(self.spr_dropdown, self.unsaved_label,
            resource_name="sprite build", unsaved_changes=self._unsaved_changes,
            on_new=None, on_load=None,
            on_save=None, on_save_as=None,
            on_remove=None)
        layout.addLayout(toolbar)

        sprite_panel = self.ui_build_sprite_panel()     # LEFT PANEL: Sprite View and File Manager
        editing_panel = self.ui_build_editing_panel()   # RIGHT PANEL: Editing Controls

        # Horizontal splitter between the sprite viewer and editor
        self.content_splitter = create_splitter((sprite_panel, editing_panel),
            orientation=Qt.Orientation.Horizontal, stretch_factors=(1, 1), sizes=(664, 336))
        layout.addWidget(self.content_splitter, stretch=1)

        # Close File Manager tray to start
        self.btn_toggle_filemanager.setChecked(False)

        # Disable everything for now
        for widget_type in (QtW.QPushButton, QtW.QComboBox, QtW.QSpinBox,
                            QtW.QLineEdit, QtW.QCheckBox):
            for widget in self.findChildren(widget_type):
                if widget not in (self.btn_toggle_filemanager, self.dplc_cb):
                    widget.setEnabled(False)
        for table in (self.art_file_table, self.map_file_table,
                      self.pal_file_table, self.piece_list_table):
            table.setEditTriggers(QtW.QAbstractItemView.EditTrigger.NoEditTriggers)

    def ui_build_sprite_panel(self):
        sprite_panel = QtW.QWidget()
        sprite_layout = QtW.QVBoxLayout(sprite_panel)
        sprite_layout.setContentsMargins(0, 0, 0, 0)

        sprite_layout.addWidget(self.ui_build_frame_viewer(), stretch=2)
        sprite_layout.addWidget(self.ui_build_file_manager(), stretch=1)
        return sprite_panel

    def ui_build_frame_viewer(self):
        # Sprite Frame Viewer
        sprite_box = QtW.QGroupBox("Sprite Viewer")
        sprite_viewer = QtW.QVBoxLayout(sprite_box)

        # Scrollable Sprite Viewer
        self.sprite_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.sprite_label.setMargin(0)
        self.sprite_label.setFrameShape(QtW.QFrame.Shape.NoFrame)
        self.sprite_label.setFixedSize(
            self.sprite_canvas_width * self.sprite_zoom,
            self.sprite_canvas_height * self.sprite_zoom)

        scroll_area = create_scrollarea(
            self.sprite_label, resizable=False, layout=sprite_viewer)
        scroll_area.setAlignment(Qt.AlignmentFlag.AlignCenter)

        return sprite_box

    def ui_build_file_manager(self):
        # Sprite File Manager
        file_header_layout = self.spr_file_group.header_layout

        # The following items emulate an in-game object's art_tile OST
        # VRAM Address Selector
        file_header_layout.addWidget(QtW.QLabel("VRAM Address:"))
        file_header_layout.addWidget(self.vram_spinbox)

        # VRAM Base Palette Selector
        file_header_layout.addWidget(QtW.QLabel("Palette:"))
        file_header_layout.addWidget(self.sprpal_spinbox)

        # Clear sprite data button
        file_header_layout.addWidget(self.btn_clear_spritedata)

        # File-related elements here
        self.filemanager_tabs.addTab(self.ui_build_art_tab(), "Art")
        self.filemanager_tabs.addTab(self.ui_build_mappings_tab(), "Mappings")
        self.filemanager_tabs.addTab(self.ui_build_palettes_tab(), "Palettes")
        self.spr_file_group.content_layout.addWidget(self.filemanager_tabs)

        return self.spr_file_group

    def ui_build_art_tab(self):
        tab = QtW.QWidget()
        layout = QtW.QVBoxLayout(tab)

        # File toolbar
        toolbar = QtW.QHBoxLayout()
        toolbar.setSpacing(4)
        toolbar.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)

        # File actions remain disabled placeholders
        toolbar.addWidget(self.btn_art_add)
        toolbar.addWidget(self.btn_art_load)
        toolbar.addWidget(self.btn_art_save)
        toolbar.addWidget(self.btn_art_remove)

        layout.addLayout(toolbar)

        # Table: initially zero rows, four columns
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

    def ui_build_mappings_tab(self):
        tab = QtW.QWidget()
        layout = QtW.QVBoxLayout(tab)

        # File toolbar
        toolbar = QtW.QHBoxLayout()
        toolbar.setSpacing(4)
        toolbar.setAlignment(Qt.AlignmentFlag.AlignTop)

        # File actions remain disabled placeholders
        toolbar.addWidget(self.btn_map_add)
        toolbar.addWidget(self.btn_map_load)
        toolbar.addWidget(self.btn_map_save)
        toolbar.addWidget(self.btn_map_remove)

        toolbar.addStretch()

        # Options above the table
        toolbar.addWidget(QtW.QLabel("Format:"))

        # Map version dropdown (Add custom support)
        self.map_dropdown.addItems(["Sonic 1", "Sonic 2", "Sonic 3K"])
        toolbar.addWidget(self.map_dropdown)

        # MapMacro checkbox
        toolbar.addWidget(self.macro_cb)

        # DPLC checkbox
        toolbar.addWidget(self.dplc_cb)

        layout.addLayout(toolbar)

        # Table
        table = self.map_file_table

        table.setHorizontalHeaderLabels(["Type", "File", "Map Label"])

        table.setSelectionBehavior(QtW.QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QtW.QAbstractItemView.SelectionMode.SingleSelection)
        table.setSortingEnabled(False)

        header = table.verticalHeader()
        header.hide()
        header.setDefaultSectionSize(20)
        header.setSectionResizeMode(QtW.QHeaderView.ResizeMode.Fixed)

        # Let the filename column take space as the window resizes
        header = table.horizontalHeader()
        header.setSectionResizeMode(1, QtW.QHeaderView.ResizeMode.Stretch)
        table.setColumnWidth(0, 90)
        table.setColumnWidth(2, 110)

        # Fixed, non-editable type labels for column 0
        for row, name in enumerate(("Mappings", "DPLC")):
            item = QtW.QTableWidgetItem(name)
            item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            table.setItem(row, 0, item)

        # Row 0: Mapping file
        self.map_path_input.setPlaceholderText("Mapping Filepath...")
        table.setCellWidget(0, 1, self.map_path_input)

        self.map_name_input.setPlaceholderText("Map_")
        table.setCellWidget(0, 2, self.map_name_input)

        # Row 1: DPLC file
        self.dplc_path_input.setPlaceholderText("DPLC Filepath...")
        self.dplc_name_input.setPlaceholderText("DPLC_")

        dplc_file_widget = QtW.QWidget()
        dplc_file_layout = QtW.QHBoxLayout(dplc_file_widget)
        dplc_file_layout.setContentsMargins(0, 0, 0, 0)
        dplc_file_layout.setSpacing(2)

        btn_dplc_browse = QtW.QPushButton("...")
        btn_dplc_browse.setFixedWidth(30)

        dplc_file_layout.addWidget(self.dplc_path_input, stretch=1)
        dplc_file_layout.addWidget(btn_dplc_browse)

        table.setCellWidget(1, 1, dplc_file_widget)
        table.setCellWidget(1, 2, self.dplc_name_input)

        # Show the DPLC row only when enabled
        table.setRowHidden(1, True)
        self.dplc_cb.toggled.connect(lambda enabled: table.setRowHidden(1, not enabled))

        layout.addWidget(table, stretch=1)

        return tab

    def ui_build_palettes_tab(self):
        tab = QtW.QWidget()
        layout = QtW.QVBoxLayout(tab)

        # File toolbar
        toolbar = QtW.QHBoxLayout()
        toolbar.setSpacing(4)
        toolbar.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)

        # File actions remain disabled placeholders
        toolbar.addWidget(self.btn_pal_add)
        toolbar.addWidget(self.btn_pal_load)
        toolbar.addWidget(self.btn_pal_save)
        toolbar.addWidget(self.btn_pal_remove)

        layout.addLayout(toolbar)

        # Table: initially zero rows, two columns
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
        editing_panel = QtW.QWidget()
        editing_layout = QtW.QVBoxLayout(editing_panel)
        editing_layout.setContentsMargins(0, 0, 0, 0)

        # Palette stays above the three editing tabs
        editing_layout.addWidget(self.ui_build_palette_preview())

        # Editing tabs
        # Art: existing VRAM viewer and preview palette selector
        self.editing_tabs.addTab(self.ui_build_art_viewer(), "Art")

        # Sprites: placeholder list for compiled sprite frames
        self.editing_tabs.addTab(self.ui_build_sprite_viewer(), "Sprites")

        # Mappings: frame and piece control placeholders
        self.editing_tabs.addTab(self.ui_build_map_editor(), "Mapping Data")

        editing_layout.addWidget(self.editing_tabs, stretch=2)

        return editing_panel

    def ui_build_palette_preview(self):
        spr_palette_group = QtW.QGroupBox("Palette")
        spr_palette_layout = QtW.QVBoxLayout(spr_palette_group)

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

        spr_palette_layout.addWidget(pal_grid_container,
            alignment=Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        spr_palette_layout.addStretch()

        return spr_palette_group

    def ui_build_art_viewer(self):
        art_viewer_layout = QtW.QVBoxLayout(self.vram_box)

        # Active Palette Line Selector for the Viewer
        viewer_controls = QtW.QHBoxLayout()
        viewer_controls.addWidget(QtW.QLabel("Preview Palette Line:"))
        viewer_controls.addWidget(self.viewer_line_combo)
        viewer_controls.addStretch()
        art_viewer_layout.addLayout(viewer_controls)

        # Scrollable Canvas
        self.vram_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        art_viewer_layout.addWidget(self.vram_scroll)
        self.vram_scroll.setAlignment(Qt.AlignmentFlag.AlignRight)

        # Tileset modifying buttons
        tile_controls = QtW.QHBoxLayout()

        tile_controls.addWidget(self.arrange_tiles)
        tile_controls.addWidget(self.strip_tiles)

        tile_controls.addStretch()
        art_viewer_layout.addLayout(tile_controls)

        return self.vram_box

    def ui_build_sprite_viewer(self):
        # List of frame thumbnails
        frame_list = self.sprite_frame_list

        frame_list.setViewMode(QtW.QListView.ViewMode.IconMode)
        frame_list.setFlow(QtW.QListView.Flow.TopToBottom)
        frame_list.setWrapping(False)
        frame_list.setMovement(QtW.QListView.Movement.Static)
        frame_list.setResizeMode(QtW.QListView.ResizeMode.Adjust)

        # Thumbnail size
        frame_list.setIconSize(QSize(192, 192))
        frame_list.setGridSize(QSize(208, 224))
        frame_list.setUniformItemSizes(False)
        frame_list.setWordWrap(False)

        frame_list.setSelectionMode(QtW.QAbstractItemView.SelectionMode.SingleSelection)
        frame_list.setEditTriggers(QtW.QAbstractItemView.EditTrigger.NoEditTriggers)
        frame_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        frame_list.setTextElideMode(Qt.TextElideMode.ElideRight)

        frame_list.setSortingEnabled(False)
        frame_list.setDragDropMode(QtW.QAbstractItemView.DragDropMode.NoDragDrop)
        frame_list.setDragEnabled(False)
        frame_list.setAcceptDrops(False)

        return frame_list

    def ui_build_map_editor(self):
        map_editor = QtW.QVBoxLayout(self.map_edit_box)

        frame_controls = QtW.QHBoxLayout()

        # Frame selector
        frame_controls.addWidget(QtW.QLabel("Frame Index:"))
        frame_controls.addWidget(self.frame_spinbox)

        frame_controls.addStretch()

        # Frame name input
        frame_controls.addWidget(self.frame_name_input)
        self.frame_name_input.setEnabled(False)

        frame_controls.addStretch()
        map_editor.addLayout(frame_controls)

        frame_buttons = QtW.QHBoxLayout()
        frame_buttons.setSpacing(4)

        frame_buttons.addWidget(self.btn_frame_add)
        frame_buttons.addWidget(self.btn_frame_remove)
        frame_buttons.addWidget(self.btn_frame_copy)

        frame_buttons.addStretch()
        map_editor.addLayout(frame_buttons)

        frame_tile_buttons = QtW.QHBoxLayout()
        frame_tile_buttons.setSpacing(4)

        frame_tile_buttons.addWidget(self.btn_frame_clone)
        frame_tile_buttons.addWidget(self.btn_frame_erase)

        frame_tile_buttons.addStretch()
        map_editor.addLayout(frame_tile_buttons)

        piece_list = QtW.QHBoxLayout()
        piece_list.addWidget(self.ui_build_piece_list())
        map_editor.addLayout(piece_list)

        map_editor.addSpacing(8)

        piece_buttons = QtW.QHBoxLayout()
        piece_buttons.setSpacing(4)

        piece_buttons.addWidget(self.btn_piece_add)
        piece_buttons.addWidget(self.btn_piece_remove)

        piece_buttons.addStretch()
        map_editor.addLayout(piece_buttons)

        map_editor.addSpacing(8)

        piece_controls = QtW.QVBoxLayout()
        piece_controls.addWidget(self.index_label)
        piece_controls.addLayout(self.ui_build_piece_controls())
        map_editor.addLayout(piece_controls)

        map_editor.addStretch()

        return self.map_edit_box

    def ui_build_piece_list(self):
        table = self.piece_list_table

        table.setHorizontalHeaderLabels(["Piece List"])

        table.setSelectionBehavior(QtW.QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QtW.QAbstractItemView.SelectionMode.ExtendedSelection)
        table.setEditTriggers(QtW.QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setSortingEnabled(False)

        table.horizontalHeader().setDefaultAlignment(Qt.AlignmentFlag.AlignLeft)
        table.horizontalHeader().setSectionResizeMode(0, QtW.QHeaderView.ResizeMode.Stretch)

        table.verticalHeader().setSectionResizeMode(QtW.QHeaderView.ResizeMode.Fixed)
        table.verticalHeader().setDefaultSectionSize(26)

        # Starting dimensions
        table.setMinimumHeight(100)
        table.setMaximumHeight(100)

        return table

    def ui_build_piece_controls(self):
        piece_layout = QtW.QVBoxLayout()

        # Row 1: Position
        position_row = QtW.QHBoxLayout()
        position_row.addWidget(QtW.QLabel("X:"))
        position_row.addWidget(self.piece_x_spinbox)
        position_row.addStretch()
        position_row.addWidget(QtW.QLabel("Y:"))
        position_row.addWidget(self.piece_y_spinbox)
        position_row.addStretch()

        # Row 2: Size dimensions
        size_row = QtW.QHBoxLayout()
        size_row.addWidget(QtW.QLabel("Width:"))
        size_row.addWidget(self.piece_width_spinbox)
        size_row.addStretch()
        size_row.addWidget(QtW.QLabel("Height:"))
        size_row.addWidget(self.piece_height_spinbox)
        size_row.addStretch()

        # Row 3: Art Tile
        tile_row = QtW.QHBoxLayout()
        tile_row.addWidget(QtW.QLabel("Tile:"))
        tile_row.addWidget(self.piece_tile_spinbox)
        tile_row.addStretch()
        tile_row.addWidget(QtW.QLabel("Palette:"))
        tile_row.addWidget(self.piece_palette_spinbox)
        tile_row.addStretch()

        # Row 4: Flags
        flag_row = QtW.QHBoxLayout()
        flag_row.addWidget(self.piece_x_flip_checkbox)
        flag_row.addStretch()
        flag_row.addWidget(self.piece_y_flip_checkbox)
        flag_row.addStretch()
        flag_row.addWidget(self.piece_priority_checkbox)
        flag_row.addStretch()

        # Stack the rows
        piece_layout.addLayout(position_row)
        piece_layout.addLayout(size_row)
        piece_layout.addLayout(tile_row)
        piece_layout.addLayout(flag_row)

        return piece_layout
