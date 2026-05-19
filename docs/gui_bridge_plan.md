# CutSmith Timeline Bridge — GUI Implementation Plan

**Current prototype**: `docs/gui_prototype_bridge_v2.html`  
**Previous prototype**: `docs/gui_prototype_bridge.html` (v1, archived)  
**Target framework**: PySide6 (Qt 6.x)  
**Positioning**: Project Handoff Assistant — not a player, not an editor.

---

## UX Flow (v2 — decision-first)

The UI answers these questions in order, left to right, top to bottom:

```
1. Which project am I exporting?     → left project list (selected row)
2. Is it safe / portable?            → center card: portability badge
3. What WILL migrate?                → center: readiness checklist ✓ items
4. What will NOT migrate?            → center: readiness checklist ⚠ items
5. Where does the package go?        → right: output path + tree preview
6. What do I click?                  → right: big purple Collect button
```

Key shift from v1: **decision-flow over database-report.**  
The readiness checklist is the primary information surface.  
The asset category table is secondary reference.  
The Collect button is visually dominant — not buried after warnings.

---

## 1. Component Map (v2)

```
MainWindow (QMainWindow, 980×730)
├── TitleBar         custom macOS traffic-light style, 36px
└── BodyWidget (QFrame)
    └── BodyLayout (QHBoxLayout, spacing=0, margins=0)
        ├── ProjectDiscoveryPanel    216px fixed
        ├── ProjectReadinessPanel    flex (QSizePolicy.Expanding)
        └── ExportDecisionPanel      272px fixed
```

### ProjectDiscoveryPanel (left, 216px)

```
ProjectDiscoveryPanel
├── BrandHeader (QFrame, fixed)
│   ├── AppNameLabel        "CutSmith Bridge"        13px sans bold
│   └── VersionLabel        "v0.3.6-alpha · …"       9px mono muted
├── SearchFilter (QLineEdit, fixed)
├── ProjectScrollArea (QScrollArea, flex)
│   └── ProjectListWidget (QWidget + QVBoxLayout)
│       ├── GroupLabel      "CAPCUT PROJECTS"         sticky
│       ├── ProjectItem × N (custom QFrame)
│       │   ├── StatusDot (QLabel, CSS border-radius)
│       │   ├── InfoStack (QVBoxLayout)
│       │   │   ├── ProjectNameLabel   10px semi-bold
│       │   │   └── MetaLabel          9px muted "CapCut Desktop · date"
│       │   └── BadgeLabel            8px colored pill
│       ├── GroupLabel      "JIANYING PROJECTS"
│       ├── (EmptyStateLabel if none)
│       ├── GroupLabel      "ENCRYPTED / UNSUPPORTED"
│       └── ProjectItem(disabled) × N
└── FooterRow (QFrame, fixed)
    ├── AddFolderButton     "+ Add Folder…"   secondary style
    └── RescanButton        "↺ Rescan"        secondary style
```

**ProjectItem states:**
- `ready`: green dot · "ready" badge
- `warn`: orange dot (pulsing) · "N warn" badge
- `encrypted`: red dot · "encrypted" badge · `setEnabled(False)`
- `selected`: purple left border + tinted background

### ProjectReadinessPanel (center, stretch)

```
ProjectReadinessPanel
├── ProjectCard (QFrame, fixed height ~96px)
│   ├── CardTopRow (QHBoxLayout)
│   │   ├── CardLeft (QVBoxLayout)
│   │   │   ├── ProjectNameLabel   20px sans bold    e.g. "0519V"
│   │   │   └── AppDetailLabel     9px mono muted
│   │   └── PortabilityBadge       colored pill
│   └── QuickStatsGrid (QGridLayout, 4 cols)
│       └── StatCard (QFrame) × 4
│           ├── KeyLabel     8px faint
│           └── ValueLabel   11px
│
├── ReadinessSection (QFrame, fixed height)
│   ├── SectionHeader (QHBoxLayout)
│   │   ├── SectionLabel   "PROJECT READINESS"
│   │   └── ScoreLabel     "5 migrated · 2 report-only"
│   └── ChecklistWidget (QWidget + QVBoxLayout)
│       └── ReadinessItem (QFrame) × N
│           ├── IconLabel   "✓" (green) or "⚠" (orange)
│           ├── FeatureLabel  10px primary or orange
│           └── DetailLabel   9px faint, right-aligned
│
├── AssetSection (QScrollArea, flex)
│   ├── AssetSectionHeader (sticky)
│   └── AssetGroupedList
│       ├── GroupDivider    "FULLY MIGRATED"
│       ├── AssetRow × N
│       ├── GroupDivider    "INCLUDED WITH WARNING"
│       ├── AssetRow × N
│       ├── GroupDivider    "REPORT-ONLY · NOT PORTABLE"
│       └── AssetRow × N
│           Each row: dot · name · count · portability status
│
└── CenterStatusBar (QFrame, fixed)
    ├── SchemaLabel
    └── SizeLabel
```

