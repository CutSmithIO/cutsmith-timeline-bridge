"""Canonical Timeline IR — the contract between readers and writers.

Designed for v0.1 scope: cut points, original audio, BGM tracks, multi-track
order. Deliberately leaves room (via `extras` dicts) for v0.2+ features
(keyframes, speed ramps, transitions) without forcing a schema migration.

Time model: everything in IR is integer microseconds. Readers normalize from
their source unit (CapCut uses microseconds internally; some legacy versions
used milliseconds). Writers convert to their target unit (FCP7 XML uses frame
counts at a declared timebase; FCPXML uses rational seconds).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class TrackKind(str, Enum):
    VIDEO = "video"
    AUDIO = "audio"


class MediaKind(str, Enum):
    VIDEO = "video"      # has visual track, may also have audio
    AUDIO = "audio"      # audio-only (BGM, voiceover)
    IMAGE = "image"      # still image
    UNKNOWN = "unknown"  # couldn't probe; writer will guess


class AssetClass(str, Enum):
    USER_VIDEO      = "user_video"      # user-imported video file
    USER_AUDIO      = "user_audio"      # user-imported audio / embedded-audio extract
    USER_IMAGE      = "user_image"      # user-imported image
    CAPCUT_MUSIC    = "capcut_music"    # CapCut music library track (may be cached)
    CAPCUT_SFX      = "capcut_sfx"      # CapCut sound effect (may be cached)
    CAPCUT_STICKER  = "capcut_sticker"  # CapCut sticker / overlay
    CAPCUT_EFFECT   = "capcut_effect"   # CapCut video effect, filter, or transition
    CAPCUT_FONT     = "capcut_font"     # CapCut-downloaded font (app-bundle; not copied)
    UNKNOWN         = "unknown"


@dataclass
class MediaAsset:
    """A source file referenced by one or more clips.

    `asset_id` is stable across the IR — readers assign it, writers use it to
    dedupe <file> / <asset> nodes in the output XML.
    """
    asset_id: str
    name: str                       # display name, usually basename
    original_path: str              # path as recorded in the draft (may be missing/relative)
    resolved_path: str | None       # absolute path on the current machine, or None if unresolved
    media_kind: MediaKind
    duration_us: int                # full length of the source media
    has_video: bool
    has_audio: bool
    width: int | None = None
    height: int | None = None
    frame_rate: float | None = None # source media's native rate; not the sequence rate
    audio_channels: int | None = None
    audio_sample_rate: int | None = None
    extras: dict[str, Any] = field(default_factory=dict)
    asset_class: AssetClass = AssetClass.UNKNOWN  # filled by scanner, not reader
    is_cached: bool = False                        # True when path is inside a CapCut cache dir


@dataclass
class Clip:
    """One segment placed on one track.

    Time fields:
      - `source_in_us`        : in-point inside the source media
      - `source_out_us`       : out-point inside the source media (exclusive)
      - `timeline_start_us`   : where this clip starts on the sequence timeline
      - `timeline_duration_us`: how long this clip occupies on the timeline

    In a draft with no speed changes, `timeline_duration_us` equals
    `source_out_us - source_in_us`. With a speed change CapCut's source
    duration and target slot diverge — e.g. a 10s source slice slowed to 0.5×
    occupies 20s on the timeline. The writer keeps `timeline_duration_us` so
    downstream clips stay aligned with what CapCut showed; FCP7 XML encodes
    the duration mismatch (end-start ≠ out-in) which Premiere interprets as
    an implicit speed effect. The report still flags speed-changed clips so
    the user can override the implied speed manually in Premiere if desired.

    Constructor: `timeline_duration_us=None` (the default) derives the value
    from `source_out_us - source_in_us` in __post_init__, so existing callers
    that didn't know about the field keep working.
    """
    clip_id: str
    asset_id: str
    source_in_us: int
    source_out_us: int
    timeline_start_us: int
    timeline_duration_us: int | None = None
    enabled: bool = True
    # v0.1 keeps these as constants only; keyframes deferred.
    volume: float = 1.0           # linear gain; audio tracks only meaningful
    opacity: float = 1.0          # video tracks only meaningful
    extras: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.timeline_duration_us is None:
            self.timeline_duration_us = self.source_out_us - self.source_in_us


@dataclass
class Track:
    track_id: str
    kind: TrackKind
    name: str
    clips: list[Clip] = field(default_factory=list)
    muted: bool = False
    locked: bool = False
    extras: dict[str, Any] = field(default_factory=dict)


@dataclass
class SequenceSettings:
    """Sequence-level (i.e., output timeline) settings.

    These come from the CapCut draft's canvas_config / fps fields. The writer
    uses them to declare the FCP7 sequence rate and frame size.
    """
    width: int
    height: int
    frame_rate: float           # e.g. 30.0, 29.97, 25.0, 60.0
    sample_rate: int = 48000
    audio_channels: int = 2

    @property
    def is_ntsc(self) -> bool:
        """FCP7 XML splits timebase into integer + NTSC flag. 29.97 = (30, NTSC).

        Tolerance is 0.02 — wide enough for CapCut's various 29.97 stringifications
        (29.97, 29.97002997, 29.970029...) but tight enough that an honest 30.0
        stays NDF. A user shooting at exactly 30.0 fps in CapCut should not have
        their sequence silently relabeled as 29.97 drop-frame in Premiere.
        """
        for ntsc_rate in (23.976, 29.97, 59.94):
            if abs(self.frame_rate - ntsc_rate) < 0.02:
                return True
        return False

    @property
    def timebase(self) -> int:
        """FCP7's integer timebase: 24/25/30/60. NTSC rates round up."""
        if self.is_ntsc:
            return int(round(self.frame_rate))
        return int(round(self.frame_rate))


