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
        """For clips WITHOUT a timeremap filter end-start must equal out-in.
        Speed-changed clips carry a timeremap filter and intentionally diverge."""
        result = bridge.run(draft=FIXTURE, out_dir=self.out, name="t")
        root = ET.parse(result.xml_path).getroot()
        for ci in root.iter("clipitem"):
            has_timeremap = any(
                e.findtext("effectid") == "timeremap"
                for e in ci.iter("effect")
            )
            if has_timeremap:
                continue  # divergence is intentional — speed filter handles it
            start = int(ci.findtext("start"))
            end = int(ci.findtext("end"))
            in_ = int(ci.findtext("in"))
            out = int(ci.findtext("out"))
            self.assertEqual(end - start, out - in_,
                             f"clipitem {ci.attrib.get('id')} has "
                             f"mismatched timeline/source duration without speed filter")

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


class SpeedFilterWriterTest(unittest.TestCase):
    """FCP7 Time Remap filter — regression tests for explicit speed encoding.

    Without the timeremap filter, Premiere ignores end-start vs out-in
    divergence and plays speed-changed clips at 100% with a black tail.
    These tests pin the filter to appear when and only when needed.
    """

    def _make_timeline(
        self,
        source_dur_us: int,
        timeline_dur_us: int,
        kind: str = "video",
    ):
        """Build a minimal IR with one clip at the given source/timeline durations."""
        from cutsmith.ir import (
            Clip, MediaAsset, MediaKind, SequenceSettings, Timeline, Track, TrackKind,
        )
        fps = 30.0
        tl = Timeline(name="t", settings=SequenceSettings(1920, 1080, fps))
        tl.assets["a"] = MediaAsset(
            asset_id="a", name="a.mp4",
            original_path="/x/a.mp4", resolved_path="/x/a.mp4",
            media_kind=MediaKind.VIDEO, duration_us=source_dur_us,
            has_video=True, has_audio=True,
        )
        clip = Clip(
            clip_id="c1", asset_id="a",
            source_in_us=0, source_out_us=source_dur_us,
            timeline_start_us=0,
            timeline_duration_us=timeline_dur_us,
        )
        if kind == "video":
            track = Track(track_id="vt", kind=TrackKind.VIDEO, name="V1")
            tl.video_tracks.append(track)
        else:
            track = Track(track_id="at", kind=TrackKind.AUDIO, name="A1")
            tl.audio_tracks.append(track)
        track.clips.append(clip)
        return tl

    def setUp(self):
        import tempfile
        self._tmp = tempfile.TemporaryDirectory()
        self.out = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def _write_and_parse(self, tl):
        from cutsmith.writer import write_fcp7_xml
        xml_path = self.out / "t.xml"
        write_fcp7_xml(tl, xml_path)
        return ET.parse(xml_path).getroot()

    def _timeremap_values(self, root):
        """Return list of speed values from all timeremap filters in the XML."""
        values = []
        for eff in root.iter("effect"):
            if eff.findtext("effectid") == "timeremap":
                for param in eff.iter("parameter"):
                    if param.findtext("parameterid") == "speed":
                        values.append(param.findtext("value"))
        return values

    def test_speed_1x_clip_has_no_timeremap_filter(self):
        """A 1.0× clip (source == timeline) must NOT get a timeremap filter."""
        tl = self._make_timeline(source_dur_us=10_000_000, timeline_dur_us=10_000_000)
        root = self._write_and_parse(tl)
        self.assertEqual(self._timeremap_values(root), [],
                         "1.0× clip must not emit a timeremap filter")

    def test_half_speed_clip_gets_timeremap_filter(self):
        """0.5× clip (source=5s, timeline=10s) → timeremap filter present."""
        tl = self._make_timeline(source_dur_us=5_000_000, timeline_dur_us=10_000_000)
        root = self._write_and_parse(tl)
        values = self._timeremap_values(root)
        self.assertEqual(len(values), 1, "exactly one timeremap filter expected")

    def test_half_speed_value_is_50(self):
        """0.5× speed → speed parameter value ≈ 50.0000."""
        tl = self._make_timeline(source_dur_us=5_000_000, timeline_dur_us=10_000_000)
        root = self._write_and_parse(tl)
        values = self._timeremap_values(root)
        self.assertEqual(len(values), 1)
        self.assertAlmostEqual(float(values[0]), 50.0, places=1)

    def test_double_speed_value_is_200(self):
        """2.0× speed → speed parameter value ≈ 200.0000."""
        tl = self._make_timeline(source_dur_us=10_000_000, timeline_dur_us=5_000_000)
        root = self._write_and_parse(tl)
        values = self._timeremap_values(root)
        self.assertEqual(len(values), 1)
        self.assertAlmostEqual(float(values[0]), 200.0, places=1)

    def test_timeremap_effectid_and_category(self):
        """Filter must declare effectid=timeremap and effectcategory=motion."""
        tl = self._make_timeline(source_dur_us=5_000_000, timeline_dur_us=10_000_000)
        root = self._write_and_parse(tl)
        effects = [e for e in root.iter("effect") if e.findtext("effectid") == "timeremap"]
        self.assertEqual(len(effects), 1)
        eff = effects[0]
        self.assertEqual(eff.findtext("effectcategory"), "motion")
        self.assertEqual(eff.findtext("effecttype"), "motion")

    def test_timeremap_reverse_and_frameblending_params_present(self):
        """Filter must include reverse=FALSE and frameblending=FALSE params."""
        tl = self._make_timeline(source_dur_us=5_000_000, timeline_dur_us=10_000_000)
        root = self._write_and_parse(tl)
        effects = [e for e in root.iter("effect") if e.findtext("effectid") == "timeremap"]
        eff = effects[0]
        param_ids = {
            p.findtext("parameterid"): p.findtext("value")
            for p in eff.iter("parameter")
        }
        self.assertEqual(param_ids.get("reverse"), "FALSE")
        self.assertEqual(param_ids.get("frameblending"), "FALSE")

    def test_audio_clip_speed_change_gets_timeremap_filter(self):
        """Speed-changed audio clipitems also get the timeremap filter."""
        tl = self._make_timeline(
            source_dur_us=5_000_000, timeline_dur_us=10_000_000, kind="audio"
        )
        root = self._write_and_parse(tl)
        values = self._timeremap_values(root)
        self.assertEqual(len(values), 1, "audio speed clip needs timeremap too")
        self.assertAlmostEqual(float(values[0]), 50.0, places=1)

    def test_audio_timeremap_mediatype_is_audio(self):
        """timeremap filter on an audio clipitem must declare mediatype=audio."""
        tl = self._make_timeline(
            source_dur_us=5_000_000, timeline_dur_us=10_000_000, kind="audio"
        )
        root = self._write_and_parse(tl)
        effects = [e for e in root.iter("effect") if e.findtext("effectid") == "timeremap"]
        self.assertEqual(len(effects), 1)
        self.assertEqual(effects[0].findtext("mediatype"), "audio")

    def test_video_timeremap_mediatype_is_video(self):
        """timeremap filter on a video clipitem must declare mediatype=video."""
        tl = self._make_timeline(source_dur_us=5_000_000, timeline_dur_us=10_000_000)
        root = self._write_and_parse(tl)
        effects = [e for e in root.iter("effect") if e.findtext("effectid") == "timeremap"]
        self.assertEqual(len(effects), 1)
        self.assertEqual(effects[0].findtext("mediatype"), "video")

    def test_rounding_tolerance_no_spurious_filter(self):
        """A 1-frame rounding difference must NOT produce a timeremap filter."""
        frame_us = int(1_000_000 / 30)  # 33333 µs
        tl = self._make_timeline(
            source_dur_us=10_000_000,
            timeline_dur_us=10_000_000 + frame_us,  # 1 frame over — within tolerance
        )
        root = self._write_and_parse(tl)
        self.assertEqual(self._timeremap_values(root), [],
                         "1-frame rounding delta must not trigger timeremap")

    def test_clipitem_duration_equals_source_range(self):
        """<clipitem><duration> must equal out-in (source frames used), not
        the full asset duration. Premiere uses <file><duration> for trim bounds;
        clipitem duration is the clip's own source-domain length."""
        # 0.5× speed: source=5s (150f), timeline=10s (300f), asset=20s (600f)
        from cutsmith.ir import (
            Clip, MediaAsset, MediaKind, SequenceSettings, Timeline, Track, TrackKind,
        )
        tl = Timeline(name="t", settings=SequenceSettings(1920, 1080, 30.0))
        tl.assets["a"] = MediaAsset(
            asset_id="a", name="a.mp4",
            original_path="/x/a.mp4", resolved_path="/x/a.mp4",
            media_kind=MediaKind.VIDEO, duration_us=20_000_000,  # full file = 20s
            has_video=True, has_audio=False,
        )
        clip = Clip(
            clip_id="c1", asset_id="a",
            source_in_us=0, source_out_us=5_000_000,      # use 5s of the 20s file
            timeline_start_us=0, timeline_duration_us=10_000_000,  # 10s slot at 0.5×
        )
        track = Track(track_id="vt", kind=TrackKind.VIDEO, name="V1")
        track.clips.append(clip)
        tl.video_tracks.append(track)
        root = self._write_and_parse(tl)
        ci = root.find(".//sequence/media/video/track/clipitem")
        self.assertIsNotNone(ci)
        dur = int(ci.findtext("duration"))
        out = int(ci.findtext("out"))
        in_ = int(ci.findtext("in"))
        self.assertEqual(dur, out - in_,
                         f"clipitem duration must be out-in={out-in_} "
                         f"(source frames), got {dur}")
        # file.duration must still be the full asset (20s = 600f)
        # File body now lives in the master <clip>, not in the <clipitem> stub.
        file_el = root.find(".//clip/file[@id='file-a']")
        self.assertIsNotNone(file_el, "file body must be in master clip")
        file_dur = int(file_el.findtext("duration"))
        self.assertEqual(file_dur, 600, "file.duration must reflect full source file")

    def test_clipitem_duration_source_range_for_speed_clip(self):
        """Speed clip: duration = out-in (source range), not timeline slot."""
        tl = self._make_timeline(source_dur_us=5_000_000, timeline_dur_us=10_000_000)
        root = self._write_and_parse(tl)
        ci = root.find(".//sequence/media/video/track/clipitem")
        dur = int(ci.findtext("duration"))
        out = int(ci.findtext("out"))
        in_ = int(ci.findtext("in"))
        end = int(ci.findtext("end"))
        start = int(ci.findtext("start"))
        self.assertEqual(dur, out - in_, "speed clip duration must be source range")
        self.assertNotEqual(dur, end - start, "duration must NOT be timeline slot")


