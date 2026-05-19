"""CutSmith CLI.

Subcommands:

  detect       — classify a draft (project dir or single file).
  inspect      — analyze a draft's schema; write summary JSONs.
  convert      — full pipeline: draft → FCP7 XML + compatibility report.
  export-srt   — extract subtitles/captions to SRT / TXT / JSON.
  scan-assets  — enumerate and classify all referenced materials.
  collect      — copy + relink: scan → copy media → rewrite XML paths.

Backwards compat: if the first positional looks like a `.json` path and no
subcommand keyword is given, we route to `convert` automatically so the
older `python -m cutsmith path/to/draft.json -o out` invocation still works.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from cutsmith import bridge
from cutsmith.collector import collect as _collect
from cutsmith.detect import detect_project
from cutsmith.inspect import inspect_draft
from cutsmith.subtitle import export_subtitles
from cutsmith.scanner import scan_assets
from cutsmith.scanner.manifest import AssetManifest


def main(argv: list[str] | None = None) -> int:
    argv = list(argv) if argv is not None else sys.argv[1:]
    argv = _shim_legacy_invocation(argv)

    parser = argparse.ArgumentParser(
        prog="cutsmith",
        description="CapCut/JianyingPro draft → Premiere Pro FCP7 XML.",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    # ── detect ──────────────────────────────────────────────────────────── #
    p_detect = sub.add_parser(
        "detect",
        help="Classify a draft (project dir or single file).",
        description=(
            "Triage tool: report app / version / encryption / "
            "supported_status without parsing the timeline. Run this on any "
            "unfamiliar sample to decide whether inspect/convert applies."
        ),
    )
    p_detect.add_argument("path", help="Project directory or single draft file")
    p_detect.add_argument(
        "--json", action="store_true",
        help="Emit machine-readable JSON (suitable for pasting into "
             "tests/fixtures/real_world/sample_manifest.json).",
    )
    p_detect.set_defaults(func=_cmd_detect)

    # ── inspect ─────────────────────────────────────────────────────────── #
    p_inspect = sub.add_parser(
        "inspect",
        help="Analyze a draft's schema; write summary JSONs.",
        description=(
            "Inspect a draft_content.json and emit structural summaries "
            "(no XML produced). Run this on any unfamiliar draft before "
            "convert, especially after a CapCut version upgrade."
        ),
    )
    p_inspect.add_argument("draft", help="Path to draft_content.json")
    p_inspect.add_argument("-o", "--out-dir", required=True,
                           help="Directory to write *_summary.json files")
    p_inspect.add_argument(
        "--raw-paths", action="store_true",
        help="Keep full file paths in output (default: basenames only, "
             "for safer sharing in bug reports).",
    )
    p_inspect.set_defaults(func=_cmd_inspect)

    # ── convert ─────────────────────────────────────────────────────────── #
    p_conv = sub.add_parser(
        "convert",
        help="Convert a draft to FCP7 XML + report.",
        description="Full pipeline: read draft → resolve media → write XML "
                    "→ write compatibility report.",
    )
    p_conv.add_argument("draft", help="Path to draft_content.json")
    p_conv.add_argument("-o", "--out-dir", required=True,
                        help="Output directory for .xml and .report.md")
    p_conv.add_argument("-s", "--search-root", action="append", default=[],
                        help="Directory to scan for missing media (repeatable)")
    p_conv.add_argument("-n", "--name", default=None,
                        help="Override sequence name (default: draft stem)")
    p_conv.set_defaults(func=_cmd_convert)

    # ── export-srt ──────────────────────────────────────────────────────────── #
    p_srt = sub.add_parser(
        "export-srt",
        help="Extract subtitles/captions to SRT, TXT, or JSON.",
        description=(
            "Extract all text/caption tracks from a draft and write them as "
            "SRT (default), plain TXT, or structured JSON. Handles both "
            "plain-text segments (Pattern A) and animated subtitle templates "
            "(Pattern B / CapCut AI Captions)."
        ),
    )
    p_srt.add_argument("draft", help="Path to draft_info.json or project directory")
    p_srt.add_argument("-o", "--out-dir", required=True,
                       help="Output directory")
    p_srt.add_argument(
        "--format", dest="formats", action="append",
        choices=["srt", "txt", "json"], default=None,
        help="Output format (repeatable; default: srt)",
    )
    p_srt.add_argument("-n", "--name", default=None,
                       help="Override output file stem")
    p_srt.set_defaults(func=_cmd_export_srt)

    # ── scan-assets ─────────────────────────────────────────────────────────── #
    p_scan = sub.add_parser(
        "scan-assets",
        help="Enumerate and classify all referenced materials.",
        description=(
            "Scan a draft and produce a manifest of every material: user media, "
            "CapCut music/SFX, stickers, effects, filters, and transitions. "
            "Reports online/offline status and file sizes. Does not copy files."
        ),
    )
    p_scan.add_argument("draft", help="Path to draft_info.json or project directory")
    p_scan.add_argument("-o", "--out-dir", default=None,
                        help="Output directory for manifest JSON + scan report "
                             "(if omitted, prints summary to stdout)")
    p_scan.add_argument("-s", "--search-root", action="append", default=[],
                        help="Directory to scan for missing user media (repeatable)")
    p_scan.add_argument("--json", action="store_true",
                        help="Print full manifest JSON to stdout (implies no -o output)")
    p_scan.set_defaults(func=_cmd_scan_assets)

    # ── collect ─────────────────────────────────────────────────────────────── #
    p_collect = sub.add_parser(
        "collect",
        help="Copy + relink: scan → copy media → rewrite XML paths.",
        description=(
            "Full v0.3 collect pipeline: scan all materials, copy online user "
            "assets to media/<class>/, rewrite XML <pathurl> to point at the "
            "copied files, and write a manifest + offline report. The output "
            "directory is a self-contained package ready to open in Premiere."
        ),
    )
    p_collect.add_argument("project",
                           help="Project directory or path to draft_info.json")
    p_collect.add_argument("-o", "--out-dir", required=True,
                           help="Output directory for the collected package")
    p_collect.add_argument("-s", "--search-root", action="append", default=[],
                           help="Extra directory to scan for missing user media (repeatable)")
    p_collect.add_argument("-n", "--name", default=None,
                           help="Override sequence / project name")
    p_collect.set_defaults(func=_cmd_collect)

    args = parser.parse_args(argv)
    return args.func(args, parser)


def _shim_legacy_invocation(argv: list[str]) -> list[str]:
    """Allow `python -m cutsmith draft.json -o out` (the pre-subcommand form)
    to keep working by injecting 'convert' as the first argument."""
    if not argv:
        return argv
    first = argv[0]
    if first in ("detect", "inspect", "convert", "export-srt", "scan-assets",
                 "collect", "-h", "--help"):
        return argv
    # If the first arg looks like a path (no leading -) treat as legacy convert.
    if not first.startswith("-"):
        return ["convert", *argv]
    return argv


# --------------------------------------------------------------------------- #
# subcommand impls                                                            #
# --------------------------------------------------------------------------- #

def _cmd_detect(args: argparse.Namespace,
                parser: argparse.ArgumentParser) -> int:
    path = Path(args.path).expanduser()
    if not path.exists():
        parser.error(f"path not found: {path}")

    result = detect_project(path)

    if args.json:
        print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))
        return 0 if result.supported_status != "error" else 1

    print(f"[detect] {result.input_path}")
    print(f"  app_type:            {result.app_type}")
    print(f"  app_version:         {result.app_version or '(unknown)'}")
    print(f"  schema_version:      {result.schema_version if result.schema_version is not None else '(unknown)'}")
    print(f"  schema_type:         {result.schema_type}")
    print(f"  encryption:          {result.encryption}")
    print(f"  timeline_entry:      {result.timeline_entry_path or '(none)'}")
    print(f"  supported_status:    {result.supported_status}")
    if result.notes:
        print("  notes:")
        for n in result.notes:
            print(f"    - {n}")
    return 0 if result.supported_status != "error" else 1


def _resolve_draft_entry(path: Path, parser: argparse.ArgumentParser) -> Path:
    """Resolve a project root, Timelines dir, or direct JSON path to draft_info.json."""
    if path.is_file():
        return path
    if path.is_dir():
        result = detect_project(path)
        if not result.timeline_entry_path:
            parser.error(f"no supported draft found in {path}")
        if result.encryption != "plaintext":
            parser.error(f"draft is encrypted — only plaintext drafts are supported")
        return Path(result.timeline_entry_path)
    parser.error(f"path not found: {path}")


def _cmd_inspect(args: argparse.Namespace,
                 parser: argparse.ArgumentParser) -> int:
    draft = _resolve_draft_entry(Path(args.draft), parser)
    result = inspect_draft(draft, args.out_dir, raw_paths=args.raw_paths)

    print(f"[inspect] read {draft}")
    print(f"[inspect] wrote {len(result.written_files)} file(s) to {args.out_dir}/")
    for p in result.written_files:
        print(f"          - {p.name}")

    schema = result.schema_summary
    print()
    print(f"  draft: {schema['draft_size_bytes'] / 1024:.1f} KiB, "
          f"version={schema['version_fields']['version'] or schema['version_fields']['new_version']}")
    dur_s = schema['top_level']['duration_seconds']
    fps = schema['top_level']['fps']
    print(f"  fps={fps}, duration={f'{dur_s:.2f}s' if dur_s is not None else '?'}")
    counts = schema["counts"]
    mats_nonempty = ", ".join(f"{k}={v}" for k, v in counts["material_categories"].items() if v)
    print(f"  materials: {mats_nonempty or '(none)'}")
    tracks_str = ", ".join(f"{k}={v}" for k, v in counts["tracks_by_type"].items())
    print(f"  tracks: {tracks_str or '(none)'}")

    unknown = result.unknown_fields
    flat_unknown_count = (
        len(unknown["top_level"]) + len(unknown["canvas_config"])
        + len(unknown["video_materials"]) + len(unknown["audio_materials"])
        + len(unknown["tracks"])
        + sum(len(v) for v in unknown["segments_by_track_type"].values())
    )
    if flat_unknown_count:
        print(f"  ⚠  {flat_unknown_count} field(s) present in draft but "
              f"unread by reader — see unknown_fields.json")
    else:
        print(f"  ✓  no schema drift vs. reader's known fields")

    return 0


def _cmd_convert(args: argparse.Namespace,
                 parser: argparse.ArgumentParser) -> int:
    draft = _resolve_draft_entry(Path(args.draft), parser)

    result = bridge.run(
        draft=draft,
        out_dir=args.out_dir,
        search_roots=args.search_root,
        name=args.name,
    )

    res = result.resolution
    print(f"[ok] wrote {result.xml_path}")
    print(f"[ok] wrote {result.report_path}")
    print(f"     assets: {res.total} total, "
          f"{res.resolved_as_is + res.resolved_via_search} linked, "
          f"{res.unresolved} offline")
    if result.timeline.unsupported:
        print(f"     unsupported items: {len(result.timeline.unsupported)} "
              f"(see report)")
    return 0


_SUBTITLE_EXTENSIONS = frozenset({".srt", ".txt", ".json"})


def _cmd_export_srt(args: argparse.Namespace,
                    parser: argparse.ArgumentParser) -> int:
    draft = _resolve_draft_entry(Path(args.draft), parser)

    # -o may be a directory (default) or a direct file path ending in a subtitle
    # extension (e.g. -o captions.srt). In the latter case, derive out_dir and
    # name from the file path so the output lands exactly where requested.
    out_path = Path(args.out_dir)
    if out_path.suffix in _SUBTITLE_EXTENSIONS and not out_path.is_dir():
        out_dir = out_path.parent
        name = args.name or out_path.stem
    else:
        out_dir = out_path
        name = args.name

    formats = args.formats or ["srt"]
    written = export_subtitles(
        draft_path=draft,
        out_dir=out_dir,
        formats=formats,
        name=name,
    )
    if not written:
        print("[export-srt] no subtitle tracks found — nothing written")
        return 0
    for p in written:
        print(f"[ok] wrote {p}")
    return 0


def _cmd_scan_assets(args: argparse.Namespace,
                     parser: argparse.ArgumentParser) -> int:
    draft = Path(args.draft)
    if not draft.exists():
        parser.error(f"path not found: {draft}")

    manifest = scan_assets(draft, search_roots=args.search_root)

    if args.json:
        print(manifest.to_json())
        return 0

    if args.out_dir:
        out_dir = Path(args.out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        stem = manifest.project_name or "project"
        json_path = out_dir / f"{stem}.manifest.json"
        report_path = out_dir / f"{stem}.scan.md"
        json_path.write_text(manifest.to_json(), encoding="utf-8")
        report_path.write_text(_render_scan_report(manifest), encoding="utf-8")
        print(f"[ok] wrote {json_path}")
        print(f"[ok] wrote {report_path}")

    # Always print summary
    _print_scan_summary(manifest)
    return 0


def _print_scan_summary(m: AssetManifest) -> None:
    print()
    print(f"  project:    {m.project_name}")
    print(f"  duration:   {m.duration_us / 1_000_000:.2f}s")
    print(f"  assets:     {m.total_assets} total, "
          f"{m.online_count} online, {m.offline_count} offline, "
          f"{m.cached_count} cached")
    total_mb = m.total_online_size_bytes / (1024 * 1024)
    print(f"  online size:{total_mb:8.1f} MB")
    if m.videos:
        print(f"  videos:     {len(m.videos)}")
    if m.audios:
        print(f"  user audio: {len(m.audios)}")
    if m.music:
        print(f"  music:      {len(m.music)}")
    if m.sfx:
        print(f"  sfx:        {len(m.sfx)}")
    if m.images:
        print(f"  images:     {len(m.images)}")
    if m.stickers:
        print(f"  stickers:   {len(m.stickers)} (not exported — CapCut proprietary)")
    if m.effects:
        print(f"  effects:    {len(m.effects)} (not exported)")
    if m.filters:
        print(f"  filters:    {len(m.filters)} (not exported)")
    if m.transitions:
        print(f"  transitions:{len(m.transitions)} (not exported)")
    if m.offline:
        print(f"  ⚠ offline:  {len(m.offline)} asset(s) unresolved")
        for e in m.offline[:5]:
            print(f"      {e.name}  ({e.asset_class.value})")
        if len(m.offline) > 5:
            print(f"      … and {len(m.offline) - 5} more — see manifest JSON")


def _render_scan_report(m: AssetManifest) -> str:
    lines: list[str] = []
    lines.append(f"# Asset Scan Report — {m.project_name}\n")
    lines.append(f"Source: `{m.source_draft}`\n")
    lines.append(f"## Summary\n")
    lines.append(f"| | Count | Notes |")
    lines.append(f"|---|---|---|")
    lines.append(f"| Total assets | {m.total_assets} | |")
    lines.append(f"| Online | {m.online_count} | |")
    lines.append(f"| Offline | {m.offline_count} | |")
    lines.append(f"| Cached (CapCut library) | {m.cached_count} | |")
    mb = m.total_online_size_bytes / (1024 * 1024)
    lines.append(f"| Total online size | {mb:.1f} MB | |")
    lines.append("")

    def _table(title: str, entries: list, note: str = "") -> None:
        if not entries:
            return
        lines.append(f"## {title}\n")
        if note:
            lines.append(f"_{note}_\n")
        lines.append("| Name | Online | Size | Cached | Path |")
        lines.append("|---|---|---|---|---|")
        for e in entries:
            size_str = f"{e.file_size_bytes / (1024*1024):.1f} MB" if e.file_size_bytes else "—"
            online_str = "✓" if e.is_online else "✗"
            cached_str = "✓" if e.is_cached else ""
            path = e.original_path or ""
            lines.append(f"| {e.name} | {online_str} | {size_str} | {cached_str} | `{path}` |")
        lines.append("")

    _table("User Video", m.videos)
    _table("User Audio", m.audios)
    _table("CapCut Music", m.music,
           "Cached music library tracks. Licensing may be restricted to CapCut/TikTok platforms.")
    _table("CapCut SFX", m.sfx)
    _table("Images", m.images)
    _table("Stickers", m.stickers, "Not exported — CapCut proprietary format.")
    _table("Effects", m.effects, "Not exported.")
    _table("Filters", m.filters, "Not exported.")
    _table("Transitions", m.transitions, "Not exported.")

    if m.offline:
        lines.append("## ⚠ Offline Assets\n")
        lines.append("| Name | Class | Last known path |")
        lines.append("|---|---|---|")
        for e in m.offline:
            lines.append(f"| {e.name} | {e.asset_class.value} | `{e.original_path or ''}` |")
        lines.append("")
        lines.append("**Suggested actions**:\n")
        lines.append("- User media: use Premiere's \"Link Media\" after XML import.")
        lines.append("- CapCut cache: re-download the asset in CapCut, then re-run scan.")
        lines.append("")

    return "\n".join(lines)


def _cmd_collect(args: argparse.Namespace,
                 parser: argparse.ArgumentParser) -> int:
    project = Path(args.project)
    if not project.exists():
        parser.error(f"path not found: {project}")

    try:
        result = _collect(
            project_path=project,
            out_dir=args.out_dir,
            search_roots=args.search_root or [],
            name=args.name,
        )
    except ValueError as e:
        parser.error(str(e))

    s = result.stats
    print(f"[ok] wrote {result.xml_path}")
    print(f"[ok] wrote {result.report_path}")
    print(f"[ok] wrote {result.manifest_path}")
    if result.offline_report_path:
        print(f"[ok] wrote {result.offline_report_path}")
    print()
    print(f"  project:    {result.project_name}")
    print(f"  copied:     {s.copied_count} asset(s)")
    sz_mb = s.total_copied_size_bytes / 1_048_576
    print(f"  size:       {sz_mb:.1f} MB")
    print(f"  offline:    {s.offline_count} asset(s) not found")
    print(f"  report-only:{s.skipped_report_only_count} (effects/transitions/filters)")
    if result.offline_report_path:
        print(f"  ⚠ see {result.offline_report_path.name} for unresolved assets")
    return 0


if __name__ == "__main__":
    sys.exit(main())
