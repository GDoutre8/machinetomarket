/**
 * MTM Spec Resolver  v2.1
 * ─────────────────────────────────────────────────────────────────────────────
 * Presentation-layer only. Never modifies registry source data.
 *
 * Three display tiers: essential (8) | standard (12) | technical (15)
 * Default: standard
 *
 * Public API
 * ──────────
 *  get_spec_profile(equipment_type, profile?)
 *    → string[]   ordered field keys defined in the profile (no record context,
 *                 no null-skipping — returns the full profile field list)
 *
 *  render_spec_block(record, equipment_type, profile?)
 *    → SpecRow[]  displayable label/value pairs, null fields silently skipped
 *
 *  render_feature_flags(record)
 *    → FlagRow[]  all flags, profile-independent (skid steer / CTL)
 *
 *  getMiniExBadges(record)
 *    → BadgeRow[]  only true mini excavator feature badges
 *
 *  getMachineClassTon(record)
 *    → string | null   weight-based class label for mini excavators
 *
 *  getDigDepthClass(record)
 *    → string | null   dig-depth-based class label for mini excavators
 */

'use strict';

// ── Load profiles ─────────────────────────────────────────────────────────────
// In Next.js / Node: require('./spec_display_profiles.json') works directly.
// Browser bundle: import profiles from './spec_display_profiles.json' assert { type: 'json' }
const PROFILES =
  typeof require !== 'undefined'
    ? require('./spec_display_profiles.json')
    : null; // populated via init() in browser builds

const DEFAULT_PROFILE = 'standard';
const VALID_PROFILES  = ['essential', 'standard', 'technical'];

// Maps live registry equipment_type values to canonical profile keys.
// Keeps alias resolution in the resolver so spec_display_profiles.json
// contains only one authoritative entry per equipment type.
const EQUIPMENT_TYPE_ALIASES = {
  ctl:               'compact_track_loader',
  skid_steer_loader: 'skid_steer',
};

// ── Field metadata ────────────────────────────────────────────────────────────

const FIELD_LABELS = {
  // ── CTL dealer-input core output fields ───────────────────────────────────
  hours:                           'Hours',
  high_flow:                       'High Flow',
  two_speed:                       '2-Speed',
  quick_attach:                    'Quick Attach',
  ac:                              'A/C',
  track_condition:                 'Track Condition',
  serial_number:                   'Serial Number',
  // ── Skid steer / CTL ──────────────────────────────────────────────────────
  rated_operating_capacity_lbs:    'Rated Operating Capacity',
  operating_weight_lbs:            'Operating Weight',
  horsepower_hp:                   'Horsepower (net)',
  horsepower_gross_hp:             'Horsepower (gross)',
  aux_flow_standard_gpm:           'Aux Flow (std)',
  aux_flow_high_gpm:               'Aux Flow (high)',
  width_over_tires_in:             'Width Over Tires',
  lift_path:                       'Lift Path',
  bucket_hinge_pin_height_in:      'Hinge Pin Height',
  travel_speed_high_mph:           'Travel Speed (high)',
  travel_speed_low_mph:            'Travel Speed (low)',
  emissions_tier:                  'Emissions Tier',
  tipping_load_lbs:                'Tipping Load',
  dump_height_in:                  'Dump Height',
  dump_reach_in:                   'Dump Reach',
  hydraulic_pressure_standard_psi: 'Hydraulic Pressure (std)',
  hydraulic_pressure_high_psi:     'Hydraulic Pressure (high)',
  hydraulic_pump_type:             'Pump Type',
  fuel_capacity_gal:               'Fuel Capacity',
  fuel_type:                       'Fuel Type',
  engine_manufacturer:             'Engine Make',
  engine_model:                    'Engine Model',
  engine_displacement_cu_in:       'Displacement',
  engine_cylinders:                'Cylinders',
  engine_aspiration:               'Aspiration',
  frame_size:                      'Frame Size',
  tail_swing_type:                 'Tail Swing',
  wheelbase_in:                    'Wheelbase',
  standard_tire_size:              'Tire Size',
  // ── Mini excavator ────────────────────────────────────────────────────────
  max_dig_depth_in:                'Max Dig Depth',
  max_reach_ground_in:             'Max Reach (ground)',
  overall_width_in:                'Overall Width',
  bucket_dig_force_lbf:            'Bucket Dig Force',
  arm_dig_force_lbf:               'Arm Dig Force',
  max_dump_height_in:              'Max Dump Height',
  max_cutting_height_in:           'Max Cutting Height',
  aux_flow_primary_gpm:            'Aux Flow',
  hydraulic_pressure_psi:          'Hydraulic Pressure',
  overall_height_in:               'Overall Height',
  track_width_in:                  'Track Width',
  blade_width_in:                  'Blade Width',
  swing_speed_rpm:                 'Swing Speed',
  cab_type:                        'Cab Type',
  track_type:                      'Track Type',
  hydraulic_flow_gpm:              'Hydraulic Flow',
  aux_pressure_primary_psi:        'Aux Pressure',
  // ── Wheel loader ──────────────────────────────────────────────────────────
  bucket_capacity_yd3:             'Bucket Capacity',
  breakout_force_lbs:              'Breakout Force',
  travel_speed_mph:                'Travel Speed',
  dump_clearance_ft:               'Dump Clearance',
  reach_at_dump_ft:                'Reach at Full Dump',
  overall_length_ft:               'Overall Length',
  overall_width_ft:                'Overall Width',
  // ── Excavator ─────────────────────────────────────────────────────────────
  max_dig_depth_ft:                'Max Dig Depth',
  bucket_breakout_force_lbs:       'Bucket Breakout Force',
  arm_digging_force_lbs:           'Arm Digging Force',
  max_reach_ft:                    'Max Reach (ground)',
  ground_pressure_psi:             'Ground Pressure',
  // ── Telehandler ───────────────────────────────────────────────────────────
  max_lift_capacity_lbs:           'Max Lift Capacity',
  lift_height_ft:                  'Max Lift Height',
  forward_reach_ft:                'Max Forward Reach',
  overall_height_ft:               'Overall Height',
  ground_clearance_in:             'Ground Clearance',
};

