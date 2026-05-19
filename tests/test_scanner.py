"""Tests for cutsmith.scanner — asset classification and manifest assembly."""

from __future__ import annotations

import unittest
from pathlib import Path

from cutsmith.ir import AssetClass, MediaAsset, MediaKind
from cutsmith.scanner import scan_assets
from cutsmith.scanner.classify import (
    classify_asset,
    classify_raw_material,
    expand_cache_roots,
    is_cache_path,
)

FIXTURE = Path(__file__).parent / "fixtures" / "mock_scan_draft.json"

# A cache path that matches the known CapCut cache root template
_CACHE_PATH = (
    "/Users/mac/Library/Containers/com.lemon.lvoverseas/Data/"
    "Movies/CapCut/User Data/Cache/music/cool_track.mp3"
)
_USER_PATH = "/Users/mac/Downloads/my_footage.mp4"


# ─── classify helpers ─────────────────────────────────────────────────────── #

class CachePathDetectionTest(unittest.TestCase):

    def setUp(self):
        self.roots = expand_cache_roots()

    def test_cache_path_detected(self):
        self.assertTrue(is_cache_path(_CACHE_PATH, self.roots))

    def test_user_path_not_cache(self):
        self.assertFalse(is_cache_path(_USER_PATH, self.roots))

    def test_empty_path_not_cache(self):
        self.assertFalse(is_cache_path("", self.roots))

    def test_none_safe(self):
        self.assertFalse(is_cache_path(None, self.roots))  # type: ignore[arg-type]


class AudioClassificationTest(unittest.TestCase):

    def _asset(self, cap_type: str, path: str = _USER_PATH) -> MediaAsset:
        return MediaAsset(
            asset_id="X", name="x", original_path=path, resolved_path=None,
            media_kind=MediaKind.AUDIO, duration_us=0,
            has_video=False, has_audio=True,
            extras={"capcut_type": cap_type},
        )

    def setUp(self):
        self.roots = expand_cache_roots()

    def test_music_type_is_capcut_music(self):
        asset = self._asset("music")
        self.assertEqual(classify_asset(asset, self.roots), AssetClass.CAPCUT_MUSIC)

    def test_sound_type_is_capcut_sfx(self):
        asset = self._asset("sound")
        self.assertEqual(classify_asset(asset, self.roots), AssetClass.CAPCUT_SFX)

    def test_video_original_sound_is_user_audio(self):
        asset = self._asset("video_original_sound")
        self.assertEqual(classify_asset(asset, self.roots), AssetClass.USER_AUDIO)

    def test_extract_music_is_user_audio(self):
        asset = self._asset("extract_music")
        self.assertEqual(classify_asset(asset, self.roots), AssetClass.USER_AUDIO)

    def test_cache_path_without_type_is_capcut_music(self):
        asset = self._asset("", path=_CACHE_PATH)
        self.assertEqual(classify_asset(asset, self.roots), AssetClass.CAPCUT_MUSIC)

    def test_unknown_type_non_cache_is_user_audio(self):
        asset = self._asset("custom_audio")
        self.assertEqual(classify_asset(asset, self.roots), AssetClass.USER_AUDIO)


class VideoClassificationTest(unittest.TestCase):

    def setUp(self):
        self.roots = expand_cache_roots()

    def test_video_is_user_video(self):
        asset = MediaAsset(
            asset_id="V1", name="clip.mp4", original_path="/Users/x/clip.mp4",
            resolved_path=None, media_kind=MediaKind.VIDEO, duration_us=0,
            has_video=True, has_audio=True, extras={"capcut_type": "video"},
        )
        self.assertEqual(classify_asset(asset, self.roots), AssetClass.USER_VIDEO)

    def test_image_is_user_image(self):
        asset = MediaAsset(
            asset_id="I1", name="photo.jpg", original_path="/Users/x/photo.jpg",
            resolved_path=None, media_kind=MediaKind.IMAGE, duration_us=0,
            has_video=True, has_audio=False, extras={"capcut_type": "photo"},
        )
        self.assertEqual(classify_asset(asset, self.roots), AssetClass.USER_IMAGE)


class RawMaterialClassificationTest(unittest.TestCase):

    def setUp(self):
        self.roots = expand_cache_roots()

    def test_sticker_is_capcut_sticker(self):
        mat = {"id": "S1", "name": "stk", "type": "sticker", "path": ""}
        self.assertEqual(
            classify_raw_material(mat, "stickers", self.roots),
            AssetClass.CAPCUT_STICKER,
        )

    def test_effects_type_filter_is_capcut_effect(self):
        mat = {"id": "E1", "name": "Film", "type": "filter", "path": ""}
        self.assertEqual(
            classify_raw_material(mat, "effects", self.roots),
            AssetClass.CAPCUT_EFFECT,
        )

    def test_effects_type_video_effect_is_capcut_effect(self):
        mat = {"id": "E2", "name": "Glitch", "type": "video_effect", "path": ""}
        self.assertEqual(
            classify_raw_material(mat, "effects", self.roots),
            AssetClass.CAPCUT_EFFECT,
        )

    def test_transition_is_capcut_effect(self):
        mat = {"id": "T1", "name": "Slide", "type": "transition", "path": ""}
        self.assertEqual(
            classify_raw_material(mat, "transitions", self.roots),
            AssetClass.CAPCUT_EFFECT,
        )


