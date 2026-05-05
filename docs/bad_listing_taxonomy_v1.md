# Equipment Listing Failure Taxonomy v1

Research purpose: identify listing-copy failure modes for MTM Listing Copy Engine v3. This is a usage intelligence audit, not a blacklist. Many weak phrases become useful when supported by proof, buyer context, and precise machine facts.

Scope sampled: public listing language from MachineryTrader, Equipment Trader, Ritchie List, Boom & Bucket-style inspection listings, dealer listings, and auction-style descriptions across CTL, skid steer, mini excavator, telehandler, excavator, wheel loader, and dozer categories.

Core MTM rule: silence is safer than false specificity.

| failure_mode | what_it_looks_like | why_it_hurts | MTM_guardrail |
|---|---|---|---|
| Weak generic hook | "Nice machine", "clean unit", "ready to work" as the lead | Opens with claims buyers have seen thousands of times and gives no reason to keep reading | Lead with machine identity plus one proven buyer-relevant fact: hours, capacity, dig depth, lift height, high flow GPM, attachment package, inspection status, or price |
| Spec dumping | Long bullet list of HP, weight, ROC, bucket size, cab, tires, serial with no interpretation | Forces the buyer to translate specs into job value | Follow each priority spec family with an outcome sentence when space allows |
| Unsupported condition claims | "No leaks", "no codes", "like new", "needs nothing" without inspection proof | Creates credibility risk and post-sale dispute exposure | Require inspection, code scan, leak check, service record, or condition field before rendering |
| Vague condition | "Good condition", "runs good", "solid machine" | Does not answer what is good: engine, hydraulics, tracks, pins, cab, cosmetics, undercarriage | Prefer component-specific condition: tracks %, undercarriage %, tires %, cab condition, cold start, hydraulics, attachment wear |
| Missing hours | Listing omits meter reading or buries it | Hours are a first-pass buyer filter and affect trust, financing, and resale | If hours are missing, avoid "low hour" and prompt collection; do not imply condition from year alone |
| Missing price | "Call for price" with no pricing context | Increases friction on marketplace buyers and can suppress inquiries | For marketplace/direct copy, include price when available; if not available, CTA should say "confirm current price" not "great deal" |
| Missing attachments | Says "comes loaded" or lists machine features but not included buckets/forks/head | Attachments materially change value and buyer fit | Separate installed features from included attachments; never imply pictured attachment is included unless field confirms it |
| Attachment ambiguity | Photos show forks, mulcher, auger, breaker, or bucket but text does not specify included/excluded | Causes expectation mismatch and wasted leads | Add deterministic line: "Included attachments: X" or "Attachments shown not confirmed included" |
| Weak CTA | "Call for details", "Call now", "Contact us" | Does not tell the buyer what action or verification is next | CTA should offer specific next step: confirm availability, request walkaround, verify included attachments, schedule inspection, discuss delivery/financing |
| Fake urgency | "Won't last long", "priced to sell fast", "first come first served" | Sounds like low-grade classified copy and can reduce dealer credibility | Block urgency unless tied to real auction date, closing date, or inventory event |
| Repeated phrasing | Same lead and CTA across many similar units | Makes dealer inventory feel templated and lowers perceived care | Use deterministic phrase rotation by machine identity while preserving claim gates |
| No use-case framing | "High flow, 2-speed, cab, A/C" only | Buyer must infer whether it fits mulching, grading, pallets, trenching, demolition, snow, loading | Convert features/specs into approved use cases only when supported by specs and feature fields |
| Feature without capability | "High flow" without GPM or attachment fit | High flow varies widely; buyers care what attachments it can run | If GPM present, mention supported attachment families; if GPM missing, say "high-flow equipped" only when confirmed |
| Comfort-only overfocus | Cab, heat, A/C lead on production equipment while capacity/use case is buried | Comfort matters, but buyer value usually starts with productivity and fit | Prioritize production-critical facts before comfort unless platform/audience is owner-operator or premium |
| Overclaiming low hours | "Low hours" on older machines with moderate or unknown usage | Buyers benchmark low hours by year and class; unsupported "low" sounds careless | Gate "low hours" by equipment-specific threshold or phrase as factual hours only |
| "One owner" without proof | "One owner" used as generic trust language | Valuable when true, damaging when unverified | Render only when dealer field or documentation supports ownership count |
| "Fleet maintained" without records | Claiming fleet or rental maintenance without service logs | Fleet-maintained can mean good records or heavy rental use; ambiguous without proof | Require maintenance records, fleet source, or service history; otherwise use neutral source wording |
| "Fresh service" without detail | "Fresh service" with no date, hours, or work performed | Sounds like filler and raises questions about what was serviced | Require service date/hours and service items; render as "Serviced at X hours: filters/oil/etc." |
| Code/leak claims without inspection | "No codes", "dry machine", "no leaks" in uninspected listings | These are high-trust mechanical claims and need proof | Require inspection checklist, diagnostic scan, or leak inspection field |
| Hype adjectives | "Beautiful", "monster", "beast", "mint", "cream puff", "bad boy" | Adds emotional noise while removing professional credibility | Keep adjectives tied to observed facts: "enclosed cab", "75% tracks", "hydraulic thumb", "verified hours" |
| All-caps wall text | "READY TO WORK CALL NOW CLEAN HIGH FLOW CAB A/C" | Hard to scan and feels spammy | Normalize casing; use short sections or sentence blocks by platform |
| Keyword stuffing | Repeating "mini excavator, trackhoe, digger, landscaping, trenching, demolition..." | Hurts readability and sounds search-engine generated | Allow limited synonym tail only for SEO destinations; keep main copy natural |
| Missing known issue disclosure | AC not working, non-runner, leak, codes, worn tracks omitted or softened | Creates bad leads and trust damage | Tier C issues must be disclosed directly and early; do not bury limitations |
| Misleading "turnkey" | "Turnkey" used while attachments, service, codes, or condition are unknown | Strong readiness claim implies verified state | Gate behind inspection passed, no active codes, no visible leaks, service current, and included work-ready configuration |
| Dealer benefits without terms | "Financing available", "delivery available", "warranty available" with no scope | Useful, but vague if used as filler | Render as CTA/support line only; avoid implying approval, price, or coverage unless terms are provided |
| Missing proof assets | No inspection report, close-up photos, service records, oil analysis, or walkaround video for high-value claims | Buyers cannot verify trust phrases, especially on remote transactions | Prompt for proof assets; claims with high dispute risk require proof fields |
| Poor platform fit | Dealer-site long spec copy pasted into Facebook or auction copy pasted into dealer site | Each channel rewards different density, CTA, and proof level | Platform formatter controls length, sections, CTA, proof density, and buyer-value translation |

