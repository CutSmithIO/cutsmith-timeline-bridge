# Creator Validation Checklist — v0.1.1 alpha

This is the manual-verification protocol for confirming a CutSmith export
opens correctly in Premiere Pro. CLI tests pin structural correctness
(frame counts, file references, etc.); only a human can answer "does this
look like what CapCut showed me?"

Run the three samples in the order below. Each builds on the last —
if step 1 fails, don't bother with the rest until that's understood.

---

## Before you start

- **Premiere Pro 2024 or 2025** (older builds also work for FCP7 XML; this
  is just what's been used during development).
- The three `.xml` files from `out_convert/` (produced by `python3 -m cutsmith convert ...`).
- Each sample's source media accessible at the path baked into the XML
  (the `.report.md` will tell you if anything is offline).
- About 20 minutes per sample, mostly for scrubbing.

**Import procedure (every sample):**
1. New Premiere project, any preset.
2. `File → Import…`, pick the `.xml`. **Do not** use `Open Project`.
3. Premiere creates a Sequence and Project items. Open the Sequence.
4. Open the matching `*.report.md` side-by-side; tick items as you confirm
   them.

If a clip imports as **Offline**, right-click it in the Project panel →
`Link Media…` → pick any matching file. Premiere will auto-link the rest
by name from the same folder.

---

## Sample 1 — `cutsmith.xml` (clean multicut)

**Why first**: zero unsupported items. If anything here looks wrong, the
bug is in CutSmith's core path — don't waste time on stress tests yet.

**Expected shape** (per `cutsmith.report.md`):

- 60.000s sequence at 30 fps NDF, 1920×1080
- V1: 7 clips, butt-cut to 60s
- V2: 1 clip (`image.png`) at 0.000s–5.000s overlay
- A1: 1 clip (BGM, 0–60s)
- A2: 1 clip (SFX hit, 22.633s–30.600s)

**Checklist:**

- [ ] Sequence preset matches: 30 fps NDF, 1920×1080.
- [ ] V1 total length is exactly 60.000s; no gaps or overlapping clipitems
      anywhere on the track.
- [ ] V1 cuts land at the seven points listed in the report
      (10.567s, 19.400s, 26.733s, 40.533s, 47.067s, 56.833s, 60.000s).
- [ ] V2 overlay appears at 0.000s and ends at exactly 5.000s.
- [ ] A1 BGM plays for the full 60s without dropping out at cut points.
- [ ] A2 SFX hit lines up with the moment expected (22.633s in CapCut).
- [ ] No phantom A3/A4 tracks (this would be the pre-v0.1.1 double-audio bug).
- [ ] Playback works: scrub through; no offline media markers.

**If anything fails here:** stop, capture the failing clipitem's start/end
frames vs. what Premiere shows, and check `out_ir/capcut_multicut/ir_summary.json`
to see whether the IR was wrong or the writer was.

---

## Sample 2 — `0509.xml` (long take + ignored captions)

**Why second**: a single-cut 151.4s timeline with 154 caption materials and
2 caption tracks. Validates that the long-form pipeline doesn't choke and
that text tracks really stay out of the XML.

**Expected shape** (per `0509.report.md`):

- 151.433s sequence at 30 fps NDF, 1920×1080
- V1: 1 clip, full length (source 141.433s–292.867s of a 25-min mp4)
- A1: 1 clip, full length
- No V2, no other audio tracks
- 156 unsupported items reported (154 text materials + 2 text tracks),
  all in the report's "Features not exported" section

**Checklist:**

- [ ] Sequence is exactly 151.433s (4543 frames at 30 fps).
- [ ] V1 has one continuous clip; no extra cuts.
- [ ] Scrub to a moment that had a caption in CapCut — confirm no text
      appears in Premiere (this is intended; captions are deliberately
      dropped, not silently kept somewhere).
- [ ] A1 plays original audio synced with picture.
- [ ] No second audio track playing the same content (no duplicate audio).
- [ ] The `Note: N video clip(s) contain embedded audio…` paragraph in
      the report is the new neutral phrasing, not a `⚠` warning.
- [ ] If you wanted the captions back: open CapCut, export SRT
      (`File → Export → Subtitle`), drop it on a Captions track in
      Premiere. (The report has the same hint.)

**If anything fails here:** the 154-caption count is a stress-load for the
report writer's detail list. The report truncates to the first 50 lines
with `… N more not shown.` — that's expected, not a bug.

---

## Sample 3 — `cutsmith2.xml` (stress test)

**Why third**: every v0.1.1 feature and corner case fires in one draft:
multi-cut + V2 overlay + BGM + SFX + captions + stickers + transitions +
filters + effects + a real variable-speed clip.

This is the most important manual test. Everything that v0.1.1 ships works
**in the XML** (verified by tests); the question is whether Premiere
**interprets** the XML the way CapCut intended.

**Expected shape** (per `cutsmith2.report.md`):

- 60.000s sequence at 30 fps NDF, 1920×1080
- V1: 7 clips (same continuity as sample 1, with effects/transitions on
  some segments — those won't appear in PR)
- V2: 2 clips — one **0.640× speed-changed** clip starting at 2.333s
  (timeline duration 13.800s, source range 8.833s), and an `image.png`
  overlay later
- A1: 2 BGM clips (split by a gap), A2: 1 SFX hit
- 15 unsupported items, each with a specific category (text, sticker,
  transition, video_effect, effect, hsl, loudness, filter, speed,
  speed_curve)

**General checklist:**

- [ ] All 12 media files link successfully (use `-s` search roots from
      the convert command if Offline).
- [ ] Sequence length is 60.000s.
- [ ] V1's seven cuts are continuous; no gaps.
- [ ] V2 first clip (the speed-changed one) starts at exactly 2.333s and
      ends at exactly 11.167s on the timeline (a 13.800s slot).
- [ ] V2 second clip (`image.png`) starts at 47.067s and ends at 56.833s.
- [ ] No captions, stickers, transitions, filters, or HSL effects appear.
      All 15 unsupported items in the report should be absent from the
      visual result.
- [ ] No duplicate audio.

### Critical observation — the speed-changed V2 clip

This is the variable-speed clip. v0.1.1's design is:

- The timeline slot uses **target_dur** (13.800s) so subsequent clips
  align with what CapCut showed.
- The source range stays as **source_timerange** (8.833s of source
  content).
- The writer does NOT add an explicit `<filter>` for Time Remapping.
- The XML's `end-start` (13.800s) thus differs from `out-in` (8.833s).
  Premiere will interpret that ratio as an implied speed factor.

**What you should see in Premiere:**

- [ ] V2.1 occupies 2.333s–11.167s on the timeline (the 13.800s slot —
      not 8.833s).
- [ ] When you select V2.1, the clip's "Speed/Duration" panel
      (`Clip → Speed/Duration…` or right-click on the clip) shows a
      non-100% speed value, approximately **64.0%** (the 8.833/13.800 ratio).
- [ ] Playback shows the source content stretched over 13.8s — visually
      slower than the original.

**If Premiere shows this clip at 100% playing in 8.833s (i.e., the rest of
the V2 slot is empty):** the implicit-speed interpretation didn't trigger.
Report it — this is the assumption the v0.1.1 design hinges on.

**If you want to override the implied speed:**

1. Right-click V2.1 → `Speed/Duration…`
2. Set Speed to 100%, untick "Maintain audio pitch" if needed.
3. The clip will now play at 1.0× for its 8.833s of source content; the
   trailing 4.967s of the 13.800s timeline slot will go empty.

That's the manual override path the report mentions ("re-apply Time
Remapping where flagged"). It's not what most users want, but it's
available.

### Other things to spot-check

- [ ] The two BGM clips on A1 sound continuous across the gap (they're
      slices of the same source file).
- [ ] The SFX on A2 fires at the right beat.
- [ ] Premiere shows no errors in `Window → Events`.

---

## After all three samples

Save your findings somewhere. Useful info to capture:

- Premiere build number (Help → About).
- Which samples worked, which didn't, where exactly.
- Screenshots / screen recording of any anomaly.
- For variable-speed V2.1: confirm the Speed/Duration panel reading.

A reasonable verdict format:

```
Premiere: 2025.x build NNNN
Sample 1 cutsmith.xml      : PASS / PASS-with-notes / FAIL — details
Sample 2 0509.xml          : PASS / PASS-with-notes / FAIL — details
Sample 3 cutsmith2.xml     : PASS / PASS-with-notes / FAIL — details
   Speed clip V2.1         : interpreted as 64% / 100% / other — details
Unexpected behaviour       : …
```

That format keeps follow-up debuggable.

---

## Where to look when something fails

- `out_ir/<sample>/ir_summary.json` — what the reader produced for the IR.
  If the bug is here, it's a reader bug.
- `out_convert/<sample>/<sample>.xml` — the FCP7 output. Compare clipitem
  start/end/in/out frames against what PR shows.
- `out_convert/<sample>/<sample>.report.md` — what CutSmith *thinks* it
  produced. If this doesn't match the XML, that's a report-vs-writer
  desync bug (the kind v0.1.1 fixed once already).
- `docs/known_limitations.md` — check if the behavior is a known caveat
  before filing.