const FIELD_UNITS = {
  // ── CTL dealer-input core output fields ───────────────────────────────────
  hours:                           'hrs',
  // ── Skid steer / CTL ──────────────────────────────────────────────────────
  rated_operating_capacity_lbs:    'lbs',
  tipping_load_lbs:                'lbs',
  operating_weight_lbs:            'lbs',
  horsepower_hp:                   'hp',
  horsepower_gross_hp:             'hp',
  aux_flow_standard_gpm:           'gpm',
  aux_flow_high_gpm:               'gpm',
  width_over_tires_in:             'in',
  bucket_hinge_pin_height_in:      'in',
  dump_height_in:                  'in',
  dump_reach_in:                   'in',
  travel_speed_high_mph:           'mph',
  travel_speed_low_mph:            'mph',
  hydraulic_pressure_standard_psi: 'psi',
  hydraulic_pressure_high_psi:     'psi',
  fuel_capacity_gal:               'gal',
  engine_displacement_cu_in:       'cu in',
  wheelbase_in:                    'in',
  // ── Mini excavator ────────────────────────────────────────────────────────
  max_dig_depth_in:                'in',
  max_reach_ground_in:             'in',
  overall_width_in:                'in',
  bucket_dig_force_lbf:            'lbf',
  arm_dig_force_lbf:               'lbf',
  max_dump_height_in:              'in',
  max_cutting_height_in:           'in',
  aux_flow_primary_gpm:            'gpm',
  hydraulic_pressure_psi:          'psi',
  overall_height_in:               'in',
  track_width_in:                  'in',
  blade_width_in:                  'in',
  swing_speed_rpm:                 'rpm',
  hydraulic_flow_gpm:              'gpm',
  aux_pressure_primary_psi:        'psi',
  // ── Wheel loader ──────────────────────────────────────────────────────────
  bucket_capacity_yd3:             'yd³',
  breakout_force_lbs:              'lbs',
  travel_speed_mph:                'mph',
  dump_clearance_ft:               'ft',
  reach_at_dump_ft:                'ft',
  overall_length_ft:               'ft',
  overall_width_ft:                'ft',
  // ── Excavator ─────────────────────────────────────────────────────────────
  max_dig_depth_ft:                'ft',
  bucket_breakout_force_lbs:       'lbs',
  arm_digging_force_lbs:           'lbs',
  max_reach_ft:                    'ft',
  ground_pressure_psi:             'psi',
  // ── Telehandler ───────────────────────────────────────────────────────────
  max_lift_capacity_lbs:           'lbs',
  lift_height_ft:                  'ft',
  forward_reach_ft:                'ft',
  overall_height_ft:               'ft',
  ground_clearance_in:             'in',
};

