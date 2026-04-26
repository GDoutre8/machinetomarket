"""
spec_resolver.py
Main orchestrator.

Entry points
------------
resolve(input: ResolverInput) -> ResolverOutput
resolve_from_dict(d: dict)     -> ResolverOutput

Orchestration order (matches spec doc §3)
-----------------------------------------
1.  Validate input
2.  Build RegistryEntry from registry_match dict
3.  Re-run option detection on raw_listing_text   ← always from raw, not pre-parsed
4.  Re-run numeric claim extraction
5.  Parse year from raw text (best-effort)
6.  For each field family, build ResolutionContext and call field resolver
7.  Collect resolved specs, ui_hints, requires_confirm, per_field_metadata,
    warnings, and audit traces
8.  Compute overall_resolution_status and safe_for_listing_injection
9.  Return ResolverOutput

Design rules enforced here
--------------------------
- _ prefix fields go to ui_hints, NOT resolved_specs
- requires_confirm is deduplicated and sorted
- Seller claims never silently override registry values
- Fail-closed: unresolved fields are omitted from resolved_specs
- Audit trail is built and attached (available for logging/debugging)
"""

from __future__ import annotations

import re
import uuid
from typing import Any, Dict, List, Optional, Tuple

from .types import (
    FieldBehavior, FieldMeta, FieldSource, MatchType, OverallStatus,
    RegistryEntry, ResolverInput, ResolverOutput, ResolverWarning,
    WarningSeverity,
)
from .option_detector import detect_options, extract_numeric_claims, DetectedOptions
from .confidence_policy import (
    determine_overall_status, is_safe_for_listing_injection,
    HARD_FLOOR_CONFIDENCE,
)
from .audit_trail import AuditTrail, create_audit_trail, FieldTrace

from .field_resolvers._base import ResolutionContext, FieldResolution
from .field_resolvers import (
    horsepower,
    weight,
    hydraulic_flow,
    roc,
    tipping_load,
    dig_depth,
    breakout_force,
    travel_speed,
)


_CALLER_MODIFIER_ALIASES = {
    "4wd": "four_wheel_drive",
    "four_wd": "four_wheel_drive",
}


def _merge_detected_options(
    caller_modifiers: list[str],
    text_options: DetectedOptions,
) -> DetectedOptions:
    merged_keys = set(text_options.keys)
    merged_evidence = {k: list(v) for k, v in text_options.evidence.items()}

    for raw_key in caller_modifiers:
        key = _CALLER_MODIFIER_ALIASES.get(raw_key, raw_key)
        merged_keys.add(key)
        merged_evidence.setdefault(key, [])
        if "[structured input]" not in merged_evidence[key]:
            merged_evidence[key].append("[structured input]")

    return DetectedOptions(keys=frozenset(merged_keys), evidence=merged_evidence)


# ---------------------------------------------------------------------------
# Field dispatcher — maps category → ordered list of resolver callables
# Each callable receives a ResolutionContext and returns
#   FieldResolution | dict[str, FieldResolution] | None
# ---------------------------------------------------------------------------

# Categories that share CTL/SSL field layout
_CTL_SSL_RESOLVERS = [
    ("net_hp",              horsepower.resolve),
    ("operating_weight_lb", weight.resolve),
    ("roc_lb",              roc.resolve),
    ("tipping_load_lb",     tipping_load.resolve),
    ("hydraulic_flow",      hydraulic_flow.resolve),   # multi-field
    ("travel_speed",        travel_speed.resolve),     # multi-field
]

_MINI_EX_RESOLVERS = [
    ("net_hp",              horsepower.resolve),
    ("operating_weight_lb", weight.resolve),
    ("max_dig_depth",       dig_depth.resolve),
    ("bucket_breakout_lb",  breakout_force.resolve),
    ("travel_speed",        travel_speed.resolve),
]

_FULL_EX_RESOLVERS = [
    ("net_hp",              horsepower.resolve),
    ("operating_weight_lb", weight.resolve),
    ("max_dig_depth",       dig_depth.resolve),
    ("bucket_breakout_lb",  breakout_force.resolve),
    ("travel_speed",        travel_speed.resolve),
]

_WL_RESOLVERS = [
    ("net_hp",              horsepower.resolve),
    ("operating_weight_lb", weight.resolve),
    ("travel_speed",        travel_speed.resolve),
]