## Taxonomy Notes

- "Ready to work", "clean machine", "low hours", and "fresh service" are not banned. They are only weak or risky when unsupported.
- Marketplace copy can be shorter and more direct, but short copy still needs a concrete hook.
- Dealer-site and Boom & Bucket-style listings benefit from proof architecture: inspection summary, photos, documents, oil analysis, shipping/financing support, and precise included attachments.
- Auction listings often tolerate sparse language, but MTM should still preserve issue disclosure and avoid unsupported confidence claims.

## Channel Pattern Addendum

Additional research pass, May 5, 2026: sampled live/public indexed listings from MachineryTrader, Equipment Trader, AuctionTime, Ritchie List, Cat Used, IronPlanet, and Boom & Bucket-style inspection pages. Facebook Marketplace remains the hardest source to audit at scale because access is login, location, and session gated; MTM should treat direct FB examples supplied by users/dealers as a future private corpus.

| channel | common observed pattern | what works | failure risk | MTM implication |
|---|---|---|---|---|
| MachineryTrader dealer/classified | Dense spec fields plus short seller description: hours, ROPS, A/C, high flow, aux hydraulics, quick attach, "ready to work" | Structured fields make key facts scannable | Seller description often repeats generic trust phrases without proof | Use structured facts as lead inputs; gate seller-style claims separately |
| MachineryTrader auction-style | "Runs, drives, and operates", "sells as is", known issue notes, hours, basic features | Honest as-is disclosure is useful and concise | Positive claims and known problems can appear side by side without hierarchy | Tier C/auction output must surface issues before generic value language |
| Equipment Trader | SEO-heavy model/category listings, finance/dealer blocks, short private/dealer notes | Good for feature inventory and dealer support phrases | Search pages compress copy; lots of duplicated phrasing and "ready to work" | Keep marketplace copy short but not keyword-stuffed |
| Facebook Marketplace proxy | Public buyer discussions emphasize local radius, price, hours, photos, scam risk, parts support, and ability to inspect | Direct, concrete facts outperform polished prose | Full public listing access is gated; seller proof is often thin | Put price/hours/location/proof first; CTA should invite inspection or walkaround |
| AuctionTime | Repetitive "runs drives and operates", "sells as is", buyer premium/shipping/financing modules | Strong model for issue-first auction disclosure | Copy is often too thin for dealer-pack quality | Use only the disclosure discipline, not the sparse prose style |
| Ritchie List | Dealer/spec-heavy listings with price, hours, serial, warranty, delivery, high-flow GPM, exact telehandler capacity/height | Strong factual density and commercial support | Some pages dump OEM specs without buyer translation | Convert the best specs into buyer outcomes and keep deep specs in spec sheet |
| Cat Used/OEM dealer | Accessory tags, financing/protection/CVA terms, Product Link, warranty/service offers | Strongest commercial support language when terms are specific | Terms can be too complex for marketplace copy | Render financing/warranty only as short gated support lines unless terms are present |
| IronPlanet | Inspection report, limited function checks, oil sample analysis, leak categories, operational/non-operational checks | Excellent proof model for "no leaks", "operational", code/function claims | Inspection language is precise but not sales-friendly | Add inspection-backed claim fields and translate report facts into short trust lines |
| Boom & Bucket-style | "What's great", "What needs work", inspection report, close-up photos, oil analysis, digital glovebox, attachment caveats | Best proof architecture for remote buyers | Long inspection copy can overwhelm if copied directly | Separate proof block from marketing copy; preserve attachment caveat when needed |

