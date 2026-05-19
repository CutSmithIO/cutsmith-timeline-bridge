"""QApplication setup."""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from cutsmith.gui.main_window import MainWindow


def run() -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("CutSmith")
    app.setOrganizationName("Anthropic")
    window = MainWindow()
    window.show()
    window.start_auto_scan()
    return app.exec()