_TH_RESOLVERS = [
    ("net_hp",              horsepower.resolve),
    ("operating_weight_lb", weight.resolve),
    ("travel_speed",        travel_speed.resolve),
]

_BOOM_RESOLVERS = [
    ("operating_weight_lb", weight.resolve),
]

_SCIS_RESOLVERS = [
    ("operating_weight_lb", weight.resolve),
]

_DOZ_RESOLVERS = [
    ("net_hp",              horsepower.resolve),
    ("operating_weight_lb", weight.resolve),
    ("travel_speed",        travel_speed.resolve),
]

_BH_RESOLVERS = [
    ("net_hp",              horsepower.resolve),
    ("operating_weight_lb", weight.resolve),
    ("max_dig_depth",       dig_depth.resolve),
    ("bucket_breakout_lb",  breakout_force.resolve),
    ("travel_speed",        travel_speed.resolve),
]

_CATEGORY_RESOLVERS: Dict[str, list] = {
    "CTL":  _CTL_SSL_RESOLVERS,
    "SSL":  _CTL_SSL_RESOLVERS,
    "MINI": _MINI_EX_RESOLVERS,
    "EX":   _FULL_EX_RESOLVERS,
    "WL":   _WL_RESOLVERS,
    "TH":   _TH_RESOLVERS,
    "BOOM": _BOOM_RESOLVERS,
    "SCIS": _SCIS_RESOLVERS,
    "DOZ":  _DOZ_RESOLVERS,
    "BH":   _BH_RESOLVERS,
}

# Fields that come straight from registry specs without a dedicated resolver
# (string/enum fields that don't require computation)
_PASSTHROUGH_FIELDS = [
    "fuel_type",
    "lift_path",
    "tail_swing_type",
    "power_type",
    "indoor_outdoor",
    "four_wd",
    # Telehandler lift specs — numeric, no resolver needed
    "lift_capacity_lb",
    "max_lift_height_ft",
    "max_forward_reach_ft",
    "lift_capacity_at_full_height_lbs",   # promoted to standard buyer-facing tier 2026-04-13
    # Telehandler drivetrain/config string fields
    "transmission_type",                  # telehandler
    # Hydraulic flow — numeric passthrough for types without a dedicated
    # hydraulic resolver (EX, WL, TH, BH, DOZ).  The passthrough loop
    # guards against overwriting resolver output, so SSL/CTL records whose
    # hydraulic_flow_gpm is already emitted by hydraulic_flow.resolve are
    # not disturbed.
    "hydraulic_flow_gpm",
    # CTL/SSL dimensional specs — fixed OEM values, no resolver needed.
    "width_over_tires_in",
    "bucket_hinge_pin_height_in",
    # Capacity fields — numeric, no resolver needed.
    # bucket_capacity_cy (EX, WL) is renamed to bucket_capacity_yd3 by
    # _SPEC_KEY_MAP before the record reaches the resolver.
    "bucket_capacity_yd3",        # excavator, wheel_loader
    "loader_bucket_capacity_yd3", # backhoe_loader (direct registry key)
    "blade_capacity_yd3",         # crawler_dozer (direct registry key)
    # Dozer site-suitability spec and telehandler drivetrain — direct registry keys
    "ground_pressure_psi",        # crawler_dozer
    "drive_type",                 # telehandler
    # Mini excavator hydraulic pressure — renamed from aux_pressure_primary_psi
    # and hydraulic_pressure_psi by _SPEC_KEY_MAP before reaching the resolver.
    "hydraulic_pressure_standard_psi",
    # Mini excavator dimensional specs — direct registry keys (no resolver needed)
    "max_dump_height_ft",         # mini_excavator
    "max_reach_ft",               # mini_excavator
    "width_in",                   # mini_excavator
    # Boom lift and scissor lift specs — direct registry keys (no resolver needed)
    "platform_height_ft",         # boom_lift, scissor_lift
    "platform_capacity_lbs",      # boom_lift, scissor_lift
    "horizontal_reach_ft",        # boom_lift
    "boom_type",                  # boom_lift
    "power_source",               # boom_lift, scissor_lift
    "drive_speed_stowed_mph",     # boom_lift, scissor_lift
    "platform_length_ft",         # scissor_lift
    "platform_width_ft",          # scissor_lift
    # Dozer blade width — direct registry key
    "blade_width_ft",             # crawler_dozer
    # Dozer fuel tank — direct registry key
    "fuel_capacity_gal",          # crawler_dozer
]


