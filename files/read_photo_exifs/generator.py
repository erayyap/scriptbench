#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Generates a bunch of JPEGs under ./photos with different EXIF timestamp/offset combos.
# Requires: pip install pillow piexif

from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import piexif
import os

ROOT = Path("./photos")
NESTED = ROOT / "nested"
ROOT.mkdir(parents=True, exist_ok=True)
NESTED.mkdir(parents=True, exist_ok=True)

# Tag IDs we’ll use (piexif has most, but we also drop in numeric ones for offset tags)
IMG_DT   = piexif.ImageIFD.DateTime               # 306 - "DateTime" (generic)
EXIF_DTO = piexif.ExifIFD.DateTimeOriginal        # 36867
EXIF_DTD = piexif.ExifIFD.DateTimeDigitized       # 36868
OFFSET_TIME            = 36880                     # "OffsetTime"
OFFSET_TIME_ORIGINAL   = 36881                     # "OffsetTimeOriginal"
OFFSET_TIME_DIGITIZED  = 36882                     # "OffsetTimeDigitized"

def make_base(label: str, w=640, h=360):
    img = Image.new("RGB", (w, h), (240, 240, 240))
    d = ImageDraw.Draw(img)
    text = label
    # No font requirement; default is fine across environments
    d.text((10, 10), text, fill=(0, 0, 0))
    return img

def to_bytes(s):
    if s is None:
        return None
    if isinstance(s, bytes):
        return s
    return str(s).encode("ascii", "ignore")

def save_with_exif(path: Path, *, which=None, dt=None, offset=None, generic_offset=None, bad_dt=None):
    """
    which: 'original' | 'datetime' | 'digitized' | None
    dt: 'YYYY:MM:DD HH:MM:SS' or bytes
    offset: '+HH:MM', '-HHMM', '+HH:MM:SS' (applies to the chosen field)
    generic_offset: applies to generic OffsetTime (36880), used as fallback
    bad_dt: intentionally malformed datetime string (for negative test)
    """
    img = make_base(path.name)

    # Build EXIF dict
    zeroth = {}
    exif   = {}
    gps    = {}
    first  = {}

    # Put a generic "DateTime" (306) if requested
    if which == "datetime" and dt:
        zeroth[IMG_DT] = to_bytes(dt)
    if which == "original" and dt:
        exif[EXIF_DTO] = to_bytes(dt)
    if which == "digitized" and dt:
        exif[EXIF_DTD] = to_bytes(dt)

    # Bad format case (should be ignored by a strict parser)
    if bad_dt:
        # Attach to DateTimeOriginal but in the wrong format
        exif[EXIF_DTO] = to_bytes(bad_dt)

    # Offsets: pair the right offset with the chosen field
    if which == "original" and offset:
        exif[OFFSET_TIME_ORIGINAL] = to_bytes(offset)
    elif which == "digitized" and offset:
        exif[OFFSET_TIME_DIGITIZED] = to_bytes(offset)
    elif which == "datetime" and offset:
        exif[OFFSET_TIME] = to_bytes(offset)

    # Optionally also set the generic OffsetTime (fallback)
    if generic_offset:
        exif[OFFSET_TIME] = to_bytes(generic_offset)

    exif_dict = {"0th": zeroth, "Exif": exif, "GPS": gps, "1st": first, "thumbnail": None}

    try:
        exif_bytes = piexif.dump(exif_dict)
        img.save(path, "JPEG", quality=88, exif=exif_bytes, optimize=True)
    except Exception:
        # If anything goes wrong with EXIF writing, at least save the image
        img.save(path, "JPEG", quality=88, optimize=True)

def main():
    cases = [
        # Prefer Original; with offset
        (ROOT / "01_original_with_offset.jpg", dict(which="original", dt="2019:03:04 12:05:06", offset="+03:00")),
        # Original, no offset (treat as UTC)
        (ROOT / "02_original_no_offset.jpg", dict(which="original", dt="2019:03:04 09:05:06", offset=None)),
        # Only generic DateTime with offset
        (ROOT / "03_datetime_with_offset.jpg", dict(which="datetime", dt="2018:01:01 00:00:00", offset="-07:00")),
        # Only digitized with offset
        (ROOT / "04_digitized_with_offset.jpg", dict(which="digitized", dt="2020:01:01 00:00:00", offset="+02:30")),
        # No EXIF at all
        (ROOT / "05_no_exif.jpg", dict(which=None, dt=None)),
        # Weird offset format without colon (parser should still accept)
        (ROOT / "06_original_weird_offset_nocolon.jpg", dict(which="original", dt="2017:06:15 10:00:00", offset="+0330")),
        # Offset including seconds
        (ROOT / "07_original_offset_with_seconds.jpg", dict(which="original", dt="2017:06:15 09:59:59", offset="-07:30:15")),
        # Only DateTime, no offset
        (ROOT / "08_datetime_only_no_offset.jpg", dict(which="datetime", dt="2005:01:01 00:00:00", offset=None)),
        # Nested folder; very old UTC
        (NESTED / "09_original_very_old_utc.jpg", dict(which="original", dt="1999:12:31 23:59:59", offset="+00:00")),
        # Bad datetime format (should be ignored by strict parser)
        (ROOT / "10_bad_format.jpg", dict(which="original", dt=None, bad_dt="2019-03-04 12:05:06", offset="+00:00")),
        # Original time present but only the generic OffsetTime is set (fallback behavior)
        (ROOT / "11_original_generic_offset.jpg", dict(which="original", dt="2019:03:04 12:05:06", generic_offset="+01:00")),
        # Digitized time present but only generic OffsetTime (fallback)
        (ROOT / "12_digitized_generic_offset.jpg", dict(which="digitized", dt="2019:03:04 12:05:07", generic_offset="-02:00")),
        # Bytes values for both datetime and offset
        (ROOT / "13_datetime_bytes_values.jpg", dict(which="datetime", dt=b"2010:10:10 10:10:10", offset=b"+05:00")),
    ]

    for path, kwargs in cases:
        path.parent.mkdir(parents=True, exist_ok=True)
        save_with_exif(path, **kwargs)

    print(f"Made {len(cases)} images in {ROOT.resolve()}")

if __name__ == "__main__":
    main()
