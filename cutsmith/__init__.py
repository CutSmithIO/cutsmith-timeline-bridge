"""CutSmith Timeline Bridge — CapCut/JianyingPro → Premiere Pro (FCP7 XML).

v0.1 scope:
  - video clip cuts
  - explicit audio tracks from the draft (BGM, voiceover, and CapCut's
    auto-split video audio when it exists as its own audio track) — the
    writer does NOT synthesize tracks from video assets' embedded audio,
    since CapCut already exposes that audio on a dedicated track
  - multi-track order and overlay (V1/V2/A1/A2…)
  - media path resolution with relink-friendly offline placeholders
  - compatibility_report.md

Public API:
    from cutsmith import bridge
    bridge.run(draft="path/to/draft_content.json",
               out_dir="path/to/out",
               search_roots=["/Volumes/Footage"])
"""

from cutsmith import bridge

__version__ = "0.1.0"
__all__ = ["bridge", "__version__"]
