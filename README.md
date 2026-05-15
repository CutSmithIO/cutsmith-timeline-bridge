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

## Supported features

### Fully supported
- Cuts (in / out / position on timeline)
- Overlays (multi-track video order — V1, V2, ...)
- Audio tracks (BGM, voiceover, CapCut's auto-split video audio)
- BGM / SFX on independent audio tracks
- Timeline structure: framerate (NDF + NTSC), resolution, sample rate
- Asset path resolution with offline-friendly placeholders for Premiere's `Link Media`

### Partial
- **Speed changes** — exported as 1.0× clips; each is flagged in the report
  for manual retiming in Premiere. The clip occupies CapCut's target slot so
  downstream alignment is preserved.

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

v0.1.1-alpha is **structurally validated** (44 unit tests pass; three
real-world samples convert cleanly) but **awaits real-world Premiere Pro
import feedback** before promotion to limited creator testing.

The biggest unverified assumption is the variable-speed clip behaviour:
v0.1.1 leaves the duration mismatch in the XML for Premiere to interpret
as implied speed, rather than writing an explicit Time Remap filter. The
`cutsmith2.xml` sample exercises this directly — see Sample 3 in the
[validation checklist](docs/creator_validation_checklist.md).

If you import any of the three samples into Premiere and want to report
findings, please open an issue with the format suggested at the end of
the checklist.

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
- **v0.2** — FCPXML output (Final Cut Pro X / 11), explicit Time Remap
  filter for variable speed, keyframe animations.
- **Later** — DaVinci Resolve XML, CapCut Mobile fixture coverage,
  legacy plaintext fixture coverage.

## Tests

```bash
python3 -m unittest discover -s tests
```

44 tests as of v0.1.1-alpha — pipeline smoke, inspect schema drift,
writer audio contract, P1 reader regressions (speed tolerance + extra
ref classification), P3 timeline duration, name fallback.

## Repository

- GitHub: <https://github.com/CutSmithIO/cutsmith-timeline-bridge>
- Latest tag: [`v0.1.1-alpha`](https://github.com/CutSmithIO/cutsmith-timeline-bridge/releases/tag/v0.1.1-alpha)
- 中文文档: [`README.zh-CN.md`](README.zh-CN.md)

## License

MIT.
