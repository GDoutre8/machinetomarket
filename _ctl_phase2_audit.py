"""
CTL Phase 2: V1 Core Spec Completion Audit
Generates four output files:
  ctl_v1_completion_summary.txt
  ctl_missing_field_frequency.csv
  ctl_research_queue.csv
  ctl_top_models_status.csv
"""
import json, csv, os
from collections import Counter

V1_FIELDS = [
    'horsepower_hp',
    'rated_operating_capacity_lbs',
    'tipping_load_lbs',
    'operating_weight_lbs',
    'aux_flow_standard_gpm',
    'travel_speed_high_mph',
    'width_over_tires_in',
    'bucket_hinge_pin_height_in',
]

DIM_FIELDS = {'width_over_tires_in', 'bucket_hinge_pin_height_in'}
PERF_FIELDS = set(V1_FIELDS) - DIM_FIELDS

REGISTRY_PATH  = 'registry/mtm_ctl_registry_v1_6.json'
TOP_MODELS_PATH = 'registry/mtm_top_models_index_v1.json'

# ── Load data ─────────────────────────────────────────────────────────────────

with open(REGISTRY_PATH, encoding='utf-8') as fh:
    ctl_data = json.load(fh)
with open(TOP_MODELS_PATH, encoding='utf-8') as fh:
    top_data = json.load(fh)

records = ctl_data['records']
slug_map = {r.get('model_slug', ''): r for r in records}


# ── Helpers ───────────────────────────────────────────────────────────────────

def get_present(r):
    """Return set of V1 fields that are present and non-null in r's specs."""
    specs = r.get('specs', {})
    present = set()
    for f in V1_FIELDS:
        if f == 'aux_flow_standard_gpm':
            # accept the hydraulic_flow_* alt key used by some CTL records
            if (specs.get('aux_flow_standard_gpm') is not None or
                    specs.get('hydraulic_flow_standard_gpm') is not None):
                present.add(f)
        else:
            if specs.get(f) is not None:
                present.add(f)
    return present


def is_stub(r):
    """
    True when the record has no V1 core specs populated.
    Includes all coverage_stub tier records and any production-tier record
    where every V1 field is null.
    """
    if r.get('registry_tier') == 'coverage_stub':
        return True
    return len(get_present(r)) == 0


def classify(r):
    """Return (bucket_name, missing_fields_list)."""
    if is_stub(r):
        return 'STUB', list(V1_FIELDS)
    missing = [f for f in V1_FIELDS if f not in get_present(r)]
    n = len(missing)
    if n == 0:
        return 'COMPLETE', []
    if n == 1:
        return 'MISSING_1', missing
    if n == 2:
        return 'MISSING_2', missing
    return 'MISSING_3_PLUS', missing


# ── Task 1: Registry Audit ────────────────────────────────────────────────────

buckets = {'COMPLETE': [], 'MISSING_1': [], 'MISSING_2': [], 'MISSING_3_PLUS': [], 'STUB': []}

for r in records:
    bucket, missing = classify(r)
    buckets[bucket].append({
        'manufacturer': r.get('manufacturer', ''),
        'model':        r.get('model', ''),
        'slug':         r.get('model_slug', ''),
        'tier':         r.get('registry_tier', ''),
        'missing':      missing,
    })

total = sum(len(v) for v in buckets.values())


# ── Task 2: Missing field frequency ──────────────────────────────────────────

non_stub_records = [r for r in records if not is_stub(r)]
missing_freq = Counter()
for r in non_stub_records:
    for f in V1_FIELDS:
        if f not in get_present(r):
            missing_freq[f] += 1
ns_total = len(non_stub_records)


# ── Task 3: Research Queue ────────────────────────────────────────────────────

def priority_for(missing):
    """
    Priority 1 → only dimensional fields missing
    Priority 2 → 1 perf field missing (with or without dimensional)
    Priority 3 → 2+ perf fields missing
    """
    perf_missing = [f for f in missing if f in PERF_FIELDS]
    dim_missing  = [f for f in missing if f in DIM_FIELDS]
    if not perf_missing and dim_missing:
        return 1
    if len(perf_missing) == 1:
        return 2
    return 3


