# MTM CTL Soft Spec Display Policy — v1

## 1. Purpose

MTM must generate strong CTL listings even when some OEM specs are missing.
Soft specs exist for **display only** — they must **never** overwrite raw registry fields.

---

## 2. Spec Display Layers

### Exact
A trusted value from the registry (OEM or verified secondary source).

Examples:
- 74 HP
- 2,690 lb ROC
- 9,060 lb operating weight
- 125.5 in hinge pin height

### Estimated-Narrow
Strong evidence (ROC-to-HP derivation, same-platform family) supports a tight range.

Examples:
- ~70–80 HP class
- ~2,600–3,200 lb ROC class
- ~8,500–10,000 lb class

*Shown with note:* "Exact value not provided by OEM"

### Estimated-Broad
Weak evidence (frame size only, no spec cross-reference); range spans up to 20 HP or
one weight tier.

Examples:
- ~65–80 HP class
- ~8,500–10,000 lb class

*Shown with note:* "Exact value not provided by OEM"

### Suppressed
Evidence too weak or field too sensitive — field not displayed.

---

## 3. Raw vs Display Separation

| Layer | Rule |
|---|---|
| **Raw registry** | Exact values only. Never modified by soft-spec logic. |
| **Display layer** | May include soft specs. Resolved at render time — not stored in registry. |

Example:
```
horsepower_hp = null                           ← raw registry, untouched
horsepower_display = "~70–80 HP class"         ← display layer only
horsepower_display_confidence = "estimated_narrow"
```

Soft specs are a **display abstraction**, not a raw data replacement.

---

## 4. Confidence Labels

| Label | Meaning |
|---|---|
| `exact_oem` | Value from OEM spec sheet; HIGH confidence, locked in registry |
| `exact_tier2` | Value from trusted secondary source; HIGH or MEDIUM confidence, locked |
| `estimated_narrow` | Strong family or class inference; tight range (≤15 HP, one ROC tier) |
| `estimated_broad` | Weak evidence; wider range (up to 20 HP or one weight tier) |
| `suppressed` | Too uncertain — field not shown |

---

## 5. Field Policy

### 5.1 Horsepower

- `horsepower_hp` = **SAE J1349 net HP only**
- `horsepower_gross_hp` = gross HP field — **never substituted for net**
- Soft HP class allowed when `horsepower_hp` is null

**Derivation chain:**
1. `horsepower_hp` non-null + HIGH/MEDIUM confidence → exact display
2. `horsepower_hp` null + exact ROC available → HP band from ROC (estimated_narrow)
3. `horsepower_hp` null + no ROC + frame_size known → HP band from frame (estimated_broad)
4. No usable context → **suppress**

**HP Bands:**

| Band | Display Label |
|---|---|
| 50–60 HP | ~50–60 HP class |
| 60–70 HP | ~60–70 HP class |
| 70–80 HP | ~70–80 HP class |
| 80–90 HP | ~80–90 HP class |
| 90–100 HP | ~90–100 HP class |
| 100–115 HP | ~100–115 HP class |

**Rules:**
- Default band width: 10 HP
- Maximum band width: 20 HP
- If derivation would require a band wider than 20 HP → **suppress**

---

### 5.2 Rated Operating Capacity (ROC)

Core CTL spec. High importance — soft ROC classes are allowed.

**Derivation chain:**
1. `rated_operating_capacity_lbs` non-null + HIGH/MEDIUM → exact display
2. null + exact HP available → ROC band from HP (estimated_narrow)
3. null + no HP + frame_size known → ROC band from frame (estimated_broad)
4. No usable context → **suppress**

**ROC Bands:**

| Band | Display Label |
|---|---|
| ~1,500–2,000 lb | ~1,500–2,000 lb ROC class |
| ~2,000–2,600 lb | ~2,000–2,600 lb ROC class |
| ~2,600–3,200 lb | ~2,600–3,200 lb ROC class |
| ~3,200–4,000 lb | ~3,200–4,000 lb ROC class |
| 4,000+ lb | 4,000+ lb ROC class |

---

### 5.3 Operating Weight

Soft allowed only if the value is not significantly config-dependent (most CTLs: single
track width, fixed ballast).

**Derivation chain:**
1. `operating_weight_lbs` non-null + HIGH/MEDIUM → exact display
2. null + exact ROC available → weight band from ROC (estimated_narrow)
3. null + no ROC + frame_size known → weight band from frame (estimated_broad)
4. No usable context → **suppress**

