"""Subtitle / caption extraction from CapCut drafts.

Two text track patterns exist in CapCut Desktop 167.0.0:

  Pattern A — direct texts reference (plain text / simple captions)
    text_segment.material_id → materials.texts[id]
    texts[id].content (JSON string) → .text (str)

  Pattern B — animated subtitle template (CapCut's "AI Captions" style)
    text_segment.material_id → materials.text_templates[id]
    text_templates[id].text_info_resources[].text_material_id
        → materials.texts[id].content (JSON) → .text

Both patterns ultimately resolve to the same `materials.texts[].content`
JSON field. The difference is in how you navigate to the right texts[] entry
from a text track segment.

Detection: if the segment's material_id resolves to a text_template entry
(type == "text_template_subtitle"), use Pattern B. Otherwise use Pattern A.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from cutsmith.ir import SubtitleCue, SubtitleTrack


# ─── public API ─────────────────────────────────────────────────────────────── #

ExportFormat = Literal["srt", "txt", "json"]


def read_subtitles(draft_path: str | Path) -> list[SubtitleTrack]:
    """Extract subtitle / caption tracks from a CapCut draft JSON.

    Reads the draft file directly — does not go through the timeline reader.
    Returns one SubtitleTrack per text-type track in the draft, preserving
    track order. Cues with unresolvable text are included with `text=""`.
    """
    draft_path = Path(draft_path)
    with draft_path.open("r", encoding="utf-8") as f:
        raw = json.load(f)

    materials = raw.get("materials") or {}
    texts_by_id = _index_by_id(materials.get("texts") or [])
    tmpls_by_id = _index_by_id(materials.get("text_templates") or [])

    tracks: list[SubtitleTrack] = []
    for track in raw.get("tracks") or []:
        if track.get("type") != "text":
            continue
        cues: list[SubtitleCue] = []
        for seg in track.get("segments") or []:
            text = _resolve_text(seg, texts_by_id, tmpls_by_id)
            tgt = seg.get("target_timerange") or {}
            start_us = int(tgt.get("start", 0))
            dur_us = int(tgt.get("duration", 0))
            mat = texts_by_id.get(seg.get("material_id", ""))
            if mat is None:
                # Pattern B: look up the template to find the actual text mat
                tmpl = tmpls_by_id.get(seg.get("material_id", ""))
                if tmpl:
                    for res in tmpl.get("text_info_resources") or []:
                        mat = texts_by_id.get(res.get("text_material_id", ""))
                        if mat:
                            break
            is_auto = bool((mat or {}).get("recognize_type", 0))
            cues.append(SubtitleCue(
                cue_id=str(seg.get("id", f"cue_{len(cues)}")),
                start_us=start_us,
                end_us=start_us + dur_us,
                text=text,
                is_auto_caption=is_auto,
            ))
        tracks.append(SubtitleTrack(track_id=str(track.get("id", "")), cues=cues))
    return tracks


def export_subtitles(
    draft_path: str | Path,
    out_dir: str | Path,
    formats: list[ExportFormat] | None = None,
    name: str | None = None,
) -> list[Path]:
    """Run read_subtitles() and write one file per format.

    Returns list of written paths. If no text tracks are found, writes nothing
    and returns an empty list.
    """
    if formats is None:
        formats = ["srt"]
    draft_path = Path(draft_path)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    tracks = read_subtitles(draft_path)
    if not any(t.cues for t in tracks):
        return []

    stem = name or _stem_from_draft(draft_path)
    written: list[Path] = []

    for fmt in formats:
        if fmt == "srt":
            content = to_srt(tracks)
            suffix = ".srt"
        elif fmt == "txt":
            content = to_txt(tracks)
            suffix = ".txt"
        elif fmt == "json":
            content = to_json(tracks)
            suffix = ".subtitles.json"
        else:
            continue
        p = out_dir / (stem + suffix)
        p.write_text(content, encoding="utf-8")
        written.append(p)
    return written


# ─── format serialisers ────────────────────────────────────────────────────── #

def to_srt(tracks: list[SubtitleTrack]) -> str:
    """Merge all tracks into a single SRT stream sorted by start time."""
    all_cues = sorted(
        (cue for t in tracks for cue in t.cues),
        key=lambda c: c.start_us,
    )
    lines: list[str] = []
    for i, cue in enumerate(all_cues, 1):
        lines.append(str(i))
        lines.append(f"{_srt_ts(cue.start_us)} --> {_srt_ts(cue.end_us)}")
        lines.append(cue.text)
        lines.append("")
    return "\n".join(lines)


def to_txt(tracks: list[SubtitleTrack]) -> str:
    """One line per cue with timecode prefix: [HH:MM:SS.mmm] text"""
    all_cues = sorted(
        (cue for t in tracks for cue in t.cues),
        key=lambda c: c.start_us,
    )
    lines = [f"[{_txt_ts(c.start_us)}] {c.text}" for c in all_cues]
    return "\n".join(lines)


def to_json(tracks: list[SubtitleTrack]) -> str:
    """JSON array of subtitle tracks with cue arrays."""
    data = []
    for t in tracks:
        data.append({
            "track_id": t.track_id,
            "cue_count": t.cue_count,
            "likely_caption_track": t.likely_caption_track,
            "cues": [
                {
                    "cue_id": c.cue_id,
                    "start_us": c.start_us,
                    "end_us": c.end_us,
                    "start_s": round(c.start_us / 1_000_000, 3),
                    "end_s": round(c.end_us / 1_000_000, 3),
                    "text": c.text,
                    "is_auto_caption": c.is_auto_caption,
                }
                for c in t.cues
            ],
        })
    return json.dumps(data, indent=2, ensure_ascii=False)


# ─── internals ────────────────────────────────────────────────────────────── #

def _index_by_id(items: list[dict]) -> dict[str, dict]:
    return {item["id"]: item for item in items if item.get("id")}


def _resolve_text(
    seg: dict,
    texts_by_id: dict[str, dict],
    tmpls_by_id: dict[str, dict],
) -> str:
    mid = seg.get("material_id", "")

    # Pattern A: segment.material_id → texts
    if mid in texts_by_id:
        return _extract_plain_text(texts_by_id[mid])

    # Pattern B: segment.material_id → text_templates
    #   → text_info_resources[].text_material_id → texts
    tmpl = tmpls_by_id.get(mid)
    if tmpl:
        for res in tmpl.get("text_info_resources") or []:
            text_mid = res.get("text_material_id", "")
            if text_mid in texts_by_id:
                return _extract_plain_text(texts_by_id[text_mid])

    return ""  # unknown pattern — return empty rather than crash


def _extract_plain_text(mat: dict) -> str:
    """Pull the plain text string from a texts[] material.

    Primary: parse content as JSON → .text field.
    Fallback: recognize_text (ASR transcript field).
    """
    raw_content = mat.get("content") or ""
    if raw_content:
        try:
            obj = json.loads(raw_content)
            if isinstance(obj, dict) and "text" in obj:
                return str(obj["text"])
        except (json.JSONDecodeError, ValueError):
            pass
    return mat.get("recognize_text") or ""


def _srt_ts(us: int) -> str:
    """Microseconds → SRT timestamp HH:MM:SS,mmm"""
    ms = us // 1000
    h, rem = divmod(ms, 3_600_000)
    m, rem = divmod(rem, 60_000)
    s, ms_part = divmod(rem, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms_part:03d}"


def _txt_ts(us: int) -> str:
    """Microseconds → HH:MM:SS.mmm (for .txt output)"""
    return _srt_ts(us).replace(",", ".")


_UUID_RE = re.compile(
    r"^[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-"
    r"[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12}$"
)
_SCAFFOLD = {"Timelines"}


def _stem_from_draft(draft_path: Path) -> str:
    """Derive a human name from the draft path (mirrors reader logic)."""
    stem = draft_path.stem
    if stem != "draft_info":
        return stem
    for ancestor in draft_path.parents:
        name = ancestor.name
        if not name:
            continue
        if name in _SCAFFOLD or _UUID_RE.match(name):
            continue
        return name
    return stem
