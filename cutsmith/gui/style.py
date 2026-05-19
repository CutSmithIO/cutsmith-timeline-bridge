"""QSS stylesheet tokens and builder for the CutSmith GUI."""

# ─── colour tokens ────────────────────────────────────────────────────────────
BG_BASE     = "#1c1c1e"
BG_RAISED   = "#242426"
BG_HOVER    = "#2c2c2e"
BORDER      = "#3a3a3c"
BORDER_FAINT = "#2c2c2e"

ACCENT_DARK = "#5a4fcf"
ACCENT      = "#9b8cff"
ACCENT_DIM  = "#3d3570"

GREEN       = "#30d158"
ORANGE      = "#ff9f0a"
RED         = "#ff453a"

TEXT_PRIMARY = "#e5e5ea"
TEXT_MUTED   = "#636366"
TEXT_FAINT   = "#48484a"

FONT_MONO = "IBM Plex Mono, Menlo, Monaco, Courier New, monospace"
FONT_SANS = "SF Pro Display, -apple-system, Helvetica Neue, Arial, sans-serif"

# ─── full QSS ─────────────────────────────────────────────────────────────────
APP_QSS = f"""
QMainWindow, QWidget#root {{
    background: {BG_BASE};
    color: {TEXT_PRIMARY};
    font-family: {FONT_MONO};
    font-size: 12px;
}}

/* ── scrollbars ── */
QScrollBar:vertical {{
    background: {BG_BASE};
    width: 6px;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background: {BORDER};
    border-radius: 3px;
    min-height: 20px;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar:horizontal {{ height: 6px; background: {BG_BASE}; }}
QScrollBar::handle:horizontal {{ background: {BORDER}; border-radius: 3px; }}
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

/* ── group labels ── */
QLabel#groupLabel {{
    color: {TEXT_MUTED};
    font-size: 10px;
    font-family: {FONT_MONO};
    letter-spacing: 0.08em;
    padding: 4px 12px 2px 12px;
}}

/* ── project list items ── */
QPushButton#projItem {{
    background: transparent;
    border: none;
    border-left: 2px solid transparent;
    color: {TEXT_PRIMARY};
    font-family: {FONT_MONO};
    font-size: 12px;
    padding: 6px 12px;
    text-align: left;
}}
QPushButton#projItem:hover {{
    background: {BG_HOVER};
}}
QPushButton#projItem[selected="true"] {{
    background: {ACCENT_DIM};
    border-left: 2px solid {ACCENT};
}}

/* ── left footer buttons ── */
QPushButton#lfBtn {{
    background: transparent;
    border: 1px solid {BORDER};
    border-radius: 4px;
    color: {TEXT_MUTED};
    font-family: {FONT_MONO};
    font-size: 11px;
    padding: 4px 10px;
}}
QPushButton#lfBtn:hover {{
    background: {BG_HOVER};
    color: {TEXT_PRIMARY};
}}

/* ── section headers in center panel ── */
QLabel#sectionHeader {{
    color: {TEXT_MUTED};
    font-size: 10px;
    letter-spacing: 0.08em;
    padding: 8px 0 4px 0;
}}

/* ── large project name card ── */
QLabel#cardName {{
    color: {TEXT_PRIMARY};
    font-family: {FONT_SANS};
    font-size: 22px;
    font-weight: 700;
}}
QLabel#cardMeta {{
    color: {TEXT_MUTED};
    font-size: 11px;
}}

/* ── readiness items ── */
QLabel#riIcon {{
    font-size: 12px;
    min-width: 16px;
}}
QLabel#riLabel {{
    color: {TEXT_PRIMARY};
    font-size: 12px;
}}
QLabel#riLabelWarn {{
    color: {ORANGE};
    font-size: 12px;
}}
QLabel#riDetail {{
    color: {TEXT_MUTED};
    font-size: 11px;
}}

/* ── asset table ── */
QLabel#assetGroupLabel {{
    color: {TEXT_FAINT};
    font-size: 10px;
    letter-spacing: 0.08em;
    padding: 6px 0 2px 0;
}}
QLabel#assetRow {{
    color: {TEXT_PRIMARY};
    font-size: 11px;
}}
QLabel#assetRowMuted {{
    color: {TEXT_MUTED};
    font-size: 11px;
}}

/* ── stat cells ── */
QLabel#statVal {{
    color: {TEXT_PRIMARY};
    font-size: 16px;
    font-weight: 600;
}}
QLabel#statKey {{
    color: {TEXT_MUTED};
    font-size: 10px;
}}

/* ── right panel labels ── */
QLabel#rpLabel {{
    color: {TEXT_MUTED};
    font-size: 10px;
    letter-spacing: 0.05em;
    padding-bottom: 2px;
}}
QLabel#rpValue {{
    color: {TEXT_PRIMARY};
    font-size: 11px;
}}

/* ── path display ── */
QLabel#pathLabel {{
    background: {BG_BASE};
    border: 1px solid {BORDER};
    border-radius: 4px;
    color: {TEXT_MUTED};
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
    color: {TEXT_PRIMARY};
    font-size: 11px;
    padding: 6px 10px;
}}
QPushButton#secondaryBtn:hover {{
    background: {BG_HOVER};
}}
QPushButton#secondaryBtn:disabled {{
    color: {TEXT_FAINT};
}}

/* ── output tree ── */
QLabel#treeDisplay {{
    background: {BG_BASE};
    border: 1px solid {BORDER_FAINT};
    border-radius: 4px;
    color: {TEXT_MUTED};
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
    background: {BG_BASE};
    border: 1px solid {BORDER};
    border-radius: 3px;
    height: 4px;
    text-align: center;
}}
QProgressBar::chunk {{
    background: {ACCENT};
    border-radius: 3px;
}}

/* ── badge labels ── */
QLabel#badgeOk {{
    background: {GREEN};
    border-radius: 3px;
    color: {BG_BASE};
    font-size: 9px;
    font-weight: 700;
    letter-spacing: 0.06em;
    padding: 1px 5px;
}}
QLabel#badgeWarn {{
    background: {ORANGE};
    border-radius: 3px;
    color: {BG_BASE};
    font-size: 9px;
    font-weight: 700;
    letter-spacing: 0.06em;
    padding: 1px 5px;
}}
QLabel#badgeError {{
    background: {RED};
    border-radius: 3px;
    color: white;
    font-size: 9px;
    font-weight: 700;
    letter-spacing: 0.06em;
    padding: 1px 5px;
}}
QLabel#badgeDim {{
    background: {TEXT_FAINT};
    border-radius: 3px;
    color: {BG_BASE};
    font-size: 9px;
    font-weight: 700;
    letter-spacing: 0.06em;
    padding: 1px 5px;
}}

/* ── dividers ── */
QFrame#divider {{
    background: {BORDER};
    max-height: 1px;
}}
"""
