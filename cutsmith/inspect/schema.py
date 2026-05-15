"""Schema sampling primitives shared across inspect outputs.

Three responsibilities, kept here so probe.py stays readable:

  1. `summarize_objects` — given a list of homogeneous-ish dicts (e.g.
     `materials.videos`), return per-field type + sample-value + presence
     stats. This is the heart of every summary file we emit.

  2. `KNOWN_FIELDS` — the field names the reader actually reads. Anything in
     the draft that isn't in this set is a candidate for "schema drift" and
     surfaces in unknown_fields.json.

  3. `redact_path` — basename-only by default, full path if --raw-paths.
     CapCut paths often contain usernames and project names; we shouldn't
     leak those when the user pastes inspect output into a bug report.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path, PureWindowsPath
from typing import Any


# --------------------------------------------------------------------------- #
# Known fields — must stay in sync with reader/jianying_pro.py                #
# --------------------------------------------------------------------------- #
#
# Used to compute "unknown_fields": which keys did the draft have that the
# reader doesn't look at? A growing unknown_fields list across drafts is the
# signal to expand reader coverage.

KNOWN_TOP_LEVEL_FIELDS: set[str] = {
    "version", "new_version", "fps", "duration",
    "canvas_config", "materials", "tracks",
}

KNOWN_CANVAS_FIELDS: set[str] = {
    "width", "height", "ratio", "fps",
}

KNOWN_VIDEO_MATERIAL_FIELDS: set[str] = {
    "id", "material_name", "path", "type", "duration",
    "width", "height", "source_frame_rate", "fps", "has_audio",
}

KNOWN_AUDIO_MATERIAL_FIELDS: set[str] = {
    "id", "name", "path", "type", "duration",
    "channels", "sample_rate",
}

KNOWN_TRACK_FIELDS: set[str] = {
    "id", "type", "attribute", "segments",
}

KNOWN_SEGMENT_FIELDS: set[str] = {
    "id", "material_id",
    "source_timerange", "target_timerange",
    "speed", "volume", "visible", "clip",
    "extra_material_refs", "keyframe_refs",
}


# --------------------------------------------------------------------------- #
# Type + value sampling                                                       #
# --------------------------------------------------------------------------- #

def _type_label(v: Any) -> str:
    """Human-readable type label used in summaries. Keeps lists/dicts shallow."""
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "bool"
    if isinstance(v, int):
        return "int"
    if isinstance(v, float):
        return "float"
    if isinstance(v, str):
        return "str"
    if isinstance(v, list):
        if not v:
            return "list[empty]"
        inner_types = {_type_label(x) for x in v[:5]}
        return f"list[{'|'.join(sorted(inner_types))}]"
    if isinstance(v, dict):
        return "dict"
    return type(v).__name__


def _safe_sample(v: Any, max_str_len: int = 80) -> Any:
    """Pick a representative value for the summary. Truncate strings, replace
    long lists/dicts with a shape descriptor."""
    if isinstance(v, str):
        return v if len(v) <= max_str_len else v[:max_str_len] + "...[trunc]"
    if isinstance(v, list):
        if len(v) > 3:
            return f"<list of {len(v)}, first: {_safe_sample(v[0]) if v else None!r}>"
        return [_safe_sample(x) for x in v]
    if isinstance(v, dict):
        # One-level peek: just show keys, not values, so we don't blow up
        # on deeply nested structures like keyframe arrays.
        return f"<dict with keys: {sorted(v.keys())}>"
    return v


def summarize_objects(
    objs: list[dict[str, Any]],
    known_fields: set[str] | None = None,
) -> dict[str, Any]:
    """Summarize a list of dicts: union of fields, type distribution, sample
    value, and (if `known_fields` given) which fields are unexpected.

    Output shape (stable — downstream tooling can parse this):
        {
          "count": 12,
          "fields": {
            "id":       {"present_in": 12, "types": {"str": 12}, "sample": "abc-123"},
            "duration": {"present_in": 12, "types": {"int": 12}, "sample": 30000000},
            ...
          },
          "unknown_fields": ["foo", "bar"],   # only if known_fields supplied
        }
    """
    field_presence: Counter[str] = Counter()
    field_types: dict[str, Counter[str]] = {}
    field_samples: dict[str, Any] = {}

    for obj in objs:
        if not isinstance(obj, dict):
            continue
        for key, value in obj.items():
            field_presence[key] += 1
            field_types.setdefault(key, Counter())[_type_label(value)] += 1
            # Keep the first non-null sample we see.
            if key not in field_samples and value is not None and value != "":
                field_samples[key] = _safe_sample(value)

    fields_out: dict[str, Any] = {}
    for key in sorted(field_presence.keys()):
        fields_out[key] = {
            "present_in": field_presence[key],
            "types": dict(field_types[key]),
            "sample": field_samples.get(key),
        }

    summary: dict[str, Any] = {
        "count": len(objs),
        "fields": fields_out,
    }

    if known_fields is not None:
        unknown = sorted(set(field_presence.keys()) - known_fields)
        summary["unknown_fields"] = unknown
        missing_expected = sorted(known_fields - set(field_presence.keys()))
        summary["missing_known_fields"] = missing_expected

    return summary


# --------------------------------------------------------------------------- #
# Path redaction                                                              #
# --------------------------------------------------------------------------- #

def redact_path(raw: str | None, *, keep: bool) -> str | None:
    """Reduce a possibly-PII-laden path to just its basename, unless caller
    opts in to keeping the full path. Handles Windows + POSIX flavors."""
    if not raw:
        return raw
    if keep:
        return raw
    if "\\" in raw and "/" not in raw:
        return PureWindowsPath(raw).name or raw
    return Path(raw).name or raw
