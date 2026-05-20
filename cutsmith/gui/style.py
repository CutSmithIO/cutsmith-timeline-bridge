"""QSS stylesheet tokens and builder for the CutSmith GUI."""

# ── Backgrounds ──────────────────────────────────────────
BG_BASE        = "#1c1c1e"   # main window, panels
BG_ELEVATED    = "#242426"   # panel headers, selected rows
BG_RAISED      = BG_ELEVATED  # legacy alias
BG_CONTROL     = "#2c2c2e"   # buttons, inputs, selects
BG_HOVER       = BG_CONTROL  # legacy alias
BG_DEEP        = "#0d0d0d"   # log area, deep inset surfaces

# ── Borders ──────────────────────────────────────────────
BORDER_DEFAULT = "#3a3a3c"   # standard border
BORDER         = BORDER_DEFAULT  # legacy alias
BORDER_SUBTLE  = "#2c2c2e"   # between-row dividers
BORDER_FAINT   = BORDER_SUBTLE   # legacy alias

# ── Text ─────────────────────────────────────────────────
TEXT_PRIMARY   = "#e5e5ea"
TEXT_SECONDARY = "#98989f"
TEXT_MUTED     = "#636366"
TEXT_FAINT     = "#48484a"

# ── Accent ───────────────────────────────────────────────
ACCENT         = "#9b8cff"
ACCENT_DARK    = "#7b6cdf"
ACCENT_DIM     = "rgba(155,140,255,0.08)"  # QSS only — not valid for QColor()
ACCENT_SEL     = ACCENT_DIM  # legacy alias

# ── Semantic ─────────────────────────────────────────────
GREEN          = "#30d158"
ORANGE         = "#ff9f0a"
RED            = "#ff453a"

# ── Typography ───────────────────────────────────────────
FONT_MONO          = "IBM Plex Mono"
FONT_SANS          = "IBM Plex Sans"
FONT_MONO_FALLBACK = "SF Mono, Menlo, Consolas"
FONT_SANS_FALLBACK = "SF Pro Text, Helvetica Neue, Arial"

FONT_MONO_STACK = f"'{FONT_MONO}', {FONT_MONO_FALLBACK}, monospace"
FONT_SANS_STACK = f"'{FONT_SANS}', {FONT_SANS_FALLBACK}, sans-serif"