# ---------------------------------------------------------------------------
# Year extraction helper
# ---------------------------------------------------------------------------

_YEAR_RE = re.compile(r"\b(19[89]\d|20[0-3]\d)\b")

def _extract_year(text: str) -> Optional[int]:
    m = _YEAR_RE.search(text)
    return int(m.group(1)) if m else None


# ---------------------------------------------------------------------------
# Year-range warning
# ---------------------------------------------------------------------------

def _check_year_range(
    year: Optional[int],
    entry: RegistryEntry,
) -> Optional[ResolverWarning]:
    if year is None:
        return None
    lo, hi = entry.year_range[0], entry.year_range[1]
    if year < lo or year > hi:
        return ResolverWarning(
            code="YEAR_OUTSIDE_RANGE",
            message=(
                f"Year {year} is outside the typical production range "
                f"{lo}–{hi} for {entry.family}. Specs may not match."
            ),
            severity=WarningSeverity.WARNING,
        )
    return None


# ---------------------------------------------------------------------------
# Year-keyed spec override application
# ---------------------------------------------------------------------------

def _apply_year_overrides(
    entry: RegistryEntry,
    year: Optional[int],
    warnings: List[ResolverWarning],
) -> RegistryEntry:
    """
    Return a new RegistryEntry with specs updated by year_overrides, if any.
    year_overrides is keyed by max_year: the override applies when year <= key.
    Mutates a copy of entry.specs so the original entry is not touched.
    """
    if year is None or not entry.year_overrides:
        return entry

    # Find the highest key that is still >= year  (i.e. year <= key)
    applicable_keys = sorted(
        (k for k in entry.year_overrides if year <= k),
        reverse=True,
    )
    if not applicable_keys:
        return entry

    override_key = applicable_keys[0]
    override_specs = entry.year_overrides[override_key]

    # Merge override into a copy of specs
    merged = dict(entry.specs)
    merged.update(override_specs)

    warnings.append(ResolverWarning(
        code="YEAR_OVERRIDE_APPLIED",
        message=(
            f"Year {year} matched override block (≤{override_key}). "
            f"Fields overridden: {', '.join(override_specs.keys())}."
        ),
        severity=WarningSeverity.INFO,
    ))

    # Return a shallow-copied entry with updated specs
    import dataclasses
    return dataclasses.replace(entry, specs=merged)


# ---------------------------------------------------------------------------
# Single-field passthrough resolver
# ---------------------------------------------------------------------------

def _resolve_passthrough(
    field: str,
    entry: RegistryEntry,
    match_type: MatchType,
    confidence: float,
) -> Optional[Tuple[Any, FieldMeta, FieldTrace]]:
    """
    Resolve a string/enum field directly from registry specs with no computation.
    Returns (value, FieldMeta, FieldTrace) or None if not present.
    """
    from .confidence_policy import HARD_FLOOR_CONFIDENCE
    from .field_rules import get_field_behavior

    if confidence < HARD_FLOOR_CONFIDENCE:
        return None
    if match_type in (MatchType.NONE, MatchType.MANUFACTURER_ONLY):
        return None

    val = entry.specs.get(field)
    if val is None:
        return None

    behavior = get_field_behavior(field, entry.category, entry.field_behaviors)
    is_exact = match_type == MatchType.EXACT
    source   = FieldSource.REGISTRY_EXACT if is_exact else FieldSource.REGISTRY_FAMILY
    reason   = (
        "Exact model locked spec."
        if is_exact else
        "Family-level passthrough spec."
    )
    require  = not is_exact  # family matches still need confirm for passthrough

    meta = FieldMeta(
        value=val,
        source=source,
        confidence=confidence,
        behavior=behavior,
        resolution_reason=reason,
        injected=True,
    )
    trace = FieldTrace(
        field_name=field,
        final_value=val,
        source=source,
        behavior=behavior,
        confidence=confidence,
        injected=True,
        require_confirm=require,
        resolution_reason=reason,
        registry_value=val,
    )
    return val, meta, trace


# ---------------------------------------------------------------------------
# UI hints extraction
# Anything in resolved_specs or notes with a "_" prefix → ui_hints
# ---------------------------------------------------------------------------

