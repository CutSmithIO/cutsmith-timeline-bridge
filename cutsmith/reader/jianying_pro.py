"""CapCut/JianyingPro draft_content.json → Timeline IR.

The CapCut Pro draft format is undocumented. This reader targets the schema
shipped by the Mac/Windows desktop app, family 5.x–6.x, which is the dominant
version in the field as of 2024–2026.

Schema summary (only the parts v0.1 cares about):

  {
    "canvas_config": { "width": 1920, "height": 1080, "ratio": "16:9" },
    "fps": 30.0,
    "duration": 12345678,                   # microseconds, total timeline
    "materials": {
        "videos":  [ {id, path, duration, width, height, type, has_audio, ...} ],
        "audios":  [ {id, path, duration, name, type, ...} ],
        # ... many other categories we ignore in v0.1:
        "texts", "stickers", "effects", "transitions", "filters",
        "audio_effects", "masks", "video_effects", "speeds", ...
    },
    "tracks": [
        {
          "id": "...",
          "type": "video" | "audio" | "text" | "effect" | "filter" | "sticker" | ...,
          "attribute": 0,                   # 1 means muted on some versions
          "segments": [
            {
              "id": "...",
              "material_id": "...",         # → materials.videos[].id or .audios[].id
              "source_timerange": { "start": us, "duration": us },
              "target_timerange": { "start": us, "duration": us },
              "enable_adjust": ..., "volume": 1.0, "speed": 1.0,
              "extra_material_refs": [...]  # links to speeds, transitions, etc.
            }
          ]
        }
    ]
  }

Things deliberately not parsed in v0.1 (they go into `unsupported`):
  - text / sticker / effect / filter tracks
  - segment-level transitions, filters, speed curves
  - keyframe animations (segment.keyframe_refs / clip.keyframes)
  - audio fades, audio effects
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from cutsmith.ir import (
    Clip,
    MediaAsset,
    MediaKind,
    SequenceSettings,
    Timeline,
    Track,
    TrackKind,
    UnsupportedItem,
)

# CapCut track `type` values we care about in v0.1. Everything else gets
# logged as unsupported.
_VIDEO_TRACK_TYPES = {"video"}
_AUDIO_TRACK_TYPES = {"audio"}
_KNOWN_BUT_UNSUPPORTED = {
    "text", "sticker", "effect", "filter", "adjust", "cover",
}

# CapCut stores target_timerange.duration with µs-level rounding that may
# differ from source_timerange.duration by ±1µs even when no speed change
# is applied. 1ms (≈ 1/30 of a frame at 30fps) absorbs this rounding without
# masking real speed changes.
_SPEED_DUR_TOLERANCE_US = 1000

# Matches a standalone UUID directory name like CapCut's Timelines/<UUID>/ —
# used by _derive_timeline_name to walk past UUID/scaffolding directories and
# find the human-given project name.
_UUID_DIRNAME_RE = re.compile(
    r"^[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-"
    r"[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12}$"
)
_SCAFFOLD_DIRNAMES = {"Timelines"}


def _derive_timeline_name(draft_path: Path) -> str:
    """Pick a useful default sequence name.

    Modern CapCut/Jianying drafts are all literally named `draft_info.json`,
    often under `Timelines/<UUID>/` — using `Path.stem` produces the useless
    string "draft_info". Walk up until we hit an ancestor whose name is neither
    a UUID nor a scaffolding folder; that's the human-named project dir.
    """
    stem = draft_path.stem
    if stem != "draft_info":
        return stem
    for ancestor in draft_path.parents:
        name = ancestor.name
        if not name:
            continue
        if name in _SCAFFOLD_DIRNAMES or _UUID_DIRNAME_RE.match(name):
            continue
        return name
    return stem  # nothing better available; preserve the legacy behavior


# ─── extra_material_refs classification ──────────────────────────────────── #
# A CapCut segment carries `extra_material_refs` — a list of material IDs that
# point into other categories (transitions, filters, speeds, canvases, ...).
# Many of these refs exist by default (every clip gets a canvas + sound channel
# mapping + speed material even when the user didn't touch them), so reporting
# them all would drown the actual user-applied effects in noise.
#
# Policy:
#   1. ALWAYS_REAL: presence implies a user-applied feature, report it.
#   2. CONDITIONAL: a per-clip material that's only "real" if its payload
#      deviates from the default state.
#   3. BENIGN: pure bookkeeping (placeholder_infos), never reported.
#   4. Unknown categories: silently skipped — false negatives are preferable
#      to flooding the report.

_ALWAYS_REAL_REF_CATEGORIES = {
    "transitions", "filters", "effects",
    "video_effects", "audio_effects", "audio_fades",
    "audio_balances", "audio_pannings", "audio_pitch_shifts",
    "common_mask", "chromas",
    "color_curves", "hsl", "hsl_curves",
    "primary_color_wheels", "log_color_wheels",
    "video_strokes", "video_shadows", "video_radius",
    "plugin_effects",
}

_BENIGN_REF_CATEGORIES = {"placeholder_infos"}

# Predicate is called on the material payload dict; True ⇒ deviation from
# default ⇒ report. Keep these tolerant — missing fields mean default.
_CONDITIONAL_REF_PREDICATES = {
    # Only fire for actual variable-speed curves.  Constant speed changes
    # (speed != 1.0, no curve_speed) are already reported at the segment
    # level as "speed"; re-reporting them here as "speed_curve" is a
    # false positive and confuses the reader of the report.
    "speeds": lambda p: p.get("curve_speed") is not None,
    "material_animations": lambda p: bool(p.get("animations")),
    "vocal_separations": lambda p: bool(p.get("choice")),
    "canvases": lambda p: bool(p.get("color")) or bool(p.get("image")),
    "sound_channel_mappings": lambda p: (
        bool(p.get("is_config_open"))
        or p.get("audio_channel_mapping", 0) != 0
    ),
    "material_colors": lambda p: (
        bool(p.get("is_color_clip")) or bool(p.get("is_gradient"))
    ),
    "loudnesses": lambda p: bool(p.get("enable")),
    "beats": lambda p: (
        bool(p.get("enable_ai_beats")) or bool(p.get("user_beats"))
    ),
}

# Plural CapCut category → singular report label
_REF_REPORT_LABEL = {
    "transitions": "transition",
    "filters": "filter",
    "effects": "effect",
    "video_effects": "video_effect",
    "audio_effects": "audio_effect",
    "audio_fades": "audio_fade",
    "audio_balances": "audio_balance",
    "audio_pannings": "audio_panning",
    "audio_pitch_shifts": "audio_pitch_shift",
    "common_mask": "mask",
    "chromas": "chroma_key",
    "color_curves": "color_curve",
    "hsl": "hsl",
    "hsl_curves": "hsl_curve",
    "primary_color_wheels": "color_wheel",
    "log_color_wheels": "log_color_wheel",
    "video_strokes": "video_stroke",
    "video_shadows": "video_shadow",
    "video_radius": "video_radius",
    "plugin_effects": "plugin_effect",
    "speeds": "speed_curve",
    "material_animations": "material_animation",
    "vocal_separations": "vocal_separation",
    "canvases": "canvas_override",
    "sound_channel_mappings": "sound_channel_mapping",
    "material_colors": "material_color_override",
    "loudnesses": "loudness",
    "beats": "beat_sync",
}


def _classify_extra_ref(category: str, payload: dict[str, Any]) -> str | None:
    """Return the singular report-category label if this extra_material_ref
    represents a real user-applied feature, or None if it's default
    infrastructure that should not appear in the report.
    """
    if category in _BENIGN_REF_CATEGORIES:
        return None
    if category in _ALWAYS_REAL_REF_CATEGORIES:
        return _REF_REPORT_LABEL.get(category, category.rstrip("s"))
    predicate = _CONDITIONAL_REF_PREDICATES.get(category)
    if predicate is not None:
        if predicate(payload):
            return _REF_REPORT_LABEL.get(category, category.rstrip("s"))
        return None
    return None  # unknown category — silently skip


def _build_materials_index(materials: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Flatten materials.* into id → {category, payload}.

    Used to dereference a segment's extra_material_refs (a flat list of UUIDs)
    back to the specific category each one points at, so the report can be
    category-specific instead of lumping everything under 'extra_refs'.
    """
    index: dict[str, dict[str, Any]] = {}
    for category, items in materials.items():
        if not isinstance(items, list):
            continue
        for item in items:
            if isinstance(item, dict) and item.get("id"):
                index[item["id"]] = {"category": category, "payload": item}
    return index


