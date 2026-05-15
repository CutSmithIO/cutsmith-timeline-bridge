"""Smoke test for the v0.1 pipeline.

Runs the bridge against the mock draft and asserts the things that, if they
broke, would mean Premiere can't open the output. Not exhaustive — just the
'did anything obviously catch fire' layer. Run with:

    cd cutsmith && python -m unittest tests.test_pipeline
"""

from __future__ import annotations

import json
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

from cutsmith import bridge
from cutsmith.reader import read_draft

FIXTURE = Path(__file__).parent / "fixtures" / "mock_draft_content.json"


class PipelineSmokeTest(unittest.TestCase):

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.out = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_pipeline_runs_end_to_end(self):
        result = bridge.run(draft=FIXTURE, out_dir=self.out, name="t")
        self.assertTrue(result.xml_path.exists())
        self.assertTrue(result.report_path.exists())

    def test_xml_is_wellformed_fcp7(self):
        result = bridge.run(draft=FIXTURE, out_dir=self.out, name="t")
        tree = ET.parse(result.xml_path)
        root = tree.getroot()
        self.assertEqual(root.tag, "xmeml")
        self.assertEqual(root.attrib.get("version"), "5")
        seq = root.find("sequence")
        self.assertIsNotNone(seq, "missing <sequence>")

    def test_video_and_audio_sections_present(self):
        result = bridge.run(draft=FIXTURE, out_dir=self.out, name="t")
        root = ET.parse(result.xml_path).getroot()
        media = root.find(".//sequence/media")
        self.assertIsNotNone(media.find("video"))
        self.assertIsNotNone(media.find("audio"))

    def test_clipitem_times_consistent(self):
        """end - start must equal out - in for every clipitem."""
        result = bridge.run(draft=FIXTURE, out_dir=self.out, name="t")
        root = ET.parse(result.xml_path).getroot()
        for ci in root.iter("clipitem"):
            start = int(ci.findtext("start"))
            end = int(ci.findtext("end"))
            in_ = int(ci.findtext("in"))
            out = int(ci.findtext("out"))
            self.assertEqual(end - start, out - in_,
                             f"clipitem {ci.attrib.get('id')} has "
                             f"mismatched timeline/source duration")

    def test_file_emitted_once_with_body(self):
        """Each <file id> should have its body declared exactly once;
        subsequent occurrences must be id-only stubs."""
        result = bridge.run(draft=FIXTURE, out_dir=self.out, name="t")
        root = ET.parse(result.xml_path).getroot()
        bodies_seen: set[str] = set()
        for f in root.iter("file"):
            fid = f.attrib.get("id")
            self.assertIsNotNone(fid)
            has_body = f.find("pathurl") is not None
            if has_body:
                self.assertNotIn(fid, bodies_seen,
                                 f"file {fid} declared with body more than once")
                bodies_seen.add(fid)

    def test_unsupported_categories_logged(self):
        """The mock has a text track, a transition ref (via extra_material_refs),
        and a keyframe ref. After v0.1.1 the transition surfaces with its
        specific 'transition' category (was 'extra_refs' under the legacy
        blanket reporter). The orphaned 'effects' material in the mock that
        no segment references is intentionally no longer surfaced — unused
        materials have no on-timeline impact."""
        result = bridge.run(draft=FIXTURE, out_dir=self.out, name="t")
        categories = {u.category for u in result.timeline.unsupported}
        self.assertIn("text", categories)
        self.assertIn("transition", categories)
        self.assertIn("keyframe", categories)
        self.assertNotIn("extra_refs", categories,
                         "the legacy blanket 'extra_refs' bucket must not "
                         "reappear after v0.1.1's per-category classification")

    def test_offline_clips_get_marker_url(self):
        """Mock paths don't exist; every file body should point at OFFLINE/."""
        result = bridge.run(draft=FIXTURE, out_dir=self.out, name="t")
        root = ET.parse(result.xml_path).getroot()
        for pathurl in root.iter("pathurl"):
            self.assertTrue(pathurl.text.startswith("file:///OFFLINE/"),
                            f"unexpected resolved path: {pathurl.text}")

    def test_report_mentions_offline_count(self):
        result = bridge.run(draft=FIXTURE, out_dir=self.out, name="t")
        text = result.report_path.read_text()
        self.assertIn("Offline / unresolved", text)
        self.assertIn("Media linking", text)


