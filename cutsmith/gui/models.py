"""GUI data models — thin dataclasses bridging core APIs to the UI layer."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from cutsmith.detect.probe import DetectionResult
from cutsmith.scanner.manifest import AssetManifest


@dataclass
class ProjectEntry:
    """One row in the project discovery panel."""
    path: Path
    detect: DetectionResult
    # Derived display fields
    display_name: str = ""
    app_label: str = ""      # "CapCut Desktop" / "JianyingPro" / "Unknown"
    date_label: str = ""     # mtime formatted as YYYY-MM-DD
    group: str = ""          # "capcut" / "jianying" / "encrypted" / "unknown"

    def __post_init__(self) -> None:
        if not self.display_name:
            self.display_name = self.path.name
        if not self.app_label:
            at = self.detect.app_type or "unknown"
            self.app_label = {
                "capcut": "CapCut Desktop",
                "jianying": "JianyingPro",
            }.get(at, "Unknown")
        if not self.group:
            if self.detect.encryption not in (None, "none", "plaintext", ""):
                self.group = "encrypted"
            else:
                self.group = self.detect.app_type or "unknown"


@dataclass
class AnalysisResult:
    """All data the UI needs for the center + right panels."""
    entry: ProjectEntry

    # From detect (already in entry, aliased for convenience)
    detect: DetectionResult = field(init=False)

    # From scan_assets
    manifest: Optional[AssetManifest] = None

    # From read_draft / Timeline
    duration_us: int = 0
    canvas_w: int = 1920
    canvas_h: int = 1080
    fps: float = 24.0
    video_track_count: int = 0
    audio_track_count: int = 0
    clip_count: int = 0
    speed_clip_count: int = 0      # speed != 1.0, no speed curve
    speed_curve_count: int = 0     # has speed curve
    subtitle_cue_count: int = 0
    unsupported_count: int = 0

    # From manifest totals
    total_online: int = 0
    total_offline: int = 0
    total_report_only: int = 0
    total_size_bytes: int = 0

    # Cover image path (draft_cover.jpg if found, else None → placeholder)
    cover_path: Optional[Path] = None

    # Error state
    error: Optional[str] = None

    def __post_init__(self) -> None:
        self.detect = self.entry.detect

    @property
    def duration_seconds(self) -> float:
        return self.duration_us / 1_000_000

    @property
    def duration_label(self) -> str:
        s = int(self.duration_seconds)
        m, sec = divmod(s, 60)
        h, min_ = divmod(m, 60)
        if h:
            return f"{h}:{min_:02d}:{sec:02d}"
        return f"{min_}:{sec:02d}"

    @property
    def resolution_label(self) -> str:
        return f"{self.canvas_w}×{self.canvas_h}"

    @property
    def fps_label(self) -> str:
        if abs(self.fps - round(self.fps)) < 0.005:
            return f"{int(round(self.fps))}fps"
        return f"{self.fps:.2f}fps"

    @property
    def size_label(self) -> str:
        b = self.total_size_bytes
        if b >= 1_073_741_824:
            return f"{b / 1_073_741_824:.1f} GB"
        if b >= 1_048_576:
            return f"{b / 1_048_576:.1f} MB"
        if b >= 1024:
            return f"{b / 1024:.0f} KB"
        return f"{b} B"

    def default_out_dir(self) -> Path:
        return Path.cwd() / "out_collect" / self.entry.display_name

    @property
    def is_portable(self) -> bool:
        enc = (self.detect.encryption or "").lower()
        is_encrypted = enc not in ("", "none", "plaintext")
        is_error = self.detect.supported_status in ("error",)
        return self.total_offline == 0 and not is_encrypted and not is_error

    @property
    def readability_label(self) -> str:
        """Human-readable schema status for the card meta line."""
        st = self.detect.supported_status or "unknown"
        enc = (self.detect.encryption or "").lower()
        if enc not in ("", "none", "plaintext"):
            return "Encrypted"
        schema = self.detect.schema_type or ""
        if schema == "modern_plaintext":
            return "Plaintext · Ready"
        if schema == "legacy":
            return "Legacy format"
        if st == "supported":
            return "Ready"
        if st == "unverified":
            return "Plaintext"
        return st

    @property
    def has_warnings(self) -> bool:
        return (
            self.speed_curve_count > 0
            or self.speed_clip_count > 0
            or self.unsupported_count > 0
            or self.total_offline > 0
        )
