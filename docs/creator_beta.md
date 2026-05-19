# Creator Beta Guide — v0.3.6-alpha

CutSmith Timeline Bridge is entering **limited creator beta**. This guide
explains what the tool currently does, what it doesn't, and what kinds of
real-world CapCut projects are most useful for validation.

---

## What this tool does

CutSmith converts a CapCut Desktop draft into a **portable Premiere Pro
package**: an XML file plus a `media/` folder containing every user media
file, ready to open in Premiere without hunting for source files.

The core workflow:

```bash
python3 -m cutsmith collect "/path/to/CapCut/project" [--open]
```

Output:

```
out_collect/<project_name>/
├── <name>.xml                 ← drop into Premiere via File → Import
├── <name>.package_summary.txt ← open this first
├── <name>.relink_guide.md     ← Premiere import + relink instructions
├── <name>.report.md           ← what was converted vs. dropped
├── <name>.manifest.json       ← machine-readable asset index
├── <name>.offline.md          ← only if some assets couldn't be found
└── media/
    ├── video/
    ├── audio/
    ├── music/
    ├── sfx/
    └── images/
```

---

## Supported workflows

These are confirmed working end-to-end (CapCut Desktop 167.0.0 →
Premiere Pro 2024/2025):

| Workflow | Status |
|---|---|
| Multi-cut timeline (butt cuts, V1 / V2 overlays) | ✅ Confirmed |
| Independent BGM and SFX audio tracks | ✅ Confirmed |
| Vertical timelines (1080×1920) | ✅ Confirmed |
| Constant speed changes (0.5×, 2×) | ✅ Confirmed — Premiere shows correct % on import |
| Portable media package (collect + relink) | ✅ Confirmed |
| Subtitle extraction to SRT (for reimport to Premiere Captions) | ✅ Confirmed |
| Asset manifest (inventory of all materials) | ✅ Confirmed |
| CapCut cache extension normalization (`.mp3` → `.m4a` etc.) | ✅ Confirmed |
| Embedded audio dedup (video-audio split, no duplicate file) | ✅ Confirmed |
| Project panel source clips (Link Media per-folder) | ✅ Confirmed |

---

## What is NOT supported (intentionally)

These features are **reported but not reconstructed**. The `*.report.md`
tells you exactly which segments are affected so you can rebuild manually.

| Feature | Status | Workaround in Premiere |
|---|---|---|
| Variable speed ramps / speed curves | Report-only — clip plays at 1.0× | Effect Controls → Time Remapping → Velocity |
| CapCut transitions | Report-only — not in XML | Apply Premiere native transitions |
| CapCut filters / HSL / color wheels | Report-only — not in XML | Apply LUTs or Premiere color effects |
| CapCut effects / video effects | Report-only — not in XML | Apply Premiere native effects |
| CapCut stickers | Report-only — not in XML | Import PNG/GIF from asset packs |
| Subtitles / captions (in convert) | Ignored in XML — export separately | Run `export-srt`, import to Premiere Captions track |
| Keyframe animations (position/scale/rotation/opacity) | Not exported | Rebuild in Effect Controls |
| Compound clips / sub-drafts | Not parsed | Flatten in CapCut before exporting |
| Encrypted 剪映 PC ≥ 75.0.0 drafts | Detected and refused — no decryption attempted | Use CapCut Desktop or older 剪映 builds |

---

## What projects are useful for beta validation

The more diverse the CapCut project, the more useful it is. Priority:

### Highest priority (uncovered gaps)

1. **Image overlay projects** — V2 track with PNG/JPG overlay on a video.
   We have one image in the `cutsmith` fixture but dedicated image-heavy
   projects would stress-test the images pipeline.

2. **Voiceover / record audio** — clips recorded inside CapCut
   (`materials.audios` with a recorded audio entry, not a split from video).

3. **Multilingual subtitles** — projects with both Pattern A and Pattern B
   caption layouts, or mixed auto-caption + manual caption.

4. **Long-form projects** — 20+ minute timelines with 100+ clips.
   Validates IR memory use and report truncation behavior.

5. **Multiple source cameras** — projects where the V1 timeline uses footage
   from 3+ different source files. Validates master clip dedup and relink.

### Useful (fills out existing coverage)

6. **Windows-origin drafts on macOS** — `C:\Users\...` paths in the draft;
   validates cross-platform path handling with `--search-root`.

7. **Older CapCut Desktop builds** — any version other than 167.0.0;
   validates schema-drift tolerance.

8. **CapCut Mobile exports** — mobile drafts have a different layout;
   best-effort support, no fixtures confirmed yet.

9. **High-framerate sequences** — 60fps NDF or 60fps NTSC.

10. **Projects heavy on CapCut music library** — validates music licensing
    note and extension normalization on cached music files.

---

## Asset licensing

When `collect` copies music, SFX, or sticker files from the CapCut cache into
`media/`, those files may carry licensing terms set by CapCut or third-party
rights holders. Copying them into a portable package does not transfer any
usage rights.

