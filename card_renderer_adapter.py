"""
card_renderer_adapter.py
========================
Thin adapter between the MTM listing pipeline and card_renderer.render_card().

Bridges the existing pipeline data shapes (full_record dict + DealerInput) to
the v10 renderer's structured { machine / dealer / listing } payload.

Public API
----------
adapt_dealer_input(dealer_input, image_input_paths, *, theme) -> dict
    Build the renderer's listing + photo fields from a DealerInput + photo paths.

export_listing_card(full_record, dealer_dict, output_path, *, fail_silently) -> Path | None
    Full render + Playwright PNG export. Returns output_path on success,
    None on failure when fail_silently=True (default).
"""

from __future__ import annotations

import base64
import io
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

from card_renderer import render_card

if TYPE_CHECKING:
    from dealer_input import DealerInput

log = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Spec formatting helpers (adapter-local)
# ─────────────────────────────────────────────────────────────────────────────

def _fmt_ft_in(feet: float | None) -> str | None:
    """Convert decimal feet to a display string like 9' 11\" or 19'."""
    if feet is None:
        return None
    f_int = int(feet)
    inches = round((feet - f_int) * 12)
    if inches == 12:
        f_int += 1
        inches = 0
    return f"{f_int}' {inches}\"" if inches else f"{f_int}'"


def _dig_depth_str(specs: dict) -> str | None:
    """Return formatted dig depth string from raw registry specs."""
    val_in = specs.get("max_dig_depth_in")   # excavator / mini_ex: stored in inches
    if val_in is not None:
        return _fmt_ft_in(float(val_in) / 12.0)
    val_ft = specs.get("max_dig_depth_ft")   # backhoe_loader: stored in feet
    if val_ft is not None:
        return _fmt_ft_in(float(val_ft))
    return None


def _fmt_yd3_str(v: float | None) -> str | None:
    """Format a cubic-yard capacity value as a short display string (e.g. 1.75 → '1.75')."""
    if v is None:
        return None
    fv = float(v)
    return str(int(fv)) if fv == int(fv) else f"{fv:.2f}".rstrip("0")


# ─────────────────────────────────────────────────────────────────────────────
# Featured-template image fit helpers
# ─────────────────────────────────────────────────────────────────────────────
#
# Featured templates frame the machine in a fixed photo zone (1080×1350,
# 1008×540, etc.). Plain object-fit:cover crops the source to fill that zone,
# which can lop off attachments on wide horizontals and chop the cab on
# portraits. The standard listing-photo pipeline avoids this by contain-fitting
# the machine over a blurred cover-fill background. These helpers apply the
# same treatment to the featured-template hero.

