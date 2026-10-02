from pathlib import Path

import PyQt6.QtWidgets as QtW
from PyQt6.QtCore import Qt

from Core.project import Project

class TriadApp(QtW.QMainWindow):
    def __init__(self, app):
        super().__init__()
        self.app = app

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

        # Preferences button
        self.prefButton = QtW.QPushButton("Preferences")
        self.tabs.setCornerWidget(self.prefButton, Qt.Corner.TopRightCorner)

        # Init tabs
        self.projects_tab()
        self.init_tab("Palettes")
        self.init_tab("Sprites")
        self.init_tab("Animations")
        self.init_tab("Levels")
        self.init_tab("Objects")
        self.init_tab("Tilemaps")
        self.init_tab("Special Stages")

        # Connecting function for when project is loaded
        self.project.project_loaded.connect(self.project_refresh_dashboard)

        # Status label
        self.statusLabel = QtW.QLabel("Status: Idle")
        self.statusLabel.setFixedHeight(20)
        main_layout.addWidget(self.statusLabel)

    def projects_tab(self):
        tab_widget = QtW.QWidget()

        dashboard = QtW.QVBoxLayout(tab_widget)
        header = QtW.QLabel("Project Dashboard")
        header.setFixedHeight(40)
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
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
        content.addWidget(self.dropzone)

        dashboard.addLayout(content)

        self.tabs.addTab(tab_widget, "Projects")

    def init_tab(self, name):
        """
        Initializes a placeholder tab
        """
        tab = QtW.QTabWidget()
        layout = QtW.QVBoxLayout(tab)

        header = QtW.QLabel(f"{name} Editor")
        header.setFixedHeight(40)
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(header)
        self.tabs.addTab(tab, name)

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

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls:
            for url in event.mimeData().urls():
                if url.toLocalFile().lower().endswith(".json"):
                    event.acceptProposedAction()
                    return

        event.ignore()

    def dropEvent(self, event):
        for url in event.mimeData().urls():
            file_path = url.toLocalFile()
            if file_path.lower().endswith(".json"):
                self.app.project_load(file_path)
                event.acceptProposedAction()
                break
