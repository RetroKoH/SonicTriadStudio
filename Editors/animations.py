"""Animation Editor UI skeleton.

Initial Animation Editor layout, with UI factories.
File operations, project integration, sprite rendering, sequence editing and
playback functions are not wired. Editing controls are disabled placeholders;
tabs, splitters, and the collapsible file panel still work. Still WIP!
"""

import PyQt6.QtWidgets as QtW
from PyQt6.QtCore import Qt, QSize

from UI.collapse_panel import CollapsiblePanel
from UI.widgets import (
    create_combobox,
    create_label,
    create_lineedit,
    create_pushbutton,
    create_scrollarea,
    create_splitter,
    create_spinbox,
)


class AnimationEditor(QtW.QWidget):
    def __init__(self, project=None):
        super().__init__()
        self.ui_init()

    # --------------------------------------------------
    # UI Setup
    # --------------------------------------------------
    def ui_init(self):
        """Top-level UI constructor"""
        layout = QtW.QVBoxLayout(self)

        # TOP PANEL TOOLBAR
        layout.addLayout(self.ui_build_file_toolbar())

        animation_panel = self.ui_build_animation_panel()  # LEFT PANEL: Animation Viewer
        editing_panel = self.ui_build_editing_panel()  # RIGHT PANEL: Editing Controls

        # Horizontal splitter between the animation viewer and editing controls
        self.content_splitter = create_splitter((animation_panel, editing_panel),
            orientation=Qt.Orientation.Horizontal, stretch_factors=(1, 1), sizes=(664, 336))
        layout.addWidget(self.content_splitter, stretch=1)

        # Anim Timeline will be in a closed tray
        self.btn_toggle_sequence.setChecked(False)

        # Testing a dynamic status bar. I will NOT implement it here
        #layout.addLayout(self.ui_build_status_bar())

    def ui_build_file_toolbar(self):
        """
        File toolbar constructor (Dropdown and file buttons)

        Returns:
            QtW.QHBoxLayout (file_toolbar; Contains ComboBox and PushButtons)
        """
        toolbar = QtW.QHBoxLayout()
        toolbar.setSpacing(4)
        toolbar.setAlignment(Qt.AlignmentFlag.AlignLeft)

        # Animation Dropdown
        self.anim_dropdown = create_combobox(
            tooltip="Select an animation from the active project",
            layout=toolbar)

        # File Buttons
        create_pushbutton("New", tooltip="Create an animation",
            layout=toolbar)
        create_pushbutton("Load", tooltip="Load animation data",
            layout=toolbar)
        create_pushbutton("Save", tooltip="Save the current animation",
            layout=toolbar)
        create_pushbutton("Save As...", tooltip="Save animation data to another file",
            layout=toolbar)
        create_pushbutton("Remove", tooltip="Remove the current animation",
            layout=toolbar)

        toolbar.addStretch()
        return toolbar

    def ui_build_animation_panel(self):
        animation_panel = QtW.QWidget()
        animation_layout = QtW.QVBoxLayout(animation_panel)
        animation_layout.setContentsMargins(0, 0, 0, 0)

        animation_layout.addWidget(self.ui_build_animation_viewer(), stretch=2)
        animation_layout.addWidget(self.ui_build_frame_sequence(), stretch=1)
        return animation_panel

    def ui_build_animation_viewer(self):
        animation_box = QtW.QGroupBox("Animation Preview")
        viewer_layout = QtW.QVBoxLayout(animation_box)
        viewer_layout.addLayout(self.ui_build_preview_controls())

        preview_hint_label = create_label(
            "Scroll to Zoom | Click-drag to Pan",
            layout=viewer_layout)

        # To-Do: add this to QSS
        hint_font = preview_hint_label.font()
        hint_font.setPointSizeF(max(8.0, hint_font.pointSizeF() - 1.0))
        preview_hint_label.setFont(hint_font)

        self.animation_label = QtW.QLabel("Animation preview")
        self.animation_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.animation_label.setMinimumSize(256, 192)
        self.animation_label.setMargin(0)
        self.animation_label.setFrameShape(QtW.QFrame.Shape.NoFrame)

        self.animation_scroll = create_scrollarea(self.animation_label)
        self.animation_scroll.setAlignment(Qt.AlignmentFlag.AlignCenter)
        viewer_layout.addWidget(self.animation_scroll, stretch=1)

        self.playback_slider = QtW.QSlider(Qt.Orientation.Horizontal)
        self.playback_slider.setRange(0, 0)
        self.playback_slider.setEnabled(False)
        self.playback_slider.setToolTip("Position in the animation sequence")
        viewer_layout.addWidget(self.playback_slider)

        viewer_layout.addLayout(self.ui_build_playback_controls())
        return animation_box

    def ui_build_preview_controls(self):
        controls = QtW.QVBoxLayout()

        zoom_row = QtW.QHBoxLayout()
        zoom_row.setSpacing(4)
        zoom_row.addWidget(QtW.QLabel("Zoom:"))
        self.zoom_combo = create_combobox(
            max_width=100,
            items=["1×", "2×", "4×", "8×", "16×"],
            tooltip="Preview zoom", layout=zoom_row)
        self.zoom_combo.setCurrentIndex(1)
        self.btn_zoom_reset = create_pushbutton(
            "1:1", tooltip="Reset preview zoom", layout=zoom_row)
        self.btn_preview_center = create_pushbutton(
            "Center", tooltip="Center the preview", layout=zoom_row)
        zoom_row.addStretch()

        self.origin_checkbox = QtW.QCheckBox("Origin")
        self.origin_checkbox.setChecked(True)
        self.grid_checkbox = QtW.QCheckBox("Grid")
        self.bounds_checkbox = QtW.QCheckBox("Bounds")
        for checkbox in (self.origin_checkbox, self.grid_checkbox,
                         self.bounds_checkbox):
            zoom_row.addWidget(checkbox)
            checkbox.setEnabled(False)

        for widget in (self.zoom_combo, self.btn_zoom_reset,
                       self.btn_preview_center):
            widget.setEnabled(False)
        controls.addLayout(zoom_row)
        return controls

    def ui_build_playback_controls(self):
        controls = QtW.QVBoxLayout()
        transport_row = QtW.QHBoxLayout()
        transport_row.setSpacing(4)

        # Standard Qt icons follow the application's active style
        style = self.style()
        transport_specs = (
            ("btn_first_frame", QtW.QStyle.StandardPixmap.SP_MediaSkipBackward,
             "First frame"),
            ("btn_previous_frame", QtW.QStyle.StandardPixmap.SP_MediaSeekBackward,
             "Previous frame"),
            ("btn_play", QtW.QStyle.StandardPixmap.SP_MediaPlay, "Play / pause"),
            ("btn_next_frame", QtW.QStyle.StandardPixmap.SP_MediaSeekForward,
             "Next frame"),
            ("btn_last_frame", QtW.QStyle.StandardPixmap.SP_MediaSkipForward,
             "Last frame"),
        )
        for attribute, icon, tooltip in transport_specs:
            button = create_pushbutton(
                "", width=36, tooltip=tooltip, enabled=False,
                layout=transport_row)
            button.setIcon(style.standardIcon(icon))
            button.setAccessibleName(tooltip)
            setattr(self, attribute, button)

        self.playback_frame_label = QtW.QLabel("Frame — of 0")
        transport_row.addWidget(self.playback_frame_label)
        transport_row.addStretch()

        self.loop_preview_checkbox = QtW.QCheckBox("Loop preview")
        self.loop_preview_checkbox.setChecked(True)
        self.loop_preview_checkbox.setEnabled(False)
        transport_row.addWidget(self.loop_preview_checkbox)
        transport_row.addStretch()
        transport_row.addWidget(QtW.QLabel("Speed:"))
        self.playback_speed_combo = create_combobox(
            max_width=100,
            items=["0.25×", "0.5×", "1×", "2×", "4×"],
            tooltip="Preview playback speed", layout=transport_row)
        self.playback_speed_combo.setCurrentIndex(2)
        self.playback_speed_combo.setEnabled(False)

        controls.addLayout(transport_row)
        return controls

    def ui_build_frame_sequence(self):
        # Frame Sequence Viewer
        self.ani_sequence_group = CollapsiblePanel("Sequence Viewer",
            tooltip="Expand or collapse the sequence viewer")

        self.btn_toggle_sequence = self.ani_sequence_group.toggle_button

        # Scrollable Sequence Viewer
        sequencer = QtW.QWidget()
        self.ani_sequence_layout = QtW.QGridLayout(sequencer)
        self.ani_sequence_layout.setSpacing(6)
        self.ani_sequence_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)

        self.clipboard_scroll = create_scrollarea(sequencer, layout=self.ani_sequence_group.content_layout)

        """sequence_box = QtW.QGroupBox("Frame Sequence")
        sequence_layout = QtW.QVBoxLayout(sequence_box)
        toolbar = QtW.QHBoxLayout()
        toolbar.setSpacing(4)
        for attribute, text in (
            ("btn_sequence_undo", "Undo"),
            ("btn_sequence_redo", "Redo"),
            ("btn_frame_add", "Add Frame"),
            ("btn_frame_duplicate", "Duplicate"),
            ("btn_frame_remove", "Remove"),
        ):
            setattr(self, attribute, create_pushbutton(
                text, enabled=False, layout=toolbar))
        toolbar.addStretch()
        sequence_layout.addLayout(toolbar)

        self.frame_sequence_list = self.ui_create_frame_list(wrapping=False)
        self.frame_sequence_list.setMinimumHeight(160)
        sequence_layout.addWidget(self.frame_sequence_list, stretch=1)

        footer = QtW.QHBoxLayout()
        self.sequence_hint_label = QtW.QLabel("No frames in sequence")
        self.sequence_summary_label = QtW.QLabel("0 frames")
        footer.addWidget(self.sequence_hint_label)
        footer.addStretch()
        footer.addWidget(self.sequence_summary_label)
        sequence_layout.addLayout(footer)"""

        return self.ani_sequence_group

    def ui_build_editing_panel(self):
        """
        Right-side panel constructor (Editing tools).

        Returns:
            QtW.QScrollArea (which contains the editing panel group)
        """
        editing_panel = QtW.QWidget()
        editing_layout = QtW.QVBoxLayout(editing_panel)
        editing_layout.setContentsMargins(0, 0, 0, 0)

        editing_layout.addWidget(self.ui_build_sprite_frames(), stretch=1)
        editing_layout.addWidget(self.ui_build_selected_frame())
        editing_layout.addWidget(self.ui_build_animation_settings())

        return editing_panel

    def ui_build_sprite_frames(self):
        sprite_box = QtW.QGroupBox("Sprite Frames")
        sprite_layout = QtW.QVBoxLayout(sprite_box)
        selector_row = QtW.QHBoxLayout()
        selector_row.addWidget(QtW.QLabel("Sprite:"))
        self.sprite_dropdown = create_combobox(
            tooltip="Sprite build supplying the animation frames",
            layout=selector_row)
        sprite_layout.addLayout(selector_row)

        self.sprite_frames_list = self.ui_create_frame_list(wrapping=True)
        self.sprite_frames_list.setMinimumHeight(180)
        sprite_layout.addWidget(self.sprite_frames_list, stretch=1)
        self.btn_add_to_sequence = create_pushbutton(
            "Add to Sequence", tooltip="Append the selected sprite frame",
            width=180, enabled=False, layout=sprite_layout)
        return sprite_box

    def ui_build_selected_frame(self):
        selected_box = QtW.QGroupBox("Selected Frame")
        selected_layout = QtW.QHBoxLayout(selected_box)
        controls = QtW.QVBoxLayout()
        self.sequence_index_label = QtW.QLabel("Sequence index: —")
        controls.addWidget(self.sequence_index_label)

        frame_row = QtW.QHBoxLayout()
        frame_row.addWidget(QtW.QLabel("Sprite frame:"))
        self.sprite_frame_combo = create_combobox(
            tooltip="Sprite frame used by this sequence entry", layout=frame_row)
        self.sprite_frame_combo.setEnabled(False)
        controls.addLayout(frame_row)
        self.frame_delay_hint_label = QtW.QLabel("Uses animation delay")
        controls.addWidget(self.frame_delay_hint_label)
        controls.addStretch()
        selected_layout.addLayout(controls, stretch=1)

        self.selected_frame_label = QtW.QLabel("No frame")
        self.selected_frame_label.setFixedSize(96, 96)
        self.selected_frame_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.selected_frame_label.setFrameShape(QtW.QFrame.Shape.StyledPanel)
        selected_layout.addWidget(self.selected_frame_label)
        return selected_box

    def ui_build_animation_settings(self):
        settings_box = QtW.QGroupBox("Animation Settings")
        settings_layout = QtW.QVBoxLayout(settings_box)
        form = QtW.QFormLayout()
        form.setFieldGrowthPolicy(
            QtW.QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)

        self.anim_name_input = create_lineedit(tooltip="Animation name")
        form.addRow("Name:", self.anim_name_input)

        delay_row = QtW.QHBoxLayout()
        self.anim_delay_spinbox = create_spinbox(
            minimum=0, maximum=255, value=7, width=70,
            tooltip="Animation frame delay", layout=delay_row)
        delay_row.addWidget(QtW.QLabel("ticks"))
        delay_row.addStretch()
        form.addRow("Frame delay:", delay_row)

        # Only the default is available atm (no functionality)
        self.end_action_combo = create_combobox(
            items=["Loop"], tooltip="Action at the end of the sequence")
        form.addRow("End action:", self.end_action_combo)
        self.loop_from_spinbox = create_spinbox(
            minimum=0, maximum=0, width=70,
            tooltip="Sequence index to return to")
        form.addRow("Loop from:", self.loop_from_spinbox)
        settings_layout.addLayout(form)

        self.end_action_hint_label = QtW.QLabel("Returns to sequence frame 0")
        self.end_action_hint_label.setWordWrap(True)
        settings_layout.addWidget(self.end_action_hint_label)
        for widget in (self.anim_name_input, self.anim_delay_spinbox,
                       self.end_action_combo, self.loop_from_spinbox):
            widget.setEnabled(False)
        return settings_box

    def ui_build_status_bar(self):
        status_layout = QtW.QHBoxLayout()
        self.animation_status_label = QtW.QLabel("Animation: —  ·  0 frames")
        self.preview_status_label = QtW.QLabel("Frame — of 0  ·  Zoom 2×")
        self.editor_status_label = QtW.QLabel("UI skeleton")
        status_layout.addWidget(self.animation_status_label)
        status_layout.addStretch()
        status_layout.addWidget(self.preview_status_label)
        status_layout.addStretch()
        status_layout.addWidget(self.editor_status_label)
        return status_layout

    def ui_create_frame_list(self, wrapping):
        frame_list = QtW.QListWidget()
        frame_list.setViewMode(QtW.QListView.ViewMode.IconMode)
        frame_list.setFlow(QtW.QListView.Flow.LeftToRight)
        frame_list.setWrapping(wrapping)
        frame_list.setResizeMode(QtW.QListView.ResizeMode.Adjust)
        frame_list.setMovement(QtW.QListView.Movement.Static)
        frame_list.setIconSize(QSize(96, 80))
        frame_list.setGridSize(QSize(116, 112))
        frame_list.setSpacing(4)
        frame_list.setUniformItemSizes(True)
        frame_list.setSelectionMode(
            QtW.QAbstractItemView.SelectionMode.SingleSelection)
        frame_list.setEditTriggers(
            QtW.QAbstractItemView.EditTrigger.NoEditTriggers)
        frame_list.setDragDropMode(
            QtW.QAbstractItemView.DragDropMode.NoDragDrop)
        frame_list.setHorizontalScrollMode(
            QtW.QAbstractItemView.ScrollMode.ScrollPerPixel)
        frame_list.setVerticalScrollMode(
            QtW.QAbstractItemView.ScrollMode.ScrollPerPixel)
        if not wrapping:
            frame_list.setVerticalScrollBarPolicy(
                Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        return frame_list
