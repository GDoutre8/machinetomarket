"""Build category-aware Verify Specs card payloads for the template.

Reads resolved_specs (output of the spec resolver) plus the per-type card
definitions in spec_card_map and returns a flat list of dicts the
verify_specs.html partial can iterate without any per-type branching.
"""

from typing import Any

from spec_card_map import get_cards_for


def _fmt_int(v) -> str:
    try:
        return f"{int(v):,}"
    except (TypeError, ValueError):
        return ""


def _fmt_dec(v, places: int = 1) -> str:
    try:
        f = float(v)
        s = f"{f:.{places}f}"
        # Trim trailing zeros for display, but keep ".0" → "" rather than "."
        s = s.rstrip("0").rstrip(".")
        return s
    except (TypeError, ValueError):
        return ""


def _fmt_string(v) -> str:
    if v is None:
        return ""
    s = str(v).strip()
    return s


def _read_alias(specs: dict, aliases: list[str]):
    """Return the first non-empty value across the alias list."""
    for k in aliases:
        v = specs.get(k)
        if v is None:
            continue
        if isinstance(v, str) and not v.strip():
            continue
        return v
    return None


def _format_value(card: dict, raw_val: Any) -> str:
    t = card.get("type", "string")
    if t == "int":
        return _fmt_int(raw_val)
    if t == "float":
        return _fmt_dec(raw_val, card.get("decimals", 1))
    return _fmt_string(raw_val)


def build_spec_cards(equipment_type: str,
                     resolved_specs: dict,
                     engine_sub: str = "") -> list[dict[str, Any]]:
    """Return a list of fully-rendered card dicts for the template.

    Each output dict:
        key, label, short, index, type, unit, sub, required, warn,
        display     — formatted display string ("" when missing)
        oem_value   — same string, used for the data-oem attribute
        has_value   — bool, True when display is non-empty
    """
    specs = resolved_specs or {}
    cards_def = get_cards_for(equipment_type)
    out: list[dict[str, Any]] = []
    for card in cards_def:
        raw = _read_alias(specs, card.get("aliases", [card["key"]]))
        display = _format_value(card, raw)

        # Engine card pulls its sub-caption from a dynamic source
        # (displacement · tier · fuel) computed in the route handler.
        sub = card.get("sub", "")
        if card.get("sub_dynamic") == "engine_sub" and engine_sub:
            sub = engine_sub

        # Fallback display when nothing resolved — preserve em-dash for the
        # user to overwrite. Engine card has its own placeholder.
        if not display:
            if card["key"] == "engine_model":
                display = "OEM Data Pending"
            else:
                display = "—"

        out.append({
            "key":      card["key"],
            "label":    card["label"],
            "short":    card.get("short", card["label"].upper()),
            "index":    card["index"],
            "type":     card["type"],
            "unit":     card.get("unit", ""),
            "sub":      sub,
            "required": bool(card.get("required", False)),
            "warn":     bool(card.get("warn", False)),
            "display":  display,
            "oem_value": display,
            "has_value": bool(display and display != "—"),
        })
    return out
