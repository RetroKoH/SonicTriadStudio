import PyQt6.QtWidgets as QtW
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QPainter, QPen

from constants import MDCOLOR_VALUES, QCOL_BLACK
from UI.themes import THEMES

def snap_to_md_color(value):
    # Snaps an RGB color value to its corresponding index (0-7)
    value = min(MDCOLOR_VALUES, key=lambda x: abs(x - value))
    return MDCOLOR_VALUES.index(value)

""" Color Library
    Specialized color picker that only allows for validated colors.
"""
class ColorLibrary(QtW.QDialog):
    def __init__(self, color, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Color Library")

        # Color variables
        self.current_color = QColor(color)
        self.r_step = snap_to_md_color(color.red())
        self.g_step = snap_to_md_color(color.green())
        self.b_step = snap_to_md_color(color.blue())
        self.selected_color = QColor(color)

        # Containers for box and button elements
        self.grid_boxes = {}
        self.line_boxes = []
        self.channel_groups = {}

        # UI handles
        self.current_preview = None
        self.preview_box = None
        self.cram_label = None
        self.hex_label = None

        self.ui_init()
        self.update_preview()

    def ui_init(self):
        layout = QtW.QVBoxLayout(self)
        layout.addWidget(QtW.QLabel("Choose a color to replace the existing color."))
        content_layout = QtW.QHBoxLayout()
        content_layout.setSpacing(16)

        # To-Do: Add a preference setting to change how colors are laid out

        # BLUE/GREEN grid
        grid_column = QtW.QVBoxLayout()
        grid_column.addWidget(QtW.QLabel("BLUE / GREEN"))
        grid_layout = QtW.QGridLayout()
        grid_layout.setSpacing(0)

        # Iterate downward from left to right for 8 rows
        for row in range(8):
            # Rows progressively decrease green
            g_step = 7 - row
            # Columns progressively increase blue
            for b_step in range(8):
                box = ColorLibraryBox()
                box.setAccessibleName(f"Blue {b_step}, Green {g_step}")
                box.clicked.connect(lambda _, _g=g_step, _b=b_step: self._on_color_picked(self.r_step, _g, _b))
                grid_layout.addWidget(box, row, b_step)
                self.grid_boxes[g_step, b_step] = box

        grid_column.addLayout(grid_layout)
        grid_column.addStretch()
        content_layout.addLayout(grid_column)

        # RED line
        line_column = QtW.QVBoxLayout()
        line_column.addWidget(QtW.QLabel("RED"))
        line_layout = QtW.QVBoxLayout()
        line_layout.setSpacing(0)

        # Iterate downward for 8 boxes in a column
        for row in range(8):
            # Boxes progressively decrease red
            r_step = 7 - row
            box = ColorLibraryBox()
            box.setAccessibleName(f"Red {r_step}")
            box.clicked.connect(lambda _, _r=r_step: self._on_color_picked(_r, self.g_step, self.b_step))
            line_layout.addWidget(box)
            self.line_boxes.append(box)

        line_column.addLayout(line_layout)
        line_column.addStretch()
        content_layout.addLayout(line_column)

        # Current stays unchanged while New follows the candidate color.
        details_layout = QtW.QVBoxLayout()
        previews = QtW.QHBoxLayout()

        self.current_preview = QtW.QFrame()
        self.preview_box = QtW.QFrame()

        for title, preview in (("Current", self.current_preview), ("New", self.preview_box)):
            column = QtW.QVBoxLayout()
            column.addWidget(QtW.QLabel(title))

            preview.setMinimumWidth(112)
            preview.setFixedHeight(56)

            column.addWidget(preview)
            previews.addLayout(column)

        # There has to be a more efficient way to do this
        app = QtW.QApplication.instance()
        theme = getattr(app, "active_theme", THEMES["dark"])
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {self.current_color.name()};
                border: 1px solid {theme.get("box_border", "#444444")};                
            }}
        """)

        details_layout.addLayout(previews)
        details_layout.addSpacing(8)

        for channel in ('r', 'g', 'b'):
            row = QtW.QHBoxLayout()
            row.setSpacing(2)
            row.addWidget(QtW.QLabel(channel.upper()))
            group = QtW.QButtonGroup(self)
            group.setExclusive(True)

            for step in range(8):
                button = QtW.QPushButton(str(step))
                button.setCheckable(True)
                button.setAutoDefault(False)
                button.setFixedSize(28, 28)
                button.setAccessibleName(f"{channel.upper()} step {step}")
                group.addButton(button, step)
                row.addWidget(button)

            group.idClicked.connect(lambda _step, ch=channel: self._on_channel_changed(ch, _step))
            self.channel_groups[channel] = group
            details_layout.addLayout(row)

        details_layout.addSpacing(8)
        self.cram_label = QtW.QLabel()
        self.hex_label = QtW.QLabel()

        for title, label in (("CRAM code (0B GR)", self.cram_label), ("Hex color (RR GG BB)", self.hex_label)):
            row = QtW.QHBoxLayout()
            row.addWidget(QtW.QLabel(title))
            row.addStretch()
            label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            row.addWidget(label)
            details_layout.addLayout(row)

        details_layout.addStretch()
        content_layout.addLayout(details_layout)
        layout.addLayout(content_layout)

        buttons = QtW.QDialogButtonBox.StandardButton.Ok | QtW.QDialogButtonBox.StandardButton.Cancel
        btn_box = QtW.QDialogButtonBox(buttons)
        btn_box.button(QtW.QDialogButtonBox.StandardButton.Ok).setText("Apply")
        btn_box.accepted.connect(self.accept)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

    def update_preview(self):
        _r = MDCOLOR_VALUES[self.r_step]
        _g = MDCOLOR_VALUES[self.g_step]
        _b = MDCOLOR_VALUES[self.b_step]
        self.selected_color = QColor(_r, _g, _b)

        for (g_step, b_step), box in self.grid_boxes.items():
            color = QColor(_r, MDCOLOR_VALUES[g_step], MDCOLOR_VALUES[b_step])
            box.set_color(color, g_step == self.g_step and b_step == self.b_step)
            box.setToolTip(f"B: {b_step}  G: {g_step}  {color.name().upper()}")

        for row, box in enumerate(self.line_boxes):
            r_step = 7 - row
            color = QColor(MDCOLOR_VALUES[r_step], _g, _b)
            box.set_color(color, r_step == self.r_step)
            box.setToolTip(f"R: {r_step}  {color.name().upper()}")

        for channel, group in self.channel_groups.items():
            group.button(getattr(self, f"{channel}_step")).setChecked(True)

        self.preview_box.setStyleSheet(f"background-color: {self.selected_color.name()}; border: 1px solid #666;")
        # Same 0BGR packing used by the palette writer (three bits per channel).
        cram_word = (self.b_step << 9) | (self.g_step << 5) | (self.r_step << 1)
        self.cram_label.setText(f"${cram_word:04X}")
        self.hex_label.setText(self.selected_color.name().upper())

    def get_color(self):
        return QColor(self.selected_color)

    def _on_channel_changed(self, channel, step):
        setattr(self, f"{channel}_step", step)
        self.update_preview()

    def _on_color_picked(self, r_step, g_step, b_step):
        self.r_step = r_step
        self.g_step = g_step
        self.b_step = b_step

        self.update_preview()

""" Color Library Box (PaletteEditor)
    Used within the Color Library.
    When clicked, pulls its color to be used in an editor.
    Color updates in real-time as user changes selection.
"""
class ColorLibraryBox(QtW.QToolButton):
    """Selectable color box inside the ColorLibrary dialog."""
    def __init__(self):
        super().__init__()
        self.color = QCOL_BLACK
        self.selected = False
        self.setFixedSize(36, 36)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

    def set_color(self, color, selected=False):
        self.color = QColor(color)
        self.selected = selected
        self.update()

    def paintEvent(self, a0):
        painter = QPainter(self)
        painter.fillRect(self.rect(), self.color)
        if self.selected:
            painter.setPen(QPen(QColor("#666666"), 2))
            painter.drawRect(self.rect().adjusted(1, 1, -2, -2))
            painter.setPen(QPen(QColor("#FFFFFF"), 2))
            painter.drawRect(self.rect().adjusted(3, 3, -4, -4))
