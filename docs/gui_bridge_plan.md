# CutSmith Timeline Bridge — GUI Implementation Plan

**Prototype**: `docs/gui_prototype_bridge.html`  
**Target framework**: PySide6 (Qt 6.x)  
**Positioning**: Project Handoff Assistant — not a player, not an editor.

---

## 1. Component Map

```
MainWindow
├── TitleBar (custom; macOS traffic-light style)
└── CentralWidget (QFrame, no margin)
    └── BodyLayout (QHBoxLayout, no spacing)
        ├── ProjectPanel          220px fixed
        ├── MigrationPanel        flex (stretch)
        └── ExportInspectorPanel  280px fixed
```

### ProjectPanel (left, 220px)

```
ProjectPanel (QWidget)
├── BrandHeader (QFrame)
│   ├── AppNameLabel          "CutSmith Bridge"
│   └── AppSubLabel           version + description
├── ScanButton (QPushButton)  purple, primary
├── SearchFilter (QLineEdit)
├── SectionLabel              "PROJECTS  N found"
├── ProjectList (QListWidget or QScrollArea)
│   └── ProjectItem (custom QWidget) × N
│       ├── StatusDot (QLabel, colored circle)
│       ├── ProjectInfoStack (QVBoxLayout)
│       │   ├── ProjectNameLabel
│       │   ├── AppMetaLabel    "CapCut Desktop 167.0.0 · plaintext"
│       │   └── DateLabel
│       └── BadgeLabel         "ready" / "N warn" / "encrypted"
└── LogBar (QLabel)           last operation timestamp + summary
```

### MigrationPanel (center, stretch)

```
MigrationPanel (QWidget)
├── MigrationHeader (QFrame, fixed height)
│   ├── SectionLabel          "MIGRATION STATUS"
│   ├── ProjectNameLabel
│   ├── ProjectSubLabel       app + schema version
│   └── PortabilityBadge (QLabel)  "PORTABLE" / "PARTIAL" / "ENCRYPTED"
├── TimelineMetadataGrid (QGridLayout, 4 cols × 2 rows)
│   └── MetaCard (QFrame) × 8
│       ├── KeyLabel          "DURATION", "RESOLUTION", …
│       └── ValueLabel        data value, colored by state
├── AssetTableHeader (QFrame, fixed row)
│   └── four column labels
├── AssetTable (QScrollArea)
│   └── AssetRow (QFrame) × N
│       ├── StatusDot
│       ├── CategoryLabel + SubLabel
│       ├── FileCountLabel
│       └── PortabilityLabel  "✓ Copied" / "⚠ Copied*" / "Report-only" / "—"
├── ReportOnlyStrip (QFrame, fixed, pinned above status)
│   ├── StripLabel            "REPORT-ONLY ITEMS"
│   └── ReportItem (QFrame) × N
│       ├── DotLabel
│       ├── DescriptionLabel
│       └── TagLabel
└── CenterStatusBar (QFrame)
    ├── SchemaLabel
    └── SizeLabel             "N files · N MB · N offline"
```

### ExportInspectorPanel (right, 280px)

```
ExportInspectorPanel (QWidget)
├── InspectorHeader (QFrame)
│   ├── TitleLabel            "Export Inspector"
│   └── EncryptionBadge       "PLAINTEXT" / "ENCRYPTED"
├── OutputConfigSection (QFrame)
│   ├── NLESelectorRow        label + QComboBox
│   ├── OutputFolderLabel
│   ├── OutputFolderField (QLabel, monospace, word-wrap)
│   └── BrowseButton (QPushButton)
├── ExportActionsZone (QFrame)
│   ├── SectionLabel
│   ├── CollectButton (QPushButton, purple, full-width)
│   └── SecondaryRow (QHBoxLayout)
│       ├── ExportSRTButton
│       ├── XMLOnlyButton
│       └── OpenOutputButton
├── WarningsSection (QFrame)
│   ├── SectionLabel
│   └── WarningItem (QFrame) × N
│       ├── DotLabel          orange / muted
│       └── WarningText (QLabel, word-wrap)
├── LicensingSection (QFrame)
│   ├── SectionLabel
│   └── LicensingNotice (QLabel, word-wrap, muted)
├── AnalysisToolsSection (QFrame, stretch)
│   ├── SectionLabel
│   └── ToolRow × 3
│       ├── ToolLabel
│       └── RunButton (QPushButton, small)
└── FooterTagline (QLabel, italic, centered)
```

---

## 2. PySide6 Implementation Plan

### File layout

```
cutsmith/
└── gui/
    ├── __init__.py
    ├── main.py              ← entry point: python -m cutsmith.gui
    ├── main_window.py       ← MainWindow(QMainWindow)
    ├── panels/
    │   ├── __init__.py
    │   ├── project_panel.py
    │   ├── migration_panel.py
    │   └── inspector_panel.py
    ├── widgets/
    │   ├── __init__.py
    │   ├── project_item.py  ← custom list item widget
    │   ├── meta_card.py     ← metadata cell (key + value)
    │   ├── asset_row.py     ← one row in asset category table
    │   ├── warning_item.py  ← one warning row
    │   └── badge.py        ← colored status badge
    ├── workers/
    │   ├── __init__.py
    │   ├── scan_worker.py   ← QThread: discover + detect projects
    │   ├── analyze_worker.py← QThread: scan_assets + read_draft
    │   ├── collect_worker.py← QThread: collect pipeline
    │   └── srt_worker.py   ← QThread: export-srt
    └── style.py            ← QSS stylesheet constants
```