## Field Collection Opportunities

The deeper pass reinforced that MTM does not need more adjectives first; it needs more proof fields.

| missing_or_underused_field | unlocks | source pattern |
|---|---|---|
| `runs_drives_operates` | Safer auction/Tier C running-state copy | AuctionTime "runs drives and operates" |
| `known_issues` | Honest issue-forward Tier C copy | AuctionTime, Boom & Bucket "what needs work" |
| `inspection_report_available` | Inspection-backed trust line | IronPlanet, Boom & Bucket |
| `inspection_date` | Time-bounded trust claims | IronPlanet, Boom & Bucket |
| `walkaround_video_url` | Marketplace scam-resistance and remote buyer trust | Facebook Marketplace proxy, Boom & Bucket |
| `seller_identity_verified` | Safer marketplace trust language | Facebook Marketplace proxy |
| `no_visible_leaks` | "No active leaks" or "no dripping leaks" | IronPlanet, Boom & Bucket |
| `leak_seepage_notes` | Distinguish active leaks from seepage | Boom & Bucket examples with seepage/leak nuance |
| `diagnostic_scan_available` | "No active codes" | Inspection-led listings |
| `oil_analysis_available` | Premium remote-buyer trust signal | IronPlanet, Boom & Bucket |
| `hours_verified_source` | Verified meter/GPS/telematics trust | Boom & Bucket hour-meter caveats |
| `attachments_included_confirmed` | Safe attachment package copy | Boom & Bucket specialty-attachment caveat |
| `warranty_expiration_date` | Warranty remaining | Ritchie List, Cat Used |
| `delivery_available_region` | Specific delivery support | Ritchie List nationwide delivery examples |
| `financing_terms_available` | Safer financing copy | MachineryTrader, Equipment Trader, Cat Used |

## Marketplace Trust Flags

For Facebook Marketplace-style output, the highest ROI is often not better adjectives. It is proof that the machine and seller are real.

| trust_flag | buyer_question_it_answers | copy_use |
|---|---|---|
| local inspection available | Can I see it before sending money? | CTA: "Available for local inspection/walkaround." |
| walkaround video available | Is this the actual machine and current condition? | CTA/proof line with video availability |
| serial/stock visible | Can I verify the unit? | Include stock/serial when appropriate |
| dealer business identity | Is this a real seller? | Dealer footer or contact block |
| current photos date | Are photos current? | Optional proof line for marketplace/direct copy |
| attachment inclusion confirmation | Are the pictured attachments included? | Required included/excluded attachment line |
| known issues disclosed | What am I walking into? | Tier C disclosure line |
| parts/service support | Can I maintain it after purchase? | Especially important for off-brand/import mini excavators |

## Failure Frequency And Severity

This table converts the taxonomy into prioritization for engine work. Frequency reflects how often the pattern appeared across indexed public listing samples; severity reflects buyer trust and conversion risk if MTM repeats it.

