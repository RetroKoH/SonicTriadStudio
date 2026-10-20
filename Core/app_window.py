from pathlib import Path

import PyQt6.QtWidgets as QtW
from PyQt6 import QtGui
from PyQt6.QtCore import Qt

from Core.project import Project
from Core.asset_info import AssetInfo
from UI.asset_tree import AssetTree
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
        self.setMinimumSize(1024, 768)

        main_widget = QtW.QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QtW.QVBoxLayout(main_widget)

        # Mode Tabs
        self.tabs = QtW.QTabWidget()
        main_layout.addWidget(self.tabs)
        self.tabs.tabBar().setObjectName("mainTabBar")

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

        # Connecting function for when project is saved
        self.project.project_saved.connect(self.project_refresh_asset_tree)

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

        # LEFT PANEL: Asset Manager
        content = QtW.QHBoxLayout()
        asset_panel = QtW.QWidget()
        asset_panel.setFixedWidth(260)

        asset_layout = QtW.QVBoxLayout(asset_panel)
        asset_layout.setContentsMargins(0, 0, 0, 0)

        # Asset Creation and Filtering
        asset_controls = QtW.QHBoxLayout()
        asset_controls.setContentsMargins(0, 0, 0, 0)

        # Asset Filter Search
        self.asset_search = QtW.QLineEdit()
        self.asset_search.setPlaceholderText("Search Assets")
        self.asset_search.setClearButtonEnabled(True)
        self.asset_search.textChanged.connect(self.project_asset_filter)
        asset_controls.addWidget(self.asset_search, stretch=1)

        # Add Asset button
        self.asset_add_btn = QtW.QToolButton()
        self.asset_add_btn.setText("+")
        self.asset_add_btn.setToolTip("Create a project asset")
        self.asset_add_btn.setPopupMode(QtW.QToolButton.ToolButtonPopupMode.InstantPopup)

        self.asset_add_menu = QtW.QMenu(self.asset_add_btn)

        add_palette = self.asset_add_menu.addAction("Add Palette")
        add_palette.triggered.connect(lambda checked=False: self.project_asset_add("palette"))

        add_sprite = self.asset_add_menu.addAction("Add Sprite")
        add_sprite.triggered.connect(lambda checked=False: self.project_asset_add("sprite"))

        self.asset_add_btn.setMenu(self.asset_add_menu)
        asset_controls.addWidget(self.asset_add_btn)

        # Add Folder button
        self.folder_add_btn = QtW.QToolButton()
        self.folder_add_btn.setText(">")
        self.folder_add_btn.setToolTip("Create a project folder")
        self.folder_add_btn.clicked.connect(self.project_folder_add)

        asset_controls.addWidget(self.folder_add_btn)

        asset_layout.addLayout(asset_controls)

        # Asset/Folder creation requires a loaded project
        self.asset_add_btn.setEnabled(self.project.is_loaded)
        self.folder_add_btn.setEnabled(self.project.is_loaded)
        self.project.project_loaded.connect(lambda: self.asset_add_btn.setEnabled(True))
        self.project.project_loaded.connect(lambda: self.folder_add_btn.setEnabled(True))

        # Asset Tree
        self.asset_tree = AssetTree()
        self.asset_tree.assetMoveRequested.connect(self.project_asset_move)
        self.asset_tree.setHeaderLabel("Assets")
        self.asset_tree.setIndentation(20)
        self.asset_tree.setUniformRowHeights(True)
        self.asset_tree.setSortingEnabled(False)  # Preserve JSON order
        self.asset_tree.itemDoubleClicked.connect(self.project_asset_show_info)
        asset_layout.addWidget(self.asset_tree, stretch=1)
        content.addWidget(asset_panel)

        # Project JSON Dropbox
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
        ok = QtW.QMessageBox.question(self, "Load Project",
            "Load this project and replace the data currently "
            "open in the editors?\n\n"
            "Unsaved editor changes will be discarded.",
            QtW.QMessageBox.StandardButton.Yes | QtW.QMessageBox.StandardButton.No,
            QtW.QMessageBox.StandardButton.No)

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
            "Drag & Drop another .json file to switch")

    def project_refresh_asset_tree(self):
        """
        Refreshes project asset tree when a new project is loaded.
        """
        self.asset_tree.clear()
        asset_style = self.asset_tree.style()

        # To-Do: Have different file icons for different asset types
        folder_icon = asset_style.standardIcon(QtW.QStyle.StandardPixmap.SP_DirIcon)
        file_icon = asset_style.standardIcon(QtW.QStyle.StandardPixmap.SP_FileIcon)

        # Recursive function
        def add_entries(parent, entries):
            for entry in entries:
                asset_type = entry["type"]

                item = QtW.QTreeWidgetItem(parent, [entry["name"]])

                item.setData(0,
                    Qt.ItemDataRole.UserRole,
                    {"type": asset_type, "id": entry["id"]})

                # Folders
                if asset_type == "folder":
                    item.setIcon(0, folder_icon)
                    add_entries(item, entry["children"])

                # Assets
                else:
                    item.setIcon(0, file_icon)

                    # Set hover tooltip for palettes (Will do for others later)
                    if asset_type == "palette":
                        item.setToolTip(0, entry["path"])

                # All entry items can be dragged
                flags = item.flags() | Qt.ItemFlag.ItemIsDragEnabled

                # Only folders can have items dropped into them
                if asset_type == "folder":
                    flags |= Qt.ItemFlag.ItemIsDropEnabled
                # Asset items will still allow insertion above/below them
                else:
                    flags &= ~Qt.ItemFlag.ItemIsDropEnabled

                item.setFlags(flags)

        add_entries(self.asset_tree, self.project.data.get("assets", []))

        # Show resource categories with all folders collapsed
        self.asset_tree.collapseAll()

        # Refresh search (even if field is empty)
        self.project_asset_filter(self.asset_search.text())

    def project_folder_add(self):
        """
        Create a folder using the current tree selection.
        """
        project = self.project

        if not project.is_loaded:
            return

        # Capture the selected entry before opening the name dialog
        selected = self.asset_tree.selectedItems()
        target_id = None

        if selected:
            metadata = selected[0].data(0, Qt.ItemDataRole.UserRole)

            if isinstance(metadata, dict):
                target_id = metadata.get("id")

        name, ok = QtW.QInputDialog.getText(self, "New Folder", "Folder name:", text="New Folder")

        if not ok or not name.strip():
            return

        folder = {
            "id": project.new_asset_id(),
            "type": "folder",
            "name": name.strip(),
            "children": []
        }

        try:
            proposed = project.snapshot()

            if target_id is None:
                project.set_asset(proposed, folder)

            else:
                location = project.find_asset_location(proposed.get("assets", []), target_id)

                if location is None:
                    raise ValueError("The selected item no longer exists.")

                siblings, index = location
                target = siblings[index]

                if target["type"] == "folder":
                    target["children"].append(folder)

                else:
                    project.set_asset(proposed, folder, beside_id=target_id)

            project.save(proposed)

        except (OSError, TypeError, ValueError) as e:
            QtW.QMessageBox.warning(self, "Add Folder Error",
                f"Could not add folder:\n{e}")
            return

        self.asset_search.clear()

        iterator = QtW.QTreeWidgetItemIterator(self.asset_tree)

        while iterator.value():
            item = iterator.value()
            metadata = item.data(0, Qt.ItemDataRole.UserRole)

            if isinstance(metadata, dict) and metadata.get("id") == folder["id"]:
                parent = item.parent()

                while parent is not None:
                    parent.setExpanded(True)
                    parent = parent.parent()

                self.asset_tree.setCurrentItem(item)
                self.asset_tree.scrollToItem(item)
                break

            iterator += 1

    def project_asset_add(self, asset_type):
        """
        Create an asset using the relevant editor's existing New operation
        """
        if not self.project.is_loaded:
            return

        if asset_type == "palette":
            editor = self.palette_editor

            def create_palette():
                if editor.file_palette_new():
                    self.tabs.setCurrentWidget(editor)

            editor.check_unsaved_changes(create_palette)

        elif asset_type == "sprite":
            editor = self.sprite_editor

            if editor.file_sprite_new():
                self.tabs.setCurrentWidget(editor)

            # Sprite editor doesn't have "dirty flag" yet

    def project_asset_move(self, asset_id, parent_id, index):
        """
        Save a requested move, then reveal the moved entry.
        """
        project = self.project

        if not project.is_loaded:
            return

        try:
            proposed = project.snapshot()

            changed = project.move_asset(proposed, asset_id, parent_id, index)

            if not changed:
                return

            project.save(proposed)

        except (OSError, TypeError, ValueError) as e:
            QtW.QMessageBox.warning(self, "Move Asset Error", f"Could not move asset:\n{e}")
            return

        # project_saved has rebuild the tree
        iterator = QtW.QTreeWidgetItemIterator(self.asset_tree)

        while iterator.value():
            item = iterator.value()
            metadata = item.data(0, Qt.ItemDataRole.UserRole)

            if isinstance(metadata, dict) and metadata.get("id") == asset_id:
                parent = item.parent()

                while parent is not None:
                    parent.setExpanded(True)
                    parent = parent.parent()

                self.asset_tree.setCurrentItem(item)
                self.asset_tree.scrollToItem(item)
                break

            iterator += 1

    def project_asset_show_info(self, item):
        """
        Show basic information for the double-clicked project asset.

        The dialog is in its own file because I plan to expand on its functionality.
        """
        if item is None or not self.project.is_loaded:
            return

        asset = item.data(0, Qt.ItemDataRole.UserRole)

        # Ignore items without asset metadata (i.e. Folders)
        if not isinstance(asset, dict):
            return

        asset_type = asset.get("type")
        asset_id = asset.get("id")

        # Palettes (Palette Editor)
        if asset_type == "palette":
            palette = self.project.get_asset(asset_id)

            if not isinstance(palette, dict):
                return

            path = self.project.resolve_asset_path(palette["path"])

            name = palette["name"]
            type_label = "Palette"
            details = [
                ("Project path", palette["path"]),
                ("Full path", str(path)),
                ("File exists", "Yes" if path.is_file() else "No"),
            ]

        # Sprite Builds (Sprites)
        elif asset_type == "sprite":
            build = self.project.get_asset(asset_id)

            if not isinstance(build, dict):
                return

            mappings = build.get("mappings") or {}
            dplcs = build.get("dplcs") or {}

            name = build["name"]
            type_label = "Sprite Build"
            details = [
                ("Art files", len(build.get("art") or [])),
                ("Palette files", len(build.get("palettes") or [])),
                ("Mappings", mappings.get("path") or "Not configured"),
                ("DPLCs", dplcs.get("path") or "Not configured"),
            ]

        else:
            return

        # Open Asset Info window
        self.asset_info_dialog = AssetInfo(name, type_label, details, self)

        self.asset_info_dialog.finished.connect(self.asset_info_dialog.deleteLater)
        self.asset_info_dialog.open()

    def project_asset_filter(self, text):
        """
        Filter asset names and paths.
        """
        # Get text query, removing all case distinctions
        query = text.strip().casefold()
        # Disable drag-and-drop while searching
        self.asset_tree.setDragEnabled(self.project.is_loaded and not query)

        def filter_item(item):
            asset = item.data(0, Qt.ItemDataRole.UserRole)

            # Empty search shows every item (Type to narrow down)
            matches = not query

            if query and isinstance(asset, dict):
                name = item.text(0).casefold()
                path = item.toolTip(0).casefold()
                matches = query in name or query in path

            # Check every child
            child_matches = False

            for _idx in range(item.childCount()):
                if filter_item(item.child(_idx)):
                    child_matches = True

            # Hide item if it's filtered out
            visible = matches or child_matches
            item.setHidden(not visible)

            # Expand folders with matching assets
            if query and child_matches:
                item.setExpanded(True)

            return visible

        for _idx in range(self.asset_tree.topLevelItemCount()):
            filter_item(self.asset_tree.topLevelItem(_idx))

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
