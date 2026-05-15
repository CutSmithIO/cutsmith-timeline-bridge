"""High-level pipeline: draft → IR → resolve → write XML → write report.

Single function `run()` is the entry point both the CLI and direct Python
callers use. Keeping the orchestration in one place makes it easy to add
alternate output formats (FCPXML, Resolve) in v0.2 without each writer
re-implementing the resolve+report flow.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from cutsmith.reader import read_draft
from cutsmith.report import write_report
from cutsmith.resolver import resolve_media_paths, ResolutionStats
from cutsmith.writer import write_fcp7_xml
from cutsmith.ir import Timeline


@dataclass
class BridgeResult:
    timeline: Timeline
    resolution: ResolutionStats
    xml_path: Path
    report_path: Path


def run(
    draft: str | Path,
    out_dir: str | Path,
    search_roots: list[str | Path] | None = None,
    name: str | None = None,
) -> BridgeResult:
    """Run the full pipeline. Writes `<name>.xml` and `<name>.report.md` into
    `out_dir`. Defaults `name` to the draft file's stem.
    """
    draft_path = Path(draft)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    timeline = read_draft(draft_path)
    if name:
        timeline.name = name

    resolution = resolve_media_paths(timeline, search_roots=search_roots)

    xml_path = out_dir / f"{timeline.name}.xml"
    report_path = out_dir / f"{timeline.name}.report.md"

    write_fcp7_xml(timeline, xml_path)
    write_report(timeline, resolution, report_path, xml_output_path=xml_path)

    return BridgeResult(
        timeline=timeline,
        resolution=resolution,
        xml_path=xml_path,
        report_path=report_path,
    )
