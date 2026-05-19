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
from cutsmith.gui.style import (
    ACCENT, ACCENT_DIM, ACCENT_SEL, BG_HOVER, BG_RAISED,
    TEXT_FAINT, TEXT_MUTED, TEXT_PRIMARY, TEXT_SECONDARY,
)

_GROUP_ORDER  = ["capcut", "jianying", "encrypted", "unknown"]
_GROUP_LABELS = {
    "capcut":    "CAPCUT PROJECTS",
    "jianying":  "JIANYING PROJECTS",
    "encrypted": "ENCRYPTED / UNSUPPORTED",
    "unknown":   "OTHER",
}


class _ProjectItem(QWidget):
    """Single project row — QWidget with two QLabels for full color control."""

    clicked = Signal()

    def __init__(self, entry: ProjectEntry, parent=None):
        super().__init__(parent)
        self.entry = entry
        self._selected = False

        self.setObjectName("projItem")
        self.setCursor(Qt.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 6, 12, 6)
        lay.setSpacing(1)

        self._name_lbl = QLabel(entry.display_name)
        self._name_lbl.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        sub = (
            f"{entry.app_label} · {entry.date_label}"
            if entry.date_label
            else entry.app_label
        )
        self._meta_lbl = QLabel(sub)
        self._meta_lbl.setAttribute(Qt.WA_TransparentForMouseEvents, True)

        enc = (entry.detect.encryption or "").lower()
        self._is_enc = enc not in ("", "none", "plaintext")

        if self._is_enc:
            self._name_lbl.setObjectName("projNameDim")
            self._meta_lbl.setObjectName("projMetaDim")
            self.setCursor(Qt.ForbiddenCursor)
        else:
            self._name_lbl.setObjectName("projName")
            self._meta_lbl.setObjectName("projMeta")

        lay.addWidget(self._name_lbl)
        lay.addWidget(self._meta_lbl)

        self._apply_state()

    # ── interaction ────────────────────────────────────────────────────────────

    def mousePressEvent(self, event):
        if not self._is_enc:
            self.clicked.emit()
        super().mousePressEvent(event)

    def enterEvent(self, event):
        if not self._selected and not self._is_enc:
            self.setStyleSheet(f"background: {BG_HOVER}; border-left: 2px solid transparent;")
        super().enterEvent(event)

    def leaveEvent(self, event):
        if not self._selected:
            self._apply_state()
        super().leaveEvent(event)

    # ── public ─────────────────────────────────────────────────────────────────

    def set_selected(self, sel: bool):
        self._selected = sel
        self._apply_state()

    # ── private ────────────────────────────────────────────────────────────────

    def _apply_state(self):
        if self._is_enc:
            self.setStyleSheet(
                f"background: transparent; border-left: 2px solid transparent;"
                f" opacity: 0.45;"
            )
        elif self._selected:
            self.setStyleSheet(
                f"background: {ACCENT_SEL}; border-left: 2px solid {ACCENT};"
            )
            self._name_lbl.setStyleSheet(f"color: #ffffff; font-weight: 600; background: transparent;")
            self._meta_lbl.setStyleSheet(f"color: {TEXT_SECONDARY}; background: transparent;")
        else:
            self.setStyleSheet(
                f"background: transparent; border-left: 2px solid transparent;"
            )
            self._name_lbl.setStyleSheet(f"color: {TEXT_PRIMARY}; font-weight: normal; background: transparent;")
            self._meta_lbl.setStyleSheet(f"color: {TEXT_MUTED}; background: transparent;")


class ProjectDiscoveryPanel(QWidget):
    project_selected = Signal(object)   # ProjectEntry
    rescan_requested = Signal()
    add_folder_requested = Signal(Path)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("leftPanel")
        self.setFixedWidth(220)

        self._entries: list[ProjectEntry] = []
        self._items: list[_ProjectItem] = []
        self._selected: ProjectEntry | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Header
        header = QLabel("PROJECTS")
        header.setObjectName("groupLabel")
        header.setContentsMargins(14, 10, 12, 6)
        root.addWidget(header)

        # Scrollable list
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet(f"background: {BG_RAISED}; border: none;")
        scroll.viewport().setStyleSheet(f"background: {BG_RAISED};")

        self._list_widget = QWidget()
        self._list_widget.setStyleSheet(f"background: {BG_RAISED};")
        self._list_layout = QVBoxLayout(self._list_widget)
        self._list_layout.setContentsMargins(0, 4, 0, 4)
        self._list_layout.setSpacing(0)
        self._list_layout.addStretch()
        scroll.setWidget(self._list_widget)
        root.addWidget(scroll, 1)

        # Footer
        footer = QWidget()
        footer.setFixedHeight(44)
        footer.setStyleSheet(f"background: {BG_RAISED}; border-top: 1px solid #3a3a3c;")
        fl = QHBoxLayout(footer)
        fl.setContentsMargins(8, 6, 8, 6)
        fl.setSpacing(6)
        btn_add = QPushButton("+ Add Folder…")
        btn_add.setObjectName("lfBtn")
        btn_rescan = QPushButton("↺  Rescan")
        btn_rescan.setObjectName("lfBtn")
        fl.addWidget(btn_add)
        fl.addWidget(btn_rescan)
        root.addWidget(footer)

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

    # ── private ────────────────────────────────────────────────────────────────

    def _rebuild_list(self):
        while self._list_layout.count() > 1:
            item = self._list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._items.clear()

        grouped: dict[str, list[ProjectEntry]] = {g: [] for g in _GROUP_ORDER}
        for e in self._entries:
            g = e.group if e.group in grouped else "unknown"
            grouped[g].append(e)

        pos = 0
        for g in _GROUP_ORDER:
            entries = grouped[g]
            if not entries:
                continue
            lbl = QLabel(_GROUP_LABELS[g])
            lbl.setObjectName("groupLabel")
            lbl.setContentsMargins(14, 8, 12, 3)
            self._list_layout.insertWidget(pos, lbl)
            pos += 1
            for e in entries:
                item = _ProjectItem(e)
                item.clicked.connect(lambda entry=e: self._on_select(entry))
                self._list_layout.insertWidget(pos, item)
                self._items.append(item)
                pos += 1

    def _on_select(self, entry: ProjectEntry):
        self._selected = entry
        for item in self._items:
            item.set_selected(item.entry is entry)
        self.project_selected.emit(entry)

    def _on_add_folder(self):
        folder = QFileDialog.getExistingDirectory(
            self, "Add Project Folder", str(Path.home() / "Movies")
        )
        if folder:
            self.add_folder_requested.emit(Path(folder))
