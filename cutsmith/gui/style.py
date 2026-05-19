"""QSS stylesheet tokens and builder for the CutSmith GUI."""

# ─── colour tokens ────────────────────────────────────────────────────────────
BG_BASE      = "#1c1c1e"
BG_RAISED    = "#242426"
BG_HOVER     = "#2c2c2e"
BG_DEEP      = "#161618"
BORDER       = "#3a3a3c"
BORDER_FAINT = "#2c2c2e"

ACCENT_DARK  = "#5a4fcf"
ACCENT       = "#9b8cff"
ACCENT_DIM   = "#3d3570"
ACCENT_SEL   = "rgba(155, 140, 255, 0.18)"

GREEN        = "#30d158"
ORANGE       = "#ff9f0a"
RED          = "#ff453a"

TEXT_PRIMARY   = "#e5e5ea"
TEXT_SECONDARY = "#98989f"
TEXT_MUTED     = "#636366"
TEXT_FAINT     = "#48484a"

FONT_MONO = "\"IBM Plex Mono\", Menlo, Monaco, \"Courier New\", monospace"
FONT_SANS = "\"-apple-system\", \"Helvetica Neue\", Arial, sans-serif"

# ─── full QSS ─────────────────────────────────────────────────────────────────
APP_QSS = f"""
/* ── reset: stop Qt white from bleeding through ── */
QWidget {{
    background: transparent;
    color: {TEXT_PRIMARY};
    font-family: {FONT_MONO};
    font-size: 12px;
}}

QMainWindow {{
    background: {BG_BASE};
}}

QWidget#root {{
    background: {BG_BASE};
}}

/* Scroll areas: force dark on both the QScrollArea frame and its internal viewport */
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
    background: {BORDER};
    border-radius: 3px;
    min-height: 20px;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar:horizontal {{
    height: 6px;
    background: {BG_BASE};
    border: none;
}}
QScrollBar::handle:horizontal {{
    background: {BORDER};
    border-radius: 3px;
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}

/* ── panels ── */
QWidget#leftPanel {{
    background: {BG_RAISED};
    border-right: 1px solid {BORDER};
}}
QWidget#centerPanel {{
    background: {BG_BASE};
}}
QWidget#rightPanel {{
    background: {BG_RAISED};
    border-left: 1px solid {BORDER};
}}

/* ── group / section labels ── */
QLabel#groupLabel {{
    color: {TEXT_MUTED};
    font-size: 10px;
    letter-spacing: 0.08em;
    background: transparent;
}}
QLabel#sectionHeader {{
    color: {TEXT_SECONDARY};
    font-size: 10px;
    letter-spacing: 0.08em;
    padding: 8px 0 4px 0;
    background: transparent;
}}

/* ── left project items (QWidget-based, styled inline) ── */
QWidget#projItem {{
    background: transparent;
    border-left: 2px solid transparent;
}}
QWidget#projItem:hover {{
    background: {BG_HOVER};
}}
QWidget#projItem[selected="true"] {{
    background: {ACCENT_SEL};
    border-left: 2px solid {ACCENT};
}}
QLabel#projName {{
    color: {TEXT_PRIMARY};
    font-size: 12px;
    background: transparent;
}}
QLabel#projMeta {{
    color: {TEXT_MUTED};
    font-size: 10px;
    background: transparent;
}}
QLabel#projNameDim {{
    color: {TEXT_FAINT};
    font-size: 12px;
    background: transparent;
}}
QLabel#projMetaDim {{
    color: {TEXT_FAINT};
    font-size: 10px;
    background: transparent;
}}

/* ── left footer buttons ── */
QPushButton#lfBtn {{
    background: transparent;
    border: 1px solid {BORDER};
    border-radius: 4px;
    color: {TEXT_SECONDARY};
    font-size: 11px;
    padding: 4px 10px;
}}
QPushButton#lfBtn:hover {{
    background: {BG_HOVER};
    color: {TEXT_PRIMARY};
}}

/* ── large project name card ── */
QLabel#cardName {{
    color: {TEXT_PRIMARY};
    font-family: {FONT_SANS};
    font-size: 20px;
    font-weight: 700;
    background: transparent;
}}
QLabel#cardMeta {{
    color: {TEXT_SECONDARY};
    font-size: 11px;
    background: transparent;
}}

/* ── readiness items ── */
QLabel#riIcon {{
    font-size: 12px;
    min-width: 16px;
    background: transparent;
}}
QLabel#riLabel {{
    color: {TEXT_PRIMARY};
    font-size: 12px;
    background: transparent;
}}
QLabel#riLabelWarn {{
    color: {ORANGE};
    font-size: 12px;
    background: transparent;
}}
QLabel#riDetail {{
    color: {TEXT_SECONDARY};
    font-size: 11px;
    background: transparent;
}}

/* ── asset table ── */
QLabel#assetGroupLabel {{
    color: {TEXT_MUTED};
    font-size: 10px;
    letter-spacing: 0.08em;
    padding: 6px 0 2px 0;
    background: transparent;
}}
QLabel#assetRow {{
    color: {TEXT_PRIMARY};
    font-size: 11px;
    background: transparent;
}}
QLabel#assetRowMuted {{
    color: {TEXT_MUTED};
    font-size: 11px;
    background: transparent;
}}

/* ── stat cells ── */
QLabel#statVal {{
    color: {TEXT_PRIMARY};
    font-size: 16px;
    font-weight: 600;
    background: transparent;
}}
QLabel#statKey {{
    color: {TEXT_MUTED};
    font-size: 9px;
    background: transparent;
}}

/* ── right panel ── */
QLabel#rpLabel {{
    color: {TEXT_MUTED};
    font-size: 10px;
    letter-spacing: 0.05em;
    padding-bottom: 2px;
    background: transparent;
}}
QLabel#rpValue {{
    color: {TEXT_PRIMARY};
    font-size: 11px;
    background: transparent;
}}
QLabel#pathLabel {{
    background: {BG_DEEP};
    border: 1px solid {BORDER};
    border-radius: 4px;
    color: {TEXT_SECONDARY};
    font-size: 10px;
    padding: 4px 8px;
}}

/* ── collect button ── */
QPushButton#collectBtn {{
    background: {ACCENT_DARK};
    border: none;
    border-radius: 6px;
    color: white;
    font-family: {FONT_SANS};
    font-size: 14px;
    font-weight: 600;
    padding: 12px 0;
}}
QPushButton#collectBtn:hover {{
    background: {ACCENT};
}}
QPushButton#collectBtn:disabled {{
    background: {ACCENT_DIM};
    color: {TEXT_FAINT};
}}

/* ── secondary buttons ── */
QPushButton#secondaryBtn {{
    background: transparent;
    border: 1px solid {BORDER};
    border-radius: 4px;
    color: {TEXT_SECONDARY};
    font-size: 11px;
    padding: 6px 10px;
}}
QPushButton#secondaryBtn:hover {{
    background: {BG_HOVER};
    color: {TEXT_PRIMARY};
}}
QPushButton#secondaryBtn:disabled {{
    color: {TEXT_FAINT};
    border-color: {BORDER_FAINT};
}}

/* ── output tree ── */
QLabel#treeDisplay {{
    background: {BG_DEEP};
    border: 1px solid {BORDER_FAINT};
    border-radius: 4px;
    color: {TEXT_SECONDARY};
    font-size: 10px;
    padding: 8px;
}}

/* ── status bar ── */
QStatusBar {{
    background: {BG_RAISED};
    border-top: 1px solid {BORDER};
    color: {TEXT_MUTED};
    font-size: 10px;
}}

/* ── progress bar ── */
QProgressBar {{
    background: {BG_DEEP};
    border: 1px solid {BORDER};
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
    font-size: 9px;
    font-weight: 700;
    letter-spacing: 0.06em;
    padding: 1px 6px;
}}
QLabel#badgeWarn {{
    background: {ORANGE};
    border-radius: 3px;
    color: {BG_BASE};
    font-size: 9px;
    font-weight: 700;
    letter-spacing: 0.06em;
    padding: 1px 6px;
}}
QLabel#badgeError {{
    background: {RED};
    border-radius: 3px;
    color: white;
    font-size: 9px;
    font-weight: 700;
    letter-spacing: 0.06em;
    padding: 1px 6px;
}}
QLabel#badgeDim {{
    background: {TEXT_FAINT};
    border-radius: 3px;
    color: {BG_BASE};
    font-size: 9px;
    font-weight: 700;
    letter-spacing: 0.06em;
    padding: 1px 6px;
}}

/* ── dividers ── */
QFrame#divider {{
    background: {BORDER};
    max-height: 1px;
    border: none;
}}
"""
