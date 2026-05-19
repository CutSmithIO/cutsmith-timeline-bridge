"""ProjectDiscoveryPanel — left column: grouped project list."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from cutsmith.gui.models import ProjectEntry
from cutsmith.gui.style import ACCENT, GREEN, ORANGE, RED, TEXT_FAINT, TEXT_MUTED

_GROUP_ORDER = ["capcut", "jianying", "encrypted", "unknown"]
_GROUP_LABELS = {
    "capcut":    "CAPCUT PROJECTS",
    "jianying":  "JIANYING PROJECTS",
    "encrypted": "ENCRYPTED / UNSUPPORTED",
    "unknown":   "OTHER",
}


class _ProjectButton(QPushButton):
    def __init__(self, entry: ProjectEntry, parent=None):
        super().__init__(parent)
        self.entry = entry
        self.setObjectName("projItem")
        self.setCheckable(False)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._refresh()

    def _refresh(self):
        enc = (self.entry.detect.encryption or "").lower()
        is_enc = enc not in ("", "none", "plaintext")
        name = self.entry.display_name
        sub = f"{self.entry.app_label} · {self.entry.date_label}" if self.entry.date_label else self.entry.app_label
        self.setText(f"{name}\n{sub}")
        self.setEnabled(not is_enc)

    def set_selected(self, sel: bool):
        self.setProperty("selected", "true" if sel else "false")
        self.style().unpolish(self)
        self.style().polish(self)


class ProjectDiscoveryPanel(QWidget):
    project_selected = Signal(object)  # ProjectEntry
    rescan_requested = Signal()
    add_folder_requested = Signal(Path)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("leftPanel")
        self.setFixedWidth(220)

        self._entries: list[ProjectEntry] = []
        self._buttons: list[_ProjectButton] = []
        self._selected: ProjectEntry | None = None

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # Header
        header = QLabel("PROJECTS")
        header.setObjectName("groupLabel")
        header.setContentsMargins(12, 10, 12, 6)
        root_layout.addWidget(header)

        # Scroll area for project list
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._list_widget = QWidget()
        self._list_layout = QVBoxLayout(self._list_widget)
        self._list_layout.setContentsMargins(0, 0, 0, 0)
        self._list_layout.setSpacing(0)
        self._list_layout.addStretch()
        scroll.setWidget(self._list_widget)
        root_layout.addWidget(scroll, 1)

        # Footer buttons
        footer = QWidget()
        footer.setFixedHeight(44)
        fl = QHBoxLayout(footer)
        fl.setContentsMargins(8, 6, 8, 6)
        fl.setSpacing(6)
        btn_add = QPushButton("+ Add Folder…")
        btn_add.setObjectName("lfBtn")
        btn_rescan = QPushButton("↺  Rescan")
        btn_rescan.setObjectName("lfBtn")
        fl.addWidget(btn_add)
        fl.addWidget(btn_rescan)
        root_layout.addWidget(footer)

        btn_add.clicked.connect(self._on_add_folder)
        btn_rescan.clicked.connect(self.rescan_requested)

    # ── public API ─────────────────────────────────────────────────────────────

    def add_project(self, entry: ProjectEntry) -> None:
        self._entries.append(entry)
        self._rebuild_list()

    def clear(self) -> None:
        self._entries.clear()
        self._selected = None
        self._rebuild_list()

    def set_status(self, msg: str) -> None:
        pass  # status shown in main window status bar

    # ── private ────────────────────────────────────────────────────────────────

    def _rebuild_list(self):
        # Remove all widgets from list layout (except stretch)
        while self._list_layout.count() > 1:
            item = self._list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._buttons.clear()

        grouped: dict[str, list[ProjectEntry]] = {g: [] for g in _GROUP_ORDER}
        for e in self._entries:
            g = e.group if e.group in grouped else "unknown"
            grouped[g].append(e)

        insert_pos = 0
        for g in _GROUP_ORDER:
            entries = grouped[g]
            if not entries:
                continue
            lbl = QLabel(_GROUP_LABELS[g])
            lbl.setObjectName("groupLabel")
            self._list_layout.insertWidget(insert_pos, lbl)
            insert_pos += 1
            for e in entries:
                btn = _ProjectButton(e)
                btn.clicked.connect(lambda checked, entry=e: self._on_select(entry))
                self._list_layout.insertWidget(insert_pos, btn)
                self._buttons.append(btn)
                insert_pos += 1

    def _on_select(self, entry: ProjectEntry):
        self._selected = entry
        for btn in self._buttons:
            btn.set_selected(btn.entry is entry)
        self.project_selected.emit(entry)

    def _on_add_folder(self):
        folder = QFileDialog.getExistingDirectory(
            self, "Add Project Folder", str(Path.home() / "Movies")
        )
        if folder:
            self.add_folder_requested.emit(Path(folder))
