"""Timeline IR → FCP7 XML (Premiere Pro–compatible).

FCP7 XML reference: Apple "Final Cut Pro XML Interchange Format" — old but
still authoritative for the dialect both Premiere and Resolve consume.

Critical FCP7 XML gotchas this writer handles:

  1. **Time units are integer frames at the sequence rate.** Microseconds in
     IR → frames here via `us → frames = us * timebase / 1e6` with NTSC
     adjustment when applicable. Sub-frame microseconds round to the nearest
     frame; we never emit fractional frames.

  2. **`rate` blocks must appear on the sequence, on every clipitem, and on
     every file.** Premiere is strict about this. Missing rate on a clipitem
     produces "media offline" or wrong-speed playback.

  3. **`<file id="...">` must be declared once with full media info, and
     subsequent references in other clipitems use `<file id="..."/>` (empty,
     id-only).** We track which file IDs have been emitted-with-body and emit
     a stub for repeats. Without this, Premiere will sometimes import only
     the first instance and skip the rest.

  4. **`pathurl` must be a valid file:// URL with percent-encoding.** Plain
     paths don't work. Unresolved assets get a `file:///OFFLINE/<name>` URL
     that Premiere treats as offline; the user then uses Project panel →
     right-click → "Link Media" to relink in bulk.

  5. **`clipitem` in/out vs start/end:**
       - `<in>` / `<out>`   : frames inside the source media
       - `<start>` / `<end>`: frames on the sequence timeline
     Mixing these up is the #1 way to produce a "looks right but plays wrong"
     XML.

  6. **Audio clips need `<sourcetrack>` with the right `mediatype` and
     `trackindex`.** For audio-only assets (BGM), trackindex=1. For the audio
     side of a video file, also trackindex=1 (unless multi-channel — out of
     v0.1 scope).

  7. **No auto-extraction of embedded audio.** The writer emits exactly the
     audio tracks present in `Timeline.audio_tracks`. Video assets'
     `has_audio` flag is informational only — used by the report layer to
     warn the user when source audio won't appear on its own track. See
     `_build_audio_section` for the rationale.
"""

from __future__ import annotations

import math
import urllib.parse
import xml.etree.ElementTree as ET
from pathlib import Path
from xml.dom import minidom

from cutsmith.ir import (
    Clip,
    MediaAsset,
    MediaKind,
    SequenceSettings,
    Timeline,
    Track,
    TrackKind,
)

_DOCTYPE = '<!DOCTYPE xmeml>'
_XMEML_VERSION = "5"


