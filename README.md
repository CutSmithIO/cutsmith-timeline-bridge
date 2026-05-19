# CutSmith Timeline Bridge

**CapCut Desktop → portable Premiere Pro package workflow**

Convert a CapCut Desktop timeline into a self-contained Premiere package:
XML + physically-copied media + relink guide, ready to open on any machine.

**Status**: v0.3.6-alpha  
**Validated**: CapCut Desktop 167.0.0 · Premiere Pro 2024/2025 · Python ≥ 3.10

[中文文档 →](README.zh-CN.md) · [Changelog →](CHANGELOG.md) · [Creator Beta →](docs/creator_beta.md)

---

## What this does

```
CapCut Desktop draft_info.json
          │
          ▼  python3 -m cutsmith collect
          │
          ├─ out_collect/<name>/
          │    ├─ <name>.xml                ← File → Import into Premiere
          │    ├─ <name>.package_summary.txt ← open this first
          │    ├─ <name>.relink_guide.md    ← import + relink instructions
          │    ├─ <name>.report.md          ← what was kept / dropped
          │    ├─ <name>.manifest.json      ← machine-readable asset index
          │    ├─ <name>.offline.md         ← (only if assets not found)
          │    └─ media/
          │         ├─ video/              ← user video clips (physically copied)
          │         ├─ audio/              ← standalone audio (not video-split dups)
          │         ├─ music/              ← CapCut music library *
          │         ├─ sfx/               ← CapCut SFX *
          │         └─ images/            ← image overlays
          │
          └─ Premiere opens the XML, sees all paths as local absolute paths.
             Project panel shows one source clip per unique asset.
             No "Link Media" step needed for collected assets.

* verify licensing before publishing
```

CutSmith does three things:

1. **Converts** the timeline — cuts, tracks, speed, audio — into FCP7 XML
   that Premiere imports as a real, editable Sequence.
2. **Packages** all user media by physically copying files into `media/`,
   then rewriting every `<pathurl>` in the XML to point at the copies.
3. **Documents** what didn't survive (effects, transitions, speed curves,
   captions) so you know exactly what to rebuild in Premiere.

This is a **rough-cut mover**, not a full project converter. The goal: your
CapCut timeline structure (clips, tracks, timing, audio) arrives in Premiere
intact; you finish the grade in Premiere.

---

## Confirmed working

Tested end-to-end on real CapCut Desktop 167.0.0 projects, imported into
Premiere Pro 2024 / 2025:

| Feature | Confirmed |
|---|---|
| Multi-cut V1 timeline (butt cuts) | ✅ |
| Multi-track video (V1 / V2 / V3 overlays) | ✅ |
| BGM + SFX on independent audio tracks | ✅ |
| Premiere Project panel source clips (master clip reconstruction) | ✅ |
| Relink-via-parent-folder (Link Media → parent dir → auto-links rest) | ✅ |
| Constant speed changes — **0.5× clips → 49.91%**, **2× clips → 200%** | ✅ in-app confirmed |
| Vertical timelines (1080×1920) | ✅ |
| Portable media package — copy dir to another machine, relink | ✅ |
| CapCut cache extension normalization (.mp3 → .m4a, extensionless → .png) | ✅ |
| Embedded audio dedup — video-audio split shares one physical file | ✅ |
| Subtitle export to SRT (for Premiere Captions import) | ✅ Pattern A + B |
| Asset manifest JSON | ✅ |
| Package summary txt + relink guide md | ✅ |

---

## Known edge cases

| Edge case | Behaviour |
|---|---|
| Variable speed curves (`speed_curve`) | Report-only — clip plays at **1.0×** in Premiere. Rebuild via Effect Controls → Time Remapping. |
| Speed clip trim boundary | A 2× clip at source-file limit shows **wavy trim handles**. Expected — no additional source frames exist. |
| CapCut effects / transitions / filters | Ignored safely — named in report, absent from XML. Rebuild with Premiere native equivalents. |
| CapCut stickers | Ignored safely — named in report. |
| Subtitles in convert/collect | Dropped from XML. Run `export-srt` separately, import as Premiere Captions track. |
| Encrypted 剪映 PC ≥ 75.0.0 | Detected and refused. No decryption is attempted. |
| Windows paths on macOS | Requires explicit `-s` search root; basename matching used. |

---

## Quick start

```bash
git clone https://github.com/CutSmithIO/cutsmith-timeline-bridge.git
cd cutsmith-timeline-bridge
# No pip install — standard library only, Python ≥ 3.10
```

### 1. Triage — classify the draft

```bash
python3 -m cutsmith detect "/path/to/CapCut/project"
```

Reports `app_type`, `app_version`, `schema_type`, `encryption`,
`supported_status`. Run on any unfamiliar sample before going further.

