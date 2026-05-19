"""CollectWorker — run collect() in background."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QThread, Signal

from cutsmith.collector import collect, CollectResult


class CollectWorker(QThread):
    finished = Signal(object)   # CollectResult
    error = Signal(str)

    def __init__(
        self,
        project_path: Path,
        out_dir: Path,
        search_roots: list[Path] | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.project_path = project_path
        self.out_dir = out_dir
        self.search_roots = search_roots or []

    def run(self) -> None:
        try:
            result = collect(
                project_path=self.project_path,
                out_dir=self.out_dir,
                search_roots=self.search_roots or None,
            )
            self.finished.emit(result)
        except Exception as exc:
            self.error.emit(str(exc))
