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
    ACCENT, BG_BASE, BG_ELEVATED, BORDER_DEFAULT,
    GREEN, ORANGE, TEXT_FAINT, TEXT_MUTED, TEXT_PRIMARY, TEXT_SECONDARY,
)

# ── cover thumbnail ────────────────────────────────────────────────────────────

_COVER_W = 96
_COVER_H = 72


class _CoverThumbnail(QLabel):
    """96×72 cover image or dark placeholder with project initials."""

    def __init__(self, cover_path: Path | None, name: str, parent=None):
        super().__init__(parent)
        self.setFixedSize(_COVER_W, _COVER_H)
        self.setScaledContents(False)
        self.setStyleSheet(
            f"border-radius: 4px; border: 1px solid {BORDER_DEFAULT};"
            f" background: {BG_ELEVATED};"
        )
        pix = self._load(cover_path) or self._placeholder(name)
        self.setPixmap(pix)

    def _load(self, cover_path: Path | None) -> QPixmap | None:
        if not cover_path or not cover_path.exists():
            return None
        pix = QPixmap(str(cover_path))
        if pix.isNull():
            return None
        pix = pix.scaled(_COVER_W, _COVER_H,
                          Qt.KeepAspectRatioByExpanding,
                          Qt.SmoothTransformation)
        if pix.width() > _COVER_W or pix.height() > _COVER_H:
            x = (pix.width() - _COVER_W) // 2
            y = (pix.height() - _COVER_H) // 2
            pix = pix.copy(x, y, _COVER_W, _COVER_H)
        return pix

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(QColor(255, 255, 255, 20))
        painter.drawRoundedRect(self.rect().adjusted(0, 0, -1, -1), 4, 4)
        painter.end()

    def _placeholder(self, name: str) -> QPixmap:
        pix = QPixmap(_COVER_W, _COVER_H)
        pix.fill(QColor(BG_ELEVATED))
        painter = QPainter(pix)
        painter.setRenderHint(QPainter.Antialiasing)
        font = QFont("IBM Plex Sans", 22, QFont.Bold)
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


def _wrap(layout) -> QWidget:
    """Wrap a bare layout in a QWidget so _clear() can deleteLater() it."""
    w = QWidget()
    w.setLayout(layout)
    return w


class _StatCell(QWidget):
    def __init__(self, val: str, key: str, parent=None):
        super().__init__(parent)
        self.setObjectName("statCell")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 6, 10, 6)
        lay.setSpacing(2)
        v = QLabel(val)
        v.setObjectName("statVal")
        v.setAlignment(Qt.AlignCenter)
        k = QLabel(key)
        k.setObjectName("statKey")
        k.setAlignment(Qt.AlignCenter)
        lay.addWidget(v)
        lay.addWidget(k)


class _StatSep(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.VLine)
        self.setFixedWidth(1)
        self.setStyleSheet(f"background: {BORDER_DEFAULT}; border: none;")


class _ReadinessRow(QWidget):
    def __init__(self, ok: bool | None, label: str, detail: str, parent=None):
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 3, 0, 3)
        lay.setSpacing(10)

        if ok is True:
            icon_text, icon_color = "✓", GREEN
        elif ok is False:
            icon_text, icon_color = "⚠", ORANGE
        else:
            icon_text, icon_color = "△", ACCENT

        icon = QLabel(icon_text)
        icon.setObjectName("riIcon")
        icon.setFixedWidth(16)
        icon.setStyleSheet(
            f"color: {icon_color}; font-size: 12px; background: transparent;"
        )
        lay.addWidget(icon, 0, Qt.AlignTop)

        text_w = QWidget()
        text_lay = QVBoxLayout(text_w)
        text_lay.setContentsMargins(0, 0, 0, 0)
        text_lay.setSpacing(2)

        lbl = QLabel(label)
        if ok is False:
            lbl.setObjectName("riLabelWarn")
            lbl.setStyleSheet(f"color: {ORANGE}; background: transparent;")
        elif ok is None:
            lbl.setObjectName("riLabel")
            lbl.setStyleSheet(f"color: {TEXT_SECONDARY}; background: transparent;")
        else:
            lbl.setObjectName("riLabel")

        dtl = QLabel(detail)
        dtl.setObjectName("riDetail")
        dtl.setTextFormat(Qt.RichText)
        dtl.setWordWrap(True)
        text_lay.addWidget(lbl)
        text_lay.addWidget(dtl)

        lay.addWidget(text_w, 1)


