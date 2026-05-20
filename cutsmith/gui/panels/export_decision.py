"""ExportDecisionPanel — right column: output config, collect button, tree."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
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
from cutsmith.gui.style import (
    ACCENT, BG_ELEVATED, BG_DEEP, GREEN, ORANGE,
    TEXT_FAINT, TEXT_MUTED, TEXT_PRIMARY, TEXT_SECONDARY,
    FONT_MONO_STACK,
)


def _make_tree_html(out_dir: Path, stem: str) -> str:
    """Build an HTML-formatted tree for the QLabel (Qt RichText)."""
    ACCENT_C  = "#9b8cff"
    DIR_C     = "#aeaeb2"
    FILE_C    = "#636366"
    ROOT_C    = "#aeaeb2"

    def span(text: str, color: str) -> str:
        return f'<span style="color:{color};">{text}</span>'

    lines = [span(f"out_collect/{out_dir.name}/", ROOT_C)]
    entries = [
        (f"{stem}.xml",              ACCENT_C, False),
        (f"{stem}.package_summary.txt", FILE_C, False),
        (f"{stem}.report.md",        FILE_C,   False),
        (f"{stem}.relink_guide.md",  FILE_C,   False),
        (f"{stem}.manifest.json",    FILE_C,   False),
        ("media/",                   DIR_C,    True),
    ]
    for i, (name, color, is_last_parent) in enumerate(entries):
        is_last = i == len(entries) - 1
        pre = "└── " if is_last else "├── "
        lines.append(f"  {span(pre, FILE_C)}{span(name, color)}")
        if is_last_parent:
            subdirs = ["video/", "audio/", "images/", "music/", "sfx/"]
            for j, d in enumerate(subdirs):
                sp = "    └── " if j == len(subdirs) - 1 else "    ├── "
                lines.append(f"  {span(sp, FILE_C)}{span(d, DIR_C)}")
    return "<br>".join(lines)


class ExportDecisionPanel(QWidget):
    collect_requested = Signal(Path, bool)  # out_dir, include_platform_assets
    srt_requested = Signal(Path)            # out_dir
    open_folder_requested = Signal(Path)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("rightPanel")
        self.setFixedWidth(280)
        self.setStyleSheet(f"background: {BG_ELEVATED};")

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
        self._collect_btn = QPushButton("Collect Premiere Package")
        self._collect_btn.setObjectName("collectBtn")
        self._collect_btn.setEnabled(False)
        self._collect_btn.clicked.connect(self._on_collect)
        root.addWidget(self._collect_btn)

        self._collect_reason = QLabel("")
        self._collect_reason.setStyleSheet(
            f"color: {TEXT_FAINT}; font-family: {FONT_MONO_STACK};"
            f" font-size: 10px; background: transparent;"
        )
        self._collect_reason.setWordWrap(True)
        self._collect_reason.setAlignment(Qt.AlignCenter)
        root.addWidget(self._collect_reason)

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
        self._tree_label.setTextFormat(Qt.RichText)
        self._tree_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self._tree_label.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self._tree_label.setMaximumWidth(246)  # cap at content area; clips long paths at panel edge
        root.addWidget(self._tree_label)

        # Post-collect action buttons — hidden until collect completes
        self._post_collect_widget = QWidget()
        self._post_collect_widget.setStyleSheet("background: transparent;")
        post_collect_lay = QVBoxLayout(self._post_collect_widget)
        post_collect_lay.setContentsMargins(0, 0, 0, 0)
        post_collect_lay.setSpacing(6)

        action_row = QHBoxLayout()
        action_row.setSpacing(6)
        self._open_btn = QPushButton("Open Package")
        self._open_btn.setObjectName("secondaryBtn")
        self._open_btn.clicked.connect(self._on_open_folder)
        self._xml_btn = QPushButton("Reveal XML")
        self._xml_btn.setObjectName("secondaryBtn")
        self._xml_btn.clicked.connect(self._on_reveal_xml)
        action_row.addWidget(self._open_btn)
        action_row.addWidget(self._xml_btn)
        post_collect_lay.addLayout(action_row)
        self._post_collect_widget.hide()
        root.addWidget(self._post_collect_widget)

        # SRT export button
        srt_row = QHBoxLayout()
        srt_row.setSpacing(6)
        self._srt_btn = QPushButton("Export SRT")
        self._srt_btn.setObjectName("secondaryBtn")
        self._srt_btn.setEnabled(False)
        self._srt_btn.clicked.connect(self._on_export_srt)
        srt_row.addWidget(self._srt_btn)
        srt_row.addStretch()
        root.addLayout(srt_row)

        # Advanced options (legal-sensitive, default OFF)
        adv_label = QLabel("ADVANCED")
        adv_label.setObjectName("rpLabel")
        root.addWidget(adv_label)

        self._include_platform_cb = QCheckBox(
            "Include cached CapCut library audio"
        )
        self._include_platform_cb.setChecked(False)
        self._include_platform_cb.setStyleSheet(
            f"color: {TEXT_SECONDARY}; font-family: {FONT_MONO_STACK};"
            f" font-size: 10px; background: transparent;"
        )
        root.addWidget(self._include_platform_cb)

        warn_box = QWidget()
        warn_box.setStyleSheet(
            f"background: rgba(255,159,10,0.10); "
            f"border-left: 3px solid {ORANGE}; "
            f"border-radius: 2px;"
        )
        warn_box_lay = QVBoxLayout(warn_box)
        warn_box_lay.setContentsMargins(8, 6, 8, 6)
        warn_box_lay.setSpacing(0)
        self._platform_warn = QLabel(
            "CapCut library music/SFX may be licensed for use "
            "within CapCut/TikTok only. Copying does not transfer "
            "usage rights. Verify before publishing."
        )
        self._platform_warn.setStyleSheet(
            f"color: {ORANGE}; font-family: {FONT_MONO_STACK};"
            f" font-size: 10px; line-height: 1.6;"
            f" background: transparent; border: none;"
        )
        self._platform_warn.setWordWrap(True)
        warn_box_lay.addWidget(self._platform_warn)
        root.addWidget(warn_box)

        # Notes / licensing footer
        self._notes_label = QLabel("")
        self._notes_label.setObjectName("riDetail")
        self._notes_label.setWordWrap(True)
        self._notes_label.setStyleSheet(
            f"color: {TEXT_FAINT}; font-family: {FONT_MONO_STACK}; font-size: 10px;"
        )
        root.addWidget(self._notes_label)

        root.addStretch()

    # ── public ─────────────────────────────────────────────────────────────────

    def set_result(self, result: AnalysisResult) -> None:
        self._result = result
        self._out_dir = result.default_out_dir()
        self._refresh()

    def set_stage(self, msg: str) -> None:
        self._collect_reason.setText(msg)

    def set_collecting(self, active: bool) -> None:
        self._collecting = active
        self._collect_btn.setEnabled(not active and self._result is not None)
        self._collect_btn.setText("Collecting…" if active else "Collect Premiere Package")

    def set_collect_done(self, out_dir: Path) -> None:
        self._collecting = False
        self._out_dir = out_dir
        self._collect_btn.setText("Collect Premiere Package")
        self._collect_btn.setEnabled(True)
        self._collect_reason.setText("")
        self._post_collect_widget.show()
        self._refresh_path_label()

    def clear(self) -> None:
        self._result = None
        self._out_dir = None
        self._collect_btn.setEnabled(False)
        self._collect_btn.setText("Collect Premiere Package")
        self._collect_reason.setText("Select a project on the left to begin")
        self._srt_btn.setEnabled(False)
        self._post_collect_widget.hide()
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
        enc = (r.detect.encryption or "").lower()
        is_enc = enc not in ("", "none", "plaintext")
        is_err = r.detect.supported_status in ("error",)
        if is_enc:
            self._collect_btn.setEnabled(False)
            self._collect_reason.setText("Encrypted project — cannot collect")
        elif is_err:
            self._collect_btn.setEnabled(False)
            self._collect_reason.setText("Project could not be read")
        else:
            self._collect_btn.setEnabled(True)
            self._collect_reason.setText("")
        self._srt_btn.setEnabled(r.subtitle_cue_count > 0)
        notes = []
        if r.speed_curve_count:
            notes.append(
                f"{r.speed_curve_count} variable speed ramp clip(s) — "
                "exported at 1.0× (not reconstructed). "
                "Rebuild via Effect Controls → Time Remapping in Premiere."
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

        # User-owned media (always included) — green ✓ rows
        included = []
        if m.videos:
            included.append(f"✓  {len(m.videos)} video file{'s' if len(m.videos) != 1 else ''}")
        if m.audios:
            included.append(f"✓  {len(m.audios)} audio file{'s' if len(m.audios) != 1 else ''}")
        if m.images:
            included.append(f"✓  {len(m.images)} image{'s' if len(m.images) != 1 else ''}")
        included.append("✓  FCP7 XML · relink guide · reports")

        for text in included:
            lbl = QLabel(text)
            lbl.setObjectName("includeOk")
            lbl.setWordWrap(True)
            self._include_layout.addWidget(lbl)

        # Platform assets — detected but not copied — orange ⚠ rows
        platform = []
        if m.music:
            platform.append(
                f"⚠  {len(m.music)} CapCut library music track{'s' if len(m.music) != 1 else ''} "
                "— detected, not copied"
            )
        if m.sfx:
            platform.append(
                f"⚠  {len(m.sfx)} CapCut library SFX file{'s' if len(m.sfx) != 1 else ''} "
                "— detected, not copied"
            )
        if m.stickers:
            platform.append(
                f"⚠  {len(m.stickers)} CapCut sticker{'s' if len(m.stickers) != 1 else ''} "
                "— detected, not copied"
            )

        for text in platform:
            lbl = QLabel(text)
            lbl.setObjectName("includeWarn")
            lbl.setWordWrap(True)
            self._include_layout.addWidget(lbl)

        if r.total_offline:
            warn = QLabel(
                f"⚠  {r.total_offline} asset{'s' if r.total_offline != 1 else ''} offline → offline.md"
            )
            warn.setObjectName("includeWarn")
            warn.setWordWrap(True)
            self._include_layout.addWidget(warn)

        if platform:
            legend = QLabel("✓ included   ⚠ detected, not copied")
            legend.setObjectName("includeMuted")
            self._include_layout.addWidget(legend)

    def _refresh_tree(self, r: AnalysisResult) -> None:
        if self._out_dir is None:
            return
        stem = r.entry.display_name
        tree = _make_tree_html(self._out_dir, stem)
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
            self.collect_requested.emit(
                self._out_dir,
                self._include_platform_cb.isChecked(),
            )

    def _on_export_srt(self) -> None:
        if self._out_dir and self._result:
            self.srt_requested.emit(self._out_dir)

    def _on_reveal_xml(self) -> None:
        if self._out_dir and self._result:
            stem = self._result.entry.display_name
            xml_path = self._out_dir / f"{stem}.xml"
            if xml_path.exists():
                subprocess.run(["open", "-R", str(xml_path)], check=False)
            elif self._out_dir.exists():
                subprocess.run(["open", str(self._out_dir)], check=False)

    def _on_open_folder(self) -> None:
        target = self._out_dir
        if target and target.exists():
            subprocess.run(["open", str(target)], check=False)
        elif target and target.parent.exists():
            subprocess.run(["open", str(target.parent)], check=False)