def _trim_uniform_matte(img, color_thresh: int = 12, min_trim_frac: float = 0.02, max_trim_frac: float = 0.45):
    """Strip uniform-color border bands (letterbox/pillarbox matte) from a PIL image.

    Detects per-side matte by walking inward from each edge as long as every
    pixel in that row/column is within `color_thresh` of the corner reference
    on every channel. Caps each side at `max_trim_frac` of that dimension so a
    photo that happens to have a calm sky doesn't get gutted, and skips trims
    smaller than `min_trim_frac` so natural edge gradients aren't disturbed.
    Operates on a downsampled copy for speed; returns a crop of the original.
    """
    from PIL import Image as _Image

    w, h = img.size
    if w < 8 or h < 8:
        return img

    small_w = min(w, 240)
    small_h = max(8, int(round(h * (small_w / w))))
    s = img.resize((small_w, small_h), _Image.BILINEAR).convert("RGB")
    px = s.load()

    def _close(a, b):
        return (
            abs(a[0] - b[0]) <= color_thresh
            and abs(a[1] - b[1]) <= color_thresh
            and abs(a[2] - b[2]) <= color_thresh
        )

    def _row_uniform(y, ref):
        for x in range(small_w):
            if not _close(px[x, y], ref):
                return False
        return True

    def _col_uniform(x, ref):
        for y in range(small_h):
            if not _close(px[x, y], ref):
                return False
        return True

    max_top = int(small_h * max_trim_frac)
    max_bot = small_h - int(small_h * max_trim_frac) - 1
    max_lft = int(small_w * max_trim_frac)
    max_rgt = small_w - int(small_w * max_trim_frac) - 1

    top_ref = px[small_w // 2, 0]
    top = 0
    while top < max_top and _row_uniform(top, top_ref):
        top += 1

    bot_ref = px[small_w // 2, small_h - 1]
    bot = small_h - 1
    while bot > max_bot and _row_uniform(bot, bot_ref):
        bot -= 1
    bot_excl = bot + 1

    lft_ref = px[0, small_h // 2]
    lft = 0
    while lft < max_lft and _col_uniform(lft, lft_ref):
        lft += 1

    rgt_ref = px[small_w - 1, small_h // 2]
    rgt = small_w - 1
    while rgt > max_rgt and _col_uniform(rgt, rgt_ref):
        rgt -= 1
    rgt_excl = rgt + 1

    min_trim_h = max(1, int(small_h * min_trim_frac))
    min_trim_w = max(1, int(small_w * min_trim_frac))
    if top < min_trim_h:
        top = 0
    if (small_h - bot_excl) < min_trim_h:
        bot_excl = small_h
    if lft < min_trim_w:
        lft = 0
    if (small_w - rgt_excl) < min_trim_w:
        rgt_excl = small_w

    if top == 0 and bot_excl == small_h and lft == 0 and rgt_excl == small_w:
        return img

    sx = w / small_w
    sy = h / small_h
    box = (
        max(0, int(round(lft * sx))),
        max(0, int(round(top * sy))),
        min(w, int(round(rgt_excl * sx))),
        min(h, int(round(bot_excl * sy))),
    )
    if box[2] - box[0] < 8 or box[3] - box[1] < 8:
        return img
    return img.crop(box)


def _contain_on_blur_image(
    photo_path: str | Path,
    w: int,
    h: int,
    blur_radius: int = 42,
    foreground_scale: float = 1.18,
):
    """Return a (w, h) RGB PIL Image: blurred cover-fill background + enlarged contain-fit source on top.

    `foreground_scale` multiplies the pure-contain scale so the machine reads
    larger inside the featured zone. Anything that overflows the zone is mildly
    cropped by the canvas paste (centered), but the cover-fill blurred backdrop
    still fills any remaining gap on the short axis. Use ~1.0 for true contain;
    1.15-1.25 trades a tight edge crop for noticeably larger machine read.
    """
    from PIL import Image, ImageFilter

    src = Image.open(photo_path).convert("RGB")
    if src.size[0] <= 0 or src.size[1] <= 0:
        return Image.new("RGB", (w, h), (13, 13, 12))

    # Strip uniform letterbox/pillarbox matte before fitting so dealer uploads
    # with embedded coloured borders don't render as a frame-inside-a-frame.
    src = _trim_uniform_matte(src)
    sw, sh = src.size

    target_ratio = w / h
    src_ratio = sw / sh

    # Cover-cropped + blurred backdrop.
    if src_ratio > target_ratio:
        new_w = int(round(sh * target_ratio))
        x0 = (sw - new_w) // 2
        bg_crop = src.crop((x0, 0, x0 + new_w, sh))
    else:
        new_h = int(round(sw / target_ratio))
        y0 = (sh - new_h) // 2
        bg_crop = src.crop((0, y0, sw, y0 + new_h))
    background = bg_crop.resize((w, h), Image.LANCZOS).filter(
        ImageFilter.GaussianBlur(radius=blur_radius)
    )

    # Enlarged-contain foreground. Centered paste with a negative offset clips
    # silently against the canvas, giving a mild edge crop on the long axis
    # while preserving the full machine body on the short axis.
    scale = min(w / sw, h / sh) * max(0.1, foreground_scale)
    fw = max(1, int(round(sw * scale)))
    fh = max(1, int(round(sh * scale)))
    foreground = src.resize((fw, fh), Image.LANCZOS)
    fx = (w - fw) // 2
    fy = (h - fh) // 2
    background.paste(foreground, (fx, fy))
    return background


def _contain_on_blur_data_uri(
    photo_path: str | Path | None,
    w: int,
    h: int,
    blur_radius: int = 42,
) -> str | None:
    """Compose a contain-on-blur image and return it as a base64 JPEG data URI."""
    if not photo_path:
        return None
    p = Path(photo_path)
    if not p.is_file():
        return None
    img = _contain_on_blur_image(p, w, h, blur_radius=blur_radius)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=92)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode("ascii")


_FEATURED_PHOTO_ZONES = {
    "price_tag":          (1080, 1350),
    "auction_ticket":     (1008, 540),
    "wide_shot":          (1080, 746),
    "inventory_clean":    (1080, 1350),
    "simple_price_hero":  (1080, 1350),
    "tight_ad":           (1080, 1350),
    "clean_marketplace":  (1080, 1350),
    "split_horizon":      (1080, 1350),
    "corner_tag":         (1080, 1350),
}


# ─────────────────────────────────────────────────────────────────────────────
# Adapters
# ─────────────────────────────────────────────────────────────────────────────

def adapt_dealer_input(
    dealer_input: "DealerInput",
    image_input_paths: list[str],
    *,
    theme: str = "yellow",
    dealer_info: "dict | None" = None,
    featured_template: "str | None" = None,
) -> dict:
    """
    Build the renderer data dict from a validated DealerInput object.

    Parameters
    ----------
    dealer_input       : Validated DealerInput from the form.
    image_input_paths  : Ordered list of uploaded photo filesystem paths.
                         First path is used as the machine photo_path.
    theme              : Dealer theme ("yellow" | "red" | "blue" | "green" | "orange").
                         Sourced from dealer_info["accent_color"]; defaults to "yellow".

    Returns
    -------
    dict ready to pass as the 'dealer_dict' argument of export_listing_card().
    Keys: photo_path, listing_price, listing_hours, theme, high_flow.
    """
    high_flow_raw: Any = getattr(dealer_input, "high_flow", None)
    info = dealer_info or {}
    # Featured template — explicit kwarg wins, then dealer_info, then default.
    chosen_template = (
        featured_template
        or info.get("featured_template")
        or "clean_marketplace"
    )

    # Feature pills for simple_price_hero — dealer-confirmed flags only, max 3,
    # priority-ordered. Never inferred from specs or model names.
    _FEATURE_PILL_MAP = [
        # (attr,           match,       display_label)
        ("high_flow",        "yes",      "High Flow"),
        ("two_speed_travel", "yes",      "2-Speed"),
        ("cab_type",         "enclosed", "Enclosed Cab"),
        ("heater",           True,       "Heater"),
        ("ac",               True,       "A/C"),
        ("ride_control",     True,       "Ride Control"),
        ("air_ride_seat",    True,       "Air Ride Seat"),
        ("backup_camera",    True,       "Backup Camera"),
        ("self_leveling",    True,       "Self-Leveling"),
    ]
    feature_bullets: list[str] = []
    for attr, match, label in _FEATURE_PILL_MAP:
        val = getattr(dealer_input, attr, None)
        if val is None:
            continue
        if val == match or (match is True and bool(val)):
            feature_bullets.append(label)
        if len(feature_bullets) >= 3:
            break

    return {
        "photo_path":     image_input_paths[0] if image_input_paths else None,
        "listing_price":  getattr(dealer_input, "asking_price", None),
        "listing_hours":  dealer_input.hours,
        "year":           dealer_input.year,
        "theme":          theme,
        # Kept for callers that still inspect this flag directly
        "high_flow":      (high_flow_raw == "yes"),
        # Dealer identity — drives the dealer badge in templates that show it.
        "dealer_name":    info.get("dealer_name") or info.get("name"),
        "dealer_rep":     info.get("contact_name") or info.get("rep"),
        "dealer_phone":   info.get("phone"),
        "dealer_location":info.get("location") or info.get("city"),
        "dealer_logo":    info.get("logo_path") or info.get("logo"),
        "show_branding":  info.get("show_branding", True),
        "apply_dealer_badge": bool(info.get("apply_dealer_badge", True)),
        "featured_template": chosen_template,
        # Confirmed dealer feature labels for simple_price_hero Zone C
        "feature_bullets": feature_bullets,
    }


def _build_render_payload(full_record: dict, dealer_dict: dict) -> dict:
    """
    Assemble the { machine / dealer / listing } dict expected by render_card().
    """
    specs = full_record.get("specs") or {}
    flags = full_record.get("feature_flags") or {}

    # high_flow_available: prefer registry feature flag; fall back to dealer-entered bool
    high_flow_flag = flags.get("high_flow_available")
    if high_flow_flag is None:
        high_flow_flag = bool(dealer_dict.get("high_flow", False))

    make = (
        full_record.get("make")
        or full_record.get("manufacturer")
        or ""
    ).upper()

    eq_type = (full_record.get("equipment_type") or "").lower()

    return {
        "machine": {
            "year":                         dealer_dict.get("year") or full_record.get("year"),
            "make":                         make,
            "model":                        full_record.get("model") or "",
            "equipment_type":               eq_type,
            # CTL / SSL columns
            "horsepower_hp":                specs.get("horsepower_hp"),
            "rated_operating_capacity_lbs": specs.get("rated_operating_capacity_lbs"),
            "aux_flow_standard_gpm":        specs.get("aux_flow_standard_gpm"),
            "aux_flow_high_gpm":            specs.get("aux_flow_high_gpm"),
            "feature_flags": {
                "high_flow_available": high_flow_flag,
            },
            # Non-CTL columns (pre-formatted where needed)
            "net_hp":                   specs.get("horsepower_hp") or specs.get("net_power_hp"),
            "operating_weight_lb":      specs.get("operating_weight_lbs"),
            "lift_capacity_lb":         specs.get("lift_capacity_lbs") or specs.get("max_lift_capacity_lbs"),
            "max_lift_height_ft_str":   _fmt_ft_in(specs.get("lift_height_ft")),
            "max_forward_reach_ft_str": _fmt_ft_in(specs.get("forward_reach_ft")),
            "max_dig_depth_str":        _dig_depth_str(specs),
            "bucket_capacity_yd3":      _fmt_yd3_str(specs.get("bucket_capacity_yd3")),
            "blade_capacity_yd3":       _fmt_yd3_str(specs.get("blade_capacity_yd3")),
            "platform_height_ft_str":   _fmt_ft_in(specs.get("platform_height_ft")),
            "platform_capacity_lbs":    specs.get("platform_capacity_lbs"),
            "platform_width_ft_str":    _fmt_ft_in(specs.get("platform_width_ft")),
            "horizontal_reach_ft_str":  _fmt_ft_in(specs.get("horizontal_reach_ft")),
            "photo_path": dealer_dict.get("photo_path"),
        },
        "dealer": {
            "theme":         dealer_dict.get("theme") or "yellow",
            "name":          dealer_dict.get("dealer_name"),
            "rep":           dealer_dict.get("dealer_rep"),
            "phone":         dealer_dict.get("dealer_phone"),
            "location":      dealer_dict.get("dealer_location"),
            "logo_path":     dealer_dict.get("dealer_logo"),
            "show_branding": dealer_dict.get("show_branding", True),
            "apply_dealer_badge": bool(dealer_dict.get("apply_dealer_badge", True)),
        },
        "listing": {
            "price_usd":       dealer_dict.get("listing_price") or dealer_dict.get("price"),
            "hours":           dealer_dict.get("listing_hours") or dealer_dict.get("hours"),
            # feature_bullets: dealer-confirmed labels for simple_price_hero Zone C
            "feature_bullets": dealer_dict.get("feature_bullets") or [],
        },
        "featured_template": dealer_dict.get("featured_template") or "clean_marketplace",
    }


# ─────────────────────────────────────────────────────────────────────────────
# Export
# ─────────────────────────────────────────────────────────────────────────────

def export_listing_card(
    full_record: dict,
    dealer_dict: dict,
    output_path: Path,
    *,
    fail_silently: bool = True,
) -> Path | None:
    """
    Render the v10 hero listing card and export it to a PNG via Playwright.

    Parameters
    ----------
    full_record   : Raw registry record from lookup_machine()['full_record'].
                    Must have top-level keys: manufacturer/make, model, specs,
                    feature_flags.
    dealer_dict   : Pre-adapted dealer dict (from adapt_dealer_input()).
    output_path   : Destination path for the card PNG.
    fail_silently : If True (default), log errors and return None instead of
                    raising. Set False in tests to surface full tracebacks.

    Returns
    -------
    output_path on success, None on failure (when fail_silently=True).
    """
    try:
        payload  = _build_render_payload(full_record, dealer_dict)
        chosen   = (payload.get("featured_template") or "").lower()
        if chosen == "badge_only":
            _export_badge_only(payload, output_path)
        else:
            zone = _FEATURED_PHOTO_ZONES.get(chosen)
            if zone is not None:
                src_photo = (payload.get("machine") or {}).get("photo_path")
                fit_uri = _contain_on_blur_data_uri(src_photo, zone[0], zone[1])
                if fit_uri is not None:
                    payload["machine"]["photo_path"] = fit_uri
            # Templates that receive a composited badge after HTML render.
            # Their HTML-rendered dealer markup is suppressed here; the badge
            # renderer reapplies identity at the pixel layer afterward.
            # simple_price_hero and inventory_clean render dealer identity
            # directly in HTML (footer bar / text overlay); no composite badge.
            _COMPOSITE_BADGE_TEMPLATES = {"price_tag", "auction_ticket", "wide_shot"}
            dealer_full = dict(payload.get("dealer") or {})
            html_payload = dict(payload)
            if chosen in _COMPOSITE_BADGE_TEMPLATES:
                html_payload["dealer"] = {**dealer_full, "show_branding": False}
            else:
                html_payload["dealer"] = dealer_full
            html_str = render_card(html_payload)
            _screenshot_card(html_str, output_path)
            if chosen in _COMPOSITE_BADGE_TEMPLATES:
                _apply_standard_badge_to_card(output_path, dealer_full)
        log.info("[card] exported %s (template=%s)", output_path, chosen or "default")
        return output_path
    except Exception as exc:
        log.warning("[card] export failed: %s", exc, exc_info=True)
        if not fail_silently:
            raise
        return None


def _apply_standard_badge_to_card(output_path: Path, dealer: dict) -> None:
    """Composite the standard dealer badge onto a rendered card PNG in place.

    Reuses the same renderer + dealer fields as the listing-photo and
    badge_only paths so the featured listing image (`*_01_card.png`) shows
    the exact same badge style as photos #2-6.
    """
    from renderers.badge_renderer import apply_badge_to_photo

    if not bool(dealer.get("show_branding", True)):
        return

    logo_path = dealer.get("logo_path")
    name      = dealer.get("rep") or dealer.get("name")
    phone     = dealer.get("phone")
    accent    = dealer.get("theme") or "yellow"

    has_logo = bool(logo_path) and Path(logo_path).is_file()
    has_name = bool(name) or bool(phone)
    if not has_logo and not has_name:
        return

    apply_badge_to_photo(
        photo_path  = str(output_path),
        logo_path   = logo_path if has_logo else None,
        name        = name or "",
        phone       = phone or "",
        accent      = accent,
        output_path = str(output_path),
    )


def _export_badge_only(payload: dict, output_path: Path) -> None:
    """Export the badge_only featured-listing variant.

    Uses the first uploaded machine photo as the hero image and applies the
    same dealer badge rules as the listing-photo pipeline (logo badge if a
    logo is uploaded, text/initials badge if only name/phone, clean photo
    if no dealer identity). No price tag, no spec rail, no full overlay.

    The hero is sized to 1080×1350 (Facebook portrait) by contain-fitting
    the source over a blurred cover-fill background — same frame as the
    price_tag / wide_shot / auction_ticket exports — so all four templates
    produce parity output and the full machine remains visible regardless
    of the dealer's source aspect ratio.
    """
    from PIL import Image

    machine = payload.get("machine") or {}
    dealer  = payload.get("dealer")  or {}
    photo_path = machine.get("photo_path")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    HERO_W, HERO_H = 1080, 1350

    if not photo_path or not Path(photo_path).is_file():
        # No photo to badge — write a neutral placeholder so the pack build
        # doesn't crash; downstream code expects the card file to exist.
        Image.new("RGB", (HERO_W, HERO_H), (26, 26, 24)).save(output_path)
        return

    hero = _contain_on_blur_image(photo_path, HERO_W, HERO_H)
    hero.save(output_path, quality=92)

    # Reuse the shared helper so badge_only and the HTML-rendered featured
    # templates apply identical badge logic (single source of truth).
    _apply_standard_badge_to_card(output_path, dealer)


def _screenshot_card(html_str: str, output_path: Path) -> None:
    """
    Render HTML to PNG using Playwright headless Chromium.

    Card CSS is 1080×1350 (the design's native 4:5 frame). At
    device_scale_factor 1.0 the element screenshot is exactly 1080×1350 px
    (Facebook portrait recommended size).

    Fonts load via Google Fonts CDN; wait_until="networkidle" ensures they
    render before capture.
    """
    import concurrent.futures
    from playwright.sync_api import sync_playwright

    output_path.parent.mkdir(parents=True, exist_ok=True)

    def _playwright_render() -> None:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            try:
                page = browser.new_page(
                    viewport={"width": 1100, "height": 1400},
                    device_scale_factor=1.0,
                )
                page.set_content(html_str, wait_until="networkidle")
                card_el = page.query_selector(".card")
                if card_el is None:
                    raise RuntimeError("'.card' selector not found in rendered HTML")
                card_el.screenshot(path=str(output_path))
            finally:
                browser.close()

    # sync_playwright creates its own event loop internally and will raise
    # "Please use the Async API instead" if called inside FastAPI's asyncio loop.
    # Running in a ThreadPoolExecutor worker gives it a clean, loop-free context.
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        pool.submit(_playwright_render).result()