**ReadinessItem checklist (always rendered in this order):**
1. Timeline structure
2. Media package
3. Source items (master clip reconstruction)
4. Constant speed
5. Subtitle export
6. Speed curves (⚠ if any curve_speed segments)
7. Stickers / effects (⚠ if any proprietary assets)

Items 1–5 are always ✓ for supported plaintext projects.  
Items 6–7 conditionally ✓ or ⚠ based on IR inspection.

### ExportDecisionPanel (right, 272px)

```
ExportDecisionPanel
├── PanelHeader (QFrame, fixed)
│   ├── TitleLabel         "Export Decision"
│   └── EncryptionBadge    "PLAINTEXT" / "ENCRYPTED"
│
├── OutputConfigSection (QFrame, fixed)
│   ├── LabelRow
│   │   ├── OutputLabel    "OUTPUT FOLDER"
│   │   └── ChangeButton   small text link
│   ├── PathLabel          monospace, word-wrap
│   └── NLERow
│       ├── NLELabel       "TARGET NLE"
│       └── NLESelector    QComboBox
│
├── CollectButton (QPushButton, full-width, purple)
│   "Collect Premiere Package"
│   subtitle: "XML · media/ · relink guide · report · SRT"
│
├── PackageContentsSection (QFrame, fixed)
│   ├── SectionLabel       "THIS PACKAGE WILL INCLUDE"
│   └── PackageItem × 7
│       ├── CheckIcon      "✓" green
│       ├── FileNameLabel
│       └── SubLabel       muted hint
│
├── OutputTreeSection (QFrame, fixed)
│   ├── SectionLabel       "OUTPUT PREVIEW"
│   └── TreeDisplay        QLabel, monospace, white-space pre
│                          ├── XML highlighted in accent
│                          └── dirs / files muted
│
├── SecondaryButtonRow (QFrame, fixed)
│   ├── XMLOnlyButton
│   ├── ExportSRTButton
│   └── OpenOutputButton
│
├── MigrationNotesSection (QFrame, fixed)
│   ├── SectionLabel       "MIGRATION NOTES"
│   └── NoteItem × N
│       ├── ColorDot        orange / muted
│       └── NoteText        word-wrap
│
└── LicensingFooter (QLabel, very muted, 8px)
```

**ExportDecisionPanel state machine:**
```
EMPTY          → no project selected; Collect button disabled
ANALYZING      → AnalyzeWorker running; button shows "Analyzing…"
READY          → checklist populated; button enabled; tree shows predicted output
COLLECTING     → CollectWorker running; button shows "Collecting…"; spinner
DONE           → button shows "✓ Done"; OpenOutput enabled; tree shows actual files
ERROR          → button re-enabled; error message shown above notes
ENCRYPTED      → all buttons except secondary disabled; badge red; explain in notes
```

---

## 2. PySide6 File Layout

```
cutsmith/
└── gui/
    ├── __init__.py
    ├── main.py                ← python -m cutsmith.gui entry point
    ├── main_window.py         ← MainWindow(QMainWindow)
    ├── panels/
    │   ├── __init__.py
    │   ├── project_panel.py   ← ProjectDiscoveryPanel
    │   ├── readiness_panel.py ← ProjectReadinessPanel (renamed from migration_panel)
    │   └── export_panel.py    ← ExportDecisionPanel (renamed from inspector_panel)
    ├── widgets/
    │   ├── __init__.py
    │   ├── project_item.py    ← custom list row (dot + info + badge)
    │   ├── readiness_item.py  ← one checklist row (icon + label + detail)
    │   ├── stat_card.py       ← metadata cell (key + value)
    │   ├── asset_row.py       ← asset category row
    │   ├── note_item.py       ← migration note row (dot + text)
    │   └── badge.py           ← colored pill label
    ├── workers/
    │   ├── __init__.py
    │   ├── scan_worker.py     ← QThread: discover + detect projects
    │   ├── analyze_worker.py  ← QThread: detect + scan_assets + read_draft IR
    │   ├── collect_worker.py  ← QThread: collect() pipeline
    │   └── srt_worker.py      ← QThread: export_srt()
    └── style.py               ← QSS constants
```

