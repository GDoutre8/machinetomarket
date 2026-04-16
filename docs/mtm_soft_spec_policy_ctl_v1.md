# MTM Soft Spec Policy — CTL v1

## 1. Purpose

MTM must generate strong CTL listings even when some OEM specs are missing.

Soft specs:
- are allowed for **DISPLAY ONLY**
- must **NEVER** overwrite raw registry fields

---

## 2. Spec Display Layers

### Exact
Trusted exact value from registry.

Examples:
- 74 HP
- 2,100 lb ROC
- 8,900 lb operating weight
- 23 GPM auxiliary flow

### Estimated-Narrow
Strong family evidence supports a tight range.

Examples:
- ~70–80 HP class
- ~2,000–2,300 lb ROC class
- ~20–24 GPM flow class

### Estimated-Broad
Weak or mixed evidence; range is wide.

Examples:
- ~65–85 HP class
- ~1,800–2,600 lb class

### Suppress
Too uncertain — do not display.

---

## 3. Raw vs Display

**Raw registry:**
- exact values only
- never modified by soft spec logic

**Display layer:**
- may include soft specs
- soft specs are resolved at render time, not stored in registry

Example:
```
horsepower_hp = null                          ← raw registry, untouched
horsepower_display = "~65–75 HP class"        ← display layer only
horsepower_display_confidence = "estimated_narrow"
```

---

## 4. Confidence Labels

| Label | Meaning |
|---|---|
| `exact_oem` | Value from OEM spec sheet |
| `exact_tier2` | Value from trusted secondary source (HIGH confidence registry) |
| `estimated_narrow` | Strong family or class inference; tight range |
| `estimated_broad` | Weak or mixed evidence; wide range |
| `suppressed` | Too uncertain — field not shown |

---

## 5. Field Policy (CTL)

### Horsepower

- `horsepower_hp` = **net HP only** (SAE J1349)
- never substitute gross HP as net
- soft class display allowed when `horsepower_hp` is null

**Bands:**

| Band | Display Label |
|---|---|
| 40–50 HP | ~40–50 HP class |
| 50–60 HP | ~50–60 HP class |
| 60–70 HP | ~60–70 HP class |
| 70–80 HP | ~70–80 HP class |
| 80–90 HP | ~80–90 HP class |
| 90–100 HP | ~90–100 HP class |
| 100–115 HP | ~100–115 HP class |

---

### Rated Operating Capacity (ROC)

Soft classes allowed when `rated_operating_capacity_lbs` is null.

**Bands:**

| Band | Display Label |
|---|---|
| ~1,200–1,600 lb | ~1,200–1,600 lb ROC class |
| ~1,600–2,100 lb | ~1,600–2,100 lb ROC class |
| ~2,100–2,600 lb | ~2,100–2,600 lb ROC class |
| ~2,600–3,200 lb | ~2,600–3,200 lb ROC class |
| 3,200+ lb | 3,200+ lb ROC class |

---

### Operating Weight

Soft classes allowed when `operating_weight_lbs` is null.

**Bands:**

| Band | Display Label |
|---|---|
| ~5,000–6,000 lb | ~5,000–6,000 lb class |
| ~6,000–8,000 lb | ~6,000–8,000 lb class |
| ~8,000–10,000 lb | ~8,000–10,000 lb class |
| 10,000+ lb | 10,000+ lb class |

---

### Auxiliary Flow *(CTL-specific)*

Soft classes allowed when `aux_flow_standard_gpm` is null.

**Bands:**

| Band | Display Label |
|---|---|
| ~15–20 GPM | ~15–20 GPM class |
| ~20–25 GPM | ~20–25 GPM class |
| ~25–30 GPM | ~25–30 GPM class |
| 30+ GPM | 30+ GPM class |

---

### Travel Speed *(CTL-specific)*

Soft range allowed **only if** the machine class clearly supports a known range (e.g., confirmed two-speed).

Otherwise: **suppress**.

Do not display a travel speed range for single-speed machines unless the speed is exact.

---

### Bucket Hinge Pin Height

**Strict policy:**
- display only if `exact` OR very strong family evidence (same platform, same generation, OEM-confirmed sibling)
- otherwise: **suppress**

Do not use cross-platform or cross-generation inference for hinge pin height.

---

### Tipping Load

- **never display soft** — no estimated tipping load classes
- **never treat ROC × 2 derived values as exact**
- if `tipping_load_lbs` is null or `manual_review`, suppress entirely

---

### Engine Make

- **exact only**
- suppress if unknown; never infer engine manufacturer from brand family alone

---

## 6. Source Priority

1. OEM spec sheet (exact_oem)
2. Trusted secondary source — HIGH confidence registry field (exact_tier2)
3. Family inference — same platform, same generation (estimated_narrow, display only)
4. Unknown — suppress

---

## 7. Display Language

**Exact value:**
> Show value as-is.
> Example: `74 HP`

**Soft value:**
> Show range with class label.
> Add note: *"Exact value not provided by OEM — class estimate shown."*
> Example: `~70–80 HP class`

Soft display notes should be:
- brief
- honest about uncertainty
- never phrased to imply OEM confirmation

---

## 8. Cleanup Rules

**Allowed:**
- assign display classes from band tables above
- use same-platform family inference for estimated_narrow
- suppress fields that fall below confidence threshold

**NOT allowed:**
- overwrite raw registry fields with soft values
- convert gross HP → net HP silently
- treat ROC × 2 derived tipping load as exact
- apply hinge pin height from a different platform or generation
- show estimated_broad ranges for tipping load, hinge pin, or engine make

---

## 9. Goal

Listings should feel:
- **complete** — no glaring blanks where class is clearly known
- **honest** — uncertainty acknowledged, never hidden
- **operator-trustworthy** — no spec that could mislead a buyer or technician

Soft specs are a display abstraction only. The registry stays clean.
