# LAR Variables: Complete Granular Breakdown

This document lists every variable that feeds into the LAR (Likelihood of AI Recommendation) score computation.

## LAR Formula

```
LAR = 0.40·E + 0.25·X + 0.25·A + 0.10·S

With eligibility gate: if E < 60, then LAR = min(LAR, 40)
```

---

## E (Eligibility) Dimension

**Formula**: `E = 0.8 × Product_Score + 0.2 × Family_Score`

**LAR Contribution**: `0.40 × E`

### Product Score Variables (max 100 points)

Evaluates JSON-LD Product schema completeness:

1. **`has_jsonld`** (20 pts) — Server-rendered JSON-LD present in initial HTML
   - **OR** `has_jsonld_js` (15 pts) — JSON-LD rendered via JavaScript (Playwright fallback)

2. **`has_product`** (25 pts) — Product or Service schema present
   - Schema types: `Product`, `Service`

3. **`has_offer`** (20 pts) — Offer schema with price and availability
   - Required fields: `price`, `priceCurrency`, `availability`, `url`

4. **Product Identifiers** (20 pts, tiered):
   - **`has_identifiers_gtin`** (20 pts) — GTIN-13, GTIN-14, or generic GTIN present
   - **OR `has_identifiers_brand_mpn`** (15 pts) — Brand + MPN present (without GTIN)
   - Sources: `sku`, `gtin`, `gtin13`, `gtin14`, `mpn`, `brand.name`

5. **`has_policies`** (10 pts) — Any policy data present (structured or links)
   - See X dimension for policy details

6. **`has_specs_with_units`** (5 pts) — Technical specifications with units
   - Example: `additionalProperty` with `QuantitativeValue` (e.g., "65W", "1920x1080")

### Family Score Variables (max 100 points)

Evaluates ProductGroup and variant relationships:

1. **`has_productgroup`** (40 pts) — ProductGroup schema present

2. **`has_hasvariant`** (20 pts) — `hasVariant` property links to child products

3. **`links_to_children`** (20 pts) — Actual variant links present and valid

4. **`policies`** (10 pts) — Policy data at ProductGroup/family level

5. **`spec_ranges`** (10 pts) — Specification ranges for product family
   - Example: `additionalProperty.value` with `minValue`/`maxValue`

---

## X (eXtensibility) Dimension

**Formula**: `X = X_Policy_Points + X_Specs_Points` (max 100)

**LAR Contribution**: `0.25 × X`

### X Policy Variables (max 50 points, tiered)

Policy data enables AI to answer "What's the return policy?" or "Does it have a warranty?"

**Tiered scoring** (highest tier wins):

1. **`policy_structured`** (50 pts) — Structured policy on product page
   - `hasMerchantReturnPolicy` in Product/Offer JSON-LD
   - `hasWarrantyPromise` in Product/Offer JSON-LD
   - `shippingDetails` in Offer JSON-LD
   - Can be on Product, ProductGroup, or Organization schema

2. **`policy_structured_on_policy_page`** (40 pts) — Structured policy on dedicated page
   - MerchantReturnPolicy schema on `/returns` or `/policy` pages
   - WarrantyPromise schema on `/warranty` pages
   - Requires following policy links and checking for structured data

3. **`policy_link`** (25 pts) — HTML links to policy pages (no structured data)
   - Links containing keywords: "return", "warranty", "shipping", "policy"

4. **No policy information** (0 pts)

### X Specs Variables (max 50 points)

Technical specifications enable AI to answer "Find monitors with 4K resolution" or "Show me cables longer than 5m":

1. **`specs_units`** (50 pts) — Technical specifications with units present
   - `additionalProperty` array with `QuantitativeValue` objects
   - Examples:
     - "Power: 65W" → `{name: "Power", value: {value: 65, unitCode: "WTT"}}`
     - "Resolution: 1920x1080"
     - "Length: 10cm"

2. **No specs with units** (0 pts)

---

## A (Share of Answer) Dimension

**Formula**: Direct score from external measurement

**LAR Contribution**: `0.25 × A`

### A Variables

1. **`soa`** (0-100 scale) — Share of Answer score
   - **Source**: `soa_log.csv` (external tracking)
   - **Measurement**: Percentage of AI-generated answers where retailer appears
   - **Data collection**: Intent logs, AI query testing, competitive analysis

---

## S (Sentiment) Dimension

**Formula**: Centered rating with confidence and source weighting

**LAR Contribution**: `0.10 × S`

### S Raw Input Variables (per product)

**Primary source** (JSON-LD AggregateRating):

1. **`rating_value`** — Star rating (typically 0-5 scale)
   - Extracted from: `Product.aggregateRating.ratingValue`
   - Also checked: Standalone `AggregateRating` entities

2. **`rating_count`** — Number of reviews
   - Extracted from: `Product.aggregateRating.ratingCount` or `reviewCount`

**Fallback source** (embedded JSON or inline JS):

3. **`rating_value_fallback`** — Rating from non-JSON-LD sources
   - Embedded JSON in HTML
   - Inline JavaScript variables
   - JS-rendered content (Playwright)

4. **`rating_count_fallback`** — Fallback review count

