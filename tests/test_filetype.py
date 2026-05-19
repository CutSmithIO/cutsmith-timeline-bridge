"""Tests for cutsmith.collector.filetype — magic-byte detection and normalization."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from cutsmith.collector.filetype import (
    FileType,
    detect_file_type,
    should_normalize_extension,
)

# ─── magic byte fixtures ──────────────────────────────────────────────────────

_PNG   = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
_JPEG  = b"\xff\xd8\xff\xe0" + b"\x00" * 100
_GIF   = b"GIF89a" + b"\x00" * 100
_WEBP  = b"RIFF\x00\x00\x00\x00WEBP" + b"\x00" * 100
_WAV   = b"RIFF\x00\x00\x00\x00WAVE" + b"\x00" * 100
_M4A   = b"\x00\x00\x00\x1cftyp" b"M4A " b"\x00\x00\x02\x00" b"isom" + b"\x00" * 100
_MP4   = b"\x00\x00\x00\x1cftyp" b"isom" b"\x00\x00\x00\x00" b"mp42" + b"\x00" * 100
_MP3_ID3   = b"ID3\x04\x00\x00\x00\x00\x00\x00" + b"\x00" * 100
_MP3_SYNC  = b"\xff\xfb\x90\x00" + b"\x00" * 100
_UNKNOWN   = b"\x00\x01\x02\x03\x04\x05\x06\x07" + b"\x00" * 100


def _write(tmp: Path, name: str, content: bytes) -> Path:
    p = tmp / name
    p.write_bytes(content)
    return p


# ─── detect_file_type ────────────────────────────────────────────────────────

class DetectFileTypeTest(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def _detect(self, name: str, content: bytes) -> FileType | None:
        return detect_file_type(_write(self.tmp, name, content))

    def test_detects_png(self):
        ft = self._detect("img", _PNG)
        self.assertIsNotNone(ft)
        self.assertEqual(ft.ext, ".png")
        self.assertEqual(ft.mime, "image/png")

    def test_detects_jpeg(self):
        ft = self._detect("img", _JPEG)
        self.assertIsNotNone(ft)
        self.assertEqual(ft.ext, ".jpg")

    def test_detects_gif(self):
        ft = self._detect("img", _GIF)
        self.assertIsNotNone(ft)
        self.assertEqual(ft.ext, ".gif")

    def test_detects_webp(self):
        ft = self._detect("img", _WEBP)
        self.assertIsNotNone(ft)
        self.assertEqual(ft.ext, ".webp")

    def test_detects_wav(self):
        ft = self._detect("snd", _WAV)
        self.assertIsNotNone(ft)
        self.assertEqual(ft.ext, ".wav")

    def test_detects_m4a_from_ftyp_brand(self):
        ft = self._detect("track", _M4A)
        self.assertIsNotNone(ft)
        self.assertEqual(ft.ext, ".m4a")
        self.assertEqual(ft.mime, "audio/mp4")

    def test_detects_mp4_from_ftyp_isom(self):
        ft = self._detect("vid", _MP4)
        self.assertIsNotNone(ft)
        self.assertEqual(ft.ext, ".mp4")
        self.assertEqual(ft.mime, "video/mp4")

    def test_detects_mp3_from_id3_header(self):
        ft = self._detect("mus", _MP3_ID3)
        self.assertIsNotNone(ft)
        self.assertEqual(ft.ext, ".mp3")

    def test_detects_mp3_from_raw_frame_sync(self):
        ft = self._detect("mus", _MP3_SYNC)
        self.assertIsNotNone(ft)
        self.assertEqual(ft.ext, ".mp3")

    def test_returns_none_for_unknown_content(self):
        ft = self._detect("blob", _UNKNOWN)
        self.assertIsNone(ft)

    def test_returns_none_for_empty_file(self):
        ft = self._detect("empty", b"")
        self.assertIsNone(ft)

    def test_returns_none_for_missing_file(self):
        ft = detect_file_type(self.tmp / "does_not_exist")
        self.assertIsNone(ft)

    def test_m4b_brand_also_detected_as_m4a(self):
        m4b = b"\x00\x00\x00\x1cftyp" b"M4B " b"\x00\x00\x02\x00" b"M4B " + b"\x00" * 100
        ft = self._detect("audiobook", m4b)
        self.assertIsNotNone(ft)
        self.assertEqual(ft.ext, ".m4a")

    def test_mp3_frame_sync_ff_f3(self):
        ft = self._detect("mus", b"\xff\xf3\x90\x00" + b"\x00" * 100)
        self.assertIsNotNone(ft)
        self.assertEqual(ft.ext, ".mp3")

    def test_mp3_frame_sync_ff_f2(self):
        ft = self._detect("mus", b"\xff\xf2\x90\x00" + b"\x00" * 100)
        self.assertIsNotNone(ft)
        self.assertEqual(ft.ext, ".mp3")


# ─── should_normalize_extension ──────────────────────────────────────────────

class ShouldNormalizeExtensionTest(unittest.TestCase):

    def test_no_extension_with_detected_type(self):
        self.assertTrue(should_normalize_extension("", ".png"))

    def test_no_extension_with_no_detected_type(self):
        self.assertFalse(should_normalize_extension("", None))

    def test_matching_extension_no_change(self):
        self.assertFalse(should_normalize_extension(".mp3", ".mp3"))

    def test_matching_extension_case_insensitive(self):
        self.assertFalse(should_normalize_extension(".MP3", ".mp3"))

    def test_mp3_detected_as_m4a_normalizes(self):
        self.assertTrue(should_normalize_extension(".mp3", ".m4a"))

    def test_no_ext_detected_as_png_normalizes(self):
        self.assertTrue(should_normalize_extension("", ".png"))

    def test_jpg_jpeg_compatible_no_change(self):
        self.assertFalse(should_normalize_extension(".jpg", ".jpeg"))
        self.assertFalse(should_normalize_extension(".jpeg", ".jpg"))

    def test_mp4_m4v_compatible_no_change(self):
        self.assertFalse(should_normalize_extension(".mp4", ".m4v"))
        self.assertFalse(should_normalize_extension(".m4v", ".mp4"))

    def test_png_detected_as_jpeg_normalizes(self):
        # Mismatched image types should normalize.
        self.assertTrue(should_normalize_extension(".png", ".jpg"))

    def test_none_detected_no_change(self):
        self.assertFalse(should_normalize_extension(".mp3", None))

    def test_mp4_detected_as_m4a_normalizes(self):
        # Different semantic: video container vs audio container.
        self.assertTrue(should_normalize_extension(".mp4", ".m4a"))
