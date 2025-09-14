#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Scan JPEGs in "./photos" and print the earliest original capture time as ISO 8601 UTC.
Prefers DateTimeOriginal; falls back to DateTime, then DateTimeDigitized.
Respects EXIF OffsetTime* when present. Prints exactly: ANSWER=YYYY-MM-DDTHH:MM:SSZ
If no usable timestamps are found, prints: ANSWER=
"""

from __future__ import annotations

import sys
import re
from pathlib import Path
from datetime import datetime, timezone, timedelta

try:
    from PIL import Image, ExifTags, ImageFile
except ImportError:
    print("ANSWER=", flush=True)
    sys.exit(0)

# In case of slightly corrupted files
ImageFile.LOAD_TRUNCATED_IMAGES = True

# EXIF tag IDs (per EXIF spec)
TAG_DATETIME = 306                 # "DateTime"
TAG_DATETIME_ORIGINAL = 36867      # "DateTimeOriginal"
TAG_DATETIME_DIGITIZED = 36868     # "DateTimeDigitized"
TAG_OFFSET_TIME = 36880            # "OffsetTime"
TAG_OFFSET_TIME_ORIGINAL = 36881   # "OffsetTimeOriginal"
TAG_OFFSET_TIME_DIGITIZED = 36882  # "OffsetTimeDigitized"

# Accept common .jpg/.jpeg (case-insensitive)
PHOTO_DIR = Path("./photos")
JPEG_EXTS = {".jpg", ".jpeg"}


def _as_str(x) -> str | None:
    if x is None:
        return None
    if isinstance(x, bytes):
        try:
            return x.decode("utf-8", "ignore").strip()
        except Exception:
            return None
    try:
        return str(x).strip()
    except Exception:
        return None


def parse_exif_datetime(val: str | bytes | None) -> datetime | None:
    """
    Parse EXIF date/time in the standard "YYYY:MM:DD HH:MM:SS" format.
    Returns naive datetime (no tzinfo). None if parse fails.
    """
    s = _as_str(val)
    if not s:
        return None
    # Some cameras might include weird nulls/spaces
    s = s.strip().replace("\x00", "")
    for fmt in ("%Y:%m:%d %H:%M:%S",):
        try:
            return datetime.strptime(s, fmt)
        except Exception:
            pass
    return None


_OFFSET_RE = re.compile(r"^([+-])(\d{2}):?(\d{2})(?::?(\d{2}))?$")


def parse_offset_to_tzinfo(val: str | bytes | None):
    """
    Convert EXIF OffsetTime-like string into a datetime.timezone.
    Accepts +HH:MM, -HH:MM, +HHMM, -HHMM, optional :SS or SS at the end.
    Returns None if not parseable.
    """
    s = _as_str(val)
    if not s:
        return None
    m = _OFFSET_RE.match(s)
    if not m:
        return None
    sign = 1 if m.group(1) == "+" else -1
    hh = int(m.group(2))
    mm = int(m.group(3))
    ss = int(m.group(4) or 0)
    delta = timedelta(hours=hh, minutes=mm, seconds=ss)
    return timezone(sign * delta)


def get_best_timestamp_utc(img_path: Path) -> datetime | None:
    """
    Return the best UTC datetime for the given image, or None if none found.
    Preference order and offset pairing:
      1) DateTimeOriginal (+ OffsetTimeOriginal, else OffsetTime)
      2) DateTime        (+ OffsetTime)
      3) DateTimeDigitized (+ OffsetTimeDigitized, else OffsetTime)
    If no offset is present, treat the timestamp as UTC (tzinfo=UTC).
    """
    try:
        with Image.open(img_path) as im:
            exif = im.getexif()
    except Exception:
        return None

    if not exif:
        return None

    # Try in priority order
    candidates = [
        (TAG_DATETIME_ORIGINAL, (TAG_OFFSET_TIME_ORIGINAL, TAG_OFFSET_TIME)),
        (TAG_DATETIME,         (TAG_OFFSET_TIME,)),
        (TAG_DATETIME_DIGITIZED, (TAG_OFFSET_TIME_DIGITIZED, TAG_OFFSET_TIME)),
    ]

    for dt_tag, offset_tags in candidates:
        raw_dt = exif.get(dt_tag)
        dt = parse_exif_datetime(raw_dt)
        if dt is None:
            continue

        tzinfo = None
        for ot in offset_tags:
            raw_off = exif.get(ot)
            tzinfo = parse_offset_to_tzinfo(raw_off)
            if tzinfo:
                break

        if tzinfo is None:
            # No offset info: treat as already UTC (do not guess local tz).
            aware = dt.replace(tzinfo=timezone.utc)
        else:
            aware = dt.replace(tzinfo=tzinfo).astimezone(timezone.utc)

        # Drop sub-second (EXIF standard string has no subseconds anyway)
        return aware.replace(microsecond=0)

    return None


def main() -> int:
    if not PHOTO_DIR.exists() or not PHOTO_DIR.is_dir():
        print("ANSWER=", flush=True)
        return 0

    earliest: datetime | None = None

    # Sort for deterministic traversal (not required, but nice)
    for p in sorted(PHOTO_DIR.rglob("*")):
        if p.is_file() and p.suffix.lower() in JPEG_EXTS:
            ts = get_best_timestamp_utc(p)
            if ts is None:
                continue
            if earliest is None or ts < earliest:
                earliest = ts

    if earliest is None:
        print("ANSWER=", flush=True)
        return 0

    out = earliest.strftime("%Y-%m-%dT%H:%M:%SZ")
    print(f"ANSWER={out}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
