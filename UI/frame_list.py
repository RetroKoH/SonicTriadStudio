import PyQt6.QtWidgets as QtW
from PyQt6 import QtCore, QtGui
from PyQt6.QtCore import pyqtSignal, Qt, QSize
from PyQt6.QtGui import QDrag

# List Widget variant used for Sprite Frame List
# May also use this for other editors if applicable
class SpriteFrameList(QtW.QListWidget):
    frameMoveRequested = pyqtSignal(int, int)

    def __init__(self):
        super().__init__()
        self.drag_row = None

    def startDrag(self, supportedActions: QtCore.Qt.DropAction) -> None:
        self.drag_row = self.currentRow()

        if self.drag_row < 0:
            return

        drag = QDrag(self)
        index = self.model().index(self.drag_row, 0)

        drag.setMimeData(self.model().mimeData([index]))
        drag.setPixmap(self.currentItem().icon().pixmap(QSize(96, 96)))

        try:
            drag.exec(Qt.DropAction.MoveAction)

        finally:
            self.drag_row = None

    def dragEnterEvent(self, e: QtGui.QDragEnterEvent|None) -> None:
        if e.source() is not self:
            e.ignore()
            return

        super().dragEnterEvent(e)
        e.setDropAction(Qt.DropAction.MoveAction)
        e.accept()

    def dragMoveEvent(self, e: QtGui.QDragMoveEvent|None) -> None:
        if e.source() is not self:
            e.ignore()
            return

        super().dragMoveEvent(e)
        e.setDropAction(Qt.DropAction.MoveAction)
        e.accept()

    def dropEvent(self, event: QtGui.QDropEvent|None) -> None:
        old_row = self.drag_row

        if event.source() is not self or old_row is None:
            event.ignore()
            return

        # Find the insertion point in the current list
        insertion_row = self.count()

        for row in range(self.count()):
            rect = self.visualItemRect(self.item(row))

            if event.position().y() < rect.center().y():
                insertion_row = row
                break

        # Removing the original row shifts later positions up
        new_row = insertion_row

        if insertion_row > old_row:
            new_row -= 1

        if new_row != old_row:
            self.frameMoveRequested.emit(old_row, new_row)

        event.setDropAction(Qt.DropAction.MoveAction)
        event.accept()
