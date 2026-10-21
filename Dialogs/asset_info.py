import PyQt6.QtWidgets as QtW
from PyQt6.QtCore import Qt

class AssetInfo(QtW.QDialog):
    def __init__(self, name, asset_type, details, apply_changes,
                 project, parent=None, palette_path=None):
        super().__init__(parent)

        self.apply_changes = apply_changes
        self.project = project
        self.path_input = None

        self.setWindowTitle(f"Asset Information — {name}")
        self.resize(460, 260)

        layout = QtW.QVBoxLayout(self)
        form = QtW.QFormLayout()
        form.setFieldGrowthPolicy(QtW.QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        layout.addLayout(form)

        # Keep changes in the fields until Ok is clicked
        self.name_input = QtW.QLineEdit(name)
        form.addRow("Name:", self.name_input)

        for label, value in [("Type", asset_type), *details]:
            value_label = QtW.QLabel(str(value))
            value_label.setTextFormat(Qt.TextFormat.PlainText)
            value_label.setWordWrap(True)
            value_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            form.addRow(f"{label}:", value_label)

        if palette_path is not None:
            path_widget = QtW.QWidget()
            path_layout = QtW.QHBoxLayout(path_widget)
            path_layout.setContentsMargins(0, 0, 0, 0)

            self.path_input = QtW.QLineEdit(palette_path)
            path_layout.addWidget(self.path_input, stretch=1)

            browse_button = QtW.QToolButton()
            browse_button.setText("...")
            browse_button.clicked.connect(self.browse_palette_path)
            path_layout.addWidget(browse_button)

            form.addRow("Project path:", path_widget)

            # Show whether the currently entered path points to a file
            self.file_exists_label = QtW.QLabel()
            form.addRow("File exists:", self.file_exists_label)

            self.path_input.textChanged.connect(self.update_path_status)
            self.update_path_status(self.path_input.text())

        layout.addStretch()

        buttons = QtW.QDialogButtonBox(QtW.QDialogButtonBox.StandardButton.Ok
            | QtW.QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def browse_palette_path(self):
        try:
            current_path = self.project.resolve_asset_path(self.path_input.text().strip())

        except (OSError, ValueError):
            current_path = None

        start_path = str(current_path or self.project.root_dir or "")

        # DontConfirmOverwrite prevents the unnecessary overwrite prompt
        # (To-Do: Add that dialog option to the other save dialogs)
        file_path, _ = QtW.QFileDialog.getSaveFileName(self,
            "Palette Save Path", start_path,
            "Palette Files (*.bin *.pal);;All Files (*)",
            options=QtW.QFileDialog.Option.DontConfirmOverwrite)

        # Browsing only changes the field until Ok is clicked
        if file_path:
            self.path_input.setText(self.project.store_asset_path(file_path))

    def update_path_status(self, text):
        try:
            path = self.project.resolve_asset_path(text.strip())
            exists = path is not None and path.is_file()

        except (OSError, ValueError):
            exists = False

        self.file_exists_label.setText("Yes" if exists else "No")

    def accept(self):
        path = self.path_input.text() if self.path_input is not None else None

        # Apply both fields together and close only after success
        if self.apply_changes(self.name_input.text(), path):
            super().accept()
