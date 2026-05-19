"""Tests for cutsmith.collector — copy + relink pipeline."""

from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from cutsmith.collector import (
    CollectStats,
    _copy_online_assets,
    _count_media_subdirs,
    _unique_dest,
    _write_offline_report,
    _write_package_summary,
    _write_relink_guide,
)
from cutsmith.ir import AssetClass
from cutsmith.scanner.manifest import AssetManifest, ManifestEntry

# ─── fixtures ─────────────────────────────────────────────────────────────────

FIXTURE_COLLECT = Path(__file__).parent / "fixtures" / "mock_collect_draft.json"


def _entry(
    asset_id: str,
    name: str,
    asset_class: AssetClass,
    resolved_path: str | None = None,
    is_online: bool = True,
    used_in_tracks: list[str] | None = None,
) -> ManifestEntry:
    return ManifestEntry(
        asset_id=asset_id,
        name=name,
        asset_class=asset_class,
        original_path=resolved_path,
        resolved_path=resolved_path,
        is_cached=False,
        is_online=is_online,
        file_size_bytes=None if not is_online else 100,
        duration_us=1_000_000,
        used_in_tracks=used_in_tracks or [],
        clip_count=1,
    )


def _make_manifest(
    tmp_dir: Path,
    *,
    with_collision: bool = False,
    with_offline_user: bool = False,
    with_offline_capcut: bool = False,
    with_effect: bool = False,
) -> AssetManifest:
    """Build a test manifest with real temp source files where is_online=True."""
    # Create real source files so shutil.copy2 succeeds.
    v_a = tmp_dir / "clip_a.mp4"; v_a.write_bytes(b"video_a")
    a_m = tmp_dir / "bgm.mp3";    a_m.write_bytes(b"music")
    a_sfx = tmp_dir / "sfx.mp3";  a_sfx.write_bytes(b"sfx")

    videos = [_entry("VID-A", "clip_a.mp4", AssetClass.USER_VIDEO, str(v_a))]
    music  = [_entry("AUD-M", "bgm.mp3", AssetClass.CAPCUT_MUSIC, str(a_m))]
    sfx    = [_entry("AUD-S", "sfx.mp3", AssetClass.CAPCUT_SFX, str(a_sfx))]
    audios: list[ManifestEntry] = []
    effects: list[ManifestEntry] = []
    offline: list[ManifestEntry] = []

    if with_collision:
        # Second video with same basename — different asset_id → should rename.
        v_b = tmp_dir / "clip_b.mp4"; v_b.write_bytes(b"video_b")
        # We rename source to same basename to trigger collision.
        v_same = tmp_dir / "collision_src" / "clip_a.mp4"
        v_same.parent.mkdir(parents=True, exist_ok=True)
        v_same.write_bytes(b"video_b_same_name")
        videos.append(_entry("VID-B", "clip_a.mp4", AssetClass.USER_VIDEO, str(v_same)))

    if with_offline_user:
        e = _entry("VID-OFF", "lost_clip.mp4", AssetClass.USER_VIDEO,
                   is_online=False, used_in_tracks=["V1"])
        e.original_path = "/nonexistent/lost_clip.mp4"
        # Mirror real scanner: offline entries appear in primary list AND offline cross-list
        videos.append(e)
        offline.append(e)

    if with_offline_capcut:
        e = _entry("STK-OFF", "CoolSticker", AssetClass.CAPCUT_STICKER,
                   is_online=False, used_in_tracks=["sticker"])
        e.original_path = "/nonexistent/cache/sticker.webp"
        offline.append(e)

    if with_effect:
        effects = [_entry("EFF-1", "Glitch", AssetClass.CAPCUT_EFFECT,
                          is_online=False)]

    m = AssetManifest(
        project_name="test_project",
        source_draft="/tmp/draft_info.json",
        videos=videos,
        audios=audios,
        music=music,
        sfx=sfx,
        effects=effects,
        offline=offline,
        total_assets=len(videos) + len(music) + len(sfx) + len(effects),
        online_count=len(videos) + len(music) + len(sfx),
        offline_count=len(offline),
    )
    return m


# ─── _unique_dest ─────────────────────────────────────────────────────────────

