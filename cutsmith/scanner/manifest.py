"""AssetManifest schema — the scan-assets output format.

Designed to be:
  - GUI-friendly: flat dicts, no binary, UTF-8 JSON
  - Version-stable: schema_version lets consumers detect breaking changes
  - Collector-ready: collect_relative_path filled during `cutsmith collect`
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from cutsmith.ir import AssetClass


@dataclass
class ManifestEntry:
    """One referenced material in the project."""
    asset_id: str
    name: str
    asset_class: AssetClass
    original_path: str | None
    resolved_path: str | None
    is_cached: bool
    is_online: bool              # resolved_path exists and is a regular file
    file_size_bytes: int | None  # None when offline
    duration_us: int | None
    used_in_tracks: list[str]    # track names; empty for report-only materials
    clip_count: int
    # filled by collector (v0.3), not by scanner
    collect_relative_path: str | None = None

    def to_dict(self) -> dict:
        return {
            "asset_id": self.asset_id,
            "name": self.name,
            "asset_class": self.asset_class.value,
            "original_path": self.original_path,
            "resolved_path": self.resolved_path,
            "is_cached": self.is_cached,
            "is_online": self.is_online,
            "file_size_bytes": self.file_size_bytes,
            "duration_us": self.duration_us,
            "used_in_tracks": self.used_in_tracks,
            "clip_count": self.clip_count,
            "collect_relative_path": self.collect_relative_path,
        }


@dataclass
class AssetManifest:
    """Full asset scan result for one CapCut project."""
    schema_version: int = 1
    project_name: str = ""
    source_draft: str = ""
    app_version: int = 0
    duration_us: int = 0
    # IR-based categories (from reader)
    videos:   list[ManifestEntry] = field(default_factory=list)
    audios:   list[ManifestEntry] = field(default_factory=list)   # USER_AUDIO
    music:    list[ManifestEntry] = field(default_factory=list)   # CAPCUT_MUSIC
    sfx:      list[ManifestEntry] = field(default_factory=list)   # CAPCUT_SFX
    images:   list[ManifestEntry] = field(default_factory=list)
    # Non-IR categories (report-only in v0.2)
    stickers:    list[ManifestEntry] = field(default_factory=list)
    effects:     list[ManifestEntry] = field(default_factory=list)
    filters:     list[ManifestEntry] = field(default_factory=list)
    transitions: list[ManifestEntry] = field(default_factory=list)
    fonts:       list[ManifestEntry] = field(default_factory=list)  # app-bundle; not copied
    # Cross-cutting
    offline:  list[ManifestEntry] = field(default_factory=list)   # all is_online=False
    # Stats
    total_assets: int = 0
    online_count: int = 0
    offline_count: int = 0
    cached_count: int = 0
    total_online_size_bytes: int = 0

    def all_entries(self) -> list[ManifestEntry]:
        return (
            self.videos + self.audios + self.music + self.sfx + self.images
            + self.stickers + self.effects + self.filters + self.transitions
            + self.fonts
        )

    def to_dict(self) -> dict:
        def _entries(lst: list[ManifestEntry]) -> list[dict]:
            return [e.to_dict() for e in lst]

        return {
            "schema_version": self.schema_version,
            "project_name": self.project_name,
            "source_draft": self.source_draft,
            "app_version": self.app_version,
            "duration_us": self.duration_us,
            "stats": {
                "total_assets": self.total_assets,
                "online_count": self.online_count,
                "offline_count": self.offline_count,
                "cached_count": self.cached_count,
                "total_online_size_bytes": self.total_online_size_bytes,
            },
            "videos":      _entries(self.videos),
            "audios":      _entries(self.audios),
            "music":       _entries(self.music),
            "sfx":         _entries(self.sfx),
            "images":      _entries(self.images),
            "stickers":    _entries(self.stickers),
            "effects":     _entries(self.effects),
            "filters":     _entries(self.filters),
            "transitions": _entries(self.transitions),
            "fonts":       _entries(self.fonts),
            "offline":     _entries(self.offline),
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)
