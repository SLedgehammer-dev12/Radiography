# -*- coding: utf-8 -*-

import logging
import os
import sys
import tempfile
import traceback
from datetime import datetime


# ---------------------------------------------------------------------------
# Global exception handling
# ---------------------------------------------------------------------------
# PyQt6's default behaviour for an unhandled exception raised inside a slot
# (e.g. a button.clicked handler) is to call qFatal() -> abort(), which kills
# the application with no traceback (the macOS crash in 1.6.2). Installing a
# custom sys.excepthook AND overriding QApplication.notify() keeps the app
# alive and records the real traceback to a log file.
# ---------------------------------------------------------------------------


def _log_dir():
    """Writable directory for error logs (macOS: ~/Library/Logs/Radiography)."""
    candidates = [
        os.path.join(os.path.expanduser("~"), "Library", "Logs", "Radiography"),
        os.path.join(tempfile.gettempdir(), "Radiography"),
    ]
    for d in candidates:
        try:
            os.makedirs(d, exist_ok=True)
            return d
        except OSError:
            continue
    return tempfile.gettempdir()


_CRASH_LOGGER = None


def _get_crash_logger():
    global _CRASH_LOGGER
    if _CRASH_LOGGER is not None:
        return _CRASH_LOGGER
    log_path = os.path.join(_log_dir(), f"radiography_error_{datetime.now():%Y%m%d}.log")
    logger = logging.getLogger("radiography.crash")
    if not logger.handlers:
        handler = logging.FileHandler(log_path, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        logger.addHandler(handler)
        logger.setLevel(logging.ERROR)
    _CRASH_LOGGER = logger
    return logger


def _record_exception(exc_type=None, exc_value=None, exc_tb=None):
    """Formats and persists an exception traceback, returns the formatted text."""
    tb_text = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
    try:
        sys.stderr.write(tb_text + "\n")
        sys.stderr.flush()
    except Exception:
        pass
    try:
        _get_crash_logger().error("Unhandled exception:\n%s", tb_text)
    except Exception:
        pass
    return tb_text


def _install_excepthook():
    def _excepthook(exc_type, exc_value, exc_tb):
        # Do NOT re-raise: returning normally prevents PyQt6's qFatal -> abort.
        _record_exception(exc_type, exc_value, exc_tb)

    sys.excepthook = _excepthook


def _install_qapp_hook(app):
    """Monkey-patches app.notify to swallow and log slot exceptions so the
    process does not abort on a bad slot (PyQt6 qFatal behaviour)."""
    original_notify = app.notify

    def _safe_notify(receiver, event):
        try:
            return original_notify(receiver, event)
        except Exception:
            _record_exception(*sys.exc_info())
            return False

    app.notify = _safe_notify


def main():
    _install_excepthook()

    is_android = "ANDROID_ARGUMENT" in os.environ or "ANDROID_PRIVATE" in os.environ

    if is_android:
        from src.mobile.main import RadiographyApp

        RadiographyApp().run()
    else:
        from PyQt6.QtCore import Qt
        from PyQt6.QtWidgets import QApplication, QMessageBox
        from src.ui.main_window import MainWindow

        self_test = "--self-test" in sys.argv
        argv = [arg for arg in sys.argv if arg != "--self-test"]

        app = QApplication(argv)
        if not self_test:
            _install_qapp_hook(app)

        app.setAttribute(Qt.ApplicationAttribute.AA_DontShowIconsInMenus, False)

        try:
            window = MainWindow()
        except Exception:
            tb_text = _record_exception(*sys.exc_info())
            if self_test:
                sys.exit(1)
            try:
                QMessageBox.critical(
                    None,
                    "Radiography — Başlatma Hatası / Startup Error",
                    f"Uygulama başlatılırken bir hata oluştu:\n\n{tb_text[-1200:]}",
                )
            except Exception:
                pass
            sys.exit(1)

        if self_test:
            window.update_calculations()
            sys.exit(0)

        window.show()
        sys.exit(app.exec())


if __name__ == "__main__":
    main()