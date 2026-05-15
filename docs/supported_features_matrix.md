# Supported Features Matrix — v0.1.1 alpha

## Validation scope

**Validated**: CapCut Desktop **167.0.0**, `modern_plaintext` schema
(`schema_version = 360000`).

Three real projects converted end-to-end without manual intervention:
single-cut (`0509`), multicut (`cutsmith`), and stress-test (`cutsmith2`).
See `tests/fixtures/real_world/sample_manifest.json`.

Other apps / versions are best-effort — the reader's structural assumptions
should generalize, but no other configuration has been confirmed against
a real draft.

---

## Status legend

| Status | What it means |
|---|---|
| ✅ Fully supported | Feature round-trips into Premiere exactly as it was in CapCut. |
| ◐ Partially supported | Feature is preserved but with caveats; check the report's `Features not exported` section and `docs/known_limitations.md`. |
| ⊘ Ignored safely | Feature is recognised, named in the report, and intentionally not exported. Premiere imports the timeline without it; rebuild manually if needed. |
| ✗ Unsupported | Feature is not handled at all. May be missing from the report (we didn't recognise it) or block the entire conversion. |

---

## ✅ Fully supported

| Feature | Notes |
|---|---|
| Sequence frame rate (NDF) | 24 / 25 / 30 / 60 |
| Sequence frame rate (NTSC) | 23.976 / 29.97 / 59.94, detected within 0.02 tolerance |
| Sequence resolution | Read from `canvas_config.width / height`; default 1920×1080 |
| Video clip cuts (in / out / timeline start) | Per-frame accuracy verified against 7-cut samples |
| Multi-track video order | V1, V2, V3… preserved as separate FCP7 video tracks |
| Multi-track audio order | A1, A2, A3… preserved as separate FCP7 audio tracks |
| Video overlay (V2+) | Timeline start and clip-source slot independently preserved |
| Independent audio tracks | BGM, voiceover, SFX — each on its own track at correct timing |
| Audio component of imported videos | If CapCut split video-with-audio into a separate `materials.audios` entry and placed it on an explicit audio track, it round-trips correctly |
| Per-clip constant volume | Emitted as FCP7 `<filter>` Audio Levels when ≠ 1.0 |
| Per-clip constant opacity | Read from CapCut's `clip.alpha` |
| Media path resolution | Absolute paths preserved when accessible; otherwise scanned through `--search-root` |
| Offline media fallback | Unresolved files emit `file:///OFFLINE/<name>` URLs so Premiere's `Link Media` workflow works in bulk |
| `<file>` dedup | Same source referenced by multiple clipitems emits one body and id-only stubs for the rest |
| Schema-drift visibility | `inspect` enumerates unknown fields so creators can flag schema-shift quickly after a CapCut update |
| Sequence name auto-derivation | Walks up past `Timelines/<UUID>/` to find the human-named project dir |
| Compatibility report | `*.report.md` accompanies every export with categorised unsupported items |

---

## ◐ Partially supported

| Feature | What works | What doesn't |
|---|---|---|
| Variable speed (constant ramp) | Timeline slot uses `target_dur`, source range uses `source_timerange`, downstream clips don't drift. XML's `end-start ≠ out-in` is left for Premiere to interpret as implied speed. | No explicit Time Remapping `<filter>` is emitted, so the user can override by setting Speed to 100% in PR. Premiere's auto-interpretation of the implied speed is **assumed** to work — verify against `docs/creator_validation_checklist.md` Sample 3. |
| Audio of imported videos (when CapCut left no separate audio track) | The report flags video clips whose source has embedded audio that's not on any track. | The audio itself is not emitted. Premiere imports the video silently. User must re-attach in CapCut or link audio manually in PR. |
| Windows-formatted paths on macOS | Drive-stripped basename matching against `--search-root` directories. | Requires explicit search roots; cross-platform conversion without `-s` will land all clips offline. |

---

## ⊘ Ignored safely (reported, not exported)

These appear in the report's `Features not exported` section with the
specific category label. Premiere imports the timeline without them and
the report tells the user what was dropped (with segment timing when
known) so manual rebuild is feasible.

### Visual

| Category label | Source |
|---|---|
| `transition` | `materials.transitions` referenced from a segment |
| `filter` | `materials.filters` referenced from a segment, or whole `filter` track |
| `effect` | `materials.effects` referenced from a segment |
| `video_effect` | `materials.video_effects` referenced from a segment |
| `mask` | `materials.common_mask` |
| `chroma_key` | `materials.chromas` |
| `color_curve` | `materials.color_curves` |
| `hsl` / `hsl_curve` | `materials.hsl` / `materials.hsl_curves` |
| `color_wheel` / `log_color_wheel` | primary / log color wheels |
| `video_stroke` / `video_shadow` / `video_radius` | stylistic adjustments |
| `plugin_effect` | `materials.plugin_effects` |
| `material_animation` | `materials.material_animations` with non-empty `animations[]` |
| `sticker` | `materials.stickers` and the entire `sticker` track |
| `text` | `materials.texts` and the entire `text` track (use CapCut's SRT export) |
| `keyframe` | Segment-level `keyframe_refs` for motion/scale/rotation/opacity |
| `canvas_override` | `materials.canvases` with non-empty `color` or `image` |

### Audio

| Category label | Source |
|---|---|
| `audio_effect` | `materials.audio_effects` |
| `audio_fade` | `materials.audio_fades` |
| `audio_balance` | `materials.audio_balances` |
| `audio_panning` | `materials.audio_pannings` |
| `audio_pitch_shift` | `materials.audio_pitch_shifts` |
| `vocal_separation` | `materials.vocal_separations` with `choice ≠ 0` |
| `loudness` | `materials.loudnesses` with `enable = true` |
| `beat_sync` | `materials.beats` with non-default state |

### Time / speed

| Category label | Source |
|---|---|
| `speed` | Per-segment speed change reported at segment level (segment.speed ≠ 1.0 or duration delta > 1ms) |
| `speed_curve` | `materials.speeds` referenced from a segment with speed ≠ 1.0 or non-null `curve_speed` |

### Bookkeeping ("benign refs") — NOT reported

These exist as `extra_material_refs` in every segment by default. They
are NOT surfaced in the report because they don't represent user
intent:

- `placeholder_infos` (always benign)
- `canvases` with empty `color` and `image`
- `sound_channel_mappings` with `is_config_open = false` and `audio_channel_mapping = 0`
- `material_colors` with `is_color_clip = false` and `is_gradient = false`
- `loudnesses` with `enable = false`
- `beats` with neither `enable_ai_beats` nor `user_beats`
- `vocal_separations` with `choice = 0`
- `material_animations` with empty `animations[]`
- `speeds` with `speed = 1.0` and no `curve_speed`

If you find a CapCut feature that should be reported but isn't, the
classifier table is in `cutsmith/reader/jianying_pro.py` at
`_CONDITIONAL_REF_PREDICATES`.

---

## ✗ Unsupported

| Feature | Status | Replacement |
|---|---|---|
| 现代版剪映 PC ≥ 75.0.0 encrypted drafts | Detected and refused | Use CapCut Desktop / CapCut Mobile / older 剪映 builds whose drafts are plaintext |
| FCPXML output (Final Cut Pro X / 11) | Planned v0.2 | Use FCP7 XML; FCP imports it (with auto-conversion) |
| DaVinci Resolve XML | Not planned for v0.1 / v0.2 | Resolve can import FCP7 XML directly but path / rate quirks are untested — proceed with caution |
| Explicit Time Remapping filter for variable speed | Planned v0.2 | v0.1.1 relies on implicit speed via XML mismatch (see "Partially supported") |
| Speed ramps (curve speed) | Reported as `speed_curve`, dropped | Manual Time Remap in Premiere |
| Sub-draft / compound clips (`materials.drafts`) | Not parsed | Flatten in CapCut before exporting the draft |
| Multi-language captions | Not parsed | Export SRT per language from CapCut |
| Digital humans / AI-generated content placeholders | Not parsed | Replace with conventional clips before drafting |

---

## What's not in this matrix

If a CapCut feature isn't listed here, it falls into one of three
buckets:

1. **The reader hasn't encountered it yet.** Run `python3 -m cutsmith inspect`
   on your draft — `unknown_fields.json` will surface anything CutSmith
   doesn't know about.
2. **CutSmith silently dropped it as `unknown_extra_ref`.** Search the
   `.report.md` for that label — if present, it's an extra_material_ref
   to a category the classifier doesn't have a rule for. Add a rule in
   `cutsmith/reader/jianying_pro.py:_CONDITIONAL_REF_PREDICATES` or
   `_ALWAYS_REAL_REF_CATEGORIES`.
3. **It's outside v0.1 scope.** See `docs/known_limitations.md` for
   what's deliberately deferred.

This matrix gets updated as new real-world samples land in the
fixture manifest.
