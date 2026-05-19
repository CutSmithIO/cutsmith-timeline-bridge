# Changelog — CutSmith Timeline Bridge

All notable changes are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [v0.3.6-alpha] — 2026-05-19

### Added
- **Embedded audio dedup** (`_VIDEO_AUDIO_EXTENSIONS` rule): when a `USER_AUDIO`
  entry's source is a video-format file (`.mp4`, `.mov`, `.mkv`, …) already
  copied as `USER_VIDEO`, the audio entry reuses the `media/video/` copy instead
  of making a duplicate in `media/audio/`. CapCut's automatic video-audio split
  previously produced `.MP4` files in `media/audio/`.
- `CollectStats.embedded_audio_reused_count` tracks reuses per collect run.
- CLI output line: `Embedded audio reused: N (video file, no audio/ copy)`.
- `package_summary.txt` "Embedded audio reused from video assets: N" line.
- `relink_guide.md` "Audio extracted from video clips" section.
- 15 regression tests in `EmbeddedAudioReuseTest`.

### Changed
- Real-world result on `0519V`: 6 files → **5 files**, 7.3 MB → **5.8 MB**;
  `media/audio/` directory eliminated entirely.

---

## [v0.3.5] — 2026-05-19

### Added
- **`<stem>.package_summary.txt`** written alongside every `collect` package:
  absolute Package root + Relink root, per-subdir file counts, normalized
  extension pairs, offline / report-only counts, Premiere import steps, known
  limitations.
- **Rich collect CLI output**: `[ok] portable package created` banner; absolute
  Output root and Media package paths; all output filenames; dedup, ext-norm,
  and embedded-audio stats.
- **`-o` / `--out-dir` is now optional**: defaults to `out_collect/<project_name>/`
  in the current working directory. `_guess_project_name()` walks up past UUID /
  Timelines directory components to derive a human-readable name.
- **`--open` flag**: calls `open <out_dir>` (Finder / macOS) after collect.
- `_count_media_subdirs()` helper for per-subdir file counting.
- 23 new regression tests (261 total).

### Changed
- README wording fix: CutSmith **physically copies** media; Premiere reads
  collected paths and creates Project panel source items — it does not copy
  anything itself.

---

## [v0.3.4] — 2026-05-19

### Added
- **`<stem>.relink_guide.md`** per collect package: Premiere `File → Import`
  instructions, exact `media/` path to paste into `Link Media…`, folder
  structure map, proprietary-assets-not-portable section, speed trim-boundary
  edge case documentation.
- `AssetManifest` new fields: `collected_root`, `relink_root_hint`, `path_mode`,
  `package_portable`, `report_only_count`, `normalized_extension_count`.
- These fields are populated by the collector before `manifest.to_json()` and
  appear in `stats` in the output JSON.
- Speed trim-boundary edge case documented in `docs/known_limitations.md`.
- 30 regression tests (238 total).

### Fixed
- Collect report speed text: replaced stale "Premiere shows clips at 100% speed
  — apply manually" copy with accurate `timeremap` / auto-speed description.

---

## [v0.3.3] — 2026-05-19

### Added
- **Premiere Project panel master clip reconstruction**: one
  `<clip id="masterclip-{asset_id}">` element per asset at the FCP7 `xmeml`
  root. Each `<clipitem>` carries a `<masterclipid>` back-reference.
  Confirmed: Project panel shows source clips; relink-via-parent-folder works.
- **Constant speed reconstruction**: explicit FCP7
  `<filter><effectid>timeremap</effectid>` emitted for every speed-changed clip.
  Premiere imports 2× clips at **200%**, 0.5× clips at **49.91% / 49.96%**
  (confirmed in-app, 2026-05-19). No manual Speed/Duration step needed.
- `<clipitem><duration>` now uses source frames (`out − in`), not full asset
  duration. Fixes wavy trim handles on clips 2 and 3 of `0519V2`.
