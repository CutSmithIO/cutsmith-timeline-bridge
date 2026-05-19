# CutSmith Timeline Bridge

CapCut Desktop → Premiere Pro XML bridge.

Convert real-world CapCut timelines into editable Premiere Pro sequences.

**Status**: Alpha

**Validated against**:
- CapCut Desktop 167.0.0
- modern_plaintext schema (`schema_version = 360000`)
- Premiere Pro FCP7 XML import

[中文文档 →](README.zh-CN.md)

---

## What this is (and isn't)

CutSmith is a **rough-cut timeline mover**, not a full CapCut → Premiere project
converter. The goal is to let editors who've already structured a sequence in
CapCut continue in Premiere Pro without rebuilding cuts and audio from scratch.

The reader normalises a CapCut `draft_info.json` into a small Timeline IR; the
writer emits FCP7 XML that Premiere imports as a real sequence. A sidecar
`*.report.md` lists everything that didn't survive the conversion (transitions,
filters, captions, speed changes, ...) so the editor knows what to rebuild.

## Tested against real-world projects

v0.1.1-alpha has been end-to-end validated against three real CapCut Desktop
167.0.0 projects. They live in [`tests/fixtures/real_world/sample_manifest.json`](tests/fixtures/real_world/sample_manifest.json).

| Type | Sample ID | Shape |
|---|---|---|
| Single-cut | `0509` | One 151.4s slice from a long source + 154 ignored captions — validates long-timeline stability |
| Multicut | `cutsmith` | V1 with 7 butt-cut clips + V2 overlay + BGM + SFX. 0 unsupported items. |
| Stress-test | `cutsmith2` | Multi-cut + overlay + captions + stickers + transitions + filters + effects + 0.640× variable speed |
| Vertical full-stress | `0519V` | 1080×1920, 7 video tracks, 0.5× + 2.0× speed clips, speed_curve, stickers, transitions, effects, filters, 8-cue subtitles (Pattern B) |

## Supported features

### Fully supported
- Cuts (in / out / position on timeline)
- Overlays (multi-track video order — V1, V2, ...)
- Audio tracks (BGM, voiceover, CapCut's auto-split video audio)
- BGM / SFX on independent audio tracks
- Timeline structure: framerate (NDF + NTSC), resolution, sample rate
- Asset path resolution with offline-friendly placeholders for Premiere's `Link Media`

### Partial
- **Speed changes** — timeline slot uses CapCut's target duration (downstream
  clips don't drift). Source in/out range is preserved. **Premiere shows
  the clip at 100% speed** — native Premiere speed is not reconstructed.
  Each flagged segment appears in the report with its speed value so you
  can apply Speed/Duration manually. (Confirmed: Premiere import test 2026-05-19.)

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

The full validation workflow — IR diagnostic, Premiere-side checks per
sample — is in
[`docs/creator_validation_checklist.md`](docs/creator_validation_checklist.md).

## Creator validation status

v0.2-alpha is **structurally validated** (108 unit tests pass; four
real-world samples convert cleanly, including Premiere Pro import of `0519V`
on 2026-05-19).

**Confirmed Premiere behaviours:**
- Sequence resolution (including vertical 1080×1920) imports correctly.
- Speed clips: timeline slot and source range are preserved. **Premiere shows
  clips at 100% speed** — native Premiere speed is not reconstructed from the
  XML. Apply Speed/Duration manually per the report. This is a known
  limitation, not a bug.

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
├── writer/          # IR → FCP7 XML
├── report/          # IR + resolution → compatibility_report.md
├── bridge.py        # high-level pipeline
└── __main__.py      # detect / inspect / convert CLI
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

- **v0.1.2** — Smart Embedded Audio Fallback. Reader-side derivation of
  an audio track from a video asset when no explicit audio track covers
  the same source over the same target range. See the limitation note in
  [`docs/known_limitations.md`](docs/known_limitations.md#embedded-audio-of-video-clips).
- **v0.2** — Asset manifest (`scan-assets`), subtitle extraction (`export-srt`),
  Pattern A + B subtitle support. ✅ shipped.
- **v0.3** — collect / relink (gather + copy user media alongside the XML).
- **Research track** — Premiere native speed reconstruction via explicit
  Time Remap `<filter>` nodes. (FCP7 implicit encoding confirmed not
  auto-interpreted by Premiere.)
- **Later** — FCPXML output, DaVinci Resolve XML, keyframe animations,
  CapCut Mobile fixture coverage.

## Tests

```bash
python3 -m unittest discover -s tests
```

108 tests as of v0.2-alpha — pipeline smoke, inspect schema drift,
writer audio contract, reader regressions, subtitle extraction (Pattern A + B),
asset manifest and classification.

## Repository

- GitHub: <https://github.com/CutSmithIO/cutsmith-timeline-bridge>
- Latest tag: [`v0.1.1-alpha`](https://github.com/CutSmithIO/cutsmith-timeline-bridge/releases/tag/v0.1.1-alpha)
- 中文文档: [`README.zh-CN.md`](README.zh-CN.md)

## License

MIT.