### Color and style constants (`style.py`)

```python
# Mirrors the HTML prototype's CSS token system exactly.
BG_BASE      = "#1c1c1e"
BG_RAISED    = "#242426"
BG_SURFACE   = "#2c2c2e"
BORDER       = "#3a3a3c"
BORDER_SUB   = "#2c2c2e"
ACCENT       = "#9b8cff"
ACCENT_DARK  = "#5a4fcf"
ACCENT_HOVER = "#6b60e0"
TEXT_PRIMARY = "#e5e5ea"
TEXT_SECONDARY = "#98989f"
TEXT_MUTED   = "#636366"
TEXT_FAINT   = "#48484a"
GREEN        = "#30d158"
ORANGE       = "#ff9f0a"
RED          = "#ff453a"
FONT_MONO    = "'IBM Plex Mono', 'SF Mono', monospace"
FONT_SANS    = "'IBM Plex Sans', 'SF Pro Display', sans-serif"

QSS = f"""
QWidget {{ background: {BG_BASE}; color: {TEXT_PRIMARY};
          font-family: 'IBM Plex Mono'; font-size: 11px; }}
QScrollBar:vertical {{ background: {BG_BASE}; width: 6px; }}
QScrollBar::handle:vertical {{ background: {BORDER}; border-radius: 3px; }}
/* ... */
"""
```

### Threading model

```
Main Thread (Qt event loop)
│
├── ScanWorker (QThread)
│   Input:  list of CapCut project root paths to check
│   Steps:  detect_project() on each path
│   Output: list[DetectResult]
│   Signals: progress(str), project_found(DetectResult), finished()
│
├── AnalyzeWorker (QThread)
│   Input:  selected project path
│   Steps:  detect_project() + scan_assets() + read_draft() (IR only)
│   Output: AnalysisResult (see Data Bindings section)
│   Signals: progress(str), finished(AnalysisResult), error(str)
│
├── CollectWorker (QThread)
│   Input:  project path, out_dir, search_roots
│   Steps:  collect() pipeline
│   Output: CollectResult
│   Signals: progress(str), finished(CollectResult), error(str)
│
└── SRTWorker (QThread)
    Input:  project path, out_path
    Steps:  export_srt()
    Output: Path (written file)
    Signals: finished(Path), error(str)
```

### Signal / slot wiring

```python
# MainWindow.__init__
project_panel.project_selected.connect(migration_panel.load_project)
project_panel.project_selected.connect(inspector_panel.load_project)
project_panel.scan_requested.connect(self._start_scan)

inspector_panel.collect_requested.connect(self._start_collect)
inspector_panel.srt_requested.connect(self._start_srt)
inspector_panel.xml_only_requested.connect(self._start_xml_only)
inspector_panel.open_output_requested.connect(self._open_output)
inspector_panel.browse_requested.connect(self._browse_output_dir)

self._analyze_worker.finished.connect(migration_panel.show_analysis)
self._analyze_worker.finished.connect(inspector_panel.show_warnings)
self._collect_worker.finished.connect(inspector_panel.show_result)
self._collect_worker.error.connect(inspector_panel.show_error)
```

### CapCut project discovery (ScanWorker)

Default paths to search:

```python
CAPCUT_SEARCH_ROOTS = [
    # macOS CapCut Desktop
    "~/Library/Containers/com.lemon.lvmediapro/Data/Library/"
    "Application Support/LVMediaProSandBox/UserData/draft",
    # macOS 剪映 Professional
    "~/Movies/JianyingPro/User Data/Projects/com.lveditor.draft",
    # Windows (resolved at runtime if os.name == 'nt')
    "~/AppData/Local/CapCut/User Data/Projects/com.lveditor.draft",
]
```

Walk each root, find directories containing `draft_info.json`, run
`detect_project()` on each.

### Progress feedback

- Log bar (left panel): last N log lines, updated via signal
- Collect button: text changes to "Collecting…" while running;
  re-enabled with "✓ Done" flash on success
- Status bar (center): updates with current operation phase

---

## 3. Data Bindings — Core → GUI

### detect_project() → ProjectItem + ExportInspector badge

```python
# cutsmith.detect.DetectResult (existing)
detect_result.app_type          → proj_app label  "CapCut Desktop"
detect_result.app_version       → proj_app label  "167.0.0"
detect_result.schema_type       → proj_app label  "plaintext" / "encrypted"
detect_result.encryption        → StatusDot color + EncryptionBadge
detect_result.supported_status  → BadgeLabel "ready" / "warn" / "encrypted"
```

