"""Magic-byte file type detection for CapCut cache asset extension normalization.

No external dependencies. Reads only the first 16 bytes of each file.

Detected types
--------------
  image/png    .png   — 89 50 4E 47 0D 0A 1A 0A
  image/jpeg   .jpg   — FF D8 FF
  image/gif    .gif   — GIF87a / GIF89a
  image/webp   .webp  — RIFF....WEBP
  audio/wav    .wav   — RIFF....WAVE
  video/mp4    .mp4   — ftyp box, non-audio brand
  audio/mp4    .m4a   — ftyp box, brand M4A / M4B / M4P
  audio/mpeg   .mp3   — ID3 header or raw frame sync FF FB / FF F3 / FF F2
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

_READ_BYTES = 16

# First 3 bytes of the 4-byte brand field identify M4 audio containers.
_M4_AUDIO_BRANDS: frozenset[bytes] = frozenset({b"M4A", b"M4B", b"M4P"})

# Extension pairs considered equivalent — normalization is skipped between them.
_COMPATIBLE_PAIRS: tuple[frozenset[str], ...] = (
    frozenset({".jpg", ".jpeg"}),
    frozenset({".mp4", ".m4v"}),   # same ISO Base Media container
)


@dataclass(frozen=True)
class FileType:
    mime: str
    ext: str  # canonical extension with leading dot, e.g. ".m4a"


def detect_file_type(path: str | Path) -> FileType | None:
    """Read magic bytes from *path* and return the detected FileType, or None.

    Returns None if the type is unrecognised or the file cannot be read.
    """
    try:
        with open(path, "rb") as f:
            header = f.read(_READ_BYTES)
    except OSError:
        return None
    return _classify(header)


def should_normalize_extension(src_suffix: str, detected_ext: str | None) -> bool:
    """Return True if *src_suffix* should be replaced with *detected_ext*.

    Rules:
      - No detected type → never normalize.
      - No source extension → always add the detected extension.
      - Same extension (case-insensitive) → no change.
      - Extensions in the same compatible pair (e.g. .jpg/.jpeg) → no change.
      - Otherwise → normalize.
    """
    if not detected_ext:
        return False
    if not src_suffix:
        return True
    s = src_suffix.lower()
    d = detected_ext.lower()
    if s == d:
        return False
    for pair in _COMPATIBLE_PAIRS:
        if s in pair and d in pair:
            return False
    return True


# ─── internal classifier ──────────────────────────────────────────────────────

def _classify(h: bytes) -> FileType | None:
    n = len(h)
    if n < 4:
        return None

    # PNG
    if n >= 8 and h[:8] == b"\x89PNG\r\n\x1a\n":
        return FileType("image/png", ".png")

    # JPEG
    if h[:3] == b"\xff\xd8\xff":
        return FileType("image/jpeg", ".jpg")

    # GIF
    if h[:6] in (b"GIF87a", b"GIF89a"):
        return FileType("image/gif", ".gif")

    # WebP: "RIFF" at 0-3, "WEBP" at 8-11
    if h[:4] == b"RIFF" and n >= 12 and h[8:12] == b"WEBP":
        return FileType("image/webp", ".webp")

    # WAV: "RIFF" at 0-3, "WAVE" at 8-11
    if h[:4] == b"RIFF" and n >= 12 and h[8:12] == b"WAVE":
        return FileType("audio/wav", ".wav")

    # ISO Base Media File Format: "ftyp" box at bytes 4-7.
    # Major brand at bytes 8-11; we check the first 3 chars.
    if n >= 12 and h[4:8] == b"ftyp":
        brand3 = h[8:11]
        if brand3 in _M4_AUDIO_BRANDS:
            return FileType("audio/mp4", ".m4a")
        return FileType("video/mp4", ".mp4")

    # MP3: ID3v2 tag header
    if h[:3] == b"ID3":
        return FileType("audio/mpeg", ".mp3")

    # MP3: raw MPEG Layer 3 frame sync (FF FB / FF F3 / FF F2)
    if n >= 2 and h[0] == 0xFF and h[1] in (0xFB, 0xF3, 0xF2):
        return FileType("audio/mpeg", ".mp3")

    return None
