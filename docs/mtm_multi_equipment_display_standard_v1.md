# MTM Multi-Equipment Display Standard v1

## 1. Purpose
MTM must present listings, spec summaries, and visual outputs in a consistent way across equipment types even when the raw specs differ.

## 2. Core Display Principle
Each equipment type should render specs using the same display hierarchy:
1. Exact
2. Estimated-Narrow
3. Estimated-Broad
4. Suppressed

Soft specs are display-layer only and must never overwrite raw registry fields.

## 3. Universal Display Precedence
For any displayed field:
1. use exact raw registry value if present
2. if exact missing, use soft-spec display value if allowed
3. if soft-spec status is suppressed, omit the field entirely

## 4. Universal Confidence Labels
Define:
- exact_oem
- exact_tier2
- estimated_narrow
- estimated_broad
- suppressed

## 5. Universal Wording Rules
Exact:
- show exact value only

Soft:
- show estimated range/class
- add note:
  "Exact value not provided by OEM"

Suppressed:
- omit entirely
- never show placeholders like N/A or Unknown in customer-facing output

## 6. Cross-Type Output Structure
Each equipment type should try to render:
- headline
- 3–5 key specs
- one machine-positioning sentence
- optional feature highlights
- optional condition/operator notes

## 7. Field Grouping by Equipment Type

### Shared display categories
Define these shared groups:
- Power
- Capacity
- Operating Weight
- Reach / Working Geometry
- Machine Class / Positioning

### Example mapping by type
Skid Steer:
- Power = horsepower
- Capacity = ROC
- Operating Weight = operating_weight
- Reach / Working Geometry = hinge pin
- Machine Class = vertical/radial + frame size

CTL:
- Power = horsepower
- Capacity = ROC
- Operating Weight = operating_weight
- Reach / Working Geometry = hinge pin
- Machine Class = vertical/radial + frame size

Mini Excavator:
- Power = horsepower
- Capacity = operating weight / dig-depth positioning
- Operating Weight = operating_weight
- Reach / Working Geometry = max dig depth
- Machine Class = compact / mid-size / zero-tail / conventional

## 8. Universal “Complete-Feeling Listing” Rule
The system should not depend on every machine having identical raw specs.
The system should create complete-feeling listings by combining:
- exact specs where available
- soft specs where appropriate
- machine positioning language
- market features / dealer inputs

## 9. Launch Rule
No equipment type is launch-ready unless it has:
- exact/raw spec precedence defined
- soft-spec fallback behavior defined
- suppressed-field behavior defined
- at least one display example doc or mapping

## 10. Deferred Standardization
Some equipment types may not yet have finalized soft-spec policies.
Those types must be explicitly flagged before launch.

## 11. Final Rule
Uniform output matters more than uniform raw fields.
The display layer is the cross-type standard.
