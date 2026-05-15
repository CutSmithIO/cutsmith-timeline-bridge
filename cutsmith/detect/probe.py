"""Detect what kind of CapCut / JianyingPro draft we're looking at.

Goal: a fast triage tool that classifies a sample without parsing the
timeline. Given either a project root or a single draft file, report
app / version / encryption / timeline-entry-path / supported_status, so
real-world samples can be sorted into fixture buckets and unsupported
encrypted drafts can be rejected with a clear message before inspect
or convert is attempted.

Detection is *structural*:
  - File names and directory layout are the primary signal
    (Timelines/<UUID>/draft_info.json vs draft_content.json).
  - First-byte check (b'{' vs anything else) separates plaintext JSON
    from encrypted / encoded content. We never attempt to decode.
  - When plaintext, read `version` and `new_version` from the top level
    to populate schema_version / app_version.

This module is independent of reader/ and inspect/. It must not import
either, so it remains usable when those modules fail.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path


# ── result type ─────────────────────────────────────────────────────────── #

@dataclass
class DetectionResult:
    input_path: str
    app_type: str                   # jianying | capcut | unknown
    app_version: str | None         # from `new_version` field, e.g. "75.0.0"
    schema_version: int | None      # from `version` field, e.g. 360000
    schema_type: str                # legacy_plaintext | modern_plaintext | modern_encrypted | unknown
    encryption: str                 # plaintext | encrypted | unknown
    timeline_entry_path: str | None
    supported_status: str           # supported | unsupported_encrypted | unverified | unknown | error
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


# ── public entry point ──────────────────────────────────────────────────── #

def detect_project(path: str | Path) -> DetectionResult:
    """Classify a project root or a single draft-related file."""
    p = Path(path).expanduser()
    input_str = str(p)

    if not p.exists():
        return _result(
            input_str, app_type="unknown",
            encryption="unknown", schema_type="unknown",
            supported_status="error", notes=["path does not exist"],
        )

    if p.is_dir():
        return _detect_dir(p, input_str)
    return _detect_file(p, input_str)


# ── directory-mode detection ────────────────────────────────────────────── #

def _detect_dir(root: Path, input_str: str) -> DetectionResult:
    """Three known directory layouts:

      1. legacy:        <root>/draft_content.json
      2. flat modern:   <root>/draft_info.json   (CapCut Desktop ≥ 167.0.0)
      3. nested modern: <root>/Timelines/<UUID>/draft_info.json
                        (JianyingPro ≥ 75.0.0, typically encrypted)

    Precedence when more than one is present: nested modern > flat modern
    > legacy. Newer layouts may retain older filenames as initialisation
    stubs, so the deeper layout signal wins.
    """
    app_type = _guess_app_type(root)
    notes: list[str] = []

    legacy = root / "draft_content.json"
    flat_modern = root / "draft_info.json"
    nested_manifest = root / "Timelines" / "project.json"

    has_legacy = legacy.is_file()
    has_flat = flat_modern.is_file()
    has_nested = nested_manifest.is_file()

    if has_nested:
        if has_flat or has_legacy:
            notes.append("nested Timelines/ layout takes precedence over "
                         "draft_info.json / draft_content.json at root")
        return _from_nested_modern_layout(root, nested_manifest, app_type, input_str, notes)

    if has_flat:
        if has_legacy:
            notes.append("preferring draft_info.json over draft_content.json at root")
        return _classify_modern_entry(flat_modern, app_type, input_str, notes)

    if has_legacy:
        return _from_legacy_file(legacy, app_type, input_str, notes)

    return _result(
        input_str, app_type=app_type,
        encryption="unknown", schema_type="unknown",
        supported_status="unknown",
        notes=notes + ["no draft_content.json, draft_info.json, or Timelines/project.json found"],
    )


def _from_legacy_file(legacy: Path, app_type: str, input_str: str,
                      notes: list[str]) -> DetectionResult:
    peek = _peek(legacy)
    if peek.plaintext:
        return _result(
            input_str, app_type=app_type,
            app_version=peek.new_version, schema_version=peek.schema_version,
            schema_type="legacy_plaintext", encryption="plaintext",
            timeline_entry_path=str(legacy),
            supported_status="supported",
            notes=notes,
        )
    return _result(
        input_str, app_type=app_type,
        schema_type="unknown", encryption="encrypted",
        timeline_entry_path=str(legacy),
        supported_status="unsupported_encrypted",
        notes=notes + ["draft_content.json present but content is not plaintext JSON"],
    )


def _from_nested_modern_layout(root: Path, project_json: Path, app_type: str,
                               input_str: str, notes: list[str]) -> DetectionResult:
    main_id, manifest_notes = _read_main_timeline_id(project_json)
    notes.extend(manifest_notes)

    candidate = None
    if main_id:
        c = root / "Timelines" / main_id / "draft_info.json"
        if c.is_file():
            candidate = c
        else:
            notes.append(f"main_timeline_id={main_id} but its draft_info.json is missing")

    if candidate is None:
        for sub in (root / "Timelines").iterdir():
            if sub.is_dir() and (sub / "draft_info.json").is_file():
                candidate = sub / "draft_info.json"
                notes.append(f"falling back to first Timelines/<UUID>/draft_info.json ({sub.name})")
                break

    if candidate is None:
        return _result(
            input_str, app_type=app_type,
            schema_type="unknown", encryption="unknown",
            supported_status="error",
            notes=notes + ["modern layout but no Timelines/<UUID>/draft_info.json found"],
        )

    return _classify_modern_entry(candidate, app_type, input_str, notes)


def _read_main_timeline_id(project_json: Path) -> tuple[str | None, list[str]]:
    try:
        with project_json.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        return None, [f"failed to read Timelines/project.json: {e}"]
    main_id = data.get("main_timeline_id")
    return (main_id if isinstance(main_id, str) else None, [])


# ── file-mode detection ─────────────────────────────────────────────────── #

def _detect_file(p: Path, input_str: str) -> DetectionResult:
    app_type = _guess_app_type(p)
    name = p.name.lower()

    if name == "draft_content.json":
        return _from_legacy_file(p, app_type, input_str, [])

    if name == "draft_info.json":
        return _classify_modern_entry(p, app_type, input_str, [])

    if name == "template.tmp":
        peek = _peek(p)
        return _result(
            input_str, app_type=app_type,
            app_version=peek.new_version, schema_version=peek.schema_version,
            schema_type="unknown",
            encryption="plaintext" if peek.plaintext else "encrypted",
            supported_status="unknown",
            notes=["template.tmp is typically an empty project skeleton, not the user's timeline"],
        )

    peek = _peek(p)
    return _result(
        input_str, app_type=app_type,
        app_version=peek.new_version, schema_version=peek.schema_version,
        schema_type="unknown",
        encryption="plaintext" if peek.plaintext else "encrypted",
        timeline_entry_path=str(p) if peek.plaintext else None,
        supported_status="unverified" if peek.plaintext else "unknown",
        notes=[f"unrecognized filename: {p.name}"],
    )


def _classify_modern_entry(p: Path, app_type: str, input_str: str,
                           notes: list[str]) -> DetectionResult:
    peek = _peek(p)
    if peek.plaintext:
        return _result(
            input_str, app_type=app_type,
            app_version=peek.new_version, schema_version=peek.schema_version,
            schema_type="modern_plaintext", encryption="plaintext",
            timeline_entry_path=str(p),
            supported_status="unverified",
            notes=notes + ["modern path layout with plaintext content — "
                           "no fixture verified yet, treat as research sample"],
        )
    return _result(
        input_str, app_type=app_type,
        schema_type="modern_encrypted", encryption="encrypted",
        timeline_entry_path=str(p),
        supported_status="unsupported_encrypted",
        notes=notes + ["modern encrypted draft (e.g. JianyingPro >= 75.0.0); "
                       "see docs/notes/modern_jianying_75_storage.md"],
    )


# ── helpers ─────────────────────────────────────────────────────────────── #

@dataclass
class _Peek:
    plaintext: bool
    new_version: str | None = None
    schema_version: int | None = None


def _peek(p: Path) -> _Peek:
    """Cheap first-byte probe + top-level version fields if plaintext JSON."""
    try:
        with p.open("rb") as f:
            head = f.read(1)
    except OSError:
        return _Peek(plaintext=False)
    if head != b"{":
        return _Peek(plaintext=False)
    try:
        with p.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return _Peek(plaintext=True)
    if not isinstance(data, dict):
        return _Peek(plaintext=True)
    nv = data.get("new_version")
    v = data.get("version")
    return _Peek(
        plaintext=True,
        new_version=nv if isinstance(nv, str) else None,
        schema_version=v if isinstance(v, int) else None,
    )


def _guess_app_type(path: Path) -> str:
    lowered = {part.lower() for part in path.parts}
    if "capcut" in lowered:
        return "capcut"
    if "jianyingpro" in lowered or "jianying" in lowered:
        return "jianying"
    return "unknown"


def _result(input_str: str, *, app_type: str,
            encryption: str, schema_type: str, supported_status: str,
            app_version: str | None = None, schema_version: int | None = None,
            timeline_entry_path: str | None = None,
            notes: list[str] | None = None) -> DetectionResult:
    return DetectionResult(
        input_path=input_str,
        app_type=app_type,
        app_version=app_version,
        schema_version=schema_version,
        schema_type=schema_type,
        encryption=encryption,
        timeline_entry_path=timeline_entry_path,
        supported_status=supported_status,
        notes=list(notes or []),
    )
