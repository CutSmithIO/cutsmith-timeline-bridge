"""Run the v0.1 pipeline against the mock draft and print where outputs went.

Usage:
    cd cutsmith
    python examples/demo.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# Make `cutsmith` importable when running this script directly.
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from cutsmith import bridge


def main() -> None:
    draft = ROOT / "tests" / "fixtures" / "mock_draft_content.json"
    out_dir = ROOT / "examples" / "out"

    result = bridge.run(
        draft=draft,
        out_dir=out_dir,
        # The mock draft references paths under /Users/demo/Footage that
        # don't exist here, so everything will land in OFFLINE. Pass a real
        # directory here when you have actual footage to relink to.
        search_roots=[],
        name="demo_sequence",
    )

    print("Pipeline complete.")
    print(f"  XML:    {result.xml_path}")
    print(f"  Report: {result.report_path}")
    print()
    print(f"  Assets: {result.resolution.total}, "
          f"offline: {result.resolution.unresolved}")
    print(f"  Tracks: V={len(result.timeline.video_tracks)} "
          f"A={len(result.timeline.audio_tracks)}")
    print(f"  Unsupported items flagged: {len(result.timeline.unsupported)}")


if __name__ == "__main__":
    main()
