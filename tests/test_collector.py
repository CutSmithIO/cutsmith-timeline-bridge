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
    _unique_dest,
    _write_offline_report,
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