// Enum → human string
const ENUM_DISPLAY = {
  lift_path: {
    vertical: 'Vertical lift',
    radial:   'Radial lift',
  },
  frame_size: {
    small:        'Small frame',
    mid:          'Mid frame',
    medium:       'Medium frame',
    medium_large: 'Medium-large frame',
    large:        'Large frame',
    extra_large:  'Extra large frame',
    mini:         'Mini frame',
  },
  engine_aspiration: {
    turbocharged:             'Turbocharged',
    turbocharged_intercooled: 'Turbocharged / intercooled',
    turbocharged_aftercooled: 'Turbocharged / aftercooled',
    naturally_aspirated:      'Naturally aspirated',
  },
  // tail_swing_type covers both skid steer (legacy short keys) and
  // mini excavator (full descriptive keys from live registry)
  tail_swing_type: {
    // skid steer / CTL values
    radial:                   'Conventional',
    zero:                     'Zero tail swing',
    reduced:                  'Reduced tail swing',
    // mini excavator live values
    zero_tail_swing:          'Zero tail swing',
    conventional_tail_swing:  'Conventional',
    reduced_tail_swing:       'Reduced tail swing',
  },
  hydraulic_pump_type: {
    gear_pump:             'Gear pump',
    piston_xps:            'Piston / XPS',
    axial_piston:          'Axial piston',
    variable_displacement: 'Variable displacement',
  },
  fuel_type: {
    diesel:   'Diesel',
    electric: 'Electric',
    gas:      'Gasoline',
  },
  cab_type: {
    canopy:   'Canopy',
    cab:      'Enclosed cab',   // live value used by Yanmar, Kubota records
    enclosed: 'Enclosed cab',
  },
  track_type: {
    rubber: 'Rubber tracks',
    steel:  'Steel tracks',
  },
};

// Feature flag labels — skid steer / CTL
const FLAG_LABELS = {
  high_flow_available:         'High-Flow Hydraulics',
  two_speed_available:         'Two-Speed Drive',
  enclosed_cab_available:      'Enclosed Cab',
  ride_control_available:      'Ride Control',
  joystick_controls_available: 'Joystick Controls',
  hydraulic_coupler_available: 'Hydraulic Coupler',
};

// Mini excavator badge labels — only true flags rendered
const MINI_EX_BADGE_LABELS = {
  zero_tail_swing:             'Zero Tail Swing',
  hydraulic_thumb_available:   'Hydraulic Thumb',
  angle_blade_available:       'Angle Blade',
  long_arm_available:          'Long Arm',
};

// ─────────────────────────────────────────────────────────────────────────────
// Core resolver
// ─────────────────────────────────────────────────────────────────────────────

function _resolveProfiles() {
  return PROFILES;
}

/**
 * get_spec_profile(equipment_type, profile?)
 *
 * Returns the ordered list of spec field keys for the requested tier.
 * This is the field list only — does not filter against a specific record.
 * Use render_spec_block() to get record-aware output with null-skipping.
 *
 * @param {string}  equipment_type  'ctl' | 'skid_steer_loader' | 'mini_excavator'
 *                                  or 'compact_track_loader' | 'skid_steer' (canonical names)
 * @param {string}  [profile]       'essential' | 'standard' | 'technical'
 *                                  defaults to 'standard'
 * @returns {string[]}
 */
