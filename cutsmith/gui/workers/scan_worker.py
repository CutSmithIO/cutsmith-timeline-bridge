"""ScanWorker — discover and detect projects in background."""

from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtCore import QThread, Signal

from cutsmith.detect import detect_project
from cutsmith.detect.probe import DetectionResult
from cutsmith.gui.models import ProjectEntry

# Default roots searched on startup (macOS paths)
CAPCUT_ROOTS_MACOS = [
    Path.home() / "Movies" / "CapCut" / "User Data" / "Projects" / "com.lveditor.draft",
    Path.home() / "Movies" / "JianyingPro" / "User Data" / "Projects" / "com.lveditor.draft",
    Path.home() / "Library" / "Application Support" / "CapCut" / "User Data" / "Projects" / "com.lveditor.draft",
]


def _mtime_label(path: Path) -> str:
    try:
        ts = path.stat().st_mtime
        import datetime
        return datetime.datetime.fromtimestamp(ts).strftime("%Y-%m-%d")
    except OSError:
        return ""


def _make_entry(path: Path, detect: DetectionResult) -> ProjectEntry:
    at = detect.app_type or "unknown"
    enc = detect.encryption or ""
    group = "encrypted" if enc not in ("", "none", "plaintext") else at
    app_label = {"capcut": "CapCut Desktop", "jianying": "JianyingPro"}.get(at, "Unknown")
    return ProjectEntry(
        path=path,
        detect=detect,
        display_name=path.name,
        app_label=app_label,
        date_label=_mtime_label(path),
        group=group,
    )


class ScanWorker(QThread):
    """Scans a list of root directories for CapCut/JianyingPro projects."""

    started_scan = Signal()
    found = Signal(object)      # emits ProjectEntry per project found
    finished_scan = Signal(int) # total count
    error = Signal(str)

    def __init__(self, roots: list[Path], parent=None) -> None:
        super().__init__(parent)
        self.roots = roots

    def run(self) -> None:
        self.started_scan.emit()
        count = 0
        for root in self.roots:
            if not root.exists():
                continue
            try:
                for entry in sorted(root.iterdir()):
                    if not entry.is_dir():
                        continue
                    try:
                        detect = detect_project(entry)
                        proj = _make_entry(entry, detect)
                        self.found.emit(proj)
                        count += 1
                    except Exception:
                        pass
            except PermissionError:
                pass
        self.finished_scan.emit(count)
