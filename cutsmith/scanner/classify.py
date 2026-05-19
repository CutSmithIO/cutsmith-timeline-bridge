"""Asset classification logic for scan-assets.

Maps CapCut material dicts + resolved paths to AssetClass values.
The reader stores `capcut_type` (the raw material `type` field) in
`MediaAsset.extras`, making audio sub-classification straightforward without
re-parsing the draft JSON.
"""

from __future__ import annotations

from pathlib import Path

from cutsmith.ir import AssetClass, MediaAsset, MediaKind

# Known CapCut cache root patterns on macOS. Expanded by `expand_cache_roots()`.
# Windows paths are not yet covered — deferred to v0.3 when collect ships.
_CACHE_ROOT_TEMPLATES = [
    "~/Library/Containers/com.lemon.lvoverseas/Data/Movies/CapCut/User Data/Cache",
    "~/Library/Containers/com.lemon.lvoverseas/Data/Library/Caches",
    "~/Library/Group Containers/group.com.lemon.lvoverseas",
    "~/Movies/CapCut/User Data/Cache",
    "~/Movies/JianyingPro/User Data/Cache",
    # CapCut for Mac (App Store variant)
    "~/Library/Containers/com.lemon.lvoveroverseas/Data/Movies/CapCut",
]

# CapCut's audio `type` field values and their AssetClass mappings.
_AUDIO_TYPE_MAP: dict[str, AssetClass] = {
    "music":                 AssetClass.CAPCUT_MUSIC,
    "sound":                 AssetClass.CAPCUT_SFX,
    "video_original_sound":  AssetClass.USER_AUDIO,  # embedded audio split to explicit track
    "extract_music":         AssetClass.USER_AUDIO,
    "record":                AssetClass.USER_AUDIO,
}


def expand_cache_roots() -> list[Path]:
    """Return expanded, deduplicated cache root paths that exist on disk."""
    seen: set[Path] = set()
    result: list[Path] = []
    for tmpl in _CACHE_ROOT_TEMPLATES:
        p = Path(tmpl).expanduser()
        if p not in seen:
            seen.add(p)
            result.append(p)
    return result


def is_cache_path(path: str, cache_roots: list[Path]) -> bool:
    """True when `path` is a descendant of any known CapCut cache directory."""
    if not path:
        return False
    try:
        p = Path(path)
        return any(p.is_relative_to(root) for root in cache_roots)
    except (ValueError, TypeError):
        return False


def classify_asset(asset: MediaAsset, cache_roots: list[Path]) -> AssetClass:
    """Determine AssetClass for an IR MediaAsset.

    Uses `asset.extras['capcut_type']` (stored by the reader) to distinguish
    CapCut library tracks from user-imported media without re-reading the draft.
    Cache-path check catches library assets whose `type` field is absent or
    non-standard.
    """
    cap_type = str(asset.extras.get("capcut_type") or "").lower()
    path = asset.original_path or ""

    if asset.media_kind == MediaKind.AUDIO:
        # 1. Explicit type field wins
        if cap_type in _AUDIO_TYPE_MAP:
            return _AUDIO_TYPE_MAP[cap_type]
        # 2. Cache path → CapCut library (no reliable type field in some versions)
        if is_cache_path(path, cache_roots):
            return AssetClass.CAPCUT_MUSIC  # default; can be refined by path segment
        return AssetClass.USER_AUDIO

    if asset.media_kind == MediaKind.VIDEO:
        return AssetClass.USER_VIDEO

    if asset.media_kind == MediaKind.IMAGE:
        return AssetClass.USER_IMAGE

    return AssetClass.UNKNOWN


def classify_raw_material(mat: dict, category: str, cache_roots: list[Path]) -> AssetClass:
    """Classify a non-IR material dict (sticker, effect, filter, transition).

    `category` is the CapCut materials dict key (e.g. 'stickers', 'effects').
    """
    mat_type = str(mat.get("type") or "").lower()
    path = str(mat.get("path") or "")

    if category == "stickers":
        return AssetClass.CAPCUT_STICKER

    if category in ("effects", "video_effects", "filters"):
        # effects[] stores both video effects AND filters (type=filter).
        # All are CapCut proprietary — sub-classification deferred to v0.4.
        return AssetClass.CAPCUT_EFFECT

    if category == "transitions":
        return AssetClass.CAPCUT_EFFECT

    if category in ("texts", "text_templates"):
        # These are styled text presets, not copyable media.
        return AssetClass.CAPCUT_EFFECT

    # Fallback: cache path heuristic
    if is_cache_path(path, cache_roots):
        return AssetClass.CAPCUT_EFFECT

    return AssetClass.UNKNOWN