research_queue = []
for r in records:
    if is_stub(r):
        continue
    missing = [f for f in V1_FIELDS if f not in get_present(r)]
    if not missing:
        continue
    research_queue.append({
        'priority_level': priority_for(missing),
        'manufacturer':   r.get('manufacturer', ''),
        'model':          r.get('model', ''),
        'slug':           r.get('model_slug', ''),
        'registry_tier':  r.get('registry_tier', ''),
        'n_missing':      len(missing),
        'missing_fields': '; '.join(missing),
    })

research_queue.sort(key=lambda x: (x['priority_level'], x['manufacturer'], x['model']))


# ── Task 4: Top Models Coverage ───────────────────────────────────────────────

ctl_top = [r for r in top_data['records']
           if r.get('equipment_type') == 'compact_track_loader']

top_status = []
for tm in ctl_top:
    all_slugs = [tm['slug']] + tm.get('alt_slugs', [])
    reg_rec = None
    matched_slug = None
    for s in all_slugs:
        if s in slug_map:
            reg_rec = slug_map[s]
            matched_slug = s
            break

    if reg_rec is None:
        top_status.append({
            'priority':     tm['priority'],
            'manufacturer': tm['manufacturer'],
            'model_family': tm['model_family'],
            'slug':         tm['slug'],
            'registry_tier': 'N/A',
            'v1_status':    'NOT_IN_REGISTRY',
            'missing_fields': 'all',
        })
        continue

    present = get_present(reg_rec)
    missing = [f for f in V1_FIELDS if f not in present]

    if is_stub(reg_rec):
        status = 'STUB'
    elif not missing:
        status = 'COMPLETE'
    else:
        status = f'MISSING_{len(missing)}' if len(missing) <= 2 else f'MISSING_{len(missing)}+'

    top_status.append({
        'priority':      tm['priority'],
        'manufacturer':  tm['manufacturer'],
        'model_family':  tm['model_family'],
        'slug':          matched_slug,
        'registry_tier': reg_rec.get('registry_tier', ''),
        'v1_status':     status,
        'missing_fields': '; '.join(missing),
    })

top_status.sort(key=lambda x: x['priority'])


# ── Write: ctl_v1_completion_summary.txt ─────────────────────────────────────

def pct(n, d):
    return f'{100 * n / d:.1f}%' if d else '0.0%'

summary_lines = [
    'CTL V1 Completion Summary',
    '=' * 60,
    'Generated:  2026-03-30',
    f'Registry:   mtm_ctl_registry_v1_6.json  ({total} total records)',
    '',
    'V1 Core Fields (8 required):',
]
for f in V1_FIELDS:
    ftype = 'dimensional' if f in DIM_FIELDS else 'performance'
    summary_lines.append(f'  {f:<42} [{ftype}]')

summary_lines += [
    '',
    'BUCKET SUMMARY',
    '-' * 50,
    f'{"Bucket":<20} {"Count":>6}  {"Pct of Total":>12}',
    '-' * 50,
]
for bucket in ['COMPLETE', 'MISSING_1', 'MISSING_2', 'MISSING_3_PLUS', 'STUB']:
    cnt = len(buckets[bucket])
    summary_lines.append(f'{bucket:<20} {cnt:>6}  {pct(cnt, total):>12}')
summary_lines += [
    '-' * 50,
    f'{"TOTAL":<20} {total:>6}  {"100.0%":>12}',
    '',
    f'Non-stub records (have at least 1 V1 field):  {ns_total}',
    '',
]

# COMPLETE
summary_lines += ['COMPLETE RECORDS', '-' * 50]
for row in sorted(buckets['COMPLETE'], key=lambda x: (x['manufacturer'], x['model'])):
    summary_lines.append(f'  {row["manufacturer"]:<14} {row["model"]:<16}  [{row["slug"]}]  ({row["tier"]})')

# MISSING_1
summary_lines += ['', 'MISSING 1 FIELD', '-' * 50]
for row in sorted(buckets['MISSING_1'], key=lambda x: (x['manufacturer'], x['model'])):
    summary_lines.append(f'  {row["manufacturer"]:<14} {row["model"]:<16}  missing: {row["missing"]}')

# MISSING_2
summary_lines += ['', 'MISSING 2 FIELDS', '-' * 50]
for row in sorted(buckets['MISSING_2'], key=lambda x: (x['manufacturer'], x['model'])):
    summary_lines.append(f'  {row["manufacturer"]:<14} {row["model"]:<16}  missing: {row["missing"]}')