### style.py — color token system

```python
# All tokens match the HTML prototype CSS exactly.
BG_BASE       = "#1c1c1e"
BG_RAISED     = "#242426"
BG_SURFACE    = "#2c2c2e"
BG_DEEP       = "#161618"
BORDER        = "#3a3a3c"
BORDER_SUB    = "#2c2c2e"
BORDER_FAINT  = "#222224"
ACCENT        = "#9b8cff"
ACCENT_DARK   = "#5a4fcf"
ACCENT_HOVER  = "#6b60e0"
TEXT_PRIMARY  = "#e5e5ea"
TEXT_SECONDARY= "#98989f"
TEXT_MUTED    = "#636366"
TEXT_FAINT    = "#48484a"
TEXT_DEEP     = "#3a3a3c"
TEXT_GHOST    = "#2c2c2e"
GREEN         = "#30d158"
ORANGE        = "#ff9f0a"
RED           = "#ff453a"
FONT_MONO     = "IBM Plex Mono, SF Mono, Consolas, monospace"
FONT_SANS     = "IBM Plex Sans, SF Pro Display, Helvetica Neue, sans-serif"

# Named style roles for QSS generation
def panel_border() -> str:
    return f"border-right: 1px solid {BORDER};"
def section_label_style() -> str:
    return f"font-size: 9px; color: {TEXT_MUTED}; letter-spacing: 0.1em;"
def primary_button_style() -> str:
    return (f"background: {ACCENT_DARK}; color: white; border: none; "
            f"font-size: 13px; font-weight: 600; padding: 13px 16px;")
```

### Threading model

```
Main Thread (Qt event loop)
│
├── ScanWorker (QThread)
│   Input:  list[Path]  — CapCut / Jianying project root dirs
│   Steps:  detect_project(path) on each dir concurrently
│   Signals:
│     project_found(DetectResult)   → ProjectDiscoveryPanel adds item
│     finished(int)                 → "N projects · M encrypted" in log
│
├── AnalyzeWorker (QThread)
│   Input:  Path  — selected project root
│   Steps:  detect_project() + scan_assets() + read_draft()
│   Output: AnalysisResult (see Data Bindings)
│   Signals:
│     finished(AnalysisResult)      → ReadinessPanel.populate()
│                                   → ExportPanel.populate()
│     error(str)                    → ExportPanel.show_error()
│
├── CollectWorker (QThread)
│   Input:  Path project, Path out_dir, list[Path] search_roots
│   Steps:  collect() full pipeline
│   Output: CollectResult
│   Signals:
│     progress(str)                 → center status bar text
│     finished(CollectResult)       → ExportPanel.on_collect_done()
│     error(str)                    → ExportPanel.show_error()
│
└── SRTWorker (QThread)
    Input:  Path project, Path out_path
    Steps:  export_srt()
    Signals:
      finished(Path)                → ExportPanel.on_srt_done()
      error(str)                    → ExportPanel.show_error()
```

### Signal / slot wiring

```python
# MainWindow.__init__
project_panel.project_selected.connect(self._on_project_selected)
project_panel.add_folder_requested.connect(self._browse_add_folder)
project_panel.rescan_requested.connect(self._start_scan)

export_panel.collect_requested.connect(self._start_collect)
export_panel.srt_requested.connect(self._start_srt)
export_panel.xml_only_requested.connect(self._start_xml_only)
export_panel.open_output_requested.connect(self._open_output)
export_panel.change_output_requested.connect(self._browse_output_dir)

# MainWindow._on_project_selected
self._analyze_worker = AnalyzeWorker(path)
self._analyze_worker.finished.connect(readiness_panel.populate)
self._analyze_worker.finished.connect(export_panel.populate)
self._analyze_worker.error.connect(export_panel.show_error)
self._analyze_worker.start()
```

