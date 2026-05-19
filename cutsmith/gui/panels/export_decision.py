"""ExportDecisionPanel — right column: output config, collect button, tree."""

from __future__ import annotations

import os
import subprocess
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

from cutsmith.gui.models import AnalysisResult
from cutsmith.gui.style import ACCENT, GREEN, ORANGE, RED, TEXT_FAINT, TEXT_MUTED, TEXT_PRIMARY


def _make_tree(out_dir: Path, stem: str) -> str:
    lines = [f"out_collect/{out_dir.name}/"]
    files = [
        f"{stem}.xml",
        f"{stem}.package_summary.txt",
        f"{stem}.report.md",
        f"{stem}.relink_guide.md",
        f"{stem}.manifest.json",
        "media/",
    ]
    for i, f in enumerate(files):
        prefix = "└── " if i == len(files) - 1 else "├── "
        lines.append(f"  {prefix}{f}")
    # media subdirs
    subdirs = ["video/", "audio/", "images/", "music/", "sfx/"]
    for i, d in enumerate(subdirs):
        prefix = "    └── " if i == len(subdirs) - 1 else "    ├── "
        lines.append(f"  {prefix}{d}")
    return "\n".join(lines)


class ExportDecisionPanel(QWidget):
    collect_requested = Signal(Path)    # out_dir
    srt_requested = Signal(Path)        # out_dir
    open_folder_requested = Signal(Path)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("rightPanel")
        self.setFixedWidth(280)

        self._result: AnalysisResult | None = None
        self._out_dir: Path | None = None
        self._collecting = False

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        # Output path row
        path_row_label = QLabel("OUTPUT FOLDER")
        path_row_label.setObjectName("rpLabel")
        root.addWidget(path_row_label)

        path_row = QHBoxLayout()
        path_row.setSpacing(6)
        self._path_label = QLabel("—")
        self._path_label.setObjectName("pathLabel")
        self._path_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._path_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self._path_label.setToolTip("")
        btn_browse = QPushButton("…")
        btn_browse.setObjectName("lfBtn")
        btn_browse.setFixedWidth(28)
        btn_browse.clicked.connect(self._on_browse)
        path_row.addWidget(self._path_label, 1)
        path_row.addWidget(btn_browse)
        root.addLayout(path_row)

        # Collect button
        self._collect_btn = QPushButton("Collect & Package")
        self._collect_btn.setObjectName("collectBtn")
        self._collect_btn.setEnabled(False)
        self._collect_btn.clicked.connect(self._on_collect)
        root.addWidget(self._collect_btn)

        # "This package will include" list
        include_label = QLabel("THIS PACKAGE WILL INCLUDE")
        include_label.setObjectName("rpLabel")
        root.addWidget(include_label)

        self._include_widget = QWidget()
        self._include_layout = QVBoxLayout(self._include_widget)
        self._include_layout.setContentsMargins(0, 0, 0, 0)
        self._include_layout.setSpacing(2)
        root.addWidget(self._include_widget)

        # Output tree
        tree_label = QLabel("OUTPUT STRUCTURE")
        tree_label.setObjectName("rpLabel")
        root.addWidget(tree_label)

        self._tree_label = QLabel("—")
        self._tree_label.setObjectName("treeDisplay")
        self._tree_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self._tree_label.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        root.addWidget(self._tree_label)

        # Secondary buttons
        sec_row = QHBoxLayout()
        sec_row.setSpacing(6)
        self._srt_btn = QPushButton("Export SRT")
        self._srt_btn.setObjectName("secondaryBtn")
        self._srt_btn.setEnabled(False)
        self._srt_btn.clicked.connect(self._on_export_srt)
        self._open_btn = QPushButton("Open in Finder")
        self._open_btn.setObjectName("secondaryBtn")
        self._open_btn.setEnabled(False)
        self._open_btn.clicked.connect(self._on_open_folder)
        sec_row.addWidget(self._srt_btn)
        sec_row.addWidget(self._open_btn)
        root.addLayout(sec_row)

        # Notes / licensing footer
        self._notes_label = QLabel("")
        self._notes_label.setObjectName("riDetail")
        self._notes_label.setWordWrap(True)
        self._notes_label.setStyleSheet(f"color: {TEXT_FAINT}; font-size: 10px;")
        root.addWidget(self._notes_label)

        root.addStretch()

    # ── public ─────────────────────────────────────────────────────────────────

    def set_result(self, result: AnalysisResult) -> None:
        self._result = result
        self._out_dir = result.default_out_dir()
        self._refresh()

    def set_collecting(self, active: bool) -> None:
        self._collecting = active
        self._collect_btn.setEnabled(not active and self._result is not None)
        self._collect_btn.setText("Collecting…" if active else "Collect & Package")

    def set_collect_done(self, out_dir: Path) -> None:
        self._collecting = False
        self._out_dir = out_dir
        self._collect_btn.setText("Collect & Package")
        self._collect_btn.setEnabled(True)
        self._open_btn.setEnabled(True)
        self._refresh_path_label()

    def clear(self) -> None:
        self._result = None
        self._out_dir = None
        self._collect_btn.setEnabled(False)
        self._collect_btn.setText("Collect & Package")
        self._srt_btn.setEnabled(False)
        self._open_btn.setEnabled(False)
        self._path_label.setText("—")
        self._tree_label.setText("—")
        self._notes_label.setText("")
        self._clear_include()

    # ── private ────────────────────────────────────────────────────────────────

    def _refresh(self) -> None:
        if self._result is None:
            return
        r = self._result
        self._refresh_path_label()
        self._refresh_include(r)
        self._refresh_tree(r)
        self._collect_btn.setEnabled(True)
        self._srt_btn.setEnabled(r.subtitle_cue_count > 0)
        notes = []
        if r.manifest and (r.manifest.music or r.manifest.sfx or r.manifest.stickers):
            notes.append(
                "CapCut library assets (music, SFX, stickers) are copied for "
                "convenience. Copying does not transfer usage rights — verify "
                "distribution rights before publishing."
            )
        if r.speed_curve_count:
            notes.append(
                f"{r.speed_curve_count} speed-curve clip(s) exported at 1.0×. "
                "Rebuild via Time Remapping in Premiere."
            )
        self._notes_label.setText("\n\n".join(notes))

    def _refresh_path_label(self) -> None:
        if self._out_dir:
            parts = self._out_dir.parts[-3:] if len(self._out_dir.parts) > 3 else self._out_dir.parts
            self._path_label.setText("…/" + "/".join(parts))
            self._path_label.setToolTip(str(self._out_dir))

    def _clear_include(self) -> None:
        while self._include_layout.count():
            item = self._include_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _refresh_include(self, r: AnalysisResult) -> None:
        self._clear_include()
        m = r.manifest
        if m is None:
            return
        items = []
        if m.videos:
            items.append(f"▶  {len(m.videos)} video file{'s' if len(m.videos) != 1 else ''}")
        if m.audios:
            items.append(f"♪  {len(m.audios)} audio file{'s' if len(m.audios) != 1 else ''}")
        if m.images:
            items.append(f"□  {len(m.images)} image{'s' if len(m.images) != 1 else ''}")
        if m.music:
            items.append(f"♫  {len(m.music)} music track{'s' if len(m.music) != 1 else ''} ⚠")
        if m.sfx:
            items.append(f"~  {len(m.sfx)} SFX file{'s' if len(m.sfx) != 1 else ''} ⚠")
        items.append("   FCP7 XML (Premiere-ready)")
        items.append("   Relink guide + package summary")
        if r.total_offline:
            items.append(f"⚠  {r.total_offline} asset{'s' if r.total_offline != 1 else ''} offline → offline.md")
        for text in items:
            lbl = QLabel(text)
            lbl.setObjectName("riDetail")
            self._include_layout.addWidget(lbl)

    def _refresh_tree(self, r: AnalysisResult) -> None:
        if self._out_dir is None:
            return
        stem = r.entry.display_name
        tree = _make_tree(self._out_dir, stem)
        self._tree_label.setText(tree)

    def _on_browse(self) -> None:
        start = str(self._out_dir.parent) if self._out_dir else str(Path.home())
        folder = QFileDialog.getExistingDirectory(self, "Choose Output Folder", start)
        if folder:
            self._out_dir = Path(folder) / (self._result.entry.display_name if self._result else "project")
            self._refresh_path_label()
            if self._result:
                self._refresh_tree(self._result)

    def _on_collect(self) -> None:
        if self._out_dir and self._result:
            self.collect_requested.emit(self._out_dir)

    def _on_export_srt(self) -> None:
        if self._out_dir and self._result:
            self.srt_requested.emit(self._out_dir)

    def _on_open_folder(self) -> None:
        target = self._out_dir
        if target and target.exists():
            subprocess.run(["open", str(target)], check=False)
        elif target and target.parent.exists():
            subprocess.run(["open", str(target.parent)], check=False)