### scan_assets() → AssetCategoryTable

```python
# cutsmith.scanner.AssetManifest (existing)
manifest.videos          → AssetRow "User Video"       count + is_online
manifest.audios          → AssetRow "User Audio"       count + is_online
manifest.music           → AssetRow "CapCut Music"     count + license warn
manifest.sfx             → AssetRow "CapCut SFX"       count + is_online
manifest.images          → AssetRow "User Images"      count + is_online
manifest.stickers        → AssetRow "Stickers"         count + Report-only
manifest.effects         → AssetRow "Effects"          count + Report-only
manifest.filters         → AssetRow "Filters"          count + Report-only
manifest.transitions     → AssetRow "Transitions"      count + Report-only
manifest.fonts           → AssetRow "Fonts"            count + Report-only
```

### read_draft() → IR → TimelineMetadataGrid

```python
# cutsmith.ir.Timeline (existing)
timeline.duration_us / 1_000_000 → "DURATION"  formatted mm:ss.s
timeline.canvas.width            → "RESOLUTION" "W×H"
timeline.canvas.height           →
timeline.fps                     → "FRAME RATE"
sum(len(t.segments) for t in timeline.video_tracks)  → "CLIP COUNT"
len(timeline.video_tracks)       → "VIDEO TRACKS"
len(timeline.audio_tracks)       → "AUDIO TRACKS"
sum(1 for s in all_segs if s.speed and s.speed != 1.0) → "SPEED CLIPS"
subtitle_count (from scan)       → "SUBTITLES"
```

### IR segment inspection → ReportOnlyStrip + WarningsSection

```python
# Derived from IR segments (existing reader fields)
speed_curve_segs = [s for s in all_segs if s.curve_speed is not None]
sticker_count    = len(manifest.stickers)
effect_count     = len(manifest.effects)
transition_count = len(manifest.transitions)

# → ReportOnlyStrip items
# → WarningsSection items in InspectorPanel
```

### collect() → post-collect state

```python
# cutsmith.collector.CollectResult (existing)
result.stats.copied_count              → "N files · N MB"
result.stats.offline_count             → offline warning if > 0
result.stats.embedded_audio_reused_count → note in status bar
result.stats.extension_normalized_count  → note in status bar
result.manifest.collected_root         → OutputFolderField update
result.manifest.relink_root_hint       → shown in collect completion notice
result.out_dir                         → OpenOutputButton enabled
```

### export_srt() → SRT completion

```python
# cutsmith.subtitle.export_srt() return value
srt_path → success notice: "Wrote captions.srt · N cues"
```

---

## 4. Explicit Non-Goals

This GUI is a **Project Handoff Assistant**. The following are intentionally
out of scope and should not be added without a separate product decision:

| Non-goal | Why excluded |
|---|---|
| Video playback | Not a player. Opens in Premiere. |
| Waveform display | Not an audio tool. No waveform data in draft_info.json. |
| Subtitle editor | Separate product (Subtitle Studio). |
| Timeline preview | Not a NLE. Premiere is the preview. |
| Effect reconstruction | CapCut-proprietary; legally out of scope. |
| Keyframe animation editor | Out of scope; rebuild in Premiere. |
| CapCut encrypted draft support | Intentionally refused; no decryption. |
| CapCut CDN / asset download | Out of scope; redistribution risk. |
| App bundle extraction (sticker packs) | Out of scope; licensing risk. |
| In-app Premiere integration / plugin | Separate integration layer. |
| Batch collect across multiple projects | Possible later; not MVP. |

---

## 5. MVP Milestone Definition

**GUI MVP = prototype renders with real data from a selected project.**

Milestone checklist:

- [ ] `MainWindow` opens with three-panel layout
- [ ] `ScanButton` discovers CapCut projects via `detect_project()`
- [ ] Clicking a project triggers `AnalyzeWorker` (detect + scan_assets)
- [ ] `MigrationPanel` populates with real timeline metadata
- [ ] `AssetCategoryTable` shows real category counts and portability status
- [ ] `WarningsSection` shows speed_curve / proprietary asset warnings
- [ ] `CollectButton` triggers `CollectWorker` and shows completion state
- [ ] `ExportSRTButton` triggers `SRTWorker`
- [ ] `OpenOutputButton` opens Finder / Explorer on output dir
- [ ] Encrypted projects show red badge; Collect button disabled for them
- [ ] `LicensingNotice` always visible when music/SFX present

**Not required for MVP:**
- Progress bar (log bar text updates are sufficient)
- Schema inspect button wired up
- Settings / preferences panel
- Multiple search roots UI

---

## 6. Product positioning reminder

```
CutSmith Timeline Bridge = workflow bridge.
Not a CapCut clone. Not a player. Not an effect tool.

"CutSmith moves your rough-cut structure. You bring the grade."
"Take your timeline with you."
```

The GUI makes the CLI accessible to creators who don't use a terminal.
All core logic stays in the existing Python modules — the GUI is a thin
PySide6 shell over the existing `detect`, `scan_assets`, `read_draft`,
`collect`, and `export_srt` functions.
