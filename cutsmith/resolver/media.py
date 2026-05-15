"""Resolve MediaAsset.original_path → absolute paths Premiere can find.

CapCut stores three kinds of paths in `materials.videos[].path` /
`materials.audios[].path`:

  1. Absolute paths on the machine that authored the draft, e.g.
     "/Users/alice/Movies/shoot01/clipA.mp4" or
     "C:\\Users\\alice\\Videos\\clipA.mp4". These break on any other machine.

  2. Paths under the draft's own Resources folder, e.g.
     "/Users/alice/Movies/JianyingPro/User Data/Projects/com.lveditor.draft/MyProj/Resources/import/clipA.mp4"
     These move with the project — when a draft is copied, Resources/ moves
     with it, so we can re-anchor by replacing the old project root with the
     current one.

  3. Cloud / library paths (CapCut stock content, AI-generated assets). These
     point inside the CapCut app's library directories and don't exist on
     other machines. We surface these as unresolved and let the user handle
     it (re-export, replace clip, etc.).

Strategy:
  - First try the path as-is (covers "draft hasn't moved").
  - Then try `search_roots` — directories the user passed in via CLI. Match
    by basename + size+duration heuristics. Basename match alone is the v0.1
    default; size/duration can be added later if we add ffprobe.
  - Track stats so the report can say e.g. "12/15 resolved, 3 missing".

The Premiere side: FCP7 XML uses `<pathurl>file:///...</pathurl>`. Premiere is
forgiving — when the pathurl is wrong, the project opens with offline clips
and the user can right-click → "Link Media" to relink. We minimize that by
trying hard here, but we never fabricate a path: unresolved clips get a
clearly-marked placeholder URL so Premiere's relink UI knows what to look for.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath, PureWindowsPath

from cutsmith.ir import Timeline


@dataclass
class ResolutionStats:
    total: int = 0
    resolved_as_is: int = 0           # path existed without help
    resolved_via_search: int = 0      # found by scanning search_roots
    unresolved: int = 0
    missing_assets: list[str] = field(default_factory=list)  # asset names that failed


def resolve_media_paths(
    timeline: Timeline,
    search_roots: list[str | Path] | None = None,
) -> ResolutionStats:
    """Populate `MediaAsset.resolved_path` for every asset in the timeline.

    `search_roots` is a list of directories to walk when the original path
    doesn't exist. Files are matched by basename only in v0.1.
    """
    stats = ResolutionStats()
    search_index = _build_search_index(search_roots or [])

    for asset in timeline.assets.values():
        stats.total += 1

        # Step 1: try the path verbatim. This handles the "draft hasn't been
        # moved" case and Windows-style paths on Windows hosts.
        normalized = _normalize_path(asset.original_path)
        if normalized and normalized.exists() and normalized.is_file():
            asset.resolved_path = str(normalized.resolve())
            stats.resolved_as_is += 1
            continue

        # Step 2: try basename match against search roots.
        basename = _basename_of(asset.original_path) or asset.name
        if basename and basename in search_index:
            candidates = search_index[basename]
            # If multiple matches, just pick the first — v0.1 doesn't have
            # enough info to disambiguate. Future: use file size + duration.
            asset.resolved_path = str(candidates[0].resolve())
            stats.resolved_via_search += 1
            continue

        # Step 3: give up. Leave resolved_path = None; writer will emit a
        # clearly-fake pathurl so Premiere's offline-clip relink works.
        stats.unresolved += 1
        stats.missing_assets.append(asset.name)

    return stats


# --------------------------------------------------------------------------- #
# helpers                                                                     #
# --------------------------------------------------------------------------- #

def _normalize_path(raw: str) -> Path | None:
    """Best-effort: convert any reasonable path string to a local Path.

    CapCut on Windows writes backslash paths; on macOS, forward-slash. When a
    draft moves between OSes, the path string is the wrong flavor for the
    current OS. We try both interpretations.
    """
    if not raw:
        return None

    # Direct attempt first — works when the OS matches the path flavor.
    p = Path(raw)
    if p.exists():
        return p

    # If we're on POSIX but the path looks Windows-y, try extracting basename
    # only (we have no way to know where the equivalent file lives).
    if "\\" in raw and os.sep == "/":
        # Don't return a Path that won't exist; let the search-root step
        # handle it via basename.
        return None
    if "/" in raw and os.sep == "\\":
        return None

    return p  # exists() will be False; caller falls through to search


def _basename_of(raw: str) -> str | None:
    """Get the filename component regardless of path flavor."""
    if not raw:
        return None
    if "\\" in raw and "/" not in raw:
        return PureWindowsPath(raw).name
    if "/" in raw and "\\" not in raw:
        return PurePosixPath(raw).name
    # Mixed or neither — let Path figure it out for the current OS.
    return Path(raw).name


def _build_search_index(roots: list[str | Path]) -> dict[str, list[Path]]:
    """Walk every search root once; map basename → list of full paths.

    O(n) up front so per-asset lookup is O(1).
    """
    index: dict[str, list[Path]] = {}
    for root in roots:
        root_path = Path(root)
        if not root_path.is_dir():
            continue
        for dirpath, _dirnames, filenames in os.walk(root_path):
            for fn in filenames:
                index.setdefault(fn, []).append(Path(dirpath) / fn)
    return index