class WriterAudioContractTest(unittest.TestCase):
    """Regression tests for the writer's audio-track contract (v0.1.1).

    Before v0.1.1 the writer auto-extracted an audio track from every video
    clip whose asset.has_audio=True, on top of the IR's explicit audio_tracks.
    Real CapCut drafts ALWAYS also contain an explicit audio material+track
    for the same content, so the writer's auto-extraction caused duplicate
    audio on Premiere import (same audio on A1 and A2). These tests pin the
    writer to a pure IR→XML transform: emit exactly what the IR contains.
    """

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.out = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_mock_fixture_emits_exactly_one_audio_track(self):
        """Mock has 1 explicit audio (BGM) + 2 video clips with has_audio=True.
        Pre-fix XML had 2 audio tracks; post-fix must have exactly 1."""
        result = bridge.run(draft=FIXTURE, out_dir=self.out, name="t")
        root = ET.parse(result.xml_path).getroot()
        audio_tracks = root.findall("./sequence/media/audio/track")
        audio_clipitems = root.findall("./sequence/media/audio/track/clipitem")
        self.assertEqual(len(audio_tracks), 1,
                         "writer must emit exactly one audio track for a "
                         "draft with one explicit audio track in the IR")
        self.assertEqual(len(audio_clipitems), 1,
                         "exactly one audio clipitem (the BGM) — auto-extraction "
                         "from video assets must not happen")

    def test_ir_with_no_audio_tracks_yields_no_audio_clipitems(self):
        """Build an IR with one video track whose asset has has_audio=True
        but no audio tracks. Writer must emit zero audio clipitems."""
        from cutsmith.ir import (Timeline, SequenceSettings, MediaAsset,
                                 MediaKind, Track, TrackKind, Clip)
        from cutsmith.writer import write_fcp7_xml

        tl = Timeline(name="t", settings=SequenceSettings(1920, 1080, 30.0))
        tl.assets["v"] = MediaAsset(
            asset_id="v", name="v.mp4",
            original_path="/x/v.mp4", resolved_path="/x/v.mp4",
            media_kind=MediaKind.VIDEO, duration_us=10_000_000,
            has_video=True, has_audio=True,
        )
        vtrack = Track(track_id="vt", kind=TrackKind.VIDEO, name="V1")
        vtrack.clips.append(Clip(
            clip_id="c1", asset_id="v",
            source_in_us=0, source_out_us=5_000_000, timeline_start_us=0,
        ))
        tl.video_tracks.append(vtrack)

        xml_path = self.out / "no_audio.xml"
        write_fcp7_xml(tl, xml_path)
        root = ET.parse(xml_path).getroot()
        audio_clipitems = root.findall("./sequence/media/audio/track/clipitem")
        self.assertEqual(len(audio_clipitems), 0,
                         "writer must not synthesize audio clipitems from "
                         "video assets even when has_audio=True")

    def test_report_flags_video_clip_with_unexposed_embedded_audio(self):
        """Same IR as above (video with has_audio=True, no audio track) →
        report must include a warning so the user knows PR will import
        silent video. Without this warning, the silent-import is a silent
        regression that the user wouldn't notice until playback."""
        from cutsmith.ir import (Timeline, SequenceSettings, MediaAsset,
                                 MediaKind, Track, TrackKind, Clip)
        from cutsmith.resolver import ResolutionStats
        from cutsmith.report import write_report

        tl = Timeline(name="t", settings=SequenceSettings(1920, 1080, 30.0))
        tl.assets["v"] = MediaAsset(
            asset_id="v", name="v.mp4",
            original_path="/x/v.mp4", resolved_path="/x/v.mp4",
            media_kind=MediaKind.VIDEO, duration_us=10_000_000,
            has_video=True, has_audio=True,
        )
        vtrack = Track(track_id="vt", kind=TrackKind.VIDEO, name="V1")
        vtrack.clips.append(Clip(
            clip_id="c1", asset_id="v",
            source_in_us=0, source_out_us=5_000_000, timeline_start_us=0,
        ))
        tl.video_tracks.append(vtrack)

        report_path = self.out / "r.md"
        stats = ResolutionStats(
            total=1, resolved_as_is=1, resolved_via_search=0,
            unresolved=0, missing_assets=[],
        )
        write_report(tl, stats, report_path)
        text = report_path.read_text()
        self.assertIn("embedded audio", text,
                      "report must flag video clips whose source audio "
                      "is not on any track")

    def test_report_does_not_flag_when_audio_path_matches(self):
        """CapCut splits a video-with-audio into two material entries sharing
        the same `original_path`. When the IR has both (video track + audio
        track pointing at the same path), the report MUST NOT raise the
        embedded-audio warning — that audio IS exposed, just under a separate
        asset id."""
        from cutsmith.ir import (Timeline, SequenceSettings, MediaAsset,
                                 MediaKind, Track, TrackKind, Clip)
        from cutsmith.resolver import ResolutionStats
        from cutsmith.report import write_report

        tl = Timeline(name="t", settings=SequenceSettings(1920, 1080, 30.0))
        # video + audio assets pointing at the same source file
        tl.assets["v"] = MediaAsset(
            asset_id="v", name="v.mp4",
            original_path="/x/v.mp4", resolved_path="/x/v.mp4",
            media_kind=MediaKind.VIDEO, duration_us=10_000_000,
            has_video=True, has_audio=True,
        )
        tl.assets["a"] = MediaAsset(
            asset_id="a", name="v.mp4",
            original_path="/x/v.mp4", resolved_path="/x/v.mp4",
            media_kind=MediaKind.AUDIO, duration_us=10_000_000,
            has_video=False, has_audio=True,
        )
        vtrack = Track(track_id="vt", kind=TrackKind.VIDEO, name="V1")
        vtrack.clips.append(Clip(clip_id="c1", asset_id="v",
            source_in_us=0, source_out_us=5_000_000, timeline_start_us=0))
        atrack = Track(track_id="at", kind=TrackKind.AUDIO, name="A1")
        atrack.clips.append(Clip(clip_id="c2", asset_id="a",
            source_in_us=0, source_out_us=5_000_000, timeline_start_us=0))
        tl.video_tracks.append(vtrack)
        tl.audio_tracks.append(atrack)

        report_path = self.out / "r.md"
        stats = ResolutionStats(
            total=2, resolved_as_is=2, resolved_via_search=0,
            unresolved=0, missing_assets=[],
        )
        write_report(tl, stats, report_path)
        text = report_path.read_text()
        self.assertNotIn(
            "embedded audio", text,
            "audio asset with matching original_path covers the video's "
            "embedded audio — no warning should fire",
        )