class _AssetRow(QWidget):
    def __init__(self, icon: str, name: str, count_label: str, muted: bool = False, parent=None):
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 2, 0, 2)
        lay.setSpacing(8)
        icon_lbl = QLabel(icon)
        icon_lbl.setFixedWidth(16)
        icon_lbl.setStyleSheet(
            f"color: {TEXT_MUTED}; font-size: 11px; background: transparent;"
        )
        name_lbl = QLabel(name)
        name_lbl.setObjectName("assetRowMuted" if muted else "assetRow")
        count_lbl = QLabel(count_label)
        count_lbl.setObjectName("assetRowMuted")
        count_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        lay.addWidget(icon_lbl)
        lay.addWidget(name_lbl, 1)
        lay.addWidget(count_lbl)


# ── main panel ─────────────────────────────────────────────────────────────────

class ProjectReadinessPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("centerPanel")
        self.setStyleSheet(f"background: {BG_BASE};")

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.setStyleSheet(f"background: {BG_BASE}; border: none;")
        scroll.viewport().setStyleSheet(f"background: {BG_BASE};")

        self._content = QWidget()
        self._content.setStyleSheet(f"background: {BG_BASE};")
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
        self._content_layout.addStretch()
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
        lbl.setStyleSheet("color: #ff453a; background: transparent;")
        lbl.setWordWrap(True)
        self._content_layout.addStretch()
        self._content_layout.addWidget(lbl)
        self._content_layout.addStretch()

    # ── private ────────────────────────────────────────────────────────────────

    def _clear(self):
        while self._content_layout.count():
            item = self._content_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

    def _show_empty(self):
        self._content_layout.addStretch(2)

        headline = QLabel("Move your CapCut rough cut\ninto a portable Premiere package")
        headline.setObjectName("onboardHeadline")
        headline.setAlignment(Qt.AlignCenter)
        self._content_layout.addWidget(headline)

        self._content_layout.addSpacing(8)

        subtext = QLabel("Timeline structure · user media · subtitles · speed")
        subtext.setObjectName("onboardSubtext")
        subtext.setAlignment(Qt.AlignCenter)
        self._content_layout.addWidget(subtext)

        self._content_layout.addSpacing(20)

        helper = QLabel("Select a project on the left\nto analyze timeline compatibility.")
        helper.setObjectName("onboardHelper")
        helper.setAlignment(Qt.AlignCenter)
        self._content_layout.addWidget(helper)

        self._content_layout.addStretch(3)

    def _build_card(self, r: AnalysisResult):
        card_w = QWidget()
        card_row = QHBoxLayout(card_w)
        card_row.setContentsMargins(0, 0, 0, 0)
        card_row.setSpacing(14)
        card_row.setAlignment(Qt.AlignTop)

        thumb = _CoverThumbnail(r.cover_path, r.entry.display_name)
        card_row.addWidget(thumb, 0, Qt.AlignTop)

        title_w = QWidget()
        title_lay = QVBoxLayout(title_w)
        title_lay.setContentsMargins(0, 0, 0, 0)
        title_lay.setSpacing(4)
        title_lay.setAlignment(Qt.AlignTop)

        name_lbl = QLabel(r.entry.display_name)
        name_lbl.setObjectName("cardName")
        title_lay.addWidget(name_lbl)

        sv = r.detect.schema_version or ""
        meta_lbl = QLabel(f"{r.entry.app_label} · {r.readability_label}")
        meta_lbl.setObjectName("cardMeta")
        if sv:
            meta_lbl.setToolTip(f"schema {sv}")
        title_lay.addWidget(meta_lbl)

        _badge_text = {
            "portable":  "PORTABLE · READY",
            "limited":   "READY WITH NOTES",
            "partial":   "PARTIAL · ASSETS OFFLINE",
            "encrypted": "ENCRYPTED",
            "error":     "ERROR",
        }
        _badge_obj = {
            "portable":  "badgeOk",
            "limited":   "badgeWarn",
            "partial":   "badgeWarn",
            "encrypted": "badgeError",
            "error":     "badgeError",
        }
        state = r.readiness_state
        badge = QLabel(_badge_text.get(state, state.upper()))
        badge.setObjectName(_badge_obj.get(state, "badgeDim"))
        badge.setFixedHeight(18)
        badge.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        title_lay.addWidget(badge)

        card_row.addWidget(title_w, 1)
        self._content_layout.addWidget(card_w)

        self._content_layout.addSpacing(10)

        # Stats strip — cells separated by spacing, no explicit separator widget
        stats_w = QWidget()
        stats_w.setFixedHeight(56)
        stats_row = QHBoxLayout(stats_w)
        stats_row.setContentsMargins(0, 0, 0, 0)
        stats_row.setSpacing(4)
        cells = [
            (r.duration_label, "Duration"),
            (r.resolution_label, "Canvas"),
            (r.fps_label, "Frame rate"),
            (str(r.clip_count), "Clips"),
        ]
        for val, key in cells:
            stats_row.addWidget(_StatCell(val, key), 1)
        self._content_layout.addWidget(stats_w)

    def _build_readiness(self, r: AnalysisResult):
        self._content_layout.addWidget(_section_header("Project Readiness"))

        offline_detail = f"{r.total_online} online"
        if r.total_offline:
            offline_detail += (
                f" · <span style='color:{ORANGE};font-weight:600;'>"
                f"{r.total_offline} offline</span>"
            )

        rows = [
            (True, "Timeline structure",
             f"{r.video_track_count} video track{'s' if r.video_track_count != 1 else ''}"
             f" · {r.audio_track_count} audio track{'s' if r.audio_track_count != 1 else ''}"
             f" · {r.clip_count} clip{'s' if r.clip_count != 1 else ''}"),
            (True, "Asset paths resolved", offline_detail),
            (True, "FCP7 XML (timeline structure)",
             "Sequence + master clips · constant speed via timeremap · Premiere-ready"),
        ]

        if r.speed_clip_count:
            n = r.speed_clip_count
            rows.append((False, "Speed-adjusted clips",
                          f"{n} clip{'s' if n != 1 else ''} with constant speed changes "
                          "— preserved in export via timeremap"))
        if r.speed_curve_count:
            n = r.speed_curve_count
            rows.append((False, "Speed ramp clips",
                          f"{n} clip{'s' if n != 1 else ''} with variable speed ramps "
                          "— exported at 1.0×. Rebuild via Time Remapping in Premiere."))
        if r.subtitle_cue_count:
            n = r.subtitle_cue_count
            rows.append((False, "Subtitles",
                          f"{n} subtitle cue{'s' if n != 1 else ''} — not included in XML. "
                          "Use \"Export SRT\" to get a sidecar file."))
        if r.total_report_only:
            n = r.total_report_only
            rows.append((False, "CapCut-proprietary features",
                          f"{n} effect{'s' if n != 1 else ''}, filter{'s' if n != 1 else ''}, "
                          f"or transition{'s' if n != 1 else ''} — not portable outside CapCut"))

        for ok, label, detail in rows:
            self._content_layout.addWidget(_ReadinessRow(ok, label, detail))

    def _build_asset_table(self, r: AnalysisResult):
        if r.manifest is None:
            return
        m = r.manifest

        self._content_layout.addWidget(_section_header("Assets"))

        migrated = []
        if m.videos:
            migrated.append(("▶", "Video clips",
                              f"{len(m.videos)} file{'s' if len(m.videos) != 1 else ''}"))
        if m.audios:
            migrated.append(("♪", "Audio tracks",
                              f"{len(m.audios)} file{'s' if len(m.audios) != 1 else ''}"))
        if m.images:
            migrated.append(("▫", "Images",
                              f"{len(m.images)} file{'s' if len(m.images) != 1 else ''}"))
        if migrated:
            grp = QLabel("USER-OWNED MEDIA — INCLUDED")
            grp.setObjectName("assetGroupLabel")
            self._content_layout.addWidget(grp)
            for icon, name, count in migrated:
                self._content_layout.addWidget(_AssetRow(icon, name, count))

        detected = []
        if m.music:
            detected.append(("♫", "CapCut library music",
                              f"{len(m.music)} detected — not copied by default"))
        if m.sfx:
            detected.append(("≈", "CapCut SFX",
                              f"{len(m.sfx)} detected — not copied by default"))
        if m.stickers:
            detected.append(("◆", "CapCut stickers",
                              f"{len(m.stickers)} detected — not copied by default"))
        if detected:
            grp = QLabel("PLATFORM ASSETS — DETECTED, NOT COPIED")
            grp.setObjectName("assetGroupLabel")
            self._content_layout.addWidget(grp)
            for icon, name, count in detected:
                self._content_layout.addWidget(_AssetRow(icon, name, count, muted=True))

        report = []
        if m.effects:
            report.append(("⚙", "Effects", f"{len(m.effects)} — CapCut proprietary"))
        if m.filters:
            report.append(("◧", "Filters/LUTs", f"{len(m.filters)} — CapCut proprietary"))
        if m.transitions:
            report.append(("⇄", "Transitions", f"{len(m.transitions)} — CapCut proprietary"))
        if report:
            grp = QLabel("CAPCUT-PROPRIETARY · NOT PORTABLE")
            grp.setObjectName("assetGroupLabel")
            self._content_layout.addWidget(grp)
            for icon, name, count in report:
                self._content_layout.addWidget(_AssetRow(icon, name, count, muted=True))
