"""AnalyzeWorker — run detect + scan_assets + read_draft in background."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QThread, Signal

from cutsmith.detect import detect_project
from cutsmith.gui.models import AnalysisResult, ProjectEntry
from cutsmith.ir import AssetClass
from cutsmith.reader import read_draft
from cutsmith.scanner import scan_assets


class AnalyzeWorker(QThread):
    finished = Signal(object)   # AnalysisResult
    error = Signal(str)

    def __init__(self, entry: ProjectEntry, parent=None) -> None:
        super().__init__(parent)
        self.entry = entry

    def run(self) -> None:
        result = AnalysisResult(entry=self.entry)
        try:
            path = self.entry.path

            # Detect (re-run to ensure freshness)
            detect = detect_project(path)
            self.entry.detect = detect

            # Find the actual draft file
            draft_path = _find_draft(path)
            if draft_path is None:
                result.error = "No draft_info.json found in project directory"
                self.finished.emit(result)
                return

            # scan_assets — asset manifest
            manifest = scan_assets(draft_path)
            result.manifest = manifest

            # Tally manifest counts
            all_entries = (
                manifest.videos + manifest.audios + manifest.music
                + manifest.sfx + manifest.images + manifest.stickers
            )
            report_only = manifest.effects + manifest.filters + manifest.transitions
            result.total_online = sum(1 for e in all_entries if e.is_online)
            result.total_offline = sum(1 for e in all_entries if not e.is_online)
            result.total_report_only = len(report_only)
            result.total_size_bytes = sum(
                getattr(e, "file_size_bytes", 0) or 0 for e in all_entries
            )

            # read_draft — timeline IR
            timeline = read_draft(draft_path)
            s = timeline.settings
            result.canvas_w = s.width
            result.canvas_h = s.height
            result.fps = float(s.frame_rate)
            result.video_track_count = len(timeline.video_tracks)
            result.audio_track_count = len(timeline.audio_tracks)

            clip_count = 0
            speed_clip = 0
            speed_curve = 0
            for track in timeline.video_tracks + timeline.audio_tracks:
                for clip in track.clips:
                    clip_count += 1
                    spd = getattr(clip, "speed", None)
                    crv = getattr(clip, "curve_speed", None)
                    if crv is not None:
                        speed_curve += 1
                    elif spd is not None and abs(spd - 1.0) > 0.01:
                        speed_clip += 1

            result.clip_count = clip_count
            result.speed_clip_count = speed_clip
            result.speed_curve_count = speed_curve

            sub_count = 0
            for st in timeline.subtitle_tracks:
                sub_count += len(st.cues)
            result.subtitle_cue_count = sub_count

            result.unsupported_count = len(timeline.unsupported)

            # Duration from source_metadata or fall back to track span
            sm = getattr(timeline, "source_metadata", {}) or {}
            dur = sm.get("draft_total_duration_us")
            if dur:
                result.duration_us = int(dur)
            else:
                # max timeline_start + duration across all clips
                spans = []
                for track in timeline.video_tracks + timeline.audio_tracks:
                    for clip in track.clips:
                        end = clip.timeline_start_us + clip.timeline_duration_us
                        spans.append(end)
                result.duration_us = max(spans) if spans else 0

        except Exception as exc:
            result.error = str(exc)

        result.cover_path = _find_cover(self.entry.path)
        self.finished.emit(result)


def _find_cover(project_path: Path) -> Path | None:
    """Return draft_cover.jpg path if it exists, else None."""
    candidates = [project_path / "draft_cover.jpg"]
    tl = project_path / "Timelines"
    if tl.is_dir():
        for sub in sorted(tl.iterdir()):
            candidates.append(sub / "draft_cover.jpg")
    for c in candidates:
        if c.exists():
            return c
    return None


def _find_draft(project_path: Path) -> Path | None:
    candidates = [
        project_path / "draft_info.json",
        project_path / "draft_content.json",
    ]
    # Check nested Timelines/UUID/ pattern
    tl = project_path / "Timelines"
    if tl.is_dir():
        for sub in sorted(tl.iterdir()):
            candidates.append(sub / "draft_info.json")
    for c in candidates:
        if c.exists():
            return c
    return None