class ReaderP1RegressionTest(unittest.TestCase):
    """v0.1.1 P1 fixes: speed tolerance + extra_material_refs categorization.

    These pin the two reader behaviours we shipped to silence false-positive
    speed-change reports (caused by CapCut's µs-level rounding) and to
    replace the blanket 'extra_refs' bucket with specific category labels.
    Both bugs disappeared from cleaner sample reports but neither has
    structural protection; without these tests a refactor could regress
    them silently.
    """

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.out = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _draft_with_segment(self, source_dur, target_dur, speed=1.0,
                            extra_materials=None, extra_refs=None):
        """One-video-clip draft tailored for assertions about a single segment.
        `extra_materials` is a dict like {"canvases": [...]} merged into
        materials; `extra_refs` is the segment's extra_material_refs list.
        """
        mats = {
            "videos": [{"id": "v", "path": "/tmp/v.mp4",
                        "duration": 30_000_000, "type": "video",
                        "has_audio": False}],
            "audios": [],
        }
        if extra_materials:
            mats.update(extra_materials)
        return {
            "version": 360000, "new_version": "test",
            "fps": 30.0, "duration": target_dur,
            "canvas_config": {"width": 1920, "height": 1080},
            "materials": mats,
            "tracks": [{
                "id": "vt", "type": "video", "attribute": 0,
                "segments": [{
                    "id": "s1", "material_id": "v",
                    "source_timerange": {"start": 0, "duration": source_dur},
                    "target_timerange": {"start": 0, "duration": target_dur},
                    "speed": speed,
                    "extra_material_refs": extra_refs or [],
                }],
            }],
        }

    def _run(self, raw):
        path = self.out / "draft.json"
        path.write_text(json.dumps(raw), encoding="utf-8")
        return read_draft(path)

    # ── speed tolerance ────────────────────────────────────────────────── #

    def test_speed_1us_duration_diff_is_silent(self):
        """1µs source/target rounding (what CapCut 167.0.0 emits all the time)
        must not look like a speed change."""
        tl = self._run(self._draft_with_segment(5_000_000, 5_000_001))
        self.assertEqual([u for u in tl.unsupported if u.category == "speed"], [])

    def test_speed_1ms_duration_diff_at_tolerance_is_silent(self):
        """Boundary: exactly 1000µs diff. Tolerance is `> 1000`, so equal is silent."""
        tl = self._run(self._draft_with_segment(5_000_000, 5_001_000))
        self.assertEqual([u for u in tl.unsupported if u.category == "speed"], [])

    def test_speed_2ms_duration_diff_is_reported(self):
        """Above tolerance — actual speed change disguised as duration mismatch."""
        tl = self._run(self._draft_with_segment(5_000_000, 5_002_000))
        self.assertEqual(len([u for u in tl.unsupported if u.category == "speed"]), 1)

    def test_explicit_non_unit_speed_is_reported(self):
        """speed=2.0 fires even though target_dur matches source_dur×2 exactly."""
        tl = self._run(self._draft_with_segment(2_500_000, 5_000_000, speed=2.0))
        self.assertEqual(len([u for u in tl.unsupported if u.category == "speed"]), 1)

    # ── extra_material_refs classification ─────────────────────────────── #

    def test_default_canvas_ref_is_silent(self):
        raw = self._draft_with_segment(
            5_000_000, 5_000_000,
            extra_materials={"canvases": [{"id": "c1", "type": "canvas_color",
                                           "color": "", "image": ""}]},
            extra_refs=["c1"])
        tl = self._run(raw)
        cats = {u.category for u in tl.unsupported}
        self.assertNotIn("canvas_override", cats)
        self.assertNotIn("extra_refs", cats)

    def test_default_speed_material_ref_is_silent(self):
        raw = self._draft_with_segment(
            5_000_000, 5_000_000,
            extra_materials={"speeds": [{"id": "sp1", "type": "speed", "mode": 0,
                                         "speed": 1.0, "curve_speed": None}]},
            extra_refs=["sp1"])
        tl = self._run(raw)
        self.assertNotIn("speed_curve", {u.category for u in tl.unsupported})

    def test_transition_ref_emits_transition_category(self):
        raw = self._draft_with_segment(
            5_000_000, 5_000_000,
            extra_materials={"transitions": [{"id": "tr1", "name": "Cross Dissolve"}]},
            extra_refs=["tr1"])
        tl = self._run(raw)
        cats = {u.category for u in tl.unsupported}
        self.assertIn("transition", cats)
        self.assertNotIn("extra_refs", cats)