class MasterClipWriterTest(unittest.TestCase):
    """Regression tests for FCP7 master clip structure.

    Without <clip id="masterclip-..."> at the xmeml root and <masterclipid>
    in each <clipitem>, Premiere imports the timeline but creates no Project
    panel source items — breaking relink, trim stability, and media management.
    """

    def setUp(self):
        import tempfile
        self._tmp = tempfile.TemporaryDirectory()
        self.out = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def _make_simple_timeline(self):
        from cutsmith.ir import (
            Clip, MediaAsset, MediaKind, SequenceSettings, Timeline, Track, TrackKind,
        )
        tl = Timeline(name="t", settings=SequenceSettings(1920, 1080, 30.0))
        tl.assets["v1"] = MediaAsset(
            asset_id="v1", name="clip1.mp4",
            original_path="/x/clip1.mp4", resolved_path="/x/clip1.mp4",
            media_kind=MediaKind.VIDEO, duration_us=10_000_000,
            has_video=True, has_audio=False,
        )
        tl.assets["v2"] = MediaAsset(
            asset_id="v2", name="clip2.mp4",
            original_path="/x/clip2.mp4", resolved_path="/x/clip2.mp4",
            media_kind=MediaKind.VIDEO, duration_us=8_000_000,
            has_video=True, has_audio=False,
        )
        vtrack = Track(track_id="vt", kind=TrackKind.VIDEO, name="V1")
        from cutsmith.ir import Clip, TrackKind
        vtrack.clips.append(Clip(clip_id="c1", asset_id="v1",
            source_in_us=0, source_out_us=10_000_000, timeline_start_us=0))
        vtrack.clips.append(Clip(clip_id="c2", asset_id="v2",
            source_in_us=0, source_out_us=8_000_000, timeline_start_us=10_000_000))
        tl.video_tracks.append(vtrack)
        return tl

    def _write_and_parse(self, tl):
        from cutsmith.writer import write_fcp7_xml
        xml_path = self.out / "t.xml"
        write_fcp7_xml(tl, xml_path)
        return ET.parse(xml_path).getroot()

    def test_master_clips_at_xmeml_root(self):
        """One <clip id="masterclip-..."> per asset must appear at xmeml root."""
        root = self._write_and_parse(self._make_simple_timeline())
        master_clips = root.findall("clip")  # direct children of xmeml
        self.assertEqual(len(master_clips), 2, "one master clip per asset")
        ids = {c.attrib.get("id") for c in master_clips}
        self.assertIn("masterclip-v1", ids)
        self.assertIn("masterclip-v2", ids)

    def test_master_clip_before_sequence(self):
        """Master clips must precede <sequence> in document order so Premiere
        can resolve <masterclipid> references when parsing the sequence."""
        root = self._write_and_parse(self._make_simple_timeline())
        children = list(root)
        tags = [c.tag for c in children]
        last_clip_idx = max(i for i, t in enumerate(tags) if t == "clip")
        seq_idx = tags.index("sequence")
        self.assertLess(last_clip_idx, seq_idx,
                        "all master clips must appear before <sequence>")

    def test_master_clip_duration_is_asset_duration(self):
        """Master clip <duration> must be the full source file duration."""
        root = self._write_and_parse(self._make_simple_timeline())
        mc = root.find("clip[@id='masterclip-v1']")
        self.assertIsNotNone(mc)
        self.assertEqual(mc.findtext("duration"), "300",  # 10s @ 30fps
                         "master clip duration must be full asset duration (300f)")

    def test_master_clip_in_out_minus_one(self):
        """Master clip in/out must be -1 (untrimmed — full source available)."""
        root = self._write_and_parse(self._make_simple_timeline())
        for mc in root.findall("clip"):
            self.assertEqual(mc.findtext("in"), "-1",
                             f"{mc.attrib.get('id')} must have in=-1")
            self.assertEqual(mc.findtext("out"), "-1",
                             f"{mc.attrib.get('id')} must have out=-1")

    def test_file_body_in_master_clip_not_clipitem(self):
        """<file> body (with <pathurl>) must live in master clip; clipitems get stubs."""
        root = self._write_and_parse(self._make_simple_timeline())
        # Bodies must be in master <clip> elements
        for mc in root.findall("clip"):
            f = mc.find("file")
            self.assertIsNotNone(f, f"{mc.attrib.get('id')} must contain a <file>")
            self.assertIsNotNone(f.find("pathurl"),
                                 f"{mc.attrib.get('id')}.file must have <pathurl>")
        # clipitems must have id-only stubs
        for ci in root.iter("clipitem"):
            f = ci.find("file")
            self.assertIsNotNone(f, f"clipitem {ci.attrib.get('id')} must have <file> stub")
            self.assertIsNone(f.find("pathurl"),
                              f"clipitem {ci.attrib.get('id')}.file must be a stub (no pathurl)")

    def test_clipitem_has_masterclipid(self):
        """Every <clipitem> must have a <masterclipid> element."""
        root = self._write_and_parse(self._make_simple_timeline())
        for ci in root.iter("clipitem"):
            mci = ci.findtext("masterclipid")
            self.assertIsNotNone(mci,
                                 f"clipitem {ci.attrib.get('id')} missing <masterclipid>")

    def test_masterclipid_references_existing_master_clip(self):
        """Each <masterclipid> value must match an actual <clip> id at xmeml root."""
        root = self._write_and_parse(self._make_simple_timeline())
        master_ids = {c.attrib.get("id") for c in root.findall("clip")}
        for ci in root.iter("clipitem"):
            mci = ci.findtext("masterclipid")
            self.assertIn(mci, master_ids,
                          f"clipitem {ci.attrib.get('id')} masterclipid={mci!r} "
                          f"has no matching master clip")

    def test_collect_path_override_appears_in_master_clip_file_body(self):
        """path_override (collect mode) must flow into the master clip's <file><pathurl>,
        not stay in the original resolved_path. Relink via parent-folder in Premiere
        requires the collected path to be the one in the XML."""
        from cutsmith.ir import (
            Clip, MediaAsset, MediaKind, SequenceSettings, Timeline, Track, TrackKind,
        )
        from cutsmith.writer import write_fcp7_xml
        tl = Timeline(name="t", settings=SequenceSettings(1920, 1080, 30.0))
        tl.assets["v1"] = MediaAsset(
            asset_id="v1", name="a.mp4",
            original_path="/src/a.mp4", resolved_path="/src/a.mp4",
            media_kind=MediaKind.VIDEO, duration_us=10_000_000,
            has_video=True, has_audio=False,
        )
        vtrack = Track(track_id="vt", kind=TrackKind.VIDEO, name="V1")
        vtrack.clips.append(Clip(clip_id="c1", asset_id="v1",
            source_in_us=0, source_out_us=10_000_000, timeline_start_us=0))
        tl.video_tracks.append(vtrack)
        collected_path = "/out/media/video/a.mp4"
        xml_path = self.out / "t.xml"
        write_fcp7_xml(tl, xml_path, path_override={"v1": collected_path})
        root = ET.parse(xml_path).getroot()
        mc = root.find("clip[@id='masterclip-v1']")
        pathurl = mc.findtext("file/pathurl")
        self.assertIsNotNone(pathurl)
        self.assertIn("media/video/a.mp4", pathurl,
                      "collected path must appear in master clip pathurl")
        self.assertNotIn("/src/a.mp4", pathurl,
                         "original path must NOT appear in master clip pathurl")

    def test_multiple_clipitems_same_asset_share_one_master_clip(self):
        """If the same asset appears multiple times on the timeline, there must
        still be exactly one master clip and one file body for it."""
        from cutsmith.ir import (
            Clip, MediaAsset, MediaKind, SequenceSettings, Timeline, Track, TrackKind,
        )
        tl = Timeline(name="t", settings=SequenceSettings(1920, 1080, 30.0))
        tl.assets["v1"] = MediaAsset(
            asset_id="v1", name="clip1.mp4",
            original_path="/x/clip1.mp4", resolved_path="/x/clip1.mp4",
            media_kind=MediaKind.VIDEO, duration_us=30_000_000,
            has_video=True, has_audio=False,
        )
        vtrack = Track(track_id="vt", kind=TrackKind.VIDEO, name="V1")
        vtrack.clips.append(Clip(clip_id="c1", asset_id="v1",
            source_in_us=0, source_out_us=10_000_000, timeline_start_us=0))
        vtrack.clips.append(Clip(clip_id="c2", asset_id="v1",
            source_in_us=10_000_000, source_out_us=20_000_000, timeline_start_us=10_000_000))
        tl.video_tracks.append(vtrack)
        root = self._write_and_parse(tl)
        master_clips = root.findall("clip")
        self.assertEqual(len(master_clips), 1, "one master clip even when reused")
        file_bodies = [f for f in root.iter("file") if f.find("pathurl") is not None]
        self.assertEqual(len(file_bodies), 1, "one file body even when reused")


if __name__ == "__main__":
    unittest.main()