@dataclass
class Timeline:
    """The reader's output and the writer's input. Two contracts worth knowing:

    * `audio_tracks` contains EXACTLY the explicit audio tracks the source
      draft declares (BGM, voiceover, plus the audio component that CapCut
      splits off when a video-with-audio is imported). The writer emits these
      one-for-one. It does NOT synthesize additional audio tracks from video
      clips whose `MediaAsset.has_audio=True` — that would produce duplicate
      audio in Premiere because CapCut already gave us an explicit track for
      the same content.

    * `MediaAsset.has_audio` on a video asset is therefore purely informational
      after v0.1.1: the report layer uses it to flag video clips whose source
      audio is unaccounted for by any audio track, so the user knows what
      Premiere will see (silent video).
    """
    name: str
    settings: SequenceSettings
    assets: dict[str, MediaAsset] = field(default_factory=dict)
    video_tracks: list[Track] = field(default_factory=list)
    audio_tracks: list[Track] = field(default_factory=list)
    unsupported: list[UnsupportedItem] = field(default_factory=list)
    subtitle_tracks: list[SubtitleTrack] = field(default_factory=list)  # v0.2
    source_metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class SubtitleCue:
    """One timed text entry on a subtitle / caption track.

    Timing uses the same integer-microsecond model as the rest of the IR.
    `text` is plain UTF-8 with no markup — styling is not preserved in v0.2.
    """
    cue_id: str
    start_us: int
    end_us: int
    text: str
    is_auto_caption: bool = False  # True when recognize_type != 0 (ASR-generated)


@dataclass
class SubtitleTrack:
    track_id: str
    cues: list[SubtitleCue] = field(default_factory=list)

    @property
    def cue_count(self) -> int:
        return len(self.cues)

    @property
    def likely_caption_track(self) -> bool:
        return self.cue_count > 5


@dataclass
class UnsupportedItem:
    """A feature the reader saw but the IR doesn't model in v0.1.

    Kept separately from `extras` because these are the things the user needs
    to know about — they will not survive into Premiere.
    """
    category: str          # e.g. "transition", "effect", "keyframe", "text"
    detail: str            # human-readable, ends up verbatim in the report
    track_hint: str | None = None
    time_hint_us: int | None = None
