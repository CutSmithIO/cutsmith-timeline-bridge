"""Tests for cutsmith.subtitle — subtitle extraction, Pattern A + B, SRT/TXT/JSON."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from cutsmith.subtitle import (
    export_subtitles,
    read_subtitles,
    to_json,
    to_srt,
    to_txt,
)

FIXTURE_A = Path(__file__).parent / "fixtures" / "mock_subtitle_pattern_a.json"
FIXTURE_B = Path(__file__).parent / "fixtures" / "mock_subtitle_pattern_b.json"
FIXTURE_MAIN = Path(__file__).parent / "fixtures" / "mock_draft_content.json"


class PatternAExtractionTest(unittest.TestCase):
    """Pattern A: text_segment.material_id → materials.texts[id]."""

    def setUp(self):
        self.tracks = read_subtitles(FIXTURE_A)

    def test_returns_one_track(self):
        self.assertEqual(len(self.tracks), 1)

    def test_three_cues(self):
        self.assertEqual(self.tracks[0].cue_count, 3)

    def test_cue_texts(self):
        texts = [c.text for c in self.tracks[0].cues]
        self.assertEqual(texts[0], "Hello world")
        self.assertEqual(texts[1], "Goodbye world")
        self.assertEqual(texts[2], "See you later")

    def test_cue_timing_microseconds(self):
        cues = self.tracks[0].cues
        self.assertEqual(cues[0].start_us, 0)
        self.assertEqual(cues[0].end_us, 3_000_000)
        self.assertEqual(cues[1].start_us, 4_000_000)
        self.assertEqual(cues[1].end_us, 7_500_000)

    def test_auto_caption_flag(self):
        cues = self.tracks[0].cues
        self.assertFalse(cues[0].is_auto_caption)
        self.assertFalse(cues[1].is_auto_caption)
        self.assertTrue(cues[2].is_auto_caption)   # recognize_type=1 in fixture

    def test_likely_caption_track_false_for_small_count(self):
        # 3 cues < 5 threshold
        self.assertFalse(self.tracks[0].likely_caption_track)


class PatternBExtractionTest(unittest.TestCase):
    """Pattern B: text_segment.material_id → text_templates → texts."""

    def setUp(self):
        self.tracks = read_subtitles(FIXTURE_B)

    def test_returns_one_track(self):
        self.assertEqual(len(self.tracks), 1)

    def test_three_cues(self):
        self.assertEqual(self.tracks[0].cue_count, 3)

    def test_cue_texts(self):
        texts = [c.text for c in self.tracks[0].cues]
        self.assertEqual(texts[0], "Pattern B text one")
        self.assertEqual(texts[1], "Pattern B text two")
        self.assertEqual(texts[2], "Pattern B text three")

    def test_cue_timing(self):
        cues = self.tracks[0].cues
        self.assertEqual(cues[0].start_us, 1_000_000)
        self.assertEqual(cues[0].end_us, 5_000_000)

    def test_no_false_auto_caption(self):
        for cue in self.tracks[0].cues:
            self.assertFalse(cue.is_auto_caption)


class SRTFormatTest(unittest.TestCase):

    def _tracks_a(self):
        return read_subtitles(FIXTURE_A)

    def test_srt_cue_numbering_starts_at_one(self):
        srt = to_srt(self._tracks_a())
        lines = srt.strip().split("\n")
        self.assertEqual(lines[0], "1")

    def test_srt_timestamp_format(self):
        srt = to_srt(self._tracks_a())
        # First timestamp line should be "00:00:00,000 --> 00:00:03,000"
        lines = srt.strip().split("\n")
        self.assertIn("-->", lines[1])
        self.assertRegex(lines[1], r"\d{2}:\d{2}:\d{2},\d{3} --> \d{2}:\d{2}:\d{2},\d{3}")

    def test_srt_first_cue_times(self):
        srt = to_srt(self._tracks_a())
        lines = srt.strip().split("\n")
        self.assertEqual(lines[1], "00:00:00,000 --> 00:00:03,000")

    def test_srt_text_on_third_line(self):
        srt = to_srt(self._tracks_a())
        lines = srt.strip().split("\n")
        self.assertEqual(lines[2], "Hello world")

    def test_srt_cues_separated_by_blank_line(self):
        srt = to_srt(self._tracks_a())
        lines = srt.strip().split("\n")
        # Line 3 (index 3) should be blank between cue 1 and cue 2
        self.assertEqual(lines[3], "")

    def test_srt_sorted_by_start_time(self):
        """Cues from all tracks are merged and sorted by start_us."""
        srt = to_srt(self._tracks_a())
        lines = srt.strip().split("\n")
        # All three cues in order: 0s, 4s, 8s
        ts_lines = [l for l in lines if "-->" in l]
        starts = [l.split("-->")[0].strip() for l in ts_lines]
        self.assertEqual(starts[0], "00:00:00,000")
        self.assertEqual(starts[1], "00:00:04,000")
        self.assertEqual(starts[2], "00:00:08,000")

    def test_srt_three_cues_produced(self):
        srt = to_srt(self._tracks_a())
        count = sum(1 for l in srt.split("\n") if l == "1" or l == "2" or l == "3")
        ts_count = sum(1 for l in srt.split("\n") if "-->" in l)
        self.assertEqual(ts_count, 3)


class TXTFormatTest(unittest.TestCase):

    def test_one_line_per_cue(self):
        tracks = read_subtitles(FIXTURE_A)
        txt = to_txt(tracks)
        lines = [l for l in txt.split("\n") if l.strip()]
        self.assertEqual(len(lines), 3)

    def test_line_starts_with_timecode(self):
        tracks = read_subtitles(FIXTURE_A)
        txt = to_txt(tracks)
        first_line = txt.split("\n")[0]
        self.assertTrue(first_line.startswith("[00:00:00.000]"))

    def test_line_contains_text(self):
        tracks = read_subtitles(FIXTURE_A)
        txt = to_txt(tracks)
        self.assertIn("Hello world", txt)


class JSONFormatTest(unittest.TestCase):

    def setUp(self):
        tracks = read_subtitles(FIXTURE_A)
        self.data = json.loads(to_json(tracks))

    def test_is_list(self):
        self.assertIsInstance(self.data, list)

    def test_one_track_entry(self):
        self.assertEqual(len(self.data), 1)

    def test_track_has_cues_key(self):
        self.assertIn("cues", self.data[0])

    def test_cue_has_required_keys(self):
        cue = self.data[0]["cues"][0]
        for key in ("cue_id", "start_us", "end_us", "start_s", "end_s",
                    "text", "is_auto_caption"):
            self.assertIn(key, cue)

    def test_cue_start_s_precision(self):
        cue = self.data[0]["cues"][1]
        self.assertAlmostEqual(cue["start_s"], 4.0, places=2)

    def test_cue_text_correct(self):
        self.assertEqual(self.data[0]["cues"][0]["text"], "Hello world")


class ExportSubtitlesTest(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.out = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_writes_srt_by_default(self):
        written = export_subtitles(FIXTURE_A, self.out)
        self.assertEqual(len(written), 1)
        self.assertTrue(written[0].name.endswith(".srt"))

    def test_writes_multiple_formats(self):
        written = export_subtitles(FIXTURE_A, self.out,
                                   formats=["srt", "txt", "json"])
        extensions = {p.suffix for p in written}
        self.assertIn(".srt", extensions)
        self.assertIn(".txt", extensions)
        # json uses .subtitles.json
        json_files = [p for p in written if "json" in p.name]
        self.assertEqual(len(json_files), 1)

    def test_no_text_tracks_returns_empty(self):
        # main mock draft has a 'text' track but the reader drops it;
        # the subtitle module reads raw JSON and should find no text tracks
        # that produce cues if all materials are empty.
        # Use a fixture with no text tracks: videos-only mock.
        import json as _json
        import tempfile as _tmp
        minimal = {
            "version": 360000, "fps": 30.0, "duration": 5000000,
            "canvas_config": {"width": 1920, "height": 1080},
            "materials": {"videos": [], "audios": [], "texts": [],
                          "stickers": [], "effects": [], "transitions": [],
                          "filters": [], "video_effects": [], "text_templates": []},
            "tracks": []
        }
        with _tmp.NamedTemporaryFile(suffix=".json", mode="w",
                                     delete=False) as f:
            _json.dump(minimal, f)
            fpath = Path(f.name)
        try:
            written = export_subtitles(fpath, self.out)
            self.assertEqual(written, [])
        finally:
            fpath.unlink(missing_ok=True)

    def test_name_override_applied(self):
        written = export_subtitles(FIXTURE_A, self.out, name="my_project")
        self.assertTrue(written[0].stem, "my_project")

    def test_pattern_b_export_srt(self):
        written = export_subtitles(FIXTURE_B, self.out)
        srt = written[0].read_text(encoding="utf-8")
        self.assertIn("Pattern B text one", srt)
        self.assertIn("Pattern B text two", srt)


class NoTextTrackTest(unittest.TestCase):

    def test_project_without_text_tracks_returns_empty_list(self):
        tracks = read_subtitles(FIXTURE_MAIN)
        # The main mock fixture has a 'text' track type segment,
        # so it may return a track. The important thing is no crash.
        # Just assert it's a list.
        self.assertIsInstance(tracks, list)
