# CutSmith Timeline Bridge

CapCut Desktop → Premiere Pro XML bridge.

Convert real-world CapCut timelines into editable Premiere Pro sequences,
and collect all user media into a portable package ready for Premiere delivery.

**Status**: v0.3.4

**Validated against**:
- CapCut Desktop 167.0.0
- modern_plaintext schema (`schema_version = 360000`)
- Premiere Pro FCP7 XML import

[中文文档 →](README.zh-CN.md)

---

## What this is (and isn't)

CutSmith is a **rough-cut timeline mover and media packager**, not a full
CapCut → Premiere project converter. The goal is to let editors who've already
structured a sequence in CapCut continue in Premiere Pro without rebuilding
cuts and audio from scratch — and to hand off a self-contained package where
all user media travels with the XML.

The reader normalises a CapCut `draft_info.json` into a small Timeline IR; the
writer emits FCP7 XML that Premiere imports as a real sequence. A sidecar
`*.report.md` lists everything that didn't survive the conversion (transitions,
filters, captions, speed changes, ...) so the editor knows what to rebuild.
The v0.3 `collect` command copies all resolved user media alongside the XML and
rewrites the XML paths so Premiere opens the package directly without a
`Link Media` step.

## Tested against real-world projects

v0.3-alpha has been end-to-end validated against real CapCut Desktop 167.0.0
projects. They live in [`tests/fixtures/real_world/sample_manifest.json`](tests/fixtures/real_world/sample_manifest.json).

| Type | Sample ID | Shape |
|---|---|---|
| Single-cut | `0509` | One 151.4s slice from a long source + 154 ignored captions — validates long-timeline stability |
| Multicut | `cutsmith` | V1 with 7 butt-cut clips + V2 overlay + BGM + SFX. 0 unsupported items. |
| Stress-test | `cutsmith2` | Multi-cut + overlay + captions + stickers + transitions + filters + effects + 0.640× variable speed |
| Vertical full-stress | `0519V` | 1080×1920, 7 video tracks, 0.5× + 2.0× speed clips, speed_curve, stickers, transitions, effects, filters, 8-cue subtitles (Pattern B) |
| Vertical multi-speed | `0519V2` | 1080×1920, 30fps NDF, 7 clips with 2.0×/0.5×/0.5× constant speed, 33 auto-captions, 10 stickers; collect dedup fixed |

`collect` validated on: `0509`, `cutsmith`, `0519V`, `0519V2`.

## Supported features