### CapCut project discovery

```python
CAPCUT_ROOTS_MACOS = [
    "~/Library/Containers/com.lemon.lvmediapro/Data/Library"
    "/Application Support/LVMediaProSandBox/UserData/draft",
    "~/Movies/JianyingPro/User Data/Projects/com.lveditor.draft",
]
CAPCUT_ROOTS_WIN = [
    "~/AppData/Local/CapCut/User Data/Projects/com.lveditor.draft",
    "~/AppData/Local/JianyingPro/User Data/Projects/com.lveditor.draft",
]
```

ScanWorker walks each root, finds subdirs with `draft_info.json`,
calls `detect_project()` on each, emits `project_found` per result.
Encrypted results placed in the "ENCRYPTED / UNSUPPORTED" group.

### Collect button state machine (PySide6 implementation)

```python
class CollectButton(QPushButton):
    def set_ready(self):
        self.setText("Collect Premiere Package")
        self.setEnabled(True)
        self.setStyleSheet(primary_button_style())

    def set_running(self):
        self.setText("Collecting…")
        self.setEnabled(False)

    def set_done(self):
        self.setText("✓ Package Ready")
        self.setEnabled(True)  # click = open output

    def set_error(self, msg: str):
        self.setText("Collect Premiere Package")
        self.setEnabled(True)

    def set_encrypted(self):
        self.setText("Encrypted — handoff not available")
        self.setEnabled(False)
        self.setStyleSheet("background: #2c2c2e; color: #48484a; …")
```

---

## 3. Data Bindings — Core → GUI

### AnalysisResult dataclass (new; wraps core outputs)

```python
@dataclass
class AnalysisResult:
    # from detect_project()
    detect: DetectResult

    # from scan_assets()
    manifest: AssetManifest

    # derived from read_draft() IR
    duration_us: int
    canvas_w: int
    canvas_h: int
    fps: float
    video_track_count: int
    audio_track_count: int
    clip_count: int
    speed_clip_count: int         # segments where speed != 1.0 and curve_speed is None
    speed_curve_count: int        # segments where curve_speed is not None
    subtitle_cue_count: int       # from scan or export-srt dry-run

    # portability summary
    total_online: int
    total_offline: int
    total_report_only: int        # effects + transitions + stickers + fonts
    total_size_bytes: int
```

### detect → ProjectItem

```python
detect.app_type         → GroupLabel selection (CAPCUT / JIANYING / ENCRYPTED)
detect.app_version      → MetaLabel  "CapCut Desktop 167.0.0"
detect.encryption       → dot color, badge, enabled state
detect.supported_status → badge text "ready" / "N warn" / "encrypted"
```

### AnalysisResult → ProjectCard

```python
f"{canvas_w}×{canvas_h}"       → RESOLUTION stat
fps_string(fps)                 → FRAME RATE stat
format_duration(duration_us)   → DURATION stat
clip_count                      → CLIPS stat
portability_badge_state()       → "PORTABLE PACKAGE READY" / "PARTIAL" / …
```

### AnalysisResult → ReadinessChecklist

```python
# Always ✓ for supported plaintext
"Timeline structure"  → f"{video_track_count} video · {audio_track_count} audio · {clip_count} clips"
"Media package"       → f"{total_online} files · {size_mb:.1f} MB · {total_offline} offline"
"Source items"        → "Premiere Project panel reconstruction"
"Constant speed"      → (shown only if speed_clip_count > 0) "N× → N% via timeremap"
"Subtitle export"     → (shown only if subtitle_cue_count > 0) f"{N} cues · Pattern A/B"

# Conditional ⚠
"Speed curves"        → (shown only if speed_curve_count > 0) ⚠ f"{N} clip(s) → 1.0× in Premiere"
"Stickers / effects"  → (shown only if total_report_only > 0) ⚠ f"{N} items → report-only"
```

### manifest → AssetGroupedTable

```python
# Group: FULLY MIGRATED
manifest.videos   → "User Video"       count, is_online → "✓ Copied"
manifest.audios   → "Embedded Audio"   with video-dedup note
manifest.sfx      → "CapCut SFX"       count

# Group: INCLUDED WITH WARNING
manifest.music    → "CapCut Music"     "⚠ Copied*" + licensing note

# Group: REPORT-ONLY
manifest.stickers   → "Stickers"       "Report-only"
manifest.effects    → "Effects"        "Report-only"
manifest.filters    → "Filters"        "Report-only"
manifest.transitions→ "Transitions"    (if any)
manifest.images     → "User Images"    (if any)
```