def read_draft(draft_path: str | Path) -> Timeline:
    """Parse a draft_content.json into a Timeline IR.

    The reader is permissive: missing fields fall back to defaults rather than
    raising. Anything genuinely structural (no canvas_config, no tracks) does
    raise — there's no sensible default for those.
    """
    draft_path = Path(draft_path)
    with draft_path.open("r", encoding="utf-8") as f:
        raw = json.load(f)

    timeline = Timeline(
        name=_derive_timeline_name(draft_path),
        settings=_parse_settings(raw),
        source_metadata={
            "draft_path": str(draft_path),
            "draft_total_duration_us": int(raw.get("duration", 0)),
            "capcut_version": raw.get("version") or raw.get("new_version"),
        },
    )

    materials_index = _build_materials_index(raw.get("materials") or {})
    _parse_assets(raw, timeline)
    _parse_tracks(raw, timeline, materials_index)
    return timeline


# --------------------------------------------------------------------------- #
# canvas / fps                                                                #
# --------------------------------------------------------------------------- #

def _parse_settings(raw: dict[str, Any]) -> SequenceSettings:
    canvas = raw.get("canvas_config") or {}
    width = int(canvas.get("width") or 1920)
    height = int(canvas.get("height") or 1080)
    # CapCut stores fps as a float at the top level, sometimes also inside
    # canvas_config. Top-level wins when present.
    fps = float(raw.get("fps") or canvas.get("fps") or 30.0)
    return SequenceSettings(width=width, height=height, frame_rate=fps)


