import sys
import PyQt6.QtWidgets as QtW


def main():
    app = QtW.QApplication(sys.argv)

    window = QtW.QMainWindow()
    window.setWindowTitle("Sonic Triad Studio - RetroKoH 2027")
    window.resize(800, 600)
    window.show()

    # Without this, the window immediately closes
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