function get_spec_profile(equipment_type, profile) {
  const prof           = profile || DEFAULT_PROFILE;
  const cfg            = _resolveProfiles();
  const normalizedType = EQUIPMENT_TYPE_ALIASES[equipment_type] || equipment_type;

  if (!cfg) {
    throw new Error(
      'spec_display_profiles.json has not been loaded. ' +
      'In browser/ESM builds, assign the imported profiles object to PROFILES before calling get_spec_profile().'
    );
  }

  if (!VALID_PROFILES.includes(prof)) {
    throw new Error(
      `Invalid profile "${prof}". Valid options: ${VALID_PROFILES.join(', ')}.`
    );
  }

  // Live equipment types (canonical names only in the JSON)
  if (cfg[normalizedType]) {
    const tier = cfg[normalizedType][prof];
    if (!tier || !Array.isArray(tier.fields)) {
      throw new Error(
        `Profile "${prof}" not configured for equipment type "${normalizedType}".`
      );
    }
    return [...tier.fields]; // return copy — never expose internal reference
  }

  // Scaffold / future types
  if (cfg._future_equipment_types?.[normalizedType]) {
    throw new Error(
      `Equipment type "${normalizedType}" is scaffolded but not yet configured. ` +
      `Add profiles to spec_display_profiles.json when its registry is locked.`
    );
  }

  const supported = Object.keys(cfg).filter(k => !k.startsWith('_'));
  throw new Error(
    `Unknown equipment type "${equipment_type}"` +
    (normalizedType !== equipment_type ? ` (resolved to "${normalizedType}")` : '') +
    `. Supported canonical types: ${supported.join(', ')}.`
  );
}

/**
 * render_spec_block(record, equipment_type, profile?)
 *
 * Returns displayable spec rows from a registry record, filtered to the
 * requested profile. Fields with null / undefined / '' values are silently
 * skipped — no blank labels are ever returned.
 *
 * @param {Object}  record          Registry record object
 * @param {string}  equipment_type
 * @param {string}  [profile]       defaults to 'standard'
 * @returns {Array<{field, label, value, unit, raw_value, confidence, behavior}>}
 */
function render_spec_block(record, equipment_type, profile) {
  const fields     = get_spec_profile(equipment_type, profile);
  const specs      = record.specs            || {};
  const confidence = record.field_confidence || {};
  const behavior   = record.field_behavior   || {};
  const rows       = [];

  for (const field of fields) {
    // Field not present in this record's spec block at all — skip
    if (!(field in specs)) continue;

    const raw = specs[field];

    // Null / undefined / empty string — skip silently, no blank label
    if (raw === null || raw === undefined || raw === '') continue;

    rows.push({
      field,
      label:      FIELD_LABELS[field] || field,
      value:      _format_value(field, raw),
      unit:       FIELD_UNITS[field]  || null,
      raw_value:  raw,
      confidence: (confidence[field] || '').toLowerCase(),
      behavior:   behavior[field]    || null,
    });
  }

  return rows;
}

/**
 * render_feature_flags(record, equipment_type?)
 *
 * Returns feature flags from the record with human labels.
 * Profile-independent — used for skid steer / CTL flag chips.
 *
 * For skid_steer: high_flow_available and two_speed_available are model-level
 * availability flags, not unit-installed config. They are suppressed here to
 * prevent them being rendered as buyer-facing "installed" chips. Unit-level
 * high_flow / two_speed truth comes from DealerInput (Python pipeline only).
 *
 * @param {Object} record
 * @param {string} [equipment_type]  optional — 'skid_steer' triggers SSL suppression
 * @returns {Array<{flag, label, value}>}
 */
function render_feature_flags(record, equipment_type) {
  const flags        = record.feature_flags || {};
  const normalizedType = EQUIPMENT_TYPE_ALIASES[equipment_type] || (equipment_type || '');
  const isSSL        = normalizedType === 'skid_steer';
  const isCTL        = normalizedType === 'compact_track_loader';

  // SSL and CTL: high_flow_available / two_speed_available are model-level availability flags,
  // not unit-installed config. Suppress them from buyer-facing chips for both types.
  // Unit-level high_flow / two_speed truth comes from DealerInput (Python pipeline only).
  const AVAILABILITY_SUPPRESSED = new Set(['high_flow_available', 'two_speed_available']);

  return Object.entries(flags)
    .filter(([flag]) => !((isSSL || isCTL) && AVAILABILITY_SUPPRESSED.has(flag)))
    .map(([flag, value]) => ({
      flag,
      label: FLAG_LABELS[flag] || flag,
      value,
    }));
}

