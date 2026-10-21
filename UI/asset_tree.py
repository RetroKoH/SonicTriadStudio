import PyQt6.QtWidgets as QtW
from PyQt6 import QtCore, QtGui
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QDrag


class AssetTree(QtW.QTreeWidget):
    """
    This subclass was created to divide some of the responsibilities
    of the Project tab's asset tree.

    This class: Handles mouse gestures and drag-and-drop; Makes requests
    TriadApp: Connects these requests to project operations and shows errors
        - project_asset_move()
    Project: Changes, validates, and saves the JSON
    """

    # Request signals
    assetMoveRequested = pyqtSignal(str, object, int)
    assetOpenRequested = pyqtSignal(object)
    assetRenameRequested = pyqtSignal(str)
    assetDuplicateRequested = pyqtSignal(str)
    assetRemoveRequested = pyqtSignal(str)

    assetAddRequested = pyqtSignal(str)
    folderAddRequested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)

        self.drag_id = None

        self.setSelectionMode(QtW.QAbstractItemView.SelectionMode.SingleSelection)
        self.setDragDropMode(QtW.QAbstractItemView.DragDropMode.InternalMove)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.setDragDropOverwriteMode(False)
        self.setDropIndicatorShown(True)
        self.setAutoExpandDelay(600)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)

    def show_context_menu(self, position):
        """
        Show actions for a right-clicked entry item.
        """
        item = self.itemAt(position)
        metadata = None

        if item is not None:
            metadata = item.data(0, Qt.ItemDataRole.UserRole)

            if not isinstance(metadata, dict):
                return

            # Select the item that was right-clicked
            self.setCurrentItem(item)

        else:
            # Empty space targets the project root
            self.clearSelection()
            self.setCurrentItem(None)

        menu = QtW.QMenu(self)
        open_action = None
        rename_action = None
        duplicate_action = None
        remove_action = None

        # Add actions
        palette_action = None
        sprite_action = None
        folder_action = None

        if item is None:
            # Enable asset creation here once it uses the tree destination
            asset_menu = menu.addMenu("Add Asset")
            palette_action = asset_menu.addAction("Palette")
            sprite_action = asset_menu.addAction("Sprite Build")
            # Add more asset types later

            folder_action = menu.addAction("Add Folder")

        else:
            if metadata["type"] == "folder":
                folder_action = menu.addAction("Add Folder")
            else:
                open_action = menu.addAction("Open")

                # Make Open BOLD
                font = open_action.font()
                font.setBold(True)
                open_action.setFont(font)

            rename_action = menu.addAction("Rename")

            if metadata["type"] != "folder":
                duplicate_action = menu.addAction("Duplicate")

            menu.addSeparator()
            remove_action = menu.addAction("Remove")

        # Dispatch signal to trigger menu action
        try:
            chosen = menu.exec(self.viewport().mapToGlobal(position))

            # Stop if the menu was dismissed
            if chosen is None:
                return

            if chosen == palette_action:
                self.assetAddRequested.emit("palette")

            elif chosen == sprite_action:
                self.assetAddRequested.emit("sprite")

            elif chosen == open_action:
                self.assetOpenRequested.emit(item)

            elif chosen == rename_action:
                self.assetRenameRequested.emit(metadata["id"])

            elif chosen == duplicate_action:
                self.assetDuplicateRequested.emit(metadata["id"])

            elif chosen == remove_action:
                self.assetRemoveRequested.emit(metadata["id"])

            elif chosen == folder_action:
                self.folderAddRequested.emit()

        finally:
            # Remove the temporary menu after use
            menu.deleteLater()

    def reveal_asset(self, asset_id):
        """
        Find an entry by UUID, expand its ancestors, and select it.
        """
        # Iterate through all tree items
        iterator = QtW.QTreeWidgetItemIterator(self)

        while iterator.value():
            item = iterator.value()
            metadata = item.data(0, Qt.ItemDataRole.UserRole)

            # Match entries by UUID, since they can have identical names
            if isinstance(metadata, dict) and metadata.get("id") == asset_id:
                parent = item.parent()

                # Expand every parent folder so the entry can be seen
                while parent is not None:
                    parent.setExpanded(True)
                    parent = parent.parent()

                # Select the entry and scroll it into view
                self.setCurrentItem(item)
                self.scrollToItem(item)
                return

            # Move to the next item
            iterator += 1

    def startDrag(self, supportedActions: QtCore.Qt.DropAction) -> None:
        selected = self.selectedItems()

        if len(selected) != 1:
            return

        item = selected[0]
        metadata = item.data(0, Qt.ItemDataRole.UserRole)

        if not isinstance(metadata, dict):
            return

        self.drag_id = metadata["id"]

        drag = QDrag(self)
        drag.setMimeData(self.model().mimeData([self.indexFromItem(item)]))

        try:
            drag.exec(Qt.DropAction.MoveAction)

        finally:
            self.drag_id = None

    def dropEvent(self, event: QtGui.QDropEvent|None) -> None:
        if event.source() is not self or self.drag_id is None:
            event.ignore()
            return

        target = self.itemAt(event.position().toPoint())
        position = self.dropIndicatorPosition()
        positions = QtW.QAbstractItemView.DropIndicatorPosition

        if target is None or position == positions.OnViewport:
            # Empty space: append at the root.
            parent = None
            index = self.topLevelItemCount()

        elif position == positions.OnItem:
            # Directly on a folder: append inside it.
            metadata = target.data(0, Qt.ItemDataRole.UserRole)

            if not isinstance(metadata, dict) or metadata["type"] != "folder":
                event.ignore()
                return

            parent = target
            index = target.childCount()

        else:
            # Above or below an item: insert among its siblings
            parent = target.parent()

            index = (
                parent.indexOfChild(target) if parent is not None
                else self.indexOfTopLevelItem(target)
            )

            if position == positions.BelowItem:
                index += 1

        # Reject moving a folder into itself or its descendants
        ancestor = parent

        while ancestor is not None:
            metadata = ancestor.data(0, Qt.ItemDataRole.UserRole)

            if metadata["id"] == self.drag_id:
                event.ignore()
                return

            ancestor = ancestor.parent()

        parent_id = (
            parent.data(0, Qt.ItemDataRole.UserRole)["id"]
            if parent is not None else None
        )

        self.assetMoveRequested.emit(self.drag_id, parent_id, index)

        event.setDropAction(Qt.DropAction.MoveAction)
        event.accept()