# ─── full QSS ─────────────────────────────────────────────────────────────────
APP_QSS = f"""
/* ── base reset ── */
QWidget {{
    background: transparent;
    color: {TEXT_PRIMARY};
    font-family: {FONT_MONO_STACK};
    font-size: 11px;
}}

QMainWindow {{
    background: {BG_BASE};
}}

QWidget#root {{
    background: {BG_BASE};
}}

/* scroll areas */
QScrollArea {{
    background: {BG_BASE};
    border: none;
}}
QScrollArea > QWidget {{
    background: {BG_BASE};
}}
QAbstractScrollArea {{
    background: {BG_BASE};
    border: none;
}}

/* ── scrollbars ── */
QScrollBar:vertical {{
    background: {BG_BASE};
    width: 6px;
    margin: 0;
    border: none;
}}
QScrollBar::handle:vertical {{
    background: {BORDER_DEFAULT};
    border-radius: 3px;
    min-height: 20px;
}}
QScrollBar::handle:vertical:hover {{
    background: {TEXT_FAINT};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar:horizontal {{
    height: 6px;
    background: {BG_BASE};
    border: none;
}}
QScrollBar::handle:horizontal {{
    background: {BORDER_DEFAULT};
    border-radius: 3px;
}}
QScrollBar::handle:horizontal:hover {{
    background: {TEXT_FAINT};
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}

/* ── panels ── */
QWidget#leftPanel {{
    background: {BG_ELEVATED};
    border-right: 1px solid {BORDER_DEFAULT};
}}
QWidget#centerPanel {{
    background: {BG_BASE};
}}
QWidget#rightPanel {{
    background: {BG_ELEVATED};
    border-left: 1px solid {BORDER_DEFAULT};
}}

/* ── section / group labels ── */
QLabel#groupLabel {{
    color: {TEXT_MUTED};
    font-family: {FONT_MONO_STACK};
    font-size: 9px;
    letter-spacing: 0.10em;
    padding: 8px 14px 6px;
    border-bottom: 1px solid {BORDER_SUBTLE};
    background: transparent;
}}
QLabel#sectionHeader {{
    color: {TEXT_MUTED};
    font-family: {FONT_MONO_STACK};
    font-size: 9px;
    letter-spacing: 0.10em;
    padding: 8px 0 6px;
    border-bottom: 1px solid {BORDER_SUBTLE};
    background: transparent;
}}

/* ── left project items ── */
QWidget#projItem {{
    background: transparent;
    border-left: 2px solid transparent;
    border-bottom: 1px solid {BORDER_SUBTLE};
}}
QWidget#projItem:hover {{
    background: {BG_CONTROL};
}}
QLabel#projName {{
    color: {TEXT_PRIMARY};
    font-family: {FONT_SANS_STACK};
    font-size: 12px;
    background: transparent;
}}
QLabel#projMeta {{
    color: {TEXT_MUTED};
    font-family: {FONT_MONO_STACK};
    font-size: 9px;
    background: transparent;
}}
QLabel#projNameDim {{
    color: {TEXT_FAINT};
    font-family: {FONT_SANS_STACK};
    font-size: 12px;
    background: transparent;
}}
QLabel#projMetaDim {{
    color: #3a3a3c;
    font-family: {FONT_MONO_STACK};
    font-size: 9px;
    background: transparent;
}}

/* ── left footer buttons ── */
QPushButton#lfBtn {{
    background: {BG_CONTROL};
    border: 1px solid {BORDER_DEFAULT};
    border-radius: 4px;
    color: {TEXT_SECONDARY};
    font-family: {FONT_MONO_STACK};
    font-size: 10px;
    padding: 6px 10px;
}}
QPushButton#lfBtn:hover {{
    background: {BORDER_DEFAULT};
    color: {TEXT_PRIMARY};
}}

/* ── large project name card ── */
QLabel#cardName {{
    color: {TEXT_PRIMARY};
    font-family: {FONT_SANS_STACK};
    font-size: 16px;
    font-weight: 600;
    background: transparent;
}}
QLabel#cardMeta {{
    color: {TEXT_SECONDARY};
    font-family: {FONT_MONO_STACK};
    font-size: 9px;
    letter-spacing: 0.04em;
    background: transparent;
}}

/* ── stat cells ── */
QWidget#statCell {{
    background: {BG_ELEVATED};
    border: 1px solid {BORDER_SUBTLE};
    border-radius: 3px;
}}
QLabel#statVal {{
    color: {TEXT_PRIMARY};
    font-family: {FONT_MONO_STACK};
    font-size: 15px;
    font-weight: 500;
    background: transparent;
}}
QLabel#statKey {{
    color: {TEXT_MUTED};
    font-family: {FONT_MONO_STACK};
    font-size: 9px;
    letter-spacing: 0.06em;
    background: transparent;
}}

/* ── readiness rows ── */
QLabel#riIcon {{
    font-size: 12px;
    min-width: 16px;
    background: transparent;
}}
QLabel#riLabel {{
    color: {TEXT_PRIMARY};
    font-family: {FONT_SANS_STACK};
    font-size: 12px;
    background: transparent;
}}
QLabel#riLabelWarn {{
    color: {ORANGE};
    font-family: {FONT_SANS_STACK};
    font-size: 12px;
    background: transparent;
}}
QLabel#riDetail {{
    color: {TEXT_SECONDARY};
    font-family: {FONT_MONO_STACK};
    font-size: 10px;
    background: transparent;
}}

/* ── asset table ── */
QLabel#assetGroupLabel {{
    color: {TEXT_MUTED};
    font-family: {FONT_MONO_STACK};
    font-size: 9px;
    letter-spacing: 0.08em;
    padding: 6px 0 2px 0;
    background: transparent;
}}
QLabel#assetRow {{
    color: {TEXT_PRIMARY};
    font-family: {FONT_SANS_STACK};
    font-size: 11px;
    background: transparent;
}}
QLabel#assetRowMuted {{
    color: {TEXT_FAINT};
    font-family: {FONT_SANS_STACK};
    font-size: 11px;
    background: transparent;
}}

/* ── right panel labels ── */
QLabel#rpLabel {{
    color: {TEXT_MUTED};
    font-family: {FONT_MONO_STACK};
    font-size: 9px;
    letter-spacing: 0.10em;
    padding: 8px 0 6px;
    border-bottom: 1px solid {BORDER_SUBTLE};
    background: transparent;
}}
QLabel#rpValue {{
    color: {TEXT_PRIMARY};
    font-family: {FONT_MONO_STACK};
    font-size: 11px;
    background: transparent;
}}
QLabel#pathLabel {{
    background: {BG_ELEVATED};
    border: 1px solid {BORDER_DEFAULT};
    border-radius: 3px;
    color: {TEXT_SECONDARY};
    font-family: {FONT_MONO_STACK};
    font-size: 10px;
    padding: 5px 9px;
}}

/* ── include list rows ── */
QLabel#includeOk {{
    color: {GREEN};
    font-family: {FONT_MONO_STACK};
    font-size: 10px;
    background: transparent;
    padding: 2px 0;
}}
QLabel#includeWarn {{
    color: {ORANGE};
    font-family: {FONT_MONO_STACK};
    font-size: 10px;
    background: transparent;
    padding: 2px 0;
}}
QLabel#includeMuted {{
    color: {TEXT_MUTED};
    font-family: {FONT_MONO_STACK};
    font-size: 10px;
    background: transparent;
    padding: 2px 0;
}}

/* ── collect button (primary CTA) ── */
QPushButton#collectBtn {{
    background: {ACCENT};
    border: none;
    border-radius: 5px;
    color: {BG_BASE};
    font-family: {FONT_SANS_STACK};
    font-size: 13px;
    font-weight: 700;
    padding: 11px;
    letter-spacing: 0.02em;
}}
QPushButton#collectBtn:hover {{
    background: #b8adff;
}}
QPushButton#collectBtn:disabled {{
    background: {BG_CONTROL};
    color: {TEXT_FAINT};
    border: 1px solid {BORDER_DEFAULT};
}}

/* ── secondary buttons ── */
QPushButton#secondaryBtn {{
    background: {BG_CONTROL};
    border: 1px solid {BORDER_DEFAULT};
    border-radius: 4px;
    color: {TEXT_SECONDARY};
    font-family: {FONT_MONO_STACK};
    font-size: 10px;
    padding: 7px 12px;
}}
QPushButton#secondaryBtn:hover {{
    background: {BORDER_DEFAULT};
    color: {TEXT_PRIMARY};
}}
QPushButton#secondaryBtn:disabled {{
    color: {BORDER_DEFAULT};
    border-color: {BORDER_SUBTLE};
}}

/* ── output tree ── */
QLabel#treeDisplay {{
    background: {BG_DEEP};
    border: 1px solid {BORDER_SUBTLE};
    border-radius: 4px;
    color: {TEXT_MUTED};
    font-family: {FONT_MONO_STACK};
    font-size: 11px;
    padding: 8px;
}}

/* ── onboarding empty state ── */
QLabel#onboardHeadline {{
    color: {TEXT_PRIMARY};
    font-family: {FONT_SANS_STACK};
    font-size: 17px;
    font-weight: 600;
    background: transparent;
}}
QLabel#onboardSubtext {{
    color: {TEXT_MUTED};
    font-family: {FONT_MONO_STACK};
    font-size: 12px;
    background: transparent;
}}
QLabel#onboardHelper {{
    color: {TEXT_MUTED};
    font-family: {FONT_MONO_STACK};
    font-size: 11px;
    background: transparent;
}}

/* ── modal dialogs ── */
QDialog {{
    background: {BG_ELEVATED};
}}

/* ── status bar ── */
QStatusBar {{
    background: {BG_CONTROL};
    border-top: 1px solid {BORDER_DEFAULT};
    color: {TEXT_SECONDARY};
    font-family: {FONT_MONO_STACK};
    font-size: 10px;
    padding: 0 14px;
}}

/* ── progress bar ── */
QProgressBar {{
    background: {BG_DEEP};
    border: 1px solid {BORDER_DEFAULT};
    border-radius: 3px;
    height: 4px;
    text-align: center;
}}
QProgressBar::chunk {{
    background: {ACCENT};
    border-radius: 3px;
}}

/* ── badges ── */
QLabel#badgeOk {{
    background: {GREEN};
    border-radius: 3px;
    color: {BG_BASE};
    font-family: {FONT_MONO_STACK};
    font-size: 9px;
    font-weight: 700;
    letter-spacing: 0.06em;
    padding: 1px 6px;
}}
QLabel#badgeWarn {{
    background: {ORANGE};
    border-radius: 3px;
    color: {BG_BASE};
    font-family: {FONT_MONO_STACK};
    font-size: 9px;
    font-weight: 700;
    letter-spacing: 0.06em;
    padding: 1px 6px;
}}
QLabel#badgeError {{
    background: {RED};
    border-radius: 3px;
    color: white;
    font-family: {FONT_MONO_STACK};
    font-size: 9px;
    font-weight: 700;
    letter-spacing: 0.06em;
    padding: 1px 6px;
}}
QLabel#badgeDim {{
    background: {TEXT_FAINT};
    border-radius: 3px;
    color: {BG_BASE};
    font-family: {FONT_MONO_STACK};
    font-size: 9px;
    font-weight: 700;
    letter-spacing: 0.06em;
    padding: 1px 6px;
}}

/* ── dividers ── */
QFrame#divider {{
    background: {BORDER_DEFAULT};
    max-height: 1px;
    border: none;
}}
"""