# ─── full scan integration ────────────────────────────────────────────────── #

class ScanAssetsIntegrationTest(unittest.TestCase):
    """Run scan_assets on the mock scan fixture and verify manifest structure."""

    def setUp(self):
        self.manifest = scan_assets(FIXTURE)

    def test_project_name_derived(self):
        # Fixture filename stem is "mock_scan_draft" (not "draft_info"),
        # so the name should come from the file stem.
        self.assertIn("mock_scan_draft", self.manifest.project_name)

    def test_one_user_video(self):
        self.assertEqual(len(self.manifest.videos), 1)
        self.assertEqual(self.manifest.videos[0].asset_class, AssetClass.USER_VIDEO)
        self.assertEqual(self.manifest.videos[0].name, "my_video.mp4")

    def test_music_classified_correctly(self):
        self.assertEqual(len(self.manifest.music), 1)
        self.assertEqual(self.manifest.music[0].asset_class, AssetClass.CAPCUT_MUSIC)
        self.assertEqual(self.manifest.music[0].name, "Cool Track")

    def test_sfx_classified_correctly(self):
        self.assertEqual(len(self.manifest.sfx), 1)
        self.assertEqual(self.manifest.sfx[0].asset_class, AssetClass.CAPCUT_SFX)
        self.assertEqual(self.manifest.sfx[0].name, "Swoosh")

    def test_embedded_audio_is_user_audio(self):
        self.assertEqual(len(self.manifest.audios), 1)
        self.assertEqual(self.manifest.audios[0].asset_class, AssetClass.USER_AUDIO)

    def test_sticker_classified(self):
        self.assertEqual(len(self.manifest.stickers), 1)
        self.assertEqual(self.manifest.stickers[0].asset_class, AssetClass.CAPCUT_STICKER)

    def test_filter_in_effects_split_correctly(self):
        # effects[type=filter] → manifest.filters
        self.assertEqual(len(self.manifest.filters), 1)
        self.assertEqual(self.manifest.filters[0].name, "Film Look")

    def test_video_effect_in_effects(self):
        # effects[type=video_effect] → manifest.effects
        self.assertEqual(len(self.manifest.effects), 1)
        self.assertEqual(self.manifest.effects[0].name, "Glitch")

    def test_transition_classified(self):
        self.assertEqual(len(self.manifest.transitions), 1)
        self.assertEqual(self.manifest.transitions[0].name, "Slide Left")

    def test_stats_counts_are_consistent(self):
        total = (len(self.manifest.videos) + len(self.manifest.audios)
                 + len(self.manifest.music) + len(self.manifest.sfx)
                 + len(self.manifest.images) + len(self.manifest.stickers)
                 + len(self.manifest.effects) + len(self.manifest.filters)
                 + len(self.manifest.transitions) + len(self.manifest.fonts))
        self.assertEqual(self.manifest.total_assets, total)

    def test_manifest_to_dict_has_required_keys(self):
        d = self.manifest.to_dict()
        for key in ("schema_version", "project_name", "stats",
                    "videos", "audios", "music", "sfx", "stickers",
                    "effects", "filters", "transitions", "offline"):
            self.assertIn(key, d)

    def test_manifest_to_json_is_valid_json(self):
        import json
        data = json.loads(self.manifest.to_json())
        self.assertIsInstance(data, dict)

    def test_text_materials_not_in_manifest(self):
        # text/text_template materials are not media — excluded from all categories
        all_names = [e.name for e in self.manifest.all_entries()]
        self.assertNotIn("caption", all_names)


class ManifestOfflineTest(unittest.TestCase):
    """Assets whose resolved_path doesn't exist should be offline."""

    def setUp(self):
        self.manifest = scan_assets(FIXTURE)

    def test_offline_cross_list_populated(self):
        # All paths in the mock fixture are fake → every path-based asset is offline
        # except for paths we happen to not resolve.
        # Just verify the offline list is a list and cross-references correctly.
        self.assertIsInstance(self.manifest.offline, list)
        offline_ids = {e.asset_id for e in self.manifest.offline}
        for entry in self.manifest.all_entries():
            if not entry.is_online:
                self.assertIn(entry.asset_id, offline_ids)

    def test_online_count_plus_offline_count_equals_total(self):
        self.assertEqual(
            self.manifest.online_count + self.manifest.offline_count,
            self.manifest.total_assets,
        )