### 2. Inspect — check for schema drift

```bash
python3 -m cutsmith inspect "/path/to/CapCut/project" -o ./inspect_out
```

`inspect_out/unknown_fields.json` lists anything in the draft that the reader
doesn't handle. Empty list = reader schema assumptions are current. If it's
non-empty, open an issue — it means CapCut has added new fields since the last
update.

### 3. Collect — produce the portable package

```bash
# -o is optional; default: out_collect/<project_name>/
python3 -m cutsmith collect "/path/to/CapCut/project" \
  [-s "/path/to/footage"]   \   # repeat for multiple search roots
  [--open]                        # open output folder in Finder (macOS)
```

Then open the package:

```
out_collect/<name>/
  ├─ <name>.package_summary.txt  ← read this first
  ├─ <name>.relink_guide.md      ← paste the Relink root into Premiere Link Media
  └─ <name>.xml                  ← File → Import (not Open Project)
```

### 4. Import into Premiere

1. `File → Import…` → select `<name>.xml`. **Not** `Open Project`.
2. A Sequence opens. Project panel shows one source clip per unique asset.
3. Clips should be online automatically for all collected assets.
4. If any show as Offline: right-click → **Link Media…** → navigate to the
   `Relink root` path from `relink_guide.md` → Premiere auto-links the rest.

---

## Portable package output

```
out_collect/0519V/
├── 0519V.xml
├── 0519V.package_summary.txt
├── 0519V.relink_guide.md
├── 0519V.report.md
├── 0519V.manifest.json
├── 0519V.offline.md              ← (when assets couldn't be found)
└── media/
    ├── video/
    │   ├── 1034:5282281359605774.MP4
    │   └── 1034:5287675846918209.MP4
    ├── music/
    │   └── 5a24a7e2eb1672953b926de5b8429eb6.m4a   ← extension normalized
    └── sfx/
        ├── 229f88e6452098f686f43df9309b1acc.m4a
        └── 7280126e481ab565481e5ef464d85365.m4a
```

*Note: `media/audio/` is absent because the only audio reference was a video-file
split (embedded audio reuse) — the MP4 in `media/video/` serves both tracks.*

> **Screenshot placeholder** — Premiere Project panel showing reconstructed
> source clips (one per unique asset), Sequence on timeline. *(To be added after
> next creator validation session.)*

---

## Other subcommands

### convert — XML only (no media copy)

```bash
python3 -m cutsmith convert "/path/to/draft_info.json" \
  -o ./out \
  -s "/path/to/footage" \
  -n my_sequence
```

Produces `my_sequence.xml` + `my_sequence.report.md`. Use when you just want
the XML and will manage media paths manually.

### export-srt — export captions to SRT

```bash
python3 -m cutsmith export-srt "/path/to/CapCut/project" -o ./captions.srt
```

Exports all caption entries to SRT. Import into Premiere via
`File → Import → Captions`. Supports Pattern A (top-level texts) and
Pattern B (nested content segments).

### scan-assets — asset inventory

```bash
python3 -m cutsmith scan-assets "/path/to/CapCut/project" -o ./scan_out
```

Produces `<name>.manifest.json` + `<name>.scan.md` listing every material
(video, audio, music, SFX, images, stickers, effects, filters) with online /
offline / cached status and file sizes.

---

## Tested against real-world projects

| Type | Sample | Shape |
|---|---|---|
| Single-cut | `0509` | 151.4s slice · 154 ignored captions |
| Multi-cut | `cutsmith` | 7-cut V1 · V2 overlay · BGM · SFX · 0 unsupported |
| Stress-test | `cutsmith2` | All of the above + 0.640× speed · captions · stickers · transitions |
| Vertical full-stress | `0519V` | 1080×1920 · 7 video tracks · 0.5× + 2.0× speed · speed_curve · 8-cue subtitles |
| Vertical multi-speed | `0519V2` | 1080×1920 · 2.0×/0.5×/0.5× clips · 33 auto-captions · collect dedup |

`collect` validated on: `0509`, `cutsmith`, `0519V`, `0519V2`.

---

## Supported features

### Fully supported

| Feature | Notes |
|---|---|
| Cuts (in / out / timeline position) | Per-frame accuracy |
| Multi-track video (V1, V2, …) | Vertical (1080×1920) included |
| Multi-track audio (A1, A2, …) | BGM, voiceover, SFX |
| Premiere master clip reconstruction | `<clip id="masterclip-…">` at xmeml root |
| Relink-via-parent-folder | `<masterclipid>` back-refs in every clipitem |
| Constant speed (0.5×, 2×) | Explicit FCP7 `timeremap` filter; Premiere shows 49.91% / 200% |
| Portable media package | Physically copies to `media/`, rewrites pathurls |
| Embedded audio dedup | Video-split audio reuses `media/video/` — no MP4 in `media/audio/` |
| Extension normalization | Magic-byte detection corrects cache file extensions |
| Asset manifest JSON | `collected_root`, `relink_root_hint`, per-entry stats |
| Subtitle export (export-srt) | Pattern A + B |
| Schema-drift inspection | `inspect` surfaces unknown fields after CapCut updates |