**Weight Bands:**

| Band | Display Label |
|---|---|
| ~7,000–8,500 lb | ~7,000–8,500 lb class |
| ~8,500–10,000 lb | ~8,500–10,000 lb class |
| ~10,000–12,000 lb | ~10,000–12,000 lb class |
| 12,000+ lb | 12,000+ lb class |

---

### 5.4 Bucket Hinge Pin Height

**Strict policy.** Hinge pin height is machine-specific and varies across platforms and
lift-path configurations.

**Display rules:**
- `exact_oem` — HIGH confidence + locked → show exact value
- `exact_tier2` — HIGH confidence + locked (secondary source) → show exact value
- `estimated_narrow` — MEDIUM confidence non-null, or tight same-platform family cluster
  (≤3 in spread, ≥2 confirmed siblings) → show approximate range with note
- **suppress** — all other cases (null, LOW confidence, cross-platform inference)

**What is NOT allowed:**
- Cross-platform or cross-generation hinge pin inference
- Deriving hinge pin from frame_size alone
- Estimated-broad for hinge pin

---

### 5.5 Tipping Load

- **Never display soft** — no estimated tipping load classes
- `tipping_load_lbs` derived as ROC × 2 must never be shown as exact
- If null or manual_review → **suppress**

---

### 5.6 Engine Make / Model

- **Exact only** — no inference from brand family
- If unknown → **suppress**

---

## 6. Source Priority

| Priority | Source | Confidence Label |
|---|---|---|
| 1 | OEM spec sheet (confirmed on OEM site) | `exact_oem` |
| 2 | Trusted secondary source — HIGH confidence registry | `exact_tier2` |
| 3 | Family inference — same platform, same generation | `estimated_narrow` |
| 4 | Frame/class inference only | `estimated_broad` |
| 5 | No reliable evidence | `suppressed` |

---

## 7. HP–ROC–Weight Derivation Cross-Reference

```
HP ← ROC        (ROC < 1,500 → ~50–60; < 2,000 → ~60–70; < 2,500 → ~70–80;
                 < 3,000 → ~80–90; < 3,800 → ~90–100; ≥ 3,800 → ~100–115)

ROC ← HP        (HP < 60 → ~1,500–2,000; < 75 → ~2,000–2,600; < 90 → ~2,600–3,200;
                 < 110 → ~3,200–4,000; ≥ 110 → 4,000+)

Weight ← ROC    (ROC < 2,000 → ~7,000–8,500; < 2,800 → ~8,500–10,000;
                 < 3,600 → ~10,000–12,000; ≥ 3,600 → 12,000+)
```

Frame-size fallback (when no cross-spec available):

| Frame | HP (broad) | ROC (broad) | Weight (broad) |
|---|---|---|---|
| small | ~50–70 HP class | ~1,500–2,000 lb | ~7,000–8,500 lb |
| mid | ~65–80 HP class | ~2,000–2,600 lb | ~8,500–10,000 lb |
| large | ~80–100 HP class | ~2,600–3,200 lb | ~10,000–12,000 lb |

---

## 8. Display Language

**Exact value:**
> Show value as-is.
> Example: `74 HP` | `2,690 lb ROC` | `9,060 lb` | `125.5 in`

**Soft class value:**
> Show range with class label.
> Add note: *"Exact value not provided by OEM"*
> Example: `~70–80 HP class`

Soft notes must be:
- Brief and honest
- Never phrased to imply OEM confirmation
- Never omitted from the display card

---

## 9. Cleanup Rules

**Allowed:**
- Assign display classes from band tables above
- Use ROC ↔ HP ↔ weight cross-derivation for estimated_narrow
- Use frame_size fallback for estimated_broad
- Suppress fields that fall below confidence threshold

**NOT allowed:**
- Overwrite raw registry fields with soft values
- Convert gross HP → net HP silently
- Treat ROC × 2 derived tipping load as exact
- Apply hinge pin height from a different platform or generation
- Show estimated tipping load in any form
- Assign estimated_broad to hinge pin height

---

## 10. Policy Goal

Listings should feel:
- **Complete** — no glaring blanks where class is clearly known
- **Honest** — uncertainty acknowledged, never hidden
- **Operator-trustworthy** — no spec that could mislead a buyer or technician

The registry stays clean. Soft specs live only in the display layer.
