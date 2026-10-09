import PyQt6.QtWidgets as QtW
from PyQt6.QtCore import Qt

class AssetInfo(QtW.QDialog):
    def __init__(self, name, asset_type, details, parent=None):
        super().__init__(parent)

        self.setWindowTitle(f"Asset Information — {name}")
        self.resize(460, 260)

        layout = QtW.QVBoxLayout(self)
        form = QtW.QFormLayout()
        form.setFieldGrowthPolicy(QtW.QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        layout.addLayout(form)

        rows = [
            ("Name", name),
            ("Type", asset_type),
            *details
        ]

        for label, value in rows:
            value_label = QtW.QLabel(str(value))
            value_label.setTextFormat(Qt.TextFormat.PlainText)
            value_label.setWordWrap(True)
            value_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            form.addRow(f"{label}:", value_label)

        layout.addStretch()

        buttons = QtW.QDialogButtonBox(QtW.QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
