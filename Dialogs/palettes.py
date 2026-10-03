import PyQt6.QtWidgets as QtW
from PyQt6 import QtCore
from PyQt6.QtCore import pyqtSignal, Qt, QEvent, QPointF, QRectF
from PyQt6.QtGui import QColor, QImage, QPixmap, QPainter, QPen

from UI.md_color import snap_to_md_color, ColorLibrary

from constants import *

""" The following classes are subtypes for the AdvancedEditDialog class.
    They contain their own functions that edit facets of the main editor.
"""
class AdvancedEditDialog(QtW.QDialog):
    # Signal to apply changes to the palette's colors
    colors_applied = pyqtSignal(list)

    def __init__(self, editor, title="Advanced Editing"):
        super().__init__(editor)
        self.editor = editor
        self.setWindowTitle(title)
        self.setMinimumSize(680, 260)

        # Temp palette structures
        self.original_colors = []
        self.result_colors = []
        self.preview_boxes = []

        # Setup this window
        self.ui_init()
        self.reload_from_editor()

        # Connect signals for live background updating
        self.editor.selection_changed.connect(self.reload_from_editor)
        self.editor.palette_changed.connect(self.reload_from_editor)

    def ui_init(self):
        main_layout = QtW.QVBoxLayout(self)
        content_layout = QtW.QHBoxLayout()

        # -----------------------------
        # LEFT PANEL: Options
        # -----------------------------
        options_layout = QtW.QVBoxLayout()

        # Target Scope Option
        scope_group = QtW.QGroupBox("Target Scope")
        scope_layout = QtW.QVBoxLayout(scope_group)

        self.opt_all = QtW.QRadioButton("Entire Palette")
        self.opt_selected = QtW.QRadioButton("Selected Colors Only")

        # Default scope selection based on active selection count
        if len(self.editor.selected_indices) > 1:
            self.opt_selected.setChecked(True)
        else:
            self.opt_all.setChecked(True)

        self.opt_all.toggled.connect(self.update_preview)
        self.opt_selected.toggled.connect(self.update_preview)

        scope_layout.addWidget(self.opt_all)
        scope_layout.addWidget(self.opt_selected)
        options_layout.addWidget(scope_group)

        # Hook for Subclass-specific UI
        self.setup_custom_options(options_layout)

        options_layout.addStretch()
        content_layout.addLayout(options_layout, stretch=1)

        # -----------------------------
        # RIGHT PANEL: Palette Preview
        # -----------------------------
        preview_group = QtW.QGroupBox("Preview (Updates as you make changes)")
        preview_group_layout = QtW.QVBoxLayout(preview_group)

        scroll_area = QtW.QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_content = QtW.QWidget()

        self.grid_layout = QtW.QGridLayout(scroll_content)
        self.grid_layout.setSpacing(4)
        self.grid_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)

        scroll_area.setWidget(scroll_content)
        preview_group_layout.addWidget(scroll_area)
        content_layout.addWidget(preview_group, stretch=2)

        main_layout.addLayout(content_layout)

        # -----------------------------
        # BOTTOM PANEL: Action Buttons
        # -----------------------------
        buttons = QtW.QDialogButtonBox.StandardButton.Ok | QtW.QDialogButtonBox.StandardButton.Cancel
        btn_box = QtW.QDialogButtonBox(buttons)

        btn_apply = btn_box.button(QtW.QDialogButtonBox.StandardButton.Ok)
        btn_apply.setText("Apply")

        btn_apply.clicked.connect(self.on_apply)
        btn_box.rejected.connect(self.reject)
        main_layout.addWidget(btn_box)

    def on_apply(self):
        self.colors_applied.emit(self.result_colors)
        self.accept()

    def update_preview(self):
        only_selected = self.opt_selected.isChecked()

        for idx, original_color in enumerate(self.original_colors):
            # Check if color should be modified based on scope selection
            if only_selected and idx not in self.editor.selected_indices:
                self.result_colors[idx] = QColor(original_color)
            else:
                # Call the subclass-specific transformation
                self.result_colors[idx] = self.transform_color(original_color)

            # Update preview box color
            if idx < len(self.preview_boxes):
                self.preview_boxes[idx].setStyleSheet(
                    f"background-color: {self.result_colors[idx].name()}; border: 1px solid #444;"
                )

    def reload_from_editor(self):
        # Get updated colors and selections from the main window
        self.original_colors = [QColor(c) for c in self.editor.colors]

        # Rebuild preview boxes if palette size changed
        if len(self.original_colors) != len(self.preview_boxes):
            self.rebuild_preview_grid()

        # Reset result array length to match original
        self.result_colors = [QColor(c) for c in self.original_colors]
        self.update_preview()

    def rebuild_preview_grid(self):
        # Rebuild preview grid when palette size changes
        for box in self.preview_boxes:
            box.deleteLater()
        self.preview_boxes.clear()

        MAX_COLUMNS = 16
        for idx, color in enumerate(self.original_colors):
            row, col = idx // MAX_COLUMNS, idx % MAX_COLUMNS
            box = QtW.QFrame()
            box.setFixedSize(20, 20)
            self.grid_layout.addWidget(box, row, col)
            self.preview_boxes.append(box)

    def changeEvent(self, a0: QtCore.QEvent|None) -> None:
        # Sync with main window whenever this window gains focus
        if a0.type() == QEvent.Type.ActivationChange and self.isActiveWindow():
            self.reload_from_editor()
        super().changeEvent(a0)

    # --- Overridden by dialog subclasses ---
    def setup_custom_options(self, layout):
        pass

    # --- Overridden by dialog subclasses ---
    def transform_color(self, original_color):
        return QColor(original_color)