# --------------------------------------------------------------------------- #
# materials → MediaAsset                                                       #
# --------------------------------------------------------------------------- #

def _parse_assets(raw: dict[str, Any], timeline: Timeline) -> None:
    materials = raw.get("materials") or {}

    for v in materials.get("videos") or []:
        asset = _video_material_to_asset(v)
        timeline.assets[asset.asset_id] = asset

    for a in materials.get("audios") or []:
        asset = _audio_material_to_asset(a)
        timeline.assets[asset.asset_id] = asset

    # Log text/sticker materials at scan time. These categories aren't
    # referenced via segments' extra_material_refs (they live on dedicated
    # text/sticker tracks), so the segment-level dereferencer below wouldn't
    # surface them. Everything else (transitions, filters, effects, video/
    # audio effects, masks, ...) is reported per-use via _classify_extra_ref
    # when a segment actually references it. Trade-off: an effect material
    # that's added to the project but not applied to any segment will be
    # silently dropped — which is correct, since it has no on-timeline impact.
    for category in ("texts", "stickers"):
        items = materials.get(category) or []
        for item in items:
            timeline.unsupported.append(UnsupportedItem(
                category=category.rstrip("s"),
                detail=f"{category[:-1]} material '{item.get('name') or item.get('id')}' "
                       f"present in draft but not exported (v0.1 scope)",
            ))


def _video_material_to_asset(m: dict[str, Any]) -> MediaAsset:
    # CapCut sets material.type = "video" for regular video, "photo" for
    # stills. Both live in materials.videos.
    is_photo = (m.get("type") == "photo")
    return MediaAsset(
        asset_id=str(m["id"]),
        name=m.get("material_name") or Path(m.get("path", "")).name or m["id"],
        original_path=m.get("path", ""),
        resolved_path=None,                       # filled later by resolver
        media_kind=MediaKind.IMAGE if is_photo else MediaKind.VIDEO,
        duration_us=int(m.get("duration") or 0),
        has_video=True,
        has_audio=bool(m.get("has_audio", not is_photo)),
        width=m.get("width"),
        height=m.get("height"),
        frame_rate=_safe_float(m.get("source_frame_rate")) or _safe_float(m.get("fps")),
        extras={"capcut_type": m.get("type")},
    )


def _audio_material_to_asset(m: dict[str, Any]) -> MediaAsset:
    return MediaAsset(
        asset_id=str(m["id"]),
        name=m.get("name") or Path(m.get("path", "")).name or m["id"],
        original_path=m.get("path", ""),
        resolved_path=None,
        media_kind=MediaKind.AUDIO,
        duration_us=int(m.get("duration") or 0),
        has_video=False,
        has_audio=True,
        audio_channels=m.get("channels"),
        audio_sample_rate=m.get("sample_rate"),
        extras={"capcut_type": m.get("type")},
    )


def _safe_float(v: Any) -> float | None:
    try:
        return float(v) if v is not None else None
    except (TypeError, ValueError):
        return None


# --------------------------------------------------------------------------- #
# tracks → Track + Clip                                                        #
# --------------------------------------------------------------------------- #

def _parse_tracks(
    raw: dict[str, Any],
    timeline: Timeline,
    materials_index: dict[str, dict[str, Any]],
) -> None:
    tracks_raw = raw.get("tracks") or []
    video_idx = 0
    audio_idx = 0

    for t in tracks_raw:
        ttype = t.get("type")
        if ttype in _VIDEO_TRACK_TYPES:
            video_idx += 1
            track = _parse_av_track(t, TrackKind.VIDEO, f"V{video_idx}",
                                    timeline, materials_index)
            timeline.video_tracks.append(track)
        elif ttype in _AUDIO_TRACK_TYPES:
            audio_idx += 1
            track = _parse_av_track(t, TrackKind.AUDIO, f"A{audio_idx}",
                                    timeline, materials_index)
            timeline.audio_tracks.append(track)
        elif ttype in _KNOWN_BUT_UNSUPPORTED:
            seg_count = len(t.get("segments") or [])
            timeline.unsupported.append(UnsupportedItem(
                category=ttype,
                detail=f"'{ttype}' track with {seg_count} segment(s) skipped (v0.1 scope)",
            ))
        else:
            # Unknown track type — log it, don't crash.
            timeline.unsupported.append(UnsupportedItem(
                category="unknown_track",
                detail=f"track type '{ttype}' not recognized; skipped",
            ))