### PackageContentsSection + OutputTreeSection

Populated from `AnalysisResult` before collect runs (predicted).  
Updated from `CollectResult` after collect completes (actual).

```python
# Pre-collect: predicted from analysis
predicted_files = [
    f"{name}.xml",
    f"media/  · {total_online} files · {size_mb:.1f} MB",
    f"{name}.relink_guide.md",
    f"{name}.package_summary.txt",
    f"{name}.report.md",
    f"{name}.manifest.json",
]
if subtitle_cue_count > 0:
    predicted_files.append(f"{name}.srt  · {subtitle_cue_count} cues")

# Post-collect: from CollectResult
actual_tree = build_tree(result.out_dir)  # read actual filesystem
```

### MigrationNotesSection

```python
if speed_curve_count > 0:
    add_note(ORANGE, "Speed curves",
             f"{speed_curve_count} clip(s) play at 1.0× in Premiere. "
             "Rebuild via Effect Controls → Time Remapping.")
if total_report_only > 0:
    add_note(ORANGE, "Stickers / effects",
             f"{total_report_only} items not portable. Listed in report.md.")
if len(manifest.music) > 0:
    add_note(MUTED, "CapCut music",
             "In media/music/. Verify licensing before publishing.")
if detect.encryption != "plaintext":
    add_note(RED, "Encrypted draft",
             "This project cannot be collected. No decryption is attempted.")
```

---

## 4. Explicit Non-Goals

| Non-goal | Why excluded |
|---|---|
| Video playback | Not a player. Opens in Premiere. |
| Waveform display | Not an audio tool. No waveform data in draft_info.json. |
| Subtitle editor | Separate product (Subtitle Studio). |
| Timeline preview | Not a NLE. Premiere is the destination. |
| Effect reconstruction | CapCut-proprietary; legally out of scope. |
| Keyframe animation editor | Out of scope; rebuild in Premiere. |
| Encrypted draft support | Intentionally refused; no decryption attempted. |
| CapCut CDN / asset download | Out of scope; redistribution risk. |
| App bundle extraction (sticker packs) | Out of scope; licensing risk. |
| In-app Premiere plugin | Separate integration layer. |
| Batch collect | Possible post-MVP; not in scope now. |
| Settings / preferences panel | Not required for MVP. |
| Progress bar | Log bar text updates sufficient for MVP. |

---

## 5. MVP Milestone Definition

**GUI MVP = prototype renders with real data from a selected project.**

```
[ ] MainWindow opens at 980×730, three-panel layout, correct colors
[ ] ScanWorker discovers CapCut projects from default paths
[ ] Project groups: CapCut / Jianying / Encrypted rendered correctly
[ ] Add Folder… opens QFileDialog; result added to scan list
[ ] Clicking a project fires AnalyzeWorker
[ ] ProjectCard populates with real name, resolution, fps, duration
[ ] ReadinessChecklist renders ✓ / ⚠ from real IR + manifest data
[ ] AssetGroupedTable shows real category counts grouped correctly
[ ] PackageContentsSection shows predicted output files
[ ] OutputTreeSection shows predicted tree (pre-collect)
[ ] CollectButton fires CollectWorker; button states cycle correctly
[ ] OutputTreeSection updates with actual tree after collect
[ ] ExportSRTButton fires SRTWorker; success notice shown
[ ] OpenOutputButton calls subprocess.open (macOS) or os.startfile (Win)
[ ] Encrypted projects: red badge, Collect button disabled, note shown
[ ] LicensingFooter visible whenever music or SFX in manifest
```

---

## 6. Product positioning

```
CutSmith Timeline Bridge = Project Handoff Assistant.
Not a CapCut clone. Not a player. Not an effect tool.

Primary message:  "Your CapCut project is ready to hand off to Premiere."
Tagline:          "CutSmith moves your rough-cut structure. You bring the grade."
Secondary:        "Take your timeline with you."
```

The GUI makes the CLI accessible to creators who don't use a terminal.
All business logic stays in the existing Python modules — the GUI is a
thin PySide6 shell. No new core logic in `gui/`.
