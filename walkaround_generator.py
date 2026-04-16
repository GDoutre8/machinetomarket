"""
walkaround_generator.py
=======================
MTM Walkaround Video Generator

Produces a clean slideshow MP4 from machine photos using ffmpeg.
Each photo is shown for a configurable duration with a crossfade
transition between slides.  No audio, ready for dealers to add music.

Target spec:
  - 1080×1080 square (Facebook Marketplace / Instagram compatible)
  - 3 seconds per photo, 0.5s crossfade transition
  - H.264/AAC, CRF 23, fast preset, yuv420p (widest playback compat)
  - ~1–3 MB per photo at typical phone-photo resolution

Usage:
    from walkaround_generator import generate_walkaround_video
    path = generate_walkaround_video(
        image_paths=["img1.jpg", "img2.jpg"],
        output_path="walkaround.mp4",
    )
"""

from __future__ import annotations
import os
import subprocess
import shutil
from pathlib import Path

# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────

# Check common explicit locations first; fall back to PATH
_FFMPEG_CANDIDATES = [
    r"C:\ffmpeg\ffmpeg\bin\ffmpeg.exe",  # Windows explicit install
    "/usr/bin/ffmpeg",                    # Linux system install
    "/usr/local/bin/ffmpeg",              # Linux local install
    "ffmpeg",                             # PATH fallback (any platform)
]

SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff", ".tif", ".heic"}

DEFAULT_TARGET_W   = 1080
DEFAULT_TARGET_H   = 1080
DEFAULT_SLIDE_SECS = 3.0
DEFAULT_TRANS_SECS = 0.5
DEFAULT_CRF        = 23
DEFAULT_PRESET     = "fast"
DEFAULT_TIMEOUT    = 180   # seconds


# ─────────────────────────────────────────────────────────────────────────────
# ffmpeg discovery
# ─────────────────────────────────────────────────────────────────────────────

def _find_ffmpeg() -> str:
    """Return path to ffmpeg binary, or raise RuntimeError."""
    for candidate in _FFMPEG_CANDIDATES:
        if os.path.isfile(candidate):
            return candidate
        found = shutil.which(candidate)
        if found:
            return found
    raise RuntimeError(
        "ffmpeg not found. Install ffmpeg and ensure it is on PATH "
        "(e.g. `apt-get install ffmpeg` on Linux, or https://ffmpeg.org on Windows)."
    )


# ─────────────────────────────────────────────────────────────────────────────
# Filter-complex builder
# ─────────────────────────────────────────────────────────────────────────────

def _build_filter_complex(
    n: int,
    target_w: int,
    target_h: int,
    transition_secs: float,
    slide_secs: float,
) -> tuple[str, str]:
    """
    Build an ffmpeg filter_complex string for N inputs.

    Returns (filter_complex_str, output_label).
    For N=1 returns a simple scale+crop with no xfade.
    """
    scale_filter = (
        f"scale={target_w}:{target_h}:force_original_aspect_ratio=increase,"
        f"crop={target_w}:{target_h}"
    )

    parts: list[str] = []

    # Scale/crop each input
    for i in range(n):
        parts.append(f"[{i}:v]{scale_filter}[v{i}]")

    if n == 1:
        return ";".join(parts), "v0"

    # xfade chain
    # offset[i] = (i+1) * (slide_secs - transition_secs)
    step = slide_secs - transition_secs
    prev_label = "v0"
    for i in range(n - 1):
        offset = round((i + 1) * step, 6)
        next_label = f"t{i}" if i < n - 2 else "out"
        parts.append(
            f"[{prev_label}][v{i + 1}]"
            f"xfade=transition=fade:duration={transition_secs}:offset={offset}"
            f"[{next_label}]"
        )
        prev_label = next_label

    return ";".join(parts), "out"


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def generate_walkaround_video(
    image_paths: "list[str]",
    output_path: str,
    target_w: int   = DEFAULT_TARGET_W,
    target_h: int   = DEFAULT_TARGET_H,
    slide_secs: float        = DEFAULT_SLIDE_SECS,
    transition_secs: float   = DEFAULT_TRANS_SECS,
    crf: int                 = DEFAULT_CRF,
    preset: str              = DEFAULT_PRESET,
    timeout: int             = DEFAULT_TIMEOUT,
    ffmpeg_path: "str | None" = None,
) -> str:
    """
    Generate a walkaround slideshow video from a list of image paths.

    Parameters
    ----------
    image_paths     : Ordered list of absolute paths to source images.
    output_path     : Where to write the output .mp4.
    target_w/h      : Output frame dimensions (default 1080×1080).
    slide_secs      : How long each photo is visible (default 3.0 s).
    transition_secs : Crossfade duration between photos (default 0.5 s).
    crf             : H.264 quality factor (lower = better, default 23).
    preset          : H.264 encoding speed preset (default "fast").
    timeout         : Max seconds to wait for ffmpeg (default 180 s).
    ffmpeg_path     : Override ffmpeg binary path; auto-detected if None.

    Returns
    -------
    Absolute path to the written .mp4 file.

    Raises
    ------
    ValueError      : No valid images provided.
    RuntimeError    : ffmpeg not found or encoding failed.
    subprocess.TimeoutExpired : ffmpeg took longer than `timeout` seconds.
    """
    # Filter to supported images that actually exist
    valid = [
        p for p in image_paths
        if os.path.isfile(p) and Path(p).suffix.lower() in SUPPORTED_EXTENSIONS
    ]
    if not valid:
        raise ValueError("No valid image files found in image_paths.")

    ffmpeg = ffmpeg_path or _find_ffmpeg()
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

    n = len(valid)
    # Each input needs duration = slide + transition to cover overlap,
    # except the last which just needs slide_secs.
    input_duration = slide_secs + transition_secs

    # Build ffmpeg command as a list (avoids Windows shell quoting problems)
    cmd: list[str] = [ffmpeg, "-y"]

    for i, path in enumerate(valid):
        dur = input_duration if i < n - 1 else slide_secs
        cmd += ["-loop", "1", "-t", str(dur), "-i", path]

    if n == 1:
        # Single image — simple encode, no filter_complex needed
        cmd += [
            "-vf", f"scale={target_w}:{target_h}:force_original_aspect_ratio=increase,crop={target_w}:{target_h}",
            "-c:v", "libx264",
            "-crf", str(crf),
            "-preset", preset,
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            output_path,
        ]
    else:
        fc, out_label = _build_filter_complex(n, target_w, target_h, transition_secs, slide_secs)
        cmd += [
            "-filter_complex", fc,
            "-map", f"[{out_label}]",
            "-c:v", "libx264",
            "-crf", str(crf),
            "-preset", preset,
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            output_path,
        ]

    print(f"  [Video] Encoding {n} photos -> {os.path.basename(output_path)}")

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
    )

    if result.returncode != 0:
        # Surface the last 10 lines of stderr for diagnosis
        stderr_tail = "\n".join(result.stderr.strip().splitlines()[-10:])
        raise RuntimeError(
            f"ffmpeg exited with code {result.returncode}.\n{stderr_tail}"
        )

    if not os.path.isfile(output_path):
        raise RuntimeError("ffmpeg completed but output file was not created.")

    size_kb = os.path.getsize(output_path) // 1024
    duration_est = round(n * slide_secs - (n - 1) * transition_secs, 1)
    print(f"  [Video] Done: {size_kb} KB, ~{duration_est}s, {n} slides")

    return os.path.abspath(output_path)