class UniquDestTest(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dest_dir = Path(self._tmp.name)
        self.used: set[str] = set()

    def tearDown(self):
        self._tmp.cleanup()

    def test_no_collision_keeps_original_name(self):
        src = Path("/some/path/clip.mp4")
        dest = _unique_dest(src, "ABCDEF12-0000-0000-0000-000000000000", self.dest_dir, self.used)
        self.assertEqual(dest.name, "clip.mp4")
        self.assertIn("clip.mp4", self.used)

    def test_collision_adds_asset_id_prefix(self):
        src = Path("/some/path/clip.mp4")
        _unique_dest(src, "AAAAAAAA-0000-0000-0000-000000000000", self.dest_dir, self.used)
        dest2 = _unique_dest(src, "BBBBBBBB-0000-0000-0000-000000000000", self.dest_dir, self.used)
        self.assertIn("BBBBBBBB", dest2.name)
        self.assertTrue(dest2.name.endswith(".mp4"))
        self.assertNotEqual(dest2.name, "clip.mp4")

    def test_no_collision_different_extensions_both_kept(self):
        src_mp4 = Path("/a/clip.mp4")
        src_mov = Path("/b/clip.mov")
        d1 = _unique_dest(src_mp4, "ID1", self.dest_dir, self.used)
        d2 = _unique_dest(src_mov, "ID2", self.dest_dir, self.used)
        self.assertEqual(d1.name, "clip.mp4")
        self.assertEqual(d2.name, "clip.mov")


# ─── _copy_online_assets ──────────────────────────────────────────────────────

class CopyOnlineAssetsTest(unittest.TestCase):

    def setUp(self):
        self._src_tmp = tempfile.TemporaryDirectory()
        self._out_tmp = tempfile.TemporaryDirectory()
        self.src_dir = Path(self._src_tmp.name)
        self.out_dir = Path(self._out_tmp.name)
        self.media_dir = self.out_dir / "media"

    def tearDown(self):
        self._src_tmp.cleanup()
        self._out_tmp.cleanup()

    def test_copies_online_video_to_video_subdir(self):
        m = _make_manifest(self.src_dir)
        _copy_online_assets(m, self.media_dir, self.out_dir)
        self.assertTrue((self.media_dir / "video" / "clip_a.mp4").exists())

    def test_copies_music_to_music_subdir(self):
        m = _make_manifest(self.src_dir)
        _copy_online_assets(m, self.media_dir, self.out_dir)
        self.assertTrue((self.media_dir / "music" / "bgm.mp3").exists())

    def test_copies_sfx_to_sfx_subdir(self):
        m = _make_manifest(self.src_dir)
        _copy_online_assets(m, self.media_dir, self.out_dir)
        self.assertTrue((self.media_dir / "sfx" / "sfx.mp3").exists())

    def test_returns_path_override_for_copied_assets(self):
        m = _make_manifest(self.src_dir)
        override, _ = _copy_online_assets(m, self.media_dir, self.out_dir)
        self.assertIn("VID-A", override)
        self.assertTrue(Path(override["VID-A"]).exists())

    def test_skips_offline_assets(self):
        m = _make_manifest(self.src_dir, with_offline_user=True)
        override, stats = _copy_online_assets(m, self.media_dir, self.out_dir)
        self.assertNotIn("VID-OFF", override)
        self.assertGreater(stats.offline_count, 0)

    def test_skips_report_only_effects(self):
        m = _make_manifest(self.src_dir, with_effect=True)
        override, stats = _copy_online_assets(m, self.media_dir, self.out_dir)
        self.assertNotIn("EFF-1", override)
        self.assertGreater(stats.skipped_report_only_count, 0)

    def test_no_effect_files_in_media_dir(self):
        m = _make_manifest(self.src_dir, with_effect=True)
        _copy_online_assets(m, self.media_dir, self.out_dir)
        effect_dir = self.media_dir / "effect"
        self.assertFalse(effect_dir.exists())

    def test_collision_produces_two_distinct_files(self):
        m = _make_manifest(self.src_dir, with_collision=True)
        override, stats = _copy_online_assets(m, self.media_dir, self.out_dir)
        video_files = list((self.media_dir / "video").iterdir())
        self.assertEqual(len(video_files), 2)
        names = {f.name for f in video_files}
        self.assertIn("clip_a.mp4", names)
        # The disambiguated file has the asset_id[:8] in its name.
        non_original = [n for n in names if n != "clip_a.mp4"]
        self.assertEqual(len(non_original), 1)
        self.assertIn("VID-B"[:8], non_original[0])

    def test_collect_relative_path_populated_on_entry(self):
        m = _make_manifest(self.src_dir)
        _copy_online_assets(m, self.media_dir, self.out_dir)
        video_entry = m.videos[0]
        self.assertIsNotNone(video_entry.collect_relative_path)
        self.assertTrue(video_entry.collect_relative_path.startswith("media/"))

    def test_stats_copied_count_matches_files(self):
        m = _make_manifest(self.src_dir)
        _, stats = _copy_online_assets(m, self.media_dir, self.out_dir)
        # video(1) + music(1) + sfx(1) = 3
        self.assertEqual(stats.copied_count, 3)

    def test_stats_total_size_nonzero(self):
        m = _make_manifest(self.src_dir)
        _, stats = _copy_online_assets(m, self.media_dir, self.out_dir)
        self.assertGreater(stats.total_copied_size_bytes, 0)

    def test_offline_not_in_path_override(self):
        m = _make_manifest(self.src_dir, with_offline_user=True)
        override, _ = _copy_online_assets(m, self.media_dir, self.out_dir)
        for e in m.offline:
            self.assertNotIn(e.asset_id, override)

    def test_online_uncopyable_capcut_effect_not_copied(self):
        """Even if an effect somehow has is_online=True, it should be skipped."""
        m = _make_manifest(self.src_dir)
        # Inject an "online" effect (shouldn't copy it).
        eff_path = self.src_dir / "effect.bundle"
        eff_path.write_bytes(b"bundle")
        fake_eff = _entry("EFF-X", "FakeEffect", AssetClass.CAPCUT_EFFECT, str(eff_path))
        m.effects.append(fake_eff)
        override, stats = _copy_online_assets(m, self.media_dir, self.out_dir)
        self.assertNotIn("EFF-X", override)
        self.assertGreater(stats.skipped_report_only_count, 0)

    # ── deduplication (same physical file, multiple asset IDs) ────────────────

    def test_same_physical_file_copied_once_in_same_subdir(self):
        """Two video asset IDs pointing to the same source file must produce
        one physical copy, not two."""
        src = self.src_dir / "interview.mp4"
        src.write_bytes(b"video" * 200)
        entry_a = ManifestEntry(
            asset_id="VID-A1", name="interview.mp4", asset_class=AssetClass.USER_VIDEO,
            original_path=str(src), resolved_path=str(src),
            is_cached=False, is_online=True, file_size_bytes=1000,
            duration_us=10_000_000, used_in_tracks=["V1"], clip_count=1,
        )
        entry_b = ManifestEntry(
            asset_id="VID-A2", name="interview.mp4", asset_class=AssetClass.USER_VIDEO,
            original_path=str(src), resolved_path=str(src),
            is_cached=False, is_online=True, file_size_bytes=1000,
            duration_us=10_000_000, used_in_tracks=["V2"], clip_count=1,
        )
        m = AssetManifest(project_name="p", videos=[entry_a, entry_b])
        override, stats = _copy_online_assets(m, self.media_dir, self.out_dir)

        video_files = list((self.media_dir / "video").iterdir())
        self.assertEqual(len(video_files), 1, "Expected one physical copy, not two")

    def test_deduped_entries_share_path_override(self):
        """Both asset IDs must point to the same destination in path_override."""
        src = self.src_dir / "interview.mp4"
        src.write_bytes(b"video" * 200)
        entry_a = ManifestEntry(
            asset_id="VID-A1", name="interview.mp4", asset_class=AssetClass.USER_VIDEO,
            original_path=str(src), resolved_path=str(src),
            is_cached=False, is_online=True, file_size_bytes=1000,
            duration_us=10_000_000, used_in_tracks=["V1"], clip_count=1,
        )
        entry_b = ManifestEntry(
            asset_id="VID-A2", name="interview.mp4", asset_class=AssetClass.USER_VIDEO,
            original_path=str(src), resolved_path=str(src),
            is_cached=False, is_online=True, file_size_bytes=1000,
            duration_us=10_000_000, used_in_tracks=["V2"], clip_count=1,
        )
        m = AssetManifest(project_name="p", videos=[entry_a, entry_b])
        override, stats = _copy_online_assets(m, self.media_dir, self.out_dir)

        self.assertIn("VID-A1", override)
        self.assertIn("VID-A2", override)
        self.assertEqual(override["VID-A1"], override["VID-A2"],
                         "Both IDs must point to the same physical file")

    def test_dedup_counted_in_stats(self):
        src = self.src_dir / "interview.mp4"
        src.write_bytes(b"video" * 200)
        entries = [
            ManifestEntry(
                asset_id=f"VID-{i}", name="interview.mp4",
                asset_class=AssetClass.USER_VIDEO,
                original_path=str(src), resolved_path=str(src),
                is_cached=False, is_online=True, file_size_bytes=1000,
                duration_us=10_000_000, used_in_tracks=["V1"], clip_count=1,
            )
            for i in range(4)
        ]
        m = AssetManifest(project_name="p", videos=entries)
        _, stats = _copy_online_assets(m, self.media_dir, self.out_dir)
        self.assertEqual(stats.copied_count, 1)
        self.assertEqual(stats.deduped_count, 3)

    def test_same_file_different_subdir_is_not_deduped(self):
        """The same source file appearing in video and audio tracks should be
        copied to both subdirs independently (different semantic use)."""
        src = self.src_dir / "footage.mp4"
        src.write_bytes(b"data" * 200)
        vid_entry = ManifestEntry(
            asset_id="VID-X", name="footage.mp4", asset_class=AssetClass.USER_VIDEO,
            original_path=str(src), resolved_path=str(src),
            is_cached=False, is_online=True, file_size_bytes=1000,
            duration_us=10_000_000, used_in_tracks=["V1"], clip_count=1,
        )
        aud_entry = ManifestEntry(
            asset_id="AUD-X", name="footage.mp4", asset_class=AssetClass.USER_AUDIO,
            original_path=str(src), resolved_path=str(src),
            is_cached=False, is_online=True, file_size_bytes=1000,
            duration_us=10_000_000, used_in_tracks=["A1"], clip_count=1,
        )
        m = AssetManifest(project_name="p", videos=[vid_entry], audios=[aud_entry])
        override, stats = _copy_online_assets(m, self.media_dir, self.out_dir)
        self.assertEqual(stats.copied_count, 2, "Video and audio copies are independent")
        self.assertEqual(stats.deduped_count, 0)
        self.assertNotEqual(override["VID-X"], override["AUD-X"])


# ─── _write_offline_report ────────────────────────────────────────────────────

class OfflineReportTest(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.out = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def _manifest_with_offline(self) -> AssetManifest:
        src_dir = self.out / "src"
        src_dir.mkdir()
        m = _make_manifest(
            src_dir,
            with_offline_user=True,
            with_offline_capcut=True,
        )
        return m

    def test_offline_report_created(self):
        m = self._manifest_with_offline()
        report = self.out / "test.offline.md"
        _write_offline_report(m, report, "test")
        self.assertTrue(report.exists())

    def test_offline_report_has_project_name(self):
        m = self._manifest_with_offline()
        report = self.out / "test.offline.md"
        _write_offline_report(m, report, "test")
        content = report.read_text(encoding="utf-8")
        self.assertIn("test", content)

    def test_user_offline_in_user_section(self):
        m = self._manifest_with_offline()
        report = self.out / "test.offline.md"
        _write_offline_report(m, report, "test")
        content = report.read_text(encoding="utf-8")
        self.assertIn("lost_clip.mp4", content)
        self.assertIn("User media", content)

    def test_capcut_offline_in_capcut_section(self):
        m = self._manifest_with_offline()
        report = self.out / "test.offline.md"
        _write_offline_report(m, report, "test")
        content = report.read_text(encoding="utf-8")
        self.assertIn("CoolSticker", content)
        self.assertIn("CapCut assets", content)

    def test_no_user_section_when_only_capcut_offline(self):
        src_dir = self.out / "src"
        src_dir.mkdir()
        m = _make_manifest(src_dir, with_offline_capcut=True)
        report = self.out / "test.offline.md"
        _write_offline_report(m, report, "test")
        content = report.read_text(encoding="utf-8")
        self.assertNotIn("User media", content)


# ─── XML path rewrite via path_override ───────────────────────────────────────

class XMLPathOverrideTest(unittest.TestCase):
    """Verify that write_fcp7_xml honours path_override."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.out = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_path_override_appears_in_xml_pathurl(self):
        from cutsmith.reader import read_draft
        from cutsmith.writer import write_fcp7_xml
        import xml.etree.ElementTree as ET

        # Use the mock_draft_content fixture — it has known asset IDs.
        fixture = Path(__file__).parent / "fixtures" / "mock_draft_content.json"
        timeline = read_draft(fixture)

        # Pick the first asset and override its path.
        asset_id, asset = next(iter(timeline.assets.items()))
        fake_collected = self.out / "media" / "video" / "collected.mp4"
        fake_collected.parent.mkdir(parents=True, exist_ok=True)
        fake_collected.write_bytes(b"fake")

        xml_path = self.out / "test.xml"
        write_fcp7_xml(timeline, xml_path,
                       path_override={asset_id: str(fake_collected)})

        tree = ET.parse(xml_path)
        pathuris = [el.text for el in tree.findall(".//pathurl") if el.text]
        self.assertTrue(
            any("collected.mp4" in u for u in pathuris),
            f"Expected 'collected.mp4' in XML pathuris: {pathuris}",
        )

    def test_non_overridden_assets_keep_original_url(self):
        from cutsmith.reader import read_draft
        from cutsmith.writer import write_fcp7_xml
        import xml.etree.ElementTree as ET

        fixture = Path(__file__).parent / "fixtures" / "mock_draft_content.json"
        timeline = read_draft(fixture)

        xml_path = self.out / "test.xml"
        # Pass empty override — all assets keep original (OFFLINE) URLs.
        write_fcp7_xml(timeline, xml_path, path_override={})

        tree = ET.parse(xml_path)
        pathuris = [el.text for el in tree.findall(".//pathurl") if el.text]
        # Mock fixture has no real paths, so all should be OFFLINE placeholders.
        self.assertTrue(all("OFFLINE" in u or u.startswith("file://") for u in pathuris))


# ─── full collect() integration ───────────────────────────────────────────────

class CollectIntegrationTest(unittest.TestCase):
    """Run collect() end-to-end on the mock_collect_draft.json fixture.

    The fixture has placeholder paths (__PLACEHOLDER_*__). We patch the
    manifest's resolved_paths by subclassing scan_assets to inject real
    temp files, OR we use a monkeypatched fixture JSON.
    """

    def setUp(self):
        self._src_tmp = tempfile.TemporaryDirectory()
        self._out_tmp = tempfile.TemporaryDirectory()
        self.src_dir = Path(self._src_tmp.name)
        self.out_dir = Path(self._out_tmp.name)

        # Create real source files to copy.
        self.video_a = self.src_dir / "clip_a.mp4"; self.video_a.write_bytes(b"video_a" * 100)
        self.video_b = self.src_dir / "clip_b.mp4"; self.video_b.write_bytes(b"video_b" * 100)
        self.music   = self.src_dir / "bgm.mp3";    self.music.write_bytes(b"music" * 100)
        self.sfx     = self.src_dir / "sfx.mp3";    self.sfx.write_bytes(b"sfx" * 100)
        self.audio   = self.src_dir / "voice.mp3";  self.audio.write_bytes(b"voice" * 100)

        # Write a patched fixture JSON with real paths.
        with FIXTURE_COLLECT.open("r", encoding="utf-8") as f:
            raw = f.read()
        raw = (raw
               .replace("__PLACEHOLDER_VIDEO_A__", str(self.video_a))
               .replace("__PLACEHOLDER_VIDEO_B__", str(self.video_b))
               .replace("__PLACEHOLDER_MUSIC__", str(self.music))
               .replace("__PLACEHOLDER_SFX__", str(self.sfx))
               .replace("__PLACEHOLDER_AUDIO__", str(self.audio)))
        self.patched_fixture = self.src_dir / "draft_info.json"
        self.patched_fixture.write_text(raw, encoding="utf-8")

    def tearDown(self):
        self._src_tmp.cleanup()
        self._out_tmp.cleanup()

    def _run_collect(self):
        from cutsmith.collector import collect
        return collect(
            project_path=self.patched_fixture,
            out_dir=self.out_dir,
            search_roots=[str(self.src_dir)],
        )

    def test_xml_written(self):
        r = self._run_collect()
        self.assertTrue(r.xml_path.exists())

    def test_report_written(self):
        r = self._run_collect()
        self.assertTrue(r.report_path.exists())

    def test_manifest_json_written(self):
        r = self._run_collect()
        self.assertTrue(r.manifest_path.exists())

    def test_manifest_json_valid(self):
        r = self._run_collect()
        data = json.loads(r.manifest_path.read_text(encoding="utf-8"))
        self.assertIn("schema_version", data)
        self.assertIn("stats", data)

    def test_video_copied_to_media_video(self):
        self._run_collect()
        video_dir = self.out_dir / "media" / "video"
        self.assertTrue(video_dir.exists())
        self.assertGreater(len(list(video_dir.iterdir())), 0)

    def test_music_copied_to_media_music(self):
        self._run_collect()
        music_dir = self.out_dir / "media" / "music"
        self.assertTrue(music_dir.exists())
        self.assertGreater(len(list(music_dir.iterdir())), 0)

    def test_sfx_copied_to_media_sfx(self):
        self._run_collect()
        sfx_dir = self.out_dir / "media" / "sfx"
        self.assertTrue(sfx_dir.exists())
        self.assertGreater(len(list(sfx_dir.iterdir())), 0)

    def test_effect_not_in_media_dir(self):
        self._run_collect()
        # No media/effect/ or media/video_effect/ directory should exist.
        for child in (self.out_dir / "media").iterdir():
            self.assertNotIn("effect", child.name.lower())

    def test_offline_report_created_for_offline_sticker(self):
        r = self._run_collect()
        # The fixture has a sticker with /nonexistent path → offline
        self.assertIsNotNone(r.offline_report_path)
        self.assertTrue(r.offline_report_path.exists())

    def test_xml_uses_collected_path_for_online_assets(self):
        import xml.etree.ElementTree as ET
        self._run_collect()
        xml_file = next(self.out_dir.glob("*.xml"))
        tree = ET.parse(xml_file)
        pathuris = [el.text for el in tree.findall(".//pathurl") if el.text]
        # At least one pathurl should point into our out_dir/media/
        collected_urls = [u for u in pathuris if "media" in u]
        self.assertGreater(len(collected_urls), 0,
                           f"Expected collected paths in XML; got: {pathuris}")

    def test_report_contains_collect_section(self):
        r = self._run_collect()
        content = r.report_path.read_text(encoding="utf-8")
        self.assertIn("Collect package", content)

    def test_report_contains_licensing_note(self):
        r = self._run_collect()
        content = r.report_path.read_text(encoding="utf-8")
        self.assertIn("licensing", content.lower())

    def test_stats_copied_count_positive(self):
        r = self._run_collect()
        self.assertGreater(r.stats.copied_count, 0)

    def test_collect_relative_path_in_manifest(self):
        r = self._run_collect()
        data = json.loads(r.manifest_path.read_text(encoding="utf-8"))
        # At least one video should have a collect_relative_path
        videos = data.get("videos", [])
        collected = [v for v in videos if v.get("collect_relative_path")]
        self.assertGreater(len(collected), 0)

    def test_report_only_not_copied(self):
        r = self._run_collect()
        self.assertGreater(r.stats.skipped_report_only_count, 0)


# ─── extension normalization ──────────────────────────────────────────────────

# Shared magic byte constants (duplicated from test_filetype for isolation).
_PNG_MAGIC  = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
_M4A_MAGIC  = b"\x00\x00\x00\x1cftyp" b"M4A " b"\x00\x00\x02\x00" b"isom" + b"\x00" * 100
_MP3_MAGIC  = b"ID3\x04\x00\x00\x00\x00\x00\x00" + b"\x00" * 100


class ExtensionNormalizationCopyTest(unittest.TestCase):
    """Regression tests for cache extension normalization in _copy_online_assets."""

    def setUp(self):
        self._src = tempfile.TemporaryDirectory()
        self._out = tempfile.TemporaryDirectory()
        self.src_dir = Path(self._src.name)
        self.out_dir = Path(self._out.name)
        self.media_dir = self.out_dir / "media"

    def tearDown(self):
        self._src.cleanup()
        self._out.cleanup()

    def _single_entry_manifest(
        self,
        filename: str,
        content: bytes,
        asset_class: AssetClass = AssetClass.CAPCUT_MUSIC,
        asset_id: str = "TEST-001",
    ) -> AssetManifest:
        src = self.src_dir / filename
        src.write_bytes(content)
        entry = ManifestEntry(
            asset_id=asset_id,
            name=filename,
            asset_class=asset_class,
            original_path=str(src),
            resolved_path=str(src),
            is_cached=True,
            is_online=True,
            file_size_bytes=len(content),
            duration_us=1_000_000,
            used_in_tracks=["A1"],
            clip_count=1,
        )
        m = AssetManifest(
            project_name="norm_test",
            music=[entry] if asset_class == AssetClass.CAPCUT_MUSIC else [],
            images=[entry] if asset_class == AssetClass.USER_IMAGE else [],
        )
        return m

    # ── extensionless PNG cache file → copied as .png ─────────────────────────

    def test_extensionless_png_copied_as_png(self):
        """Cache image with no extension and PNG magic bytes → dest gets .png."""
        m = self._single_entry_manifest(
            "0a1a1d8f92a53cb1ea79944e5d28cfa0", _PNG_MAGIC,
            asset_class=AssetClass.USER_IMAGE,
        )
        _copy_online_assets(m, self.media_dir, self.out_dir)
        images = list((self.media_dir / "images").iterdir())
        self.assertEqual(len(images), 1)
        self.assertEqual(images[0].suffix, ".png")

    def test_extensionless_png_manifest_entry_normalized(self):
        m = self._single_entry_manifest(
            "0a1a1d8f92a53cb1ea79944e5d28cfa0", _PNG_MAGIC,
            asset_class=AssetClass.USER_IMAGE,
        )
        _copy_online_assets(m, self.media_dir, self.out_dir)
        entry = m.images[0]
        self.assertTrue(entry.extension_normalized)
        self.assertEqual(entry.original_extension, None)  # "" → None (no suffix)
        self.assertEqual(entry.detected_extension, ".png")

    # ── .mp3 path with M4A ftyp content → copied as .m4a ────────────────────

    def test_mp3_with_m4a_content_copied_as_m4a(self):
        """CapCut cache music with .mp3 extension but M4A ftyp content → .m4a."""
        m = self._single_entry_manifest(
            "5a24a7e2eb1672953b926de5b8429eb6.mp3", _M4A_MAGIC,
        )
        _copy_online_assets(m, self.media_dir, self.out_dir)
        music_files = list((self.media_dir / "music").iterdir())
        self.assertEqual(len(music_files), 1)
        self.assertEqual(music_files[0].suffix, ".m4a")

    def test_mp3_with_m4a_content_manifest_records_normalization(self):
        m = self._single_entry_manifest(
            "5a24a7e2eb1672953b926de5b8429eb6.mp3", _M4A_MAGIC,
        )
        _copy_online_assets(m, self.media_dir, self.out_dir)
        entry = m.music[0]
        self.assertTrue(entry.extension_normalized)
        self.assertEqual(entry.original_extension, ".mp3")
        self.assertEqual(entry.detected_extension, ".m4a")

    def test_mp3_with_m4a_content_path_override_uses_m4a(self):
        """path_override must point at the .m4a file so the XML uses the right path."""
        m = self._single_entry_manifest(
            "cache_track.mp3", _M4A_MAGIC, asset_id="MUSIC-001",
        )
        override, _ = _copy_online_assets(m, self.media_dir, self.out_dir)
        self.assertIn("MUSIC-001", override)
        self.assertTrue(override["MUSIC-001"].endswith(".m4a"),
                        f"Expected .m4a in path_override; got {override['MUSIC-001']}")

    # ── real .mp3 stays .mp3 ─────────────────────────────────────────────────

    def test_real_mp3_stays_mp3(self):
        """A file with .mp3 extension and genuine ID3 content must not be renamed."""
        m = self._single_entry_manifest("bgm.mp3", _MP3_MAGIC)
        _copy_online_assets(m, self.media_dir, self.out_dir)
        music_files = list((self.media_dir / "music").iterdir())
        self.assertEqual(len(music_files), 1)
        self.assertEqual(music_files[0].name, "bgm.mp3")

    def test_real_mp3_manifest_not_normalized(self):
        m = self._single_entry_manifest("bgm.mp3", _MP3_MAGIC)
        _copy_online_assets(m, self.media_dir, self.out_dir)
        entry = m.music[0]
        self.assertFalse(entry.extension_normalized)

    # ── stats ─────────────────────────────────────────────────────────────────

    def test_stats_normalized_count(self):
        """extension_normalized_count increments for each corrected file."""
        # One M4A-as-mp3 → count = 1
        m = self._single_entry_manifest("fake.mp3", _M4A_MAGIC)
        _, stats = _copy_online_assets(m, self.media_dir, self.out_dir)
        self.assertEqual(stats.extension_normalized_count, 1)

    def test_stats_normalized_count_zero_for_correct_extension(self):
        m = self._single_entry_manifest("real.mp3", _MP3_MAGIC)
        _, stats = _copy_online_assets(m, self.media_dir, self.out_dir)
        self.assertEqual(stats.extension_normalized_count, 0)

    # ── collision still works after normalization ─────────────────────────────

    def test_collision_after_normalization(self):
        """Two .mp3 files with M4A content that both normalize to the same stem
        must be disambiguated in media/music/."""
        src_a = self.src_dir / "track.mp3"
        src_b = (self.src_dir / "sub"); src_b.mkdir()
        src_b = src_b / "track.mp3"
        src_a.write_bytes(_M4A_MAGIC)
        src_b.write_bytes(_M4A_MAGIC)

        entry_a = ManifestEntry(
            asset_id="MUS-A", name="track.mp3", asset_class=AssetClass.CAPCUT_MUSIC,
            original_path=str(src_a), resolved_path=str(src_a),
            is_cached=True, is_online=True, file_size_bytes=len(_M4A_MAGIC),
            duration_us=1_000_000, used_in_tracks=["A1"], clip_count=1,
        )
        entry_b = ManifestEntry(
            asset_id="MUS-B", name="track.mp3", asset_class=AssetClass.CAPCUT_MUSIC,
            original_path=str(src_b), resolved_path=str(src_b),
            is_cached=True, is_online=True, file_size_bytes=len(_M4A_MAGIC),
            duration_us=1_000_000, used_in_tracks=["A2"], clip_count=1,
        )
        m = AssetManifest(project_name="p", music=[entry_a, entry_b])
        _copy_online_assets(m, self.media_dir, self.out_dir)

        music_files = list((self.media_dir / "music").iterdir())
        self.assertEqual(len(music_files), 2)
        names = {f.name for f in music_files}
        # Both files must have .m4a extension.
        self.assertTrue(all(n.endswith(".m4a") for n in names),
                        f"Expected all .m4a files; got {names}")
        # One is the canonical name, the other is disambiguated.
        self.assertIn("track.m4a", names)
        non_canonical = [n for n in names if n != "track.m4a"]
        self.assertEqual(len(non_canonical), 1)
        # Disambiguated name contains the asset_id prefix.
        self.assertIn("MUS-B"[:8], non_canonical[0])

    # ── XML uses normalized path ──────────────────────────────────────────────

    def test_xml_pathurl_uses_normalized_extension(self):
        """When a .mp3 file is normalised to .m4a, the XML <pathurl> must
        reference the .m4a file, not the original .mp3 path."""
        import xml.etree.ElementTree as ET
        from cutsmith.reader import read_draft
        from cutsmith.writer import write_fcp7_xml

        fixture = Path(__file__).parent / "fixtures" / "mock_draft_content.json"
        timeline = read_draft(fixture)

        # Pick the first asset and set it up with a fake .mp3 file that is
        # actually M4A, injecting it into path_override via _copy_online_assets.
        asset_id, asset = next(iter(timeline.assets.items()))

        fake_src = self.src_dir / "from_cache.mp3"
        fake_src.write_bytes(_M4A_MAGIC)

        entry = ManifestEntry(
            asset_id=asset_id, name="from_cache.mp3",
            asset_class=AssetClass.CAPCUT_MUSIC,
            original_path=str(fake_src), resolved_path=str(fake_src),
            is_cached=True, is_online=True, file_size_bytes=len(_M4A_MAGIC),
            duration_us=1_000_000, used_in_tracks=["A1"], clip_count=1,
        )
        m = AssetManifest(project_name="p", music=[entry])
        override, _ = _copy_online_assets(m, self.media_dir, self.out_dir)

        xml_path = self.out_dir / "test.xml"
        write_fcp7_xml(timeline, xml_path, path_override=override)

        tree = ET.parse(xml_path)
        pathuris = [el.text for el in tree.findall(".//pathurl") if el.text]
        self.assertTrue(
            any(u.endswith(".m4a") for u in pathuris),
            f"Expected a .m4a pathurl; got {pathuris}",
        )


# ─── _write_relink_guide ──────────────────────────────────────────────────────

class RelinkGuideTest(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.out = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def _guide_content(self, *, offline: bool = False, normalized: int = 0) -> str:
        src_dir = self.out / "src"
        src_dir.mkdir(exist_ok=True)
        m = _make_manifest(src_dir, with_offline_user=offline)
        m.relink_root_hint = str(self.out / "media")
        m.package_portable = "partial" if offline else "full"
        stats = CollectStats(
            extension_normalized_count=normalized,
            offline_count=1 if offline else 0,
        )
        guide = self.out / "proj.relink_guide.md"
        _write_relink_guide(m, stats, guide, "proj")
        return guide.read_text(encoding="utf-8")

    def test_relink_guide_created(self):
        src_dir = self.out / "src"
        src_dir.mkdir()
        m = _make_manifest(src_dir)
        m.relink_root_hint = str(self.out / "media")
        m.package_portable = "full"
        guide = self.out / "proj.relink_guide.md"
        _write_relink_guide(m, CollectStats(), guide, "proj")
        self.assertTrue(guide.exists())

    def test_guide_contains_stem_name(self):
        content = self._guide_content()
        self.assertIn("proj", content)

    def test_guide_contains_media_root_hint(self):
        content = self._guide_content()
        self.assertIn(str(self.out / "media"), content)

    def test_guide_mentions_link_media(self):
        content = self._guide_content()
        self.assertIn("Link Media", content)

    def test_guide_full_package_says_automatic(self):
        content = self._guide_content(offline=False)
        self.assertIn("link automatically", content)

    def test_guide_partial_package_mentions_offline(self):
        content = self._guide_content(offline=True)
        self.assertIn("Offline", content)

    def test_guide_mentions_speed_trim_boundary(self):
        content = self._guide_content()
        self.assertIn("trim", content.lower())
        self.assertIn("wavy", content.lower())

    def test_guide_mentions_proprietary_not_portable(self):
        content = self._guide_content()
        self.assertIn("not portable", content)

    def test_guide_extension_section_present_when_normalized(self):
        content = self._guide_content(normalized=2)
        self.assertIn("Extension normalization", content)

    def test_guide_extension_section_absent_when_zero(self):
        content = self._guide_content(normalized=0)
        self.assertNotIn("Extension normalization", content)


# ─── manifest new fields (v0.3.4) ────────────────────────────────────────────

class ManifestV034FieldsTest(unittest.TestCase):
    """Verify AssetManifest carries the new v0.3.4 collector fields."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.out = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def _minimal_manifest(self) -> AssetManifest:
        return AssetManifest(project_name="test", source_draft="/tmp/draft.json")

    def test_default_path_mode_is_original(self):
        m = self._minimal_manifest()
        self.assertEqual(m.path_mode, "original")

    def test_default_package_portable_is_unknown(self):
        m = self._minimal_manifest()
        self.assertEqual(m.package_portable, "unknown")

    def test_default_collected_root_is_none(self):
        m = self._minimal_manifest()
        self.assertIsNone(m.collected_root)

    def test_default_relink_root_hint_is_none(self):
        m = self._minimal_manifest()
        self.assertIsNone(m.relink_root_hint)

    def test_to_dict_contains_collected_root(self):
        m = self._minimal_manifest()
        m.collected_root = "/some/out"
        d = m.to_dict()
        self.assertIn("collected_root", d)
        self.assertEqual(d["collected_root"], "/some/out")

    def test_to_dict_contains_relink_root_hint(self):
        m = self._minimal_manifest()
        m.relink_root_hint = "/some/out/media"
        d = m.to_dict()
        self.assertIn("relink_root_hint", d)
        self.assertEqual(d["relink_root_hint"], "/some/out/media")

    def test_to_dict_contains_path_mode(self):
        m = self._minimal_manifest()
        m.path_mode = "collected_absolute"
        d = m.to_dict()
        self.assertEqual(d["path_mode"], "collected_absolute")

    def test_to_dict_contains_package_portable(self):
        m = self._minimal_manifest()
        m.package_portable = "full"
        d = m.to_dict()
        self.assertEqual(d["package_portable"], "full")

    def test_to_dict_stats_contains_report_only_count(self):
        m = self._minimal_manifest()
        m.report_only_count = 5
        d = m.to_dict()
        self.assertIn("report_only_count", d["stats"])
        self.assertEqual(d["stats"]["report_only_count"], 5)

    def test_to_dict_stats_contains_normalized_extension_count(self):
        m = self._minimal_manifest()
        m.normalized_extension_count = 3
        d = m.to_dict()
        self.assertIn("normalized_extension_count", d["stats"])
        self.assertEqual(d["stats"]["normalized_extension_count"], 3)


# ─── CollectIntegration v0.3.4 additions ─────────────────────────────────────

class CollectIntegrationV034Test(unittest.TestCase):
    """Verify v0.3.4 additions in the full collect() pipeline."""

    def setUp(self):
        self._src_tmp = tempfile.TemporaryDirectory()
        self._out_tmp = tempfile.TemporaryDirectory()
        self.src_dir = Path(self._src_tmp.name)
        self.out_dir = Path(self._out_tmp.name)

        self.video_a = self.src_dir / "clip_a.mp4"; self.video_a.write_bytes(b"video_a" * 100)
        self.video_b = self.src_dir / "clip_b.mp4"; self.video_b.write_bytes(b"video_b" * 100)
        self.music   = self.src_dir / "bgm.mp3";    self.music.write_bytes(b"music" * 100)
        self.sfx     = self.src_dir / "sfx.mp3";    self.sfx.write_bytes(b"sfx" * 100)
        self.audio   = self.src_dir / "voice.mp3";  self.audio.write_bytes(b"voice" * 100)

        with FIXTURE_COLLECT.open("r", encoding="utf-8") as f:
            raw = f.read()
        raw = (raw
               .replace("__PLACEHOLDER_VIDEO_A__", str(self.video_a))
               .replace("__PLACEHOLDER_VIDEO_B__", str(self.video_b))
               .replace("__PLACEHOLDER_MUSIC__", str(self.music))
               .replace("__PLACEHOLDER_SFX__", str(self.sfx))
               .replace("__PLACEHOLDER_AUDIO__", str(self.audio)))
        self.patched_fixture = self.src_dir / "draft_info.json"
        self.patched_fixture.write_text(raw, encoding="utf-8")

    def tearDown(self):
        self._src_tmp.cleanup()
        self._out_tmp.cleanup()

    def _run_collect(self):
        from cutsmith.collector import collect
        return collect(
            project_path=self.patched_fixture,
            out_dir=self.out_dir,
            search_roots=[str(self.src_dir)],
        )

    def test_relink_guide_written(self):
        r = self._run_collect()
        self.assertIsNotNone(r.relink_guide_path)
        self.assertTrue(r.relink_guide_path.exists())

    def test_relink_guide_in_written_files(self):
        r = self._run_collect()
        self.assertIn(r.relink_guide_path, r.written_files)

    def test_relink_guide_contains_media_root(self):
        r = self._run_collect()
        content = r.relink_guide_path.read_text(encoding="utf-8")
        expected_media = str(self.out_dir / "media")
        self.assertIn(expected_media, content)

    def test_manifest_has_collected_root(self):
        r = self._run_collect()
        data = json.loads(r.manifest_path.read_text(encoding="utf-8"))
        self.assertIn("collected_root", data)
        self.assertIsNotNone(data["collected_root"])

    def test_manifest_has_relink_root_hint(self):
        r = self._run_collect()
        data = json.loads(r.manifest_path.read_text(encoding="utf-8"))
        self.assertIn("relink_root_hint", data)
        self.assertIn("media", data["relink_root_hint"])

    def test_manifest_path_mode_is_collected_absolute(self):
        r = self._run_collect()
        data = json.loads(r.manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(data["path_mode"], "collected_absolute")

    def test_manifest_stats_has_report_only_count(self):
        r = self._run_collect()
        data = json.loads(r.manifest_path.read_text(encoding="utf-8"))
        self.assertIn("report_only_count", data["stats"])
        self.assertGreater(data["stats"]["report_only_count"], 0)

    def test_xml_master_clip_pathurls_point_to_media_dir(self):
        """All master clip <pathurl>s must reference the collected media/ directory."""
        import xml.etree.ElementTree as ET
        r = self._run_collect()
        tree = ET.parse(r.xml_path)
        # Pathurls in the master clips (direct <clip> children of <xmeml>)
        xmeml = tree.getroot()
        master_clip_files = xmeml.findall("clip/file/pathurl")
        collected_media = str(self.out_dir / "media")
        for el in master_clip_files:
            url = el.text or ""
            if "OFFLINE" in url:
                continue  # skip assets that were offline
            self.assertIn("media", url,
                          f"Master clip pathurl not pointing to collected media: {url}")

    def test_report_only_assets_not_in_xml_pathuris(self):
        """Effects/transitions/filters must not appear as XML pathurls."""
        import xml.etree.ElementTree as ET
        r = self._run_collect()
        tree = ET.parse(r.xml_path)
        pathuris = [el.text or "" for el in tree.findall(".//pathurl")]
        for url in pathuris:
            # No pathurl should point into a CapCut effect cache
            self.assertNotIn("capcut_effect", url.lower())

    def test_report_speed_text_updated(self):
        r = self._run_collect()
        content = r.report_path.read_text(encoding="utf-8")
        self.assertIn("timeremap", content)
        # Old misleading text must be gone
        self.assertNotIn("shows clips at 100% speed", content)


# ─── _count_media_subdirs ─────────────────────────────────────────────────────

class CountMediaSubdirsTest(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.media_dir = Path(self._tmp.name) / "media"

    def tearDown(self):
        self._tmp.cleanup()

    def test_empty_media_dir_returns_empty(self):
        self.media_dir.mkdir()
        self.assertEqual(_count_media_subdirs(self.media_dir), {})

    def test_nonexistent_media_dir_returns_empty(self):
        self.assertEqual(_count_media_subdirs(self.media_dir), {})

    def test_counts_files_per_subdir(self):
        (self.media_dir / "video").mkdir(parents=True)
        (self.media_dir / "video" / "a.mp4").write_bytes(b"x")
        (self.media_dir / "video" / "b.mp4").write_bytes(b"x")
        (self.media_dir / "audio").mkdir()
        (self.media_dir / "audio" / "c.mp3").write_bytes(b"x")
        counts = _count_media_subdirs(self.media_dir)
        self.assertEqual(counts["video"], 2)
        self.assertEqual(counts["audio"], 1)

    def test_only_counts_files_not_subdirs(self):
        (self.media_dir / "video").mkdir(parents=True)
        (self.media_dir / "video" / "a.mp4").write_bytes(b"x")
        (self.media_dir / "video" / "sub").mkdir()  # subdir inside — not counted
        counts = _count_media_subdirs(self.media_dir)
        self.assertEqual(counts["video"], 1)


# ─── _write_package_summary ───────────────────────────────────────────────────

class PackageSummaryTest(unittest.TestCase):

    def setUp(self):
        self._src_tmp = tempfile.TemporaryDirectory()
        self._out_tmp = tempfile.TemporaryDirectory()
        self.src_dir = Path(self._src_tmp.name)
        self.out_dir = Path(self._out_tmp.name)
        self.media_dir = self.out_dir / "media"

    def tearDown(self):
        self._src_tmp.cleanup()
        self._out_tmp.cleanup()

    def _run_and_read(self, *, offline: bool = False, normalized: int = 0) -> str:
        m = _make_manifest(self.src_dir, with_offline_user=offline)
        m.collected_root = str(self.out_dir.resolve())
        m.relink_root_hint = str(self.media_dir.resolve())
        m.project_name = "test_proj"

        # Create a fake media/video directory with one file for subdir counts.
        (self.media_dir / "video").mkdir(parents=True, exist_ok=True)
        (self.media_dir / "video" / "clip.mp4").write_bytes(b"x" * 100)

        stats = CollectStats(
            copied_count=3,
            offline_count=1 if offline else 0,
            skipped_report_only_count=2,
            total_copied_size_bytes=7_340_032,
            extension_normalized_count=normalized,
        )

        if normalized:
            # Inject a normalized entry for the pairs line.
            from cutsmith.scanner.manifest import ManifestEntry
            e = ManifestEntry(
                asset_id="MUS-X", name="track.mp3", asset_class=AssetClass.CAPCUT_MUSIC,
                original_path=str(self.src_dir / "track.mp3"),
                resolved_path=str(self.src_dir / "track.mp3"),
                is_cached=True, is_online=True, file_size_bytes=100,
                duration_us=1_000_000, used_in_tracks=["A1"], clip_count=1,
                extension_normalized=True,
                original_extension=".mp3",
                detected_extension=".m4a",
                collect_relative_path="media/music/track.m4a",
            )
            m.music.append(e)

        summary_path = self.out_dir / "test_proj.package_summary.txt"
        _write_package_summary(m, stats, self.media_dir, "test_proj", summary_path)
        return summary_path.read_text(encoding="utf-8")

    def test_summary_file_created(self):
        m = _make_manifest(self.src_dir)
        m.collected_root = str(self.out_dir.resolve())
        m.relink_root_hint = str(self.media_dir.resolve())
        summary_path = self.out_dir / "proj.package_summary.txt"
        _write_package_summary(m, CollectStats(), self.media_dir, "proj", summary_path)
        self.assertTrue(summary_path.exists())

    def test_summary_has_project_name(self):
        content = self._run_and_read()
        self.assertIn("test_proj", content)

    def test_summary_has_package_root(self):
        content = self._run_and_read()
        self.assertIn(str(self.out_dir.resolve()), content)

    def test_summary_has_relink_root(self):
        content = self._run_and_read()
        self.assertIn(str(self.media_dir.resolve()), content)

    def test_summary_has_copied_count(self):
        content = self._run_and_read()
        self.assertIn("3 file", content)

    def test_summary_has_size(self):
        content = self._run_and_read()
        self.assertIn("7.0 MB", content)

    def test_summary_lists_subdir_counts(self):
        content = self._run_and_read()
        self.assertIn("video/", content)
        self.assertIn("1 file", content)  # the one fake clip.mp4

    def test_summary_offline_none_message_when_zero(self):
        content = self._run_and_read(offline=False)
        self.assertIn("none — package is fully self-contained", content)

    def test_summary_offline_count_when_present(self):
        content = self._run_and_read(offline=True)
        self.assertIn("offline.md", content)

    def test_summary_report_only_count(self):
        content = self._run_and_read()
        self.assertIn("2", content)
        self.assertIn("effects", content)

    def test_summary_normalized_section_present(self):
        content = self._run_and_read(normalized=1)
        self.assertIn("Normalized extensions", content)
        self.assertIn(".mp3 → .m4a", content)

    def test_summary_normalized_section_absent_when_zero(self):
        content = self._run_and_read(normalized=0)
        self.assertNotIn("Normalized extensions", content)

    def test_summary_has_premiere_import_instructions(self):
        content = self._run_and_read()
        self.assertIn("File → Import", content)

    def test_summary_has_known_limitations(self):
        content = self._run_and_read()
        self.assertIn("Known limitations", content)
        self.assertIn("speed", content.lower())


# ─── collect() integration — v0.3.5 package_summary ─────────────────────────

class CollectIntegrationV035Test(unittest.TestCase):
    """Verify package_summary.txt in the full collect() integration."""

    def setUp(self):
        self._src_tmp = tempfile.TemporaryDirectory()
        self._out_tmp = tempfile.TemporaryDirectory()
        self.src_dir = Path(self._src_tmp.name)
        self.out_dir = Path(self._out_tmp.name)

        self.video_a = self.src_dir / "clip_a.mp4"; self.video_a.write_bytes(b"video_a" * 100)
        self.video_b = self.src_dir / "clip_b.mp4"; self.video_b.write_bytes(b"video_b" * 100)
        self.music   = self.src_dir / "bgm.mp3";    self.music.write_bytes(b"music" * 100)
        self.sfx     = self.src_dir / "sfx.mp3";    self.sfx.write_bytes(b"sfx" * 100)
        self.audio   = self.src_dir / "voice.mp3";  self.audio.write_bytes(b"voice" * 100)

        with FIXTURE_COLLECT.open("r", encoding="utf-8") as f:
            raw = f.read()
        raw = (raw
               .replace("__PLACEHOLDER_VIDEO_A__", str(self.video_a))
               .replace("__PLACEHOLDER_VIDEO_B__", str(self.video_b))
               .replace("__PLACEHOLDER_MUSIC__", str(self.music))
               .replace("__PLACEHOLDER_SFX__", str(self.sfx))
               .replace("__PLACEHOLDER_AUDIO__", str(self.audio)))
        self.patched_fixture = self.src_dir / "draft_info.json"
        self.patched_fixture.write_text(raw, encoding="utf-8")

    def tearDown(self):
        self._src_tmp.cleanup()
        self._out_tmp.cleanup()

    def _run_collect(self):
        from cutsmith.collector import collect
        return collect(
            project_path=self.patched_fixture,
            out_dir=self.out_dir,
            search_roots=[str(self.src_dir)],
        )

    def test_package_summary_written(self):
        r = self._run_collect()
        self.assertIsNotNone(r.package_summary_path)
        self.assertTrue(r.package_summary_path.exists())

    def test_package_summary_in_written_files(self):
        r = self._run_collect()
        self.assertIn(r.package_summary_path, r.written_files)

    def test_package_summary_has_absolute_paths(self):
        r = self._run_collect()
        content = r.package_summary_path.read_text(encoding="utf-8")
        self.assertIn(str(self.out_dir.resolve()), content)

    def test_package_summary_has_video_subdir_count(self):
        r = self._run_collect()
        content = r.package_summary_path.read_text(encoding="utf-8")
        self.assertIn("video/", content)

    def test_package_summary_copied_count_matches_stats(self):
        r = self._run_collect()
        content = r.package_summary_path.read_text(encoding="utf-8")
        self.assertIn(str(r.stats.copied_count), content)
