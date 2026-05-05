"""
walkaround_generator.py
=======================
MTM Walkaround Video Generator (async-friendly, vertical 1080x1920).

Produces a 1080x1920 H.264 MP4 with a silent AAC stereo track, intro card,
per-photo Ken-Burns slides, and outro card. Designed to be invoked from
`asyncio.to_thread(...)` by an async job runner. Synchronous internals.

Public API:
    generate_walkaround_video(
        photos: list[str],
        output_path: str,
        year: int,
        make: str,
        model: str,
        dealer_name: Optional[str] = None,
        dealer_phone: Optional[str] = None,
        accent_color: Optional[str] = None,
    ) -> str

    walkaround_filename(year, make, model) -> str
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Optional

from PIL import Image, ImageDraw, ImageFont

# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────

_FFMPEG_CANDIDATES = [
    r"C:\ffmpeg\ffmpeg\bin\ffmpeg.exe",
    "/usr/bin/ffmpeg",
    "/usr/local/bin/ffmpeg",
    "ffmpeg",
]

SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff", ".tif"}

TARGET_W = 1080
TARGET_H = 1920
FPS = 30
SLIDE_SECS = 3.0          # per-photo slide duration
INTRO_SECS = 2.0
OUTRO_SECS = 2.5
MAX_PHOTOS = 10
MIN_PHOTOS = 4
DEFAULT_TIMEOUT = 240
DEFAULT_ACCENT = "#FFCC00"

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

_SANITIZE_RE = re.compile(r"[^A-Za-z0-9_-]+")


def _sanitize_part(part: str) -> str:
    s = _SANITIZE_RE.sub("_", str(part or "")).strip("_-")
    return s or "x"


def walkaround_filename(year, make: str, model: str) -> str:
    """Return a filesystem-safe filename for the walkaround MP4."""
    y = _sanitize_part(year)
    mk = _sanitize_part(make)
    md = _sanitize_part(model)
    return f"{y}_{mk}_{md}_Walkaround.mp4"


def _find_ffmpeg() -> str:
    for candidate in _FFMPEG_CANDIDATES:
        if os.path.isfile(candidate):
            return candidate
        found = shutil.which(candidate)
        if found:
            return found
    raise RuntimeError("ffmpeg not found on PATH or known install locations.")


def check_ffmpeg_available() -> None:
    """Raise RuntimeError if ffmpeg cannot be located. Call before starting a job."""
    _find_ffmpeg()


def _load_font(size: int) -> ImageFont.ImageFont:
    """Best-effort font load; fall back to default."""
    candidates = [
        r"C:\Windows\Fonts\arialbd.ttf",
        r"C:\Windows\Fonts\arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for c in candidates:
        try:
            if os.path.isfile(c):
                return ImageFont.truetype(c, size)
        except Exception:
            continue
    return ImageFont.load_default()


def _parse_accent(accent: Optional[str]) -> tuple[int, int, int]:
    """Parse '#RRGGBB' or named token to RGB."""
    if not accent:
        accent = DEFAULT_ACCENT
    a = str(accent).strip()
    named = {
        "yellow": "#FFCC00",
        "orange": "#FF7A00",
        "red": "#E53935",
        "blue": "#1976D2",
        "green": "#2E7D32",
        "black": "#111111",
        "white": "#FFFFFF",
    }
    if a.lower() in named:
        a = named[a.lower()]
    if a.startswith("#") and len(a) == 7:
        try:
            return (int(a[1:3], 16), int(a[3:5], 16), int(a[5:7], 16))
        except Exception:
            pass
    return (255, 204, 0)


def _draw_centered_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    y: int,
    font: ImageFont.ImageFont,
    fill,
    canvas_w: int = TARGET_W,
) -> int:
    """Draw text horizontally centered. Returns text height."""
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    draw.text(((canvas_w - tw) // 2, y), text, font=font, fill=fill)
    return th


def _make_intro_card(
    out_path: str,
    year: int,
    make: str,
    model: str,
    accent_rgb: tuple[int, int, int],
) -> None:
    img = Image.new("RGB", (TARGET_W, TARGET_H), (15, 15, 15))
    draw = ImageDraw.Draw(img)

    # Accent bar
    bar_h = 14
    draw.rectangle([0, TARGET_H // 2 - 220, TARGET_W, TARGET_H // 2 - 220 + bar_h], fill=accent_rgb)

    title_font = _load_font(120)
    sub_font = _load_font(72)
    label_font = _load_font(48)

    label = "WALKAROUND"
    _draw_centered_text(draw, label, TARGET_H // 2 - 360, label_font, accent_rgb)

    year_str = str(year) if year else ""
    if year_str:
        _draw_centered_text(draw, year_str, TARGET_H // 2 - 160, sub_font, (230, 230, 230))

    mk = (make or "").upper()
    if mk:
        _draw_centered_text(draw, mk, TARGET_H // 2 - 60, title_font, (255, 255, 255))

    md = str(model or "")
    if md:
        _draw_centered_text(draw, md, TARGET_H // 2 + 90, title_font, (255, 255, 255))

    img.save(out_path, "PNG")


def _make_outro_card(
    out_path: str,
    dealer_name: Optional[str],
    dealer_phone: Optional[str],
    accent_rgb: tuple[int, int, int],
) -> None:
    img = Image.new("RGB", (TARGET_W, TARGET_H), (15, 15, 15))
    draw = ImageDraw.Draw(img)

    bar_h = 14
    draw.rectangle([0, TARGET_H // 2 - 220, TARGET_W, TARGET_H // 2 - 220 + bar_h], fill=accent_rgb)

    cta_font = _load_font(72)
    name_font = _load_font(96)
    phone_font = _load_font(84)

    _draw_centered_text(draw, "CALL FOR DETAILS", TARGET_H // 2 - 360, cta_font, accent_rgb)

    y = TARGET_H // 2 - 120
    if dealer_name:
        _draw_centered_text(draw, str(dealer_name), y, name_font, (255, 255, 255))
        y += 160
    if dealer_phone:
        _draw_centered_text(draw, str(dealer_phone), y, phone_font, (230, 230, 230))

    img.save(out_path, "PNG")


def _letterbox_photo(src: str, dst: str) -> bool:
    """Letterbox a source photo onto a 1080x1920 black canvas. Returns True on success."""
    try:
        with Image.open(src) as im:
            im = im.convert("RGB")
            sw, sh = im.size
            scale = min(TARGET_W / sw, TARGET_H / sh)
            new_w = max(1, int(sw * scale))
            new_h = max(1, int(sh * scale))
            resized = im.resize((new_w, new_h), Image.LANCZOS)
            canvas = Image.new("RGB", (TARGET_W, TARGET_H), (0, 0, 0))
            canvas.paste(resized, ((TARGET_W - new_w) // 2, (TARGET_H - new_h) // 2))
            canvas.save(dst, "PNG")
        return True
    except Exception as exc:
        print(f"  [Walkaround] photo letterbox failed for {src}: {exc}")
        return False


# ─────────────────────────────────────────────────────────────────────────────
# Filter graph
# ─────────────────────────────────────────────────────────────────────────────

def _build_filter_complex(n_photos: int) -> str:
    """
    Build a filter_complex graph: intro + N photo zoompan slides + outro,
    concatenated. Inputs order:
      [0] intro_card.png  (loop, t=INTRO_SECS)
      [1..n] photo_NN.png (loop, t=SLIDE_SECS each)
      [n+1] outro_card.png (loop, t=OUTRO_SECS)
    All inputs are already 1080x1920 so we just set sar=1 and run zoompan
    on photo inputs for a subtle ken-burns effect.
    """
    parts: list[str] = []
    labels: list[str] = []

    intro_frames = max(1, int(round(INTRO_SECS * FPS)))
    slide_frames = max(1, int(round(SLIDE_SECS * FPS)))
    outro_frames = max(1, int(round(OUTRO_SECS * FPS)))

    # Intro
    parts.append(
        f"[0:v]setsar=1,fps={FPS},format=yuv420p,trim=duration={INTRO_SECS},setpts=PTS-STARTPTS[vintro]"
    )
    labels.append("[vintro]")

    # Photo slides with zoompan
    for i in range(n_photos):
        in_idx = i + 1
        # zoompan: start at 1.0, end at 1.08 across slide_frames
        zoom_expr = f"min(zoom+0.0008,1.08)"
        parts.append(
            f"[{in_idx}:v]setsar=1,fps={FPS},format=yuv420p,"
            f"zoompan=z='{zoom_expr}':d={slide_frames}:s={TARGET_W}x{TARGET_H}:fps={FPS},"
            f"trim=duration={SLIDE_SECS},setpts=PTS-STARTPTS[vp{i}]"
        )
        labels.append(f"[vp{i}]")

    # Outro
    out_idx = n_photos + 1
    parts.append(
        f"[{out_idx}:v]setsar=1,fps={FPS},format=yuv420p,trim=duration={OUTRO_SECS},setpts=PTS-STARTPTS[voutro]"
    )
    labels.append("[voutro]")

    # Concat
    concat_inputs = "".join(labels)
    parts.append(f"{concat_inputs}concat=n={len(labels)}:v=1:a=0[vout]")

    return ";".join(parts)


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def generate_walkaround_video(
    photos: "list[str]",
    output_path: str,
    year: int,
    make: str,
    model: str,
    dealer_name: Optional[str] = None,
    dealer_phone: Optional[str] = None,
    accent_color: Optional[str] = None,
) -> str:
    """
    Render a 1080x1920 walkaround MP4.

    Raises ValueError if fewer than MIN_PHOTOS valid photos are provided.
    Silently truncates to MAX_PHOTOS.
    Returns the absolute output path.
    """
    valid = [
        p for p in (photos or [])
        if p and os.path.isfile(p) and Path(p).suffix.lower() in SUPPORTED_EXTENSIONS
    ]
    if len(valid) < MIN_PHOTOS:
        raise ValueError(
            f"Walkaround requires at least {MIN_PHOTOS} machine photos (got {len(valid)})."
        )
    if len(valid) > MAX_PHOTOS:
        valid = valid[:MAX_PHOTOS]

    ffmpeg = _find_ffmpeg()
    out_dir = os.path.dirname(os.path.abspath(output_path))
    os.makedirs(out_dir, exist_ok=True)

    tmp_dir = os.path.join(out_dir, "_walkaround_tmp")
    os.makedirs(tmp_dir, exist_ok=True)

    accent_rgb = _parse_accent(accent_color)

    try:
        # 1. Build cards
        intro_path = os.path.join(tmp_dir, "intro.png")
        outro_path = os.path.join(tmp_dir, "outro.png")
        _make_intro_card(intro_path, year, make, model, accent_rgb)
        _make_outro_card(outro_path, dealer_name, dealer_phone, accent_rgb)

        # 2. Letterbox photos to PNG
        photo_pngs: list[str] = []
        for i, src in enumerate(valid):
            dst = os.path.join(tmp_dir, f"photo_{i:02d}.png")
            if _letterbox_photo(src, dst):
                photo_pngs.append(dst)

        if len(photo_pngs) < MIN_PHOTOS:
            raise RuntimeError(
                f"Only {len(photo_pngs)} photo(s) preprocessed successfully — need {MIN_PHOTOS}."
            )

        n = len(photo_pngs)

        # 3. Build ffmpeg command
        cmd: list[str] = [ffmpeg, "-y"]
        cmd += ["-loop", "1", "-t", str(INTRO_SECS), "-i", intro_path]
        for p in photo_pngs:
            cmd += ["-loop", "1", "-t", str(SLIDE_SECS), "-i", p]
        cmd += ["-loop", "1", "-t", str(OUTRO_SECS), "-i", outro_path]
        # Silent stereo audio source
        cmd += [
            "-f", "lavfi",
            "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
        ]

        fc = _build_filter_complex(n)
        cmd += [
            "-filter_complex", fc,
            "-map", "[vout]",
            "-map", f"{n + 2}:a",
            "-c:v", "libx264",
            "-crf", "20",
            "-preset", "medium",
            "-pix_fmt", "yuv420p",
            "-r", str(FPS),
            "-c:a", "aac",
            "-b:a", "128k",
            "-shortest",
            "-movflags", "+faststart",
            output_path,
        ]

        print(f"  [Walkaround] ffmpeg encoding {n} photos -> {os.path.basename(output_path)}")

        # 4. Run with single retry on non-zero exit
        attempts = 0
        last_err = ""
        while attempts < 2:
            attempts += 1
            try:
                result = subprocess.run(
                    cmd, capture_output=True, text=True, timeout=DEFAULT_TIMEOUT
                )
            except subprocess.TimeoutExpired:
                # Don't retry on timeout
                raise

            if result.returncode == 0 and os.path.isfile(output_path):
                break

            last_err = "\n".join(result.stderr.strip().splitlines()[-15:])
            print(f"  [Walkaround] ffmpeg attempt {attempts} failed (code {result.returncode}). "
                  f"Tail:\n{last_err}")

            if attempts < 2:
                time.sleep(2)

        if not os.path.isfile(output_path) or os.path.getsize(output_path) == 0:
            raise RuntimeError(f"ffmpeg failed after retry. Stderr tail:\n{last_err}")

        size_kb = os.path.getsize(output_path) // 1024
        print(f"  [Walkaround] Done: {size_kb} KB, {n} slides")
        return os.path.abspath(output_path)

    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
