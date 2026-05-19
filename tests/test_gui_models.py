"""Tests for GUI model logic (no PySide6 required)."""

import unittest
from pathlib import Path
from unittest.mock import MagicMock

from cutsmith.gui.models import AnalysisResult, ProjectEntry


def _fake_detect(app_type="capcut", encryption="", supported="supported", schema_version="360000"):
    d = MagicMock()
    d.app_type = app_type
    d.encryption = encryption
    d.supported_status = supported
    d.schema_version = schema_version
    return d


def _make_entry(name="0519V", app_type="capcut", encryption=""):
    detect = _fake_detect(app_type=app_type, encryption=encryption)
    return ProjectEntry(
        path=Path(f"/tmp/projects/{name}"),
        detect=detect,
        display_name=name,
    )


class TestProjectEntryGrouping(unittest.TestCase):
    def test_capcut_group(self):
        e = _make_entry(app_type="capcut")
        self.assertEqual(e.group, "capcut")

    def test_jianying_group(self):
        e = _make_entry(app_type="jianying")
        self.assertEqual(e.group, "jianying")

    def test_encrypted_group(self):
        e = _make_entry(encryption="encrypted")
        self.assertEqual(e.group, "encrypted")

    def test_unknown_group(self):
        e = _make_entry(app_type="unknown")
        self.assertEqual(e.group, "unknown")

    def test_app_label_capcut(self):
        e = _make_entry(app_type="capcut")
        self.assertEqual(e.app_label, "CapCut Desktop")

    def test_app_label_jianying(self):
        e = _make_entry(app_type="jianying")
        self.assertEqual(e.app_label, "JianyingPro")

    def test_display_name_defaults_to_path_name(self):
        detect = _fake_detect()
        e = ProjectEntry(path=Path("/tmp/some_project"), detect=detect)
        self.assertEqual(e.display_name, "some_project")


class TestAnalysisResultDerived(unittest.TestCase):
    def _make_result(self, **kwargs) -> AnalysisResult:
        entry = _make_entry()
        r = AnalysisResult(entry=entry)
        for k, v in kwargs.items():
            setattr(r, k, v)
        return r

    def test_duration_label_minutes(self):
        r = self._make_result(duration_us=90_000_000)  # 90 s = 1:30
        self.assertEqual(r.duration_label, "1:30")

    def test_duration_label_hours(self):
        r = self._make_result(duration_us=3_661_000_000)  # 1h 1m 1s
        self.assertEqual(r.duration_label, "1:01:01")

    def test_resolution_label(self):
        r = self._make_result(canvas_w=1920, canvas_h=1080)
        self.assertEqual(r.resolution_label, "1920×1080")

    def test_fps_label_integer(self):
        r = self._make_result(fps=24.0)
        self.assertEqual(r.fps_label, "24fps")

    def test_fps_label_fractional(self):
        r = self._make_result(fps=29.97)
        self.assertEqual(r.fps_label, "29.97fps")

    def test_size_label_mb(self):
        r = self._make_result(total_size_bytes=5_800_000)
        self.assertIn("MB", r.size_label)

    def test_is_portable_no_offline(self):
        r = self._make_result(total_offline=0)
        self.assertTrue(r.is_portable)

    def test_is_portable_with_offline(self):
        r = self._make_result(total_offline=2)
        self.assertFalse(r.is_portable)

    def test_has_warnings_speed_curve(self):
        r = self._make_result(speed_curve_count=1)
        self.assertTrue(r.has_warnings)

    def test_has_warnings_none(self):
        r = self._make_result(speed_curve_count=0, speed_clip_count=0,
                               unsupported_count=0, total_offline=0)
        self.assertFalse(r.has_warnings)


class TestOutputPathGeneration(unittest.TestCase):
    def test_default_out_dir_name(self):
        entry = _make_entry(name="MyProject")
        result = AnalysisResult(entry=entry)
        out = result.default_out_dir()
        self.assertEqual(out.name, "MyProject")
        self.assertEqual(out.parent.name, "out_collect")


if __name__ == "__main__":
    unittest.main()