def _parse_av_track(
    t: dict[str, Any],
    kind: TrackKind,
    name: str,
    timeline: Timeline,
    materials_index: dict[str, dict[str, Any]],
) -> Track:
    track = Track(
        track_id=str(t.get("id") or name),
        kind=kind,
        name=name,
        muted=bool(t.get("attribute") == 1),  # CapCut convention; 0 = active
    )

    for seg in t.get("segments") or []:
        clip = _parse_segment(seg, timeline, track_hint=name,
                              materials_index=materials_index)
        if clip is not None:
            track.clips.append(clip)

    track.clips.sort(key=lambda c: c.timeline_start_us)
    return track


def _parse_segment(
    seg: dict[str, Any],
    timeline: Timeline,
    track_hint: str,
    materials_index: dict[str, dict[str, Any]],
) -> Clip | None:
    material_id = str(seg.get("material_id") or "")
    if not material_id or material_id not in timeline.assets:
        timeline.unsupported.append(UnsupportedItem(
            category="orphan_segment",
            detail=f"segment {seg.get('id')} references missing material_id "
                   f"'{material_id}'; clip dropped",
            track_hint=track_hint,
        ))
        return None

    src = seg.get("source_timerange") or {}
    tgt = seg.get("target_timerange") or {}
    source_start = int(src.get("start", 0))
    source_dur = int(src.get("duration", 0))
    target_start = int(tgt.get("start", 0))
    target_dur = int(tgt.get("duration", source_dur))

    # v0.1 doesn't support speed != 1.0. CapCut also writes target/source
    # durations with µs-level rounding that's well below frame precision, so
    # tolerate sub-millisecond drift. Real speed changes either set
    # segment.speed away from 1.0 or have a duration delta > 1ms.
    speed = float(seg.get("speed", 1.0))
    dur_diff = abs(target_dur - source_dur)
    if abs(speed - 1.0) > 1e-3 or dur_diff > _SPEED_DUR_TOLERANCE_US:
        timeline.unsupported.append(UnsupportedItem(
            category="speed",
            detail=f"segment {seg.get('id')} has speed={speed:.3f} "
                   f"(source={source_dur}us, target={target_dur}us); "
                   f"timeline slot preserved; Premiere shows 100% — apply Speed/Duration manually",
            track_hint=track_hint,
            time_hint_us=target_start,
        ))

    # Detect features we explicitly drop in v0.1.
    if seg.get("keyframe_refs"):
        timeline.unsupported.append(UnsupportedItem(
            category="keyframe",
            detail=f"segment {seg.get('id')} has keyframe animation; "
                   f"exported as static",
            track_hint=track_hint,
            time_hint_us=target_start,
        ))

    # Dereference extra_material_refs by category. The classifier filters out
    # default-state infrastructure refs (canvases, sound channel mappings,
    # 1.0× speeds, …) and reports user-applied features (transitions, filters,
    # effects, animations, …) under their specific category labels.
    for ref_id in seg.get("extra_material_refs") or []:
        info = materials_index.get(str(ref_id))
        if info is None:
            continue
        label = _classify_extra_ref(info["category"], info["payload"])
        if label is None:
            continue
        payload = info["payload"]
        name = (payload.get("name") or payload.get("effect_name")
                or payload.get("type") or label)
        timeline.unsupported.append(UnsupportedItem(
            category=label,
            detail=f"{label} '{name}' on segment {seg.get('id')} — "
                   f"not exported (v0.1 scope)",
            track_hint=track_hint,
            time_hint_us=target_start,
        ))

    volume = float(seg.get("volume", 1.0))
    # CapCut "clip" sub-object holds opacity/scale/position. v0.1 only reads
    # opacity as a constant.
    clip_obj = seg.get("clip") or {}
    opacity = float(clip_obj.get("alpha", 1.0))

    return Clip(
        clip_id=str(seg.get("id") or f"seg_{target_start}"),
        asset_id=material_id,
        source_in_us=source_start,
        source_out_us=source_start + source_dur,
        timeline_start_us=target_start,
        # Honor CapCut's target slot length so subsequent clips line up the
        # way the editor saw them. When source_dur != target_dur (a speed
        # change), the FCP7 XML's end-start ≠ out-in encodes that delta;
        # Premiere interprets the mismatch as implied speed. The report
        # surfaces this so the user can override the implied speed.
        timeline_duration_us=target_dur,
        enabled=not bool(seg.get("visible") is False),
        volume=volume,
        opacity=opacity,
        extras={"capcut_segment_id": seg.get("id")},
    )
