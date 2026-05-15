"""Tests for the inspect subcommand.

Two fixtures:
  - mock_draft_content.json     — clean, reader's "known good" shape.
                                  Should produce zero unknown_fields.
  - pathological_draft_content.json
                                — intentionally weird: null paths, missing
                                  source_timerange, bitmask attribute,
                                  unknown track types, etc. Must NOT crash
                                  inspect, and SHOULD light up unknown_fields.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from cutsmith.inspect import inspect_draft

FIXTURES = Path(__file__).parent / "fixtures"
MOCK = FIXTURES / "mock_draft_content.json"
PATHO = FIXTURES / "pathological_draft_content.json"

EXPECTED_FILES = {
    "schema_summary.json",
    "media_summary.json",
    "track_summary.json",
    "unsupported_summary.json",
    "unknown_fields.json",
    "debug_inspect.json",
}


class InspectMockDraftTest(unittest.TestCase):
    """The mock fixture matches the reader's known schema. Inspect should
    produce all six files and zero unknown fields."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.out = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_writes_all_expected_files(self):
        result = inspect_draft(MOCK, self.out)
        written = {p.name for p in result.written_files}
        self.assertEqual(written, EXPECTED_FILES)

    def test_schema_summary_has_fps_and_duration(self):
        inspect_draft(MOCK, self.out)
        data = json.loads((self.out / "schema_summary.json").read_text())
        self.assertEqual(data["top_level"]["fps"], 30.0)
        self.assertAlmostEqual(data["top_level"]["duration_seconds"], 15.0)
        self.assertIn("canvas_config", data)
        self.assertEqual(data["canvas_config"]["values"]["width"], 1920)

    def test_media_summary_counts_assets(self):
        inspect_draft(MOCK, self.out)
        data = json.loads((self.out / "media_summary.json").read_text())
        self.assertEqual(data["videos"]["summary"]["count"], 3)  # 2 video + 1 photo
        self.assertEqual(data["audios"]["summary"]["count"], 1)

    def test_media_summary_redacts_paths_by_default(self):
        """Paths should be basename-only unless --raw-paths is passed."""
        inspect_draft(MOCK, self.out, raw_paths=False)
        data = json.loads((self.out / "media_summary.json").read_text())
        for v in data["videos"]["preview"]:
            # Mock paths look like /Users/demo/Footage/foo.mp4.
            self.assertNotIn("/", v["path"] or "",
                             f"path leaked through redaction: {v['path']}")

    def test_media_summary_keeps_paths_when_requested(self):
        inspect_draft(MOCK, self.out, raw_paths=True)
        data = json.loads((self.out / "media_summary.json").read_text())
        # At least one preview should retain a slash.
        paths = [v["path"] for v in data["videos"]["preview"] if v["path"]]
        self.assertTrue(any("/" in p for p in paths),
                        "raw_paths=True did not preserve any path")

    def test_track_summary_groups_by_type(self):
        inspect_draft(MOCK, self.out)
        data = json.loads((self.out / "track_summary.json").read_text())
        self.assertIn("video", data["by_track_type"])
        self.assertIn("audio", data["by_track_type"])
        # Mock has text + effect tracks too.
        self.assertIn("text", data["by_track_type"])
        self.assertIn("effect", data["by_track_type"])

    def test_unsupported_summary_flags_dropped_categories(self):
        inspect_draft(MOCK, self.out)
        data = json.loads((self.out / "unsupported_summary.json").read_text())
        # Mock has 1 text material + 1 transition + 1 effect.
        self.assertEqual(data["material_categories_dropped"].get("texts"), 1)
        self.assertEqual(data["material_categories_dropped"].get("transitions"), 1)
        self.assertEqual(data["material_categories_dropped"].get("effects"), 1)
        # 1 segment has keyframe_refs in the mock.
        self.assertEqual(data["av_segments_with_keyframes"], 1)

    def test_mock_has_no_schema_drift(self):
        """Whole point of the mock fixture: it shouldn't surprise the reader."""
        inspect_draft(MOCK, self.out)
        data = json.loads((self.out / "unknown_fields.json").read_text())
        self.assertEqual(data["top_level"], [])
        self.assertEqual(data["canvas_config"], [])
        self.assertEqual(data["video_materials"], [])
        self.assertEqual(data["audio_materials"], [])

    def test_debug_inspect_merges_everything(self):
        inspect_draft(MOCK, self.out)
        merged = json.loads((self.out / "debug_inspect.json").read_text())
        for key in ("schema_summary", "media_summary", "track_summary",
                    "unsupported_summary", "unknown_fields"):
            self.assertIn(key, merged)
        self.assertIn("_meta", merged)


