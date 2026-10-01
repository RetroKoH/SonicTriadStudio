import PyQt6.QtWidgets as QtW
from PyQt6.QtCore import Qt

class TriadApp(QtW.QMainWindow):
    def __init__(self, app):
        super().__init__()
        self.app = app

        self.setWindowTitle("Sonic Triad Studio - RetroKoH 2027")
        self.resize(1024, 768)
        self.setMinimumSize(800, 600)

        mainWidget = QtW.QWidget()
        self.setCentralWidget(mainWidget)
        mainLayout = QtW.QVBoxLayout(mainWidget)

        # Mode Tabs
        self.tabs = QtW.QTabWidget()
        mainLayout.addWidget(self.tabs)

        # Preferences button
        self.prefButton = QtW.QPushButton("Preferences")
        self.tabs.setCornerWidget(self.prefButton, Qt.Corner.TopRightCorner)

        # Init tabs
        self.init_tab("Project")
        self.init_tab("Palettes")
        self.init_tab("Sprites")
        self.init_tab("Animations")
        self.init_tab("Levels")
        self.init_tab("Objects")
        self.init_tab("Tilemaps")
        self.init_tab("Special Stages")

        # Status label
        self.statusLabel = QtW.QLabel("Status: Idle")
        self.statusLabel.setFixedHeight(20)
        mainLayout.addWidget(self.statusLabel)

    def init_tab(self, name):
        tab = QtW.QTabWidget()
        layout = QtW.QVBoxLayout(tab)

        header = QtW.QLabel(f"{name} Editor")
        header.setFixedHeight(40)
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.tabs.addTab(tab, name)