- Resolver inconsistency fix: `inspect` / `convert` / `collect` all accept
  project-root directories via `detect_project()`.
- `export-srt -o` now accepts a file path (e.g. `-o captions.srt`) in addition
  to a directory.

### Fixed
- `test_clipitem_times_consistent`: skip clips with `timeremap` filter (speed
  clips intentionally diverge `end−start` from `out−in`).

---

## [v0.3.2 / v0.3.1] — 2026-05-16

### Added
- **Cache extension normalization** via magic-byte detection (`detect_file_type`):
  CapCut cache files with wrong or missing extensions (`.mp3` files containing
  M4A data, extensionless PNG images) are copied with corrected extensions so
  Premiere opens them directly.
- `ManifestEntry` fields: `original_extension`, `detected_extension`,
  `extension_normalized`.
- `0519V2` fixture registered (`capcut-desktop-vertical-audio-channel-caption-speed`).

### Fixed
- `speed_curve` false-positive: the `speeds` predicate now only fires when
  `curve_speed is not None`, not for every segment with `speed == 1.0`.
- Collect dedup: key changed to `f"{src.resolve()}|{subdir_name}"` to prevent
  cross-subdir deduplication of semantically distinct uses.

---

## [v0.3.0] — 2026-05-16

### Added
- **`collect` command** (`cutsmith collect`): scan → copy user media to
  `media/<class>/` → rewrite XML `<pathurl>` to collected paths → write
  manifest + offline report. Validated on `0509`, `cutsmith`, `0519V`.
- Filename collision disambiguation: `<stem>_<asset_id[:8]><suffix>`.
- `AssetManifest.collect_relative_path` per entry.
- `<stem>.offline.md` for unresolved assets with suggested actions.
- `CollectResult` dataclass with `stats`, `manifest`, `written_files`.

---

## [v0.2.0] — 2026-05-16

### Added
- **`scan-assets`** subcommand: enumerate and classify all referenced materials
  into `<stem>.manifest.json` + `<stem>.scan.md`.
- **`export-srt`** subcommand: extract captions to `.srt` / `.txt` / `.json`.
  Supports Pattern A (top-level `texts[]`) and Pattern B (nested `content_segments`).
- **`inspect`** subcommand: schema-drift detection independent of the reader.
  Outputs `schema_summary.json`, `media_summary.json`, `track_summary.json`,
  `unsupported_summary.json`, `unknown_fields.json`, `debug_inspect.json`.
- IR extensions: `AssetClass` enum, `Asset.duration_us`, per-asset resolution.
- 108 unit tests at v0.2 baseline.

---

## [v0.1.1] — 2026-05-14

### Fixed
- **Double-audio bug**: auto-extracting audio from video assets produced
  duplicate `A3`/`A4` tracks. Removed; audio only emitted when CapCut creates
  an explicit `materials.audios` entry on an audio track.
- Report phrasing: embedded-audio note changed from `⚠` warning to neutral `Note`.

### Added
- `detect` subcommand: triage without parsing timeline.
- `_resolve_draft_entry()` unified draft-path resolution for all subcommands.

---

## [v0.1.0] — 2026-05-13

### Added
- Initial pipeline: `draft_info.json` → Timeline IR → FCP7 XML + `*.report.md`.
- Reader: CapCut Desktop `modern_plaintext` schema (`schema_version = 360000`,
  CapCut 167.0.0).
- Writer: FCP7 XML sequences, `<sequence>`, `<clipitem>`, `<file>` with OFFLINE
  fallback, `<filter>` for audio levels.
- Resolver: absolute path lookup + `--search-root` basename scan.
- Compatibility report: categorised unsupported items per segment.
- NTSC framerate detection (0.02 tolerance band).
- Windows-path cross-platform handling (drive-letter strip + basename match).
- `cutsmith2` stress-test fixture (speed, stickers, transitions, effects).