### Partially supported

| Feature | What works | What doesn't |
|---|---|---|
| Constant speed clips | Timeline slot, source in/out, Speed/Duration in Premiere | Variable speed curves play at 1.0× |
| Embedded video audio | Reuses video copy, no duplicate file | — |
| Windows paths on macOS | Basename matching via `--search-root` | Requires explicit `-s`; no auto-discovery |

### Ignored safely (reported, not exported)

Subtitles / captions · Stickers · Transitions · Filters · Effects · HSL ·
Color wheels · Material animations · Vocal separations · Loudness · Beat sync ·
Keyframe animations · Canvas overrides · Speed curves

Each is named in the report with its segment timing so you know what to rebuild.

---

## Project layout

```
cutsmith/
├── ir/          # canonical Timeline IR
├── reader/      # CapCut draft_info.json → IR
├── detect/      # triage: app / version / encryption / supported_status
├── inspect/     # schema-drift detection (independent of reader)
├── resolver/    # asset path resolution + offline placeholders
├── scanner/     # asset manifest + classification
├── subtitle/    # SRT export
├── collector/   # v0.3 collect: copy + relink + package docs
├── writer/      # IR → FCP7 XML
├── report/      # compatibility_report.md generation
├── bridge.py    # high-level pipeline
└── __main__.py  # CLI entry point
```

Each layer is independently testable. Adding an FCPXML or Resolve writer
won't touch the reader. `inspect` doesn't call `reader` — it parses JSON
independently so schema bugs in the reader don't block triage.

---

## Tests

```bash
python3 -m unittest discover -s tests
```

**276 tests** as of v0.3.6-alpha:

- Pipeline smoke (convert + collect integration)
- Writer: audio contract, speed filter (timeremap), master clip structure
- Speed filter: 12 tests covering 0.5×/2×/no-change/rounding/audio/video
- Embedded audio reuse: 15 tests
- Collector: dedup, offline, path override, extension normalization
- Package summary + relink guide output
- Manifest v0.3.4 fields
- Subtitle export (Pattern A + B)
- Asset manifest and classification
- Inspect schema drift

---

## Roadmap

- **v0.3 ✅** — collect: physical copy + relink. Validated.
- **v0.3.3 ✅** — Premiere master clip reconstruction + constant speed (timeremap).
- **v0.3.5 ✅** — package_summary.txt · rich CLI · default `-o` · `--open`.
- **v0.3.6 ✅** — embedded audio dedup (video-split shares one file).
- **Research** — FCPXML output, DaVinci Resolve XML, keyframe animations,
  CapCut Mobile fixture coverage, variable speed curve reconstruction.

---

## Legal / interoperability notice

CutSmith is an **interoperability and workflow portability tool** intended for
creators working with their own projects and media.

- CutSmith reads `draft_info.json`, a plaintext file CapCut writes into the
  user's own filesystem. It does not modify CapCut binaries or hook into the
  CapCut process.
- CutSmith does not bypass, circumvent, or attempt to decrypt any form of
  DRM or encryption. Drafts that are detected as encrypted are refused; no
  decryption is attempted.
- CutSmith copies files the user already has access to on their own machine,
  into a portable package they control.
- **Third-party asset licensing**: some assets bundled or cached by CapCut —
  including music library tracks, SFX, and sticker packs — may be subject to
  CapCut's or third-party licensors' terms. Copying these files into a
  portable package does not transfer any usage rights. Users are responsible
  for ensuring they have the rights to use exported assets outside the CapCut
  ecosystem, particularly for published or commercially distributed content.
- CutSmith has no affiliation with ByteDance, CapCut, or TikTok.

---

## Repository

- GitHub: <https://github.com/CutSmithIO/cutsmith-timeline-bridge>
- Changelog: [`CHANGELOG.md`](CHANGELOG.md)
- Creator beta guide: [`docs/creator_beta.md`](docs/creator_beta.md)
- Known limitations: [`docs/known_limitations.md`](docs/known_limitations.md)
- Supported features matrix: [`docs/supported_features_matrix.md`](docs/supported_features_matrix.md)
- 中文文档: [`README.zh-CN.md`](README.zh-CN.md)

## License

MIT.
