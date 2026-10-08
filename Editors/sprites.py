"""Sprite Editor

File Manager and rendering with shared functions now working.
Thumbnails and editing tools are still under construction.
"""

from pathlib import Path
from copy import deepcopy

import PyQt6.QtWidgets as QtW
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QColor, QImage, QPainter, QPixmap

from constants import PALLINE_COLORS, PALETTE_MAXCOLORS, QCOL_BLACK
from AssetIO.art import decode_art, encode_art
from AssetIO.palettes import decode_palette, encode_palette
from AssetIO.mappings import *
from Rendering.tiles import render_tile_grid
from Rendering.sprites import SpriteRenderer
from UI.collapse_panel import CollapsiblePanel
from UI.color_box import MiniColorBox
from UI.file_toolbar import create_file_toolbar
from UI.md_color import ColorLibrary
from UI.widgets import (
    create_checkbox,
    create_combobox,
    create_label,
    create_lineedit,
    create_pushbutton,
    create_scrollarea,
    create_splitter,
    create_spinbox,
)

# Edit toolbar button IDs
EDIT_UNDO, EDIT_REDO = 0, 1

class SpriteEditor(QtW.QWidget):
    def __init__(self, project=None):
        super().__init__()
        self.project = project

        # Reusable rendering and piece caching live outside the editor
        self.renderer = SpriteRenderer()

        # File and Project paths
        self.active_sprite_build = None
        self.project_sprite_builds = {}

        # Dropdown selection index
        self._current_dropdown_index = -1

        # 64 color palette (4 palette lines) for sprite rendering
        self.palette_boxes = []
        self.palette_colors = [QCOL_BLACK for _i in range(64)]

        # These are used in the palette file manager
        self.pal_rows = []  # Stores (path_input, line_combo) for palette loading
        self.pal_line_combos = []

        # File layout associated with the current palette buffer
        # (None: buffer is not associated with any configured layout)
        self.palette_buffer_layout = None

        # Nonexistent destinations explicitly chosen through palette_entry_new()
        self.palette_new_paths = set()

        # VRAM art tile structure (Dynamic art_tile structures are loaded into this structure)
        # Individual art tile structures (Create dynamically for each row in self.art_rows)
        # That is done in art_add_entry
        self.vram_tiles = {}

        # Tells the sprite map list when sprite data changes
        self.art_preview_revision = 0

        # Used in the art file manager
        self.art_rows = []  # Stores row items in the table for art loading

        # Loaded file associated with each art row's path widget
        self.art_buffer_paths = {}

        # File associated with the initialized mapping buffer
        self.mapping_buffer_path = None

        # Stores the parsed mapping data in memory (Not loading DPLCs right now)
        self.map_frames = []

        # Frame labels (I'll work this into map_frames later)
        self.frame_labels = []

        # Sprite viewer canvas
        self.sprite_canvas_width = 256
        self.sprite_canvas_height = 256
        self.sprite_zoom = 2

        # Piece selection and dragging
        self.hovered_piece = None   # Hovered pieces will have transparency if not selected
        self.selected_pieces = set()
        self.piece_drag = None      # Remember where the mouse and piece were when dragging began
        self.selection_drag = None

        # State of mapping piece editor and list
        self.piece_controls_state = None
        self.piece_list_state = None

        # "Dirty flag" - Cleared if current state matches last saved state
        self._unsaved_changes = False

        # UI Widget handlers
        # ui_init()
        self.content_splitter = None

        # ui_build_file_toolbar()
        self.spr_dropdown = create_combobox(tooltip="Select a sprite build from the active project",
            on_index_changed=self._on_sprite_dropdown_changed)
        self.unsaved_label = create_label("Unsaved Changes")

        # ui_build_frame_viewer()
        self.sprite_label = QtW.QLabel("Sprite preview")
        self.btn_edit_group = QtW.QButtonGroup(self)
        self.btn_zoom_reset = create_pushbutton("1:1", tooltip="Reset preview zoom")
        self.btn_preview_center = create_pushbutton("Center", tooltip="Center the preview")
        self.origin_checkbox = create_checkbox("Origin", checked=True)
        self.grid_checkbox = create_checkbox("Grid")
        self.bounds_checkbox = create_checkbox("Bounds")

        # ui_build_file_manager()
        self.spr_file_group = CollapsiblePanel("Sprite Data and Files",
            tooltip="Expand or collapse the file manager")
        self.btn_toggle_filemanager = self.spr_file_group.toggle_button
        self.vram_spinbox = create_spinbox(minimum=0, maximum=2047,
            display_base=16, prefix="$", width=50, tooltip="Starting VRAM Tile Index (Hex)")
        self.sprpal_spinbox = create_spinbox(minimum=0, maximum=3, width=40, tooltip="Base Palette Line")
        self.btn_clear_spritedata = create_pushbutton("Clear Data", tooltip="Clear the current sprite data",
            on_clicked=self.file_sprite_clear)
        self.filemanager_tabs = QtW.QTabWidget()

        # ui_build_art_tab()
        self.btn_art_add = create_pushbutton("Add", tooltip="Add art tiles",
            width=50, on_clicked=self.art_entry_new)
        self.btn_art_load = create_pushbutton("Load", tooltip="Load added art tiles",
            width=50, on_clicked=self.art_entry_load, enabled=False)
        self.btn_art_save = create_pushbutton("Save", tooltip="Save art tile data",
            width=50, on_clicked=self.art_entry_save, enabled=False)
        self.btn_art_remove = create_pushbutton("Remove", tooltip="Remove the selected art tile entry",
            width=50, on_clicked=lambda: self.art_remove_entry(), enabled=False)
        self.art_file_table = QtW.QTableWidget(0, 4)

        # ui_build_mappings_tab()
        self.btn_map_add = create_pushbutton("Add", tooltip="Add sprite mappings",
            width=50, on_clicked=self.mapping_entry_new)
        self.btn_map_load = create_pushbutton("Load", tooltip="Load added mappings",
            width=50, on_clicked=self.mapping_entry_load, enabled=False)
        self.btn_map_save = create_pushbutton("Save", tooltip="Save mappings data",
            width=50, on_clicked=self.mapping_entry_save, enabled=False)
        self.btn_map_remove = create_pushbutton("Remove", tooltip="Remove mappings data",
            width=50, on_clicked=lambda: self.mapping_remove_entry(), enabled=False)
        self.map_dropdown = QtW.QComboBox()
        self.macro_cb = QtW.QCheckBox("Save with Macros")
        self.dplc_cb = QtW.QCheckBox("Use DPLCs")
        self.map_file_table = QtW.QTableWidget(2, 3)
        self.map_path_input = QtW.QLineEdit()
        self.map_name_input = QtW.QLineEdit()
        self.dplc_path_input = QtW.QLineEdit()
        self.dplc_name_input = QtW.QLineEdit()

        # ui_build_palettes_tab()
        self.btn_pal_add = create_pushbutton("Add", tooltip="Add color palettes",
            width=50, on_clicked=self.palette_entry_new)
        self.btn_pal_load = create_pushbutton("Load", tooltip="Load added palettes",
            width=50, on_clicked=self.palette_entry_load, enabled=False)
        self.btn_pal_save = create_pushbutton("Save", tooltip="Save palette data",
            width=50, on_clicked=self.palette_entry_save, enabled=False)
        self.btn_pal_remove = create_pushbutton("Remove", tooltip="Remove the selected palette entry",
            width=50, on_clicked=lambda: self.palette_remove_entry(), enabled=False)
        self.pal_file_table = QtW.QTableWidget(0, 2)

        # ui_build_editing_panel()
        self.editing_tabs = QtW.QTabWidget()

        # ui_build_art_viewer()
        self.vram_box = QtW.QGroupBox()
        self.viewer_line_combo = create_combobox(
            tooltip="Choose a palette line to view art tiles with",
            items=["Line 0", "Line 1", "Line 2", "Line 3"])
        self.vram_label = QtW.QLabel()
        self.vram_scroll = create_scrollarea(self.vram_label)
        self.arrange_tiles = create_pushbutton("Arrange Tiles",
            width=90, tooltip="Arrange tiles by sprite usage", enabled=False)
        self.strip_tiles = create_pushbutton("Strip Unused Tiles",
            width=110, tooltip="Remove all unused tiles", enabled=False)

        # ui_build_sprite_viewer()
        self.sprite_frame_list = QtW.QListWidget()

        # ui_build_map_editor()
        self.map_edit_box = QtW.QGroupBox()
        self.frame_spinbox = create_spinbox(minimum=0, maximum=0, on_value_changed=self._on_sprite_frame_changed)
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
        for field, spinbox in self.piece_spinboxes.items():
            spinbox.valueChanged.connect(lambda value, field=field:
                self.sprite_edit_piece_property(field, value))

        for field, checkbox in self.piece_checkboxes.items():
            checkbox.clicked.connect(lambda checked, field=field:
                self.sprite_edit_piece_property(field, checked))

        self.ui_init()
        self.sprite_refresh_editing_ui()

        self.vram_spinbox.valueChanged.connect(self.render_sprite_frame)
        self.sprpal_spinbox.valueChanged.connect(self.render_sprite_frame)
        self.origin_checkbox.toggled.connect(self.render_sprite_frame)
        self.viewer_line_combo.currentIndexChanged.connect(self.render_art_tiles)
        self.render_sprite_frame()

        self.project.project_loaded.connect(self._on_project_loaded)

    # --------------------------------------------------
    # UI Setup
    # --------------------------------------------------
    def ui_init(self):
        """Top-level UI constructor"""
        layout = QtW.QVBoxLayout(self)

        # TOP PANEL TOOLBAR
        toolbar = create_file_toolbar(self.spr_dropdown, self.unsaved_label,
            resource_name="sprite build", unsaved_changes=self._unsaved_changes,
            on_new=self.file_sprite_new, on_load=self.file_sprite_load,
            on_save=self.file_sprite_save, on_save_as=self.file_sprite_save,
            on_remove=self.file_sprite_remove)
        layout.addLayout(toolbar)

        sprite_panel = self.ui_build_sprite_panel()     # LEFT PANEL: Sprite View and File Manager
        editing_panel = self.ui_build_editing_panel()   # RIGHT PANEL: Editing Controls

        # Horizontal splitter between the sprite viewer and editor
        self.content_splitter = create_splitter((sprite_panel, editing_panel),
            orientation=Qt.Orientation.Horizontal, stretch_factors=(1, 1), sizes=(664, 336))
        layout.addWidget(self.content_splitter, stretch=1)

        # Close File Manager tray to start
        self.btn_toggle_filemanager.setChecked(False)

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

        # Palette Editing Toolbar
        edit_layout = QtW.QHBoxLayout()
        edit_layout.setSpacing(4)

        # Set-up Edit Group (Created in __init__)
        self.btn_edit_group.setExclusive(False)

        btn_undo = create_pushbutton("Undo", tooltip="Undo the last change made", width=55)
        btn_redo = create_pushbutton("Redo", tooltip="Redo the last undone change", width=55,)
        # Copy, Cut and Paste won't go here.

        self.btn_edit_group.addButton(btn_undo, id=EDIT_UNDO)
        self.btn_edit_group.addButton(btn_redo, id=EDIT_REDO)

        for button in self.btn_edit_group.buttons():
            edit_layout.addWidget(button)

        edit_layout.addStretch()

        # Add widgets from animation editor
        edit_layout.addWidget(QtW.QLabel("Zoom: 2×"))
        edit_layout.addWidget(self.btn_zoom_reset)
        edit_layout.addWidget(self.btn_preview_center)

        edit_layout.addStretch()

        # Visuals toggles
        for checkbox in (self.origin_checkbox, self.grid_checkbox, self.bounds_checkbox):
            edit_layout.addWidget(checkbox)

        sprite_viewer.addLayout(edit_layout)

        # Scrollable Sprite Viewer
        preview_hint_label = create_label(
            "Scroll to Zoom | Click-drag to Pan",
            layout=sprite_viewer)

        # To-Do: add this to QSS
        hint_font = preview_hint_label.font()
        hint_font.setPointSizeF(max(8.0, hint_font.pointSizeF() - 1.0))
        preview_hint_label.setFont(hint_font)

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

        # Update buttons when the filepath is typed or changed
        self.map_path_input.textChanged.connect(self.mapping_update_file_controls)

        # Show the DPLC row only when enabled
        table.setRowHidden(1, True)
        self.dplc_cb.toggled.connect(lambda enabled: table.setRowHidden(1, not enabled))

        layout.addWidget(table, stretch=1)
        self.mapping_update_file_controls()

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
            box = MiniColorBox(_i)
            box.clicked.connect(lambda _idx = _i: self.palette_open_color_library(_idx))
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
        self.vram_label.setAlignment(Qt.AlignmentFlag.AlignRight)

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

        table.itemSelectionChanged.connect(self.sprite_piece_list_selection_changed)

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


    # --------------------------------------------------
    # File Operations
    # --------------------------------------------------
    def file_sprite_new(self):
        """
        Create and select an empty sprite build definition.

        Returns:
            True if successful.
            False on failure or cancellation.
        """
        project = self.project

        # Verify a project is loaded (To-Do: Palette Editor SHOULD do this also).
        if not project.is_loaded:
            QtW.QMessageBox.warning(self, "No Project",
                "Please load a project file first.")
            return False

        # Prompt user for a new sprite build name (To-Do: Append a number to 'New Sprite' with repeated use)
        sprite_name, ok = QtW.QInputDialog.getText(self, "New Sprite Build",
            "Enter a name for the new sprite build:", text="New Sprite")

        if not ok or not sprite_name.strip():
            return False

        # Can this be done before the OK check?
        sprite_name = sprite_name.strip()

        # Ensure 'sprites' dictionary exists in project data
        sprites_dict = project.data.get("sprites", {})

        # Prevent duplicate definitions
        if sprite_name in sprites_dict:
            QtW.QMessageBox.warning(self, "Duplicate Name",
                f"A sprite named '{sprite_name}' already exists.")
            return False

        # Confirm before creating and switching to the new build
        if self._current_dropdown_index >= 0:
            answer = QtW.QMessageBox.question(self, "New Sprite Build",
                f"Create and switch to '{sprite_name}'?\n\n"
                "This will clear the current palettes, art, mappings, and "
                "file-manager entries. Unsaved changes will be discarded.",
                QtW.QMessageBox.StandardButton.Yes | QtW.QMessageBox.StandardButton.No,
                QtW.QMessageBox.StandardButton.No)

            if answer != QtW.QMessageBox.StandardButton.Yes:
                return False

        # Create an empty template for the sprite build
        new_sprite = {
            "format": 1,        # Sonic 1 by default
            "vram_index": 0,    # Global starting VRAM index
            "palette_line": 0,
            "palettes": [],
            "art": [],
            "mappings": {},
            "dplcs": {
                "enabled": False,
                "path": "",
                "label": "",
            }
        }

        try:
            # Prepare the new build without changing active project data
            proposed = project.snapshot()
            proposed.setdefault("sprites", {})[sprite_name] = new_sprite

            # Save and commit through the shared service
            project.save(proposed)

        except (OSError, TypeError, ValueError) as e:
            QtW.QMessageBox.warning(
                self,
                "New Sprite Error",
                f"Could not create sprite build '{sprite_name}':\n{e}",
            )
            return False

        # Use the configuration objects committed by the service
        self.project_sprite_builds = project.data["sprites"]
        new_sprite = self.project_sprite_builds[sprite_name]

        # Select the new build without triggering another confirmation
        was_blocked = self.spr_dropdown.blockSignals(True)

        try:
            if (
                self.spr_dropdown.count() == 1
                and self.spr_dropdown.itemText(0) == "No Sprites Found"
            ):
                self.spr_dropdown.clear()

            self.spr_dropdown.setEnabled(True)
            self.spr_dropdown.addItem(
                sprite_name,
                userData=new_sprite,
            )

            # Saving replaces the project dictionary. Refresh the
            # configurations attached to existing dropdown entries too.
            for index in range(self.spr_dropdown.count()):
                name = self.spr_dropdown.itemText(index)

                if name in self.project_sprite_builds:
                    self.spr_dropdown.setItemData(
                        index,
                        self.project_sprite_builds[name],
                    )

            self.spr_dropdown.setCurrentText(sprite_name)

        finally:
            self.spr_dropdown.blockSignals(was_blocked)

        # Clear prior assets and repopulate file manager
        self._on_sprite_dropdown_changed(confirm=False)
        return True

    def file_sprite_load(self):
        """
        Prepare all configured sprite assets before applying them.

        Returns:
            True if loading succeeds.
            False if the project, build, or asset preparation fails.
        """
        project = self.project

        if not project.is_loaded:
            return False

        # Get the selected sprite build name
        sprite_name = self.spr_dropdown.currentText()
        if not sprite_name or sprite_name == "No Sprites Found":
            return False

        # Get sprite data so we can load the global VRAM index
        sprite_data = project.data.get("sprites", {}).get(sprite_name)
        if sprite_data is None:
            QtW.QMessageBox.warning(self, "Load Error",
                f"Sprite '{sprite_name}' not found in project data.")
            return False

        # Prepare all assets before changing loaded data
        prepared_palettes = self.palette_prepare_load()
        if prepared_palettes is None:
            return False

        prepared_art = self.art_prepare_load()
        if prepared_art is None:
            return False

        prepared_mappings = self.mapping_prepare_load()
        if prepared_mappings is None:
            return False

        # Prevent viewing settings from triggering early renders
        vram_blocked = self.vram_spinbox.blockSignals(True)
        palette_blocked = self.sprpal_spinbox.blockSignals(True)

        try:
            # Set global VRAM index and reset frame counter
            self.vram_spinbox.setValue(sprite_data.get("vram_index", 0))
            self.sprpal_spinbox.setValue(sprite_data.get("palette_line", 0))

            # Apply prepared buffers without rendering
            self.palette_entry_load(prepared=prepared_palettes, refresh=False)
            self.art_entry_load(prepared=prepared_art, refresh=False)
            self.mapping_entry_load(prepared=prepared_mappings, refresh=False)

        finally:
            self.vram_spinbox.blockSignals(vram_blocked)
            self.sprpal_spinbox.blockSignals(palette_blocked)

        # Refresh after all buffers and settings are installed
        self.render_art_tiles()
        self._on_sprite_frame_changed(refresh_thumbnails=True)

        # Notification (since mapping_entry_load doesn't trigger one here)
        QtW.QMessageBox.information(self, "Sprite Loaded",
            f"Sprite '{sprite_name}' loaded successfully.\n"
            f"Mapping frames: {len(self.map_frames)}")

        return True

    def file_sprite_save(self):
        """
        Prepare all sprite assets and build settings, then save them.

        Returns:
            True if all saves succeed, False on failure or cancellation.
            Earlier asset writes are not rolled back if a later save fails.
        """
        project = self.project

        if not project.is_loaded:
            QtW.QMessageBox.warning(
                self,
                "No Project",
                "Please load a project file first.",
            )
            return False

        # Get the selected sprite build name
        sprite_name = self.spr_dropdown.currentText()
        if not sprite_name or sprite_name == "No Sprites Found":
            return False

        # Ensure Sprite dict exists and retrieve it
        sprite_data = project.data.get("sprites", {}).get(sprite_name)
        if sprite_data is None:
            QtW.QMessageBox.warning(self, "Save Error",
                f"Sprite '{sprite_name}' not found in project data."
            )
            return False

        try:
            # Prepare the current build without changing active data
            proposed_project = project.snapshot()
            proposed_project["sprites"][sprite_name] = self.file_sprite_collect_config(sprite_data)

            # Validate the destination and serialize before saving assets
            prepared_project = project.prepare_save(proposed_project)
            project_path = prepared_project[0]

        except Exception as e:
            QtW.QMessageBox.warning(
                self,
                "Save Error",
                f"Could not prepare sprite configuration:\n{e}",
            )
            return False

        # Prepare all assets before writing any files
        prepared_palettes = self.palette_prepare_save()
        if prepared_palettes is None:
            return False

        prepared_art = self.art_prepare_save()
        if prepared_art is None:
            return False

        prepared_mappings = self.mapping_prepare_save()
        if prepared_mappings is None:
            return False

        # Collect every destination, including the project JSON
        # Here we check destinations to avoid cross-contamination
        # (writing different kinds of files to the same destination)
        destinations = [(project_path, "Project JSON")]

        if prepared_palettes:
            save_jobs, _ = prepared_palettes
            destinations.extend((path, "Palette") for path, _ in save_jobs)

        if prepared_art:
            save_jobs, _ = prepared_art
            destinations.extend((path, "Art") for path, _ in save_jobs)

        if prepared_mappings:
            path, _ = prepared_mappings
            destinations.append((path, "Mappings"))

        # Reject destinations shared by multiple files
        seen_paths = {}

        for path, asset_type in destinations:
            if path in seen_paths:
                QtW.QMessageBox.warning(self, "Save Error",
                    f"{seen_paths[path]} and {asset_type} use the same "
                    f"save destination:\n{path}\n\n"
                    "Choose separate destinations before saving.")
                return False

            seen_paths[path] = asset_type

        # Write the prepared assets; stop if any save fails
        # Save palette(s)
        if not self.palette_entry_save(prepared=prepared_palettes):
            return False

        # Save art file(s)
        if not self.art_entry_save(prepared=prepared_art):
            return False

        # Save mappings
        if not self.mapping_entry_save(prepared=prepared_mappings):
            return False

        try:
            # Write the prepared JSON and commit active project data
            project.save_prepared(prepared_project)

        except Exception as e:
            QtW.QMessageBox.warning(
                self,
                "Project Save Error",
                f"Could not save project JSON:\n{e}",
            )
            return False

        # Refresh references from the newly committed project data
        self.project_sprite_builds = project.data["sprites"]

        was_blocked = self.spr_dropdown.blockSignals(True)

        try:
            for index in range(self.spr_dropdown.count()):
                name = self.spr_dropdown.itemText(index)

                if name in self.project_sprite_builds:
                    self.spr_dropdown.setItemData(
                        index,
                        self.project_sprite_builds[name],
                    )

        finally:
            self.spr_dropdown.blockSignals(was_blocked)

        QtW.QMessageBox.information(self, "Project Saved",
            f"Sprite '{sprite_name}' configuration saved to project JSON.")

        return True

    def file_sprite_remove(self):
        """
        Remove the selected build from the active project.
        Discard all pending edits without deleting asset files from disk.

        Returns:
            True if successful, False on failure or cancellation.
        """
        project = self.project

        if not project.is_loaded:
            return False

        # Get the currently selected sprite build
        sprite_name = self.spr_dropdown.currentText()
        if not sprite_name or sprite_name == "No Sprites Found":
            return False

        sprites_dict = project.data.get("sprites", {})
        if sprite_name not in sprites_dict:
            QtW.QMessageBox.warning(self, "Remove Sprite Error",
                f"Sprite '{sprite_name}' not found in project data.")
            return False

        # Prompt user before removing the sprite
        answer = QtW.QMessageBox.question(
            self, "Remove Sprite Build",
            f"Are you sure you want to remove '{sprite_name}' from the project?\n\n"
            "Note: The actual files will NOT be deleted from your disassembly.",
            QtW.QMessageBox.StandardButton.Yes | QtW.QMessageBox.StandardButton.No,
            QtW.QMessageBox.StandardButton.No)

        if answer != QtW.QMessageBox.StandardButton.Yes:
            return False

        try:
            # Prepare removal without changing active project data
            proposed = project.snapshot()
            del proposed["sprites"][sprite_name]

            # Save and commit through the shared service
            project.save(proposed)

        except (OSError, TypeError, ValueError) as e:
            QtW.QMessageBox.warning(
                self,
                "Remove Sprite Error",
                f"Could not remove sprite build '{sprite_name}':\n{e}",
            )
            return False

        # Clear discarded editor data only after saving succeeds
        self.sprite_clear_data()
        self.active_sprite_build = None

        # Rebuild the dropdown from the newly committed project data
        self.proj_populate_sprite_list(
            project.data.get("sprites", {})
        )

        return True

    def file_sprite_clear(self):
        """
        Discard loaded sprite assets while preserving File Manager settings.

        Returns:
            True if cleared, False if canceled.
        """
        answer = QtW.QMessageBox.question(self, "Clear Loaded Data",
            "Clear the loaded palettes, art, and mappings?\n\n"
            "Pending asset edits will be discarded. "
            "File Manager settings will be kept.",
            QtW.QMessageBox.StandardButton.Yes | QtW.QMessageBox.StandardButton.No,
            QtW.QMessageBox.StandardButton.No)

        if answer != QtW.QMessageBox.StandardButton.Yes:
            return False

        # Clear out all sprite data
        self.sprite_clear_data(clear_file_manager=False)
        return True

    def file_sprite_collect_config(self, sprite_data):
        """
        Collect current build settings and store them in a separate dictionary,
        without changing live project data.

        Returns collected build data.
        """
        config = deepcopy(sprite_data)
        stored_path = self.project.store_asset_path

        config["vram_index"] = self.vram_spinbox.value()
        config["palette_line"] = self.sprpal_spinbox.value()
        config["format"] = (self.map_dropdown.currentIndex() + 1
            if self.map_dropdown is not None
            else config.get("format", 1))

        # Include empty lists and rows reserving palette lines
        config["palettes"] = [
            {"path": stored_path(path), "length": num_lines}
            for path, num_lines in self.palette_get_file_layout()
        ]

        config["art"] = []
        for path_input, comp_combo, offset_spin, count_spin, _ in self.art_rows:
            path_text = path_input.text().strip()
            if path_text:
                config["art"].append({
                    "path": stored_path(path_text),
                    "compression": comp_combo.currentText(),
                    "offset": offset_spin.value(),
                    "count": count_spin.value(),
                })

        # Clear removed mappings and their DPLC settings
        config["mappings"] = {}
        config["dplcs"] = {"enabled": False, "path": "", "label": ""}
        map_path = (self.map_path_input.text().strip()
            if self.map_path_input is not None else "")

        if map_path:
            config["mappings"] = {
                "path": stored_path(map_path),
                "label": self.map_name_input.text().strip(),
            }
            config["dplcs"] = {
                "enabled": self.dplc_cb.isChecked(),
                "path": stored_path(self.dplc_path_input.text().strip()),
                "label": self.dplc_name_input.text().strip(),
            }

        return config


    def file_confirm_overwrites(self, paths):
        """
        Confirm replacement of existing files at changed save assignments.

        Returns:
            True if confirmation is unnecessary or accepted.
            False if canceled or a destination is invalid.
        """
        try:
            existing_paths = []

            for path in dict.fromkeys(paths):
                if path.is_dir():
                    raise IsADirectoryError(f"Save destination is a directory: {path}")

                if path.exists():
                    existing_paths.append(path)

        except OSError as e:
            QtW.QMessageBox.warning(self, "Save Error", str(e))
            return False

        if not existing_paths:
            return True

        file_list = "\n".join(str(path) for path in existing_paths)

        answer = QtW.QMessageBox.question(self, "Overwrite Files",
            f"These files already exist:\n\n{file_list}\n\n"
            "Overwrite them with the current editor data?",
            QtW.QMessageBox.StandardButton.Yes | QtW.QMessageBox.StandardButton.No,
            QtW.QMessageBox.StandardButton.No,
        )

        return answer == QtW.QMessageBox.StandardButton.Yes


    # --------------------------------------------------
    # Project File Selection
    # --------------------------------------------------
    def proj_populate_sprite_list(self, sprite_builds):
        self.project_sprite_builds = sprite_builds

        # Previous indices no longer refer to the rebuilt list
        self._current_dropdown_index = -1

        self.spr_dropdown.blockSignals(True)
        self.spr_dropdown.clear()

        if not sprite_builds:
            self.spr_dropdown.addItem("No Sprites Found", userData=None)
            self.spr_dropdown.setEnabled(False)
            self.spr_dropdown.blockSignals(False)
            return

        self.spr_dropdown.setEnabled(True)
        for sprite_name, config in sprite_builds.items():
            # Display key name in dropdown
            self.spr_dropdown.addItem(sprite_name, userData=config)

        # Silently reset the selection
        self.spr_dropdown.setCurrentIndex(-1)
        self.spr_dropdown.blockSignals(False)

        # Only auto-load index 0 if we aren't currently targeting a specific sprite build
        if not self.active_sprite_build and self.spr_dropdown.count() > 0:
            self.spr_dropdown.setCurrentIndex(0)

    # File Toolbar Dropdown function
    def _on_sprite_dropdown_changed(self, *, confirm=True):
        project = self.project

        if not project.is_loaded:
            return

        # Get the selected sprite build name
        sprite_name = self.spr_dropdown.currentText()
        if not sprite_name or sprite_name == "No Sprites Found":
            return

        # Ensure 'sprites' dictionary exists and contains our sprite
        sprites_dict = project.data.get("sprites", {})
        if sprite_name not in sprites_dict:
            QtW.QMessageBox.warning(self, "Load Error", f"Sprite '{sprite_name}' not found in project data.")
            return

        # Get data for the newly selected sprite build
        sprite_data = sprites_dict[sprite_name]
        if not sprite_data:
            QtW.QMessageBox.warning(self, "Load Error", f"Sprite '{sprite_name}' not found in project data.")
            return

        # Helper to convert relative paths/Path objects to full absolute path strings
        def resolve_path_str(raw_path):
            path = project.resolve_asset_path(raw_path)
            return str(path) if path is not None else ""

        # Ignore an unchanged selection
        new_index = self.spr_dropdown.currentIndex()
        if new_index == self._current_dropdown_index:
            return

        # Confirm before discarding the current build's editor state
        if confirm and self._current_dropdown_index >= 0:
            answer = QtW.QMessageBox.question(
                self, "Switch Sprite Build",
                f"Switch to '{sprite_name}'?\n\n"
                "This will clear the current palettes, art, and mappings. "
                "Unsaved changes will be discarded.",
                QtW.QMessageBox.StandardButton.Yes
                | QtW.QMessageBox.StandardButton.No,
                QtW.QMessageBox.StandardButton.No,
            )

            if answer != QtW.QMessageBox.StandardButton.Yes:
                # Restore the previous selection without triggering this handler
                was_blocked = self.spr_dropdown.blockSignals(True)

                try:
                    self.spr_dropdown.setCurrentIndex(
                        self._current_dropdown_index
                    )
                finally:
                    self.spr_dropdown.blockSignals(was_blocked)

                return

        # Clear loaded assets and entries before applying new ones
        self.sprite_clear_data()

        # Fill out palette data
        for pal in sprite_data.get("palettes", []):
            raw_path = pal.get("path", "") if isinstance(pal, dict) else pal
            self.palette_add_entry(resolve_path_str(raw_path))

            # New row at the end of the list
            path_input, line_combo = self.pal_rows[-1]
            line_combo.setCurrentText(str(pal.get("length", 1)))

        # Fill out art data
        for art in sprite_data.get("art", []):
            raw_path = art.get("path", "") if isinstance(art, dict) else art
            self.art_add_entry(resolve_path_str(raw_path))

            # New row at the end of the list
            path_input, comp_combo, offset_spin, count_spin, art_tiles = self.art_rows[-1]
            offset_spin.setValue(art.get("offset", 0))
            comp_combo.setCurrentText(art.get("compression", "Uncompressed"))
            count_spin.setValue(art.get("count", 0))  # Load all tiles by default

        # Fill out mapping data
        mappings = sprite_data.get("mappings", {})
        dplcs = sprite_data.get("dplcs", {})

        # Support an older configuration containing only a path
        if not isinstance(mappings, dict):
            mappings = {"path": mappings}

        if not isinstance(dplcs, dict):
            dplcs = {}

        self.map_dropdown.setCurrentIndex(sprite_data.get("format", 1) - 1)

        self.map_path_input.setText(resolve_path_str(mappings.get("path", "")))
        self.map_name_input.setText(mappings.get("label", ""))

        self.dplc_path_input.setText(resolve_path_str(dplcs.get("path", "")))
        self.dplc_name_input.setText(dplcs.get("label", ""))
        self.dplc_cb.setChecked(dplcs.get("enabled", False))

        # Remember the accepted selection
        self._current_dropdown_index = new_index

    def _on_project_loaded(self):
        """
        Reset sprite data and read the active project's build list.
        """
        self.sprite_clear_data()
        self.active_sprite_build = None

        sprite_builds = self.project.data.get("sprites", [])
        self.proj_populate_sprite_list(sprite_builds)


    # --------------------------------------------------
    # File Manager
    # --------------------------------------------------
    def filemanager_clear(self):
        """
        Remove file-manager entries and invalidate their file associations.
        """
        self.palette_buffer_layout = None
        self.palette_new_paths.clear()

        # Clean out Palette rows
        while self.pal_rows:
            self.palette_remove_entry(0)

        # Clean out Art rows
        while self.art_rows:
            self.art_remove_entry(0)

        # Clean out Mapping fields
        self.mapping_remove_entry()


    # --------------------------------------------------
    # Sprite Functions
    # --------------------------------------------------
    def sprite_clear_data(self, *, clear_file_manager=True):
        """Clear loaded assets and reset previews, optionally clearing file manager entries."""
        # Clear sprite piece selection
        self.sprite_clear_selection(refresh=False)

        # Clear palette to black and invalidate file association
        self.palette_buffer_layout = None
        black = QColor(0, 0, 0)
        self.palette_colors = [black for _i in range(64)]
        for box in self.palette_boxes:
            box.set_color(black)

        # Clear art buffers and their file associations
        self.art_buffer_paths.clear()

        # Clear Art Tiles
        for _, _, _, _, art_tiles in self.art_rows:
            art_tiles.clear()

        # Flush VRAM and invalidate cached previews
        self.vram_tiles.clear()
        self.art_preview_revision += 1

        # Invalidate stale mapping file association
        self.mapping_buffer_path = None

        # Clear Sprite mappings and labels
        self.map_frames.clear()
        self.frame_labels.clear()
        self.sprite_refresh_frame_name()

        # Reset UI widgets in the Sprite Viewer
        if clear_file_manager:
            self.vram_spinbox.setValue(0)
            self.sprpal_spinbox.setValue(0)

        # Reset the frame selector for the empty mapping buffer
        was_blocked = self.frame_spinbox.blockSignals(True)

        try:
            self.frame_spinbox.setRange(0, 0)
            self.frame_spinbox.setValue(0)

        finally:
            self.frame_spinbox.blockSignals(was_blocked)

        # Refresh controls and previews after clearing the data
        self.sprite_refresh_editing_ui()
        self.render_art_tiles()
        #self.sprite_refresh_previews() # Refresh canvas AND thumbnails

        if clear_file_manager:
            self.filemanager_clear()

    def sprite_refresh_frame_name(self):
        frame_index = self.frame_spinbox.value()
        has_frame = (0 <= frame_index < len(self.map_frames)
            and frame_index < len(self.frame_labels))

        # Change label text box to that of the new frame's label (or blank if there is no frame)
        self.frame_name_input.setEnabled(has_frame)
        self.frame_name_input.setText(self.frame_labels[frame_index] if has_frame else "")

    def sprite_get_selected_pieces(self):
        frame_index = self.frame_spinbox.value()

        if not 0 <= frame_index < len(self.map_frames):
            return []

        pieces = self.map_frames[frame_index]

        return [
            (index, pieces[index])
            for index in sorted(self.selected_pieces)
            if 0 <= index < len(pieces)
        ]

    def sprite_refresh_editing_ui(self):
        """
        Refresh list contents, selection, and property controls in order.
        """
        self.sprite_refresh_piece_list()
        self.sprite_sync_piece_list_selection()
        self.sprite_refresh_piece_controls()

    def sprite_refresh_piece_list(self):
        """
        Update piece-list contents when the frame or displayed names change.
        """
        table = self.piece_list_table
        frame_index = self.frame_spinbox.value()

        if 0 <= frame_index < len(self.map_frames):
            pieces = self.map_frames[frame_index]
        else:
            pieces = []

        # Remove selection indices that no longer exist
        self.selected_pieces.intersection_update(range(len(pieces)))

        # Took names out of the enum loop below
        names = tuple(
            str(piece.get("name") or piece.get("label") or f"Piece {row}")
            for row, piece in enumerate(pieces)
        )

        # Position, appearance, and selection do not affect list contents
        state = (frame_index, names)
        if state == self.piece_list_state:
            return

        was_blocked = table.blockSignals(True)

        try:
            table.setRowCount(len(names))

            for row, name in enumerate(names):
                item = table.item(row, 0)

                if item is None:
                    item = QtW.QTableWidgetItem()
                    item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                    table.setItem(row, 0, item)

                if item.text() != name:
                    item.setText(name)

                item.setToolTip(name)

                # Match the zero-based indices used by the editor
                if table.verticalHeaderItem(row) is None:
                    table.setVerticalHeaderItem(row, QtW.QTableWidgetItem(str(row)))

        finally:
            table.blockSignals(was_blocked)

        self.piece_list_state = state

    def sprite_sync_piece_list_selection(self):
        """
        Match the table selection to the selected sprite pieces.
        """
        table = self.piece_list_table
        table_selection = {
            index.row()
            for index in table.selectionModel().selectedRows()
        }

        if table_selection == self.selected_pieces:
            return

        was_blocked = table.blockSignals(True)

        try:
            table.clearSelection()

            # Sync table selection to piece(s) selected on view
            for row in sorted(self.selected_pieces):
                table.setRangeSelected(
                    QtW.QTableWidgetSelectionRange(row, 0, row, 0),
                    True
                )

        finally:
            table.blockSignals(was_blocked)

    def sprite_piece_list_selection_changed(self):
        self.selected_pieces = {index.row() for index in self.piece_list_table.selectionModel().selectedRows()}

        self.piece_drag = None
        self.hovered_piece = None
        #self.sprite_end_box_select()

        # Update property panel and canvas
        self.sprite_refresh_piece_controls()
        self.render_sprite_frame()

    def sprite_refresh_piece_controls(self):
        selected = self.sprite_get_selected_pieces()
        has_selection = bool(selected)

        # Disable property spinboxes when nothing is selected
        for spinbox in self.piece_spinboxes.values():
            spinbox.setEnabled(has_selection)

        # Same with property checkboxes
        for checkbox in self.piece_checkboxes.values():
            checkbox.setEnabled(has_selection)

        # Update when buttons are enabled based on piece change
        frame_index = self.frame_spinbox.value()

        self.btn_piece_add.setEnabled(0 <= frame_index < len(self.map_frames))
        self.btn_piece_remove.setEnabled(bool(selected))

        has_frames = (
            0 <= frame_index < len(self.map_frames)
            and frame_index < len(self.frame_labels)
        )
        self.btn_frame_remove.setEnabled(has_frames)
        self.btn_frame_clone.setEnabled(has_frames)

        # Include selection identity and property values
        state = (
            self.frame_spinbox.value(),
            tuple(
                (index,
                    tuple(
                        piece[field]
                        for field in self.piece_spinboxes
                    ),
                    tuple(
                        bool(piece.get(field, False))
                        for field in self.piece_checkboxes
                    ),
                )
                for index, piece in selected
            ),
        )

        if state == self.piece_controls_state:
            return

        self.piece_controls_state = state
        self.index_label.setEnabled(bool(selected))

        if selected:
            index, reference_piece = selected[0]

            title = f"Piece {index}"
            if len(selected) > 1:
                title += f" — {len(selected)} selected"

            self.index_label.setText(title)
        else:
            reference_piece = None
            self.index_label.setText("Piece Properties")

        # Updating the UI must not write values back into the data
        for field, spinbox in self.piece_spinboxes.items():
            was_blocked = spinbox.blockSignals(True)

            try:
                if reference_piece is None:
                    spinbox.setValue(spinbox.minimum())
                    spinbox.clear()
                else:
                    spinbox.setValue(reference_piece[field])
            finally:
                spinbox.blockSignals(was_blocked)

        for field, checkbox in self.piece_checkboxes.items():
            values = {
                bool(piece.get(field, False))
                for _, piece in selected
            }
            mixed = len(values) > 1

            was_blocked = checkbox.blockSignals(True)

            try:
                checkbox.setTristate(mixed)

                if mixed:
                    checkbox.setCheckState(
                        Qt.CheckState.PartiallyChecked
                    )
                else:
                    checkbox.setChecked(True in values)
            finally:
                checkbox.blockSignals(was_blocked)

    def sprite_edit_piece_property(self, field, value):
        if field not in self.piece_spinboxes and field not in self.piece_checkboxes:
            return

        selected = self.sprite_get_selected_pieces()
        if not selected:
            return

        changed = False

        if field in ("x", "y"):
            # Position edits move the group by the same distance
            reference_piece = selected[0][1]
            delta = int(value) - reference_piece[field]

            spinbox = self.piece_spinboxes[field]

            min_delta = max(spinbox.minimum() - piece[field] for _, piece in selected)
            max_delta = min(spinbox.maximum() - piece[field] for _, piece in selected)

            # Keep the entire group within the editing limits
            if min_delta <= max_delta:
                delta = max(min_delta, min(max_delta, delta))
            else:
                delta = 0

            if delta:
                for _, piece in selected:
                    piece[field] += delta
                changed = True

        else:
            if field in self.piece_checkboxes:
                value = bool(value)
            else:
                value = int(value)

            for _, piece in selected:
                if piece.get(field) != value:
                    piece[field] = value
                    changed = True

        # Restore displayed values even if an edit was limited or rejected
        self.piece_controls_state = None
        self.sprite_refresh_piece_controls()

        if changed:
            self.render_sprite_frame()

    def sprite_clear_selection(self, *, refresh=True):
        """
        Clear selection and mouse interactions, optionally updating the UI.
        """
        self.selected_pieces.clear()
        self.piece_drag = None
        self.hovered_piece = None
        #self.sprite_end_box_select()

        # Proper refresh (only if needed)
        if refresh:
            self.sprite_refresh_editing_ui()
            self.render_sprite_frame()

    def _on_sprite_frame_changed(self, *, refresh_thumbnails=False):
        """
        Update frame controls and canvas.
        Also refresh thumbnails if needed.
        """
        self.sprite_refresh_frame_name()
        self.sprite_clear_selection()

    # --------------------------------------------------
    # Art File Entries
    # --------------------------------------------------
    def art_entry_new(self):
        """
        Add an art file to the sprite build.
        """
        # Access project directory
        project_dir = self.project.root_dir
        start_dir = str(project_dir) if project_dir else ""

        # Filetype filter (To-Do: Move this to a global file and have each load instance pick and choose)
        art_file_filter = (
            "Uncompressed Art (*.bin *.unc);;"
            "Nemesis Art (*.nem *.unc);;"
            "Kosinski Art (*.kos *.unc);;"
            "Moduled Kosinski Art (*.kosm *.unc);;"
            "All Files (*)"
        )

        # Open dialog for new art file
        file_path, _ = QtW.QFileDialog.getOpenFileName(self, "Add Art File", start_dir, art_file_filter)

        # If successful, create a new row under the art tab
        if file_path:
            self.art_add_entry(file_path)

    def art_entry_load(self, *, prepared=None, refresh=True):
        """
        Apply art data, preparing it first unless supplied.

        Returns:
            True if successful, False if preparation fails.
        """
        # Prepare when called directly
        if prepared is None:
            prepared = self.art_prepare_load()

        # Preparation failed/cancelled
        if prepared is None:
            return False

        load_jobs, loaded_paths = prepared

        # Preserve each row's buffer reference
        for art_tiles, loaded_tiles in load_jobs:
            art_tiles[:] = loaded_tiles

        # Set path associations and refresh VRAM
        self.art_buffer_paths = loaded_paths
        self.art_refresh_vram(refresh=refresh)

        return True

    def art_entry_save(self, *, prepared=None):
        """
        Save art, preparing it first unless a result is supplied.

        Returns:
            True if all files saved or no files are configured.
            False on failure or cancellation.
            Earlier files may have saved if a later write fails.
        """
        # If not prepared beforehand, do it here
        if prepared is None:
            prepared = self.art_prepare_save()

        # Preparation failed/cancelled
        if prepared is None:
            return False

        # No art files are configured
        if not prepared:
            return True

        save_jobs, saved_paths = prepared

        # Write only after every entry has been prepared
        for path, art_data in save_jobs:
            try:
                # Create directory structure if saving to a new path
                path.parent.mkdir(parents=True, exist_ok=True)

                with open(path, "wb") as f:
                    f.write(art_data)

            except Exception as e:
                QtW.QMessageBox.warning(self, "Art Save Error",
                    f"Could not save art file {path.name}:\n{str(e)}")
                return False

        # Adopt destinations only after all saves succeed
        self.art_buffer_paths.update(saved_paths)
        return True

    def art_prepare_load(self):
        """
        Read and decompress art for eventual loading.

        Returns:
            (load_jobs, loaded_paths) on success.
            None if preparation fails.
            Blank entries receive empty buffers when applied.
        """
        load_jobs = []
        loaded_paths = {}
        seen_paths = set()

        # Loop for each filepath added
        for path_input, comp_combo, _, _, art_tiles in self.art_rows:
            file_path_str = path_input.text().strip()

            # Clear for unassigned entries
            if not file_path_str:
                load_jobs.append((art_tiles, []))
                continue

            path = Path(file_path_str)

            try:
                path = self.project.resolve_asset_path(path)

                # Reject duplicate file assignments
                if path in seen_paths:
                    raise ValueError("Art file is listed more than once.")

                seen_paths.add(path)

                with open(path, "rb") as f:
                    raw_data = f.read()

                # Unpack tiles and load into buffer storage
                loaded_tiles = decode_art(raw_data, comp_combo.currentText())

                # Queue buffer to be loaded
                load_jobs.append((art_tiles, loaded_tiles))
                loaded_paths[path_input] = path

            except Exception as e:
                QtW.QMessageBox.warning(self, "Art Load Error",
                    f"Could not load art file {path.name}:\n{str(e)}")
                return None

        return load_jobs, loaded_paths

    def art_prepare_save(self):
        """
        Validate art entries and prepare their encoded file contents.
        (Much of this code was pulled from art_entry_save).

        Returns:
            (save_jobs, saved_paths) when ready to save.
            () if no art files are configured.
            None if preparation fails or is canceled.
        """
        save_jobs = []
        seen_paths = set()
        overwrite_paths = []
        saved_paths = {}

        for path_input, comp_combo, _, _, art_tiles in self.art_rows:
            file_path_str = path_input.text().strip()
            if not file_path_str:
                continue

            path = Path(file_path_str)

            try:
                # Resolve the destination
                path = self.project.resolve_asset_path(path)

                if path.is_dir():
                    raise IsADirectoryError(f"Save destination is a directory: {path}")

                # Reject duplicate destinations
                if path in seen_paths:
                    raise ValueError("Art file is listed more than once.")
                seen_paths.add(path)

                # Require a loaded buffer for this row
                source_path = self.art_buffer_paths.get(path_input)

                if source_path is None:
                    raise ValueError("Load art for this entry before saving.")

                # Require a populated source buffer
                if not art_tiles:
                    raise ValueError("No art tiles are loaded for this entry.")

                # Changed destinations may require overwrite confirmation
                if source_path != path:
                    overwrite_paths.append(path)

                # Pack art tiles into binary data (Compressed, if necessary)
                art_data = encode_art(art_tiles, comp_combo.currentText())

                # Queue prepared file and record its proposed path
                save_jobs.append((path, bytes(art_data)))
                saved_paths[path_input] = path

            # Handle unexpected errors (validation, packing, compression)
            except Exception as e:
                QtW.QMessageBox.warning(self, "Art Save Error",
                    f"Could not prepare art file {path.name}:\n{e}")
                return None

        if not save_jobs:
            return ()

        if not self.file_confirm_overwrites(overwrite_paths):
            return None

        return save_jobs, saved_paths

    def art_add_entry(self, file_path):
        """
        Add an art entry to the file manager.
        """
        # Cap sprite build at 3 art files
        if len(self.art_rows) >= 3:
            return

        # Filepath text box
        path_input = QtW.QLineEdit(file_path)

        # Compression Dropdown
        comp_combo = QtW.QComboBox()
        comp_combo.addItems(["Uncompressed", "Nemesis", "Kosinski", "Kosinski-M"])

        # Set compression dropdown based on file extension (if not .bin)
        compression_by_extension = {
            ".nem": "Nemesis",
            ".kos": "Kosinski",
            ".kosm": "Kosinski-M",
        }
        extension = Path(file_path).suffix.lower()
        comp_combo.setCurrentText(compression_by_extension.get(extension, "Uncompressed"))

        artloc_spin = QtW.QSpinBox()
        artloc_spin.setRange(0, 2047)  # Cap at 2048 tiles (I'll worry about specifics later)
        artloc_spin.setDisplayIntegerBase(16)  # Display in hex
        artloc_spin.setPrefix("$")

        count_spin = QtW.QSpinBox()
        count_spin.setRange(0, 2048)  # Cap at 2048 tiles (Max possible in VRAM)
        count_spin.setSpecialValueText("All")
        count_spin.setToolTip("Number of source tiles to load into VRAM.\n"
            "0 to load all tiles that fit.")

        # Each entry has its own art_tile structure
        art_tiles = []

        # Store elements
        row_data = (path_input, comp_combo, artloc_spin, count_spin, art_tiles)
        self.art_rows.append(row_data)

        # Add and assemble a table row
        row = self.art_file_table.rowCount()
        self.art_file_table.insertRow(row)

        self.art_file_table.setCellWidget(row, 0, path_input)
        self.art_file_table.setCellWidget(row, 1, comp_combo)
        self.art_file_table.setCellWidget(row, 2, artloc_spin)
        self.art_file_table.setCellWidget(row, 3, count_spin)

        self.art_file_table.selectRow(row)

        # Initial evaluation
        self.art_update_file_controls()

        artloc_spin.valueChanged.connect(self.art_refresh_vram)
        count_spin.valueChanged.connect(self.art_refresh_vram)

    def art_remove_entry(self, row=None):
        if row is None:
            row = self.art_file_table.currentRow()

        if not 0 <= row < len(self.art_rows):
            return

        # Remove the row and its file association
        path_input, _, _, _, _ = self.art_rows.pop(row)
        self.art_buffer_paths.pop(path_input, None)
        self.art_file_table.removeRow(row)

        if self.art_rows:
            self.art_file_table.selectRow(min(row, len(self.art_rows) - 1))

        self.art_update_file_controls()
        self.art_refresh_vram()

    def art_update_file_controls(self):
        """
        Enable/Disable controls based on file manager state.
        """
        count = len(self.art_rows)
        selected_row = self.art_file_table.currentRow()

        # Enable/Disable buttons based on number of art files
        self.btn_art_add.setEnabled(count < 3)
        self.btn_art_load.setEnabled(count > 0)
        self.btn_art_save.setEnabled(count > 0)
        self.btn_art_remove.setEnabled(0 <= selected_row < count)

    def art_refresh_vram(self, *, refresh=True):
        """
        Load each file's source tiles into VRAM
        """
        self.vram_tiles.clear()

        for _, _, offset_spin, count_spin, art_tiles in self.art_rows:
            start = offset_spin.value()
            requested_count = count_spin.value()

            # If count == 0, load all tiles that will fit into VRAM
            if requested_count == 0:
                requested_count = len(art_tiles)

            preview_count = min(requested_count, len(art_tiles), 2048 - start)

            # Copy from source to VRAM
            for source_index in range(preview_count):
                self.vram_tiles[start + source_index] = (art_tiles[source_index].copy())

        # Invalidate cached previews after rebuilding VRAM
        self.art_preview_revision += 1

        # Whole-build loading can defer refreshing
        if refresh:
            self.render_art_tiles()
            self.render_sprite_frame()

    # --------------------------------------------------
    # Mapping File Entries
    # --------------------------------------------------
    def mapping_entry_new(self):
        if self.map_path_input.text().strip():
            return

        # Access project directory
        project_dir = self.project.root_dir
        start_dir = str(project_dir) if project_dir else ""

        # Save dialog for new mapping file, WITHOUT creating the file
        file_path, _ = QtW.QFileDialog.getSaveFileName(self, "New Mapping File",
            start_dir, "Mapping Files (*.asm *.bin);;All Files (*)")

        if not file_path:
            return

        path = self.project.resolve_asset_path(file_path)
        initialize = self.mapping_buffer_path is None and not path.exists()

        self.mapping_add_entry(str(path))

        # Initialize a new document without creating its file
        if initialize:
            self.mapping_set_buffer(path, [], [],
                self.map_name_input.text().strip(), self.macro_cb.isChecked())

    def mapping_entry_load(self, *, prepared=None, refresh=True):
        """
        Apply mapping data, preparing it first unless supplied.

        Returns:
            True if successful, False if preparation fails.
        """
        # If not prepared beforehand, do it here
        if prepared is None:
            prepared = self.mapping_prepare_load()

        # Preparation failed/cancelled
        if prepared is None:
            return False

        # Commit data and association together
        self.mapping_set_buffer(*prepared, refresh=refresh)

        # Report direct loads of configured files
        path = prepared[0]
        if refresh and path is not None:
            QtW.QMessageBox.information(self, "Mappings Loaded",
                f"Successfully loaded {len(self.map_frames)} frames from {path.name}.")

        return True

    def mapping_entry_save(self, *, prepared=None):
        """
        Save sprite mappings, preparing them first unless a result is supplied.

        Returns:
            True if saved successfully or no file is configured.
            False on failure or cancellation.
        """
        # If not prepared beforehand, do it here
        if prepared is None:
            prepared = self.mapping_prepare_save()

        # Preparation failed or was canceled
        if prepared is None:
            return False

        # No mapping file is configured
        if not prepared:
            return True

        path, mapping_data = prepared

        # Write only after mappings are prepared
        try:
            # Write the prepared file
            path.parent.mkdir(parents=True, exist_ok=True)
            save_mappings(path, mapping_data)

        except Exception as e:
            QtW.QMessageBox.warning(self, "Mapping Save Error",
                f"Could not save mappings to {path.name}:\n{str(e)}")
            return False

        # Adopt the destination only after a successful save
        self.mapping_buffer_path = path

        QtW.QMessageBox.information(self, "Mappings Saved",
            f"Successfully saved {len(self.map_frames)} frames to {path.name}.")
        return True

    def mapping_prepare_load(self):
        """
        Parse configured mappings without changing the editor.

        Returns:
            (path, frames, frame_labels, map_label, use_macros) on success.
            An empty mapping buffer if no file is configured.
            None if preparation fails.
        """
        file_path_str = (
            self.map_path_input.text().strip()
            if self.map_path_input is not None else "")

        # For unconfigured mappings, use an empty buffer
        if not file_path_str:
            return None, [], [], "", False

        path = Path(file_path_str)

        try:
            # Resolve relative paths against the project directory
            path = self.project.resolve_asset_path(path)

            # Prepare data without changing anything in the editor
            loaded = load_mappings(path, self.map_dropdown.currentIndex() + 1)

        except Exception as e:
            QtW.QMessageBox.warning(self, "Mapping Load Error",
                f"Could not load mappings {path.name}:\n{e}")
            return None

        return path, *loaded

    def mapping_prepare_save(self):
        """
        Validate mappings and prepare file contents for saving.
        (Much of this code was pulled from mapping_entry_save).

        Returns:
            (path, data) when ready to save.
            () if no mapping file is configured.
            None if preparation fails or is canceled.
        """
        # If a filepath is empty, don't save
        file_path_str = self.map_path_input.text().strip()
        if not file_path_str:
            return ()

        # Require a loaded or initialized mapping buffer
        if self.mapping_buffer_path is None:
            QtW.QMessageBox.warning(self, "Mapping Save Error",
                "Load or initialize mappings for this build before saving.")
            return None

        # Require at least one frame; frames may contain no pieces
        if not self.map_frames:
            QtW.QMessageBox.warning(self, "Mapping Save Error",
                "Add or load at least one mapping frame before saving.")
            return None

        path = Path(file_path_str)

        try:
            # Resolve the destination
            path = self.project.resolve_asset_path(path)

            if path.is_dir():
                raise IsADirectoryError(f"Save destination is a directory: {path}")

            # Confirm a changed destination
            if path != self.mapping_buffer_path:
                if not self.file_confirm_overwrites([path]):
                    return None

            # Collect the optional ASM description before writing
            description = ""
            if path.suffix.lower() == ".asm":
                description, accepted = QtW.QInputDialog.getText(self, "Sprite Description",
                    "Enter an optional description for the mappings:", text="New Sprite")

                if not accepted:
                    return None

            # Build the complete file without writing it
            mapping_data = prepare_mappings(path, self.map_frames, self.frame_labels,
                self.map_dropdown.currentIndex() + 1, map_label=self.map_name_input.text().strip(),
                use_macros=self.macro_cb.isChecked(), description=description)

        except Exception as e:
            QtW.QMessageBox.warning(self, "Mapping Save Error",
                f"Could not prepare mappings for {path.name}:\n{e}")
            return None

        return path, mapping_data

    def mapping_add_entry(self, file_path):
        # Only one mapping file can be configured
        if self.map_path_input.text().strip():
            return

        self.map_path_input.setText(file_path)
        self.map_file_table.selectRow(0)

    def mapping_remove_entry(self):
        # Invalidate stale file association
        self.mapping_buffer_path = None

        # Removes the mapping/DPLC data and re-enables the Add button
        self.map_path_input.clear()
        self.map_name_input.clear()

        self.dplc_path_input.clear()
        self.dplc_name_input.clear()

        self.map_dropdown.setCurrentIndex(0)
        self.macro_cb.setChecked(False)
        self.dplc_cb.setChecked(False)

        self.map_file_table.clearSelection()

        # Empty the buffer
        self.mapping_set_buffer(None, [], [], "", False)

        # This re-enables the Add button
        self.mapping_update_file_controls()

    def mapping_set_buffer(self, path, frames, frame_labels, map_label, use_macros, *, refresh=True):
        """
        Install loaded or initialized mappings and record their association.
        """
        self.map_frames = frames
        self.frame_labels = frame_labels
        self.map_name_input.setText(map_label)
        self.macro_cb.setChecked(use_macros)
        self.mapping_buffer_path = path

        # Reset the frame index before refreshing controls
        was_blocked = self.frame_spinbox.blockSignals(True)

        try:
            self.frame_spinbox.setRange(0, max(0, len(frames) - 1))
            self.frame_spinbox.setValue(0)

        finally:
            self.frame_spinbox.blockSignals(was_blocked)

        self.piece_controls_state = None

        # Whole-build loading can defer refreshing
        if refresh:
            self._on_sprite_frame_changed(refresh_thumbnails=True)

    def mapping_update_file_controls(self):
        # Disable Add and Enable Load/Save if map asset is loaded
        has_asset = bool(self.map_path_input.text().strip())

        self.btn_map_add.setEnabled(not has_asset)
        self.btn_map_load.setEnabled(has_asset)
        self.btn_map_save.setEnabled(has_asset)

        # Always available to reset the table
        self.btn_map_remove.setEnabled(True)

    def mapping_dplc_browse(self, line_edit):
        # Access project directory
        project_dir = self.project.root_dir
        start_dir = str(project_dir) if project_dir else ""

        # Save dialog for new DPLC file, WITHOUT creating the file
        file_path, _ = QtW.QFileDialog.getSaveFileName(self, "Select DPLC File",
            start_dir, "DPLC Files (*.asm *.bin);;All Files (*)")

        # If successful, store DPLC filepath
        if file_path:
            path = self.project.resolve_asset_path(file_path)
            line_edit.setText(str(path))


    # --------------------------------------------------
    # Palette File Entries
    # --------------------------------------------------
    def palette_entry_new(self):
        """
        Add a palette file to the sprite build.
        """
        # Access project directory
        project_dir = self.project.root_dir
        start_dir = str(project_dir) if project_dir else ""

        # # Save dialog for new palette file, WITHOUT creating the file
        file_path, _ = QtW.QFileDialog.getSaveFileName(self,
            "New Palette File", start_dir, "Palette Files (*.pal *.bin);;All Files (*)")

        # If successful, create a new row under the palette tab
        if file_path:
            path = self.project.resolve_asset_path(file_path)
            previous_count = len(self.pal_rows)

            self.palette_add_entry(str(path))

            if len(self.pal_rows) > previous_count and not path.exists():
                self.palette_new_paths.add(path)

    def palette_entry_load(self, *, prepared=None, refresh=True):
        """
        Apply loaded palette data, preparing it first unless supplied.

        Returns:
            True if successful, False if preparation fails.
        """
        # If not prepared beforehand, do it here
        if prepared is None:
            prepared = self.palette_prepare_load()

        # Preparation failed/cancelled
        if prepared is None:
            return False

        # Install colors and their file associations together
        loaded_colors, layout, new_paths = prepared

        self.palette_colors = loaded_colors
        self.palette_buffer_layout = layout
        self.palette_new_paths = new_paths

        # Set color boxes to loaded colors
        for box, color in zip(self.palette_boxes, self.palette_colors):
            box.set_color(color)

        # Sprite build loading can defer rendering
        if refresh:
            self.render_art_tiles()     # Refresh VRAM
            self.render_sprite_frame()

        return True

    def palette_entry_save(self, *, prepared=None):
        """
        Save palettes, preparing them first unless a result is supplied.

        Returns:
            True if all files saved or no files are configured.
            False on failure or cancellation.
            Earlier files may have saved if a later write fails.
        """
        # If not prepared beforehand, do it here
        if prepared is None:
            prepared = self.palette_prepare_save()

        # Preparation failed/cancelled
        if prepared is None:
            return False

        # No palette file is configured
        if not prepared:
            return True

        save_jobs, layout = prepared

        # Write only after every entry has been prepared
        for path, binary_data in save_jobs:
            try:
                # Write the prepared file
                path.parent.mkdir(parents=True, exist_ok=True)
                with open(path, "wb") as f:
                    f.write(binary_data)

            except (OSError, ValueError) as e:
                QtW.QMessageBox.warning(self,"Palette Save Error",
                    f"Could not save palette file {path.name}:\n{str(e)}")
                return False

            self.palette_new_paths.discard(path)

        # Adopt the layout only after all saves succeed
        self.palette_buffer_layout = layout
        return True

    def palette_prepare_load(self):
        """
        Read configured palettes for eventual loading.

        Returns:
            (loaded colors, layout, new_paths) on success.
            None otherwise.
        """
        try:
            layout = self.palette_get_file_layout()     # (path, line count)
            loaded_colors = [QCOL_BLACK for _ in range(PALETTE_MAXCOLORS)] # Temp buffer of 64 colors
            new_paths = self.palette_new_paths.copy()
            current_index = 0   # Index to load the next color into

            for path, num_lines in layout:
                # Number of colors to load based on number of lines in the entry
                num_colors = num_lines * PALLINE_COLORS

                if path is not None:
                    try:
                        with open(path, "rb") as f:
                            data = f.read(num_colors * 2)   # each color is 2 bytes

                    except FileNotFoundError:
                        # New, unsaved palettes remain black
                        if path not in new_paths:
                            raise

                    else:
                        # Reject files shorter than their configured line count
                        if len(data) != num_colors * 2:
                            raise ValueError(f"{path.name}: expected {num_colors * 2} bytes, but read {len(data)}.")

                        loaded_colors[current_index:current_index + num_colors] = decode_palette(data)

                        # For file association management
                        new_paths.discard(path)

                # Blank paths still reserve their palette lines
                current_index += num_colors

        except (OSError, ValueError) as e:
            QtW.QMessageBox.warning(self, "Palette Load Error", str(e))
            return None

        return loaded_colors, layout, new_paths

    def palette_prepare_save(self):
        """
        Validate palette assignments and prepare file contents for saving.
        (Much of this code was pulled from palette_entry_save).

        Returns:
            (save_jobs, layout) when ready to save.
            () if no palette files are configured.
            None if preparation fails or is canceled.
        """
        try:
            layout = self.palette_get_file_layout()

            # No configured destinations
            if not any(path is not None for path, _ in layout):
                return ()

            # Require palette data loaded or initialized for this build
            if self.palette_buffer_layout is None:
                raise ValueError("Load or initialize palette data for this build before saving.")

            # Map each file to its starting grid line and line count
            previous_ranges = {}
            start_line = 0

            for path, num_lines in self.palette_buffer_layout:
                if path is not None:
                    previous_ranges[path] = (start_line, num_lines)

                # Blank entries still occupy grid lines
                start_line += num_lines

            save_jobs = []
            overwrite_paths = []
            start_line = 0

            for path, num_lines in layout:
                if path is not None:
                    if path.is_dir():
                        raise IsADirectoryError(f"Save destination is a directory: {path}")

                    # Identify changed destinations or assigned lines
                    if previous_ranges.get(path) != (start_line, num_lines):
                        overwrite_paths.append(path)

                    first_color = start_line * 16
                    num_colors = num_lines * 16

                    # Encode the colors assigned to this file
                    binary_data = encode_palette(self.palette_colors[first_color:first_color + num_colors])
                    save_jobs.append((path, binary_data))

                # Blank rows still reserve their grid lines
                start_line += num_lines

            # Confirm changed assignments before returning prepared data
            if not self.file_confirm_overwrites(overwrite_paths):
                return None

        except Exception as e:
            QtW.QMessageBox.warning(self, "Palette Save Error",
                f"Could not prepare palette files:\n{e}")
            return None

        return save_jobs, layout

    def palette_add_entry(self, file_path):
        """
        Add a palette entry to the file manager.
        """
        # Each new file needs at least one available palette line.
        total_lines = sum(int(combo.currentText() or "1") for combo in self.pal_line_combos)
        if total_lines >= 4:
            return

        # Filepath text box
        path_input = QtW.QLineEdit(file_path)

        # Line count dropdown (1-4)
        line_combo = QtW.QComboBox()
        line_combo.addItem("1")    # Prime it with 1 for palette_update_file_controls
        line_combo.setToolTip("Number of palette lines used by this file")
        line_combo.currentIndexChanged.connect(self.palette_update_file_controls)

        # Track the combo boxes in a list for evaluation
        self.pal_line_combos.append(line_combo)
        self.pal_rows.append((path_input, line_combo))

        # Add the widgets to the table
        row = self.pal_file_table.rowCount()
        self.pal_file_table.insertRow(row)

        self.pal_file_table.setCellWidget(row, 0, path_input)
        self.pal_file_table.setCellWidget(row, 1, line_combo)

        self.pal_file_table.selectRow(row)

        # Seems redundant, but we need an initial evaluation
        self.palette_update_file_controls()

    def palette_remove_entry(self, row=None):
        """
        Removes a palette entry from the file manager.
        """
        if row is None:
            row = self.pal_file_table.currentRow()

        if not 0 <= row < len(self.pal_rows):
            return

        # Remove references before the table deletes the widgets
        path_input, line_combo = self.pal_rows.pop(row)
        self.pal_line_combos.remove(line_combo)

        self.pal_file_table.removeRow(row)

        if self.pal_rows:
            self.pal_file_table.selectRow(min(row, len(self.pal_rows) - 1))

        self.palette_update_file_controls()

    def palette_move_entry(self, logical_index, old_position, new_position):
        """
        Move a palette entry in the file manager to another line.
        """
        if old_position == new_position:
            return

        # Collect filepaths and line counts
        entries = [
            (path_input.text(), int(line_combo.currentText() or "1"))
            for path_input, line_combo in self.pal_rows
        ]

        # Reorder file assignments
        entry = entries.pop(old_position)
        entries.insert(new_position, entry)

        # Restore header order; apply the move to the cell values instead
        header = self.pal_file_table.verticalHeader()
        previous_state = header.blockSignals(True)
        header.moveSection(new_position, old_position)
        header.blockSignals(previous_state)

        # Update the existing widgets
        for widgets, entry in zip(self.pal_rows, entries):
            path_input, line_combo = widgets
            file_path, line_count = entry

            path_input.setText(file_path)

            previous_state = line_combo.blockSignals(True)
            line_combo.clear()
            line_combo.addItems(["1", "2", "3", "4"])
            line_combo.setCurrentText(str(line_count))
            line_combo.blockSignals(previous_state)

        self.pal_file_table.selectRow(new_position)
        self.palette_update_file_controls()

    def palette_update_file_controls(self):
        """
        Enable/Disable controls based on file manager state.
        """
        # Sum the values of all active line combo boxes
        total_lines = sum(int(combo.currentText() or "1") for combo in self.pal_line_combos)

        # Enable/Disable buttons accordingly
        count = len(self.pal_rows)
        selected_row = self.pal_file_table.currentRow()

        self.btn_pal_add.setEnabled(total_lines < 4)
        self.btn_pal_load.setEnabled(count > 0)
        self.btn_pal_save.setEnabled(count > 0)
        self.btn_pal_remove.setEnabled(0 <= selected_row < count)

        # Dynamically restrict each dropdown so the user can't select a value that exceeds 4
        for combo in self.pal_line_combos:
            current_val = int(combo.currentText() or "1")
            # Max allowed for this specific combo is 4 minus the lines taken up
            max_allowed = 4 - (total_lines - current_val)

            # Rebuild dropdown options
            combo.blockSignals(True)
            combo.clear()

            for _i in range(1, max_allowed + 1):
                combo.addItem(str(_i))

            combo.setCurrentText(str(current_val))
            combo.blockSignals(False)

    def palette_open_color_library(self, col_idx):
        # Get active color from the clicked box
        active_color = self.palette_colors[col_idx]

        # Run color picker window
        dialog = ColorLibrary(active_color, self)
        if dialog.exec():
            # Apply picked color to active index
            new_color = dialog.get_color()
            self.palette_colors[col_idx] = new_color

            # Update color box
            self.palette_boxes[col_idx].set_color(new_color)
            # Refresh VRAM after loading new palette
            self.render_art_tiles()
            # Refresh the active frame with the new colors
            self.render_sprite_frame()

    def palette_get_file_layout(self):
        """
        Get the configured palette layout in table order.

        Returns:
            Tuple: (absolute Path or None, line count) for each entry.
            (Note: Blank paths reserve their configured palette lines.)
        """
        layout = []
        seen_paths = set()
        total_lines = 0

        # Validate line allocation
        for path_input, line_combo in self.pal_rows:
            num_lines = int(line_combo.currentText() or "1")
            total_lines += num_lines

            if not 1 <= num_lines <= 4 or total_lines > 4:
                raise ValueError("Palette entries must fit within four lines.")

            # Blank paths remain unassigned
            path_text = path_input.text().strip()
            path = None

            if path_text:
                # Resolve relative paths against the project root
                path = self.project.resolve_asset_path(path_text)

                # Prevents writing to the same palette file twice from separate entries
                if path in seen_paths:
                    raise ValueError(f"Palette file listed more than once: {path}")

                seen_paths.add(path)

            # Preserve row order and reserved lines
            layout.append((path, num_lines))

        # Includes blank entries as they reserve palette lines
        return tuple(layout)

    # --------------------------------------------------
    # Rendering
    # --------------------------------------------------
    def render_art_tiles(self):
        """
        Renders the virtual VRAM contents into an image and refreshes the viewer canvas.
        """
        # Render VRAM tile grid
        image = render_tile_grid(self.vram_tiles, self.palette_colors,
            palette_line=self.viewer_line_combo.currentIndex())

        # Scale up 2x
        pixmap = QPixmap.fromImage(image)
        scaled_pixmap = pixmap.scaled(image.width() * 2, image.height() * 2,
            Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.FastTransformation)

        self.vram_label.setPixmap(scaled_pixmap)

    def sprite_build_frame_image(self, frame_idx, show_overlays=False):
        # Synchronize shared sources once before composing the frame.
        self.renderer.prepare(self.vram_tiles, self.palette_colors,
            art_revision=self.art_preview_revision)
        frame_data = self.map_frames[frame_idx] if 0 <= frame_idx < len(self.map_frames) else []
        base_tile = self.vram_spinbox.value()
        base_palette = self.sprpal_spinbox.value()

        # If no overlay elements are needed, just use the shared renderer
        if not show_overlays:
            return self.renderer.render_frame(frame_data,
                canvas_size=(self.sprite_canvas_width, self.sprite_canvas_height),
                base_tile=base_tile, base_palette=base_palette)
        
        # Otherwise, use the Sprite Editor's native renderer
        canvas_w, canvas_h = self.sprite_canvas_width, self.sprite_canvas_height
        center_x, center_y = canvas_w // 2, canvas_h // 2

        image = QImage(canvas_w, canvas_h, QImage.Format.Format_ARGB32)
        image.fill(Qt.GlobalColor.transparent)

        if self.origin_checkbox.isChecked():
            # Draw an origin crosshair to easily see the sprite's anchor pivot
            crosshair_color = QColor(255, 0, 255, 100)  # To-Do: Make this an option (ColorPicker)
            for _x in range(canvas_w):
                image.setPixelColor(_x, center_y, crosshair_color)
            for _y in range(canvas_h):
                image.setPixelColor(center_x, _y, crosshair_color)

        if not 0 <= frame_idx < len(self.map_frames):
            return image

        painter = QPainter(image)

        try:
            # Draw lower indices last, preserving indices for hover/selection.
            for piece_index in range(len(frame_data) - 1, -1, -1):
                piece = frame_data[piece_index]
                piece_image = self.renderer.render_piece(piece, base_tile=base_tile, base_palette=base_palette)

                x = center_x + piece["x"]
                y = center_y + piece["y"]

                # Selected pieces never receive the hover effect
                hovered = show_overlays and piece_index == self.hovered_piece and piece_index not in self.selected_pieces

                # Unselected pieces with the mouse over them are transparent
                if hovered:
                    painter.fillRect(x, y, piece["width"] * 8, piece["height"] * 8,
                        QColor(255, 255, 0, 18))
                    painter.setOpacity(0.45)

                # Draw the cached image at its current position
                painter.drawImage(x, y, piece_image)

                # Restore opacity before drawing the next piece
                painter.setOpacity(1.0)

        finally:
            painter.end()

        # Draw selection outlines after all sprite pieces
        if show_overlays and self.selected_pieces:
            painter = QPainter(image)
            painter.setPen(QColor(255, 255, 0))
            painter.setBrush(Qt.BrushStyle.NoBrush)

            for index in sorted(self.selected_pieces):
                if not 0 <= index < len(frame_data):
                    continue

                piece = frame_data[index]

                painter.drawRect(center_x + piece["x"], center_y + piece["y"],
                    piece["width"] * 8 - 1, piece["height"] * 8 - 1)

            painter.end()

        return image

    def render_sprite_frame(self):
        """
        Draw the current sprite frame on the editor canvas.
        """
        image = self.sprite_build_frame_image(self.frame_spinbox.value(), show_overlays=True)
        self.render_sprite_image(image)

    def render_sprite_image(self, image):
        pixmap = QPixmap.fromImage(image)
        scaled_pixmap = pixmap.scaled(
            image.width() * self.sprite_zoom,
            image.height() * self.sprite_zoom,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.FastTransformation,
        )
        self.sprite_label.setPixmap(scaled_pixmap)