def write_fcp7_xml(timeline: Timeline, output_path: str | Path) -> Path:
    """Render `timeline` to an FCP7 XML file. Returns the path written."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    xmeml = ET.Element("xmeml", attrib={"version": _XMEML_VERSION})
    state = _WriterState(timeline.settings)
    _build_sequence(xmeml, timeline, state)

    # Pretty-print via minidom; ElementTree's own indent works in 3.9+ but
    # minidom gives more predictable whitespace for diff-friendly output.
    rough = ET.tostring(xmeml, encoding="utf-8")
    parsed = minidom.parseString(rough)
    pretty = parsed.toprettyxml(indent="  ", encoding="UTF-8").decode("utf-8")
    # minidom emits its own XML declaration; insert the DOCTYPE after it.
    pretty = pretty.replace(
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<?xml version="1.0" encoding="UTF-8"?>\n' + _DOCTYPE,
        1,
    )

    output_path.write_text(pretty, encoding="utf-8")
    return output_path


# --------------------------------------------------------------------------- #
# writer state — tracks which <file> nodes have been emitted in full          #
# --------------------------------------------------------------------------- #

class _WriterState:
    """Per-write mutable state: file emission dedup + frame conversion."""

    def __init__(self, settings: SequenceSettings):
        self.settings = settings
        self.emitted_files: set[str] = set()

    def us_to_frames(self, us: int) -> int:
        """Microseconds → integer frames at sequence rate.

        For NTSC (29.97 = 30000/1001), Premiere wants frames counted at the
        integer rate (30) with NTSC=TRUE on the <rate> element. The actual
        conversion uses the float rate to map time correctly.
        """
        frames = us * self.settings.frame_rate / 1_000_000.0
        # Round half-up. Premiere rejects non-integer frame counts.
        return int(math.floor(frames + 0.5))

    @property
    def file_id_for(self) -> dict:
        # Stable mapping asset_id → file_id; FCP7 file ids should be like
        # "file-1" / start with a letter. We just prefix.
        return {}


# --------------------------------------------------------------------------- #
# top-level: <sequence>                                                       #
# --------------------------------------------------------------------------- #

def _build_sequence(parent: ET.Element, timeline: Timeline, state: _WriterState) -> None:
    seq = ET.SubElement(parent, "sequence", attrib={"id": "sequence-1"})
    _append_text(seq, "name", timeline.name)
    # Sequence duration: max end across all clips.
    total_frames = _compute_total_frames(timeline, state)
    _append_text(seq, "duration", str(total_frames))
    _append_rate(seq, state.settings)

    # timecode block — Premiere shows this in the timecode column.
    tc = ET.SubElement(seq, "timecode")
    _append_rate(tc, state.settings)
    _append_text(tc, "string", "00:00:00:00")
    _append_text(tc, "frame", "0")
    _append_text(tc, "displayformat", "NDF" if not state.settings.is_ntsc else "DF")

    # media block — contains <video> and <audio> sections.
    media = ET.SubElement(seq, "media")
    _build_video_section(media, timeline, state)
    _build_audio_section(media, timeline, state)


def _compute_total_frames(timeline: Timeline, state: _WriterState) -> int:
    end_us = 0
    for track in (*timeline.video_tracks, *timeline.audio_tracks):
        for clip in track.clips:
            end_us = max(end_us, clip.timeline_start_us + clip.timeline_duration_us)
    if end_us == 0:
        return 1  # empty timeline; Premiere wants duration ≥ 1
    return state.us_to_frames(end_us)


# --------------------------------------------------------------------------- #
# <media><video>                                                              #
# --------------------------------------------------------------------------- #

def _build_video_section(media: ET.Element, timeline: Timeline, state: _WriterState) -> None:
    video = ET.SubElement(media, "video")

    # format block: tells Premiere the sequence frame size + sample rate.
    fmt = ET.SubElement(video, "format")
    sc = ET.SubElement(fmt, "samplecharacteristics")
    _append_rate(sc, state.settings)
    _append_text(sc, "width", str(state.settings.width))
    _append_text(sc, "height", str(state.settings.height))
    _append_text(sc, "pixelaspectratio", "square")
    _append_text(sc, "fielddominance", "none")
    _append_text(sc, "colordepth", "24")

    # One <track> per IR video track. Order matters in FCP7 XML: track index
    # in the rendered output = order of appearance; the first <track> is V1.
    if not timeline.video_tracks:
        # Premiere accepts a video section with no tracks, but some versions
        # warn. Emit an empty track to be safe.
        ET.SubElement(video, "track")
        return

    for track in timeline.video_tracks:
        track_el = ET.SubElement(video, "track")
        for clip in track.clips:
            asset = timeline.assets[clip.asset_id]
            if not asset.has_video:
                continue  # audio-only asset on a video track — skip
            _build_clipitem(track_el, clip, asset, TrackKind.VIDEO, state)


# --------------------------------------------------------------------------- #
# <media><audio>                                                              #
# --------------------------------------------------------------------------- #

def _build_audio_section(media: ET.Element, timeline: Timeline, state: _WriterState) -> None:
    audio = ET.SubElement(media, "audio")

    fmt = ET.SubElement(audio, "format")
    sc = ET.SubElement(fmt, "samplecharacteristics")
    _append_text(sc, "depth", "16")
    _append_text(sc, "samplerate", str(state.settings.sample_rate))

    _append_text(audio, "numOutputChannels", str(state.settings.audio_channels))

    # Writer contract: emit exactly the audio tracks the IR contains. Never
    # synthesize a track from a video asset's embedded audio.
    #
    # Background: CapCut's data model splits any imported video-with-audio
    # into TWO material entries (one in materials.videos, one in materials.audios)
    # that point at the same file, and places an explicit audio track in the
    # draft. The reader already turns that into IR.audio_tracks. An earlier
    # v0.1 writer additionally auto-extracted a parallel audio track from every
    # video clip with asset.has_audio=True; for real CapCut drafts this
    # produced duplicate audio (same content on A1 and A2). The auto-extraction
    # is gone — `MediaAsset.has_audio` is now purely informational, used by the
    # report to flag video clips whose source audio isn't on any track.

    emitted_any = False
    for track in timeline.audio_tracks:
        track_el = ET.SubElement(audio, "track")
        for clip in track.clips:
            asset = timeline.assets[clip.asset_id]
            if not asset.has_audio:
                continue
            _build_clipitem(track_el, clip, asset, TrackKind.AUDIO, state)
            emitted_any = True

    if not emitted_any:
        # FCP7 requires at least one <track> inside <audio>. Emit an empty one.
        ET.SubElement(audio, "track")


# --------------------------------------------------------------------------- #
# <clipitem>                                                                  #
# --------------------------------------------------------------------------- #

def _build_clipitem(
    parent: ET.Element,
    clip: Clip,
    asset: MediaAsset,
    kind: TrackKind,
    state: _WriterState,
) -> None:
    in_frames = state.us_to_frames(clip.source_in_us)
    out_frames = state.us_to_frames(clip.source_out_us)
    # FCP7 quirk: in/out must differ by ≥1 frame, even if source is a still.
    if out_frames <= in_frames:
        out_frames = in_frames + 1
    source_frames = out_frames - in_frames

    # The on-timeline length comes from the IR's timeline_duration_us
    # (CapCut's target slot), not from the source range. For speed=1.0 clips
    # the two match; for variable-speed clips they intentionally diverge so
    # downstream clips line up with what the editor saw — Premiere then
    # interprets end-start ≠ out-in as an implicit speed change on import.
    start_frames = state.us_to_frames(clip.timeline_start_us)
    timeline_frames = state.us_to_frames(clip.timeline_duration_us)
    if timeline_frames <= 0:
        timeline_frames = source_frames
    end_frames = start_frames + timeline_frames

    item = ET.SubElement(parent, "clipitem", attrib={"id": f"clipitem-{clip.clip_id}"})
    _append_text(item, "name", asset.name)
    _append_text(item, "enabled", "TRUE" if clip.enabled else "FALSE")
    _append_text(item, "duration", str(state.us_to_frames(asset.duration_us) or source_frames))
    _append_rate(item, state.settings)
    _append_text(item, "start", str(start_frames))
    _append_text(item, "end", str(end_frames))
    _append_text(item, "in", str(in_frames))
    _append_text(item, "out", str(out_frames))

    _build_file_node(item, asset, state)

    # sourcetrack tells Premiere which stream inside the file we're using.
    st = ET.SubElement(item, "sourcetrack")
    _append_text(st, "mediatype", "video" if kind == TrackKind.VIDEO else "audio")
    _append_text(st, "trackindex", "1")

    # constant volume / opacity via FCP7 <filter> blocks. We only emit these
    # if non-default to keep the XML small.
    if kind == TrackKind.AUDIO and abs(clip.volume - 1.0) > 1e-3:
        _append_audio_level_filter(item, clip.volume)
    if kind == TrackKind.VIDEO and abs(clip.opacity - 1.0) > 1e-3:
        _append_opacity_filter(item, clip.opacity)


# --------------------------------------------------------------------------- #
# <file>                                                                      #
# --------------------------------------------------------------------------- #

def _build_file_node(parent: ET.Element, asset: MediaAsset, state: _WriterState) -> None:
    """Emit <file id="..."> — full body on first occurrence, stub afterwards."""
    file_id = f"file-{asset.asset_id}"

    if file_id in state.emitted_files:
        # Stub reference — Premiere looks up the body by id.
        ET.SubElement(parent, "file", attrib={"id": file_id})
        return

    state.emitted_files.add(file_id)
    file_el = ET.SubElement(parent, "file", attrib={"id": file_id})
    _append_text(file_el, "name", asset.name)
    _append_text(file_el, "pathurl", _path_to_url(asset))
    _append_rate(file_el, state.settings)
    _append_text(file_el, "duration", str(state.us_to_frames(asset.duration_us)))

    media = ET.SubElement(file_el, "media")
    if asset.has_video or asset.media_kind == MediaKind.IMAGE:
        video = ET.SubElement(media, "video")
        _append_text(video, "duration", str(state.us_to_frames(asset.duration_us)))
        sc = ET.SubElement(video, "samplecharacteristics")
        _append_rate(sc, state.settings)
        if asset.width and asset.height:
            _append_text(sc, "width", str(asset.width))
            _append_text(sc, "height", str(asset.height))
    if asset.has_audio:
        a = ET.SubElement(media, "audio")
        sc = ET.SubElement(a, "samplecharacteristics")
        _append_text(sc, "depth", "16")
        _append_text(sc, "samplerate", str(asset.audio_sample_rate or 48000))
        _append_text(a, "channelcount", str(asset.audio_channels or 2))


def _path_to_url(asset: MediaAsset) -> str:
    """Convert a resolved or unresolved path to a file:// URL.

    Unresolved → file:///OFFLINE/<basename>. Premiere will show these clips
    as offline; the user then uses Link Media to point them at the right
    files (typically by selecting the parent folder once and Premiere finds
    everything by basename).
    """
    if asset.resolved_path:
        return Path(asset.resolved_path).resolve().as_uri()
    # The OFFLINE/ sentinel directory makes it obvious in Premiere's Link
    # Media dialog which clips need attention.
    safe = urllib.parse.quote(asset.name)
    return f"file:///OFFLINE/{safe}"


# --------------------------------------------------------------------------- #
# small helpers                                                               #
# --------------------------------------------------------------------------- #

def _append_text(parent: ET.Element, tag: str, text: str) -> ET.Element:
    el = ET.SubElement(parent, tag)
    el.text = text
    return el


def _append_rate(parent: ET.Element, settings: SequenceSettings) -> ET.Element:
    rate = ET.SubElement(parent, "rate")
    _append_text(rate, "timebase", str(settings.timebase))
    _append_text(rate, "ntsc", "TRUE" if settings.is_ntsc else "FALSE")
    return rate


def _append_audio_level_filter(clipitem: ET.Element, volume: float) -> None:
    """Constant-level audio gain via FCP7's standard Audio Levels filter."""
    flt = ET.SubElement(clipitem, "filter")
    eff = ET.SubElement(flt, "effect")
    _append_text(eff, "name", "Audio Levels")
    _append_text(eff, "effectid", "audiolevels")
    _append_text(eff, "effectcategory", "audiolevels")
    _append_text(eff, "effecttype", "audiolevels")
    _append_text(eff, "mediatype", "audio")
    param = ET.SubElement(eff, "parameter", attrib={"authoringApp": "PremierePro"})
    _append_text(param, "parameterid", "level")
    _append_text(param, "name", "Level")
    _append_text(param, "valuemin", "0")
    _append_text(param, "valuemax", "3.98109")  # +12 dB in linear
    _append_text(param, "value", f"{volume:.6f}")


def _append_opacity_filter(clipitem: ET.Element, opacity: float) -> None:
    flt = ET.SubElement(clipitem, "filter")
    eff = ET.SubElement(flt, "effect")
    _append_text(eff, "name", "Opacity")
    _append_text(eff, "effectid", "opacity")
    _append_text(eff, "effectcategory", "motion")
    _append_text(eff, "effecttype", "motion")
    _append_text(eff, "mediatype", "video")
    param = ET.SubElement(eff, "parameter", attrib={"authoringApp": "PremierePro"})
    _append_text(param, "parameterid", "opacity")
    _append_text(param, "name", "opacity")
    _append_text(param, "valuemin", "0")
    _append_text(param, "valuemax", "100")
    _append_text(param, "value", f"{opacity * 100:.4f}")