/**
 * getMiniExBadges(record)
 *
 * Returns only the true (value === true) mini excavator feature badges.
 * Null, false, and absent flags are silently excluded — no empty chips.
 *
 * @param {Object} record
 * @returns {Array<{flag, label}>}
 */
function getMiniExBadges(record) {
  const flags = record.feature_flags || {};
  return Object.entries(MINI_EX_BADGE_LABELS)
    .filter(([flag]) => flags[flag] === true)
    .map(([flag, label]) => ({ flag, label }));
}

/**
 * getMachineClassTon(record)
 *
 * Returns a buyer-friendly weight class string based on operating_weight_lbs.
 * Returns null if the field is null or missing.
 *
 * @param {Object} record
 * @returns {string | null}
 */
function getMachineClassTon(record) {
  const weight = record.specs?.operating_weight_lbs;
  if (weight === null || weight === undefined) return null;

  if (weight < 4000)                       return 'Under 2 Ton Class';
  if (weight >= 4000  && weight < 6000)    return '2–3 Ton Class';
  if (weight >= 6000  && weight < 8000)    return '3–4 Ton Class';
  if (weight >= 8000  && weight < 12000)   return '4–6 Ton Class';
  if (weight >= 12000 && weight < 18000)   return '6–9 Ton Class';
  return '9+ Ton Class';
}

/**
 * getDigDepthClass(record)
 *
 * Returns a buyer-friendly dig depth class string based on max_dig_depth_in.
 * Returns null if the field is null or missing.
 *
 * @param {Object} record
 * @returns {string | null}
 */
function getDigDepthClass(record) {
  const depth = record.specs?.max_dig_depth_in;
  if (depth === null || depth === undefined) return null;

  if (depth < 96)                      return 'Under 8 ft Dig Depth';
  if (depth >= 96  && depth < 120)     return '8–10 ft Dig Depth';
  if (depth >= 120 && depth < 144)     return '10–12 ft Dig Depth';
  if (depth >= 144 && depth < 168)     return '12–14 ft Dig Depth';
  return '14+ ft Dig Depth';
}

// ── Readiness tier thresholds ─────────────────────────────────────────────────
//
// Tiers evaluated from highest to lowest; first match wins.
//
//   "extra_standard" = standard_fields_present − essential_fields_present
//   (fields present in the standard tier that are not in the essential tier)
//
//   SPEC_SHEET_READY  all essential present  AND  extra_standard >= 6
//   DEALER_READY      all essential present  AND  extra_standard >= 4
//   FULL_READY        standard_fields_present >= 10
//   CORE_READY        essential_fields_present >= 8
//   WEAK_READY        essential_fields_present >= 5
//   MATCH_ONLY        essential_fields_present < 5
//
// Profile reality check (standard − essential field counts per type):
//   skid_steer / compact_track_loader / mini_excavator : 12 − 8 = 4 extra
//   wheel_loader / excavator                           :  9 − 5 = 4 extra
//   telehandler                                        :  8 − 5 = 3 extra
// → DEALER_READY is the highest achievable tier for all current profiles.
// → SPEC_SHEET_READY becomes reachable when profiles are widened to ≥11 standard fields.
// → FULL_READY (standard_present ≥ 10) is reachable only for SSL/CTL/mini_ex (standard_total = 12).
//
const READINESS_TIERS = [
  { tier: 'SPEC_SHEET_READY', check: (eP, eT, sP) => eP === eT && (sP - eP) >= 6 },
  { tier: 'DEALER_READY',     check: (eP, eT, sP) => eP === eT && (sP - eP) >= 4 },
  { tier: 'FULL_READY',       check: (eP, eT, sP) => sP >= 10                     },
  { tier: 'CORE_READY',       check: (eP)         => eP >= 8                       },
  { tier: 'WEAK_READY',       check: (eP)         => eP >= 5                       },
  { tier: 'MATCH_ONLY',       check: ()           => true                          },
];

