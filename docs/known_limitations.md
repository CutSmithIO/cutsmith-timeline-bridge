# Known Limitations — v0.3.3

What CutSmith does NOT do, and the caveats that apply to what it does do.
Read this before filing a bug or before promising a result to a creator.

## Schema / app coverage

### Validated

- **CapCut Desktop 167.0.0** (`new_version = "167.0.0"`,
  `schema_version = 360000`, modern_plaintext layout) — four real
  projects converted end-to-end and registered in
  `tests/fixtures/real_world/sample_manifest.json`, including
  `0519V` (capcut-desktop-vertical-full-stress): vertical 1080×1920,
  7-track multi-layer, 0.5× + 2.0× constant speed clips, speed_curve,
  stickers, transitions, effects, filters, subtitles.

### Best-effort (not yet end-to-end verified by fixtures)

- Older CapCut Desktop builds with the legacy `draft_content.json` layout.
- CapCut Mobile draft exports. The reader's schema assumptions came from
  desktop builds; mobile drafts may have additional/missing fields.
- 剪映 PC (Chinese build) before version 75.0.0, which still ships
  plaintext drafts.

### Explicitly NOT supported

- **现代版剪映 PC ≥ 75.0.0** (`new_version = "75.0.0"` or later, nested
  `Timelines/<UUID>/draft_info.json` layout, base64-encrypted content).
  The `detect` command identifies these and refuses gracefully with
  `supported_status: unsupported_encrypted`. Decryption is not on the
  v0.1 / v0.2 path — see `docs/notes/modern_jianying_75_storage.md`.

If you have a sample that doesn't behave the way CutSmith expects:

```bash
python3 -m cutsmith detect /path/to/project --json
python3 -m cutsmith inspect /path/to/draft.json -o ./inspect_out
```

The `unknown_fields.json` count from `inspect` is the most useful number
for the bug report — it quantifies how much the schema differs from what
the reader assumes.

## Time-and-speed handling

### Constant-speed clips — native Premiere speed reconstructed (v0.3.3)

**Confirmed working (Premiere import test, 2026-05-19):**

CutSmith v0.3.3 emits an explicit FCP7 `<filter><effectid>timeremap</effectid>`
on every clip where `source_range ≠ timeline_slot`. Premiere recognises this and
applies the correct Speed/Duration on import:
- 2.0× clip → Premiere shows 200%
- 0.5× clip → Premiere shows 49.91% / 49.96% (µs rounding, ≈ 50%)

The timeline slot is always `target_timerange.duration` — downstream clips
don't drift. Source trim bounds are correct: `<clipitem><duration>` = source
range used, `<file><duration>` = total source file available.

**What the editor should verify manually:** Clips flagged as `speed` in the
report carry explicit speed metadata in the XML. Premiere imports them with the
correct Speed/Duration value automatically, but confirming visually in the
Effect Controls panel takes one second and is worth doing before delivery.

### Speed ramps (variable curves) — dropped

