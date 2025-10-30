# LAR Model Methodology

## Overview

The **LAR (Likelihood of AI Recommendation)** model quantifies how ready a retailer's product pages are for discovery and shortlisting by AI-powered search services (Google AI Overviews, ChatGPT, Perplexity, etc.).

LAR is a composite score (0-100) based on four dimensions:

```
LAR = 0.40·E + 0.25·X + 0.25·A + 0.10·S
```

With a penalty: if E < 60, then LAR is capped at 40.

**Note on D dimension**: An earlier version included D (Distribution coherence) measuring cross-channel consistency. This has been removed as it's not applicable to third-party retailers selling through own channels. See "D Dimension: Why It Was Removed" section below for details and potential future implementations.

---

## The Four Dimensions

### 1. **E (Enrichment)** - 40% weight
**What it measures:** The quality and completeness of structured product data (JSON-LD/Schema.org).

**Why it matters:** AI crawlers rely on structured data to understand product attributes, pricing, availability, ratings, and specifications. Without it, AI services cannot reliably extract or shortlist products.

**How it's scored:**
- Product-level structured data (80%): name, description, image, price, availability, brand, SKU/GTIN
- Family-level structured data (20%): breadcrumbs, category hierarchy, product relationships

**Machine readability impact:**
- Pages with complete JSON-LD score 80-100
- Pages with partial or missing structured data score 0-40
- JavaScript-rendered JSON-LD is acceptable (as long as it appears in the final DOM)

**Key insight from testing:** Swedish retailers (Elgiganten, NetOnNet, Kjell) all have strong E scores (80+), indicating they're well-positioned for AI discovery.

---

### 2. **X (eXtended attributes)** - 25% weight
**What it measures:** The presence of actionable metadata beyond basic product info—policies (return, warranty, shipping) and technical specifications with units.

**Why it matters:** AI services need to answer user questions like "Does it have free returns?" or "What's the warranty?" without clicking through. Rich metadata enables these answers.

**How it's scored:**
- Policies present (return, warranty, shipping): +50 points
- Specifications with units (e.g., "24 inches", "100W", "1920x1080"): +50 points
- Maximum: 100 points

**Machine readability impact:**
- Policies and specs should be in structured data (e.g., `hasMerchantReturnPolicy`, `hasWarrantyPromise`, `additionalProperty`)
- Plain text policies are harder for AI to parse reliably

**Critical gap identified:** Testing of Swedish retailers (Elgiganten, NetOnNet, Kjell) shows:
- ✅ Strong product-level structured data (E scores 80+)
- ❌ **Zero structured policy data** (no `hasMerchantReturnPolicy` or `hasWarrantyPromise`)
- Impact: Missing 50 points in X dimension, limiting AI's ability to answer policy-related queries

This represents a **significant competitive opportunity** for retailers who implement structured policies correctly.

---

### 3. **A (Answer-ability / Share of Answer)** - 25% weight
**What it measures:** How often a retailer's products appear in AI-generated answers/shortlists for relevant queries.

**Why it matters:** This is the **outcome metric**—actual visibility in AI responses. High E and X scores should lead to high A scores.

**How it's scored:**
- Measure share-of-answer (SOA) across a set of test queries (intents)
- Score = (appearances / total possible appearances) × 100

**Data source:** `data/soa_log.csv` contains historical SOA measurements per brand/domain.

**Feedback loop:** If E and X are high but A is low, there may be external factors (domain authority, content quality, competitive pressure).

---

### 4. **S (Service Quality)** - 10% weight
**What it measures:** Customer satisfaction and brand reputation signals.

**Why it matters:** AI systems likely consider trust signals (review ratings, customer satisfaction) when making recommendations. Retailers with strong service reputations are safer recommendations, reducing risk for AI assistants.

**How it's scored:**

**Automated measurement (default):**
- Extracts `AggregateRating` data from product pages during audit
- Averages `ratingValue` across all audited products per retailer
- Normalized to 0-100 scale (assumes 5-star maximum)
- Only includes products with ratings (no penalty for missing ratings on some products)

**Manual override (optional):**
- Use `--service-csv` to provide aggregated scores from external sources:
  - Trustpilot (overall brand rating)
  - Google Reviews (location-averaged)
  - Prisjakt/PriceRunner (merchant ratings)
- Useful when:
  - Retailer doesn't display product ratings on-site
  - You want to use overall brand reputation instead of product-level ratings
  - External ratings are more comprehensive

**Data sources:**
- **Primary**: Audit CSV (`rating_value`, `rating_count` columns) - auto-computed
- **Override**: `service.csv` with format: `key,score` (0-100 scale)

**Implementation note:** When `--service-csv` is provided, manual scores override auto-computed ratings for matching domains. Domains not in service.csv still use auto-computed ratings.

