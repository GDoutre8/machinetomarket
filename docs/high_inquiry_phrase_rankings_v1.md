# High Inquiry Phrase Rankings v1

Purpose: rank listing phrases by likely inquiry value, not raw frequency. The goal is to prioritize the phrases and claim families MTM v3 should place into the strongest slots when proof gates pass.

Basis: cross-channel research from dealer listings, MachineryTrader, Equipment Trader, AuctionTime, Ritchie List, Cat Used/OEM used inventory, IronPlanet inspection listings, Boom & Bucket-style listings, and buyer-side marketplace proxy discussions.

Important: high inquiry value does not mean safe by default. Many of the strongest phrases also carry the highest proof burden.

| rank | phrase | why_it_drives_inquiry | best_equipment_type | proof_required | best_slot |
|---:|---|---|---|---|---|
| 1 | hydraulic thumb | One of the clearest mini-ex/excavator value signals; tells buyers the machine can grab brush, logs, concrete, pipe, and demo debris immediately. | mini excavator, excavator | `thumb_type == hydraulic` or attachment confirmed | lead, capability slot |
| 2 | high flow hydraulics | Signals access to higher-dollar attachment work and filters serious CTL/skid steer buyers quickly. | CTL, skid steer | `high_flow == yes`; GPM preferred for outcome copy | lead, capability slot |
| 3 | verified hours | Hours drive price, financing, resale, and buyer trust; "verified" separates MTM copy from ordinary seller claims. | all | `hours`, `hours_verified_source` | lead, trust line |
| 4 | enclosed cab with heat and A/C | Easy to understand, visible in photos, strong comfort/resale value, and widely searched. | CTL, skid steer, mini excavator, wheel loader, dozer | `cab_type == enclosed`; heater/A/C fields if stated | lead or feature block |
| 5 | attachment package included | Changes immediate value and can justify inquiry even when machine price is not the lowest. | mini excavator, CTL, skid steer, wheel loader, telehandler | `attachments_included` confirmed; caveat if pictured attachments excluded | lead, capability slot |
| 6 | inspection report available | Reduces remote-buyer risk and supports higher-trust claims without overexplaining in the listing body. | all, especially excavator/dozer/wheel loader | `inspection_report_available == true` | trust line, CTA |
| 7 | no active fault codes | High confidence signal for Tier 4/electronic machines; especially valuable for remote buyers. | excavator, CTL, skid steer, wheel loader, dozer | diagnostic scan/telematics field with date | trust line |
| 8 | no visible leaks / no active leaks | One of the strongest mechanical trust signals, especially for hydraulics-heavy machines. | excavator, mini excavator, wheel loader, CTL, skid steer | inspection-backed leak status; exact category retained | trust line |
| 9 | fresh service with date/items | Specific service detail lowers near-term uncertainty; generic "fresh service" is much weaker. | all | `service_date` or `service_hours`, `service_items` | trust line |
| 10 | one owner | Strong history signal when verified; often creates inquiry because it implies clearer care and fewer unknowns. | CTL, skid steer, mini excavator, telehandler | `owner_count == 1` or verified ownership | trust line |
| 11 | low hours | Drives clicks and inquiries when defensible by category and age; damaging when stretched. | all | passes `low_hours_benchmarks_v1.yaml`, hours credible | lead |
| 12 | quick coupler / hydraulic coupler | Practical productivity feature; buyers know it saves time and expands attachment use. | mini excavator, excavator, wheel loader, CTL, skid steer | `coupler_type` confirmed | lead, capability slot |
| 13 | multiple buckets included | Very strong for mini excavators because it solves trenching, cleanup, and digging-width needs. | mini excavator, excavator | included bucket list confirmed | lead, capability slot |
| 14 | auxiliary hydraulics | Core attachment-readiness phrase; high intent for buyers planning breakers, augers, thumbs, compactors, and specialty tools. | mini excavator, excavator, skid steer, CTL | aux hydraulics confirmed | capability slot |
| 15 | track percent / undercarriage percent | Major ownership-cost proof; can trigger inquiry from buyers comparing similar machines. | CTL, mini excavator, excavator, dozer | percent plus source/photos preferred | lead or trust/spec line |
| 16 | lift capacity / lift height / reach | Telehandler buyers filter by these numbers before almost anything else. | telehandler | resolved capacity/height/reach specs | lead |
| 17 | forks included | Simple but powerful for telehandler and wheel-loader buyers who need immediate pallet/material handling. | telehandler, wheel loader | attachments included confirms forks/carriage | lead, capability slot |
| 18 | grade control equipped | High-dollar productivity/resale feature that attracts serious contractors. | dozer, excavator | `grade_control_type` confirmed | lead, capability slot |
| 19 | warranty remaining | Strong risk-reducer, especially on newer machines; must be exact. | all newer machines | warranty expiration date/hours and coverage source | trust line |
| 20 | delivery available | Removes logistics friction and expands buyer radius. | all | dealer delivery/shipping availability; region if stated | CTA |
| 21 | financing available | Reduces purchase friction and invites buyer engagement even before final price negotiation. | all dealer listings | financing availability; terms needed for payments/rates | CTA |
| 22 | walkaround video available | Strong marketplace and remote-buyer trust signal; proves current condition better than polished prose. | all | `walkaround_video_url` or video available flag | CTA, trust line |
| 23 | service records available | Stronger than "well maintained"; supports higher-hour machines and fleet units. | all, especially high-dollar equipment | service records attached/available | trust line |
| 24 | 2-speed travel | Practical productivity feature for loaders; often searched and understood by experienced buyers. | CTL, skid steer | `two_speed_travel == yes` | capability slot, feature block |
| 25 | ride control | Useful loader productivity/comfort phrase when moving material; not always lead-worthy but inquiry-positive for the right buyer. | CTL, skid steer, wheel loader | `ride_control == true` | capability slot, feature block |

