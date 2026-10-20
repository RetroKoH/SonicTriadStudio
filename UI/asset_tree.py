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

    assetMoveRequested = pyqtSignal(str, object, int)

    def __init__(self, parent=None):
        super().__init__(parent)

        self.drag_id = None

        self.setSelectionMode(QtW.QAbstractItemView.SelectionMode.SingleSelection)
        self.setDragDropMode(QtW.QAbstractItemView.DragDropMode.InternalMove)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.setDragDropOverwriteMode(False)
        self.setDropIndicatorShown(True)
        self.setAutoExpandDelay(600)

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