class ColorBlendDialog(AdvancedEditDialog):
    def __init__(self, editor):
        super().__init__(editor, title="Blend Colors")

    def setup_custom_options(self, layout):
        # -----------------------------
        # LEFT PANEL MOD: Color Blend Options
        # -----------------------------
        blend_group = QtW.QGroupBox("Blend Options")
        blend_layout = QtW.QVBoxLayout(blend_group)

        self.chk_split_toning = QtW.QCheckBox("Split Toning")
        self.chk_split_toning.setToolTip(
            "Brightness below 128 uses Shadows; "
            "128 and above uses Highlights."
        )
        blend_layout.addWidget(self.chk_split_toning)
        self.chk_split_toning.toggled.connect(self.on_split_toning_toggled)

        # Color Picker
        color_layout = QtW.QHBoxLayout()
        self.blend_label = QtW.QLabel("Blend Color:")

        self.color_preview = QtW.QFrame()
        self.color_preview.setFixedSize(32, 24)

        self.color_picker = QtW.QPushButton("Select Color")
        self.blend_color = QColor(0, 0, 0)
        self.color_picker.setAutoDefault(False)
        self.color_preview.setStyleSheet(f"background-color: {self.blend_color.name()}; border: 1px solid #444;")
        self.color_picker.clicked.connect(lambda: self.choose_color(False))

        color_layout.addWidget(self.blend_label)
        color_layout.addWidget(self.color_preview)
        color_layout.addWidget(self.color_picker)
        blend_layout.addLayout(color_layout)

        # Keep the second row visible while ordinary blending is selected
        self.highlight_controls = QtW.QWidget()
        highlight_layout = QtW.QHBoxLayout(self.highlight_controls)
        highlight_layout.setContentsMargins(0, 0, 0, 0)

        self.highlight_preview = QtW.QFrame()
        self.highlight_preview.setFixedSize(32, 24)

        self.highlight_picker = QtW.QPushButton("Select Color")
        self.highlight_color = QColor(255, 255, 255)
        self.highlight_picker.setAutoDefault(False)
        self.highlight_preview.setStyleSheet(f"background-color: {self.highlight_color.name()}; border: 1px solid #444;")
        self.highlight_picker.clicked.connect(lambda: self.choose_color(True))

        highlight_layout.addWidget(QtW.QLabel("Highlights:"))
        highlight_layout.addWidget(self.highlight_preview)
        highlight_layout.addWidget(self.highlight_picker)
        self.highlight_controls.setEnabled(False)
        blend_layout.addWidget(self.highlight_controls)

        # Percentage Selector
        blend_layout.addWidget(QtW.QLabel("Blend Amount:"))

        pct_layout = QtW.QHBoxLayout()

        self.blend_pct_slider = QtW.QSlider(Qt.Orientation.Horizontal)
        self.blend_pct_slider.setRange(10, 100)

        self.pct_tolerance = QtW.QSpinBox()
        self.pct_tolerance.setRange(10, 100)
        self.pct_tolerance.setSuffix("%")
        self.pct_tolerance.setSingleStep(10)
        self.pct_tolerance.setKeyboardTracking(False)

        self.blend_pct_slider.valueChanged.connect(self.on_percentage_changed)
        self.pct_tolerance.valueChanged.connect(self.on_percentage_changed)

        pct_layout.addWidget(self.blend_pct_slider)
        pct_layout.addWidget(self.pct_tolerance)
        blend_layout.addLayout(pct_layout)

        layout.addWidget(blend_group)

        self.update_color_previews()

    def on_percentage_changed(self, value):
        # Snap to the nearest multiple of ten
        snapped = ((value + 2) // 10) * 10

        # Synchronize without triggering another valueChanged signal
        self.blend_pct_slider.blockSignals(True)
        self.pct_tolerance.blockSignals(True)

        self.blend_pct_slider.setValue(snapped)
        self.pct_tolerance.setValue(snapped)

        self.blend_pct_slider.blockSignals(False)
        self.pct_tolerance.blockSignals(False)

        self.update_preview()

    def on_split_toning_toggled(self, enabled):
        self.blend_label.setText("Shadows:" if enabled else "Blend Color:")
        self.highlight_controls.setEnabled(enabled)
        self.update_preview()

    def choose_color(self, highlights=False):
        current_color = (self.highlight_color if highlights else self.blend_color)
#        title = "Choose Highlight Color" if highlights else (
#            "Choose Shadow Color"
#            if self.chk_split_toning.isChecked()
#            else "Choose Blend Color"
#        )
        dialog = ColorLibrary(current_color, self)

        if dialog.exec() == QtW.QDialog.DialogCode.Accepted:
            if highlights:
                self.highlight_color = dialog.get_color()
            else:
                self.blend_color = dialog.get_color()

            self.update_color_previews()
            self.update_preview()

    def update_color_previews(self):
        for preview, color in (
            (self.color_preview, self.blend_color),
            (self.highlight_preview, self.highlight_color),
        ):
            preview.setStyleSheet(
                f"background-color: {color.name()}; "
                "border: 1px solid #666;"
            )
            preview.setToolTip(color.name().upper())

    def transform_color(self, original_color):
        _r = original_color.red()
        _g = original_color.green()
        _b = original_color.blue()

        # By default, use the shadow color (primary blend color)
        target_color = self.blend_color

        # Determine whether to use Shadow or Highlight blend color
        # based on the brightness of the original color
        if self.chk_split_toning.isChecked():
            brightness = (299 * _r + 587 * _g + 114 * _b) / 1000.0

            # If this is a brighter color, use the highlight color
            if brightness >= 128:
                target_color = self.highlight_color

        # Get percentage as a decimal, and the inverse
        pct_str = self.pct_tolerance.value()
        blend_factor = int(pct_str) / 100.0     # Get percentage as a decimal
        inverse_factor = 1.0 - blend_factor

        # Calculate blended RGB color
        _r = int(_r * inverse_factor + target_color.red() * blend_factor)
        _g = int(_g * inverse_factor + target_color.green() * blend_factor)
        _b = int(_b * inverse_factor + target_color.blue() * blend_factor)

        # Convert to a compatible color
        step_r = snap_to_md_color(_r)
        step_g = snap_to_md_color(_g)
        step_b = snap_to_md_color(_b)

        return QColor(MDCOLOR_VALUES[step_r], MDCOLOR_VALUES[step_g], MDCOLOR_VALUES[step_b])


class GreyscaleDialog(AdvancedEditDialog):
    def __init__(self, editor):
        super().__init__(editor, title="Apply Greyscale")

    def setup_custom_options(self, layout):
        # -----------------------------
        # LEFT PANEL MOD: Greyscale Options
        # -----------------------------
        options_group = QtW.QGroupBox("Greyscale Options")
        options_layout = QtW.QVBoxLayout(options_group)

        # Greyscale Method
        options_layout.addWidget(QtW.QLabel("Method:"))
        self.combo_method = QtW.QComboBox()
        self.combo_method.addItems(["Luminosity", "Lightness", "Average"])
        options_layout.addWidget(self.combo_method)
        self.combo_method.currentIndexChanged.connect(self.update_preview)

        separator = QtW.QFrame()
        separator.setFrameShape(QtW.QFrame.Shape.HLine)
        separator.setFrameShadow(QtW.QFrame.Shadow.Sunken)

        options_layout.addSpacing(8)
        options_layout.addWidget(separator)
        options_layout.addSpacing(8)

        self.chk_color_popping = QtW.QCheckBox("Color Popping")
        options_layout.addWidget(self.chk_color_popping)
        self.chk_color_popping.toggled.connect(self.on_color_popping_toggled)

        self.pop_controls = QtW.QWidget()
        pop_layout = QtW.QVBoxLayout(self.pop_controls)
        pop_layout.setContentsMargins(0, 0, 0, 0)

        # Default target: red
        self.pop_color = QColor(MDCOLOR_VALUES[7], 0, 0)
        pop_layout.addWidget(QtW.QLabel("Target Color:"))

        color_layout = QtW.QHBoxLayout()
        self.pop_preview = QtW.QFrame()
        self.pop_preview.setFixedSize(40, 28)

        self.btn_pop_color = QtW.QPushButton("Select Color...")
        self.btn_pop_color.setAutoDefault(False)
        self.btn_pop_color.clicked.connect(self.choose_pop_color)

        color_layout.addWidget(self.pop_preview)
        color_layout.addWidget(self.btn_pop_color)
        pop_layout.addLayout(color_layout)

        """ To-Do: Add to tooltips later
        self.gs_luminosity.setToolTip("Weighted (0.299R, 0.587G, 0.114B)")
        self.gs_lightness.setToolTip("(Max(R,G,B) + Min(R,G,B)) / 2")
        self.gs_average.setToolTip("(R + G + B) / 3")"""

        # Hue Tolerance
        pop_layout.addWidget(QtW.QLabel("Hue Tolerance:"))

        tolerance_layout = QtW.QHBoxLayout()

        self.pop_tolerance_slider = QtW.QSlider(Qt.Orientation.Horizontal)
        self.pop_tolerance_slider.setRange(0, 100)

        self.pop_tolerance = QtW.QSpinBox()
        self.pop_tolerance.setRange(0, 100)
        self.pop_tolerance.setSuffix("%")
        self.pop_tolerance.setSingleStep(5)
        self.pop_tolerance.setKeyboardTracking(False)

        self.pop_tolerance_slider.valueChanged.connect(self.on_tolerance_changed)
        self.pop_tolerance.valueChanged.connect(self.on_tolerance_changed)

        self.pop_tolerance.setToolTip(
            "0% preserves only matching hues. "
            "100% includes all hues."
        )

        tolerance_layout.addWidget(self.pop_tolerance_slider)
        tolerance_layout.addWidget(self.pop_tolerance)
        pop_layout.addLayout(tolerance_layout)

        options_layout.addWidget(self.pop_controls)
        layout.addWidget(options_group)

        # Start with ordinary greyscale
        self.pop_controls.setEnabled(False)
        self.update_pop_preview()

    def on_tolerance_changed(self, value):
        # Snap to the nearest multiple of five
        snapped = ((value + 2) // 5) * 5

        # Synchronize without triggering another valueChanged signal
        self.pop_tolerance_slider.blockSignals(True)
        self.pop_tolerance.blockSignals(True)

        self.pop_tolerance_slider.setValue(snapped)
        self.pop_tolerance.setValue(snapped)

        self.pop_tolerance_slider.blockSignals(False)
        self.pop_tolerance.blockSignals(False)

        self.update_preview()

    def on_color_popping_toggled(self, enabled):
        self.pop_controls.setEnabled(enabled)
        self.update_preview()

    def choose_pop_color(self):
        dialog = ColorLibrary(self.pop_color, self)

        if dialog.exec() == QtW.QDialog.DialogCode.Accepted:
            self.pop_color = dialog.get_color()
            self.update_pop_preview()
            self.update_preview()

    def update_pop_preview(self):
        self.pop_preview.setStyleSheet(
            f"background-color: {self.pop_color.name()}; "
            "border: 1px solid #666;"
        )
        self.pop_preview.setToolTip(self.pop_color.name().upper())

    def matches_pop_hue(self, color):
        # Neutral colors have no hue to match
        if color.saturation() == 0 or self.pop_color.saturation() == 0:
            return False

        hue = color.hsvHueF()
        target_hue = self.pop_color.hsvHueF()

        # Shortest distance around the hue circle, in the range 0–0.5
        difference = abs(hue - target_hue)
        hue_distance = min(difference, 1.0 - difference)

        # 0% = exact hue; 100% = the full hue circle
        tolerance = self.pop_tolerance.value() / 200.0
        return hue_distance <= tolerance + 1e-9

    def transform_color(self, original_color):
        # Test the original hue before converting to greyscale
        if (self.chk_color_popping.isChecked() and self.matches_pop_hue(original_color)):
            return QColor(original_color)

        # Convert to greyscale
        _r, _g, _b = original_color.red(), original_color.green(), original_color.blue()

        # Calculate grey color value based on selected greyscale method
        method = self.combo_method.currentIndex()

        if method == 0:  # Luminosity
            grey_val = int(0.299 * _r + 0.587 * _g + 0.114 * _b)
        elif method == 1:  # Lightness
            grey_val = int((max(_r, _g, _b) + min(_r, _g, _b)) / 2)
        else:  # Average
            grey_val = int((_r + _g + _b) / 3)

        # Snap calculated grey to Mega Drive color limits
        step = snap_to_md_color(grey_val)
        md_grey = MDCOLOR_VALUES[step]

        return QColor(md_grey, md_grey, md_grey)


""" This window does not inherit AdvancedEditDialog
    I'll redo this later on.
"""
class GradientBuilderDialog(QtW.QDialog):
    gradient_applied = pyqtSignal(list)

    def __init__(self, editor):
        super().__init__(editor)
        self.editor = editor
        self.setWindowTitle("Build Gradient")
        self.setMinimumSize(680, 260)

        # Initial source color is the currently active color
        active_color = self.editor.colors[self.editor.active_index]
        self.color_src = QColor(active_color)
        self.color_dst = QColor(255, 255, 255)  # Default dest is white
        self.preview_boxes = []

        # Setup this window (Unlike the others, we don't need to live update)
        self.init_ui()
        self.update_gradient()

    def init_ui(self):
        main_layout = QtW.QVBoxLayout(self)
        content_layout = QtW.QHBoxLayout()

        # -----------------------------
        # LEFT PANEL: Options
        # -----------------------------
        options_layout = QtW.QVBoxLayout()

        control_group = QtW.QGroupBox("Gradient Options")
        control_layout = QtW.QGridLayout(control_group)

        # Source Color Picker
        self.btn_src = QtW.QPushButton("Select Source Color")
        self.btn_src.clicked.connect(lambda: self.choose_color('src'))
        self.lbl_src = QtW.QFrame()
        self.lbl_src.setFixedSize(20, 20)
        self.update_color_label('src')

        control_layout.addWidget(self.btn_src, 0, 0)
        control_layout.addWidget(self.lbl_src, 0, 1)

        # Dest Color Picker
        self.btn_dst = QtW.QPushButton("Select Dest Color")
        self.btn_dst.clicked.connect(lambda: self.choose_color('dst'))
        self.lbl_dst = QtW.QFrame()
        self.lbl_dst.setFixedSize(20, 20)
        self.update_color_label('dst')

        control_layout.addWidget(self.btn_dst, 1, 0)
        control_layout.addWidget(self.lbl_dst, 1, 1)

        # Length Configuration
        control_layout.addWidget(QtW.QLabel("Gradient Length:"), 2, 0)
        self.grad_length = QtW.QSpinBox()
        self.grad_length.setRange(2, PALEDIT_MAXCOLORS)
        self.grad_length.setValue(8)
        self.grad_length.valueChanged.connect(self.update_gradient)
        control_layout.addWidget(self.grad_length, 2, 1)

        # Loop Toggle
        self.chk_loop = QtW.QCheckBox("Loop Gradient")
        self.chk_loop.toggled.connect(self.update_gradient)
        control_layout.addWidget(self.chk_loop, 3, 0)

        options_layout.addWidget(control_group)
        options_layout.addStretch()
        content_layout.addLayout(options_layout, stretch=1)

        # -----------------------------
        # RIGHT PANEL: Gradient Preview
        # -----------------------------
        preview_group = QtW.QGroupBox("Gradient Preview")
        preview_group_layout = QtW.QVBoxLayout(preview_group)

        scroll_area = QtW.QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_content = QtW.QWidget()

        self.grid_layout = QtW.QGridLayout(scroll_content)
        self.grid_layout.setSpacing(4)
        self.grid_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)

        scroll_area.setWidget(scroll_content)
        preview_group_layout.addWidget(scroll_area)
        content_layout.addWidget(preview_group, stretch=2)

        main_layout.addLayout(content_layout)

        # -----------------------------
        # BOTTOM PANEL: Action Buttons
        # -----------------------------
        buttons = QtW.QDialogButtonBox.StandardButton.Ok | QtW.QDialogButtonBox.StandardButton.Cancel
        btn_box = QtW.QDialogButtonBox(buttons)

        btn_apply = btn_box.button(QtW.QDialogButtonBox.StandardButton.Ok)
        btn_apply.setText("Apply")

        btn_apply.clicked.connect(self.on_apply)
        btn_box.rejected.connect(self.reject)
        main_layout.addWidget(btn_box)

    def on_apply(self):
        self.gradient_applied.emit(self.calc_gradient())
        self.accept()

    def update_gradient(self):
        # Rebuild gradient on change
        for box in self.preview_boxes:
            box.deleteLater()
        self.preview_boxes.clear()

        colors = self.calc_gradient()
        MAX_COLUMNS = 16
        for idx, color in enumerate(colors):
            row, col = idx // MAX_COLUMNS, idx % MAX_COLUMNS
            box = QtW.QFrame()
            box.setFixedSize(20, 20)
            box.setStyleSheet(f"background-color: {color.name()}; border: 1px solid #444;")
            self.grid_layout.addWidget(box, row, col)
            self.preview_boxes.append(box)

    def choose_color(self, target):
        current = self.color_src if target == 'src' else self.color_dst
        color = QtW.QColorDialog.getColor(current, self, "Select Color")

        if color.isValid():
            if target == 'src':
                self.color_src = color
            else:
                self.color_dst = color

            self.update_color_label(target)
            self.update_gradient()

    def update_color_label(self, target):
        color = self.color_src if target == 'src' else self.color_dst
        lbl = self.lbl_src if target == 'src' else self.lbl_dst
        lbl.setStyleSheet(f"background-color: {color.name()}; border: 1px solid #444;")

    def calc_gradient(self):
        length = self.grad_length.value()
        loop = self.chk_loop.isChecked()
        colors = []

        for _i in range(length):
            if loop:
                # Wave mapping (NEW): returns a blend factor (_t) that goes from 0 to 1 and back to >0
                _t = 1.0 - abs(1.0 - (2.0 * _i / length))
            else:
                # Linear mapping (Original Triad: merge_color(src, dest, ((i-pals[a])/(grad_length-1))) )
                _t = _i / (length - 1) if length > 1 else 0

            inv_t = 1.0 - _t
            _r = int(self.color_src.red() * inv_t + self.color_dst.red() * _t)
            _g = int(self.color_src.green() * inv_t + self.color_dst.green() * _t)
            _b = int(self.color_src.blue() * inv_t + self.color_dst.blue() * _t)

            # Convert to MD colors
            step_r = snap_to_md_color(_r)
            step_g = snap_to_md_color(_g)
            step_b = snap_to_md_color(_b)
            colors.append(QColor(MDCOLOR_VALUES[step_r], MDCOLOR_VALUES[step_g], MDCOLOR_VALUES[step_b]))

        return colors


""" Basic Palette Extractor
    To-Do: Add full palette generation from screenshot 
"""
class PaletteExtractDialog(QtW.QDialog):
    def __init__(self, editor):
        super().__init__(editor)
        self.editor = editor
        self.setWindowTitle("Extract Palette")
        self.setMinimumSize(800, 600)

        self.init_ui()

    def init_ui(self):
        main_layout = QtW.QVBoxLayout(self)

        # Top Bar: Load Button & Status
        top_layout = QtW.QHBoxLayout()
        btn_load = QtW.QPushButton("Load Image...")
        btn_load.clicked.connect(self.browse_image)
        lbl_status = QtW.QLabel("Left-Click to Pick Color | Scroll to Zoom | Right-Click to Pan")

        top_layout.addWidget(btn_load)
        top_layout.addSpacing(15)
        top_layout.addWidget(lbl_status)
        top_layout.addStretch()
        main_layout.addLayout(top_layout)

        # Workspace: Picker View + Magnifier
        workspace_layout = QtW.QHBoxLayout()

        self.picker_view = ImagePickerView()
        self.picker_view.pixel_hovered.connect(self.on_pixel_hover)
        self.picker_view.pixel_clicked.connect(self.on_pixel_picked)

        self.magnifier = MagnifierWidget()

        # Right Side Panel
        side_panel = QtW.QVBoxLayout()
        side_panel.addWidget(self.magnifier)
        side_panel.addStretch()

        workspace_layout.addWidget(self.picker_view, stretch=1)
        workspace_layout.addLayout(side_panel)
        main_layout.addLayout(workspace_layout)

    def browse_image(self):
        file_path, _ = QtW.QFileDialog.getOpenFileName(
            self, "Open Image", "", "Images (*.png *.bmp *.gif *.jpg)"
        )
        if file_path:
            self.picker_view.load_image(file_path)

    def on_pixel_hover(self, image, scene_pos):
        self.magnifier.update_view(image, scene_pos)

    def on_pixel_picked(self, raw_color):
        # Snaps picked color
        _r = min(MDCOLOR_VALUES, key=lambda x: abs(x - raw_color.red()))
        _g = min(MDCOLOR_VALUES, key=lambda x: abs(x - raw_color.green()))
        _b = min(MDCOLOR_VALUES, key=lambda x: abs(x - raw_color.blue()))
        snapped_color = QColor(_r, _g, _b)

        # # Record state before extracting color
        self.editor.history_push_state()

        # Apply to current index in main editor
        self.editor.edit_set_active_color(snapped_color)
        self.editor.update_unsaved_changes()

        # Advance selection sequentially, wrapping around if needed
        next_idx = (self.editor.active_index + 1) % len(self.editor.colors)
        self.editor.active_index = next_idx
        self.editor.selected_indices = [next_idx]
        self.editor.palette_refresh_highlighting()


class ImagePickerView(QtW.QGraphicsView):
    """Handles image display, zoom, pan, and click/hover events for PaletteExtractDialog"""
    pixel_hovered = pyqtSignal(QImage, QPointF)
    pixel_clicked = pyqtSignal(QColor)

    def __init__(self):
        super().__init__()
        self.scene = QtW.QGraphicsScene(self)
        self.setScene(self.scene)
        self.setMouseTracking(True)
        self.setTransformationAnchor(QtW.QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setDragMode(QtW.QGraphicsView.DragMode.NoDrag)

        # Optional: Hide scroll-bars
#        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
#        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.image = None
        self.image_map = None
        self.pan_start = None   # initial mouse position on right-click

    def load_image(self, file_path):
        self.image = QImage(file_path)
        pixmap = QPixmap.fromImage(self.image)
        self.scene.clear()
        self.image_map = self.scene.addPixmap(pixmap)
        self.setSceneRect(QRectF(pixmap.rect()))
        self.fitInView(self.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def wheelEvent(self, event):
        zoom_factor = 1.25 if event.angleDelta().y() > 0 else 0.8
        self.scale(zoom_factor, zoom_factor)

    def mouseMoveEvent(self, event):
        super().mouseMoveEvent(event)

        # Handle Right-Click Panning
        if (event.buttons() & Qt.MouseButton.RightButton) and self.pan_start is not None:
            delta = event.pos() - self.pan_start
            self.pan_start = event.pos()

            # Scroll canvas in reverse direction of mouse motion
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - delta.x())
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - delta.y())
            return

        # Magnifier updates
        if self.image_map and self.image:
            scene_pos = self.mapToScene(event.pos())
            self.pixel_hovered.emit(self.image, scene_pos)

    def mousePressEvent(self, event):
        # Left-click: Extract color
        if event.button() == Qt.MouseButton.LeftButton and self.image_map and self.image:
            scene_pos = self.mapToScene(event.pos())
            x, y = int(scene_pos.x()), int(scene_pos.y())
            if 0 <= x < self.image.width() and 0 <= y < self.image.height():
                self.pixel_clicked.emit(self.image.pixelColor(x, y))

        # Right-click: Panning
        elif event.button() == Qt.MouseButton.RightButton:
            self.pan_start = event.pos()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return

        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        # Right-click: Stop panning
        if event.button() == Qt.MouseButton.RightButton:
            self.pan_start = None
            self.unsetCursor()
            event.accept()
            return

        super().mouseReleaseEvent(event)


class MagnifierWidget(QtW.QWidget):
    """Displays a zoomed-in pixel grid and crosshair for PaletteExtractDialog"""
    def __init__(self):
        super().__init__()
        self.setFixedSize(140, 140)
        self.image = None
        self.hover_pos = QPointF(0, 0)
        self.zoom = 10  # Pixel scale factor

    def update_view(self, image, pos):
        self.image = image
        self.hover_pos = pos
        self.update()

    def paintEvent(self, a0):
        painter = QPainter(self)
        painter.fillRect(self.rect(), Qt.GlobalColor.black)
        if not self.image:
            return

        src_x, src_y = int(self.hover_pos.x()), int(self.hover_pos.y())
        pixels_across = self.width() // self.zoom
        half_pixels = pixels_across // 2

        # Draw magnified pixels
        for dx in range(-half_pixels, half_pixels + 1):
            for dy in range(-half_pixels, half_pixels + 1):
                px, py = src_x + dx, src_y + dy
                if 0 <= px < self.image.width() and 0 <= py < self.image.height():
                    color = self.image.pixelColor(px, py)
                    rect = QRectF((dx + half_pixels) * self.zoom, (dy + half_pixels) * self.zoom, self.zoom, self.zoom)
                    painter.fillRect(rect, color)

        # Draw grid
        painter.setPen(QColor(80, 80, 80, 180))
        for i in range(pixels_across + 1):
            painter.drawLine(i * self.zoom, 0, i * self.zoom, self.height())
            painter.drawLine(0, i * self.zoom, self.width(), i * self.zoom)

        # Draw center crosshair
        center = half_pixels * self.zoom
        painter.setPen(QPen(Qt.GlobalColor.white, 1))
        painter.drawRect(center, center, self.zoom, self.zoom)
        painter.setPen(QPen(Qt.GlobalColor.black, 1, Qt.PenStyle.DotLine))
        painter.drawRect(center, center, self.zoom, self.zoom)