- **CapCut music / SFX**: subject to CapCut/TikTok licensing terms. Verify
  distribution rights before publishing content that includes them. Tracks
  marked for "commercial use" in CapCut may still have restrictions outside
  the platform.
- **Stickers and overlay graphics**: if the sticker file is locally cached
  and copyable, it will be included in `media/stickers/`. Licensing terms
  vary by pack; check the source before redistribution.
- **Your own footage, voiceover, and images**: no licensing concern from
  CutSmith's side — these are files you own and have already stored locally.

When in doubt, remove the third-party asset from the Premiere project and
replace it with a licensed equivalent.

---

## How to run the tool

```bash
# Clone
git clone https://github.com/CutSmithIO/cutsmith-timeline-bridge.git
cd cutsmith-timeline-bridge

# No pip install needed — standard library only, Python ≥ 3.10

# Triage an unfamiliar project first
python3 -m cutsmith detect "/path/to/CapCut/project"

# Check for schema drift (any unknown fields?)
python3 -m cutsmith inspect "/path/to/CapCut/project" -o ./inspect_out
cat inspect_out/unknown_fields.json   # empty list = reader is up to date

# Collect (convert + copy media + relink)
python3 -m cutsmith collect "/path/to/CapCut/project" --open

# Read the outputs before opening Premiere
open out_collect/<name>/<name>.package_summary.txt
open out_collect/<name>/<name>.report.md
```

---

## Premiere import procedure

1. `File → Import…` → select `<name>.xml`. **Not** `Open Project`.
2. A Sequence appears. Project panel shows one source clip per unique asset.
3. If any clips are Offline:
   - right-click any offline clip → **Link Media…**
   - navigate to `out_collect/<name>/media/`
   - select any one matching file — Premiere auto-links the rest by name.
4. Open `<name>.relink_guide.md` for the exact `media/` path to paste.

---

## Recommended validation checklist

After importing into Premiere, check:

- [ ] Sequence frame rate and resolution match what CapCut showed.
- [ ] V1 cut points are in the right places (scrub and compare to CapCut).
- [ ] Overlays (V2, V3) appear at the correct timeline positions.
- [ ] BGM / SFX tracks are on separate audio tracks and play correctly.
- [ ] No duplicate audio (double playback of the same content).
- [ ] Speed-changed clips show the correct percentage in Effect Controls
      (right-click → Speed/Duration…).
- [ ] Project panel has source clips — not empty.
- [ ] No unexpected Offline clips for assets that should have been collected.
- [ ] `*.report.md` lists the dropped items you expected (effects, transitions,
      etc.) — nothing surprising is missing.

For the speed trim-boundary edge case:
- [ ] Speed clips at 2× that use the full source file may show wavy trim
      handles at the boundary. This is expected — see `relink_guide.md`.

---

## How to report issues

Please open an issue with:

1. `python3 -m cutsmith detect <path> --json` output.
2. `python3 -m cutsmith inspect <path> -o inspect_out` →
   `inspect_out/unknown_fields.json` and `schema_summary.json`.
3. The `<name>.report.md` from `collect` or `convert`.
4. Premiere build number (`Help → About Premiere Pro`).
5. macOS / Windows version.
6. For visual discrepancies: a screen recording or screenshot comparing
   CapCut's timeline to what Premiere shows, with timecodes visible.

**Redact paths before sharing** — `inspect` redacts to basenames by default.
Use `--raw-paths` only if absolute paths are needed for debugging.

---

## Portability expectations

A collected package (`out_collect/<name>/`) is fully self-contained for
online assets:

- Copy the entire `out_collect/<name>/` directory to another machine.
- Open Premiere, `File → Import` the `.xml`.
- If clips are Offline: Link Media → navigate to `media/` in the copied dir.
- The `relink_guide.md` inside has the exact folder path.

Assets that were **offline at collect time** (file not on disk) will still be
offline after the move. Check `<name>.offline.md` for what wasn't collected and why.

CapCut proprietary assets (effects, transitions, filters, stickers, fonts)
are never in the package — rebuild them in Premiere or skip.

---

## Known edge cases

| Edge case | Behavior |
|---|---|
| Speed clip trim boundary | 2× clips at source-file limit show wavy trim handles in Premiere — expected, not a bug |
| Variable speed curves | Only the constant speed factor is exported; the clip plays at 1.0× in Premiere |
| CapCut music licensing | Tracks copied to `media/music/` are subject to CapCut/TikTok terms |
| Windows paths on macOS | Requires explicit `-s` search roots; basename matching used |
| NTSC framerate strings | 29.97 / 29.97002997 both handled via 0.02 tolerance |
| Extension-less cache files | Detected via magic bytes and renamed on copy |

---

## Version tested

- CapCut Desktop **167.0.0** (`schema_version = 360000`, modern_plaintext layout)
- Premiere Pro 2024 / 2025 (FCP7 XML import)
- Python 3.10+ on macOS

Other configurations are best-effort. Run `detect` + `inspect` on any
unfamiliar draft before `collect` to surface schema differences quickly.