class P3SpeedTimelineDurationTest(unittest.TestCase):
    """v0.1.1 P3 fix: timeline_duration_us must come from target_timerange.duration.

    The bug: variable-speed CapCut segments (e.g. 10s of source slowed to 0.5×
    to fill a 20s slot) had the writer producing a timeline slot of source_dur,
    not target_dur. Downstream clips would then start at the wrong frame —
    "looks right but plays wrong" — and the editor wouldn't notice until
    playback diverged from what CapCut showed.
    """

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.out = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _build_draft(self, segments: list[dict]) -> dict:
        """segments: list of {source_start, source_dur, target_start, target_dur, speed}."""
        return {
            "version": 360000, "new_version": "test",
            "fps": 30.0,
            "duration": max(s["target_start"] + s["target_dur"] for s in segments),
            "canvas_config": {"width": 1920, "height": 1080},
            "materials": {
                "videos": [{"id": "v", "path": "/tmp/v.mp4",
                            "duration": 1_000_000_000, "type": "video",
                            "has_audio": False}],
                "audios": [],
            },
            "tracks": [{
                "id": "vt", "type": "video", "attribute": 0,
                "segments": [{
                    "id": f"s{i}", "material_id": "v",
                    "source_timerange": {"start": s["source_start"],
                                         "duration": s["source_dur"]},
                    "target_timerange": {"start": s["target_start"],
                                         "duration": s["target_dur"]},
                    "speed": s.get("speed", 1.0),
                } for i, s in enumerate(segments)],
            }],
        }

    def _write(self, raw, filename="d.json"):
        path = self.out / filename
        path.write_text(json.dumps(raw), encoding="utf-8")
        return path

    def test_speed_change_clip_uses_target_duration(self):
        """Source slice 10s slowed into 20s target slot — IR clip must occupy
        20s on the timeline (not 10s)."""
        raw = self._build_draft([{
            "source_start": 0, "source_dur": 10_000_000,
            "target_start": 0, "target_dur": 20_000_000,
            "speed": 0.5,
        }])
        tl = read_draft(self._write(raw))
        clip = tl.video_tracks[0].clips[0]
        self.assertEqual(clip.timeline_duration_us, 20_000_000)
        self.assertEqual(clip.source_in_us, 0)
        self.assertEqual(clip.source_out_us, 10_000_000)

    def test_subsequent_clips_dont_drift_after_speed_change(self):
        """3 segments — middle one is sped up (10s source → 5s target). The
        third clip's timeline_start must equal seg1.target_dur + seg2.target_dur,
        NOT seg1.target_dur + seg2.source_dur (the pre-fix bug)."""
        raw = self._build_draft([
            {"source_start": 0, "source_dur": 5_000_000,
             "target_start": 0, "target_dur": 5_000_000},
            {"source_start": 0, "source_dur": 10_000_000,
             "target_start": 5_000_000, "target_dur": 5_000_000,
             "speed": 2.0},
            {"source_start": 0, "source_dur": 5_000_000,
             "target_start": 10_000_000, "target_dur": 5_000_000},
        ])
        tl = read_draft(self._write(raw))
        clips = tl.video_tracks[0].clips
        self.assertEqual(clips[0].timeline_start_us, 0)
        self.assertEqual(clips[0].timeline_duration_us, 5_000_000)
        self.assertEqual(clips[1].timeline_start_us, 5_000_000)
        self.assertEqual(clips[1].timeline_duration_us, 5_000_000)
        # The critical assertion: clip 3 starts where CapCut said it does (10s),
        # not where the pre-fix bug placed it (5 + 10 = 15s drift).
        self.assertEqual(clips[2].timeline_start_us, 10_000_000)
        self.assertEqual(clips[2].timeline_duration_us, 5_000_000)

    def test_writer_emits_target_duration_for_speed_clip(self):
        """XML's end-start frames must reflect target_dur, not source_dur.
        For a 0.5× speed clip (5s source → 10s target at 30fps), end-start = 300f."""
        raw = self._build_draft([{
            "source_start": 0, "source_dur": 5_000_000,
            "target_start": 0, "target_dur": 10_000_000,
            "speed": 0.5,
        }])
        xml_path = self.out / "speed.xml"
        from cutsmith import bridge
        result = bridge.run(draft=self._write(raw), out_dir=self.out, name="t")
        root = ET.parse(result.xml_path).getroot()
        clip_el = root.find(".//sequence/media/video/track/clipitem")
        self.assertIsNotNone(clip_el)
        start = int(clip_el.findtext("start"))
        end = int(clip_el.findtext("end"))
        in_ = int(clip_el.findtext("in"))
        out = int(clip_el.findtext("out"))
        # 10s @ 30fps = 300 frames timeline; 5s @ 30fps = 150 frames source
        self.assertEqual(end - start, 300,
                         "timeline slot must be target_dur frames (300), "
                         "not source_dur frames (150)")
        self.assertEqual(out - in_, 150,
                         "source range stays source_timerange — Premiere will "
                         "interpret the end-start ≠ out-in mismatch as implied "
                         "speed and the report flags it for manual override")