5. **`rating_source_fallback`** — Source identifier
   - Examples: "embedded_json", "js_rendered", "inline_script"

### S Computation Process

**Step 1: Source Selection**
- Prefer `rating_value` (JSON-LD primary)
- Fall back to `rating_value_fallback` if JSON-LD missing
- Apply `source_weight`:
  - JSON-LD: `source_weight = 1.0`
  - Fallback: `source_weight = FALLBACK_RATING_WEIGHT = 0.9`

**Step 2: Confidence Weighting**
- Formula: `confidence = min(1.0, rating_count / RATING_CONFIDENCE_THRESHOLD)`
- Where: `RATING_CONFIDENCE_THRESHOLD = 25` reviews
- Rationale: Ratings with fewer reviews are statistically less reliable
- Scale:
  - 0 reviews → 0% confidence
  - 25+ reviews → 100% confidence
  - Linear interpolation between

**Step 3: Centered Normalization**
- Constants:
  - `RATING_NEUTRAL_POINT = 3.5` (out of 5 stars)
  - `RATING_SCALE_RANGE = 1.5`
- Formula: `S_normalized = ((rating_value - 3.5) / 1.5) × 100 × confidence × source_weight`
- Range: -100 (terrible 2.0★) to +100 (perfect 5.0★)
- Key insight: **3.5★ = S of 0** (neutral point, no penalty or reward)

**Step 4: Per-Retailer Aggregation**
- Average all `S_normalized` values across products with ratings
- If no ratings found: `S = 0`

### S Configuration Variables

From `src/asr/config.py`:

- **`RATING_CONFIDENCE_THRESHOLD`** = 25 reviews
  - Threshold for full confidence in rating reliability

- **`FALLBACK_RATING_WEIGHT`** = 0.9
  - Weight applied to non-JSON-LD ratings (slight discount for less structured data)

- **`RATING_NEUTRAL_POINT`** = 3.5 (out of 5 stars)
  - Center point for centered scoring; ratings below this get negative S

- **`RATING_SCALE_RANGE`** = 1.5
  - Denominator for normalization; defines spread of S scores

---

## LAR Eligibility Gate

**Penalty Rule**:
```
if E < 60:
    LAR = min(LAR, 40)
```

**Rationale**: Without basic structured data (E < 60), AI services cannot reliably extract or shortlist products, regardless of other factors. This reflects that machine readability is a **prerequisite** for AI discoverability.

---

## Data Sources Summary

### Primary Audit Data
**Source**: `data/audit_results.csv` (from `asr audit`)

Per-URL columns used in LAR computation:
- `server_jsonld` — JSON-LD in initial HTML (bool)
- `js_jsonld` — JSON-LD via JavaScript (bool)
- `has_product` — Product schema present (bool)
- `has_offer` — Offer schema present (bool)
- `identifiers` — Any identifier present (bool)
- `ident_gtin` — GTIN present (bool)
- `ident_brand_mpn` — Brand+MPN present (bool)
- `policies` — Any policy data (bool)
- `policy_structured` — Structured policy on PDP (bool)
- `policy_link` — Links to policy pages (bool)
- `policy_structured_on_policy_page` — Structured on policy page (bool)
- `specs_units` — Specs with units present (bool)
- `productgroup` — ProductGroup schema (bool)
- `product_score` — Computed product score (0-100)
- `family_score` — Computed family score (0-100)
- `has_rating` — JSON-LD rating present (bool)
- `rating_value` — Primary star rating (float)
- `rating_count` — Primary review count (int)
- `rating_value_fallback` — Fallback rating (float)
- `rating_count_fallback` — Fallback count (int)
- `rating_source_fallback` — Fallback source (string)

### Supplementary Data
**Source**: `data/soa_log.csv`
- `soa` — Share of Answer score per brand/domain (0-100)

### Configuration Constants
**Source**: `src/asr/config.py`
- Product/family scoring weights
- Rating confidence and normalization parameters

---

## Attribution Output

**File**: `data/lar_scores_attribution.csv` (auto-generated by `asr lar`)

Contains per-retailer breakdown:
- Raw dimension scores (E, X, A, S)
- Dimension contributions to LAR (after weighting)
- Underlying component averages:
  - E: product score avg, family score avg
  - X: policy points avg, specs points avg, structured rates
  - S: raw rating avg, count avg, confidence avg, source weight avg, fallback share
- Volume context: URLs audited, ratings found

---

## Visualization

**Script**: `scripts/visualize_attribution.py`

Generates:
1. **Top-N overview**: Stacked contributions (E/X/A/S) with LAR tick
2. **Detailed components**: Split E (product/family) and X (policy/specs) with raw scores annotated
3. **Single-peer deep dive**: 4-panel breakdown showing:
   - E components with raw scores
   - X components with raw points
   - S context (rating, count, confidence)
   - A contribution

**Output**: `data/figures/*.png`

---

## References

- **Methodology**: `docs/methodology.md`
- **Scoring logic**: `docs/scoring.md`
- **Code implementation**: `src/asr/lar.py`, `src/asr/audit.py`
- **Configuration**: `src/asr/config.py`