# MISSING_3_PLUS
summary_lines += ['', 'MISSING 3+ FIELDS', '-' * 50]
for row in sorted(buckets['MISSING_3_PLUS'], key=lambda x: (x['manufacturer'], x['model'])):
    summary_lines.append(f'  {row["manufacturer"]:<14} {row["model"]:<16}  missing: {row["missing"]}')

# STUB
summary_lines += ['', f'STUB RECORDS ({len(buckets["STUB"])} coverage stubs — no V1 specs populated)', '-' * 50]
for row in sorted(buckets['STUB'], key=lambda x: (x['manufacturer'], x['model'])):
    summary_lines.append(f'  {row["manufacturer"]:<14} {row["model"]:<16}  [{row["slug"]}]')

summary_lines += [
    '',
    '=' * 60,
    'RESEARCH PRIORITY BREAKDOWN (non-stub records with gaps)',
    '-' * 50,
]
for p in [1, 2, 3]:
    cnt = sum(1 for r in research_queue if r['priority_level'] == p)
    desc = {
        1: 'Only dimensional fields missing (width/hinge pin)',
        2: 'Missing 1 performance field (+/- dimensional)',
        3: 'Missing 2+ performance fields',
    }[p]
    summary_lines.append(f'  Priority {p} ({desc}): {cnt} records')

with open('ctl_v1_completion_summary.txt', 'w', encoding='utf-8') as fh:
    fh.write('\n'.join(summary_lines) + '\n')
print('Written: ctl_v1_completion_summary.txt')


# ── Write: ctl_missing_field_frequency.csv ───────────────────────────────────

with open('ctl_missing_field_frequency.csv', 'w', newline='', encoding='utf-8') as fh:
    w = csv.DictWriter(fh, fieldnames=['field', 'field_type', 'missing_count', 'pct_of_non_stub'])
    w.writeheader()
    for field in V1_FIELDS:
        ftype = 'dimensional' if field in DIM_FIELDS else 'performance'
        w.writerow({
            'field':           field,
            'field_type':      ftype,
            'missing_count':   missing_freq[field],
            'pct_of_non_stub': f'{100 * missing_freq[field] / ns_total:.1f}' if ns_total else '0.0',
        })
print('Written: ctl_missing_field_frequency.csv')


# ── Write: ctl_research_queue.csv ────────────────────────────────────────────

with open('ctl_research_queue.csv', 'w', newline='', encoding='utf-8') as fh:
    w = csv.DictWriter(fh, fieldnames=[
        'priority_level', 'manufacturer', 'model', 'slug',
        'registry_tier', 'n_missing', 'missing_fields',
    ])
    w.writeheader()
    for row in research_queue:
        w.writerow(row)
print('Written: ctl_research_queue.csv')


# ── Write: ctl_top_models_status.csv ─────────────────────────────────────────

with open('ctl_top_models_status.csv', 'w', newline='', encoding='utf-8') as fh:
    w = csv.DictWriter(fh, fieldnames=[
        'priority', 'manufacturer', 'model_family', 'slug',
        'registry_tier', 'v1_status', 'missing_fields',
    ])
    w.writeheader()
    for row in top_status:
        w.writerow(row)
print('Written: ctl_top_models_status.csv')


# ── Print console summary ─────────────────────────────────────────────────────

print()
print('=== CTL V1 COMPLETION AUDIT ===')
print()
print(f'Total records: {total}')
print()
print('BUCKET SUMMARY:')
for bucket in ['COMPLETE', 'MISSING_1', 'MISSING_2', 'MISSING_3_PLUS', 'STUB']:
    cnt = len(buckets[bucket])
    print(f'  {bucket:<18} {cnt:>4}  ({pct(cnt, total)})')
print()
print('MISSING FIELD FREQUENCY (non-stub records):')
for f in V1_FIELDS:
    ftype = 'dim' if f in DIM_FIELDS else 'perf'
    print(f'  {f:<42} {missing_freq[f]:>4}  ({pct(missing_freq[f], ns_total)}) [{ftype}]')
print()
print('RESEARCH QUEUE:')
for p in [1, 2, 3]:
    cnt = sum(1 for r in research_queue if r['priority_level'] == p)
    print(f'  Priority {p}: {cnt} records')
print()
print('TOP MODELS STATUS:')
for ts in top_status:
    missing_str = f'  missing: {ts["missing_fields"]}' if ts['missing_fields'] else ''
    print(f'  p{ts["priority"]} {ts["manufacturer"]:<14} {ts["model_family"]:<24} -> {ts["v1_status"]}{missing_str}')
