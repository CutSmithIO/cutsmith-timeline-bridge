"""MainWindow — three-panel layout, signal/slot wiring."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QMainWindow,
    QProgressBar,
    QStatusBar,
    QWidget,
)

from cutsmith.gui.models import AnalysisResult, ProjectEntry
from cutsmith.gui.panels.export_decision import ExportDecisionPanel
from cutsmith.gui.panels.project_discovery import ProjectDiscoveryPanel
from cutsmith.gui.panels.project_readiness import ProjectReadinessPanel
from cutsmith.gui.style import APP_QSS
from cutsmith.gui.workers.analyze_worker import AnalyzeWorker
from cutsmith.gui.workers.collect_worker import CollectWorker
from cutsmith.gui.workers.scan_worker import CAPCUT_ROOTS_MACOS, ScanWorker
from cutsmith.gui.workers.srt_worker import SRTWorker


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("CutSmith · Project Handoff Assistant")
        self.resize(1100, 700)
        self.setMinimumSize(900, 580)
        self.setStyleSheet(APP_QSS)

        self._current_entry: ProjectEntry | None = None
        self._current_result: AnalysisResult | None = None
        self._workers: list = []  # keep references to prevent GC

        # ── panels ──
        self._left = ProjectDiscoveryPanel()
        self._center = ProjectReadinessPanel()
        self._right = ExportDecisionPanel()

        # ── layout ──
        body = QWidget()
        body.setObjectName("root")
        h = QHBoxLayout(body)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(0)
        h.addWidget(self._left)
        h.addWidget(self._center, 1)
        h.addWidget(self._right)
        self.setCentralWidget(body)

        # ── status bar ──
        self._status = QStatusBar()
        self._status.setSizeGripEnabled(False)
        self._progress = QProgressBar()
        self._progress.setFixedWidth(120)
        self._progress.setFixedHeight(4)
        self._progress.setTextVisible(False)
        self._progress.setRange(0, 0)  # indeterminate
        self._progress.hide()
        self._status.addPermanentWidget(self._progress)
        self.setStatusBar(self._status)

        # ── signals ──
        self._left.project_selected.connect(self._on_project_selected)
        self._left.rescan_requested.connect(self._start_scan)
        self._left.add_folder_requested.connect(self._scan_extra_folder)
        self._right.collect_requested.connect(self._on_collect_requested)
        self._right.srt_requested.connect(self._on_srt_requested)

    # ── startup scan ───────────────────────────────────────────────────────────

    def start_auto_scan(self) -> None:
        self._start_scan()

    def _start_scan(self) -> None:
        self._left.clear()
        self._right.clear()
        self._center.show_loading("projects")
        self._set_status("Scanning for projects…", busy=True)
        w = ScanWorker(CAPCUT_ROOTS_MACOS)
        w.found.connect(self._left.add_project)
        w.finished_scan.connect(self._on_scan_done)
        w.error.connect(lambda msg: self._set_status(f"Scan error: {msg}", busy=False))
        self._workers.append(w)
        w.start()

    def _scan_extra_folder(self, folder: Path) -> None:
        self._set_status(f"Scanning {folder.name}…", busy=True)
        w = ScanWorker([folder])
        w.found.connect(self._left.add_project)
        w.finished_scan.connect(lambda n: self._set_status(f"Found {n} project(s) in {folder.name}", busy=False))
        self._workers.append(w)
        w.start()

    def _on_scan_done(self, count: int) -> None:
        self._set_status(f"Found {count} project(s)", busy=False)
        if count == 0:
            self._center.show_error(
                "No CapCut projects found in default locations.\n"
                "Use '+ Add Folder…' to locate your projects."
            )
        else:
            from cutsmith.gui.panels.project_readiness import ProjectReadinessPanel
            self._center._clear()
            self._center._show_empty()

    # ── project selection ──────────────────────────────────────────────────────

    def _on_project_selected(self, entry: ProjectEntry) -> None:
        self._current_entry = entry
        self._current_result = None
        self._right.clear()
        self._center.show_loading(entry.display_name)
        self._set_status(f"Analyzing {entry.display_name}…", busy=True)

        w = AnalyzeWorker(entry)
        w.finished.connect(self._on_analysis_done)
        w.error.connect(lambda msg: self._on_analysis_error(msg))
        self._workers.append(w)
        w.start()

    def _on_analysis_done(self, result: AnalysisResult) -> None:
        self._current_result = result
        if result.error:
            self._center.show_error(result.error)
            self._set_status(f"Analysis failed: {result.error[:60]}", busy=False)
            return
        self._center.show_result(result)
        self._right.set_result(result)
        clips = result.clip_count
        warns = result.speed_curve_count + result.total_report_only
        msg = f"{result.entry.display_name} · {clips} clip{'s' if clips != 1 else ''}"
        if warns:
            msg += f" · {warns} warning{'s' if warns != 1 else ''}"
        self._set_status(msg, busy=False)

    def _on_analysis_error(self, msg: str) -> None:
        self._center.show_error(msg)
        self._set_status(f"Error: {msg[:80]}", busy=False)

    # ── collect ────────────────────────────────────────────────────────────────

    def _on_collect_requested(self, out_dir: Path) -> None:
        if self._current_entry is None:
            return
        self._right.set_collecting(True)
        self._set_status("Collecting assets…", busy=True)
        w = CollectWorker(
            project_path=self._current_entry.path,
            out_dir=out_dir,
        )
        w.finished.connect(lambda r: self._on_collect_done(r, out_dir))
        w.error.connect(self._on_collect_error)
        self._workers.append(w)
        w.start()

    def _on_collect_done(self, result, out_dir: Path) -> None:
        self._right.set_collect_done(out_dir)
        self._set_status(f"Package ready → {out_dir.name}/", busy=False)

    def _on_collect_error(self, msg: str) -> None:
        self._right.set_collecting(False)
        self._set_status(f"Collect failed: {msg[:80]}", busy=False)

    # ── srt export ────────────────────────────────────────────────────────────

    def _on_srt_requested(self, out_dir: Path) -> None:
        if self._current_entry is None:
            return
        from cutsmith.gui.workers.analyze_worker import _find_draft
        draft_path = _find_draft(self._current_entry.path)
        if draft_path is None:
            self._set_status("Cannot locate draft file for SRT export", busy=False)
            return
        out_dir.mkdir(parents=True, exist_ok=True)
        w = SRTWorker(draft_path=draft_path, out_dir=out_dir)
        w.finished.connect(lambda p: self._set_status(f"SRT written → {Path(p).name}", busy=False))
        w.error.connect(lambda msg: self._set_status(f"SRT export failed: {msg[:80]}", busy=False))
        self._workers.append(w)
        self._set_status("Exporting SRT…", busy=True)
        w.start()

    # ── helpers ────────────────────────────────────────────────────────────────

    def _set_status(self, msg: str, busy: bool = False) -> None:
        self._status.showMessage(msg)
        if busy:
            self._progress.show()
        else:
            self._progress.hide()
