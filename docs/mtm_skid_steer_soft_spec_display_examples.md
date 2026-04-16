# MTM Skid Steer Soft Spec Display Examples

This guide uses [mtm_skid_steer_soft_spec_cleanup_v1.json](C:/mtm_mvp3/registry/mtm_skid_steer_soft_spec_cleanup_v1.json) as the display reference source.

## 1. Exact Spec Display Examples
- `bobcat_s590` rated operating capacity: `2,100 lb ROC`
- `bobcat_s590` operating weight: `6,594 lb operating weight`
- `bobcat_s590` bucket hinge pin height: `119 in hinge pin height`
- `bobcat_s650` horsepower: `70 HP`
- `bobcat_s650` rated operating capacity: `2,690 lb ROC`
- `bobcat_s650` operating weight: `7,582 lb operating weight`
- `bobcat_s650` bucket hinge pin height: `122 in hinge pin height`
- `bobcat_s750` rated operating capacity: `3,200 lb ROC`
- `bobcat_s750` operating weight: `9,963 lb operating weight`
- `bobcat_s750` bucket hinge pin height: `127.2 in hinge pin height`

Display convention:
- Show the exact value only.
- Do not add an estimated note.

## 2. Estimated-Narrow Display Examples
- `bobcat_s590` horsepower: `~70-80 HP class`
  Exact value not provided by OEM
- `jd_318d` bucket hinge pin height: `~105-110 in hinge pin class`
  Exact value not provided by OEM
- `jd_318e` bucket hinge pin height: `~105-110 in hinge pin class`
  Exact value not provided by OEM
- `jd_319d` bucket hinge pin height: `~105-110 in hinge pin class`
  Exact value not provided by OEM
- `jd_319e` bucket hinge pin height: `~105-110 in hinge pin class`
  Exact value not provided by OEM
- `jd_318_p_tier` horsepower: `~60-70 HP class`
  Exact value not provided by OEM
- `jd_318_p_tier` rated operating capacity: `~1,200-1,600 lb ROC class`
  Exact value not provided by OEM
- `bobcat_s250` bucket hinge pin height: `~120-125 in hinge pin class`
  Exact value not provided by OEM
- `bobcat_s300` bucket hinge pin height: `~120-125 in hinge pin class`
  Exact value not provided by OEM
- `bobcat_s330` bucket hinge pin height: `~120-125 in hinge pin class`
  Exact value not provided by OEM

Display convention:
- Show the range or class.
- Always add: `Exact value not provided by OEM`

## 3. Estimated-Broad Display Examples
- `bobcat_s750` horsepower: `~70-115 HP class`
  Exact value not provided by OEM
- `gehl_5635sx_ii` horsepower: `~60-90 HP class`
  Exact value not provided by OEM
- `gehl_5635sx_ii` rated operating capacity: `~1,600-2,100 lb ROC class`
  Exact value not provided by OEM
- `gehl_5635sx_ii` operating weight: `~6,000-8,000 lb operating weight class`
  Exact value not provided by OEM
- `gehl_5635sxt` horsepower: `~60-90 HP class`
  Exact value not provided by OEM
- `gehl_5635sxt` rated operating capacity: `~1,600-2,100 lb ROC class`
  Exact value not provided by OEM
- `gehl_5635sxt` operating weight: `~6,000-8,000 lb operating weight class`
  Exact value not provided by OEM
- `gehl_5640e` horsepower: `~60-90 HP class`
  Exact value not provided by OEM
- `gehl_5640e` rated operating capacity: `~1,600-2,100 lb ROC class`
  Exact value not provided by OEM
- `gehl_5640e` operating weight: `~6,000-8,000 lb operating weight class`
  Exact value not provided by OEM

Display convention:
- Show the range or class.
- Always add: `Exact value not provided by OEM`
- Avoid making broad estimated ranges look exact.

## 4. Suppressed-Field Handling Examples
- `kubota_ssv65` operating weight: suppress
- `kubota_ssv75` operating weight: suppress
- `jd_323g` bucket hinge pin height: suppress
- `jd_317` bucket hinge pin height: suppress
- `jd_320` bucket hinge pin height: suppress
- `jd_320d` bucket hinge pin height: suppress
- `jd_320e` bucket hinge pin height: suppress
- `jd_323d` bucket hinge pin height: suppress
- `jd_324e` bucket hinge pin height: suppress
- `jd_332e` bucket hinge pin height: suppress

Display convention:
- Omit the field from customer-facing display.
- Do not show `N/A`, `Unknown`, `TBD`, or blank placeholders.

## 5. Recommended Wording for Listings
- Exact: `70 HP`
- Exact: `2,690 lb ROC`
- Estimated: `~60-70 HP class`
  `Exact value not provided by OEM`
- Estimated: `~6,000-8,000 lb operating weight class`
  `Exact value not provided by OEM`
- Suppressed: do not render the field at all

## 6. Recommended Wording for Spec Sheets
- Exact: `Horsepower: 70 HP`
- Exact: `Rated Operating Capacity: 2,690 lb`
- Estimated: `Horsepower: ~60-70 HP class`
- Estimated note line: `Exact value not provided by OEM`
- Estimated: `Operating Weight: ~6,000-8,000 lb class`
- Suppressed: remove the row entirely instead of showing an empty value

## 7. Recommended Wording for Image Overlays
- Exact: `70 HP`
- Exact: `2,690 lb ROC`
- Estimated: `~60-70 HP class`
- Estimated: `~1,600-2,100 lb ROC class`
- Keep overlay note short when needed:
  `OEM exact not published`
- Suppressed: leave the metric off the overlay

Display convention summary:
- Exact: show exact value
- Estimated: show range or class plus note `Exact value not provided by OEM`
- Suppressed: omit from display and do not show placeholders
