# -*- coding: utf-8 -*-

import sys
from PyQt6.QtWidgets import QApplication
from src.ui.main_window import MainWindow

def main():
    app = QApplication(sys.argv)
    
    # Enable High DPI scaling
    app.setAttribute(Qt.ApplicationAttribute.AA_DontShowIconsInMenus, False) # just generic setting if needed
    
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    from PyQt6.QtCore import Qt
    main()
