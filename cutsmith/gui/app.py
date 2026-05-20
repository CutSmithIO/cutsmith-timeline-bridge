"""QApplication setup."""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import QApplication

from cutsmith.gui.main_window import MainWindow
from cutsmith.gui.style import APP_QSS

_FONTS_DIR = Path(__file__).parent.parent.parent / "assets" / "fonts"


def _load_fonts() -> None:
    if not _FONTS_DIR.is_dir():
        return
    for font_file in sorted(_FONTS_DIR.glob("*.ttf")) + sorted(_FONTS_DIR.glob("*.otf")):
        QFontDatabase.addApplicationFont(str(font_file))


def run() -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("CutSmith")
    app.setOrganizationName("Anthropic")
    _load_fonts()
    app.setStyleSheet(APP_QSS)
    window = MainWindow()
    window.show()
    window.start_auto_scan()
    return app.exec()
