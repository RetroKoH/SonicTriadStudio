from pathlib import Path

import PyQt6.QtWidgets as QtW
from PyQt6 import QtGui
from PyQt6.QtCore import Qt

from Core.project import Project
from UI.themes import apply_theme
from Editors import *

class TriadApp(QtW.QMainWindow):
    def __init__(self, app):
        super().__init__()
        self.app = app
        self.app.setStyle("Fusion")

        # Window theme (color scheme)
        apply_theme(app, set_theme="Dark")

        # Project Manager
        self.project = Project()

        self.setWindowTitle("Sonic Triad Studio - RetroKoH 2027")
        self.resize(1024, 768)
        self.setMinimumSize(800, 600)

        main_widget = QtW.QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QtW.QVBoxLayout(main_widget)

        # Mode Tabs
        self.tabs = QtW.QTabWidget()
        main_layout.addWidget(self.tabs)

        # Theme button (Later, this will be a preferences button)
        self.theme_button = QtW.QPushButton("Dark")
        self.theme_button.clicked.connect(self.toggle_theme)
        self.tabs.setCornerWidget(self.theme_button, Qt.Corner.TopRightCorner)

        # Init editing tools
        self.palette_editor = PaletteEditor(self.project)
        self.sprite_editor = SpriteEditor(self.project)
        self.animation_editor = AnimationEditor(self.project)
        self.level_editor = LevelEditor(self.project)
        self.objdef_editor = ObjectDefEditor(self.project)
        self.tilemap_editor = TilemapEditor(self.project)
        self.special_editor = SpecStageEditor(self.project)

        self.init_tabs()

        # Connecting function for when project is loaded
        self.project.project_loaded.connect(self.project_refresh_dashboard)

        # Status label
        self.statusLabel = QtW.QLabel("Status: Idle")
        self.statusLabel.setFixedHeight(20)
        main_layout.addWidget(self.statusLabel)

    def toggle_theme(self):
        # Set to the next theme in the list, and send the name to the button text
        self.theme_button.setText(apply_theme(self.app))

    def projects_tab(self):
        tab_widget = QtW.QWidget()

        dashboard = QtW.QVBoxLayout(tab_widget)
        header = QtW.QLabel("Project Dashboard")
        header.setFixedHeight(40)
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header.setObjectName("headerLabel")
        dashboard.addWidget(header)

        # Asset Tree
        content = QtW.QHBoxLayout()
        self.asset_tree = QtW.QTreeWidget()
        self.asset_tree.setHeaderLabel("Assets")
        self.asset_tree.setFixedWidth(240)
        self.asset_tree.setIndentation(20)
        self.asset_tree.setUniformRowHeights(True)
        self.asset_tree.setSortingEnabled(False)  # Preserve JSON order (for now)
        content.addWidget(self.asset_tree, stretch=1)

        self.dropzone = DropWidget(self, "Drop Project JSON file here")
        self.dropzone.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.dropzone.setObjectName("dropZone")
        content.addWidget(self.dropzone)

        dashboard.addLayout(content)

        self.tabs.addTab(tab_widget, "Projects")

    def init_tabs(self):
        """
        Initializes tabs
        """
        self.projects_tab()
        self.tabs.addTab(self.palette_editor, "Palettes")
        self.tabs.addTab(self.sprite_editor, "Sprites")
        self.tabs.addTab(self.animation_editor, "Animations")
        self.tabs.addTab(self.level_editor, "Levels")
        self.tabs.addTab(self.objdef_editor, "Objects")
        self.tabs.addTab(self.tilemap_editor, "Tilemaps")
        self.tabs.addTab(self.special_editor, "Special Stages")

    def project_load(self, project_path):
        """
        Loads a project from a specified JSON

        Returns:
            True if successful, otherwise False
        """
        ok = QtW.QMessageBox.question(self, "Load Prject",
                                      "Load this project and replace the data currently "
                                      "open in the editors?\n\n"
                                      "Unsaved editor changes will be discarded.",
                                      QtW.QMessageBox.StandardButton.Yes | QtW.QMessageBox.StandardButton.No,
                                      QtW.QMessageBox.StandardButton.No
                                      )

        if ok != QtW.QMessageBox.StandardButton.Yes:
            return False

        try:
            self.project.load(project_path)

        except Exception as e:
            QtW.QMessageBox.warning(self, "Project Load Error",
                                    f"Could not load project:\n{e}")
            return False

        self.project_refresh_asset_tree()
        return True

    def project_refresh_dashboard(self):
        """
        Refreshes project dashboard when a new project is loaded.
        """
        project = self.project
        data = project.data

        project_name = data.get("project_name", "Unnamed Project")

        self.dropzone.setText(
            f"<b>Project:</b> {project_name}<br>"
            f"{project.root_dir}<br><br>"
            "Drag & Drop another .json file to switch"
        )

    def project_refresh_asset_tree(self):
        """
        Refreshes project asset tree when a new project is loaded.
        """
        self.asset_tree.clear()
        project = self.project
        data = project.data
        asset_style = self.asset_tree.style()

        folder_icon = asset_style.standardIcon(QtW.QStyle.StandardPixmap.SP_DirIcon)
        file_icon = asset_style.standardIcon(QtW.QStyle.StandardPixmap.SP_FileIcon)

        def add_folder(parent, name):
            item = QtW.QTreeWidgetItem(parent, [name])
            item.setIcon(0, folder_icon)
            return item

        def add_file(parent, path):
            if not path:
                return

            path = str(path)
            item = QtW.QTreeWidgetItem(parent, [Path(path).name])
            item.setIcon(0, file_icon)
            item.setToolTip(0, path)

            # Keep JSON path available for future open/context menu actions
            item.setData(0, Qt.ItemDataRole.UserRole, path)
            return item

        # Standalone palette resources
        palettes_item = add_folder(self.asset_tree, "Palettes")

        for path in data.get("palettes", []):
            add_file(palettes_item, path)

        # Sprite builds and their associated resources
        # Sprite builds
        sprites_item = add_folder(self.asset_tree, "Sprites")

        for name in data.get("sprites", {}):
            build_item = QtW.QTreeWidgetItem(sprites_item, [name])
            build_item.setIcon(0, file_icon)
            build_item.setData(0, Qt.ItemDataRole.UserRole, name)

        # Show resource categories with folders collapsed
        self.asset_tree.expandToDepth(-1)


class DropWidget(QtW.QLabel):
    def __init__(self, app, text=""):
        super().__init__(text)
        self.app = app
        self.setAcceptDrops(True)

    def dragEnterEvent(self, a0: QtGui.QDragEnterEvent|None) -> None:
        if a0.mimeData().hasUrls:
            for url in a0.mimeData().urls():
                if url.toLocalFile().lower().endswith(".json"):
                    a0.acceptProposedAction()
                    return

        a0.ignore()

    def dropEvent(self, a0: QtGui.QDropEvent|None) -> None:
        for url in a0.mimeData().urls():
            file_path = url.toLocalFile()
            if file_path.lower().endswith(".json"):
                self.app.project_load(file_path)
                a0.acceptProposedAction()
                break
