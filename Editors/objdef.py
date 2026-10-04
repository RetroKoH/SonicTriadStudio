"""Object Definitions Editor UI skeleton.

Obvious note: diverted away from the layout scheme used in the other editors,
in favor of a three-column set-up. Still a work-in-progress.

File operations, project integration, rendering and editing are not implemented.
Tables start empty and editing controls are disabled placeholders. No object
definition file format or game-specific serialization is prescribed here.
"""

import PyQt6.QtWidgets as QtW
from PyQt6.QtCore import Qt

from UI.widgets import (
    create_combobox,
    create_label,
    create_lineedit,
    create_pushbutton,
    create_scrollarea,
    create_splitter,
    create_spinbox,
)


class ObjectDefEditor(QtW.QWidget):
    def __init__(self, project=None):
        super().__init__()
        self.project = project
        self.ui_init()

    # --------------------------------------------------
    # UI Setup
    # --------------------------------------------------
    def ui_init(self):
        """Construct the toolbar and three panel columns."""
        layout = QtW.QVBoxLayout(self)
        layout.addLayout(self.ui_build_file_toolbar())

        definitions_panel = self.ui_build_definitions_panel()
        preview_panel = self.ui_build_object_viewer()
        editing_panel = self.ui_build_editing_panel()
        self.content_splitter = create_splitter(
            (definitions_panel, preview_panel, editing_panel),
            orientation=Qt.Orientation.Horizontal,
            stretch_factors=(0, 1, 1), sizes=(280, 520, 420))
        self.content_splitter.setChildrenCollapsible(False)
        layout.addWidget(self.content_splitter, stretch=1)

    def ui_build_file_toolbar(self):
        toolbar = QtW.QHBoxLayout()
        toolbar.setSpacing(4)
        toolbar.setAlignment(Qt.AlignmentFlag.AlignLeft)

        create_label("Definition Set:", layout=toolbar)
        # Definition Dropdown
        self.definition_set_dropdown = create_combobox(
            tooltip="Object definition set used by a level", layout=toolbar)

        for attribute, title, tooltip in (
            ("btn_file_new", "New", "Create an object definition set"),
            ("btn_file_load", "Load", "Load an object definition set"),
            ("btn_file_save", "Save", "Save the current definition set"),
            ("btn_file_save_as", "Save As...", "Save to another file"),
            ("btn_file_remove", "Remove", "Remove the set from the project"),
        ):
            setattr(self, attribute, create_pushbutton(
                title, tooltip=tooltip, enabled=False, layout=toolbar))

        toolbar.addStretch()
        return toolbar

    def ui_build_object_viewer(self):
        box = QtW.QGroupBox("Object Preview")
        layout = QtW.QVBoxLayout(box)

        zoom_row = QtW.QHBoxLayout()
        zoom_row.setSpacing(4)
        create_label("Zoom:", layout=zoom_row)

        self.zoom_combo = create_combobox(
            items=["1×", "2×", "4×", "8×", "16×"], max_width=100,
            tooltip="Object preview zoom", layout=zoom_row)

        self.zoom_combo.setCurrentIndex(1)

        self.btn_zoom_reset = create_pushbutton(
            "1:1", tooltip="Reset preview zoom", layout=zoom_row)

        self.btn_preview_center = create_pushbutton(
            "Center", tooltip="Center the object preview", layout=zoom_row)

        zoom_row.addStretch()
        layout.addLayout(zoom_row)

        overlay_row = QtW.QHBoxLayout()
        self.origin_checkbox = QtW.QCheckBox("Origin")
        self.origin_checkbox.setChecked(True)
        self.grid_checkbox = QtW.QCheckBox("Grid")
        self.bounds_checkbox = QtW.QCheckBox("Bounds")

        for checkbox in (self.origin_checkbox, self.grid_checkbox, self.bounds_checkbox):
            overlay_row.addWidget(checkbox)

        overlay_row.addStretch()
        layout.addLayout(overlay_row)

        self.preview_hint_label = create_label(
            "No object definition selected", layout=layout)
        self.object_preview_label = QtW.QLabel("Object preview")
        self.object_preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.object_preview_label.setMinimumSize(256, 192)
        self.object_preview_label.setMargin(0)
        self.object_preview_label.setFrameShape(QtW.QFrame.Shape.NoFrame)
        self.object_preview_scroll = create_scrollarea(self.object_preview_label)
        self.object_preview_scroll.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.object_preview_scroll, stretch=1)

        variant_row = QtW.QHBoxLayout()
        create_label("Subtype:", layout=variant_row)
        self.preview_subtype_combo = create_combobox(
            max_width=200, tooltip="Preview a named object subtype", layout=variant_row)
        variant_row.addStretch()
        self.preview_xflip_checkbox = QtW.QCheckBox("X-Flip")
        self.preview_yflip_checkbox = QtW.QCheckBox("Y-Flip")
        variant_row.addWidget(self.preview_xflip_checkbox)
        variant_row.addWidget(self.preview_yflip_checkbox)
        layout.addLayout(variant_row)

        self.ui_disable_controls(
            self.zoom_combo, self.btn_zoom_reset, self.btn_preview_center,
            self.origin_checkbox, self.grid_checkbox, self.bounds_checkbox,
            self.preview_subtype_combo, self.preview_xflip_checkbox,
            self.preview_yflip_checkbox)
        return box

    def ui_build_definitions_panel(self):
        """Permanent left-side definition list and entry actions."""
        self.definitions_group = QtW.QGroupBox("Object Definitions")
        self.definitions_group.setMinimumWidth(245)
        layout = QtW.QVBoxLayout(self.definitions_group)

        self.definition_search_input = create_lineedit(
            tooltip="Filter definitions by ID or name", layout=layout)
        self.definition_search_input.setPlaceholderText("Search ID or name…")
        self.definition_search_input.setEnabled(False)

        self.definitions_table = self.ui_create_table(["ID", "Name"])
        self.definitions_table.setMinimumHeight(140)
        header = self.definitions_table.horizontalHeader()
        header.setSectionResizeMode(0, QtW.QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(1, QtW.QHeaderView.ResizeMode.Stretch)
        header.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.definitions_table.setColumnWidth(0, 65)
        self.definitions_table.setWordWrap(False)
        self.definitions_table.setToolTip("Object definitions in ascending hexadecimal ID order")

        # Sort by integer and format it as hexadecimal
        header.setSortIndicator(0, Qt.SortOrder.AscendingOrder)
        header.setSortIndicatorShown(True)
        header.setSectionsClickable(False)

        layout.addWidget(self.definitions_table, stretch=1)
        layout.addLayout(self.ui_build_entry_toolbar("definition"))
        self.definition_count_label = create_label("0 definitions", layout=layout)
        return self.definitions_group

    def ui_build_editing_panel(self):
        self.definition_editing_group = QtW.QGroupBox("Object Definition — No selection")
        panel = self.definition_editing_group
        layout = QtW.QVBoxLayout(panel)

        # To-Do: Update this group's title with the selected
        # definition's name and hexadecimal ID (Platform — $18).
        self.editing_tabs = QtW.QTabWidget()
        self.editing_tabs.setUsesScrollButtons(True)

        for title, builder in (
            ("General", self.ui_build_general_tab),
            ("Sprites", self.ui_build_sprites_tab),
            ("Subtypes", self.ui_build_subtypes_tab),
            ("Properties", self.ui_build_properties_tab),
            ("Enums", self.ui_build_enums_tab),
            ("Display", self.ui_build_display_tab)
        ):
            self.editing_tabs.addTab(create_scrollarea(builder()), title)
        layout.addWidget(self.editing_tabs, stretch=1)
        return panel

    def ui_build_general_tab(self):
        tab = QtW.QWidget()
        layout = QtW.QVBoxLayout(tab)
        form = QtW.QFormLayout()

        self.object_id_input = create_lineedit(tooltip="Object ID in the layout")
        self.object_id_input.setPlaceholderText("Object ID")
        self.object_name_input = create_lineedit(tooltip="Name shown in the Level Editor")
        self.object_category_input = create_lineedit(tooltip="Object browser category")
        self.default_subtype_input = create_lineedit(tooltip="Default subtype value")
        self.default_subtype_input.setText("0")
        self.default_sprite_combo = create_combobox(
            tooltip="Default sprite entry for this definition")
        form.addRow("Object ID:", self.object_id_input)
        form.addRow("Name:", self.object_name_input)
        form.addRow("Category:", self.object_category_input)
        form.addRow("Default subtype:", self.default_subtype_input)
        form.addRow("Default sprite:", self.default_sprite_combo)
        layout.addLayout(form)

        self.remember_state_checkbox = QtW.QCheckBox("Remember state")
        self.debug_checkbox = QtW.QCheckBox("Include in debug object list")
        layout.addWidget(self.remember_state_checkbox)
        layout.addWidget(self.debug_checkbox)
        create_label("Description:", layout=layout)
        self.object_description_input = QtW.QPlainTextEdit()
        self.object_description_input.setPlaceholderText("Description for the Level Editor")
        self.object_description_input.setMinimumHeight(90)
        layout.addWidget(self.object_description_input)
        layout.addStretch()

        self.ui_disable_controls(
            self.object_id_input, self.object_name_input, self.object_category_input,
            self.default_subtype_input, self.default_sprite_combo,
            self.remember_state_checkbox, self.debug_checkbox,
            self.object_description_input)
        return tab

    def ui_build_sprites_tab(self):
        tab = QtW.QWidget()
        layout = QtW.QVBoxLayout(tab)
        self.sprites_table = self.ui_create_table(["Name", "Sprite Build", "Frame"])
        layout.addWidget(self.sprites_table, stretch=1)
        layout.addLayout(self.ui_build_entry_toolbar("sprite"))
        create_label("Selected Sprite", object_name="infoLabel", layout=layout)

        form = QtW.QFormLayout()
        self.sprite_name_input = create_lineedit(tooltip="Name of this sprite entry")
        self.sprite_build_dropdown = create_combobox(
            tooltip="Project sprite build used by this entry")
        self.sprite_frame_combo = create_combobox(tooltip="Mapping frame to display")
        self.sprite_x_spinbox = create_spinbox(
            minimum=-32768, maximum=32767, width=80, tooltip="Display offset X")
        self.sprite_y_spinbox = create_spinbox(
            minimum=-32768, maximum=32767, width=80, tooltip="Display offset Y")
        form.addRow("Name:", self.sprite_name_input)
        form.addRow("Sprite build:", self.sprite_build_dropdown)
        form.addRow("Frame:", self.sprite_frame_combo)
        form.addRow("Offset X:", self.sprite_x_spinbox)
        form.addRow("Offset Y:", self.sprite_y_spinbox)
        layout.addLayout(form)

        flips = QtW.QHBoxLayout()
        self.sprite_xflip_checkbox = QtW.QCheckBox("X-Flip")
        self.sprite_yflip_checkbox = QtW.QCheckBox("Y-Flip")
        flips.addWidget(self.sprite_xflip_checkbox)
        flips.addWidget(self.sprite_yflip_checkbox)
        flips.addStretch()
        layout.addLayout(flips)
        self.ui_disable_controls(
            self.sprite_name_input, self.sprite_build_dropdown, self.sprite_frame_combo,
            self.sprite_x_spinbox, self.sprite_y_spinbox,
            self.sprite_xflip_checkbox, self.sprite_yflip_checkbox)
        return tab

    def ui_build_subtypes_tab(self):
        tab = QtW.QWidget()
        layout = QtW.QVBoxLayout(tab)
        self.subtypes_table = self.ui_create_table(["Value", "Name", "Sprite"])
        layout.addWidget(self.subtypes_table, stretch=1)
        layout.addLayout(self.ui_build_entry_toolbar("subtype"))
        create_label("Selected Subtype", object_name="infoLabel", layout=layout)

        form = QtW.QFormLayout()
        self.subtype_value_input = create_lineedit(tooltip="Subtype value")
        self.subtype_name_input = create_lineedit(tooltip="Name shown in the object browser")
        self.subtype_sprite_combo = create_combobox(
            tooltip="Sprite entry used by this subtype")
        form.addRow("Value:", self.subtype_value_input)
        form.addRow("Name:", self.subtype_name_input)
        form.addRow("Sprite:", self.subtype_sprite_combo)
        layout.addLayout(form)
        self.ui_disable_controls(
            self.subtype_value_input, self.subtype_name_input, self.subtype_sprite_combo)
        return tab

    def ui_build_properties_tab(self):
        tab = QtW.QWidget()
        layout = QtW.QVBoxLayout(tab)
        self.properties_table = self.ui_create_table(["Name", "Type", "Source"])
        layout.addWidget(self.properties_table, stretch=1)
        layout.addLayout(self.ui_build_entry_toolbar("property"))
        create_label("Selected Property", object_name="infoLabel", layout=layout)

        form = QtW.QFormLayout()
        self.property_name_input = create_lineedit(tooltip="Property display name")
        self.property_type_combo = create_combobox(
            items=["Integer", "Boolean", "Enum"], tooltip="Proposed property control type")
        self.property_source_combo = create_combobox(
            items=["Subtype"], tooltip="Object field containing this property")
        self.property_mask_input = create_lineedit(tooltip="Bits used by this property")
        self.property_shift_input = create_lineedit(tooltip="Bit shift used to read the value")
        self.property_default_input = create_lineedit(tooltip="Default property value")
        self.property_enum_combo = create_combobox(tooltip="Named value set for an enum property")
        for label, widget in (
            ("Name:", self.property_name_input), ("Type:", self.property_type_combo),
            ("Source:", self.property_source_combo), ("Mask:", self.property_mask_input),
            ("Shift:", self.property_shift_input), ("Default:", self.property_default_input),
            ("Enum:", self.property_enum_combo),
        ):
            form.addRow(label, widget)
            widget.setEnabled(False)
        layout.addLayout(form)
        return tab

    def ui_build_enums_tab(self):
        tab = QtW.QWidget()
        layout = QtW.QVBoxLayout(tab)
        self.enums_table = self.ui_create_table(["Enum Name"])
        layout.addWidget(self.enums_table, stretch=1)
        layout.addLayout(self.ui_build_entry_toolbar("enum"))

        name_row = QtW.QHBoxLayout()
        create_label("Name:", layout=name_row)
        self.enum_name_input = create_lineedit(
            tooltip="Name of the selected enum", layout=name_row)
        self.enum_name_input.setEnabled(False)
        layout.addLayout(name_row)
        create_label("Named Values", object_name="infoLabel", layout=layout)
        self.enum_values_table = self.ui_create_table(["Value", "Label"])
        layout.addWidget(self.enum_values_table, stretch=1)
        layout.addLayout(self.ui_build_entry_toolbar("enum_value"))
        return tab

    def ui_build_display_tab(self):
        tab = QtW.QWidget()
        layout = QtW.QVBoxLayout(tab)
        hint = create_label(
            "Display rules choose a sprite entry from an object's property values.",
            layout=layout)
        hint.setWordWrap(True)
        self.display_rules_table = self.ui_create_table(["Property", "Value", "Sprite"])
        layout.addWidget(self.display_rules_table, stretch=1)
        layout.addLayout(self.ui_build_entry_toolbar("display_rule"))
        create_label("Selected Rule", object_name="infoLabel", layout=layout)

        form = QtW.QFormLayout()
        self.rule_property_combo = create_combobox(tooltip="Property to compare")
        self.rule_value_input = create_lineedit(tooltip="Property value to match")
        self.rule_sprite_combo = create_combobox(tooltip="Sprite to display when matched")
        form.addRow("Property:", self.rule_property_combo)
        form.addRow("Equals:", self.rule_value_input)
        form.addRow("Sprite:", self.rule_sprite_combo)
        layout.addLayout(form)
        self.ui_disable_controls(
            self.rule_property_combo, self.rule_value_input, self.rule_sprite_combo)
        return tab

    # --------------------------------------------------
    # Shared UI Builders
    # --------------------------------------------------
    def ui_build_entry_toolbar(self, prefix):
        """Expose each placeholder action as btn_<prefix>_<action>."""
        toolbar = QtW.QHBoxLayout()
        toolbar.setSpacing(4)
        for action, title, width in (
            ("add", "Add", 65), ("duplicate", "Duplicate", 85),
            ("remove", "Remove", 65),
        ):
            button = create_pushbutton(
                title, width=width, enabled=False, layout=toolbar)
            setattr(self, f"btn_{prefix}_{action}", button)
        toolbar.addStretch()
        return toolbar

    def ui_create_table(self, headers):
        """Create an empty, non-editable list for later data integration."""
        table = QtW.QTableWidget(0, len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.setSelectionBehavior(QtW.QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QtW.QAbstractItemView.SelectionMode.SingleSelection)
        table.setEditTriggers(QtW.QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setSortingEnabled(False)
        table.setMinimumHeight(120)
        table.verticalHeader().hide()
        table.verticalHeader().setDefaultSectionSize(24)
        table.verticalHeader().setSectionResizeMode(QtW.QHeaderView.ResizeMode.Fixed)
        table.horizontalHeader().setSectionResizeMode(QtW.QHeaderView.ResizeMode.Stretch)
        return table

    def ui_disable_controls(self, *widgets):
        """Keep editing placeholders inactive while UI navigation stays usable."""
        for widget in widgets:
            widget.setEnabled(False)
