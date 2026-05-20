# CutSmith Compatibility Report — cutsmith2

Source: CapCut/JianyingPro draft

Target: Premiere Pro (via FCP7 XML)

Output: `cutsmith2.xml`


## Sequence
- Frame size: **1920 × 1080**
- Frame rate: **30.0** (NDF)
- Audio: 48000 Hz, 2 ch

## Tracks migrated
- **V1** (video): 7 clip(s)
- **V2** (video): 2 clip(s)
- **A1** (audio): 2 clip(s)
- **A2** (audio): 1 clip(s)

_Note: 8 video clip(s) contain embedded audio that was not exported on a separate audio track. This is normal when the project uses detached audio, an external BGM, or the original sound was muted in CapCut. If you intended the original audio to play, re-attach it inside CapCut or link the media's audio in Premiere._

## Media linking
- Total assets: **12**
- Linked (path existed as-is): 12
- Linked (found via search root): 0
- **Offline / unresolved: 0**

## Features not exported
**Summary:**
- `text`: 3 occurrence(s)
- `video_effect`: 1 occurrence(s)
- `effect`: 1 occurrence(s)
- `hsl`: 1 occurrence(s)
- `loudness`: 1 occurrence(s)
- `speed`: 1 occurrence(s)

**Details:**
- (text) text material '8E649A90-FC03-4AF6-9927-3225BA61A3D9' present in draft but not exported (v0.1 scope)
- (text) text material '339ECC4C-B62B-4230-857D-3964C4730AD2' present in draft but not exported (v0.1 scope)
- (video_effect) [V1] @ 0.00s video_effect 'Card Aura' on segment 4CD8C853-CC2C-4380-B64B-3B220E775041 — not exported (v0.1 scope)
- (effect) [V1] @ 19.40s effect 'brightness' on segment 6A5691D6-A22A-4507-8F80-145A94BA59DA — not exported (v0.1 scope)
- (hsl) [V1] @ 19.40s hsl 'hsl' on segment 6A5691D6-A22A-4507-8F80-145A94BA59DA — not exported (v0.1 scope)
- (loudness) [V1] @ 26.73s loudness 'loudness' on segment DA4B3099-B2D3-4542-AAAB-BA383D33982F — not exported (v0.1 scope)
- (speed) [V2] @ 2.33s segment AF3A0ECC-0AAF-441E-ADE0-58E2CEA55428 has speed=0.640 (source=8833333us, target=13800000us); timeline slot preserved; Premiere shows 100% — apply Speed/Duration manually
- (text) 'text' track with 2 segment(s) skipped (v0.1 scope)

## Suggested next steps in Premiere
1. Open the `.xml` via **File → Import** (not Open Project).
2. Speed-changed clips: timeline duration is preserved but Premiere shows these clips at 100% speed — native speed is NOT reconstructed. For each flagged segment, right-click in Premiere → Speed/Duration… and enter the speed value shown in the report above, or use Effect Controls → Time Remapping to ramp manually.
3. Transitions, filters, and effects from CapCut don't round-trip — they were dropped. Reapply Premiere's native equivalents.
4. Text/captions weren't exported. If you need them, export an SRT from CapCut (File → Export → Subtitle) and import it into Premiere on a Captions track.

## Collect package

| | Count |
|---|---|
| Assets copied | **10** |
| Shared (same file, no extra copy) | 2 |
| Extension normalized | 1 |
| Offline (not copied) | 0 |
| Report-only (proprietary) | 2 |
| Total copied size | 216.6 MB |

### Extension normalization

The following files had incorrect or missing extensions in the CapCut cache. Extensions were corrected based on file magic bytes so Premiere can open them directly.

| Original filename | Collected as | Detected type |
|---|---|---|
| `ec26041d833dd78bc1a88eb9eca84b71.mp3` | `ec26041d833dd78bc1a88eb9eca84b71.m4a` | `.m4a` |

**CapCut proprietary assets** (effects, transitions, filters, stickers) are **not portable** — they cannot be transferred outside CapCut. Rebuild them using Premiere's native equivalents.

**Third-party asset licensing**: music tracks, SFX, and sticker assets copied from the CapCut cache may be subject to CapCut's or third-party licensors' terms. Copying them into a portable package does not transfer usage rights. Verify distribution rights before publishing content that includes CapCut library assets, particularly for commercial use.

**Speed-changed clips**: CutSmith emits an explicit FCP7 `timeremap` filter so Premiere reconstructs Speed/Duration on import (e.g. 200%, 49.91%). No manual adjustment is needed. Variable-speed curves (`speed_curve`) are report-only — the clip plays at 1.0× in Premiere.

**Speed trim boundary (known edge case)**: a 2× clip that exhausts its source file will show wavy trim handles in Premiere — this is expected, not a CutSmith bug. The exported timeline slot is correct; there are simply no additional source frames available. See `cutsmith2.relink_guide.md` for details.

See `cutsmith2.offline.md` for all unresolved assets and suggested actions.

See `cutsmith2.relink_guide.md` for Premiere import and relink instructions.
