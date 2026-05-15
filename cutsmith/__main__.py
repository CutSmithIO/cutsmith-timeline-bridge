"""CutSmith CLI.

Three subcommands:

  detect   — classify a draft (project dir or single file). Reports app,
             version, plaintext/encrypted, supported_status. Run this first
             on any new real-world sample to decide whether inspect/convert
             is even applicable.

  inspect  — analyze a draft, write summary JSONs. No XML/report produced.
             Use this on plaintext drafts to surface schema drift before
             converting.

  convert  — full pipeline: draft → FCP7 XML + compatibility report.

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
from cutsmith.detect import detect_project
from cutsmith.inspect import inspect_draft


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

    args = parser.parse_args(argv)
    return args.func(args, parser)


def _shim_legacy_invocation(argv: list[str]) -> list[str]:
    """Allow `python -m cutsmith draft.json -o out` (the pre-subcommand form)
    to keep working by injecting 'convert' as the first argument."""
    if not argv:
        return argv
    first = argv[0]
    if first in ("detect", "inspect", "convert", "-h", "--help"):
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


def _cmd_inspect(args: argparse.Namespace,
                 parser: argparse.ArgumentParser) -> int:
    draft = Path(args.draft)
    if not draft.is_file():
        parser.error(f"draft not found: {draft}")

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
    draft = Path(args.draft)
    if not draft.is_file():
        parser.error(f"draft not found: {draft}")

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


if __name__ == "__main__":
    sys.exit(main())
