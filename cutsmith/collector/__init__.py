"""cutsmith.collector — copy + relink a CapCut project for Premiere delivery.

`collect` is the v0.3 pipeline:
  1. scan_assets()           → AssetManifest (classify all materials)
  2. read_draft()            → Timeline IR   (for XML writing)
  3. resolve_media_paths()   → populate resolved_path on IR assets
  4. _copy_online_assets()   → copy to media/<class>/, build path_override
  5. write_fcp7_xml()        → with path_override (XML points at copied media)
  6. write_report()          → standard compat report + collect addendum
  7. _write_offline_report() → <stem>.offline.md if any assets are offline
  8. write manifest JSON     → with collect_relative_path populated per entry

What gets copied
----------------
  user_video   → media/video/
  user_audio   → media/audio/
  capcut_music → media/music/    (licensing note written in report)
  capcut_sfx   → media/sfx/
  user_image   → media/images/
  capcut_sticker (online only, rare) → media/stickers/

What is NOT copied
------------------
  capcut_effect / capcut_font / unknown → report-only, not portable
  Any asset where is_online=False       → listed in offline.md

Filename collision
------------------
  Two assets with the same basename in the same subdir get the second one
  renamed to `<stem>_<asset_id[:8]><suffix>`.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from pathlib import Path

from cutsmith.collector.filetype import FileType, detect_file_type, should_normalize_extension
from cutsmith.detect import detect_project
from cutsmith.ir import AssetClass
from cutsmith.reader import read_draft
from cutsmith.report import write_report
from cutsmith.resolver import resolve_media_paths
from cutsmith.scanner import scan_assets
from cutsmith.scanner.manifest import AssetManifest, ManifestEntry
from cutsmith.writer import write_fcp7_xml


# ─── constants ────────────────────────────────────────────────────────────────

_COPY_CLASS_TO_SUBDIR: dict[AssetClass, str] = {
    AssetClass.USER_VIDEO:      "video",
    AssetClass.USER_AUDIO:      "audio",
    AssetClass.CAPCUT_MUSIC:    "music",
    AssetClass.CAPCUT_SFX:      "sfx",
    AssetClass.USER_IMAGE:      "images",
    AssetClass.CAPCUT_STICKER:  "stickers",
}

# These classes are never copied regardless of online status.
_REPORT_ONLY_CLASSES: frozenset[AssetClass] = frozenset({
    AssetClass.CAPCUT_EFFECT,
    AssetClass.CAPCUT_FONT,
    AssetClass.UNKNOWN,
})

# Action hints for the offline report, by asset class.
_OFFLINE_ACTION: dict[AssetClass, str] = {
    AssetClass.USER_VIDEO:      "locate the file and use Premiere's Link Media to relink",
    AssetClass.USER_AUDIO:      "locate the file and use Premiere's Link Media to relink",
    AssetClass.USER_IMAGE:      "locate the file and use Premiere's Link Media to relink",
    AssetClass.CAPCUT_MUSIC:    (
        "re-open the project in CapCut to re-download, then collect again; "
        "verify distribution rights before publishing"
    ),
    AssetClass.CAPCUT_SFX:      "re-open the project in CapCut to re-download, then collect again",
    AssetClass.CAPCUT_STICKER:  "replace with a PNG/GIF from a third-party asset pack in Premiere",
    AssetClass.CAPCUT_EFFECT:   "rebuild using Premiere's native effects or LUTs",
    AssetClass.CAPCUT_FONT:     "install the font on this machine or use a Premiere system font",
    AssetClass.UNKNOWN:         "investigate asset type; rebuild manually in Premiere",
}


# ─── public result types ──────────────────────────────────────────────────────

@dataclass
class CollectStats:
    total_assets: int = 0
    copied_count: int = 0
    deduped_count: int = 0              # same physical file referenced multiple times
    offline_count: int = 0              # online=False AND copyable class
    skipped_report_only_count: int = 0  # CAPCUT_EFFECT / FONT / UNKNOWN
    total_copied_size_bytes: int = 0
    extension_normalized_count: int = 0  # files whose extension was corrected


@dataclass
class CollectResult:
    project_name: str
    out_dir: Path
    xml_path: Path
    report_path: Path
    manifest_path: Path
    offline_report_path: Path | None
    relink_guide_path: Path | None
    stats: CollectStats
    manifest: AssetManifest
    written_files: list[Path] = field(default_factory=list)


# ─── public API ───────────────────────────────────────────────────────────────

def collect(
    project_path: str | Path,
    out_dir: str | Path,
    search_roots: list[str | Path] | None = None,
    name: str | None = None,
) -> CollectResult:
    """Run the full collect pipeline. Returns a CollectResult."""
    project_path = Path(project_path)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    draft_path = _resolve_draft_path(project_path)

    manifest = scan_assets(draft_path, search_roots)
    if name:
        manifest.project_name = name
    stem = manifest.project_name or "project"

    timeline = read_draft(draft_path)
    if name:
        timeline.name = name
    resolution = resolve_media_paths(timeline, search_roots or [])

    media_dir = out_dir / "media"
    path_override, stats = _copy_online_assets(manifest, media_dir, out_dir)

    # Populate collect-specific manifest fields now that stats are known.
    manifest.collected_root = str(out_dir.resolve())
    manifest.relink_root_hint = str((out_dir / "media").resolve())
    manifest.path_mode = "collected_absolute"
    manifest.package_portable = "full" if stats.offline_count == 0 else "partial"
    manifest.report_only_count = stats.skipped_report_only_count
    manifest.normalized_extension_count = stats.extension_normalized_count

    xml_path = out_dir / f"{stem}.xml"
    write_fcp7_xml(timeline, xml_path, path_override=path_override)

    report_path = out_dir / f"{stem}.report.md"
    _write_collect_report(
        timeline, resolution, manifest, stats, report_path,
        xml_path=xml_path, stem=stem,
    )

    manifest_path = out_dir / f"{stem}.manifest.json"
    manifest_path.write_text(manifest.to_json(), encoding="utf-8")

    offline_report_path: Path | None = None
    if manifest.offline:
        offline_report_path = out_dir / f"{stem}.offline.md"
        _write_offline_report(manifest, offline_report_path, stem)

    relink_guide_path = out_dir / f"{stem}.relink_guide.md"
    _write_relink_guide(manifest, stats, relink_guide_path, stem)

    written = [xml_path, report_path, manifest_path, relink_guide_path]
    if offline_report_path:
        written.append(offline_report_path)

    return CollectResult(
        project_name=stem,
        out_dir=out_dir,
        xml_path=xml_path,
        report_path=report_path,
        manifest_path=manifest_path,
        offline_report_path=offline_report_path,
        relink_guide_path=relink_guide_path,
        stats=stats,
        manifest=manifest,
        written_files=written,
    )


# ─── internal helpers ─────────────────────────────────────────────────────────

def _resolve_draft_path(project_path: Path) -> Path:
    if project_path.is_file():
        return project_path
    result = detect_project(project_path)
    if not result.timeline_entry_path:
        raise ValueError(f"No supported draft found in {project_path}")
    if result.encryption != "plaintext":
        raise ValueError(f"Draft is encrypted — collect requires plaintext")
    return Path(result.timeline_entry_path)


def _copy_online_assets(
    manifest: AssetManifest,
    media_dir: Path,
    out_dir: Path,
) -> tuple[dict[str, str], CollectStats]:
    """Copy every online copyable asset to media/<subdir>/.

    Returns (path_override, stats).
    path_override maps asset_id → absolute destination path string.
    Mutates manifest entries: sets collect_relative_path, original_extension,
    detected_extension, and extension_normalized on copied entries.
    """
    stats = CollectStats()
    path_override: dict[str, str] = {}
    used_names: dict[str, set[str]] = {}
    # Dedup: maps canonical (resolved, subdir, logical_name) → dest path so
    # multiple IR assets that reference the same physical file share one copy.
    resolved_to_dest: dict[str, Path] = {}

    for entry in manifest.all_entries():
        stats.total_assets += 1

        if entry.asset_class in _REPORT_ONLY_CLASSES:
            stats.skipped_report_only_count += 1
            continue

        if not entry.is_online or not entry.resolved_path:
            stats.offline_count += 1
            continue

        src = Path(entry.resolved_path)

        # Detect true file type and normalize extension if needed.
        ft = detect_file_type(src)
        detected_ext = ft.ext if ft else None
        normalized = should_normalize_extension(src.suffix, detected_ext)

        entry.original_extension = src.suffix or None
        entry.detected_extension = detected_ext
        entry.extension_normalized = normalized

        if normalized:
            logical_name = src.stem + (detected_ext or src.suffix)
        else:
            logical_name = src.name

        subdir_name = _COPY_CLASS_TO_SUBDIR.get(entry.asset_class, "misc")
        dedup_key = f"{src.resolve()}|{subdir_name}"

        # Dedup: if this exact physical file was already copied to the same
        # subdir, reuse the destination instead of making a second copy.
        if dedup_key in resolved_to_dest:
            dest = resolved_to_dest[dedup_key]
            rel = dest.relative_to(out_dir)
            entry.collect_relative_path = str(rel)
            path_override[entry.asset_id] = str(dest.resolve())
            stats.deduped_count += 1
            continue

        dest_dir = media_dir / subdir_name
        dest_dir.mkdir(parents=True, exist_ok=True)
        used_names.setdefault(subdir_name, set())

        dest = _unique_dest(src, entry.asset_id, dest_dir, used_names[subdir_name],
                            name=logical_name)
        shutil.copy2(src, dest)

        if normalized:
            stats.extension_normalized_count += 1

        try:
            size = dest.stat().st_size
        except OSError:
            size = 0
        stats.copied_count += 1
        stats.total_copied_size_bytes += size

        resolved_to_dest[dedup_key] = dest
        rel = dest.relative_to(out_dir)
        entry.collect_relative_path = str(rel)
        path_override[entry.asset_id] = str(dest.resolve())

    return path_override, stats


def _unique_dest(
    src: Path,
    asset_id: str,
    dest_dir: Path,
    used_names: set[str],
    name: str | None = None,
) -> Path:
    """Return a unique destination path; disambiguate with asset_id[:8] on collision.

    *name* overrides the filename derived from *src* (used after extension
    normalization so the disambiguated suffix also uses the corrected extension).
    """
    effective = Path(name) if name else src
    final_name = effective.name
    if final_name not in used_names:
        used_names.add(final_name)
        return dest_dir / final_name
    disambig = f"{effective.stem}_{asset_id[:8]}{effective.suffix}"
    used_names.add(disambig)
    return dest_dir / disambig


def _write_collect_report(
    timeline,
    resolution,
    manifest: AssetManifest,
    stats: CollectStats,
    output_path: Path,
    xml_path: Path | None = None,
    stem: str = "project",
) -> None:
    write_report(timeline, resolution, output_path, xml_output_path=xml_path)

    sz_mb = stats.total_copied_size_bytes / 1_048_576
    normalized_entries = [e for e in manifest.all_entries() if e.extension_normalized]

    with output_path.open("a", encoding="utf-8") as f:
        f.write("\n## Collect package\n\n")
        f.write("| | Count |\n")
        f.write("|---|---|\n")
        f.write(f"| Assets copied | **{stats.copied_count}** |\n")
        if stats.deduped_count:
            f.write(f"| Shared (same file, no extra copy) | {stats.deduped_count} |\n")
        if stats.extension_normalized_count:
            f.write(f"| Extension normalized | {stats.extension_normalized_count} |\n")
        f.write(f"| Offline (not copied) | {stats.offline_count} |\n")
        f.write(f"| Report-only (proprietary) | {stats.skipped_report_only_count} |\n")
        f.write(f"| Total copied size | {sz_mb:.1f} MB |\n")
        f.write("\n")

        if normalized_entries:
            f.write("### Extension normalization\n\n")
            f.write(
                "The following files had incorrect or missing extensions in the CapCut "
                "cache. Extensions were corrected based on file magic bytes so Premiere "
                "can open them directly.\n\n"
            )
            f.write("| Original filename | Collected as | Detected type |\n")
            f.write("|---|---|---|\n")
            for e in normalized_entries:
                orig_name = Path(e.original_path or e.name).name
                collected_name = (
                    Path(e.collect_relative_path).name
                    if e.collect_relative_path else "?"
                )
                f.write(f"| `{orig_name}` | `{collected_name}` | `{e.detected_extension}` |\n")
            f.write("\n")

        f.write(
            "**CapCut proprietary assets** (effects, transitions, filters, stickers) "
            "are **not portable** — they cannot be transferred outside CapCut. "
            "Rebuild them using Premiere's native equivalents.\n\n"
        )
        f.write(
            "**CapCut Music licensing**: tracks from the CapCut library remain "
            "subject to CapCut/TikTok licensing terms. Verify distribution rights "
            "before publishing content that includes them.\n\n"
        )
        f.write(
            "**Speed-changed clips**: CutSmith emits an explicit FCP7 `timeremap` filter "
            "so Premiere reconstructs Speed/Duration on import (e.g. 200%, 49.91%). "
            "No manual adjustment is needed. Variable-speed curves (`speed_curve`) "
            "are report-only — the clip plays at 1.0× in Premiere.\n\n"
        )
        f.write(
            "**Speed trim boundary (known edge case)**: a 2× clip that exhausts its "
            "source file will show wavy trim handles in Premiere — this is expected, "
            "not a CutSmith bug. The exported timeline slot is correct; there are "
            "simply no additional source frames available. See `{stem}.relink_guide.md` "
            "for details.\n\n".replace("{stem}", stem)
        )
        if manifest.offline:
            f.write(f"See `{stem}.offline.md` for all unresolved assets and suggested actions.\n")
        f.write(f"\nSee `{stem}.relink_guide.md` for Premiere import and relink instructions.\n")


def _write_relink_guide(
    manifest: AssetManifest,
    stats: CollectStats,
    output_path: Path,
    stem: str,
) -> None:
    """Write <stem>.relink_guide.md — Premiere import and relink instructions."""
    media_root = manifest.relink_root_hint or "(media/ inside the collect output directory)"
    portable = manifest.package_portable

    lines: list[str] = []
    lines.append(f"# Relink Guide — {stem}\n")
    lines.append(
        "Generated by `cutsmith collect`. Keep this file with the package "
        "so any editor who opens it knows where to find the media.\n"
    )

    lines.append("\n## Importing into Premiere\n")
    lines.append(f"1. `File → Import…`, select `{stem}.xml`.")
    lines.append("   **Do not** use `Open Project`.")
    lines.append("2. Premiere creates a Sequence and Project panel source items.")
    if portable == "full":
        lines.append("3. All assets should link automatically — no manual relink step needed.")
    else:
        lines.append(
            "3. Assets that were online will link automatically. "
            "Offline clips (listed in `.offline.md`) still need manual relink."
        )
    lines.append("")

    lines.append("\n## If clips appear as Offline\n")
    lines.append("Right-click any offline clip in the Project panel → **Link Media…**")
    lines.append("Navigate to:\n")
    lines.append(f"    {media_root}\n")
    lines.append(
        "Premiere will auto-link remaining offline clips by name from the "
        "same folder (this works because every clip carries a `<masterclipid>` "
        "back-reference to its source item).\n"
    )

    lines.append("\n## Media folder layout\n")
    lines.append("```")
    lines.append("media/")
    lines.append("├── video/      ← user video clips")
    lines.append("├── audio/      ← user audio / voiceover")
    lines.append("├── images/     ← image overlays and thumbnails")
    lines.append("├── music/      ← CapCut music library tracks *")
    lines.append("├── sfx/        ← CapCut SFX *")
    lines.append("└── stickers/   ← sticker assets (rare)")
    lines.append("```\n")
    lines.append(
        "\\* **CapCut music licensing**: tracks from the CapCut/TikTok library "
        "remain subject to CapCut/TikTok licensing terms. Verify distribution "
        "rights before publishing content that includes them.\n"
    )

    lines.append("\n## Assets NOT included\n")
    lines.append(
        "The following are **not portable** outside CapCut and are absent from `media/`:\n"
    )
    lines.append("- CapCut effects, video effects, plugin effects")
    lines.append("- CapCut transitions")
    lines.append("- CapCut filters and HSL adjustments")
    lines.append("- CapCut fonts (install the font on the destination machine manually)\n")
    lines.append(
        f"Rebuild these using Premiere's native effects or third-party plugins. "
        f"See `{stem}.report.md` for the full list of dropped items.\n"
    )

    lines.append("\n## Speed-changed clips\n")
    lines.append(
        "CutSmith emits an explicit FCP7 `timeremap` filter so Premiere reconstructs "
        "Speed/Duration on import (e.g. 200%, 49.91%). "
        "No manual Speed/Duration adjustment is needed after import.\n"
    )
    lines.append(
        "Variable-speed curves (`speed_curve`) are report-only — those clips play "
        "at 1.0× in Premiere. Reconstruct via "
        "Effect Controls → Time Remapping → Velocity if needed.\n"
    )
    lines.append("\n### Known edge case — trim boundary on speed-changed clips\n")
    lines.append(
        "When a speed-changed clip (e.g. 2×) uses the entire source file, Premiere "
        "may show **wavy trim handles** if you try to extend it beyond its current "
        "boundaries. This is expected behaviour, not a CutSmith bug:\n"
    )
    lines.append("- The exported timeline slot duration is correct.")
    lines.append(
        "- The wavy lines mean the source material has no additional frames "
        "beyond the file boundary."
    )
    lines.append(
        "- **To recover frames:** use a longer source take in CapCut and re-export, "
        "or manually relink the clip to a longer file in Premiere.\n"
    )

    if stats.extension_normalized_count:
        lines.append("\n## Extension normalization\n")
        lines.append(
            f"{stats.extension_normalized_count} file(s) had incorrect or missing "
            "extensions in the CapCut cache. Extensions were corrected based on "
            "file magic bytes so Premiere can open them directly. "
            f"See `{stem}.report.md` for the full table.\n"
        )

    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_offline_report(
    manifest: AssetManifest,
    output_path: Path,
    stem: str,
) -> None:
    """Write <stem>.offline.md — all offline assets bucketed by user vs CapCut."""
    user_classes = {AssetClass.USER_VIDEO, AssetClass.USER_AUDIO, AssetClass.USER_IMAGE}
    user_offline = [e for e in manifest.offline if e.asset_class in user_classes]
    capcut_offline = [e for e in manifest.offline if e.asset_class not in user_classes]

    lines: list[str] = []
    lines.append(f"# Offline Assets — {stem}\n")
    lines.append(
        "Generated by `cutsmith collect`. These assets could not be copied "
        "because their source files were not found on this machine.\n"
    )

    if user_offline:
        lines.append("\n## User media — locate manually\n")
        lines.append(
            "These are files from your own storage that could not be found. "
            "Locate them and use Premiere's **Link Media** to relink after XML import.\n"
        )
        for e in user_offline:
            tracks = ", ".join(e.used_in_tracks) or "unreferenced"
            action = _OFFLINE_ACTION.get(e.asset_class, "rebuild manually")
            lines.append(f"\n### {e.name}\n")
            lines.append(f"- Class: `{e.asset_class.value}`")
            lines.append(f"- Original path: `{e.original_path or 'unknown'}`")
            lines.append(f"- Used in: {tracks}")
            lines.append(f"- Action: {action}")

    if capcut_offline:
        lines.append("\n## CapCut assets — not portable\n")
        lines.append(
            "These assets live inside the CapCut application cache or bundle "
            "and cannot be transferred to other systems. Rebuild them using "
            "Premiere's native equivalents or third-party resources.\n"
        )
        for e in capcut_offline:
            tracks = ", ".join(e.used_in_tracks) or "unreferenced"
            action = _OFFLINE_ACTION.get(e.asset_class, "rebuild manually in Premiere")
            lines.append(f"\n### {e.name}\n")
            lines.append(f"- Class: `{e.asset_class.value}`")
            lines.append(f"- Used in: {tracks}")
            lines.append(f"- Action: {action}")

    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
