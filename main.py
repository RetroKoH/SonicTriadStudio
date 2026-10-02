import sys
import PyQt6.QtWidgets as QtW

from Core.app_window import TriadApp

def main():
    app = QtW.QApplication(sys.argv)

    window = TriadApp(app)
    window.show()

    # Without this, the window immediately closes
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
