"""ProjectReadinessPanel — center column: project card, checklist, asset table."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from cutsmith.gui.models import AnalysisResult
from cutsmith.gui.style import (
    ACCENT, ACCENT_DIM, GREEN, ORANGE, RED, TEXT_FAINT, TEXT_MUTED, TEXT_PRIMARY
)

# ── cover thumbnail ────────────────────────────────────────────────────────────

_COVER_SIZE = 72


class _CoverThumbnail(QLabel):
    """72×72 cover image or dark placeholder with project initials."""

    def __init__(self, cover_path: Path | None, name: str, parent=None):
        super().__init__(parent)
        self.setFixedSize(_COVER_SIZE, _COVER_SIZE)
        self.setScaledContents(False)
        pix = self._load(cover_path) or self._placeholder(name)
        self.setPixmap(pix)

    def _load(self, cover_path: Path | None) -> QPixmap | None:
        if not cover_path or not cover_path.exists():
            return None
        pix = QPixmap(str(cover_path))
        if pix.isNull():
            return None
        # Scale to fill, then center-crop to exact square
        pix = pix.scaled(_COVER_SIZE, _COVER_SIZE,
                          Qt.KeepAspectRatioByExpanding,
                          Qt.SmoothTransformation)
        if pix.width() > _COVER_SIZE or pix.height() > _COVER_SIZE:
            x = (pix.width() - _COVER_SIZE) // 2
            y = (pix.height() - _COVER_SIZE) // 2
            pix = pix.copy(x, y, _COVER_SIZE, _COVER_SIZE)
        return pix

    def _placeholder(self, name: str) -> QPixmap:
        pix = QPixmap(_COVER_SIZE, _COVER_SIZE)
        pix.fill(QColor(ACCENT_DIM))
        painter = QPainter(pix)
        painter.setRenderHint(QPainter.Antialiasing)
        font = QFont("SF Pro Display", 26, QFont.Bold)
        painter.setFont(font)
        painter.setPen(QColor(ACCENT))
        initials = (name[:2] if len(name) >= 2 else name).upper()
        painter.drawText(pix.rect(), Qt.AlignCenter, initials)
        painter.end()
        return pix


# ── helpers ────────────────────────────────────────────────────────────────────

def _divider() -> QFrame:
    f = QFrame()
    f.setObjectName("divider")
    f.setFrameShape(QFrame.HLine)
    f.setFixedHeight(1)
    return f


def _section_header(text: str) -> QLabel:
    lbl = QLabel(text.upper())
    lbl.setObjectName("sectionHeader")
    return lbl


class _StatCell(QWidget):
    def __init__(self, val: str, key: str, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        v = QLabel(val)
        v.setObjectName("statVal")
        v.setAlignment(Qt.AlignCenter)
        k = QLabel(key)
        k.setObjectName("statKey")
        k.setAlignment(Qt.AlignCenter)
        lay.addWidget(v)
        lay.addWidget(k)


class _ReadinessRow(QWidget):
    def __init__(self, ok: bool | None, label: str, detail: str, parent=None):
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 2, 0, 2)
        lay.setSpacing(8)

        if ok is True:
            icon_text, icon_color = "✓", GREEN
        elif ok is False:
            icon_text, icon_color = "⚠", ORANGE
        else:
            icon_text, icon_color = "–", TEXT_FAINT

        icon = QLabel(icon_text)
        icon.setObjectName("riIcon")
        icon.setFixedWidth(16)
        icon.setStyleSheet(f"color: {icon_color}; font-size: 12px;")
        lay.addWidget(icon)

        text_col = QVBoxLayout()
        text_col.setSpacing(1)
        lbl = QLabel(label)
        lbl.setObjectName("riLabel" if ok is not False else "riLabelWarn")
        if ok is False:
            lbl.setStyleSheet(f"color: {ORANGE};")
        dtl = QLabel(detail)
        dtl.setObjectName("riDetail")
        dtl.setWordWrap(True)
        text_col.addWidget(lbl)
        text_col.addWidget(dtl)
        lay.addLayout(text_col, 1)


class _AssetRow(QWidget):
    def __init__(self, icon: str, name: str, count_label: str, muted: bool = False, parent=None):
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 1, 0, 1)
        lay.setSpacing(8)
        icon_lbl = QLabel(icon)
        icon_lbl.setFixedWidth(16)
        icon_lbl.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 11px;")
        name_lbl = QLabel(name)
        name_lbl.setObjectName("assetRowMuted" if muted else "assetRow")
        count_lbl = QLabel(count_label)
        count_lbl.setObjectName("assetRowMuted")
        count_lbl.setAlignment(Qt.AlignRight)
        lay.addWidget(icon_lbl)
        lay.addWidget(name_lbl, 1)
        lay.addWidget(count_lbl)


# ── main panel ─────────────────────────────────────────────────────────────────

class ProjectReadinessPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("centerPanel")

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        self._content = QWidget()
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setContentsMargins(24, 20, 24, 20)
        self._content_layout.setSpacing(8)
        scroll.setWidget(self._content)
        root.addWidget(scroll)

        self._show_empty()

    # ── public ─────────────────────────────────────────────────────────────────

    def show_loading(self, name: str) -> None:
        self._clear()
        lbl = QLabel(f"Analyzing {name}…")
        lbl.setObjectName("cardMeta")
        lbl.setAlignment(Qt.AlignCenter)
        self._content_layout.addWidget(lbl)
        self._content_layout.addStretch()

    def show_result(self, result: AnalysisResult) -> None:
        self._clear()
        self._build_card(result)
        self._content_layout.addWidget(_divider())
        self._build_readiness(result)
        self._content_layout.addWidget(_divider())
        self._build_asset_table(result)
        self._content_layout.addStretch()

    def show_error(self, msg: str) -> None:
        self._clear()
        lbl = QLabel(f"Analysis failed:\n{msg}")
        lbl.setObjectName("cardMeta")
        lbl.setStyleSheet(f"color: #ff453a;")
        lbl.setWordWrap(True)
        self._content_layout.addWidget(lbl)
        self._content_layout.addStretch()

    # ── private ────────────────────────────────────────────────────────────────

    def _clear(self):
        while self._content_layout.count():
            item = self._content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                # clean sub-layouts
                pass

    def _show_empty(self):
        lbl = QLabel("Select a project to begin")
        lbl.setObjectName("cardMeta")
        lbl.setAlignment(Qt.AlignCenter)
        self._content_layout.addStretch()
        self._content_layout.addWidget(lbl)
        self._content_layout.addStretch()

    def _build_card(self, r: AnalysisResult):
        # Cover + title row
        card_row = QHBoxLayout()
        card_row.setSpacing(14)
        card_row.setAlignment(Qt.AlignTop)

        # Cover thumbnail (72×72)
        thumb = _CoverThumbnail(r.cover_path, r.entry.display_name)
        thumb.setStyleSheet(
            f"border-radius: 6px; background: {ACCENT_DIM};"
        )
        card_row.addWidget(thumb, 0, Qt.AlignTop)

        # Name + meta stacked on the right
        text_col = QVBoxLayout()
        text_col.setSpacing(3)
        text_col.setAlignment(Qt.AlignTop)

        name_lbl = QLabel(r.entry.display_name)
        name_lbl.setObjectName("cardName")
        text_col.addWidget(name_lbl)

        sv = r.detect.schema_version or ""
        sv_str = f" · schema {sv}" if sv else ""
        meta = f"{r.entry.app_label}{sv_str} · {r.readability_label}"
        meta_lbl = QLabel(meta)
        meta_lbl.setObjectName("cardMeta")
        text_col.addWidget(meta_lbl)

        badge = QLabel("PORTABLE PACKAGE READY" if r.is_portable else "PARTIAL — SOME ASSETS OFFLINE")
        badge.setObjectName("badgeOk" if r.is_portable else "badgeWarn")
        badge.setFixedHeight(18)
        badge.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        text_col.addWidget(badge)

        card_row.addLayout(text_col, 1)
        self._content_layout.addLayout(card_row)

        self._content_layout.addSpacing(8)

        # Stats strip
        stats_row = QHBoxLayout()
        stats_row.setSpacing(0)
        cells = [
            (r.duration_label, "Duration"),
            (r.resolution_label, "Canvas"),
            (r.fps_label, "Frame rate"),
            (str(r.clip_count), "Clips"),
        ]
        for i, (val, key) in enumerate(cells):
            cell = _StatCell(val, key)
            stats_row.addWidget(cell, 1)
            if i < len(cells) - 1:
                sep = QFrame()
                sep.setFrameShape(QFrame.VLine)
                sep.setStyleSheet(f"color: #3a3a3c;")
                stats_row.addWidget(sep)
        self._content_layout.addLayout(stats_row)

    def _build_readiness(self, r: AnalysisResult):
        self._content_layout.addWidget(_section_header("Project Readiness"))

        rows = [
            (True, "Timeline structure",
             f"{r.video_track_count} video track{'s' if r.video_track_count != 1 else ''}"
             f" · {r.audio_track_count} audio track{'s' if r.audio_track_count != 1 else ''}"
             f" · {r.clip_count} clip{'s' if r.clip_count != 1 else ''}"),
            (True, "Asset paths resolved",
             f"{r.total_online} online"
             + (f" · {r.total_offline} offline" if r.total_offline else "")),
            (True, "FCP7 XML export", "Sequence + master clips · constant speed via timeremap"),
        ]

        if r.speed_clip_count:
            rows.append((False, "Constant speed clips",
                          f"{r.speed_clip_count} clip{'s' if r.speed_clip_count != 1 else ''} "
                          "— speed preserved via timeremap filter"))

        if r.speed_curve_count:
            rows.append((False, "Speed curves",
                          f"{r.speed_curve_count} clip{'s' if r.speed_curve_count != 1 else ''} "
                          "— exported as 1.0× · rebuild via Time Remapping in Premiere"))

        if r.subtitle_cue_count:
            rows.append((False, "Subtitles",
                          f"{r.subtitle_cue_count} cue{'s' if r.subtitle_cue_count != 1 else ''} "
                          "— not in XML · export separately via Export SRT"))

        if r.total_report_only:
            rows.append((False, "Proprietary assets",
                          f"{r.total_report_only} item{'s' if r.total_report_only != 1 else ''} "
                          "(effects/filters/transitions) — not portable"))

        for ok, label, detail in rows:
            self._content_layout.addWidget(_ReadinessRow(ok, label, detail))

    def _build_asset_table(self, r: AnalysisResult):
        if r.manifest is None:
            return
        m = r.manifest

        self._content_layout.addWidget(_section_header("Assets"))

        # Fully migrated
        migrated = []
        if m.videos:
            migrated.append(("▶", "Video clips", f"{len(m.videos)} file{'s' if len(m.videos) != 1 else ''}"))
        if m.audios:
            migrated.append(("♪", "Audio tracks", f"{len(m.audios)} file{'s' if len(m.audios) != 1 else ''}"))
        if m.images:
            migrated.append(("□", "Images", f"{len(m.images)} file{'s' if len(m.images) != 1 else ''}"))

        if migrated:
            grp = QLabel("FULLY MIGRATED")
            grp.setObjectName("assetGroupLabel")
            self._content_layout.addWidget(grp)
            for icon, name, count in migrated:
                self._content_layout.addWidget(_AssetRow(icon, name, count))

        # With warning
        warned = []
        if m.music:
            warned.append(("♫", "CapCut music", f"{len(m.music)} — verify rights before publishing"))
        if m.sfx:
            warned.append(("~", "SFX", f"{len(m.sfx)} — verify rights before publishing"))
        if m.stickers:
            warned.append(("◈", "Stickers (cached)", f"{len(m.stickers)}"))

        if warned:
            grp = QLabel("INCLUDED WITH WARNING")
            grp.setObjectName("assetGroupLabel")
            self._content_layout.addWidget(grp)
            for icon, name, count in warned:
                self._content_layout.addWidget(_AssetRow(icon, name, count, muted=False))

        # Report-only
        report = []
        if m.effects:
            report.append(("✦", "Effects", f"{len(m.effects)} — CapCut only"))
        if m.filters:
            report.append(("◫", "Filters/LUTs", f"{len(m.filters)} — CapCut only"))
        if m.transitions:
            report.append(("⇌", "Transitions", f"{len(m.transitions)} — CapCut only"))

        if report:
            grp = QLabel("REPORT-ONLY · NOT PORTABLE")
            grp.setObjectName("assetGroupLabel")
            self._content_layout.addWidget(grp)
            for icon, name, count in report:
                self._content_layout.addWidget(_AssetRow(icon, name, count, muted=True))
