"""Compatibility and migration report generator for CutSmith Timeline Bridge.

The report has one job: tell the user, in plain language, what made it to
Premiere and what didn't. Two audiences:
  - The editor opening the .xml — needs to know what to look for, what to
    manually rebuild.
  - The person debugging an export — needs the raw counts.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path

from cutsmith.ir import Timeline
from cutsmith.resolver import ResolutionStats

# Unsupported-category labels that all share the "rebuild in Premiere"
# suggestion. Kept here (not in the reader) so the report layer owns its
# own grouping of user-facing categories; reader is free to emit more
# specific labels without coordinating with this list.
_EFFECT_LIKE_CATEGORIES = {
    "transition", "filter", "effect",
    "video_effect", "audio_effect", "audio_fade",
    "audio_balance", "audio_panning", "audio_pitch_shift",
    "mask", "chroma_key",
    "color_curve", "hsl", "hsl_curve",
    "color_wheel", "log_color_wheel",
    "video_stroke", "video_shadow", "video_radius",
    "plugin_effect",
    "material_animation", "vocal_separation",
    "canvas_override", "material_color_override",
    "loudness", "beat_sync",
}


def write_report(
    timeline: Timeline,
    resolution: ResolutionStats,
    output_path: str | Path,
    xml_output_path: str | Path | None = None,
) -> Path:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    lines: list[str] = []
    lines.append(f"# CutSmith Migration Report — {timeline.name}\n")
    lines.append("Source: CapCut Desktop / Jianying project (plaintext draft)\n")
    lines.append("Target: Premiere Pro (FCP7 XML + portable media package)\n")
    lines.append(
        "_CutSmith is an independent interoperability tool. "
        "Not affiliated with ByteDance, CapCut, or Jianying._\n"
    )
    if xml_output_path:
        lines.append(f"Output: `{Path(xml_output_path).name}`\n")
    lines.append("")

    _section_sequence(lines, timeline)
    _section_tracks(lines, timeline)
    _section_media(lines, timeline, resolution)
    _section_unsupported(lines, timeline)
    _section_next_steps(lines, timeline, resolution)

    output_path.write_text("\n".join(lines), encoding="utf-8")
    return output_path


def _section_sequence(lines: list[str], timeline: Timeline) -> None:
    s = timeline.settings
    lines.append("## Sequence")
    lines.append(f"- Frame size: **{s.width} × {s.height}**")
    lines.append(f"- Frame rate: **{s.frame_rate}** ({'NTSC' if s.is_ntsc else 'NDF'})")
    lines.append(f"- Audio: {s.sample_rate} Hz, {s.audio_channels} ch")
    lines.append("")


def _section_tracks(lines: list[str], timeline: Timeline) -> None:
    lines.append("## Tracks migrated")
    if not timeline.video_tracks and not timeline.audio_tracks:
        lines.append("_No video or audio tracks found in draft._\n")
        return

    for t in timeline.video_tracks:
        lines.append(f"- **{t.name}** (video): {len(t.clips)} clip(s)"
                     + (" — muted" if t.muted else ""))
    for t in timeline.audio_tracks:
        lines.append(f"- **{t.name}** (audio): {len(t.clips)} clip(s)"
                     + (" — muted" if t.muted else ""))
    lines.append("")

    orphan_clips = _video_clips_with_unexposed_audio(timeline)
    if orphan_clips:
        lines.append(
            f"_Note: {len(orphan_clips)} video clip(s) contain embedded audio "
            f"that was not exported on a separate audio track. This is normal "
            f"when the project uses detached audio, an external BGM, or the "
            f"original sound was muted in CapCut. If you intended the original "
            f"audio to play, re-attach it inside CapCut or link the media's "
            f"audio in Premiere._\n"
        )


def _video_clips_with_unexposed_audio(timeline: Timeline) -> list:
    """Video clips whose source file has audio but no audio track references it.

    Two ways an audio asset can "cover" a video clip's embedded audio:
      1. Same asset_id (rare, but defensible).
      2. Same original_path — the common CapCut case where importing a
         video-with-audio creates two material entries (video + audio)
         pointing at the same file.
    """
    covered_paths: set[str] = set()
    covered_asset_ids: set[str] = set()
    for track in timeline.audio_tracks:
        for clip in track.clips:
            covered_asset_ids.add(clip.asset_id)
            asset = timeline.assets.get(clip.asset_id)
            if asset and asset.original_path:
                covered_paths.add(asset.original_path)

    orphans = []
    for track in timeline.video_tracks:
        for clip in track.clips:
            asset = timeline.assets.get(clip.asset_id)
            if asset is None or not asset.has_audio:
                continue
            if clip.asset_id in covered_asset_ids:
                continue
            if asset.original_path and asset.original_path in covered_paths:
                continue
            orphans.append(clip)
    return orphans


def _section_media(
    lines: list[str],
    timeline: Timeline,
    resolution: ResolutionStats,
) -> None:
    lines.append("## Media linking")
    lines.append(f"- Total assets: **{resolution.total}**")
    lines.append(f"- Linked (path existed as-is): {resolution.resolved_as_is}")
    lines.append(f"- Linked (found via search root): {resolution.resolved_via_search}")
    lines.append(f"- **Offline / unresolved: {resolution.unresolved}**")
    if resolution.missing_assets:
        lines.append("")
        lines.append("Missing files (will appear as offline clips in Premiere):")
        for name in resolution.missing_assets:
            lines.append(f"  - `{name}`")
        lines.append("")
        lines.append("> In Premiere, right-click any offline clip in the "
                     "Project panel → **Link Media** → pick one file, and "
                     "Premiere will auto-resolve the rest from the same folder.")
    lines.append("")


def _section_unsupported(lines: list[str], timeline: Timeline) -> None:
    lines.append("## CapCut-proprietary features — not portable")
    if not timeline.unsupported:
        lines.append("_Nothing flagged. Draft used only v0.1-supported features._\n")
        return

    by_category = Counter(item.category for item in timeline.unsupported)
    lines.append("**Summary:**")
    for cat, count in by_category.most_common():
        lines.append(f"- `{cat}`: {count} occurrence(s)")
    lines.append("")

    # Cap detail listing to avoid runaway reports on heavy drafts.
    MAX_DETAIL = 50
    lines.append("**Details:**")
    for item in timeline.unsupported[:MAX_DETAIL]:
        loc = ""
        if item.track_hint:
            loc += f" [{item.track_hint}]"
        if item.time_hint_us is not None:
            loc += f" @ {item.time_hint_us / 1_000_000:.2f}s"
        lines.append(f"- ({item.category}){loc} {item.detail}")
    if len(timeline.unsupported) > MAX_DETAIL:
        lines.append(f"- … {len(timeline.unsupported) - MAX_DETAIL} more not shown.")
    lines.append("")


def _section_next_steps(
    lines: list[str],
    timeline: Timeline,
    resolution: ResolutionStats,
) -> None:
    lines.append("## Suggested next steps in Premiere")
    steps: list[str] = []
    steps.append("Open the `.xml` via **File → Import** (not Open Project).")
    if resolution.unresolved > 0:
        steps.append("Relink offline clips: select one in Project panel → "
                     "right-click → Link Media → choose any matching file → "
                     "Premiere finds the rest by name.")
    if any(u.category == "speed" for u in timeline.unsupported):
        steps.append(
            "Speed-changed clips: timeline duration is preserved but Premiere "
            "shows these clips at 100% speed — native speed is NOT reconstructed. "
            "For each flagged segment, right-click in Premiere → "
            "Speed/Duration… and enter the speed value shown in the report above, "
            "or use Effect Controls → Time Remapping to ramp manually."
        )
    if any(u.category == "speed_curve" for u in timeline.unsupported):
        steps.append(
            "Variable-speed ramps (speed_curve) were not exported. "
            "The clip plays at 1.0× in Premiere. "
            "Reconstruct using Effect Controls → Time Remapping → Velocity."
        )
    if any(u.category == "keyframe" for u in timeline.unsupported):
        steps.append("Keyframed motion/opacity was flattened to static; "
                     "rebuild keyframes on the listed clips.")
    if any(u.category in _EFFECT_LIKE_CATEGORIES for u in timeline.unsupported):
        steps.append(
            "CapCut effects, transitions, and filters are proprietary rendering "
            "features and are not portable outside CapCut. They are listed in the "
            "report above with their timecodes. Rebuild them in Premiere using "
            "native effects or third-party plugins."
        )
    if any(u.category == "text" for u in timeline.unsupported):
        steps.append(
            "Subtitle and caption tracks are not included in the XML. "
            "Run `cutsmith export-srt` to generate a sidecar SRT file, "
            "then import it into Premiere via File → Import → Captions."
        )

    for i, step in enumerate(steps, 1):
        lines.append(f"{i}. {step}")
    lines.append("")
