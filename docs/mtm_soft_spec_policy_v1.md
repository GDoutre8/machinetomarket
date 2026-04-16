# MTM Soft Spec Policy v1

## 1. Purpose
MTM must show strong, useful listings even when some exact OEM specs are missing.
Soft specs are allowed for display purposes only.
Soft specs must NEVER overwrite raw exact registry fields.

## 2. Spec Display Layers
Define 3 display layers:

### Exact
Use when the registry has a trusted exact value.
Examples:
- 74 HP
- 1,950 lb ROC
- 8,523 lb operating weight

### Estimated-Narrow
Use when exact value is missing but model-family evidence is strong.
Examples:
- ~70–75 HP class
- ~1,900–2,100 lb ROC class
- ~8,000–9,000 lb operating weight class

### Estimated-Broad
Use when only class-level evidence exists.
Examples:
- ~65–80 HP class
- ~1,600–2,200 lb capacity class
- ~6,000–8,000 lb operating weight class

### Suppress
If evidence is too weak or field is too sensitive, do not display a soft spec.

## 3. Raw Data vs Display Data
State clearly:
- Raw registry fields remain exact-only
- Soft specs must never be written into raw exact-value fields
- Soft specs must be generated in a derived display layer only

Examples:
- horsepower_hp = null
- horsepower_display = "~65–75 HP class"
- horsepower_display_confidence = "estimated_narrow"

## 4. Confidence Labels
Define these internal values:
- exact_oem
- exact_tier2
- estimated_narrow
- estimated_broad
- suppressed

## 5. Field-by-Field Policy

### Horsepower
- horsepower_hp = NET horsepower only
- horsepower_gross_hp = GROSS horsepower only
- Gross horsepower must never overwrite horsepower_hp
- If exact net horsepower is missing, use soft horsepower class if confidence supports it

Default band widths:
- 40–50 HP
- 50–60 HP
- 60–70 HP
- 70–80 HP
- 80–90 HP
- 90–100 HP
- 100–115 HP

Rules:
- Use 5 HP ranges only when family confidence is unusually strong
- Use 10 HP ranges by default
- Use 15 HP ranges only for weak/legacy/mixed-era cases

### Rated Operating Capacity
Allow soft ROC classes.

Default bands:
- ~1,200–1,600 lb
- ~1,600–2,100 lb
- ~2,100–2,600 lb
- ~2,600–3,200 lb
- 3,200+ lb

### Operating Weight
Allow soft weight classes.

Default bands:
- ~5,000–6,000 lb
- ~6,000–8,000 lb
- ~8,000–10,000 lb
- 10,000+ lb

### Bucket Hinge Pin Height
Only allow soft hinge-pin class/range if model-family evidence is very strong.
Otherwise suppress.

### Tipping Load
Do not use soft tipping estimates for display unless exact value exists.
Do not surface derived tipping as exact.

### Engine Make
No soft estimate. Exact only.

## 6. Source Priority
1. OEM
2. Tier 2 trusted source (RitchieSpecs, authoritative dealer spec sheet, MachineryTrader spec block, etc.)
3. Derived family inference for display class only
4. Unknown

## 7. Derivation Priority by Field

### Horsepower class
1. exact model OEM net HP
2. exact model trusted source net HP
3. same model family, same frame, same ROC zone
4. derive class from ROC + weight + frame size
5. suppress

### ROC class
1. exact OEM ROC
2. exact trusted ROC
3. same family / same frame cluster
4. derive class from trustworthy exact tipping only if appropriate
5. suppress

### Weight class
1. exact OEM weight
2. exact trusted weight
3. family cluster by frame / era
4. suppress if config-sensitive

## 8. Display Language
When exact exists:
- show exact value

When soft class is used:
- show estimated range/class
- include note:
  "Exact value not provided by OEM"

Examples:
- ~65–75 HP class
  Exact value not provided by OEM

- ~1,600–2,100 lb ROC class
  Exact value not provided by OEM

## 9. Rules for Cleanup Passes
Cleanup passes may:
- fill exact values where safe
- assign soft display ranges where exact values remain missing

Cleanup passes may not:
- overwrite exact raw fields with soft values
- convert gross horsepower into net horsepower silently
- treat derived tipping as exact
- force every model to have identical displayed spec counts

## 10. Goal
The goal is not perfect spec completeness.
The goal is complete-feeling, honest listings with trustworthy data.

Final rule:
Soft specs are a display abstraction, not a raw data replacement.