def _extract_ui_hints(
    resolved_specs:   Dict[str, Any],
    field_traces:     List[FieldTrace],
    options:          DetectedOptions,
    entry:            RegistryEntry,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Split a flat dict into (clean_specs, ui_hints).
    Also scans FieldTrace notes for "_key: value" annotations.
    Returns (resolved_specs_without_hints, ui_hints_dict).
    """
    ui_hints: Dict[str, Any] = {}
    clean: Dict[str, Any] = {}

    for k, v in resolved_specs.items():
        if k.startswith("_"):
            ui_hints[k] = v
        else:
            clean[k] = v

    # Scan trace notes for "_key: value" patterns
    note_re = re.compile(r"^(_[a-zA-Z]\w+):\s*(.+)$")
    for trace in field_traces:
        for note in trace.notes:
            m = note_re.match(note.strip())
            if m:
                hint_key = m.group(1)
                hint_val_str = m.group(2).strip()
                # Try to coerce to bool/int/float
                if hint_val_str.lower() == "true":
                    ui_hints[hint_key] = True
                elif hint_val_str.lower() == "false":
                    ui_hints[hint_key] = False
                else:
                    try:
                        ui_hints[hint_key] = int(hint_val_str)
                    except ValueError:
                        try:
                            ui_hints[hint_key] = float(hint_val_str)
                        except ValueError:
                            ui_hints[hint_key] = hint_val_str

    # Standard hints derived from detected options
    if options.has("high_flow"):
        ui_hints["_displayHiFlow"] = True
    if options.has("lgp"):
        ui_hints["_isLGP"] = True
    if options.has("has_cab"):
        ui_hints["_hasCab"] = True
    elif options.has("has_canopy"):
        ui_hints["_hasCab"] = False

    # Registry-defined display hints
    for k, v in entry.specs.items():
        if k.startswith("_"):
            ui_hints[k] = v

    return clean, ui_hints


# ---------------------------------------------------------------------------
# Requires-confirm assembler
# ---------------------------------------------------------------------------

def _collect_requires_confirm(
    field_traces:  List[FieldTrace],
    warnings:      List[ResolverWarning],
) -> List[str]:
    """
    Build the deduplicated, sorted requires_confirm list.
    Includes:
      - Fields where trace.require_confirm is True AND the field was injected
        (injected but uncertain → user should verify the pre-filled value)
      - Fields where trace.require_confirm is True AND the field was NOT injected
        but has a known behavior of package_dependent or range
        (not injected but user needs to fill it in manually)
      - Fields referenced in WARNING-level warning.field values
    """
    confirm_set: set[str] = set()

    for trace in field_traces:
        if not trace.require_confirm:
            continue
        # Include if injected (yellow cell with pre-filled value)
        if trace.final_value is not None:
            confirm_set.add(trace.field_name)
        # Also include package_dependent and range fields that weren't injected
        # — the user must fill them in, so they appear in the form
        elif trace.behavior in (
            FieldBehavior.PACKAGE_DEPENDENT, FieldBehavior.RANGE
        ):
            confirm_set.add(trace.field_name)

    for w in warnings:
        if w.severity == WarningSeverity.WARNING and w.field:
            confirm_set.add(w.field)

    return sorted(confirm_set)


# ---------------------------------------------------------------------------
# Main orchestrator
# ---------------------------------------------------------------------------

def resolve(inp: ResolverInput) -> ResolverOutput:
    """
    Resolve specs for a single equipment listing.

    All inputs arrive pre-parsed by the calling layer; the resolver does
    NOT re-parse manufacturer/model/category from raw text. It still
    re-runs option detection and numeric extraction on the raw text, then
    merges those results with any caller-provided modifiers or numeric
    claims so text-based and structured flows both work.
    """

    # ── 1. Validate ──────────────────────────────────────────────────────
    inp.validate()

    run_id = str(uuid.uuid4())[:8]

    # ── 2. Build RegistryEntry ────────────────────────────────────────────
    if not inp.registry_match:
        return _unresolved_output(
            inp, run_id,
            reason="registry_match is empty — no entry to resolve against.",
        )

    try:
        entry = RegistryEntry.from_dict(inp.registry_match)
    except (KeyError, ValueError) as exc:
        return _unresolved_output(
            inp, run_id,
            reason=f"registry_match failed to parse: {exc}",
        )

    match_type  = inp.match_type
    confidence  = inp.registry_match_confidence
    category    = inp.parsed_category.upper()

    # ── 3. Hard-floor gate ────────────────────────────────────────────────
    if confidence < HARD_FLOOR_CONFIDENCE:
        return _unresolved_output(
            inp, run_id,
            reason=(
                f"registry_match_confidence {confidence:.2f} is below hard floor "
                f"{HARD_FLOOR_CONFIDENCE}. No specs injected."
            ),
        )

    if match_type in (MatchType.NONE, MatchType.MANUFACTURER_ONLY):
        return _unresolved_output(
            inp, run_id,
            reason=f"match_type={match_type.value}: insufficient match for injection.",
        )

    # ── 4. Re-detect options from raw text ────────────────────────────────
    #    Always from raw listing text, not from pre-parsed detected_modifiers.
    #    This enforces: option detection BEFORE noise stripping.
    # Raw text detection still runs so text-only flows keep working,
    # while structured build flows can augment those results.
    options = _merge_detected_options(
        inp.detected_modifiers or [],
        detect_options(inp.raw_listing_text),
    )

    # ── 5. Re-extract numeric claims ──────────────────────────────────────
    numeric_claims = extract_numeric_claims(inp.raw_listing_text)
    # Merge with any pre-extracted claims (caller's claims are lower priority)
    merged_claims = {**inp.extracted_numeric_claims, **numeric_claims}

    # ── 6. Parse year ─────────────────────────────────────────────────────
    year = _extract_year(inp.raw_listing_text)

    # Accumulate all warnings and traces
    all_warnings:     List[ResolverWarning] = []
    all_traces:       List[FieldTrace]      = []
    resolved_specs:   Dict[str, Any]        = {}
    per_field_meta:   Dict[str, FieldMeta]  = {}

    # ── 7a. Year-range warning ────────────────────────────────────────────
    year_warn = _check_year_range(year, entry)
    if year_warn:
        all_warnings.append(year_warn)

    # ── 7b. Apply year overrides to entry ─────────────────────────────────
    entry = _apply_year_overrides(entry, year, all_warnings)

    # ── 7c. Build shared ResolutionContext factory ─────────────────────────
    def make_ctx(field_name: str) -> ResolutionContext:
        return ResolutionContext(
            field_name=field_name,
            match_type=match_type,
            registry_entry=entry,
            registry_confidence=confidence,
            detected_options=options,
            numeric_claims=merged_claims,
            parsed_year=year,
            parsed_category=category,
        )

    # ── 7d. Run field resolvers ────────────────────────────────────────────
    resolver_list = _CATEGORY_RESOLVERS.get(category, [])

    for resolver_key, resolver_fn in resolver_list:
        ctx = make_ctx(resolver_key)
        try:
            result = resolver_fn(ctx)
        except Exception as exc:
            # Fail-closed: log the error as a warning, skip the field
            all_warnings.append(ResolverWarning(
                code="RESOLVER_ERROR",
                message=f"Field resolver '{resolver_key}' raised: {exc}",
                field=resolver_key,
                severity=WarningSeverity.ERROR,
            ))
            continue

        if result is None:
            continue

        # Multi-field resolvers return dict[str, FieldResolution]
        if isinstance(result, dict):
            items = result.items()
        else:
            items = [(resolver_key, result)]

        for field_name, field_res in items:
            _ingest_field_resolution(
                field_name, field_res,
                resolved_specs, per_field_meta, all_traces, all_warnings,
            )

    # ── 7e. Passthrough fields ────────────────────────────────────────────
    for pf in _PASSTHROUGH_FIELDS:
        if pf in resolved_specs:          # resolver already handled this field
            continue
        pt = _resolve_passthrough(pf, entry, match_type, confidence)
        if pt is None:
            continue
        val, meta, trace = pt
        # Manual-review fields must not be auto-injected (same policy as evaluate_injection)
        if meta.behavior == FieldBehavior.MANUAL_REVIEW:
            all_traces.append(trace)
            continue
        resolved_specs[pf] = val
        per_field_meta[pf]  = meta
        all_traces.append(trace)

    # ── 8. Split ui_hints out of resolved_specs ───────────────────────────
    clean_specs, ui_hints = _extract_ui_hints(
        resolved_specs, all_traces, options, entry
    )

    # ── 9. Requires-confirm ───────────────────────────────────────────────
    requires_confirm = _collect_requires_confirm(all_traces, all_warnings)

    # ── 10. Overall status + injection gate ───────────────────────────────
    overall_status = determine_overall_status(
        match_type=match_type,
        registry_confidence=confidence,
        n_resolved_fields=len(clean_specs),
        n_total_fields=max(len(resolver_list) + len(_PASSTHROUGH_FIELDS), 1),
    )

    n_errors = sum(1 for w in all_warnings if w.severity == WarningSeverity.ERROR)
    safe = is_safe_for_listing_injection(
        overall_status=overall_status,
        n_warnings=n_errors,
        n_require_confirm=len(requires_confirm),
    )

    # ── 11. Build audit trail (available via debug; not in output dict) ────
    audit = create_audit_trail(
        run_id=run_id,
        raw_text=inp.raw_listing_text,
        mfr=inp.parsed_manufacturer,
        model=inp.parsed_model,
        category=category,
        match_type=match_type,
        confidence=confidence,
        detected_options=options.to_list(),
        numeric_claims=merged_claims,
    )
    for trace in all_traces:
        audit.add_trace(trace)
    for w in all_warnings:
        audit.add_warning(w.message)

    # ── 12. Return ────────────────────────────────────────────────────────
    output = ResolverOutput(
        resolved_specs=clean_specs,
        requires_confirm=requires_confirm,
        ui_hints=ui_hints,
        per_field_metadata=per_field_meta,
        warnings=all_warnings,
        overall_resolution_status=overall_status,
        safe_for_listing_injection=safe,
    )
    # Attach audit trail as a non-schema attribute for callers that want it
    output._audit_trail = audit  # type: ignore[attr-defined]
    return output


# ---------------------------------------------------------------------------
# Dict entry point (convenience for JSON callers)
# ---------------------------------------------------------------------------

def resolve_from_dict(d: dict) -> ResolverOutput:
    """
    Convenience wrapper: build ResolverInput from a plain dict and resolve.
    The dict shape matches the spec document exactly.
    """
    inp = ResolverInput(
        raw_listing_text          = d.get("raw_listing_text", ""),
        parsed_manufacturer       = d.get("parsed_manufacturer", ""),
        parsed_model              = d.get("parsed_model", ""),
        parsed_category           = d.get("parsed_category", ""),
        detected_modifiers        = d.get("detected_modifiers", []),
        extracted_numeric_claims  = d.get("extracted_numeric_claims", {}),
        registry_match            = d.get("registry_match", {}),
        registry_match_confidence = float(d.get("registry_match_confidence", 0.0)),
        match_type                = MatchType(d.get("match_type", "none")),
    )
    return resolve(inp)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ingest_field_resolution(
    field_name:     str,
    field_res:      FieldResolution,
    resolved_specs: Dict[str, Any],
    per_field_meta: Dict[str, FieldMeta],
    all_traces:     List[FieldTrace],
    all_warnings:   List[ResolverWarning],
) -> None:
    """Merge a single FieldResolution into the accumulator dicts."""
    meta  = field_res.meta
    trace = field_res.trace

    # Only add to resolved_specs if injected AND value is not None
    if meta.injected and meta.value is not None:
        resolved_specs[field_name] = meta.value

    per_field_meta[field_name] = meta
    all_traces.append(trace)
    all_warnings.extend(field_res.warnings)


def _unresolved_output(
    inp:    ResolverInput,
    run_id: str,
    reason: str,
) -> ResolverOutput:
    """
    Produce a fully-populated ResolverOutput that signals nothing was resolved.
    Used for hard-floor failures, bad input, and empty registry matches.
    """
    warning = ResolverWarning(
        code="UNRESOLVED",
        message=reason,
        severity=WarningSeverity.WARNING,
    )
    output = ResolverOutput(
        resolved_specs={},
        requires_confirm=[],
        ui_hints={},
        per_field_metadata={},
        warnings=[warning],
        overall_resolution_status=OverallStatus.UNRESOLVED,
        safe_for_listing_injection=False,
    )
    # Minimal audit trail for unresolved cases
    audit = create_audit_trail(
        run_id=run_id,
        raw_text=inp.raw_listing_text,
        mfr=inp.parsed_manufacturer,
        model=inp.parsed_model,
        category=inp.parsed_category,
        match_type=inp.match_type,
        confidence=inp.registry_match_confidence,
        detected_options=[],
        numeric_claims={},
    )
    audit.add_warning(reason)
    output._audit_trail = audit  # type: ignore[attr-defined]
    return output