**Note on original design:** S was originally conceived as "Service/Actionability" to measure booking capabilities (`BookAction`), local business presence (`LocalBusiness`), and installation/repair service offerings. This made sense for service-heavy businesses (automotive service booking, installation services) but provides limited differentiation for product retailers. Customer satisfaction ratings offer better variance and are more directly relevant to AI trust signals for your peer set (electronics, hardware, building materials retailers).

---

## D Dimension: Why It Was Removed

**Original concept**: D (Distribution coherence) was meant to measure cross-channel data consistency (website vs. marketplace vs. PDF manuals) based on the hypothesis that AI systems cross-check multiple sources and penalize inconsistent data.

**Why it doesn't apply to third-party retailers**:

1. **No marketplace presence as vendors**: Retailers like Elgiganten, NetOnNet, Kjell sell through their own websites and physical stores - they don't have "their listing" on Amazon/Prisjakt to compare against. Price comparison sites link TO them, not sell FOR them.

2. **Third-party products**: These retailers sell manufacturers' products (Belkin, Samsung, Bosch). They don't control product manuals or manufacturer specifications.

3. **Limited multi-channel**: Only own website + physical stores, not multiple online channels where data conflicts could occur.

**Redundancy with E**: Even if catalog consistency mattered, averaging E scores across intents already captures implementation consistency - no need for a separate dimension.

### Potential Future D Implementations (Context-Dependent)

If expanding LAR to other business models, D could be re-introduced as:

#### **For Manufacturers/Brands**:
```
D = Cross-channel consistency score

Measure: Compare PDP vs. Amazon listing vs. PDF manual vs. Google Shopping feed
- Price consistency (within refresh window)
- Specification consistency  
- Availability consistency
- Policy consistency
Target: <5% conflict rate across fields

Why it matters: Manufacturers control product data across channels and can be held 
accountable for consistency. AI might cross-verify sources and penalize conflicts.
```

#### **For Omnichannel Retailers**:
```
D = Omnichannel data integration score

Measure:
- Store locator with LocalBusiness schema (30pts)
- In-store pickup structured data (30pts)
- Store-specific inventory APIs (20pts)
- Mobile vs desktop data consistency (20pts)

Why it matters: AI assistants helping users with "buy online, pick up in store" or 
"check local availability" need omnichannel structured data.
```

#### **For Multi-Region Retailers**:
```
D = Multi-surface consistency score

Measure: Check same product across:
- Category page listing vs PDP
- Search results vs PDP
- Mobile site vs desktop site
- Different navigation paths to same product

Score = % of paths with complete structured data

Why it matters: AI crawls from multiple entry points. Inconsistent implementation 
across surfaces signals technical debt and reduces trust.
```

#### **For Marketplace Sellers**:
```
D = Listing quality coherence score

Measure: Compare seller's standalone site vs marketplace listings
- Product title/description consistency
- Image consistency
- Specification match
- Policy alignment (returns, shipping)

Why it matters: Sellers maintaining consistent data across platforms signal 
professionalism and reliability.
```

**Bottom line**: D is context-dependent. For third-party retailers (your current peer set), it's not applicable, so it's been removed to keep the model focused on what retailers actually control (E, X) and what actually matters (A, S).

---

## LAR Model Penalties

### Low Enrichment Penalty
```
if E < 60:
    LAR = min(LAR, 40)
```

**Rationale:** Without basic structured data (E < 60), AI services cannot reliably shortlist products, regardless of other factors. This reflects the reality that machine readability is a **prerequisite** for AI discoverability.

---

## From LAR to AI Shortlist Strategy

### High LAR (70-100): Well-positioned

5. **Critical gap identified:** **Zero structured policy data** across all tested retailers
    - No `hasMerchantReturnPolicy` (return windows, fees, methods)
    - No `hasWarrantyPromise` (warranty duration and coverage)
    - No `shippingDetails` (delivery options and costs)
    - Impact: X dimension scores are reduced by 50 points, limiting AI's ability to answer policy-related queries

This means your research assumption is validated: **Structured data (JSON-LD) is the key differentiator for AI shortlist readiness**, and the major Swedish retailers you're studying are already doing it well for product-level data. However, **policy-level structured data represents a significant untapped opportunity** for competitive advantage in the AI search paradigm.
- **Immediate action required:** Implement JSON-LD for all product pages

## Measurement and Iteration

1. **Discovery:** Use `asr discover` to find product URLs via Google Custom Search API
2. **Audit:** Use `asr audit` to extract and score structured data (E, X components)
3. **Validation:** Use `scripts/extract_jsonld_playwright.py` to verify JS-rendered JSON-LD
4. **LAR Computation:** Use `asr lar` to compute composite scores
5. **SOA Tracking:** Monitor share-of-answer in AI responses over time (feeds back into A component)

**Continuous improvement:** As AI services evolve, the LAR model weights and components can be adjusted to reflect new ranking signals.

---

## References

- Scoring weights: `src/asr/config.py`
- LAR computation: `src/asr/lar.py`
- Structured data validation: `scripts/extract_jsonld_playwright.py`
- Schema.org Product specification: https://schema.org/Product
