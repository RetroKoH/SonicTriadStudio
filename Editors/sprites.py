"""Sprite Editor

File Manager and rendering with shared functions now working.
Thumbnails and editing tools are still under construction.
"""

from pathlib import Path
from copy import deepcopy

import PyQt6.QtWidgets as QtW
from PyQt6.QtCore import Qt, QEvent, QObject, QPoint, QRect, QSize
from PyQt6.QtGui import QColor, QImage, QPainter, QPixmap, QIcon

from constants import PALLINE_COLORS, PALETTE_MAXCOLORS, QCOL_BLACK
from AssetIO.art import decode_art, encode_art
from AssetIO.palettes import decode_palette, encode_palette
from AssetIO.mappings import *
from Rendering.tiles import render_tile_grid
from Rendering.sprites import SpriteRenderer
from UI.collapse_panel import CollapsiblePanel
from UI.color_box import MiniColorBox
from UI.file_toolbar import create_file_toolbar
from UI.frame_list import SpriteFrameList
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

        # Used for DPLC rendering
        self.static_vram_tiles = {}
        self.dplc_vram_cache = {}

        # Tells the sprite map list when sprite data changes
        self.art_preview_revision = 0

        # Used in the art file manager
        self.art_rows = []  # Stores row items in the table for art loading

        # Loaded file associated with each art row's path widget
        self.art_buffer_paths = {}
        self.art_buffer_compressions = {}  # Compression used when each buffer was loaded

        # File associated with the initialized mapping buffer
        self.mapping_buffer_path = None

        # Stores the parsed mapping data in memory
        self.map_frames = []

        # Frame labels (I'll work this into map_frames later)
        self.frame_labels = []

        # Stores the parsed DPLC data in memory
        self.dplc_frames = []
        # Frame labels (I'll work this into map_frames later)
        self.dplc_frame_labels = []

        # File associated with the initialized DPLC buffer
        self.dplc_buffer_path = None
        self.dplc_buffer_format = None
        self.dplc_use_macros = False

        # Sprite viewer canvas
        self.sprite_canvas_width = 256
        self.sprite_canvas_height = 256
        self.sprite_zoom = 2

        # Mapping piece selection and dragging
        self.hovered_piece = None   # Hovered pieces will have transparency if not selected
        self.selected_pieces = set()
        self.piece_drag = None      # Remember where the mouse and piece were when dragging began
        self.selection_drag = None

        # State of mapping piece editor and list
        self.piece_controls_state = None
        self.piece_list_state = None

        # DPLC entry selection (independent of mapping piece selection)
        self.selected_entry = None

        # State of DPLC entry editor and list
        self.entry_controls_state = None
        self.entry_list_state = None

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
        self.vram_spinbox = create_spinbox(minimum=0, maximum=2047, display_base=16, prefix="$",
            width=50, tooltip="Starting VRAM Tile Index (Hex)")
        self.sprpal_spinbox = create_spinbox(minimum=0, maximum=3,
            width=40, tooltip="Base Palette Line")
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
        self.btn_map_load = create_pushbutton("Load", tooltip="Load configured mappings (and DPLCs)",
            width=50, on_clicked=self.mapping_entry_load, enabled=False)
        self.btn_map_save = create_pushbutton("Save", tooltip="Save configured mappings (and DPLCs)",
            width=50, on_clicked=self.mapping_entry_save, enabled=False)
        self.btn_map_remove = create_pushbutton("Remove", tooltip="Remove mappings data",
            width=50, on_clicked=lambda: self.mapping_remove_entry(), enabled=False)
        self.map_dropdown = QtW.QComboBox()
        self.macro_cb = QtW.QCheckBox("Save with Macros")
        self.macro_cb.setToolTip("Use macros for mapping and DPLC ASM output.")
        self.dplc_cb = QtW.QCheckBox("Use DPLCs")
        self.dplc_cb.setToolTip("Use DPLCs when loading tiles from the first art file.")
        self.map_file_table = QtW.QTableWidget(2, 3)
        self.map_path_input = QtW.QLineEdit()
        self.map_name_input = QtW.QLineEdit()
        self.dplc_path_input = QtW.QLineEdit()
        self.dplc_name_input = QtW.QLineEdit()

        # DPLC status label (Updates with usage)
        self.dplc_status_label = QtW.QLabel()

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
        self.viewer_art_combo = create_combobox(
            tooltip="Choose which art tile set to view. Art can only be directly edited in buffers, not in VRAM.",
            items=["VRAM"]
        )
        self.viewer_line_combo = create_combobox(
            tooltip="Choose a palette line to view art tiles with.",
            items=["Line 0", "Line 1", "Line 2", "Line 3"])
        self.vram_label = QtW.QLabel()
        self.vram_scroll = create_scrollarea(self.vram_label, vertical_policy=Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.arrange_tiles = create_pushbutton("Arrange Tiles",
            width=90, tooltip="Arrange tiles by sprite usage", on_clicked=self.art_arrange_tiles, enabled=False)
        self.strip_tiles = create_pushbutton("Strip Unused Tiles",
            width=110, tooltip="Remove all unused tiles", on_clicked=self.art_strip_unused_tiles, enabled=False)
        self.pad_tiles = create_checkbox("Pad Tiles")
        self.pad_tiles.setToolTip("For Arrange Tiles: complete partial pieces with blank tiles.\n"
            "Positions outside this buffer's loaded range are treated as blank.")

        # ui_build_sprite_viewer()
        self.sprite_frame_list = SpriteFrameList()

        # ui_build_map_editor()
        self.map_edit_box = QtW.QGroupBox()
        self.map_editor_tabs = QtW.QTabWidget() # Mapping Pieces/DPLC Entries tabs
        self.frame_spinbox = create_spinbox(minimum=0, maximum=0, on_value_changed=self._on_sprite_frame_changed)
        self.frame_name_input = create_lineedit(tooltip="Name of the mapping frame (in ASM files)")
        self.btn_frame_add = create_pushbutton("Add", tooltip="Add a new frame",
            on_clicked=self.sprite_add_frame, enabled=True)
        self.btn_frame_remove = create_pushbutton("Remove", tooltip="Remove the current frame",
            on_clicked=self.sprite_remove_frame, enabled=False)
        self.btn_frame_copy = create_pushbutton("Copy", tooltip="Duplicate the current mapping frame",
            on_clicked=self.sprite_clone_frame, enabled=False)
        self.btn_frame_clone = create_pushbutton("Clone", tooltip="Clone the current frame, and its tiles",
            on_clicked=self.sprite_clone_frame_and_tiles, enabled=False)
        self.btn_piece_add = create_pushbutton("Add Piece", tooltip="Add a piece to the current frame",
            on_clicked=self.sprite_add_piece, enabled=False)
        self.btn_piece_remove = create_pushbutton("Remove Pieces", width=85, tooltip="Remove the selected pieces",
            on_clicked=self.sprite_remove_pieces, enabled=False)
        self.index_label = create_label("Piece Properties", object_name="infoLabel")

        # ui_build_piece_list()
        self.piece_list_table = QtW.QTableWidget(0, 1)

        # ui_build_dplc_editor()
        self.entry_list_table = QtW.QTableWidget(0, 1)
        self.btn_entry_add = create_pushbutton("Add Entry", width=75, tooltip="Add an entry to this frame's DPLC",
            on_clicked=self.dplc_add_entry, enabled=False)
        self.btn_entry_remove = create_pushbutton("Remove Entry", width=95,
            tooltip="Remove the selected entry from this frame's DPLC",
            on_clicked=self.dplc_remove_entry, enabled=False)

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
        self.dplc_tile_spinbox = create_spinbox(minimum=0, maximum=4095,
            display_base=16, prefix="$", width=55, keyboard_tracking=False,
            tooltip="Source tile index in the first art buffer", enabled=False)
        self.dplc_count_spinbox = create_spinbox(minimum=1, maximum=16,
            value=1, width=45, keyboard_tracking=False,
            tooltip="Number of tiles to load for this entry", enabled=False)

        # Group widgets by type
        self.piece_spinboxes = {
            "x": self.piece_x_spinbox,
            "y": self.piece_y_spinbox,
            "tile": self.piece_tile_spinbox,
            "width": self.piece_width_spinbox,
            "height": self.piece_height_spinbox,
            "palette": self.piece_palette_spinbox
        }
        self.piece_checkboxes = {
            "priority": self.piece_priority_checkbox,
            "x_flip": self.piece_x_flip_checkbox,
            "y_flip": self.piece_y_flip_checkbox
        }
        self.entry_spinboxes = {
            "tile": self.dplc_tile_spinbox,
            "count": self.dplc_count_spinbox
        }
        for field, spinbox in self.piece_spinboxes.items():
            spinbox.valueChanged.connect(lambda value, field=field:
                self.sprite_edit_piece_property(field, value))

        for field, checkbox in self.piece_checkboxes.items():
            checkbox.clicked.connect(lambda checked, field=field:
                self.sprite_edit_piece_property(field, checked))

        for field, spinbox in self.entry_spinboxes.items():
            spinbox.valueChanged.connect(lambda value, field=field:
                self.dplc_edit_entry_property(field, value))

        self.ui_init()
        self.sprite_refresh_editing_ui()

        self.vram_spinbox.valueChanged.connect(self.art_refresh_vram)
        self.dplc_cb.toggled.connect(self._on_dplc_settings_changed)
        self.map_dropdown.currentIndexChanged.connect(self._on_dplc_settings_changed)
        self.dplc_path_input.textChanged.connect(self._on_dplc_settings_changed)
        self.sprpal_spinbox.valueChanged.connect(self.sprite_refresh_previews)
        self.origin_checkbox.toggled.connect(self.render_sprite_frame)

        # Note: Viewing a buffer does not affect the art used by sprite rendering (in VRAM)
        self.viewer_art_combo.currentIndexChanged.connect(self.render_art_tiles)
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
            on_save=self.file_sprite_save, on_save_as=self.file_sprite_save_as,
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

        # Scrollable Sprite Viewer
        self.sprite_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.sprite_label.setMargin(0)
        self.sprite_label.setFrameShape(QtW.QFrame.Shape.NoFrame)
        self.sprite_label.setFixedSize(
            self.sprite_canvas_width * self.sprite_zoom,
            self.sprite_canvas_height * self.sprite_zoom)
        self.sprite_label.setMouseTracking(True)
        self.sprite_label.installEventFilter(self)  # install for click and drag mechanics

        # Selection rectangle, positioned manually over the sprite canvas
        # (To-Do: Color based on theme, or by preference)
        self.selection_box = QtW.QFrame(self.sprite_label)
        self.selection_box.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.selection_box.setStyleSheet("""
            QFrame {
                background-color: rgba(100, 180, 255, 45);
                border: 1px solid rgba(100, 180, 255, 220);
            }
        """)
        self.selection_box.hide()

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

        table.itemSelectionChanged.connect(self.art_update_file_controls)

        layout.addWidget(table, stretch=1)
        self.art_update_file_controls()

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

        # Load sprite format presets (mappings and DPLCs) (To-Do: Add custom support)
        for format_id, preset in MAP_FORMATS.items():
            self.map_dropdown.addItem(preset["name"], format_id)
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
        btn_dplc_browse.clicked.connect(lambda: self.mapping_dplc_browse(self.dplc_path_input))

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
        layout.addWidget(self.dplc_status_label)
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
        header.setSectionsMovable(True)
        header.sectionMoved.connect(self.palette_move_entry)

        # Let the filename column take the remaining space
        header = table.horizontalHeader()
        header.setSectionResizeMode(0, QtW.QHeaderView.ResizeMode.Stretch)
        table.setColumnWidth(1, 75)
        table.verticalHeader().setDefaultSectionSize(30)

        table.itemSelectionChanged.connect(self.palette_update_file_controls)

        layout.addWidget(table, stretch=1)
        self.palette_update_file_controls()

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

        # Mappings: shared frame controls and separate piece/DPLC editors
        self.editing_tabs.addTab(self.ui_build_map_editor(), "Mapping Data")

        editing_layout.addWidget(self.editing_tabs, stretch=2)

        self.editing_tabs.currentChanged.connect(self.framelist_refresh)

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
        viewer_controls.addWidget(QtW.QLabel("Art View:"))
        viewer_controls.addWidget(self.viewer_art_combo)
        self.viewer_art_combo.setFixedWidth(100)
        viewer_controls.addStretch()
        viewer_controls.addWidget(QtW.QLabel("Palette View:"))
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
        tile_controls.addWidget(self.pad_tiles)

        tile_controls.addStretch()
        art_viewer_layout.addLayout(tile_controls)

        return self.vram_box

    def ui_build_sprite_viewer(self):
        # List of frame thumbnails
        self.frame_thumbnail_keys = []
        frame_list = self.sprite_frame_list

        frame_list.setViewMode(QtW.QListView.ViewMode.IconMode)
        frame_list.setFlow(QtW.QListView.Flow.TopToBottom)
        frame_list.setWrapping(False)
        frame_list.setMovement(QtW.QListView.Movement.Snap)
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

        # Establish drag-and-drop
        frame_list.setSortingEnabled(False)
        frame_list.setDragDropMode(QtW.QAbstractItemView.DragDropMode.InternalMove)
        frame_list.setDefaultDropAction(Qt.DropAction.MoveAction)
        frame_list.setDragEnabled(True)
        frame_list.setAcceptDrops(True)
        frame_list.setDragDropOverwriteMode(False)
        frame_list.setAutoScroll(True)

        frame_list.frameMoveRequested.connect(self.sprite_move_frame)

        frame_list.currentRowChanged.connect(self.on_framelist_selection_changed)

        frame_list.viewport().installEventFilter(self)
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
        self.frame_name_input.editingFinished.connect(self._on_sprite_frame_label_changed)

        frame_controls.addStretch()
        map_editor.addLayout(frame_controls)

        frame_buttons = QtW.QHBoxLayout()
        frame_buttons.setSpacing(4)

        frame_buttons.addWidget(self.btn_frame_add)
        frame_buttons.addWidget(self.btn_frame_remove)
        frame_buttons.addWidget(self.btn_frame_copy)
        frame_buttons.addWidget(self.btn_frame_clone)

        frame_buttons.addStretch()
        map_editor.addLayout(frame_buttons)

        # Frame controls apply to both inner tabs.
        self.map_editor_tabs.addTab(self.ui_build_piece_editor(), "Mapping Pieces")
        self.map_editor_tabs.addTab(self.ui_build_dplc_editor(), "DPLC Entries")
        map_editor.addWidget(self.map_editor_tabs, stretch=1)

        return self.map_edit_box

    def ui_build_piece_editor(self):
        tab = QtW.QWidget()
        piece_editor = QtW.QVBoxLayout(tab)
        piece_editor.addWidget(self.ui_build_entry_list(self.piece_list_table, "Piece List",
            self.sprite_piece_list_selection_changed), stretch=1)

        piece_buttons = QtW.QHBoxLayout()
        piece_buttons.setSpacing(4)

        piece_buttons.addWidget(self.btn_piece_add)
        piece_buttons.addWidget(self.btn_piece_remove)

        piece_buttons.addStretch()
        piece_editor.addLayout(piece_buttons)

        piece_editor.addSpacing(8)

        piece_controls = QtW.QVBoxLayout()
        piece_controls.addLayout(self.ui_build_piece_controls())
        piece_editor.addLayout(piece_controls)

        return tab

    def ui_build_dplc_editor(self):
        tab = QtW.QWidget()
        dplc_editor = QtW.QVBoxLayout(tab)
        dplc_editor.addWidget(self.ui_build_entry_list(self.entry_list_table, "Entry List",
            self.dplc_entry_list_selection_changed), stretch=1)
        self.entry_list_table.setSelectionMode(QtW.QAbstractItemView.SelectionMode.SingleSelection)

        entry_buttons = QtW.QHBoxLayout()
        entry_buttons.setSpacing(4)

        entry_buttons.addWidget(self.btn_entry_add)
        entry_buttons.addWidget(self.btn_entry_remove)

        entry_buttons.addStretch()
        dplc_editor.addLayout(entry_buttons)

        dplc_editor.addSpacing(8)

        entry_controls = QtW.QVBoxLayout()
        entry_controls.addLayout(self.ui_build_entry_controls())
        dplc_editor.addLayout(entry_controls)

        return tab

    def ui_build_entry_list(self, table, header, connect=None):
        table.setHorizontalHeaderLabels([header])

        table.setSelectionBehavior(QtW.QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QtW.QAbstractItemView.SelectionMode.ExtendedSelection)
        table.setEditTriggers(QtW.QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setSortingEnabled(False)

        table.horizontalHeader().setDefaultAlignment(Qt.AlignmentFlag.AlignLeft)
        table.horizontalHeader().setSectionResizeMode(0, QtW.QHeaderView.ResizeMode.Stretch)

        table.verticalHeader().setSectionResizeMode(QtW.QHeaderView.ResizeMode.Fixed)
        table.verticalHeader().setDefaultSectionSize(26)

        # Minimum height; the inner tab supplies the remaining space.
        table.setMinimumHeight(100)

        if connect is not None:
            table.itemSelectionChanged.connect(connect)

        return table

    def ui_build_piece_controls(self):
        piece_layout = QtW.QVBoxLayout()

        piece_layout.addWidget(self.index_label)

        # Row 1: Position
        position_row = QtW.QHBoxLayout()
        position_row.addWidget(QtW.QLabel("X:"))
        position_row.addWidget(self.piece_x_spinbox)
        position_row.addStretch()
        position_row.addWidget(QtW.QLabel("Y:"))
        position_row.addWidget(self.piece_y_spinbox)
        position_row.addStretch()

        # Row 2: Art tile and size dimensions
        size_row = QtW.QHBoxLayout()
        size_row.addWidget(QtW.QLabel("Tile:"))
        size_row.addWidget(self.piece_tile_spinbox)
        size_row.addStretch()
        size_row.addWidget(QtW.QLabel("Width:"))
        size_row.addWidget(self.piece_width_spinbox)
        size_row.addStretch()
        size_row.addWidget(QtW.QLabel("Height:"))
        size_row.addWidget(self.piece_height_spinbox)
        size_row.addStretch()

        # Row 3: Palette and flags
        flag_row = QtW.QHBoxLayout()
        flag_row.addWidget(QtW.QLabel("Palette:"))
        flag_row.addWidget(self.piece_palette_spinbox)
        flag_row.addStretch()
        flag_row.addWidget(self.piece_x_flip_checkbox)
        flag_row.addStretch()
        flag_row.addWidget(self.piece_y_flip_checkbox)
        flag_row.addStretch()
        flag_row.addWidget(self.piece_priority_checkbox)
        flag_row.addStretch()

        # Stack the rows
        piece_layout.addLayout(position_row)
        piece_layout.addLayout(size_row)
        piece_layout.addLayout(flag_row)

        return piece_layout

    def ui_build_entry_controls(self):
        entry_layout = QtW.QVBoxLayout()

        self.entry_index_label = create_label("Entry Properties", object_name="infoLabel")
        entry_layout.addWidget(self.entry_index_label)

        # Row 1: Art tile location and count
        tile_row = QtW.QHBoxLayout()
        tile_row.addWidget(QtW.QLabel("Tile Loc:"))
        tile_row.addWidget(self.dplc_tile_spinbox)
        tile_row.addStretch()
        tile_row.addWidget(QtW.QLabel("Tile Count:"))
        tile_row.addWidget(self.dplc_count_spinbox)
        tile_row.addStretch()

        # Stack the rows
        entry_layout.addLayout(tile_row)

        return entry_layout


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

        prepared_dplcs = self.dplc_prepare_load()
        if prepared_dplcs is None:
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
            self.mapping_entry_load(prepared=prepared_mappings, prepared_dplcs=prepared_dplcs, refresh=False)

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

    def file_sprite_save_as(self):
        """
        Save the current build under a new build name, keeping asset paths.
        """
        self.file_sprite_save(save_as=True)
    
    def file_sprite_save(self, *, save_as=False):
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

        # SAVE AS block
        if save_as:
            # Suggest an unused name without replacing an existing build.
            sprites_dict = project.data.get("sprites", {})
            base_name = f"{sprite_name} Copy"
            suggested_name = base_name
            suffix = 2
            while suggested_name in sprites_dict:
                suggested_name = f"{base_name} {suffix}"
                suffix += 1

            new_name, ok = QtW.QInputDialog.getText(self, "Save Sprite Build As",
                "Enter a new name for this sprite build:", text=suggested_name)
            if not ok:
                return False

            new_name = new_name.strip()
            if not new_name:
                QtW.QMessageBox.warning(self, "Invalid Name",
                    "Please enter a nonblank sprite build name.")
                return False

            if new_name == "No Sprites Found" or new_name in sprites_dict:
                QtW.QMessageBox.warning(self, "Invalid Name",
                    "That name is reserved or already belongs to a sprite build. "
                    "Please choose another name.")
                return False

            # Collect from the original definition but save under the new key.
            sprite_name = new_name

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

        prepared_dplcs = self.dplc_prepare_save()
        if prepared_dplcs is None:
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

        if prepared_dplcs:
            path, _ = prepared_dplcs
            destinations.append((path, "DPLCs"))

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

        # Save mappings and DPLCs
        if not self.mapping_entry_save(prepared=prepared_mappings, prepared_dplcs=prepared_dplcs):
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
            if save_as:
                # Add new name to the dropdown
                self.spr_dropdown.addItem(sprite_name,
                    userData=self.project_sprite_builds[sprite_name])
            
            for index in range(self.spr_dropdown.count()):
                name = self.spr_dropdown.itemText(index)

                if name in self.project_sprite_builds:
                    self.spr_dropdown.setItemData(
                        index, self.project_sprite_builds[name])

                if save_as:
                    # Keep loaded buffers and file associations. The normal dropdown
                    # handler would clear them while switching to the new build.
                    self.spr_dropdown.setCurrentText(sprite_name)
                    self._current_dropdown_index = self.spr_dropdown.currentIndex()

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
        config["format"] = (self.map_dropdown.currentData()
            if self.map_dropdown is not None
            else config.get("format", 1)) # Default to Sonic 1

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
        if map_path or self.dplc_path_input.text().strip():
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

        format_index = self.map_dropdown.findData(sprite_data.get("format", 1))
        self.map_dropdown.setCurrentIndex(max(0, format_index))

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
        """
        Clear loaded assets and reset previews, optionally clearing file manager entries.
        """
        # Clear sprite piece (and DPLC) selection
        self.sprite_clear_selection(refresh=False)
        self.selected_entry = None
        self.entry_controls_state = None
        self.entry_list_state = None

        # Clear palette to black and invalidate file association
        self.palette_buffer_layout = None
        black = QColor(0, 0, 0)
        self.palette_colors = [black for _i in range(64)]
        for box in self.palette_boxes:
            box.set_color(black)

        # Clear art buffers and their file associations
        self.art_buffer_paths.clear()
        self.art_buffer_compressions.clear()
        self.dplc_frames.clear()
        self.dplc_frame_labels.clear()
        self.dplc_buffer_path = None
        self.dplc_buffer_format = None
        self.dplc_use_macros = False
        self.dplc_vram_cache.clear()
        self.static_vram_tiles = {}

        # Clear Art Tiles
        for _, _, _, _, art_tiles in self.art_rows:
            art_tiles.clear()

        # Flush VRAM and invalidate cached previews
        self.vram_tiles = {}
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
        self.sprite_refresh_previews() # Refresh canvas AND thumbnails

        if clear_file_manager:
            self.filemanager_clear()


    # --------------------------------------------------
    # Sprite: Control Functions
    # --------------------------------------------------
    def sprite_begin_box_select(self, position, additive):
        frame_index = self.frame_spinbox.value()
        if not 0 <= frame_index < len(self.map_frames):
            return

        self.hovered_piece = None

        self.selection_drag = {
            "frame": frame_index,
            "origin": position.toPoint(),
            "initial_selection": (self.selected_pieces.copy() if additive else set()),
            "started": False
        }

    def sprite_update_box_select(self, position):
        drag = self.selection_drag
        if drag is None:
            return

        frame_index = drag["frame"]

        if frame_index != self.frame_spinbox.value() or not 0 <= frame_index < len(self.map_frames):
            self.sprite_end_box_select()
            return

        point = position.toPoint()

        # Keep the rectangle within the sprite canvas
        point = QPoint(
            max(0, min(self.sprite_label.width() - 1, point.x())),
            max(0, min(self.sprite_label.height() - 1, point.y())),
        )

        if not drag["started"]:
            distance = (point - drag["origin"]).manhattanLength()

            if distance < QtW.QApplication.startDragDistance():
                return

            drag["started"] = True

        # Normalization allows dragging in any direction
        selection_rect = QRect(drag["origin"], point).normalized()

        self.selection_box.setGeometry(selection_rect)
        self.selection_box.show()
        self.selection_box.raise_()

        center_x = self.sprite_canvas_width // 2
        center_y = self.sprite_canvas_height // 2
        zoom = self.sprite_zoom

        intersecting = set()

        for index, piece in enumerate(self.map_frames[frame_index]):
            # Convert mapping bounds to displayed canvas coordinates
            piece_rect = QRect(
                (center_x + piece["x"]) * zoom,
                (center_y + piece["y"]) * zoom,
                piece["width"] * 8 * zoom,
                piece["height"] * 8 * zoom,
            )

            if selection_rect.intersects(piece_rect):
                intersecting.add(index)

        selection = drag["initial_selection"] | intersecting

        if selection != self.selected_pieces:
            self.selected_pieces = selection
            self.sprite_refresh_selection_ui()
            self.render_sprite_frame()

    def sprite_end_box_select(self):
        self.selection_drag = None
        self.selection_box.hide()

    def sprite_mouse_to_mapping(self, position):
        x = int(position.x() // self.sprite_zoom)
        x -= self.sprite_canvas_width // 2

        y = int(position.y() // self.sprite_zoom)
        y -= self.sprite_canvas_height // 2

        return x, y

    def sprite_piece_at(self, x, y):
        frame_index = self.frame_spinbox.value()
        if not 0 <= frame_index < len(self.map_frames):
            return None

        pieces = self.map_frames[frame_index]

        # Lower indices render on top, so check them first.
        for index, piece in enumerate(pieces):
            piece = pieces[index]

            left = piece["x"]
            top = piece["y"]
            width = piece["width"] * 8
            height = piece["height"] * 8

            if left <= x < left + width and top <= y < top + height:
                return index

        return None

    def sprite_update_hover(self, position=None, *, redraw=True):
        piece_index = None

        if position is not None:
            inside_canvas = (
                    0 <= position.x() < self.sprite_label.width()
                    and 0 <= position.y() < self.sprite_label.height()
            )

            if inside_canvas:
                x, y = self.sprite_mouse_to_mapping(position)
                piece_index = self.sprite_piece_at(x, y)

        if piece_index != self.hovered_piece:
            self.hovered_piece = piece_index

            if redraw:
                self.render_sprite_frame()

    def sprite_begin_drag(self, position, modifiers):
        x, y = self.sprite_mouse_to_mapping(position)
        piece_index = self.sprite_piece_at(x, y)
        ctrl = bool(modifiers & Qt.KeyboardModifier.ControlModifier)

        # Clear everything pertaining to click/drag
        self.piece_drag = None
        self.sprite_end_box_select()

        # Clicking empty space clears selection without Ctrl
        # Also starts a potential box-selection gesture
        if piece_index is None:
            if not ctrl:
                self.selected_pieces.clear()

            self.sprite_begin_box_select(position, additive=ctrl)
            self.sprite_refresh_selection_ui()
            self.render_sprite_frame()
            return

        # Multi-select pieces
        if ctrl:
            if piece_index in self.selected_pieces:
                # Ctrl-click removes this piece without starting a drag
                self.selected_pieces.remove(piece_index)
                self.sprite_refresh_selection_ui()
                self.render_sprite_frame()
                return

            self.selected_pieces.add(piece_index)

        elif piece_index not in self.selected_pieces:
            # Clicking a new piece replaces the selection
            self.selected_pieces = {piece_index}

        # Clicking an already-selected piece preserves the group
        frame_index = self.frame_spinbox.value()
        pieces = self.map_frames[frame_index]

        start_positions = {
            index: (pieces[index]["x"], pieces[index]["y"])
            for index in self.selected_pieces
        }

        # Contains the original position of every selected piece
        self.piece_drag = (frame_index, x, y, start_positions)

        self.sprite_refresh_selection_ui()
        self.render_sprite_frame()

    def sprite_drag_piece(self, position):
        if self.piece_drag is None:
            return

        frame_index, mouse_x, mouse_y, start_positions = self.piece_drag

        # Cancel if the current frame changed (Clear & Redraw)
        if (
            frame_index != self.frame_spinbox.value()
            or not 0 <= frame_index < len(self.map_frames)
        ):
            # This removes any old selection outlines
            self.sprite_clear_selection()
            self.render_sprite_frame() # don't update thumbnails here
            return

        pieces = self.map_frames[frame_index]

        # Cancel if the current frame's piece data has changed (Clear & Redraw)
        if not start_positions or any(
            not 0 <= index < len(pieces) for index in start_positions
        ):
            # This removes any old selection outlines
            self.sprite_clear_selection()
            self.render_sprite_frame() # don't update thumbnails here
            return

        x, y = self.sprite_mouse_to_mapping(position)
        dx = x - mouse_x
        dy = y - mouse_y

        # Find the movement range that keeps every selected piece's
        # position within our current -128..127 editing limits
        min_dx = max(-128 - start_x for start_x, _ in start_positions.values())
        max_dx = min(127 - start_x for start_x, _ in start_positions.values())
        min_dy = max(-128 - start_y for _, start_y in start_positions.values())
        max_dy = min(127 - start_y for _, start_y in start_positions.values())

        if dx:
            dx = max(min_dx, min(max_dx, dx)) if min_dx <= max_dx else 0
        if dy:
            dy = max(min_dy, min(max_dy, dy)) if min_dy <= max_dy else 0

        changed = False     # re-render flag

        for index, (start_x, start_y) in start_positions.items():
            piece = pieces[index]
            new_x = start_x + dx
            new_y = start_y + dy

            if (piece["x"], piece["y"]) != (new_x, new_y):
                piece["x"] = new_x
                piece["y"] = new_y
                changed = True

        if changed:
            self.sprite_refresh_piece_controls()
            self.sprite_refresh_previews(frame_index=self.frame_spinbox.value()) # Refresh canvas AND thumbnails

    def eventFilter(self, a0: 'QObject|None', a1: 'QEvent|None') -> bool:
        # For sprite frame list when resizing
        if a0 is self.sprite_frame_list.viewport() and a1.type() == QEvent.Type.Resize:
            self.framelist_resize()

        if a0 is self.sprite_label:
            event_type = a1.type()

            if event_type in (
                QEvent.Type.MouseButtonPress,
                QEvent.Type.MouseButtonDblClick
            ):
                if a1.button() == Qt.MouseButton.LeftButton:
                    # sprite_begin_drag redraws after changing selection
                    self.sprite_update_hover(a1.position(), redraw=False)
                    self.sprite_begin_drag(a1.position(), a1.modifiers())
                    return True

            elif event_type == QEvent.Type.MouseMove:
                left_held = bool(a1.buttons() & Qt.MouseButton.LeftButton)

                if left_held and self.selection_drag is not None:
                    self.sprite_update_box_select(a1.position())

                elif left_held and self.piece_drag is not None:
                    self.sprite_drag_piece(a1.position())

                else:
                    self.piece_drag = None
                    self.sprite_end_box_select()
                    self.sprite_update_hover(a1.position())

                return True

            elif event_type == QEvent.Type.MouseButtonRelease:
                if a1.button() == Qt.MouseButton.LeftButton:
                    if self.selection_drag is not None:
                        self.sprite_update_box_select(a1.position())
                        self.sprite_end_box_select()
                    else:
                        # Apply the final position before ending the drag
                        self.sprite_drag_piece(a1.position())

                    self.piece_drag = None
                    self.sprite_update_hover(a1.position())
                    return True

            elif event_type == QEvent.Type.Leave:
                # Clear hover, but let an active drag continue
                self.sprite_update_hover()

        return super().eventFilter(a0, a1)

    # --------------------------------------------------
    # Sprite: Frame Functions
    # --------------------------------------------------
    # Add Frame and Clone Frame call this function
    def sprite_new_frame(self, name, pieces, dplc_entries=None):
        # Verify frame count with DPLCs
        if not self.sprite_check_dplc_frames():
            return False

        new_index = len(self.map_frames)

        # Keep frame data and names aligned
        self.map_frames.append(pieces)
        self.frame_labels.append(name)

        # Keep DPLC frames aligned to mappings
        if self.dplc_buffer_path is not None:
            # Generate a unique DPLC label
            base_name = f"D_{name}"
            dplc_name = base_name
            copy_number = 2

            used_labels = set(self.dplc_frame_labels)
            used_labels.update(label + "_End" for label in self.dplc_frame_labels)
            used_labels.add(self.dplc_name_input.text().strip())

            while dplc_name in used_labels or dplc_name + "_End" in used_labels:
                dplc_name = f"{base_name}{copy_number}"
                copy_number += 1

            # New frames receive empty cues; clones receive independent copies
            entries = deepcopy(dplc_entries) if dplc_entries is not None else []
            self.dplc_frames.append(entries)
            self.dplc_frame_labels.append(dplc_name)

            self.dplc_vram_cache.clear()
            self.art_preview_revision += 1

        # Update the range and selection together, then refresh
        was_blocked = self.frame_spinbox.blockSignals(True)
        try:
            self.frame_spinbox.setRange(0, new_index)
            self.frame_spinbox.setValue(new_index)
        finally:
            self.frame_spinbox.blockSignals(was_blocked)

        self.piece_controls_state = None
        self._on_sprite_frame_changed(refresh_thumbnails=True)
        return True

    def sprite_add_frame(self):
        # Commit any pending name edit before changing frames
        self._on_sprite_frame_label_changed()

        # Assign a default name
        name_number = len(self.map_frames)
        name = f"Frame_{name_number}"

        while name in self.frame_labels:
            name_number += 1
            name = f"Frame_{name_number}"

        # Add brand new frame to sprite
        return self.sprite_new_frame(name, [])

    def sprite_clone_frame_and_tiles(self):
        return self.sprite_clone_frame(clone_tiles=True)

    def sprite_clone_frame(self, clone_tiles=False):
        frame_index = self.frame_spinbox.value()

        if not (
            0 <= frame_index < len(self.map_frames)
            and frame_index < len(self.frame_labels)
        ):
            return False

        if not self.sprite_check_dplc_frames():
            return False

        if clone_tiles and self.dplc_buffer_path is not None:
            QtW.QMessageBox.warning(self, "Clone Frame and Tiles",
                "Cloning source art with loaded DPLCs is not supported yet.")
            return False

        dplc_entries = (
            self.dplc_frames[frame_index]
            if self.dplc_buffer_path is not None
            else None
        )

        # Commit any pending name edit before changing frames
        self._on_sprite_frame_label_changed()

        if clone_tiles:
            # Clone tiles here. We'll use them when we make the clone frame
            try:
                pieces = self.art_clone_frame_tiles(frame_index)
            except ValueError as e:
                QtW.QMessageBox.warning(self, "Clone Frame and Tiles", str(e))
                return False
        else:
            # Clone the frame and its pieces (not the art tiles)
            pieces = deepcopy(self.map_frames[frame_index])

        # Find an unused copy name
        base_name = f"{self.frame_labels[frame_index]}_Copy"
        name = base_name
        copy_number = 2

        # Avoid duplicate ASM frame labels
        while name in self.frame_labels:
            name = f"{base_name}{copy_number}"
            copy_number += 1

        if clone_tiles:
            # Rebuild art first; sprite_new_frame refreshes thumbnails
            self.art_refresh_vram(refresh=False)
            self.render_art_tiles()

        return self.sprite_new_frame(name, pieces, dplc_entries=dplc_entries)

    def sprite_remove_frame(self):
        frame_index = self.frame_spinbox.value()

        if not (
            0 <= frame_index < len(self.map_frames)
            and frame_index < len(self.frame_labels)
        ):
            return False

        if not self.sprite_check_dplc_frames():
            return False

        # Keep frame data and names aligned
        del self.map_frames[frame_index]
        del self.frame_labels[frame_index]

        if self.dplc_buffer_path is not None:
            del self.dplc_frames[frame_index]
            del self.dplc_frame_labels[frame_index]

            self.dplc_vram_cache.clear()
            self.art_preview_revision += 1

        last_index = max(0, len(self.map_frames) - 1)
        next_index = min(frame_index, last_index)

        was_blocked = self.frame_spinbox.blockSignals(True)
        try:
            self.frame_spinbox.setRange(0, last_index)
            self.frame_spinbox.setValue(next_index)
        finally:
            self.frame_spinbox.blockSignals(was_blocked)

        self.piece_controls_state = None
        self._on_sprite_frame_changed(refresh_thumbnails=True)
        return True

    def sprite_move_frame(self, old_index, new_index):
        frame_count = len(self.map_frames)

        if not (
            len(self.frame_labels) == frame_count
            and 0 <= old_index < frame_count
            and 0 <= new_index < frame_count
        ):
            return False

        if old_index == new_index:
            return False

        if not self.sprite_check_dplc_frames():
            return False

        # Commit a pending name edit before changing frame order
        self._on_sprite_frame_label_changed()

        frame = self.map_frames.pop(old_index)
        name = self.frame_labels.pop(old_index)

        self.map_frames.insert(new_index, frame)
        self.frame_labels.insert(new_index, name)

        if self.dplc_buffer_path is not None:
            cues = self.dplc_frames.pop(old_index)
            dplc_name = self.dplc_frame_labels.pop(old_index)

            self.dplc_frames.insert(new_index, cues)
            self.dplc_frame_labels.insert(new_index, dplc_name)

            self.dplc_vram_cache.clear()
            self.art_preview_revision += 1

        # Entries were associated with the old indices
        self.frame_thumbnail_keys = [None] * frame_count

        was_blocked = self.frame_spinbox.blockSignals(True)

        try:
            self.frame_spinbox.setValue(new_index)

        finally:
            self.frame_spinbox.blockSignals(was_blocked)

        self.piece_controls_state = None
        self._on_sprite_frame_changed(refresh_thumbnails=True)
        return True

    def sprite_refresh_frame_name(self):
        frame_index = self.frame_spinbox.value()
        has_frame = (0 <= frame_index < len(self.map_frames)
            and frame_index < len(self.frame_labels))

        # Change label text box to that of the new frame's label (or blank if there is no frame)
        self.frame_name_input.setEnabled(has_frame)
        self.frame_name_input.setText(self.frame_labels[frame_index] if has_frame else "")

    def sprite_check_dplc_frames(self):
        """
        Check that loaded DPLCs can be edited alongside mappings.
        """
        if self.dplc_buffer_path is None:
            if self.dplc_cb.isChecked():
                QtW.QMessageBox.warning(self, "Frame Edit", "Load DPLCs before editing frames.")
                return False

            return True

        frame_count = len(self.map_frames)

        if (
            len(self.dplc_frames) != frame_count
            or len(self.dplc_frame_labels) != frame_count
        ):
            QtW.QMessageBox.warning(self, "Frame Edit",
                "Mapping and DPLC frame counts must match before editing frames.")
            return False

        return True

    def _on_sprite_frame_changed(self, *, refresh_thumbnails=False):
        """
        Update frame controls and canvas.
        Also refresh thumbnails if needed.
        """
        # Clear DPLC entry selection
        self.selected_entry = None
        self.entry_controls_state = None

        # Refresh art only if DPLCs are used
        if self.dplc_cb.isChecked():
            self.dplc_refresh_vram()
            self.render_art_tiles()

        self.sprite_refresh_frame_name()
        self.sprite_clear_selection()
        self.render_sprite_frame()

        if refresh_thumbnails:
            self.framelist_refresh()
        else:
            self.framelist_sync_selection()

    def _on_sprite_frame_label_changed(self):
        frame_index = self.frame_spinbox.value()

        # Nothing to rename unless both the frame and its label exist
        if not (
            0 <= frame_index < len(self.map_frames)
            and frame_index < len(self.frame_labels)
        ):
            self.sprite_refresh_frame_name()
            return

        name = self.frame_name_input.text().strip()

        # Blank input leaves the stored name unchanged
        if name:
            self.frame_labels[frame_index] = name

        # Display the accepted name, or restore the previous one
        self.sprite_refresh_frame_name()

        # Update only this frame's caption
        self.framelist_refresh(frame_index=frame_index)


    # --------------------------------------------------
    # Sprite: Piece Functions
    # --------------------------------------------------
    def sprite_add_piece(self):
        frame_index = self.frame_spinbox.value()

        if not 0 <= frame_index < len(self.map_frames):
            return

        self.sprite_clear_selection(refresh=False)
        pieces = self.map_frames[frame_index]

        # For now, append a new 1×1 piece
        pieces.append({
            "x": 0,
            "y": 0,
            "tile": 0,
            "width": 1,
            "height": 1,
            "palette": 0,
            "x_flip": False,
            "y_flip": False,
            "priority": False
        })

        # Select the new piece in both the list and viewer
        new_index = len(pieces) - 1
        self.selected_pieces = {new_index}
        self.piece_controls_state = None

        # Create the table row before scrolling to it
        self.sprite_refresh_editing_ui()
        self.sprite_refresh_previews(frame_index=self.frame_spinbox.value()) # Refresh canvas AND thumbnails
        self.piece_list_table.scrollToItem(self.piece_list_table.item(new_index, 0))

    def sprite_remove_pieces(self):
        selected = self.sprite_get_selected_pieces()

        if not selected:
            return

        pieces = self.map_frames[self.frame_spinbox.value()]

        # Delete backward so earlier indices remain valid.
        for index, _ in reversed(selected):
            del pieces[index]

        self.piece_controls_state = None
        self.sprite_clear_selection()
        self.sprite_refresh_previews(frame_index=self.frame_spinbox.value()) # Refresh canvas AND thumbnails

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
        self.sprite_end_box_select()

        # Update property panel and canvas
        self.sprite_refresh_piece_controls()
        self.render_sprite_frame()

    def sprite_clear_selection(self, *, refresh=True):
        """
        Clear selection and mouse interactions, optionally updating the UI.
        """
        self.selected_pieces.clear()
        self.piece_drag = None
        self.hovered_piece = None
        self.sprite_end_box_select()

        # Proper refresh (only if needed)
        if refresh:
            self.sprite_refresh_editing_ui()

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
            self.sprite_refresh_previews(frame_index=self.frame_spinbox.value()) # Refresh canvas AND thumbnails


    # --------------------------------------------------
    # Sprite: DPLC Entry Functions
    # --------------------------------------------------
    def dplc_add_entry(self):
        frame_index = self.frame_spinbox.value()

        if self.dplc_buffer_path is None or not 0 <= frame_index < len(self.dplc_frames):
            return

        entries = self.dplc_frames[frame_index]

        # For now, append a new single-tile entry at tile 0
        entries.append({"tile": 0, "count": 1})

        # Select the new piece in both the list and viewer
        new_index = len(entries) - 1
        self.selected_entry = new_index

        # Create the table row before scrolling to it
        self.dplc_refresh_after_edit()
        self.entry_list_table.scrollToItem(self.entry_list_table.item(new_index, 0))

    def dplc_remove_entry(self):
        selected = self.dplc_get_selected_entry()

        if selected is None:
            return

        index, _ = selected

        del self.dplc_frames[self.frame_spinbox.value()][index]

        self.selected_entry = None
        self.dplc_refresh_after_edit()

    def dplc_get_selected_entry(self):
        frame_index = self.frame_spinbox.value()

        if self.dplc_buffer_path is None or not 0 <= frame_index < len(self.dplc_frames):
            return None

        entries = self.dplc_frames[frame_index]
        index = self.selected_entry

        if index is None or not 0 <= index < len(entries):
            return None

        return index, entries[index]

    def dplc_sync_entry_list_selection(self):
        table = self.entry_list_table
        rows = table.selectionModel().selectedRows()

        table_selection = rows[0].row() if rows else None

        if table_selection == self.selected_entry:
            return

        was_blocked = table.blockSignals(True)

        try:
            table.clearSelection()
            if self.selected_entry is not None:
                table.selectRow(self.selected_entry)

        finally:
            table.blockSignals(was_blocked)

    def dplc_entry_list_selection_changed(self):
        rows = self.entry_list_table.selectionModel().selectedRows()
        self.selected_entry = rows[0].row() if rows else None
        self.dplc_refresh_entry_controls()

    def dplc_edit_entry_property(self, field, value):
        if field not in self.entry_spinboxes:
            return

        selected = self.dplc_get_selected_entry()
        if selected is None:
            return

        value = int(value)
        spinbox = self.entry_spinboxes[field]
        if not spinbox.minimum() <= value <= spinbox.maximum():
            return

        _, entry = selected
        if entry[field] == value:
            return

        entry[field] = value
        self.dplc_refresh_after_edit()

    def dplc_refresh_after_edit(self):
        frame_index = self.frame_spinbox.value()

        # Entry order and count determine every following destination in VRAM.
        self.dplc_vram_cache.pop(frame_index, None)
        self.art_preview_revision += 1
        self.entry_controls_state = None

        self.dplc_refresh_entry_list()
        self.dplc_sync_entry_list_selection()
        self.dplc_refresh_entry_controls()

        self.dplc_refresh_vram()
        self.render_art_tiles()
        self.sprite_refresh_previews(frame_index=frame_index)


    # --------------------------------------------------
    # Sprite: Refreshing
    # --------------------------------------------------
    def sprite_refresh_previews(self, *, frame_index=None):
        """
        Refresh the sprite canvas and requested frame thumbnail(s).
        """
        self.render_sprite_frame()
        self.framelist_refresh(frame_index=frame_index)

    def sprite_refresh_selection_ui(self):
        """
        Synchronize selected rows and update piece properties.
        """
        self.sprite_sync_piece_list_selection()
        self.sprite_refresh_piece_controls()

    def sprite_refresh_editing_ui(self):
        """
        Refresh list contents, selection, and property controls in order.
        """
        self.sprite_refresh_piece_list()
        self.sprite_sync_piece_list_selection()
        self.sprite_refresh_piece_controls()

        self.dplc_refresh_entry_list()
        self.dplc_sync_entry_list_selection()
        self.dplc_refresh_entry_controls()

        self.art_update_tile_controls()

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
        self.btn_piece_remove.setEnabled(has_selection)

        has_frames = (
            0 <= frame_index < len(self.map_frames)
            and frame_index < len(self.frame_labels)
        )
        self.btn_frame_remove.setEnabled(has_frames)
        self.btn_frame_copy.setEnabled(has_frames)
        self.btn_frame_clone.setEnabled(has_frames)

        # Include selection identity and property values
        state = (self.frame_spinbox.value(),
            tuple(
                (index,
                    tuple(
                        piece[field]
                        for field in self.piece_spinboxes
                    ),
                    tuple(
                        bool(piece.get(field, False))
                        for field in self.piece_checkboxes
                    )
                )
                for index, piece in selected
            )
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

    def dplc_refresh_entry_list(self):
        table = self.entry_list_table
        frame_index = self.frame_spinbox.value()

        if self.dplc_buffer_path is not None and 0 <= frame_index < len(self.dplc_frames):
            entries = self.dplc_frames[frame_index]
        else:
            entries = []

        if self.selected_entry is not None and not 0 <= self.selected_entry < len(entries):
            self.selected_entry = None

        # Position, appearance, and selection do not affect list contents
        state = (frame_index, tuple((entry["tile"], entry["count"]) for entry in entries))
        if state == self.entry_list_state:
            return

        was_blocked = table.blockSignals(True)

        try:
            table.setRowCount(len(entries))

            for row, entry in enumerate(entries):
                item = table.item(row, 0)

                if item is None:
                    item = QtW.QTableWidgetItem()
                    item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                    table.setItem(row, 0, item)

                item.setText(f"Entry {row}")

                item.setToolTip(f"Source tile: ${entry['tile']:03X}; tile count: {entry['count']}")

                # Match the zero-based indices used by the editor
                if table.verticalHeaderItem(row) is None:
                    table.setVerticalHeaderItem(row, QtW.QTableWidgetItem(str(row)))

        finally:
            table.blockSignals(was_blocked)

        self.entry_list_state = state

    def dplc_refresh_entry_controls(self):
        selected = self.dplc_get_selected_entry()
        has_selection = selected is not None

        # Disable property spinboxes when nothing is selected
        for spinbox in self.entry_spinboxes.values():
            spinbox.setEnabled(has_selection)

        # Update when buttons are enabled based on entry change
        frame_index = self.frame_spinbox.value()

        self.btn_entry_add.setEnabled(
            self.dplc_buffer_path is not None and 0 <= frame_index < len(self.dplc_frames))
        self.btn_entry_remove.setEnabled(has_selection)
        self.entry_index_label.setEnabled(has_selection)

        if selected is not None:
            index, reference_entry = selected
            state = (frame_index, index, reference_entry["tile"], reference_entry["count"])

        else:
            reference_entry = None
            state = (frame_index, None)

        if state == self.entry_controls_state:
            return
        self.entry_controls_state = state

        if selected is not None:
            self.entry_index_label.setText(f"Entry {index}")

        else:
            self.entry_index_label.setText("Entry Properties")

        # Updating the UI must not write values back into the data
        for field, spinbox in self.entry_spinboxes.items():
            was_blocked = spinbox.blockSignals(True)

            try:
                if reference_entry is None:
                    spinbox.setValue(spinbox.minimum())
                    spinbox.clear()
                else:
                    spinbox.setValue(reference_entry[field])
            finally:
                spinbox.blockSignals(was_blocked)


    # --------------------------------------------------
    # Frame List Functions
    # --------------------------------------------------
    def framelist_refresh(self, *, frame_index=None):
        """
        Refresh a given frame's thumbnail and caption.
        Refresh all frames if index is omitted.
        """
        frame_list = self.sprite_frame_list

        # Refresh when the Sprites list tab is open
        if self.editing_tabs.currentWidget() is not frame_list:
            return

        fields = ("x", "y", "tile", "width", "height",
            "palette", "x_flip", "y_flip", "priority")

        shared_key = (
            self.art_preview_revision,
            self.vram_spinbox.value(),
            self.sprpal_spinbox.value(),
            tuple(color.rgba() for color in self.palette_colors),
            self.sprite_canvas_width,
            self.sprite_canvas_height
        )

        was_blocked = frame_list.blockSignals(True) # Block signals

        try:
            # Rebuild the entries when frames are added or removed.
            if frame_list.count() != len(self.map_frames):
                frame_list.clear()
                self.frame_thumbnail_keys = [None] * len(self.map_frames)

                for _ in self.map_frames:
                    # Add to the list, center-aligned
                    item = QtW.QListWidgetItem()
                    item.setTextAlignment(Qt.AlignmentFlag.AlignHCenter)
                    frame_list.addItem(item)

                self.framelist_resize()

                # New list items all need thumbnails
                frame_index = None

            # Check only the requested frame unless a full refresh is needed
            if frame_index is None:
                indices = range(len(self.map_frames))
            elif 0 <= frame_index < len(self.map_frames):
                indices = (frame_index,)
            else:
                indices = ()

            for index in indices:
                pieces = self.map_frames[index]
                item = frame_list.item(index)

                name = (
                    self.frame_labels[index]
                    if index < len(self.frame_labels)
                    else f"Frame_{index}"
                )
                text = f"{index}: {name}"

                if item.text() != text:
                    item.setText(text)
                    item.setToolTip(text)

                frame_key = tuple(
                    tuple(piece.get(field) for field in fields)
                    for piece in pieces
                )
                thumbnail_key = (shared_key, frame_key)

                if self.frame_thumbnail_keys[index] == thumbnail_key:
                    continue

                image = self.sprite_build_frame_image(index)

                # Find the rectangle occupied by this frame's pieces
                bounds = QRect()
                center_x = self.sprite_canvas_width // 2
                center_y = self.sprite_canvas_height // 2

                for piece in pieces:
                    piece_rect = QRect(
                        center_x + piece["x"],
                        center_y + piece["y"],
                        piece["width"] * 8,
                        piece["height"] * 8,
                    )
                    bounds = bounds.united(piece_rect)

                if not bounds.isEmpty():
                    # Include a small margin and stay within the rendered image
                    bounds = bounds.adjusted(-2, -2, 2, 2)
                    bounds = bounds.intersected(image.rect())

                    if not bounds.isEmpty():
                        image = image.copy(bounds)

                # Enlarge to 2x, reducing only when necessary to fit the icon
                thumbnail = image.scaled(
                    min(image.width() * 2, frame_list.iconSize().width()),
                    min(image.height() * 2, frame_list.iconSize().height()),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.FastTransformation,
                )

                # Fixed-size image area, with sprite frame centered inside
                preview = QPixmap(frame_list.iconSize())
                preview.fill(Qt.GlobalColor.transparent)

                # Center the thumbnail inside its fixed-size preview box
                _tx = (preview.width() - thumbnail.width()) // 2
                _ty = (preview.height() - thumbnail.height()) // 2

                # Draw the frame thumbnail
                painter = QPainter(preview)
                painter.drawImage(_tx, _ty, thumbnail)

                # Outline the sprite bounds, including the crop margin
                if pieces and not bounds.isEmpty():
                    painter.setPen(QColor(150, 150, 150))
                    painter.setBrush(Qt.BrushStyle.NoBrush)
                    painter.drawRect(_tx, _ty,
                        thumbnail.width() - 1, thumbnail.height() - 1)

                painter.end()

                # Set mapping frame as icon
                item.setIcon(QIcon(preview))
                self.frame_thumbnail_keys[index] = thumbnail_key

            self.framelist_sync_selection()

        finally:
            frame_list.blockSignals(was_blocked) # Restore signals

    def on_framelist_selection_changed(self, row):
        if not 0 <= row < len(self.map_frames):
            return

        self.frame_spinbox.setValue(row)

    def framelist_sync_selection(self):
        """
        Match the highlighted list item to the current frame.
        """
        frame_list = self.sprite_frame_list

        # Hidden lists catch up when their tab opens
        if self.editing_tabs.currentWidget() is not frame_list:
            return

        # Wait for the list to be rebuilt after structural changes
        if frame_list.count() != len(self.map_frames):
            return

        selected_row = self.frame_spinbox.value() if self.map_frames else -1

        if frame_list.currentRow() == selected_row:
            return

        was_blocked = frame_list.blockSignals(True) # Block signals

        try:
            frame_list.setCurrentRow(selected_row)

            if selected_row >= 0:
                frame_list.scrollToItem(frame_list.item(selected_row))

        finally:
            frame_list.blockSignals(was_blocked) # Restore signals

    def framelist_resize(self):
        frame_list = self.sprite_frame_list

        # Establish thumbnail and caption height
        image_height = frame_list.iconSize().height()
        caption_height = frame_list.fontMetrics().height() + 8

        # Set size
        item_size = QSize(max(1, frame_list.viewport().width()), image_height + caption_height)

        if frame_list.gridSize() != item_size:
            frame_list.setGridSize(item_size)

        for index in range(frame_list.count()):
            item = frame_list.item(index)

            if item.sizeHint() != item_size:
                item.setSizeHint(item_size)


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

        load_jobs, loaded_paths, loaded_compressions = prepared

        # Preserve each row's buffer reference
        for art_tiles, loaded_tiles in load_jobs:
            art_tiles[:] = loaded_tiles

        # Set path associations and refresh VRAM
        self.art_buffer_paths = loaded_paths
        self.art_buffer_compressions = loaded_compressions # Store compression (DPLC function reads this for buffer 1)
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
            (load_jobs, loaded_paths, loaded_compressions) on success.
            None if preparation fails.
            Blank entries receive empty buffers when applied.
        """
        load_jobs = []
        loaded_paths = {}
        loaded_compressions = {}
        seen_paths = set()

        # Loop for each filepath added
        for row_index, (path_input, comp_combo, _, _, art_tiles) in enumerate(self.art_rows):
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

                # DPLCs read directly from uncompressed source art in buffer 1
                compression = comp_combo.currentText()
                if row_index == 0 and self.dplc_cb.isChecked() and compression != "Uncompressed":
                    raise ValueError("DPLCs require uncompressed art in buffer 1. "
                        "Choose Uncompressed and load an uncompressed art file.")

                # Unpack tiles and load into buffer storage
                loaded_tiles = decode_art(raw_data, compression)

                # Queue buffer to be loaded
                load_jobs.append((art_tiles, loaded_tiles))
                loaded_paths[path_input] = path
                loaded_compressions[path_input] = compression

            except Exception as e:
                QtW.QMessageBox.warning(self, "Art Load Error",
                    f"Could not load art file {path.name}:\n{str(e)}")
                return None

        return load_jobs, loaded_paths, loaded_compressions

    def art_prepare_save(self):
        """
        Validate art entries and prepare their encoded file contents.
        (Much of this code was pulled from art_entry_save).

        Returns:
            (save_jobs, saved_paths) when ready to save.
            () if no art files are configured.
            None if preparation fails or is cancelled.
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
                    raise ValueError("Cannot save an empty art buffer.")

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
        comp_combo.currentTextChanged.connect(self.art_refresh_vram)

    def art_remove_entry(self, row=None):
        if row is None:
            row = self.art_file_table.currentRow()

        if not 0 <= row < len(self.art_rows):
            return

        # Remove the row and its file association
        path_input, _, _, _, _ = self.art_rows.pop(row)
        self.art_buffer_paths.pop(path_input, None)
        self.art_buffer_compressions.pop(path_input, None)
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

        self.art_update_view_options()

    def art_update_view_options(self):
        """
        Keep the art selection dropdown up-to-date with the art files loaded.
        """
        combo = self.viewer_art_combo
        paths = [row[0] for row in self.art_rows]
        if [combo.itemData(index) for index in range(1, combo.count())] == paths:
            return

        # Identify buffers by their path widgets
        selected = combo.currentData()
        was_blocked = combo.blockSignals(True)
        try:
            combo.clear()
            combo.addItem("VRAM")
            for index, path_input in enumerate(paths, start=1):
                combo.addItem(f"Buffer {index}", path_input)
            combo.setCurrentIndex(paths.index(selected) + 1 if selected in paths else 0)
        finally:
            combo.blockSignals(was_blocked)

        self.render_art_tiles()

    def art_update_tile_controls(self):
        """
        Enable optimization for the selected art buffer.
        """
        # "Ready" = mappings and art tile files are present and loaded in.
        buffer_index = self.viewer_art_combo.currentIndex() - 1
        ready = (bool(self.map_frames) and 0 <= buffer_index < len(self.art_rows)
            and bool(self.art_rows[buffer_index][4]) and not self.dplc_cb.isChecked())

        self.arrange_tiles.setEnabled(ready)
        self.strip_tiles.setEnabled(ready)
        self.pad_tiles.setEnabled(ready)

    def art_refresh_vram(self, *, refresh=True):
        """
        Load each file's source tiles into VRAM.

        Buffer 1 is dynamic if DPLCs are used, static otherwise.
        Buffers 2 and 3 are always static.
        """
        # Clear static VRAM
        self.static_vram_tiles = {}

        for row_index, (_, _, offset_spin, count_spin, art_tiles) in enumerate(self.art_rows):
            # Buffer 1 is dynamic if DPLCs are enabled
            dynamic_source = self.dplc_cb.isChecked() and row_index == 0

            offset_spin.setEnabled(not dynamic_source)
            count_spin.setEnabled(not dynamic_source)

            if dynamic_source:
                continue  # The complete first buffer is source art, not a static upload

            # Copy from source to VRAM
            start = offset_spin.value()
            requested_count = count_spin.value() or len(art_tiles) # If count == 0, load all tiles
            preview_count = min(requested_count, len(art_tiles), 2048 - start)
            for source_index in range(preview_count):
                self.static_vram_tiles[start + source_index] = art_tiles[source_index].copy()

        # Invalidate cached previews after rebuilding VRAM
        self.art_preview_revision += 1
        self.dplc_vram_cache.clear()
        self.dplc_refresh_vram()
        self.art_update_tile_controls()

        # Whole-build loading can defer refreshing
        if refresh:
            self.render_art_tiles()
            self.sprite_refresh_previews() # Refresh canvas AND thumbnails

    # --------------------------------------------------
    # Art: Tile Arrangement and Removal
    # --------------------------------------------------
    def art_arrange_tiles(self):
        """
        Order the selected art buffer's tiles by first mapping usage.
        Partially covered pieces are covered either with or without padding.
        """
        # Get art tile buffer to be rearranged
        buffer_index = self.viewer_art_combo.currentIndex() - 1
        if not (0 <= buffer_index < len(self.art_rows) and self.art_rows[buffer_index][4]):
            return False

        # Get tile usage for this art file, across all loaded sprite frames
        try:
            usage = self.art_collect_tile_usage(buffer_index, self.pad_tiles.isChecked())
        except ValueError as e:
            QtW.QMessageBox.warning(self, "Arrange Tiles", str(e))
            return False

        # If there are unused tiles, ask to remove them or stick them at the end of the buffer
        remove_unused = False
        if usage["unused_count"]:
            answer = QtW.QMessageBox.question(self, "Arrange Tiles",
                f"Tiles in {self.viewer_art_combo.currentText()} will be arranged "
                "in order of first sprite usage.\n\n"
                "Also delete unused tiles? Choosing No keeps unused tiles at the "
                "end of this art buffer.",
                QtW.QMessageBox.StandardButton.Yes | QtW.QMessageBox.StandardButton.No,
                QtW.QMessageBox.StandardButton.No)
            remove_unused = answer == QtW.QMessageBox.StandardButton.Yes

        # Partition blocks according to their boundary constraints
        # Leading = pieces start with a tile index BEFORE the loaded art
        # Trailing = pieces end with a tile index AFTER the loaded art
        leading, ordinary, trailing = [], [], []

        for block in usage["blocks"]:
            if block[3]: # 3 = keep_start flag
                # A block constrained at BOTH boundaries covers the entire loaded file
                # Include it once at the beginning, no other blocks fit
                leading.append(block)
            elif block[4]: # 4 = keep_end flag
                trailing.append(block)
            else:
                ordinary.append(block)

        # Sort used tiles by order of first usage, leaving out unused tiles
        # Leading partial blocks go first, then ordinary blocks by first usage
        order = [index
            for start, end, *_ in leading + sorted(ordinary, key=lambda block: block[2])
            for index in range(start, end)]

        # Retain unused ORIGINAL tiles only if removal was not requested
        if not remove_unused:
            # Append unused tiles BEFORE trailing partial blocks
            cursor = usage["offset"]
            art_end = cursor + usage["visible"]

            # Add unused tiles before, in-between, and after blocks
            for start, end, *_ in usage["blocks"]:
                loaded_start = max(start, usage["offset"])
                loaded_end = min(end, art_end)
                if loaded_start >= loaded_end:
                    continue
                order.extend(range(cursor, loaded_start))
                cursor = loaded_end

            # Include unused tiles after the final block
            order.extend(range(cursor, art_end))

        # Keep trailing partial blocks at the actual end of the output
        # otherwise these pieces would display unused art in place of missing tiles
        order.extend(index for start, end, *_ in trailing for index in range(start, end))

        # Apply changes to tile order and sprite mappings; Remove tiles if necessary
        try:
            if remove_unused:
                self.art_remove_unused_tiles(usage, order)
            else:
                self.art_apply_tile_orders(usage, order, keep_unused=True)
        except ValueError as e:
            QtW.QMessageBox.warning(self, "Arrange Tiles", str(e))
            return False

        # Refresh the editor
        self.art_refresh_after_tile_edit()
        return True

    def art_strip_unused_tiles(self):
        """
        Remove unused tiles from the selected file, retaining tile order.
        """
        # Get art tile buffer to be modified
        buffer_index = self.viewer_art_combo.currentIndex() - 1
        if not (0 <= buffer_index < len(self.art_rows)
                and self.art_rows[buffer_index][4]):
            return False

        # Get tile usage for this art file, across all loaded sprite frames
        try:
            # Strip never adds padding, even when Pad Tiles is checked
            usage = self.art_collect_tile_usage(buffer_index)
        except ValueError as e:
            QtW.QMessageBox.warning(self, "Strip Unused Tiles", str(e))
            return False

        # End early if there are no tiles to remove
        if not usage["unused_count"]:
            QtW.QMessageBox.information(self, "Strip Unused Tiles", "There are no unused tiles.")
            return False

        # Ask to remove unused tiles
        answer = QtW.QMessageBox.question(self, "Strip Unused Tiles",
            f"Delete {usage['unused_count']} unused tile(s) from "
            f"{self.viewer_art_combo.currentText()}?\n\n"
            "The remaining tiles keep their current order. Mapping tile indices "
            "will be updated. Files are changed when you save.",
            QtW.QMessageBox.StandardButton.Yes | QtW.QMessageBox.StandardButton.No,
            QtW.QMessageBox.StandardButton.No)

        # If user declines or cancels, stop here
        if answer != QtW.QMessageBox.StandardButton.Yes:
            return False

        # Remove unused tiles without altering existing tile order
        try:
            self.art_remove_unused_tiles(usage)
        except ValueError as e:
            QtW.QMessageBox.warning(self, "Strip Unused Tiles", str(e))
            return False

        # Refresh the editor
        self.art_refresh_after_tile_edit()
        return True

    def art_remove_unused_tiles(self, usage, order=None):
        """
        Remove unused tiles, preserving the supplied or original tile order.

        order contains only used positions, including planned blanks.
        The unused loaded tiles and unloaded source tail are omitted together.
        """
        # If no order is provided, Create one with used tiles in their original order
        if order is None:
            order = [index for start, end, *_ in usage["blocks"]
                for index in range(start, end)]

        # Retain original tile order, and leave out unused tiles
        self.art_apply_tile_orders(usage, order)

    def art_collect_tile_usage(self, buffer_index=None, pad_missing=False, frame_index=None):
        """
        Builds usage records for each art buffer in a sprite build.
        Positions are absolute VRAM tile indices. DPLC remapping is not yet supported.
        (Note: frame_index specifies a specific frame, though this is currently unused,
        since Frame cloning uses the old collector instead (which checks all loaded art buffers)

        Limitations:
            DPLC source tile remapping is not supported by art optimization.
            Art entry overlapping in VRAM has no effect.
                - To-Do: Might modify this to flag overlapped tiles for deletion (Optional)
            Cross-buffer pieces may require manual VRAM adjustments after optimization.
        """
        # This will add another layer to tile remapping. For now, it's disabled
        # DPLC-aware source tile remapping will be added separately
        if self.dplc_cb.isChecked():
            raise ValueError("Disable DPLCs before optimizing art. DPLC tile remapping is not implemented yet.")

        # Stop if no frames (A frame with no pieces still passes)
        if not self.map_frames:
            raise ValueError("Load or create mapping frames before optimizing art.")

        # If a specific buffer isn't picked, use the dropdown selection
        if buffer_index is None:
            buffer_index = self.viewer_art_combo.currentIndex() - 1

        # A series of art buffer validation checks
        if not 0 <= buffer_index < len(self.art_rows):
            raise ValueError("Select an art buffer before optimizing tiles.")

        path_input, _, offset_spin, count_spin, tiles = self.art_rows[buffer_index]

        if path_input.text().strip() and path_input not in self.art_buffer_paths:
            raise ValueError(f"Load art entry {buffer_index + 1} before optimizing art.")

        if not tiles:
            raise ValueError("Load art tiles into the selected buffer before optimizing art.")

        # Before, a loop ran for each loaded entry. Now, this is only performed for a selected entry
        art_start = offset_spin.value()    # VRAM offset tiles are loaded into
        # Number of visible tiles loaded into VRAM
        visible = min(count_spin.value() or len(tiles), len(tiles), 2048 - art_start)
        art_end = art_start + visible # end of the art file

        base_tile = self.vram_spinbox.value()
        frames = enumerate(self.map_frames)

        # If tile usage is being checked for a specific frame...
        if frame_index is not None:
            frames = [(frame_index, self.map_frames[frame_index])]

        # Collect these in their own temp structures. They're used to form blocks later.
        # Usage dictionary will be updated after that is finished.
        runs, candidates = [], []

        # Iterate through every frame in the sprite
        for current_frame, pieces in frames:
            # Iterate through every piece in each frame
            for piece_index, piece in enumerate(pieces):
                width, height = piece["width"], piece["height"]

                # Validation check: dimensions
                if (not isinstance(width, int) or not isinstance(height, int)
                        or not 1 <= width <= 4 or not 1 <= height <= 4):
                    raise ValueError(f"Frame {current_frame}, piece {piece_index} has invalid dimensions.")

                # Get first tile, last tile, and range of tiles for this piece
                start = (base_tile + piece["tile"]) & 2047
                end = start + width * height

                # If art is completely missing from the piece, skip piece
                # With padding, keep candidates until we know which pieces the
                # enlarged output may reach, including shared missing tiles.
                if not pad_missing and (end <= art_start or start >= art_end):
                    continue

                if pad_missing:
                    # Track loaded tiles; Missing indices act as blank placeholders
                    run_start, run_end = start, end
                    keep_start = keep_end = False
                else:
                    # Track only loaded tiles and preserve partial coverage
                    run_start = max(start, art_start)  # actual start (piece's starting index, or art's starting index)
                    run_end = min(end, art_end)  # actual end (piece's end index, or art's end index)
                    keep_start = start < art_start  # For partial runs that start BEFORE the art file
                    keep_end = end > art_end  # For partial runs that start AFTER the art file

                # Add to the list of runs (with a zero-based usage index)
                runs.append((run_start, run_end, len(runs), keep_start, keep_end))
                # Add piece candidate
                candidates.append((piece, start, end))

        # Merge overlapping runs in their original tile order
        blocks = []

        # Note: Start is inclusive, end is exclusive: [10, 14) = [10, 11, 12, 13]
        for start, end, first_use, keep_start, keep_end in sorted(runs):
            # If this isn't the 1st block, and its start precedes the end of the last block...
            if blocks and start < blocks[-1][1]:
                old_start, old_end, old_use, old_keep_start, old_keep_end = blocks[-1]

                # ... merge the current overlapping run into the last block instead of starting a new one
                blocks[-1] = (
                    old_start, # Preserve the earlier run start
                    max(old_end, end), # Use the later run end
                    min(old_use, first_use), # Preserve the earliest usage
                    old_keep_start or keep_start,  # Preserve leading partial coverage
                    old_keep_end or keep_end,  # Preserve trailing partial coverage
                )

            # Otherwise, start a new block at the end of the list
            else:
                blocks.append((start, end, first_use, keep_start, keep_end))

        # Art tile padding handling starts here
        head_padding = tail_padding = 0

        if pad_missing:
            # Start with complete merged blocks touching original art.
            # Padding grows output while maintaining the starting address.
            # If that growth reaches a wholly missing piece, include its candidate too.
            # This way, rearrangement won't make that piece display unrelated art.
            all_blocks = blocks
            output_end = art_end

            while True:
                blocks = [block for block in all_blocks
                    if block[0] < output_end and block[1] > art_start]
                # Merged blocks do not overlap, so shared missing tiles count once
                head_padding = sum(max(0, min(end, art_start) - start)
                    for start, end, *_ in blocks)
                tail_padding = sum(max(0, end - max(start, art_end))
                    for start, end, *_ in blocks)
                padded_end = art_end + head_padding + tail_padding

                if padded_end == output_end:
                    break
                output_end = padded_end

            # Include every piece belonging to a selected complete block,
            # including ones sharing only its missing tile positions
            piece_refs = [(piece, start) for piece, start, end in candidates
                if any(block[0] <= start and end <= block[1] for block in blocks)]
        else:
            # Preserve original starts, including starts before loaded art
            piece_refs = [(piece, start) for piece, start, _ in candidates]

        # NOTE: Added padding tiles never affect the count of unused original tiles
        loaded_used = sum(max(0, min(end, art_end) - max(start, art_start))
            for start, end, *_ in blocks)

        # Return completed usage record
        return {"tiles": tiles, "offset": art_start, "visible": visible,
            "count_spin": count_spin, "buffer_index": buffer_index,
            "blocks": blocks, "pieces": piece_refs, "pad_missing": pad_missing,
            "head_padding": head_padding, "tail_padding": tail_padding,
            "unused_count": len(tiles) - loaded_used}

    def art_collect_clone_tile_usage(self, frame_index=None):
        """
        Collect complete sourced runs across buffers for frame cloning.
        (Retains the original collector which examined frame(s) across all loaded buffers)
        To-Do: Consider using the new collector for cloning, and call it for each buffer here.

        Limitations:
            DPLC source tile remapping is not supported by art optimization.
            Art entries CANNOT overlap one another in VRAM (Might be resolved)
            Pieces cannot be made up of tiles from multiple art file entries (Need to test)
        """
        # This will add another layer to tile remapping. For now, it's disabled
        # DPLC-aware source tile remapping will be added separately.
        if self.dplc_cb.isChecked():
            raise ValueError("Disable DPLCs before optimizing art. DPLC tile remapping "
                "is not implemented yet.")

        # Stop if no frames (A frame with no pieces still passes)
        if not self.map_frames:
            raise ValueError("Load or create mapping frames before optimizing art.")

        # If no non-empty art tile buffer, stop here
        if not any(row[4] for row in self.art_rows):
            raise ValueError("Load art tiles before optimizing art.")

        # Usage list contains one dictionary per art row (read: art entry)
        # Sources dict has the key:value of: {VRAM tile index: (art_entry, source_tile_index)}
        usage, sources = [], {}

        # Check each art row (art entry); Compression setting is ignored
        for row_index, (path_input, _, offset_spin, count_spin, tiles) in enumerate(self.art_rows):
            # Reject art entries that haven't been loaded in
            if path_input.text().strip() and path_input not in self.art_buffer_paths:
                raise ValueError(f"Load art entry {row_index + 1} before optimizing art.")

            offset = offset_spin.value()    # VRAM offset tiles are loaded into
            count = count_spin.value()      # Number of tiles loaded into VRAM (usually all)

            # If count == 0, use all tiles. If not, use specified tile count
            # min() caps it to the number of tiles actually available
            visible = min(count or len(tiles), len(tiles), 2048 - offset)

            # Create the usage record for this art entry
            usage.append(
                {"tiles": tiles, "offset": offset, "visible": visible,
                "count_spin": count_spin, "used": set(), "runs": [], "pieces": []}
            )

            # Iterate through each VRAM index for every visible tile from this art entry
            for slot in range(offset, offset + visible):
                # Raise error if art overlaps in VRAM
                # To-Do: If art overlaps in VRAM, overlapped art should be considered not visible; unused)
                if slot in sources:
                    raise ValueError("Art entries overlap in VRAM. Give them separate "
                        "VRAM ranges before optimizing tiles.")

                # Subtracting the buffer’s offset converts the VRAM index into its source index
                # E.g. sources[102] = (0, 2) if slot == 102, and offset == 100
                sources[slot] = (row_index, slot - offset)

        base_tile = self.vram_spinbox.value()
        first_use = 0

        frames = enumerate(self.map_frames)
        if frame_index is not None:
            frames = [(frame_index, self.map_frames[frame_index])]

        # Iterate through each requested frame in the sprite
        for frame_index, pieces in frames:
            # For each frame, iterate through each piece
            for piece_index, piece in enumerate(pieces):
                width, height = piece["width"], piece["height"]

                if (not isinstance(width, int) or not isinstance(height, int)
                        or not 1 <= width <= 4 or not 1 <= height <= 4):
                    raise ValueError(f"Frame {frame_index}, piece {piece_index} has invalid dimensions.")

                # Get the piece's starting tile
                start = (base_tile + piece["tile"]) & 2047
                # Get source location for every tile in this piece
                slots = [sources.get(start + tile) for tile in range(width * height)]

                if not any(slot is not None for slot in slots):
                    continue

                if any(slot is None for slot in slots):
                    raise ValueError(f"Frame {frame_index}, piece {piece_index} has missing "
                        "art tiles. Load its complete tile run before optimizing.")

                # The first slot identifies the source buffer and the piece’s starting tile index within it
                buffer_index, source_start = slots[0]

                # This ensures the entire piece belongs to one art buffer
                # To-Do: Buffers are optimized individually; boundary-crossing piece-handling isn’t supported ATM
                if any(buffer != buffer_index for buffer, _ in slots):
                    raise ValueError(f"Frame {frame_index}, piece {piece_index} spans multiple "
                        "art buffers. Keep its complete tile run in one buffer before optimizing.")

                data = usage[buffer_index]  # Extract usage record dict for THIS art buffer
                end = source_start + width * height # Index of the first tile + (tile count)

                data["used"].update(range(source_start, end))       # Record all tiles used in this piece in the set
                data["runs"].append((source_start, end, first_use)) # Note the earliest use of these tiles
                data["pieces"].append((piece, source_start))        # Store this piece so we can update it later

                first_use += 1

        # Return completed usage records
        return usage

    def art_apply_tile_orders(self, usage, order, *, keep_unused=False):
        """Prepare one buffer and its mappings, then apply them together.

        Order positions use original absolute VRAM indices. Positions outside
        the original loaded prefix represent fresh blank tiles. When keeping
        unused tiles, the original unloaded tail remains after the new prefix.
        """
        offset, visible = usage["offset"], usage["visible"]
        new_visible = len(order)
        if offset + new_visible > 2048:
            raise ValueError("The optimized art would exceed VRAM tile 2047. "
                "Lower this buffer's VRAM start or remove unused tiles before optimizing.")

        art_end = offset + visible
        tiles = [usage["tiles"][index - offset] if offset <= index < art_end
            else [0] * 64 for index in order]
        if keep_unused:
            tiles.extend(usage["tiles"][visible:])

        positions = {old_index: new_index for new_index, old_index in enumerate(order)}
        updates = []
        base_tile = self.vram_spinbox.value()
        for piece, start in usage["pieces"]:
            # Unpadded leading pieces are remapped via their first loaded tile.
            anchor = start if usage["pad_missing"] else max(start, offset)
            new_start = offset + positions[anchor] - (anchor - start)
            updates.append((piece, (new_start - base_tile) & 2047))

        count = new_visible if usage["count_spin"].value() else 0
        usage["tiles"][:] = tiles
        for piece, tile_index in updates:
            piece["tile"] = tile_index

        spinbox = usage["count_spin"]
        was_blocked = spinbox.blockSignals(True)
        try:
            spinbox.setValue(count)
        finally:
            spinbox.blockSignals(was_blocked)

    def art_refresh_after_tile_edit(self):
        """
        Refresh VRAM, previews, and mapping controls after a tile edit.
        """
        self.piece_controls_state = None
        self.sprite_refresh_piece_controls()
        self.art_refresh_vram()

    def art_clone_frame_tiles(self, frame_index):
        """
        Duplicate a frame's sourced tiles and return remapped piece copies

        This has limitations tied to art_collect_clone_tile_usage.
        I'm working on solutions for this.
        """
        source_pieces = self.map_frames[frame_index]
        pieces = deepcopy(source_pieces)
        if not pieces:
            return pieces

        usage = self.art_collect_clone_tile_usage(frame_index)
        piece_copies = {id(source): copy for source, copy in zip(source_pieces, pieces)}
        base_tile = self.vram_spinbox.value()

        occupied = {slot for data in usage
            for slot in range(data["offset"], data["offset"] + data["visible"])}

        added_slots = set()
        planned = []

        for row_index, data in enumerate(usage):
            indices = sorted(data["used"])

            if not indices:
                continue

            visible = data["visible"]
            new_visible = visible + len(indices)
            start = data["offset"] + visible
            end = data["offset"] + new_visible

            if end > 2048:
                raise ValueError(f"Art entry {row_index + 1} has insufficient VRAM "
                    "space for the cloned tiles. Free space before cloning.")

            slots = set(range(start, end))
            if slots & (occupied | added_slots):
                raise ValueError(f"Cloned tiles for art entry {row_index + 1} would "
                    "overlap another art entry in VRAM. Leave space after this "
                    "entry before cloning.")

            added_slots.update(slots)

            # Sorted source indices preserve each piece's consecutive tile run
            positions = {old: visible + new for new, old in enumerate(indices)}
            for piece, source_start in data["pieces"]:
                piece_copies[id(piece)]["tile"] = (
                    data["offset"] + positions[source_start] - base_tile) & 2047

            tiles = [data["tiles"][index].copy() for index in indices]
            count = data["count_spin"].value()

            if count:
                count = max(count, new_visible)
            planned.append((data, tiles, count))

        # Newly populated VRAM must not change previously missing art in any
        # existing frame, including transparent pieces in the source frame
        for existing_frame, frame in enumerate(self.map_frames):
            for piece_index, piece in enumerate(frame):
                start = (base_tile + piece["tile"]) & 2047

                if any(start + tile in added_slots
                        for tile in range(piece["width"] * piece["height"])):
                    raise ValueError("Cloned tiles would fill missing art used by "
                        f"frame {existing_frame}, piece {piece_index}. Choose an "
                        "art layout that leaves its missing tiles transparent.")

        for data, tiles, count in planned:
            # Keep both buffer identity and the original loaded tile indices
            visible = data["visible"]
            data["tiles"][visible:visible] = tiles
            spinbox = data["count_spin"]
            was_blocked = spinbox.blockSignals(True)

            try:
                spinbox.setValue(count)
            finally:
                spinbox.blockSignals(was_blocked)

        return pieces


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

    def mapping_entry_load(self, *, prepared=None, prepared_dplcs=None, refresh=True):
        """
        Prepare and apply mappings (and DPLCs) before refreshing VRAM.

        Returns:
            True if successful, False if preparation fails.
        """
        # If not prepared beforehand, do it here
        if prepared is None:
            prepared = self.mapping_prepare_load()

        # Preparation failed/cancelled
        if prepared is None:
            return False

        # Prepare cues before replacing either loaded buffer.
        if prepared_dplcs is None:
            prepared_dplcs = self.dplc_prepare_load()

        # Preparation failed/cancelled
        if prepared_dplcs is None:
            return False

        self.dplc_set_buffer(*prepared_dplcs)
        self.mapping_set_buffer(*prepared, refresh=False)

        # Set to use DPLCs
        if prepared[0] is None and prepared_dplcs[0] is not None:
            self.macro_cb.setChecked(self.dplc_use_macros)

        self.art_refresh_vram(refresh=False)

        if refresh:
            self.render_art_tiles()
            self._on_sprite_frame_changed(refresh_thumbnails=True)

        # Report both assets, including a DPLC-only load before art is available
        path = prepared[0]
        if refresh and (path is not None or self.dplc_buffer_path is not None):
            details = []

            if path is not None:
                details.append(f"Mapping frames: {len(self.map_frames)} ({path.name})")
            if self.dplc_buffer_path is not None:
                details.append(f"DPLC frames: {len(self.dplc_frames)} ({self.dplc_buffer_path.name})")

            QtW.QMessageBox.information(self, "Sprite Data Loaded", "\n".join(details))

        return True

    def mapping_entry_save(self, *, prepared=None, prepared_dplcs=None):
        """
        Prepare and save configured mappings (and DPLCs).

        Returns:
            True if saved successfully or no file is configured.
            False on failure or cancellation.
            Earlier writes are not rolled back if a later write fails.
        """
        # If mappings are not prepared beforehand, do it here
        if prepared is None:
            prepared = self.mapping_prepare_save()

        # Preparation failed/cancelled
        if prepared is None:
            return False

        # If DPLCs are not prepared beforehand, do it here
        if prepared_dplcs is None:
            prepared_dplcs = self.dplc_prepare_save()

        # Preparation failed/cancelled
        if prepared_dplcs is None:
            return False

        # Reject a shared destination before writing either file
        if prepared and prepared_dplcs and prepared[0] == prepared_dplcs[0]:
            QtW.QMessageBox.warning(self, "Save Error",
                "Mappings and DPLCs cannot use the same save destination.")
            return False

        details = []
        if prepared:
            path, mapping_data = prepared
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
                save_mappings(path, mapping_data)
            except Exception as e:
                QtW.QMessageBox.warning(self, "Mapping Save Error",
                    f"Could not save mappings to {path.name}:\n{e}")
                return False

            # Adopt the destination only after a successful save
            self.mapping_buffer_path = path
            details.append(f"Mapping frames: {len(self.map_frames)} ({path.name})")

        if not self.dplc_entry_save(prepared=prepared_dplcs, notify=False):
            return False

        if prepared_dplcs:
            path, _ = prepared_dplcs
            details.append(f"DPLC frames: {len(self.dplc_frames)} ({path.name})")

        if details:
            QtW.QMessageBox.information(self, "Sprite Data Saved", "\n".join(details))

        return True

    def mapping_prepare_load(self):
        """
        Parse configured mappings without changing the currently loaded build.

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
            loaded = load_mappings(path, self.map_dropdown.currentData())

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
                self.map_dropdown.currentData(), map_label=self.map_name_input.text().strip(),
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

        # Empty the buffers
        self.mapping_set_buffer(None, [], [], "", False)
        self.dplc_set_buffer(None, [], [], "", None)

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
        has_dplcs = self.dplc_cb.isChecked() and bool(self.dplc_path_input.text().strip())
        self.btn_map_load.setEnabled(has_asset or has_dplcs)
        self.btn_map_save.setEnabled(has_asset or has_dplcs)

        # Always available to reset the table
        self.btn_map_remove.setEnabled(True)

    def mapping_dplc_browse(self, line_edit):
        # Access project directory
        project_dir = self.project.root_dir
        start_dir = str(project_dir) if project_dir else ""

        # Select an existing source or a new save destination without writing it
        file_path, _ = QtW.QFileDialog.getSaveFileName(self, "Select DPLC File",
            start_dir, "DPLC Files (*.asm *.bin);;All Files (*)",
            options=QtW.QFileDialog.Option.DontConfirmOverwrite)

        # If successful, store DPLC filepath
        if file_path:
            path = self.project.resolve_asset_path(file_path)
            line_edit.setText(str(path))


    # --------------------------------------------------
    # DPLC Handling
    # --------------------------------------------------
    def dplc_entry_save(self, *, prepared=None, notify=True):
        """
        Write prepared DPLCs and adopt the destination.

        In a combined save, preparation happens in mapping_entry_save.
        Since DPLCs aren't currently saved independently, these checks are redundant.
        This will change later when I modify map/DPLC saving to only save when edited.
        """
        # If DPLCs are not prepared beforehand, do it here
        if prepared is None:
            prepared = self.dplc_prepare_save()

        # Preparation failed/cancelled
        if prepared is None:
            return False

        # No DPLC file is configured
        if not prepared:
            return True

        path, dplc_data = prepared

        # Write only after DPLCs are prepared
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            save_dplcs(path, dplc_data)

        except Exception as e:
            QtW.QMessageBox.warning(self, "DPLC Save Error",
                f"Could not save DPLCs to {path.name}:\n{e}")
            return False

        format_id = self.map_dropdown.currentData()
        association_changed = path != self.dplc_buffer_path or format_id != self.dplc_buffer_format

        # Adopt the destination only after a successful save
        self.dplc_buffer_path = path
        self.dplc_buffer_format = format_id
        self.dplc_use_macros = path.suffix.lower() == ".asm" and self.macro_cb.isChecked()

        if association_changed:
            self.art_refresh_vram()

        if notify:
            QtW.QMessageBox.information(self, "DPLCs Saved",
                f"Successfully saved {len(self.dplc_frames)} frames to {path.name}.")

        return True

    def dplc_prepare_load(self):
        """
        Parse configured DPLCs without changing the currently loaded build.

        Returns:
            (path, frames, frame_labels, map_label, use_macros) on success.
            An empty DPLC buffer if no file is configured.
            None if preparation fails.
        """
        # To-Do: Make this a global variable, or a constant... not sure which just yet
        empty = (None, [], [], "", None)

        # Stop now if DPLC's are not enabled
        if not self.dplc_cb.isChecked():
            return empty

        file_path_str = self.dplc_path_input.text().strip()

        # For unconfigured mappings, use an empty buffer
        if not file_path_str:
            return empty

        path = Path(file_path_str)

        try:
            # Resolve relative paths against the project directory
            path = self.project.resolve_asset_path(path)

            # Prepare data without changing anything in the editor
            loaded = load_dplcs(path, self.map_dropdown.currentData())

        except Exception as e:
            QtW.QMessageBox.warning(self, "DPLC Load Error",
                f"Could not load DPLCs from {path.name}:\n{e}")
            return None

        return path, *loaded

    def dplc_prepare_save(self):
        """
        Validate DPLCs and prepare file contents without writing.

        Returns:
            (path, data) when ready to save.
            () when disabled/unconfigured.
            None if preparation fails or is canceled.

            Note: Cue ranges do not need to fit the currently loaded source art.
        """
        # if DPLCs are disabled, stop here
        if not self.dplc_cb.isChecked():
            return ()

        # If a filepath is empty, don't save
        file_path_str = self.dplc_path_input.text().strip()
        if not file_path_str:
            return ()

        # Require a loaded or initialized DPLC buffer
        if self.dplc_buffer_path is None:
            QtW.QMessageBox.warning(self, "DPLC Save Error",
                "Load DPLCs for this build before saving.")
            return None

        # Require at least one frame; frames may contain no DPLC entries
        if not self.dplc_frames:
            QtW.QMessageBox.warning(self, "DPLC Save Error",
                "Load at least one DPLC frame before saving.")
            return None

        path = Path(file_path_str)

        try:
            # Resolve the destination
            path = self.project.resolve_asset_path(path)

            if path.is_dir():
                raise IsADirectoryError(f"Save destination is a directory: {path}")

            # Confirm a changed destination
            if path != self.dplc_buffer_path:
                if not self.file_confirm_overwrites([path]):
                    return None

            # Collect the optional ASM description before writing
            description = ""
            if path.suffix.lower() == ".asm":
                description, accepted = QtW.QInputDialog.getText(self, "DPLC Description",
                    "Enter an optional description for the DPLCs:", text="")
                if not accepted:
                    return None

            # Build the complete file without writing it
            dplc_data = prepare_dplcs(path, self.dplc_frames, self.dplc_frame_labels,
                self.map_dropdown.currentData(), dplc_label=self.dplc_name_input.text().strip(),
                use_macros=self.macro_cb.isChecked(), description=description)

        except Exception as e:
            QtW.QMessageBox.warning(self, "DPLC Save Error",
                f"Could not prepare DPLCs for {path.name}:\n{e}")
            return None

        return path, dplc_data

    def dplc_set_buffer(self, path, frames, labels, table_label, use_macros):
        """
        Install parsed cues independently of whether source art is loaded.

        Retain the loaded macro flag; the shared Save with Macros checkbox
        controls the output syntax when saving mappings and DPLCs.
        """
        self.dplc_frames = frames
        self.dplc_frame_labels = labels
        self.dplc_use_macros = bool(use_macros)
        self.dplc_buffer_path = path

        self.selected_entry = None
        self.entry_list_state = None
        self.entry_controls_state = None

        if path is not None:
            self.dplc_name_input.setText(table_label)
            self.dplc_buffer_format = self.map_dropdown.currentData()
        else:
            self.dplc_buffer_format = None

        self.dplc_vram_cache.clear()
        self.art_preview_revision += 1

        self.dplc_refresh_entry_list()
        self.dplc_sync_entry_list_selection()
        self.dplc_refresh_entry_controls()

    def dplc_get_frame_vram(self, frame_index):
        """
        Return an independent (tiles, status) snapshot for one frame.

        Buffer 1 supplies source indices starting at zero; its static offset
        and count don't apply. Reject invalid frames before copying any of their dynamic tiles.
        """
        # Stop now if DPLC's are not enabled
        if not self.dplc_cb.isChecked():
            return self.static_vram_tiles, ""

        cached = self.dplc_vram_cache.get(frame_index)
        if cached is not None:
            return cached

        tiles = self.static_vram_tiles.copy()
        status = ""
        source_tiles = []

        # Update DPLC status message
        if self.dplc_buffer_path is None:
            status = "Load a DPLC file to populate frame VRAM."
        elif self.dplc_buffer_format != self.map_dropdown.currentData():
            status = "The format has changed. Reload mappings and DPLCs."

        else:
            try:
                # Resolve relative paths against the project directory
                configured_path = self.project.resolve_asset_path(self.dplc_path_input.text().strip())
            except (OSError, ValueError):
                configured_path = None

            if configured_path != self.dplc_buffer_path:
                status = "The DPLC path has changed. Load the configured DPLC file."
            elif not 0 <= frame_index < len(self.dplc_frames):
                status = f"No DPLC frame exists for mapping frame {frame_index}."
            elif not self.art_rows or not self.art_rows[0][4]:
                status = "Waiting for uncompressed art in buffer 1."
            else:
                path_input, compression, _, _, source_tiles = self.art_rows[0]
                if (compression.currentText() != "Uncompressed"
                    or self.art_buffer_compressions.get(path_input) != "Uncompressed"):
                    status = "DPLCs require buffer 1 to be loaded from uncompressed art."

        if not status:
            cues = self.dplc_frames[frame_index]
            destination = self.vram_spinbox.value()

            for cue in cues:
                source_start = cue['tile']

                # Stop if this entry starts AFTER the source buffer
                if not source_start < len(source_tiles):
                    status = (f"DPLC frame {frame_index} requests source tiles "
                              f"starting at tile offset ${cue['tile']:X}, "
                              f"which is AFTER the end of the source buffer. "
                              "DPLC loading stopped prematurely.")
                    break

                # Load only the tiles available in the source and destination
                available_count = min(cue['count'], len(source_tiles) - source_start, 2048 - destination)

                for source_index in range(source_start, source_start + available_count):
                    # Copy tiles from buffer 1 to VRAM
                    tiles[destination] = source_tiles[source_index].copy()
                    destination += 1

                # An incomplete entry ends loading for this frame
                if available_count < cue['count']:
                    break

        result = (tiles, status)
        self.dplc_vram_cache[frame_index] = result

        return result

    def dplc_refresh_vram(self):
        """
        Bring only the selected frame's tiles to VRAM.
        """
        self.vram_tiles, status = self.dplc_get_frame_vram(self.frame_spinbox.value())
        self.dplc_status_label.setText(status)

    def _on_dplc_settings_changed(self, *_):
        """
        Rebuild previews when DPLC mode, source path or format changes.
        """
        self.mapping_update_file_controls()
        self.art_refresh_vram()


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
            self.sprite_refresh_previews() # Refresh canvas AND thumbnails

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
            # Refresh frame window and thumbnails with new color
            self.sprite_refresh_previews()

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
        Render compiled VRAM or the complete selected art-file buffer.
        """
        option = self.viewer_art_combo.currentIndex()
        self.art_update_tile_controls()

        # 0 - self.vram_tiles (default)
        if option == 0:
            tiles = self.vram_tiles
            tile_count = 2048

        # 1-3 - self.art_buffer_paths[_i - 1] - load specified art buffer
        elif 1 <= option <= len(self.art_rows):
            # Source tiles start at index zero, independent of VRAM offset/count
            art_tiles = self.art_rows[option - 1][4]
            if not art_tiles:
                self.vram_label.clear()
                return

            tiles = dict(enumerate(art_tiles))
            tile_count = len(art_tiles)

        # Out-of-bounds case
        else:
            self.vram_label.clear()
            return

        # Render VRAM tile grid
        image = render_tile_grid(tiles, self.palette_colors, tile_count=tile_count,
            palette_line=self.viewer_line_combo.currentIndex())

        # Scale up 2x
        pixmap = QPixmap.fromImage(image)
        scaled_pixmap = pixmap.scaled(image.width() * 2, image.height() * 2,
            Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.FastTransformation)

        self.vram_label.setPixmap(scaled_pixmap)

    def sprite_build_frame_image(self, frame_idx, show_overlays=False):
        # Sync shared sources once before composing the frame
        tiles, _ = self.dplc_get_frame_vram(frame_idx)
        self.renderer.prepare(tiles, self.palette_colors,
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
