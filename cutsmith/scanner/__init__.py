"""scan-assets pipeline: enumerate and classify all materials in a CapCut project.

Execution order:
  1. detect()              — validate format, reject encrypted
  2. read_draft()          — Timeline IR (existing reader)
  3. resolve_media_paths() — populate resolved_path on IR assets
  4. _load_extra_mats()    — load material categories the reader skips
                             (stickers, effects, transitions, text_templates)
  5. _build_track_usage()  — asset_id/mat_id → {tracks, clip_count}
  6. classify + probe      — fill asset_class, is_cached, file_size_bytes
  7. assemble_manifest()   — produce AssetManifest

IR-based assets (videos, audios) go through the full resolver. Non-IR
assets (stickers, effects, filters, transitions) get a direct path check
— no basename-search, because they live in CapCut's cache and moving them
is handled by CapCut, not by us.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from cutsmith.detect import detect_project
from cutsmith.ir import AssetClass, MediaAsset
from cutsmith.reader import read_draft
from cutsmith.resolver.media import resolve_media_paths
from cutsmith.scanner.classify import (
    classify_asset,
    classify_raw_material,
    expand_cache_roots,
    is_cache_path,
)
from cutsmith.scanner.manifest import AssetManifest, ManifestEntry


# ─── public API ──────────────────────────────────────────────────────────────

def scan_assets(
    draft_path: str | Path,
    search_roots: list[str | Path] | None = None,
) -> AssetManifest:
    """Enumerate and classify every referenced material in a CapCut project.

    `draft_path` can be a project directory (detect will find the entry file)
    or a direct path to a draft JSON.
    """
    draft_path = Path(draft_path)

    # If a directory was given, let detect find the entry file.
    if draft_path.is_dir():
        result = detect_project(draft_path)
        if not result.timeline_entry_path:
            raise ValueError(f"No supported draft found in {draft_path}")
        if result.encryption != "plaintext":
            raise ValueError(f"Draft is encrypted — scan-assets requires plaintext")
        draft_path = Path(result.timeline_entry_path)

    cache_roots = expand_cache_roots()

    # Steps 1–3: read IR and resolve paths
    timeline = read_draft(draft_path)
    resolve_media_paths(timeline, search_roots or [])

    # Step 4: load extra material categories the reader skips
    with draft_path.open("r", encoding="utf-8") as f:
        raw = json.load(f)
    extra = _load_extra_mats(raw)

    # Step 5: build usage map from all tracks (including text/sticker/filter/effect)
    usage = _build_track_usage(raw)

    # Step 6: classify IR assets and build their manifest entries
    manifest = AssetManifest(
        project_name=timeline.name,
        source_draft=str(draft_path),
        app_version=int(timeline.source_metadata.get("capcut_version") or 0),
        duration_us=int(timeline.source_metadata.get("draft_total_duration_us") or 0),
    )

    for asset in timeline.assets.values():
        ac = classify_asset(asset, cache_roots)
        asset.asset_class = ac
        asset.is_cached = is_cache_path(asset.original_path or "", cache_roots)
        entry = _ir_asset_to_entry(asset, ac, usage)
        _place_ir_entry(manifest, entry)

    # Step 7: non-IR materials
    for category, items in extra.items():
        for mat in items:
            ac = classify_raw_material(mat, category, cache_roots)
            entry = _raw_mat_to_entry(mat, category, ac, cache_roots, usage)
            _place_raw_entry(manifest, category, entry)

    # Step 8: build offline cross-list and stats
    _finalise(manifest)
    return manifest


# ─── helpers: IR → ManifestEntry ─────────────────────────────────────────── #

def _ir_asset_to_entry(
    asset: MediaAsset,
    ac: AssetClass,
    usage: dict[str, dict],
) -> ManifestEntry:
    rpath = asset.resolved_path
    online = bool(rpath and Path(rpath).is_file())
    size = _probe_size(rpath) if online else None
    u = usage.get(asset.asset_id, {})
    return ManifestEntry(
        asset_id=asset.asset_id,
        name=asset.name,
        asset_class=ac,
        original_path=asset.original_path,
        resolved_path=rpath,
        is_cached=asset.is_cached,
        is_online=online,
        file_size_bytes=size,
        duration_us=asset.duration_us,
        used_in_tracks=u.get("tracks", []),
        clip_count=u.get("clip_count", 0),
    )


def _place_ir_entry(manifest: AssetManifest, entry: ManifestEntry) -> None:
    ac = entry.asset_class
    if ac == AssetClass.USER_VIDEO:
        manifest.videos.append(entry)
    elif ac == AssetClass.USER_AUDIO:
        manifest.audios.append(entry)
    elif ac == AssetClass.CAPCUT_MUSIC:
        manifest.music.append(entry)
    elif ac == AssetClass.CAPCUT_SFX:
        manifest.sfx.append(entry)
    elif ac == AssetClass.USER_IMAGE:
        manifest.images.append(entry)
    else:
        manifest.audios.append(entry)  # unknown audio — safe fallback


# ─── helpers: raw material → ManifestEntry ───────────────────────────────── #

def _raw_mat_to_entry(
    mat: dict,
    category: str,
    ac: AssetClass,
    cache_roots: list[Path],
    usage: dict[str, dict],
) -> ManifestEntry:
    mat_id = str(mat.get("id") or "")
    name = str(mat.get("name") or mat.get("id") or "")
    path = str(mat.get("path") or "")
    cached = is_cache_path(path, cache_roots)
    online = bool(path and Path(path).is_file())
    size = _probe_size(path) if online else None
    u = usage.get(mat_id, {})
    return ManifestEntry(
        asset_id=mat_id,
        name=name,
        asset_class=ac,
        original_path=path or None,
        resolved_path=path if online else None,
        is_cached=cached,
        is_online=online,
        file_size_bytes=size,
        duration_us=int(mat.get("duration") or 0) or None,
        used_in_tracks=u.get("tracks", []),
        clip_count=u.get("clip_count", 0),
    )


def _place_raw_entry(
    manifest: AssetManifest,
    category: str,
    entry: ManifestEntry,
) -> None:
    mat_type = entry.asset_class  # already classified by classify_raw_material
    # Distinguish filter from generic effect by category
    if category in ("filters",) or (
        category == "effects" and entry.asset_class == AssetClass.CAPCUT_EFFECT
        and _entry_is_filter(entry)
    ):
        manifest.filters.append(entry)
    elif category in ("effects", "video_effects"):
        manifest.effects.append(entry)
    elif category == "stickers":
        manifest.stickers.append(entry)
    elif category == "transitions":
        manifest.transitions.append(entry)
    elif category in ("texts", "text_templates"):
        pass  # text presets are not media; excluded from manifest
    else:
        manifest.effects.append(entry)


def _entry_is_filter(entry: ManifestEntry) -> bool:
    # The raw material's type=filter is not preserved in ManifestEntry.
    # We rely on the category passed to _place_raw_entry instead.
    # This function is a no-op placeholder for v0.4 sub-classification.
    return False


# ─── helpers: extra materials ─────────────────────────────────────────────── #

# Categories the reader intentionally skips (it logs them as UnsupportedItem).
# We read them here to build the non-IR portion of the manifest.
_EXTRA_CATEGORIES = ("stickers", "effects", "video_effects", "filters", "transitions")


def _load_extra_mats(raw: dict) -> dict[str, list[dict]]:
    """Load only the non-IR material categories."""
    materials = raw.get("materials") or {}
    result: dict[str, list[dict]] = {}
    for cat in _EXTRA_CATEGORIES:
        items = materials.get(cat) or []
        if items:
            # For effects[], split by type: filter vs video_effect
            if cat == "effects":
                filters = [m for m in items if str(m.get("type") or "").lower() == "filter"]
                effects = [m for m in items if str(m.get("type") or "").lower() != "filter"]
                if filters:
                    result.setdefault("filters", []).extend(filters)
                if effects:
                    result.setdefault("effects", []).extend(effects)
            else:
                result[cat] = list(items)
    return result


# ─── helpers: usage map ───────────────────────────────────────────────────── #

def _build_track_usage(raw: dict) -> dict[str, dict]:
    """Build material_id → {tracks: [name,...], clip_count: N} from all tracks.

    Scans every track type — video, audio, text, sticker, filter, effect — so
    non-IR materials (stickers, filters on dedicated tracks) are accounted for.
    """
    usage: dict[str, dict] = {}
    tracks = raw.get("tracks") or []

    for i, track in enumerate(tracks):
        track_type = track.get("type", "track")
        track_name = track.get("name") or f"{track_type.upper()}{i+1}"
        for seg in track.get("segments") or []:
            mid = str(seg.get("material_id") or "")
            if not mid:
                continue
            if mid not in usage:
                usage[mid] = {"tracks": [], "clip_count": 0}
            if track_name not in usage[mid]["tracks"]:
                usage[mid]["tracks"].append(track_name)
            usage[mid]["clip_count"] += 1

    return usage


# ─── helpers: stats ───────────────────────────────────────────────────────── #

def _finalise(manifest: AssetManifest) -> None:
    """Compute cross-list and aggregate stats."""
    all_entries = manifest.all_entries()
    manifest.total_assets = len(all_entries)
    manifest.online_count = sum(1 for e in all_entries if e.is_online)
    manifest.offline_count = sum(1 for e in all_entries if not e.is_online)
    manifest.cached_count = sum(1 for e in all_entries if e.is_cached)
    manifest.total_online_size_bytes = sum(
        e.file_size_bytes for e in all_entries
        if e.is_online and e.file_size_bytes is not None
    )
    manifest.offline = [e for e in all_entries if not e.is_online]


def _probe_size(path: str | None) -> int | None:
    if not path:
        return None
    try:
        return os.path.getsize(path)
    except OSError:
        return None
