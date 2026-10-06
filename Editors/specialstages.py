"""Sonic 1 Special Stage Editor UI skeleton.

Clones the revised Tilemap Editor's toolbar, scrollable canvas and splitter.
The right panel contains the stage-cell browser and selected-cell controls.
File operations, cell rendering, filtering, selection and painting are not wired.
Editing controls are disabled; the splitter and collapsible file panel work.
"""

import PyQt6.QtWidgets as QtW
from PyQt6.QtCore import Qt, QSize

from UI.collapse_panel import CollapsiblePanel
from UI.widgets import (
    create_combobox,
    create_label,
    create_pushbutton,
    create_scrollarea,
    create_splitter,
    create_spinbox,
)

class SpecStageEditor(QtW.QWidget):
    def __init__(self, project=None):
        super().__init__()
        self.project = project

        # Placeholder layout dimensions and display size, independent of art tiles
        self.stage_width = 64
        self.stage_height = 64
        self.stage_cell_size = 24
        self.stage_zoom = 1
        self.ui_init()

    # --------------------------------------------------
    # UI Setup
    # --------------------------------------------------
    def ui_init(self):
        """Build the stage canvas/file panel and cell editing panel."""
        layout = QtW.QVBoxLayout(self)
        layout.addLayout(self.ui_build_file_toolbar())

        stage_panel = self.ui_build_stage_panel()
        editing_panel = self.ui_build_editing_panel()
        self.content_splitter = create_splitter(
            (stage_panel, editing_panel),
            orientation=Qt.Orientation.Horizontal,
            stretch_factors=(1, 1), sizes=(664, 336))
        layout.addWidget(self.content_splitter, stretch=1)

        self.btn_toggle_filemanager.setChecked(False)

        for widget_type in (QtW.QPushButton, QtW.QComboBox, QtW.QSpinBox,
                            QtW.QLineEdit, QtW.QCheckBox):
            for widget in self.findChildren(widget_type):
                if widget is not self.btn_toggle_filemanager:
                    widget.setEnabled(False)
        self.stage_file_table.setEditTriggers(
            QtW.QAbstractItemView.EditTrigger.NoEditTriggers)

    def ui_build_file_toolbar(self):
        toolbar = QtW.QHBoxLayout()
        toolbar.setSpacing(4)
        toolbar.setAlignment(Qt.AlignmentFlag.AlignLeft)

        self.stage_dropdown = create_combobox(
            tooltip="Select a special stage from the active project", layout=toolbar)

        for attribute, title, tooltip in (
            ("btn_stage_new", "New", "Create a special stage"),
            ("btn_stage_load", "Load", "Load a special stage"),
            ("btn_stage_save", "Save", "Save the current special stage"),
            ("btn_stage_save_as", "Save As...", "Save the stage to another file"),
            ("btn_stage_remove", "Remove", "Remove the stage from the project"),
        ):
            setattr(self, attribute, create_pushbutton(
                title, tooltip=tooltip, layout=toolbar))
        toolbar.addSpacing(12)
        self.format_label = create_label("Format: Sonic 1", layout=toolbar)
        toolbar.addStretch()
        return toolbar

    def ui_build_stage_panel(self):
        panel = QtW.QWidget()
        layout = QtW.QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.ui_build_stage_viewer(), stretch=2)
        layout.addWidget(self.ui_build_file_manager(), stretch=1)
        return panel


    def ui_build_stage_viewer(self):
        box = QtW.QGroupBox("Special Stage Editor")
        layout = QtW.QVBoxLayout(box)

        edit_toolbar = QtW.QHBoxLayout()
        edit_toolbar.setSpacing(4)

        btn_undo = create_pushbutton("Undo", tooltip="Undo the last change made",
            width=55, layout=edit_toolbar)
        btn_redo = create_pushbutton("Redo", tooltip="Redo the last undone change",
            width=55, layout=edit_toolbar)
        btn_copy = create_pushbutton("Copy", tooltip="Copy selected stage cells to the clipboard",
            width=55, layout=edit_toolbar)
        btn_paste = create_pushbutton("Paste", tooltip="Paste over the selected cell(s)",
            width=55, layout=edit_toolbar)
        btn_clear = create_pushbutton("Clear", tooltip="Clear selected cells to Empty",
            width=55, layout=edit_toolbar)

        create_pushbutton("Resize Stage", tooltip="Resize the stage", width=85, layout=edit_toolbar)

        edit_toolbar.addStretch()
        layout.addLayout(edit_toolbar)

        canvas_row = QtW.QHBoxLayout()

        # Scrollable canvas placeholder; stage-cell painting will be added later
        self.stage_label = QtW.QLabel("Stage Grid")
        self.stage_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.stage_label.setMargin(0)
        self.stage_label.setFrameShape(QtW.QFrame.Shape.NoFrame)
        self.stage_label.setFixedSize(
            self.stage_width * self.stage_cell_size * self.stage_zoom,
            self.stage_height * self.stage_cell_size * self.stage_zoom)
        self.stage_scroll = create_scrollarea(self.stage_label, resizable=False)
        self.stage_scroll.setAlignment(Qt.AlignmentFlag.AlignCenter)
        canvas_row.addWidget(self.stage_scroll, stretch=1)
        layout.addLayout(canvas_row, stretch=1)
        return box


    def ui_build_file_manager(self):
        self.stage_file_group = CollapsiblePanel(
            "Stage Data and Files", tooltip="Expand or collapse the file manager")
        self.btn_toggle_filemanager = self.stage_file_group.toggle_button
        layout = self.stage_file_group.content_layout

        toolbar = QtW.QHBoxLayout()
        toolbar.setSpacing(4)
        toolbar.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        for attribute, title, tooltip in (
            ("btn_layout_load", "Load Layout", "Load stage layout data"),
            ("btn_layout_save", "Save Layout", "Save stage layout data"),
            ("btn_layout_import", "Import...", "Import stage layout data"),
            ("btn_layout_export", "Export...", "Export stage layout data"),
        ):
            setattr(self, attribute, create_pushbutton(
                title, width=85, tooltip=tooltip, layout=toolbar))
        toolbar.addStretch()
        layout.addLayout(toolbar)

        self.stage_file_table = QtW.QTableWidget(0, 3)
        table = self.stage_file_table
        table.setHorizontalHeaderLabels(["File", "Compression", "Size (cells)"])
        table.setSelectionBehavior(QtW.QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QtW.QAbstractItemView.SelectionMode.SingleSelection)
        table.setSortingEnabled(False)
        table.verticalHeader().setDefaultSectionSize(20)
        table.verticalHeader().setSectionResizeMode(QtW.QHeaderView.ResizeMode.Fixed)
        table.horizontalHeader().setSectionResizeMode(0, QtW.QHeaderView.ResizeMode.Stretch)
        table.setColumnWidth(1, 120)
        table.setColumnWidth(2, 110)
        layout.addWidget(table, stretch=1)
        return self.stage_file_group

    def ui_build_editing_panel(self):
        panel = QtW.QWidget()
        layout = QtW.QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.ui_build_stage_cells(), stretch=1)
        layout.addWidget(self.ui_build_selected_cell())
        return panel

    def ui_build_stage_cells(self):
        box = QtW.QGroupBox("Stage Cells")
        layout = QtW.QVBoxLayout(box)

        filters = QtW.QHBoxLayout()
        filters.setSpacing(4)
        self.cell_filter_group = QtW.QButtonGroup(self)
        self.cell_filter_group.setExclusive(True)
        for attribute, title in (
            ("btn_cells_all", "All"), ("btn_cells_walls", "Walls"),
            ("btn_cells_objects", "Objects"),
        ):
            button = create_pushbutton(title, width=80, layout=filters)
            button.setCheckable(True)
            self.cell_filter_group.addButton(button)
            setattr(self, attribute, button)
        self.btn_cells_all.setChecked(True)
        filters.addStretch()
        layout.addLayout(filters)

        # Empty browser ready for cell icons/names from stage-cell definitions
        self.stage_cell_list = QtW.QListWidget()
        cell_list = self.stage_cell_list
        cell_list.setViewMode(QtW.QListView.ViewMode.IconMode)
        cell_list.setFlow(QtW.QListView.Flow.LeftToRight)
        cell_list.setWrapping(True)
        cell_list.setResizeMode(QtW.QListView.ResizeMode.Adjust)
        cell_list.setMovement(QtW.QListView.Movement.Static)
        cell_list.setIconSize(QSize(48, 48))
        cell_list.setGridSize(QSize(88, 80))
        cell_list.setSpacing(4)
        cell_list.setUniformItemSizes(True)
        cell_list.setWordWrap(True)
        cell_list.setSelectionMode(QtW.QAbstractItemView.SelectionMode.SingleSelection)
        cell_list.setEditTriggers(QtW.QAbstractItemView.EditTrigger.NoEditTriggers)
        cell_list.setDragDropMode(QtW.QAbstractItemView.DragDropMode.NoDragDrop)
        cell_list.setSortingEnabled(False)
        cell_list.setMinimumHeight(192)
        cell_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        layout.addWidget(cell_list, stretch=1)

        self.selected_brush_label = create_label("Selected brush: —", layout=layout)
        return box

    def ui_build_selected_cell(self):
        box = QtW.QGroupBox("Selected Cell")
        layout = QtW.QHBoxLayout(box)

        self.selected_cell_preview = QtW.QLabel("No cell")
        self.selected_cell_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.selected_cell_preview.setFrameShape(QtW.QFrame.Shape.StyledPanel)
        self.selected_cell_preview.setFixedSize(80, 80)
        layout.addWidget(self.selected_cell_preview)

        controls = QtW.QVBoxLayout()
        position_row = QtW.QHBoxLayout()
        create_label("X:", layout=position_row)
        self.cell_x_spinbox = create_spinbox(
            minimum=0, maximum=self.stage_width - 1, width=55,
            tooltip="Selected cell column", layout=position_row)
        create_label("Y:", layout=position_row)
        self.cell_y_spinbox = create_spinbox(
            minimum=0, maximum=self.stage_height - 1, width=55,
            tooltip="Selected cell row", layout=position_row)
        position_row.addStretch()
        controls.addLayout(position_row)

        type_row = QtW.QHBoxLayout()
        create_label("Cell type:", layout=type_row)
        self.cell_type_combo = create_combobox(
            tooltip="Type of the selected stage cell", layout=type_row)
        controls.addLayout(type_row)
        self.btn_select_matching = create_pushbutton(
            "Select Matching", width=120,
            tooltip="Select cells of the same type", layout=controls)
        controls.addStretch()
        layout.addLayout(controls, stretch=1)
        return box
