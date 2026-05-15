"""Inspect a CapCut/JianyingPro draft and emit structural summaries.

Why this exists: before we trust reader/jianying_pro.py to handle a real
draft, we need to know how the draft's actual schema compares to what the
reader assumes. This module produces summaries — not full dumps — that
answer three questions per real draft:

  1. What fields does THIS version of CapCut emit?
  2. Which of those fields does the reader currently ignore?
  3. Are there field types/values the reader would crash or mis-parse on?

Output files (all JSON, all written to `out_dir`):

  schema_summary.json       — top-level shape + canvas + version info
  media_summary.json        — materials.videos / .audios field census
  track_summary.json        — per-track-type counts, segment field census
  unsupported_summary.json  — what the reader would currently flag as
                              unsupported (so you can see how much you'd
                              lose before doing a real export)
  unknown_fields.json       — fields seen in the draft but never read

  debug_inspect.json        — everything above merged into one file, plus
                              a tiny meta header. Useful for pasting into
                              issue reports without attaching five files.
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from cutsmith.inspect.schema import (
    KNOWN_AUDIO_MATERIAL_FIELDS,
    KNOWN_CANVAS_FIELDS,
    KNOWN_SEGMENT_FIELDS,
    KNOWN_TOP_LEVEL_FIELDS,
    KNOWN_TRACK_FIELDS,
    KNOWN_VIDEO_MATERIAL_FIELDS,
    redact_path,
    summarize_objects,
)


@dataclass
class InspectionResult:
    """In-memory result of an inspection. Mirrors what gets written to disk
    so callers (tests, scripts) can use the same structure without re-reading
    the JSON files."""
    schema_summary: dict[str, Any] = field(default_factory=dict)
    media_summary: dict[str, Any] = field(default_factory=dict)
    track_summary: dict[str, Any] = field(default_factory=dict)
    unsupported_summary: dict[str, Any] = field(default_factory=dict)
    unknown_fields: dict[str, Any] = field(default_factory=dict)
    written_files: list[Path] = field(default_factory=list)


def inspect_draft(
    draft_path: str | Path,
    out_dir: str | Path,
    *,
    raw_paths: bool = False,
) -> InspectionResult:
    """Inspect `draft_path` and write summary JSONs into `out_dir`.

    `raw_paths=False` (default): file paths are reduced to basenames before
    being written, so the output is safe to share. Set to True only when
    you specifically need the full paths for debugging path resolution.
    """
    draft_path = Path(draft_path)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    with draft_path.open("r", encoding="utf-8") as f:
        raw = json.load(f)

    result = InspectionResult()
    result.schema_summary = _build_schema_summary(raw, draft_path)
    result.media_summary = _build_media_summary(raw, raw_paths=raw_paths)
    result.track_summary = _build_track_summary(raw)
    result.unsupported_summary = _build_unsupported_summary(raw)
    result.unknown_fields = _build_unknown_fields(raw)

    # Write the five individual files, plus the merged debug file.
    files = {
        "schema_summary.json": result.schema_summary,
        "media_summary.json": result.media_summary,
        "track_summary.json": result.track_summary,
        "unsupported_summary.json": result.unsupported_summary,
        "unknown_fields.json": result.unknown_fields,
    }
    for name, payload in files.items():
        path = out_dir / name
        path.write_text(_to_json(payload), encoding="utf-8")
        result.written_files.append(path)

    merged = {
        "_meta": {
            "draft_path": str(draft_path) if raw_paths else draft_path.name,
            "draft_size_bytes": draft_path.stat().st_size,
            "raw_paths": raw_paths,
        },
        **{k.replace(".json", ""): v for k, v in files.items()},
    }
    merged_path = out_dir / "debug_inspect.json"
    merged_path.write_text(_to_json(merged), encoding="utf-8")
    result.written_files.append(merged_path)

    return result


def _to_json(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=False)


# --------------------------------------------------------------------------- #
# schema_summary                                                              #
# --------------------------------------------------------------------------- #

def _build_schema_summary(raw: dict[str, Any], draft_path: Path) -> dict[str, Any]:
    """High-level shape: what versions, sizes, frame rate, top-level keys."""
    materials = raw.get("materials") or {}
    tracks = raw.get("tracks") or []

    return {
        "draft_filename": draft_path.name,
        "draft_size_bytes": draft_path.stat().st_size,
        "version_fields": {
            "version": raw.get("version"),
            "new_version": raw.get("new_version"),
        },
        "top_level": {
            "keys": sorted(raw.keys()) if isinstance(raw, dict) else [],
            "fps": raw.get("fps"),
            "duration_us": raw.get("duration"),
            "duration_seconds": (raw["duration"] / 1_000_000.0
                                 if isinstance(raw.get("duration"), (int, float))
                                 else None),
        },
        "canvas_config": {
            "present": "canvas_config" in raw,
            "fields_seen": sorted((raw.get("canvas_config") or {}).keys()),
            "missing_known_fields": sorted(
                KNOWN_CANVAS_FIELDS - set((raw.get("canvas_config") or {}).keys())
            ),
            "values": raw.get("canvas_config"),
        },
        "counts": {
            "material_categories": {
                k: len(v) if isinstance(v, list) else "<not-a-list>"
                for k, v in materials.items()
            },
            "tracks_total": len(tracks),
            "tracks_by_type": dict(Counter(
                t.get("type", "<unknown>") for t in tracks if isinstance(t, dict)
            )),
        },
        "unknown_top_level_fields": sorted(set(raw.keys()) - KNOWN_TOP_LEVEL_FIELDS),
        "missing_known_top_level_fields": sorted(
            KNOWN_TOP_LEVEL_FIELDS - set(raw.keys())
        ),
    }


# --------------------------------------------------------------------------- #
# media_summary                                                               #
# --------------------------------------------------------------------------- #

def _build_media_summary(raw: dict[str, Any], *, raw_paths: bool) -> dict[str, Any]:
    """Field-by-field census of materials.videos and materials.audios.

    We also list a redacted preview of every asset (id + name + basename +
    duration), because seeing the names is often the fastest way to spot
    "oh that BGM isn't in there" type problems.
    """
    materials = raw.get("materials") or {}
    videos = materials.get("videos") or []
    audios = materials.get("audios") or []

    return {
        "videos": {
            "summary": summarize_objects(videos, KNOWN_VIDEO_MATERIAL_FIELDS),
            "preview": [_asset_preview(v, kind="video", raw_paths=raw_paths)
                        for v in videos],
        },
        "audios": {
            "summary": summarize_objects(audios, KNOWN_AUDIO_MATERIAL_FIELDS),
            "preview": [_asset_preview(a, kind="audio", raw_paths=raw_paths)
                        for a in audios],
        },
        # Other categories: just counts. We don't read them in v0.1, so a
        # full census is wasted bytes — but knowing they exist matters for
        # the "what you'd lose" picture.
        "other_categories": {
            k: len(v) if isinstance(v, list) else None
            for k, v in materials.items()
            if k not in ("videos", "audios")
        },
    }


def _asset_preview(asset: dict[str, Any], *, kind: str,
                   raw_paths: bool) -> dict[str, Any]:
    name_key = "material_name" if kind == "video" else "name"
    return {
        "id": asset.get("id"),
        "name": asset.get(name_key),
        "path": redact_path(asset.get("path"), keep=raw_paths),
        "duration_us": asset.get("duration"),
        "type": asset.get("type"),
    }


# --------------------------------------------------------------------------- #
# track_summary                                                               #
# --------------------------------------------------------------------------- #

def _build_track_summary(raw: dict[str, Any]) -> dict[str, Any]:
    """Group tracks by type, then census the segment fields per group.

    Reasoning: video tracks and audio tracks often have slightly different
    segment shapes (e.g. audio segments might have `fade` fields, video
    might have `clip.scale`). Pooling all segments into one census would
    blur that — keeping them split makes drift easier to spot.
    """
    tracks = raw.get("tracks") or []

    # Census of the track-level fields themselves.
    track_field_census = summarize_objects(tracks, KNOWN_TRACK_FIELDS)

    # Group segments by track type.
    segments_by_type: dict[str, list[dict[str, Any]]] = {}
    track_attrs_by_type: dict[str, list[dict[str, Any]]] = {}
    for t in tracks:
        if not isinstance(t, dict):
            continue
        ttype = t.get("type", "<unknown>")
        segs = t.get("segments") or []
        segments_by_type.setdefault(ttype, []).extend(
            s for s in segs if isinstance(s, dict)
        )
        track_attrs_by_type.setdefault(ttype, []).append({
            k: v for k, v in t.items() if k != "segments"
        })

    per_type: dict[str, Any] = {}
    for ttype, segs in segments_by_type.items():
        per_type[ttype] = {
            "segment_count": len(segs),
            "track_count": len(track_attrs_by_type.get(ttype, [])),
            "segment_fields": summarize_objects(segs, KNOWN_SEGMENT_FIELDS),
            "track_fields": summarize_objects(
                track_attrs_by_type.get(ttype, []), KNOWN_TRACK_FIELDS - {"segments"}
            ),
        }

    return {
        "tracks_total": len(tracks),
        "track_level_census": track_field_census,
        "by_track_type": per_type,
    }


# --------------------------------------------------------------------------- #
# unsupported_summary                                                         #
# --------------------------------------------------------------------------- #

def _build_unsupported_summary(raw: dict[str, Any]) -> dict[str, Any]:
    """What the reader would currently log as 'unsupported' on this draft.

    We replicate the reader's flagging logic here rather than calling the
    reader directly, because the reader also does field reads that may
    crash on unexpected types — and the whole point of inspect is to run
    safely on weird inputs.
    """
    materials = raw.get("materials") or {}
    tracks = raw.get("tracks") or []

    drop_material_categories = (
        "texts", "stickers", "effects", "filters", "transitions",
        "video_effects", "audio_effects", "masks",
    )
    drop_track_types = ("text", "sticker", "effect", "filter", "adjust", "cover")

    material_drops: dict[str, int] = {}
    for cat in drop_material_categories:
        items = materials.get(cat) or []
        if items:
            material_drops[cat] = len(items)

    track_drops: dict[str, dict[str, int]] = {}
    speed_changes = 0
    keyframe_segments = 0
    segments_with_extra_refs = 0
    total_av_segments = 0

    for t in tracks:
        if not isinstance(t, dict):
            continue
        ttype = t.get("type")
        segs = t.get("segments") or []
        if ttype in drop_track_types:
            track_drops.setdefault(ttype, {"track_count": 0, "segment_count": 0})
            track_drops[ttype]["track_count"] += 1
            track_drops[ttype]["segment_count"] += len(segs)
            continue
        if ttype not in ("video", "audio"):
            continue
        for seg in segs:
            if not isinstance(seg, dict):
                continue
            total_av_segments += 1
            speed = seg.get("speed", 1.0)
            if isinstance(speed, (int, float)) and abs(speed - 1.0) > 1e-3:
                speed_changes += 1
            src = seg.get("source_timerange") or {}
            tgt = seg.get("target_timerange") or {}
            sd, td = src.get("duration"), tgt.get("duration")
            if isinstance(sd, int) and isinstance(td, int) and sd != td:
                # Duration mismatch implies speed change even if `speed` is missing
                speed_changes += 1 if (speed == 1.0 or speed is None) else 0
            if seg.get("keyframe_refs"):
                keyframe_segments += 1
            if seg.get("extra_material_refs"):
                segments_with_extra_refs += 1

    return {
        "material_categories_dropped": material_drops,
        "track_types_dropped": track_drops,
        "av_segments_total": total_av_segments,
        "av_segments_with_speed_change": speed_changes,
        "av_segments_with_keyframes": keyframe_segments,
        "av_segments_with_extra_refs": segments_with_extra_refs,
        "_note": (
            "These are counts the v0.1 reader would emit as `unsupported` "
            "entries. High keyframe/extra_refs/speed counts on a draft you "
            "actually plan to migrate = more manual work in Premiere."
        ),
    }


# --------------------------------------------------------------------------- #
# unknown_fields                                                              #
# --------------------------------------------------------------------------- #

def _build_unknown_fields(raw: dict[str, Any]) -> dict[str, Any]:
    """Cross-cutting view: which fields appear in the draft that the reader
    never looks at? Sorted by where in the schema they live."""
    out: dict[str, Any] = {
        "top_level": sorted(set(raw.keys()) - KNOWN_TOP_LEVEL_FIELDS),
        "canvas_config": sorted(
            set((raw.get("canvas_config") or {}).keys()) - KNOWN_CANVAS_FIELDS
        ),
        "video_materials": [],
        "audio_materials": [],
        "tracks": [],
        "segments_by_track_type": {},
    }

    materials = raw.get("materials") or {}
    if videos := materials.get("videos"):
        out["video_materials"] = summarize_objects(
            videos, KNOWN_VIDEO_MATERIAL_FIELDS
        ).get("unknown_fields", [])
    if audios := materials.get("audios"):
        out["audio_materials"] = summarize_objects(
            audios, KNOWN_AUDIO_MATERIAL_FIELDS
        ).get("unknown_fields", [])

    tracks = raw.get("tracks") or []
    if tracks:
        out["tracks"] = summarize_objects(
            tracks, KNOWN_TRACK_FIELDS
        ).get("unknown_fields", [])

    # Segments split by track type — see _build_track_summary for why.
    segs_by_type: dict[str, list[dict[str, Any]]] = {}
    for t in tracks:
        if not isinstance(t, dict):
            continue
        ttype = t.get("type", "<unknown>")
        for s in t.get("segments") or []:
            if isinstance(s, dict):
                segs_by_type.setdefault(ttype, []).append(s)
    for ttype, segs in segs_by_type.items():
        out["segments_by_track_type"][ttype] = summarize_objects(
            segs, KNOWN_SEGMENT_FIELDS
        ).get("unknown_fields", [])

    return out