### Fully supported
- Cuts (in / out / position on timeline)
- Overlays (multi-track video order — V1, V2, ...)
- Audio tracks (BGM, voiceover, CapCut's auto-split video audio)
- BGM / SFX on independent audio tracks
- Timeline structure: framerate (NDF + NTSC), resolution, sample rate
- Asset path resolution with offline-friendly placeholders for Premiere's `Link Media`

### Partial
- **Constant speed changes** — native Premiere Speed/Duration reconstructed
  via explicit FCP7 `timeremap` filter (200% and ≈50% confirmed in-app,
  2026-05-19). Timeline slot uses target duration — downstream clips don't
  drift. Variable-speed ramps (`speed_curve`) remain report-only; the clip
  plays at 1.0× in Premiere.
- **Premiere Project panel** — each asset generates a root-level master clip
  (`<clip id="masterclip-…">`) so source items appear in the Project panel.
  Relink-via-parent-folder works for offline clips.

### Ignored safely
- Subtitles
- Stickers
- Filters
- Transitions
- Effects

Each is named in the report when CapCut provided a readable label. For the full
four-tier matrix (fully / partial / ignored / unsupported) see
[`docs/supported_features_matrix.md`](docs/supported_features_matrix.md).

## Known limitations

- **Embedded audio fallback** lands in v0.1.2. CapCut drafts that keep original
  sound on video clips without creating an explicit audio track are currently
  exported with silent video.
- **No native subtitle / title reconstruction** — export an SRT from CapCut
  and import into Premiere Captions.
- **No transition / filter reconstruction yet** — use the report as a checklist
  and reapply Premiere's native equivalents.

Full caveat list and reasoning in [`docs/known_limitations.md`](docs/known_limitations.md).

## Quick start

Standard library only. Python ≥ 3.10.

```bash
git clone git@github.com:CutSmithIO/cutsmith-timeline-bridge.git
cd cutsmith-timeline-bridge
```

### 1. Detect — classify a draft

```bash
python3 -m cutsmith detect "/path/to/CapCut/project"
```

Reports `app_type`, `app_version`, `schema_type`, `encryption`, and
`supported_status` without parsing the timeline. Run on any unfamiliar
sample first. `--json` prints output ready to paste into the manifest.

### 2. Inspect — surface schema drift

```bash
python3 -m cutsmith inspect "/path/to/draft_info.json" -o ./inspect_out
```

Emits structural summaries. The critical one is `unknown_fields.json` —
anything listed is in the draft but unread by the current reader (i.e.,
CapCut has drifted since the reader was last updated). `--raw-paths`
keeps absolute paths in the output; omit it to redact to basenames
before sharing in a bug report.

### 3. Convert — produce FCP7 XML + report

```bash
python3 -m cutsmith convert "/path/to/draft_info.json" \
  -o ./out \
  -s "/path/to/footage" \
  -n my_sequence
```

Outputs `my_sequence.xml` (drop into Premiere via `File → Import`, *not*
`Open Project`) and `my_sequence.report.md` (read it before opening the
XML). `-s/--search-root` is repeatable for multi-location media.

### 4. Collect — portable package for Premiere delivery (v0.3)

```bash
python3 -m cutsmith collect "/path/to/CapCut/project" \
  -o ./collected \
  [-s "/path/to/extra/footage"]
```

Scans all materials, copies every resolved user asset into `media/`, rewrites
the XML `<pathurl>` entries to point at the collected files, and writes a
manifest + offline report. Output structure:

```
collected/
├── my_sequence.xml              ← paths rewritten to collected media
├── my_sequence.report.md        ← compat report + collect summary
├── my_sequence.manifest.json    ← collected_root, relink_root_hint, path_mode, stats
├── my_sequence.relink_guide.md  ← Premiere import + relink instructions
├── my_sequence.offline.md       ← only if assets could not be found
└── media/
    ├── video/
    ├── audio/
    ├── images/
    ├── music/               ← CapCut licensed music (verify rights before publishing)
    └── sfx/
```

CapCut proprietary stickers, effects, transitions, and filters are **not
portable** — they are reported in the report and offline file but cannot
be extracted from CapCut. Rebuild them using Premiere's native equivalents.

The full validation workflow — IR diagnostic, Premiere-side checks per
sample — is in
[`docs/creator_validation_checklist.md`](docs/creator_validation_checklist.md).

## Creator validation status

v0.3.4 is **structurally and Premiere-validated** (238 unit tests pass;
real-world samples `0509`, `cutsmith`, `0519V`, and `0519V2` convert and
collect cleanly; Premiere import confirmed 2026-05-19).

**Confirmed Premiere behaviours:**
- Sequence resolution (including vertical 1080×1920) imports correctly.
- **Project panel source clips appear** — each asset generates a root-level
  master clip so the Project panel is populated; relink-via-parent-folder works.
- **Constant speed reconstructed** — 2.0× clips import at 200%, 0.5× clips at
  ≈50%. Effect Controls → Speed/Duration shows the correct value automatically.
- `collect` package opens in Premiere without a `Link Media` step for all
  online user assets.
- Variable-speed ramps (`speed_curve`) play at 1.0× in Premiere — rebuild
  manually via Effect Controls → Time Remapping → Velocity.

If you import any sample into Premiere and want to report findings, please
open an issue with the format suggested in
[`docs/creator_validation_checklist.md`](docs/creator_validation_checklist.md).

## Project layout

```
cutsmith/
├── ir/              # canonical Timeline IR (reader-writer contract)
├── reader/          # CapCut draft_info.json → IR
├── detect/          # triage: app/version/encryption/supported_status
├── inspect/         # schema-drift detection (independent of reader)
├── resolver/        # asset path resolution + offline placeholders
├── scanner/         # asset manifest + classification (scan-assets)
├── subtitle/        # SRT extraction (export-srt)
├── collector/       # v0.3 collect pipeline: copy + relink
├── writer/          # IR → FCP7 XML
├── report/          # IR + resolution → compatibility_report.md
├── bridge.py        # high-level pipeline
└── __main__.py      # detect / inspect / convert / scan-assets / export-srt / collect CLI
scripts/
└── ir_diag.py       # post-reader Timeline IR dump for diagnosis
docs/                # creator_validation_checklist, known_limitations,
                     #   supported_features_matrix, notes/
tests/fixtures/real_world/sample_manifest.json
```

Each layer is independently testable; adding a v0.2 FCPXML or Resolve
writer won't touch the reader.

`inspect` does not call `reader`; it parses the JSON independently so it
keeps working when the reader is broken. Both share a small "known
fields" table in `cutsmith/inspect/schema.py` that should be updated when
the reader learns new fields.

## Roadmap

- **v0.2** — Asset manifest (`scan-assets`), subtitle extraction (`export-srt`),
  Pattern A + B subtitle support. ✅ shipped.
- **v0.3** — `collect`: copy user media alongside the XML, rewrite paths for
  Premiere delivery. ✅ shipped. Validated on `0509` / `cutsmith` / `0519V`.
- **v0.3.4** — `<stem>.relink_guide.md` per collect package (Premiere import
  instructions, relink root hint, speed trim-boundary edge case). Manifest
  gains `collected_root`, `relink_root_hint`, `path_mode`, `package_portable`,
  `report_only_count`, `normalized_extension_count`. Speed report text updated
  to reflect v0.3.3 `timeremap` behaviour (no manual Speed/Duration needed).
  Speed trim-boundary edge case documented in `known_limitations.md`. ✅ shipped.
- **Later** — FCPXML output, DaVinci Resolve XML, keyframe animations,
  CapCut Mobile fixture coverage.

## Tests

```bash
python3 -m unittest discover -s tests
```

238 tests as of v0.3.4 — pipeline smoke, inspect schema drift, writer audio
contract, speed filter (timeremap), master clip reconstruction, reader
regressions, subtitle extraction (Pattern A + B), asset manifest and
classification, collector relink guide, manifest v0.3.4 fields.

## Repository

- GitHub: <https://github.com/CutSmithIO/cutsmith-timeline-bridge>
- Latest tag: [`v0.3-alpha`](https://github.com/CutSmithIO/cutsmith-timeline-bridge/releases/tag/v0.3-alpha)
- 中文文档: [`README.zh-CN.md`](README.zh-CN.md)

## License

MIT.