class TimelineNameFallbackTest(unittest.TestCase):
    """v0.1.1: timeline.name fallback when the file is literally `draft_info.json`."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.out = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    _MINIMAL_DRAFT = {
        "version": 360000, "new_version": "t",
        "fps": 30.0, "duration": 1_000_000,
        "canvas_config": {"width": 1920, "height": 1080},
        "materials": {"videos": [], "audios": []},
        "tracks": [],
    }

    def _write_at(self, relpath: str) -> Path:
        path = self.out / relpath
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self._MINIMAL_DRAFT), encoding="utf-8")
        return path

    def test_legacy_draft_content_uses_stem(self):
        """Old-style draft_content.json keeps using the stem ('draft_content')
        rather than walking up — the legacy filename is fine on its own."""
        path = self._write_at("legacy_project/draft_content.json")
        tl = read_draft(path)
        self.assertEqual(tl.name, "draft_content")

    def test_flat_draft_info_uses_parent_dir(self):
        """CapCut Desktop's flat layout: <project>/draft_info.json — use
        the project folder name ('cutsmith2') rather than 'draft_info'."""
        path = self._write_at("cutsmith2/draft_info.json")
        tl = read_draft(path)
        self.assertEqual(tl.name, "cutsmith2")

    def test_nested_draft_info_skips_uuid_and_timelines(self):
        """Nested layout: <project>/Timelines/<UUID>/draft_info.json — walk
        past UUID and 'Timelines' to find 'project'."""
        path = self._write_at(
            "myproject/Timelines/A90A6676-4E3C-4828-9687-301F08635DB5/draft_info.json"
        )
        tl = read_draft(path)
        self.assertEqual(tl.name, "myproject")


if __name__ == "__main__":
    unittest.main()