## Tiered Phrase Groups

### Tier 1 - Lead-Worthy When Proven

These can carry the opening hook when they are supported:

- hydraulic thumb
- high flow hydraulics with GPM
- verified low hours
- enclosed cab with heat and A/C
- attachment package included
- lift capacity / lift height / reach
- grade control equipped
- undercarriage or track percent when strong

### Tier 2 - Trust Builders

These usually belong after the lead because they support confidence more than capability:

- inspection report available
- no active fault codes
- no visible leaks / no active leaks
- fresh service with date/items
- one owner
- warranty remaining
- service records available
- walkaround video available

### Tier 3 - Friction Reducers

These should usually live in CTA/support copy, not the lead:

- delivery available
- financing available
- local inspection available
- request more photos
- confirm included attachments

## Phrases That Drive Inquiries Only When Specific

| generic_phrase | stronger_inquiry_version |
|---|---|
| fresh service | "Serviced at 1,842 hours: engine oil, filters, hydraulic service." |
| clean machine | "Clean cab, straight panels, dry engine bay shown in inspection/photos." |
| low hours | "1,124 verified hours, below MTM low-hour threshold for this category/age." |
| ready to work | "Runs, drives, operates; inspection report available." |
| high flow | "45.1 GPM high-flow hydraulics for compatible mulchers, trenchers, and planers." |
| good tracks | "Tracks measured/stated at 75% remaining." |
| good undercarriage | "Undercarriage measured/stated at 70% remaining." |
| attachment package | "Includes 12 in, 18 in, and 24 in buckets plus hydraulic thumb." |
| warranty | "Factory warranty remaining until DATE or HOURS, subject to transfer/terms." |
| delivery | "Delivery available; contact for quote to your ZIP." |

## Slot Guidance

| slot | phrase families to prefer | phrase families to avoid |
|---|---|---|
| lead | capability, verified hours, high-value attachments, capacity, strong wear proof | generic ready/clean/nice, financing/delivery, unsupported trust claims |
| capability slot | high flow, thumb, aux hydraulics, coupler, 2-speed, ride control, grade control, lift/reach/dig-depth translation | ownership/service claims |
| features block | cab, camera, control type, radio, air ride, backup camera, stabilizers, lights | vague adjectives |
| trust line | inspection, no codes, no leaks, service records, one owner, warranty, verified hours | unverified readiness |
| CTA | delivery, financing, walkaround video, inspection, availability, attachment confirmation | fake urgency |

## Engine Decision Notes

- Inquiry probability should be weighted by equipment type. "Hydraulic thumb" is top-tier for mini excavators and excavators but irrelevant elsewhere.
- Proof burden should override inquiry value. "No leaks" is high-inquiry but must never bypass inspection gating.
- Overused phrases can still convert if paired with proof. "Ready to work" alone is weak; "runs, drives, operates; inspection report available" is materially stronger.
- Commercial support phrases are useful but should not displace machine-value phrases in the lead.
- For marketplace-style output, "walkaround video available" and "local inspection available" should score higher than polished dealer prose because buyer scam anxiety is higher.