| failure_mode | observed_frequency | severity | why_priority |
|---|---|---:|---|
| Weak generic hook | Very high | 3 | Common everywhere and easy for MTM to outperform with structured facts |
| Spec dumping | High | 3 | Dealer/spec sites show plenty of facts but little translation |
| Unsupported condition claims | High | 5 | Creates credibility and dispute risk |
| Vague condition | Very high | 4 | "Clean/nice/great" is common and low proof |
| Missing hours | Medium | 5 | Buyers filter heavily by hours; omission hurts trust |
| Missing price | Medium | 3 | More acceptable on dealer sites, weaker on marketplace |
| Missing attachments | High | 4 | Value and buyer fit change materially |
| Attachment ambiguity | Medium | 5 | Source listings explicitly warn attachments shown may not be included |
| Weak CTA | High | 2 | Easy improvement but lower trust risk |
| Fake urgency | Medium | 3 | More spam-like than dangerous unless paired with price claims |
| Repeated phrasing | Very high | 2 | Inventory feels templated and generic |
| No use-case framing | High | 3 | Strong opportunity for MTM differentiation |
| Feature without capability | High | 4 | Especially high flow without GPM or attachment context |
| Comfort-only overfocus | Medium | 2 | Usually not dangerous, just weaker |
| Overclaiming low hours | High | 4 | "Low hours" is stretched across classes/ages |
| One owner without proof | Medium | 5 | High-value trust claim, high dispute risk |
| Fleet maintained without records | Medium | 4 | Ambiguous value; can mean heavy use |
| Fresh service without detail | Medium | 4 | Common, useful only with service specifics |
| Code/leak claims without inspection | Medium | 5 | Strongest trust/dispute risk category |
| Hype adjectives | High | 3 | Common in classified/dealer copy; damages professional tone |
| All-caps wall text | Medium | 2 | Readability issue, mostly marketplace/private seller style |
| Keyword stuffing | Medium | 2 | More SEO noise than trust risk |
| Missing known issue disclosure | Medium | 5 | Auction/inspection sources show issue disclosure is essential |
| Misleading turnkey | Low/Medium | 5 | Less frequent but very risky |
| Dealer benefits without terms | High | 3 | Financing/delivery are useful but can imply too much |
| Missing proof assets | High | 4 | Remote buyers increasingly expect photos/inspection/docs |
| Poor platform fit | High | 3 | Same machine needs different copy density by channel |

Severity scale: 1 = polish issue, 5 = high trust/dispute risk.

## Dealer Intake Questions To Improve Copy

These questions should be asked as structured fields when practical, not buried in free-text notes.

| question | unlocks | prevents |
|---|---|---|
| Are hours verified, and how? | Verified-hours trust line | Unsupported "low hours" |
| Does it run, drive, and operate? | Auction/Tier C running-state copy | Overbroad "ready to work" |
| Any known mechanical, hydraulic, electrical, emissions, or AC issues? | Honest issue-forward copy | Hidden issue risk |
| Has a leak inspection been done? | Leak-specific trust line | Unsupported "no leaks" |
| Has a diagnostic scan been done? | No-code trust line | Unsupported "no codes" |
| Was it recently serviced? If yes, date, hours, and items? | Fresh-service claim | Generic service filler |
| Are service records available? | Fleet/service trust line | Unsupported "maintained" |
| Ownership history known? | One-owner/source claim | Unsupported ownership claims |
| What attachments are included in the price? | Attachment package value | Pictured attachment confusion |
| Are any pictured attachments excluded or subject to change? | Attachment caveat | Buyer expectation mismatch |
| Track/tire/undercarriage percent and source? | Wear-cost trust line | Vague "good tracks/tires" |
| Warranty/protection remaining? Exact date/hours? | Warranty trust line | Unsupported warranty wording |
| Financing available? Any terms allowed in listing? | CTA/support line | Implied approval/rates |
| Delivery available? What geography? | CTA/support line | Overbroad nationwide claim |
| Inspection report, walkaround video, cold-start video, or oil analysis available? | Premium remote-buyer proof | Unsupported condition confidence |

## Equipment-Specific Failure Traps

| equipment_family | high-risk trap | safer MTM behavior |
|---|---|---|
| CTL / skid steer | "High flow" used without GPM or attachment fit | Confirm high-flow status first; use GPM for attachment outcome language |
| CTL / skid steer | "New tracks" without track proof | Require track percent, invoice, or dealer confirmation |
| Mini excavator | Hydraulic thumb/aux/bucket package not clearly included | Separate installed thumb/aux from included buckets/attachments |
| Mini excavator | Dig depth missing from value copy | Use resolved dig depth to frame trenching/drainage/utility fit |
| Telehandler | Lift height stated but capacity at reach ignored | Lead with capacity/height/reach, avoid implying full capacity at max reach |
| Telehandler | Forks shown but not included | Require forks/carriage inclusion or caveat |
| Wheel loader | Bucket/forks/coupler listed without buyer value | Translate to bulk material, pallet work, and yard handling |
| Wheel loader | Tires called "good" without percent | Ask for tire percent or photos; otherwise omit condition adjective |
| Dozer | "Good undercarriage" without measurement | Require percent or component notes |
| Dozer | Grade control named generically | Render exact system/type if available; otherwise say grade-control equipped only when confirmed |
| Excavator | "No leaks/no codes" without inspection | Gate to inspection/scan fields |
| Excavator | Hammer-ready implied from aux hydraulics alone | Require hammer plumbing or auxiliary hydraulic type |

## Engine Implications

- Separate factual specs, verified claims, dealer-entered claims, and marketing wrappers.
- Treat phrases as claim objects with eligibility, not as free text.
- Prefer "what it enables" over "what it has" when the enabling relationship is mechanically true.
- Do not let platform compression remove material disclosures.
- Use "unknown" as a reason to omit, not a reason to soften into vague positivity.
