"""SRTWorker — export subtitles in background."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QThread, Signal

from cutsmith.subtitle import export_subtitles


class SRTWorker(QThread):
    finished = Signal(str)  # path to written file
    error = Signal(str)

    def __init__(self, draft_path: Path, out_dir: Path, fmt: str = "srt", parent=None) -> None:
        super().__init__(parent)
        self.draft_path = draft_path
        self.out_dir = out_dir
        self.fmt = fmt

    def run(self) -> None:
        try:
            paths = export_subtitles(self.draft_path, self.out_dir, formats=[self.fmt])
            out = str(paths[0]) if paths else str(self.out_dir)
            self.finished.emit(out)
        except Exception as exc:
            self.error.emit(str(exc))
