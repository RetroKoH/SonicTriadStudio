import PyQt6.QtWidgets as QtW
from PyQt6.QtCore import Qt

from UI.widgets import create_toolbutton

class CollapsiblePanel(QtW.QGroupBox):
    """Embedded panel with a permanent header and collapsible content."""

    def __init__(self, title, *, tooltip="", parent=None):
        super().__init__(parent)

        self._splitter = None
        self._splitter_sizes = None

        self.panel_layout = QtW.QVBoxLayout(self)

        # Header remains visible when collapsed
        self.header_layout = QtW.QHBoxLayout()

        self.toggle_button = create_toolbutton(
            title,
            arrow_type=Qt.ArrowType.DownArrow,
            tool_button_style=Qt.ToolButtonStyle.ToolButtonTextBesideIcon,
            checkable=True,
            checked=True,
            tooltip=tooltip,
            layout=self.header_layout,
        )

        self.header_layout.addStretch()
        self.panel_layout.addLayout(self.header_layout)

        # Editors place their content inside this body
        self.content_widget = QtW.QWidget()
        self.content_layout = QtW.QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(0, 0, 0, 0)

        self.panel_layout.addWidget(self.content_widget)

        self.toggle_button.toggled.connect(self._on_toggled)

    def set_splitter(self, splitter):
        """Remember this splitter's divider positions when collapsing."""
        self._splitter = splitter

    def set_expanded(self, expanded):
        """Expand or collapse through the toggle button."""
        self.toggle_button.setChecked(expanded)

    def _on_toggled(self, expanded):
        if expanded:
            self.setMinimumHeight(0)
            self.setMaximumHeight(16777215)

            self.content_widget.show()
            self.toggle_button.setArrowType(Qt.ArrowType.DownArrow)
            self.panel_layout.activate()

            if (
                self._splitter is not None
                and self._splitter_sizes is not None
            ):
                self._splitter.setSizes(self._splitter_sizes)

        else:
            if self._splitter is not None:
                sizes = self._splitter.sizes()

                # Avoid remembering an uninitialized, all-zero layout
                if any(sizes):
                    self._splitter_sizes = sizes

            self.content_widget.hide()
            self.toggle_button.setArrowType(Qt.ArrowType.RightArrow)
            self.panel_layout.activate()

            # With the body hidden, sizeHint represents the header
            self.setFixedHeight(self.sizeHint().height())

        self.updateGeometry()
