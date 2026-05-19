#!/usr/bin/env python3
"""Dump a Timeline IR (post-reader, pre-writer) for diagnosis.

Used to verify the reader produced sensible cuts on a new draft BEFORE
running the full convert pipeline. The reader is the only piece that
sees raw CapCut schema, so if it misreads, every downstream consumer
silently produces wrong XML. This script makes its output inspectable.

Outputs two artifacts under <out_dir>/:

  ir_summary.json   — full clip lists, machine-readable
  ir_summary.md     — human eyeballing: top 5 assets + top 10 clips per track

Run:
    python3 scripts/ir_diag.py <path-to-draft.json> -o out_ir/<name>

Notes on what the script surfaces beyond raw IR fields:

* `timeline.duration_us`: computed as max clip-end across all tracks, not
  the draft's declared `duration` field. We show both so a mismatch is
  visible — that's a red flag that segments aren't being parsed correctly.
* `speed_hint` per clip: pulled from `timeline.unsupported` items with
  category=speed (the IR's Clip doesn't store speed). When speed ≠ 1.0
  the reader keeps the timeline length at source_dur, NOT target_dur,
  which is a latent bug — we flag clips where this matters.
* `text_tracks_count`: the IR drops text tracks into `unsupported`; we
  re-derive their count by matching unsupported items whose detail
  string contains "track".
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from cutsmith.reader import read_draft
from cutsmith.ir import Timeline, Track, Clip


_SPEED_RE = re.compile(r"speed=([\d.]+)")
_TARGET_DUR_RE = re.compile(r"target=(\d+)us")
_SOURCE_DUR_RE = re.compile(r"source=(\d+)us")
_SEG_ID_RE = re.compile(r"segment ([0-9A-F]{8}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{12})", re.IGNORECASE)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Dump Timeline IR after reader for diagnosis. No XML produced.")
    parser.add_argument("draft", help="Path to draft JSON (draft_content.json or draft_info.json)")
    parser.add_argument("-o", "--out-dir", required=True)
    args = parser.parse_args()

    draft = Path(args.draft).expanduser()
    out_dir = Path(args.out_dir).expanduser()
    out_dir.mkdir(parents=True, exist_ok=True)

    timeline = read_draft(draft)
    summary = build_summary(timeline, draft)

    (out_dir / "ir_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    (out_dir / "ir_summary.md").write_text(
        render_markdown(summary), encoding="utf-8")

    print(f"[ir-diag] wrote {out_dir}/ir_summary.json")
    print(f"[ir-diag] wrote {out_dir}/ir_summary.md")
    print()

    tl = summary["timeline"]
    print(f"  name:           {tl['name']}")
    print(f"  fps:            {tl['fps']} (NTSC={tl['is_ntsc']}, timebase={tl['timebase']})")
    print(f"  resolution:     {tl['width']}×{tl['height']}")
    print(f"  duration:       observed={tl['duration_seconds']:.2f}s, "
          f"declared={tl['declared_total_duration_seconds']:.2f}s "
          f"(delta={tl['duration_seconds']-tl['declared_total_duration_seconds']:+.2f}s)")
    print(f"  assets:         {summary['assets']['count']} "
          f"({summary['assets']['by_kind']})")
    print(f"  video tracks:   {len(summary['video_tracks'])} "
          f"(total {sum(t['clip_count'] for t in summary['video_tracks'])} clips)")
    print(f"  audio tracks:   {len(summary['audio_tracks'])} "
          f"(total {sum(t['clip_count'] for t in summary['audio_tracks'])} clips)")
    print(f"  text tracks:    {summary['text_tracks_count']} "
          f"(not in IR — counted via unsupported)")
    print(f"  unsupported:    {summary['unsupported']['total']} items, "
          f"categories: {summary['unsupported']['by_category']}")
    if summary['ir_inconsistencies']:
        print(f"  ⚠ ir inconsistencies: {len(summary['ir_inconsistencies'])} "
              f"(speed≠1.0 clips where IR length = source_dur, not target_dur)")
    return 0


def build_summary(timeline: Timeline, draft_path: Path) -> dict:
    s = timeline.settings

    # Speed map: segment_clip_id → speed info (parsed from unsupported.detail).
    # Keyed by clip_id (UUID from detail string), NOT by timeline_start_us — multiple
    # tracks can start at the same timeline position, so time-keying causes collisions
    # and produces false inconsistency reports.
    speed_by_clip: dict[str, dict] = {}
    for it in timeline.unsupported:
        if it.category != "speed":
            continue
        seg_m = _SEG_ID_RE.search(it.detail or "")
        if not seg_m:
            continue
        sp = _SPEED_RE.search(it.detail or "")
        tgt = _TARGET_DUR_RE.search(it.detail or "")
        src = _SOURCE_DUR_RE.search(it.detail or "")
        speed_by_clip[seg_m.group(1).upper()] = {
            "speed": float(sp.group(1)) if sp else None,
            "source_dur_us": int(src.group(1)) if src else None,
            "target_dur_us": int(tgt.group(1)) if tgt else None,
        }

    # Observed timeline duration: max clip-end across all tracks
    all_ends = [c.timeline_start_us + c.timeline_duration_us
                for trk in (timeline.video_tracks + timeline.audio_tracks)
                for c in trk.clips]
    observed_us = max(all_ends) if all_ends else 0
    declared_us = int(timeline.source_metadata.get("draft_total_duration_us", 0))

    # Text track count: unsupported items with category="text" whose detail
    # mentions "track" (vs. text *material* items which say "material").
    text_track_details = [
        it.detail for it in timeline.unsupported
        if it.category == "text" and "track" in (it.detail or "").lower()
    ]

    by_category: Counter[str] = Counter()
    for it in timeline.unsupported:
        by_category[it.category] += 1

    # Find clips whose IR duration disagrees with target_dur (speed ≠ 1.0 case).
    # Uses clip_id lookup so parallel tracks starting at the same timeline position
    # don't collide.
    ir_inconsistencies = []
    for track in timeline.video_tracks + timeline.audio_tracks:
        for c in track.clips:
            hint = speed_by_clip.get(c.clip_id.upper())
            if hint and hint.get("target_dur_us") is not None:
                if c.timeline_duration_us != hint["target_dur_us"]:
                    ir_inconsistencies.append({
                        "clip_id": c.clip_id,
                        "track": track.name,
                        "timeline_start_us": c.timeline_start_us,
                        "ir_duration_us": c.timeline_duration_us,
                        "target_duration_us": hint["target_dur_us"],
                        "speed": hint["speed"],
                        "note": "IR uses source_dur but raw target_dur differs — "
                                "downstream XML will place a clip of source_dur length",
                    })

    return {
        "draft_path": str(draft_path),
        "timeline": {
            "name": timeline.name,
            "fps": s.frame_rate,
            "is_ntsc": s.is_ntsc,
            "timebase": s.timebase,
            "width": s.width,
            "height": s.height,
            "duration_us": observed_us,
            "duration_seconds": observed_us / 1_000_000,
            "declared_total_duration_us": declared_us,
            "declared_total_duration_seconds": declared_us / 1_000_000,
        },
        "source_metadata": timeline.source_metadata,
        "assets": {
            "count": len(timeline.assets),
            "by_kind": dict(Counter(a.media_kind.value for a in timeline.assets.values())),
            "top_5": [_asset_summary(a) for a in list(timeline.assets.values())[:5]],
            "all_paths": [a.original_path for a in timeline.assets.values()],
        },
        "video_tracks": [_track_summary(t, speed_by_clip, top=10) for t in timeline.video_tracks],
        "audio_tracks": [_track_summary(t, speed_by_clip, top=10) for t in timeline.audio_tracks],
        "text_tracks_count": len(text_track_details),
        "text_tracks_detail": text_track_details,
        "unsupported": {
            "total": len(timeline.unsupported),
            "by_category": dict(by_category.most_common()),
            "first_15": [
                {"category": it.category, "detail": it.detail,
                 "track_hint": it.track_hint, "time_hint_us": it.time_hint_us}
                for it in timeline.unsupported[:15]
            ],
        },
        "ir_inconsistencies": ir_inconsistencies,
    }


def _asset_summary(a) -> dict:
    return {
        "asset_id": a.asset_id,
        "name": a.name,
        "media_kind": a.media_kind.value,
        "duration_us": a.duration_us,
        "duration_seconds": round(a.duration_us / 1_000_000, 3),
        "original_path": a.original_path,
        "width": a.width,
        "height": a.height,
        "has_audio": a.has_audio,
    }


def _track_summary(t: Track, speed_by_clip: dict, top: int) -> dict:
    return {
        "track_id": t.track_id,
        "kind": t.kind.value,
        "name": t.name,
        "muted": t.muted,
        "clip_count": len(t.clips),
        "top_10_clips": [_clip_summary(c, speed_by_clip) for c in t.clips[:top]],
    }


def _clip_summary(c: Clip, speed_by_clip: dict) -> dict:
    end_us = c.timeline_start_us + c.timeline_duration_us
    speed_info = speed_by_clip.get(c.clip_id.upper())
    speed_val = speed_info["speed"] if speed_info else 1.0
    return {
        "clip_id": c.clip_id,
        "asset_id": c.asset_id,
        "timeline_start_us": c.timeline_start_us,
        "timeline_end_us": end_us,
        "timeline_start_s": round(c.timeline_start_us / 1_000_000, 3),
        "timeline_end_s": round(end_us / 1_000_000, 3),
        "source_in_us": c.source_in_us,
        "source_out_us": c.source_out_us,
        "source_in_s": round(c.source_in_us / 1_000_000, 3),
        "source_out_s": round(c.source_out_us / 1_000_000, 3),
        "duration_us": c.timeline_duration_us,
        "duration_s": round(c.timeline_duration_us / 1_000_000, 3),
        "speed": speed_val,
        "volume": c.volume,
        "opacity": c.opacity,
        "enabled": c.enabled,
    }


def render_markdown(s: dict) -> str:
    L: list[str] = []
    tl = s["timeline"]
    L.append(f"# IR Diagnostic — {tl['name']}\n")
    L.append(f"_Source draft:_ `{s['draft_path']}`\n")

    L.append("## Timeline\n")
    L.append("| field | value |")
    L.append("|---|---|")
    L.append(f"| name | `{tl['name']}` |")
    L.append(f"| fps | {tl['fps']} (NTSC: {tl['is_ntsc']}, FCP7 timebase: {tl['timebase']}) |")
    L.append(f"| resolution | {tl['width']} × {tl['height']} |")
    L.append(f"| duration (observed from clips) | {tl['duration_seconds']:.3f}s ({tl['duration_us']:,} µs) |")
    L.append(f"| duration (declared at top level) | {tl['declared_total_duration_seconds']:.3f}s ({tl['declared_total_duration_us']:,} µs) |")
    delta = tl['duration_seconds'] - tl['declared_total_duration_seconds']
    L.append(f"| delta (observed − declared) | {delta:+.3f}s |")
    L.append("")
    L.append(f"_Source metadata:_ `{s['source_metadata']}`\n")

    a = s["assets"]
    L.append(f"## Media Assets — {a['count']} total\n")
    L.append(f"By kind: `{a['by_kind']}`\n")
    if a["top_5"]:
        L.append("### Top 5\n")
        L.append("| asset_id | name | kind | duration | size | has_audio | path |")
        L.append("|---|---|---|---|---|---|---|")
        for x in a["top_5"]:
            res = f"{x['width']}×{x['height']}" if x.get('width') else "—"
            short_id = (x['asset_id'][:12] + "…") if len(x['asset_id']) > 13 else x['asset_id']
            L.append(f"| `{short_id}` | {x['name']} | {x['media_kind']} | "
                     f"{x['duration_seconds']:.2f}s | {res} | {x['has_audio']} | "
                     f"`{x['original_path']}` |")
        L.append("")

    def _render_tracks(title: str, tracks: list[dict], audio_cols: bool):
        L.append(f"## {title} — {len(tracks)}\n")
        if not tracks:
            L.append("_(none)_\n")
            return
        for t in tracks:
            short_tid = (t['track_id'][:12] + "…") if len(t['track_id']) > 13 else t['track_id']
            L.append(f"### {t['name']} (`{short_tid}`) — {t['clip_count']} clip(s), muted={t['muted']}\n")
            if not t['top_10_clips']:
                L.append("_(no clips)_\n")
                continue
            if audio_cols:
                L.append("| # | clip_id | asset | tl_start | tl_end | tl_dur | src_in | src_out | speed | vol |")
                L.append("|---|---|---|---|---|---|---|---|---|---|")
            else:
                L.append("| # | clip_id | asset | tl_start | tl_end | tl_dur | src_in | src_out | speed |")
                L.append("|---|---|---|---|---|---|---|---|---|")
            for i, c in enumerate(t['top_10_clips']):
                cid = (c['clip_id'][:10] + "…") if len(c['clip_id']) > 11 else c['clip_id']
                aid = (c['asset_id'][:10] + "…") if len(c['asset_id']) > 11 else c['asset_id']
                row = (f"| {i+1} | `{cid}` | `{aid}` | "
                       f"{c['timeline_start_s']}s | {c['timeline_end_s']}s | "
                       f"{c['duration_s']}s | {c['source_in_s']}s | "
                       f"{c['source_out_s']}s | {c['speed']} |")
                if audio_cols:
                    row += f" {c['volume']} |"
                L.append(row)
            if t['clip_count'] > 10:
                L.append(f"\n_(+{t['clip_count'] - 10} more clips not shown — see ir_summary.json)_")
            L.append("")

    _render_tracks("Video Tracks", s["video_tracks"], audio_cols=False)
    _render_tracks("Audio Tracks", s["audio_tracks"], audio_cols=True)

    L.append(f"## Text Tracks — {s['text_tracks_count']}\n")
    L.append(f"_(Not represented in IR; reader logs each as an unsupported item. v0.1 design.)_\n")
    for d in s["text_tracks_detail"]:
        L.append(f"- {d}")
    L.append("")

    u = s["unsupported"]
    L.append(f"## Unsupported Items — {u['total']} total\n")
    L.append("### By category\n")
    L.append("| category | count |")
    L.append("|---|---|")
    for cat, n in u["by_category"].items():
        L.append(f"| {cat} | {n} |")
    L.append("")
    if u["first_15"]:
        L.append("### First 15\n")
        for it in u["first_15"]:
            tag = f" @ {it['time_hint_us']/1e6:.2f}s" if it.get('time_hint_us') is not None else ""
            track = f" [{it['track_hint']}]" if it.get('track_hint') else ""
            L.append(f"- **{it['category']}**{track}{tag}: {it['detail']}")
        L.append("")

    if s["ir_inconsistencies"]:
        L.append(f"## ⚠ IR / Source Inconsistencies — {len(s['ir_inconsistencies'])}\n")
        L.append("Reader claims to honor `target_timerange.duration` on the timeline, "
                 "but `Clip.timeline_duration_us` is derived from `source_timerange.duration`. "
                 "These clips' IR length differs from their declared target length:\n")
        L.append("| clip | track | tl_start | ir_dur | target_dur | speed |")
        L.append("|---|---|---|---|---|---|")
        for x in s["ir_inconsistencies"][:20]:
            L.append(f"| `{x['clip_id']}` | {x['track']} | "
                     f"{x['timeline_start_us']/1e6:.2f}s | "
                     f"{x['ir_duration_us']/1e6:.3f}s | "
                     f"{x['target_duration_us']/1e6:.3f}s | "
                     f"{x['speed']} |")
        L.append("")

    return "\n".join(L) + "\n"


if __name__ == "__main__":
    sys.exit(main())
