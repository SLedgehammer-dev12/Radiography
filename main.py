# -*- coding: utf-8 -*-

import os
import sys


def main():
    is_android = "ANDROID_ARGUMENT" in os.environ or "ANDROID_PRIVATE" in os.environ

    if is_android:
        from src.mobile.main import RadiographyApp

        RadiographyApp().run()
    else:
        from PyQt6.QtCore import Qt
        from PyQt6.QtWidgets import QApplication
        from src.ui.main_window import MainWindow

        app = QApplication(sys.argv)

        app.setAttribute(Qt.ApplicationAttribute.AA_DontShowIconsInMenus, False)

        window = MainWindow()
        window.show()
        sys.exit(app.exec())


if __name__ == "__main__":
    main()