/**
 * score_spec_completeness(record, equipment_type)
 *
 * Scores how complete a registry record's specs are against the three display
 * tiers defined in spec_display_profiles.json. Designed to be called after
 * spec injection; does not modify the record or invoke any resolver logic.
 *
 * @param {Object} record          Registry record — must have a `specs` object.
 *                                 Fields with null / undefined / '' are treated as absent.
 * @param {string} equipment_type  'skid_steer' | 'compact_track_loader' | 'mini_excavator'
 *                                 | 'wheel_loader' | 'excavator' | 'telehandler'
 *                                 (or any alias defined in EQUIPMENT_TYPE_ALIASES)
 * @returns {Object|null}          null for unknown or scaffold equipment types.
 *
 * Return shape:
 * {
 *   equipment_type,             // canonical type string
 *   essential_fields_total,     // total essential fields in profile
 *   essential_fields_present,   // essential fields with non-null values in record.specs
 *   standard_fields_total,
 *   standard_fields_present,
 *   technical_fields_total,
 *   technical_fields_present,
 *   completeness_percent,       // standard_present / standard_total × 100 (1 dp)
 *   readiness_tier,             // MATCH_ONLY | WEAK_READY | CORE_READY | FULL_READY
 *                               // | DEALER_READY | SPEC_SHEET_READY
 *   missing_essential,          // array of essential field keys absent from specs
 * }
 */
function score_spec_completeness(record, equipment_type) {
  const cfg            = _resolveProfiles();
  const normalizedType = EQUIPMENT_TYPE_ALIASES[equipment_type] || equipment_type;

  if (!cfg) return null;

  const typeCfg = cfg[normalizedType];
  if (!typeCfg || typeCfg._scaffold) return null;

  const essentialFields  = (typeCfg.essential  || {}).fields || [];
  const standardFields   = (typeCfg.standard   || {}).fields || [];
  const technicalFields  = (typeCfg.technical  || {}).fields || [];

  const specs = record.specs || {};

  function _present(field) {
    const v = specs[field];
    return v !== null && v !== undefined && v !== '';
  }

  const essentialPresent  = essentialFields.filter(_present).length;
  const standardPresent   = standardFields.filter(_present).length;
  const technicalPresent  = technicalFields.filter(_present).length;

  const essentialTotal    = essentialFields.length;
  const standardTotal     = standardFields.length;
  const technicalTotal    = technicalFields.length;

  const completeness_percent = standardTotal > 0
    ? Math.round((standardPresent / standardTotal) * 1000) / 10
    : 0;

  // Highest matching tier wins
  const matched = READINESS_TIERS.find(
    ({ check }) => check(essentialPresent, essentialTotal, standardPresent)
  );

  return {
    equipment_type:           normalizedType,
    essential_fields_total:   essentialTotal,
    essential_fields_present: essentialPresent,
    standard_fields_total:    standardTotal,
    standard_fields_present:  standardPresent,
    technical_fields_total:   technicalTotal,
    technical_fields_present: technicalPresent,
    completeness_percent,
    readiness_tier:           matched ? matched.tier : 'MATCH_ONLY',
    missing_essential:        essentialFields.filter(f => !_present(f)),
  };
}

// ── Internal helpers ──────────────────────────────────────────────────────────

function _format_value(field, raw) {
  if (ENUM_DISPLAY[field]) {
    return ENUM_DISPLAY[field][raw] || String(raw);
  }
  if (typeof raw === 'number') return raw;
  return String(raw);
}

// ── Exports ───────────────────────────────────────────────────────────────────

module.exports = {
  get_spec_profile,
  render_spec_block,
  render_feature_flags,
  getMiniExBadges,
  getMachineClassTon,
  getDigDepthClass,
  score_spec_completeness,
  FIELD_LABELS,
  FIELD_UNITS,
  FLAG_LABELS,
  MINI_EX_BADGE_LABELS,
  READINESS_TIERS,
};