class InspectPathologicalDraftTest(unittest.TestCase):
    """The pathological fixture exists to break things on purpose. Inspect
    must survive every weirdness and report it accurately."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.out = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_does_not_crash_on_pathological_draft(self):
        # The point: this call alone proves inspect handles null paths,
        # missing source_timerange, unknown track types, bitmask attributes.
        inspect_draft(PATHO, self.out)

    def test_uses_new_version_field_when_version_missing(self):
        inspect_draft(PATHO, self.out)
        data = json.loads((self.out / "schema_summary.json").read_text())
        self.assertEqual(data["version_fields"]["version"], None)
        self.assertEqual(data["version_fields"]["new_version"], "6.2.0")

    def test_detects_unknown_top_level_fields(self):
        """The pathological fixture has free_render_index_mode_on, color_space,
        and lyrics_taskinfo at the top level — reader doesn't know any of
        these. They should all show up in unknown_fields."""
        inspect_draft(PATHO, self.out)
        data = json.loads((self.out / "unknown_fields.json").read_text())
        self.assertIn("free_render_index_mode_on", data["top_level"])
        self.assertIn("color_space", data["top_level"])
        self.assertIn("lyrics_taskinfo", data["top_level"])

    def test_detects_unknown_canvas_field(self):
        inspect_draft(PATHO, self.out)
        data = json.loads((self.out / "unknown_fields.json").read_text())
        self.assertIn("background_color", data["canvas_config"])
        self.assertIn("background_blur", data["canvas_config"])

    def test_detects_unknown_video_material_fields(self):
        """`remote_url`, `category_name`, `stable`, `extra_info` are all
        cloud-asset / new-version fields the reader doesn't read."""
        inspect_draft(PATHO, self.out)
        data = json.loads((self.out / "unknown_fields.json").read_text())
        self.assertIn("remote_url", data["video_materials"])
        self.assertIn("category_name", data["video_materials"])

    def test_detects_unknown_audio_material_fields(self):
        inspect_draft(PATHO, self.out)
        data = json.loads((self.out / "unknown_fields.json").read_text())
        self.assertIn("wave_points", data["audio_materials"])

    def test_detects_unknown_segment_fields_per_track_type(self):
        """fade_in_duration / fade_out_duration are audio-only — they
        should appear under 'audio', not 'video'."""
        inspect_draft(PATHO, self.out)
        data = json.loads((self.out / "unknown_fields.json").read_text())
        audio_unknown = data["segments_by_track_type"].get("audio", [])
        self.assertIn("fade_in_duration", audio_unknown)
        self.assertIn("fade_out_duration", audio_unknown)

    def test_detects_unknown_track_type(self):
        """Track type 'caption' is not in the reader's vocabulary. Shouldn't
        crash; should appear in the by_track_type breakdown."""
        inspect_draft(PATHO, self.out)
        data = json.loads((self.out / "track_summary.json").read_text())
        self.assertIn("caption", data["by_track_type"])

    def test_media_preview_handles_null_path(self):
        """Asset with path=null shouldn't blow up the preview generator."""
        inspect_draft(PATHO, self.out)
        data = json.loads((self.out / "media_summary.json").read_text())
        previews = data["videos"]["preview"]
        null_path_assets = [p for p in previews if p["path"] is None]
        self.assertEqual(len(null_path_assets), 1)
        self.assertEqual(null_path_assets[0]["id"], "vid_with_null_path")

    def test_unsupported_summary_counts_speed_change(self):
        """seg_speed_2x has speed=2.0 — that should be counted."""
        inspect_draft(PATHO, self.out)
        data = json.loads((self.out / "unsupported_summary.json").read_text())
        self.assertGreaterEqual(data["av_segments_with_speed_change"], 1)


if __name__ == "__main__":
    unittest.main()