If a CapCut speed material has a non-null `curve_speed` (variable speed
over the clip's duration), the curve is reported as `speed_curve` in the
unsupported list and dropped. Only the constant speed factor (if any)
participates in the implicit timeline encoding above.

### Sub-millisecond rounding tolerance

`reader/jianying_pro.py` treats `|target_dur − source_dur| ≤ 1000µs` as
"no speed change" when `segment.speed == 1.0`. CapCut writes µs-level
rounding noise even on unedited clips; without the tolerance every clip
would falsely report a speed change. The 1ms threshold is well under one
frame at 30fps and was chosen empirically; it may need revisiting for
high-framerate sequences (120fps NTSC: one frame ≈ 8.3ms — still fine).

### NTSC framerate detection

`SequenceSettings.is_ntsc` uses a 0.02 tolerance band around the canonical
NTSC rates (23.976, 29.97, 59.94). CapCut stringifies 29.97 inconsistently
across versions — sometimes `29.97`, sometimes `29.97002997…`. The
tolerance absorbs both. A user shooting at exactly 30.000 stays NDF.

## Media and assets

### Windows paths on macOS

If a draft was created on Windows and you're converting on macOS, the
absolute path in `materials.videos[].path` will start with `C:\…`. The
reader strips drive letters and falls back to basename matching against
the `--search-root` directories you supply. **This means cross-platform
conversion almost always requires at least one `-s` flag.**

### Embedded audio of video clips

If a CapCut video file has audio but no audio track in the draft
references that audio (an unusual but valid state — user "detached
audio" and didn't replace it, or used external BGM), the writer does
**not** synthesize an audio track for it. Premiere will import the
video silently.

The report surfaces this with a neutral Note in the Tracks section. If
the user actually intended the original audio, they must re-attach it
inside CapCut and re-export, or link the file's audio in Premiere
manually.

> **v0.1.1 may drop embedded audio when CapCut keeps original sound on
> video clips without creating explicit audio tracks. v0.1.2 will restore
> this via Smart Embedded Audio Fallback** — a reader-side fallback that
> derives an audio track from a video asset only when no explicit audio
> track covers the same source over the same target time range, with
> coverage decided per-segment (not per-track) and mute detected via
> `segment.volume == 0.0`. The writer stays a pure IR→XML transform; the
> derived track will be tagged in the IR (`Track.origin =
> DERIVED_EMBEDDED`) and labeled `A{n} (auto-derived)` in the report.

### CapCut splits video and audio per import

A normal CapCut workflow (drag a video-with-audio into the timeline)
creates two `materials` entries pointing to the same file: one under
`materials.videos`, one under `materials.audios`. The reader maps both
correctly and the writer emits exactly one audio track for the audio
side. **Auto-extracting audio from video assets has been removed in
v0.1.1** — that was producing duplicate audio on import. If you're seeing
a single audio track in PR for an imported video that had audio, this is
intentional.

## What's silently dropped

These features appear in the report's "Features not exported" section,
named when their CapCut material has a readable label:

- Captions / text tracks (use CapCut's SRT export, import to PR Captions).
- Stickers, transitions, filters, effects, video_effects, audio_effects.
- HSL adjustments, color curves, color wheels (primary/log), masks,
  chroma key, video strokes/shadows/radius, plugin effects.
- Material animations (fade-in / fade-out / etc.) when non-empty.
- Vocal separations when `choice ≠ 0`.
- Loudness adjustments when `enable = true`.
- Beat-sync data, canvas overrides, material color overrides.
- Keyframe animations on position / scale / rotation / opacity.
- Filter tracks (whole-track filters applied across multiple segments).

A material that lives in `materials.<category>` but isn't referenced by
any segment is **silently skipped** — its presence in the project is
considered immaterial. This is a deliberate trade-off: false negatives
(missing an unused material) are preferred to false positives flooding
the report with bookkeeping noise.

## Sequence naming

If `draft_path.stem == "draft_info"` (the modern layout), the reader
walks up the path skipping UUID directories and the literal name
`Timelines` to find the first human-named parent. So:

- `~/Movies/CapCut/.../cutsmith2/Timelines/<UUID>/draft_info.json`
  → `cutsmith2`
- `~/Movies/CapCut/.../0509/draft_info.json`
  → `0509`

You can always override with `-n / --name` on `convert`.

If the path's ancestors are all UUID-like, the fallback drops back to
`"draft_info"`. This shouldn't happen in practice.

## What CutSmith assumes about FCP7 XML readers

The writer targets Premiere Pro's FCP7 XML dialect. Behaviour has been
spot-checked against PR 2024 builds; other consumers may differ:

- **DaVinci Resolve**: not tested. Resolve's FCP7 importer is known to be
  pickier about clipitem rate elements and stricter on path URL encoding.
- **Final Cut Pro 7 / Studio**: not tested. The XML is structurally valid
  per the FCP7 Interchange spec.
- **FCPXML targets (Final Cut Pro X / 11)**: not supported. FCP7 XML
  loaded into modern Final Cut Pro is auto-converted by FCP and may lose
  fidelity in the round-trip.

## collect — portability limits

### CapCut proprietary assets are not portable

CapCut stickers, effects, transitions, and filters are stored inside the
CapCut application bundle or downloaded to an app-private cache. They cannot
be extracted or transferred to Premiere independently.

**What happens in `collect`:**
- These assets are classified as `capcut_effect`, `capcut_font`, or `UNKNOWN`.
- They are listed in the `collect` section of the report and, if offline, in
  `<stem>.offline.md` with a suggested rebuild action.
- They are **not copied** to `media/`.
- The XML that Premiere receives has no reference to them (they were already
  ignored in the convert step as `⊘ Ignored safely`).

**What to do:** rebuild in Premiere using native effects, LUTs, third-party
plugins, or downloaded font files.

### CapCut music licensing

Tracks from the CapCut/TikTok music library are copied to `media/music/`
when online. They are subject to CapCut / TikTok licensing terms. Verify
distribution rights before publishing content that includes them.

### Offline user assets

If a user media file cannot be found (not on disk, wrong path, Windows path on
macOS), it is listed in `<stem>.offline.md` but not copied. After XML import
into Premiere, use `Link Media` to relink those clips.

---

## Version table

| Feature | v0.1 / v0.2 / v0.3 | Notes |
|---|---|---|
| CapCut Desktop modern_plaintext → PR | ✅ | Validated on CapCut 167.0.0 |
| Asset manifest (scan-assets) | ✅ v0.2 | |
| Subtitle extraction (export-srt) | ✅ v0.2 | Pattern A + B |
| collect / relink (media gather) | ✅ v0.3 | Validated on `0509`, `cutsmith`, `0519V`, `0519V2` |
| Premiere master clip reconstruction | ✅ v0.3.3 | `<clip id="masterclip-…">` at xmeml root; Project panel entries + relink-via-parent-folder confirmed |
| CapCut proprietary effects / transitions / filters | report-only, not collectable | Not portable outside CapCut |
| CapCut Mobile / legacy plaintext → PR | best-effort | No fixture confirmed |
| FCPXML output (Final Cut Pro X / 11) | not planned | |
| Keyframe animations | not planned | |
| Constant speed reconstruction | ✅ v0.3.3 | Explicit `timeremap` filter emitted; Premiere imports 200%, 49.91%, etc. confirmed in-app. |
| Speed ramps (variable curves) | report-only | speed_curve logged, clip plays at 1.0× |
| DaVinci Resolve XML | not planned | |
| Modern encrypted Jianying drafts | ✗ not planned | Detected and refused gracefully |

## Reporting bugs

Useful artefacts to include:

1. `python3 -m cutsmith detect <path> --json` output.
2. `python3 -m cutsmith inspect <draft> -o ./inspect_out`'s
   `unknown_fields.json` and `schema_summary.json`.
3. `python3 scripts/ir_diag.py <draft> -o ./ir_out`'s `ir_summary.json`.
4. The `<sample>.report.md` produced by `convert`.
5. Premiere build number and macOS/Windows version.
6. For a wrong-playback report: screen recording showing what CapCut
   showed vs. what PR shows, with timecodes visible.

`inspect`'s output redacts paths to basenames by default (drop the
`--raw-paths` flag if you want absolute paths in the bug report —
otherwise you'll be safer from accidentally sharing usernames).
