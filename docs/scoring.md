# Scoring Components

This document details how product and family scores are computed in the LAR model's **E (Enrichment)** dimension.

---

## E (Enrichment) Score Composition

```
E = 0.8 × Product_Score + 0.2 × Family_Score
```

**Product_Score** measures the completeness of product-level structured data.  
**Family_Score** measures the presence of category/navigation context.

---

## Product Score (80% of E)

The product score evaluates JSON-LD `@type: "Product"` structured data completeness.

### Core Attributes (Required)
- `name`: Product name
- `description`: Product description
- `image`: Product image URL
- `url`: Canonical product URL
- `sku` or `gtin` or `mpn`: Product identifier

**Score contribution:** 40 points (8 points per attribute)

### Offer Information (Critical for E-commerce)
- `offers` array with at least one `Offer` object containing:
  - `price`: Numeric price value
  - `priceCurrency`: Currency code (e.g., "SEK", "USD")
  - `availability`: Stock status (e.g., "https://schema.org/InStock")
  - `url`: Link to purchase

**Score contribution:** 30 points (7.5 points per sub-attribute)

### Brand Information
- `brand` object with `name` and optionally `url`

**Score contribution:** 10 points

### Ratings and Reviews
- `aggregateRating` with `ratingValue` and `reviewCount`
- Individual `review` objects (optional, but signals quality)

**Score contribution:** 10 points for aggregateRating, +5 bonus for reviews

### Additional Enrichment
- `itemCondition`: New, used, refurbished
- Multiple offer types (standard, business, in-store pickup)
- Product images: multiple angles, high resolution

**Score contribution:** 10 points

**Maximum Product Score:** 100

---

## Policy Structured Data: A Critical Gap

### Current State (Swedish Retailers)

Testing reveals that **major Swedish electronics retailers have strong product schemas but zero structured policy data:**

| Retailer | Product Schema | Policy Schema |
|----------|---------------|---------------|
| Elgiganten | ✅ Complete | ❌ Missing |
| NetOnNet | ✅ Complete | ❌ Missing |
| Kjell & Company | ✅ Complete | ❌ Missing |

**What's missing:**
- `hasMerchantReturnPolicy`: Return window, fees, methods
- `hasWarrantyPromise`: Warranty duration and coverage
- `shippingDetails`: Delivery options and costs

**Impact:**
- X dimension score: Missing 50 points out of 100
- AI cannot answer: "What's the return policy?" or "How long is the warranty?"
- Users must click through to policy pages (friction, lower conversion)

### Proper Implementation

**Return Policy (Schema.org `MerchantReturnPolicy`):**
```json
{
  "@type": "Product",
  "name": "Belkin USB-C 6-i-1 adapter",
  "hasMerchantReturnPolicy": {
    "@type": "MerchantReturnPolicy",
    "applicableCountry": "SE",
    "returnPolicyCategory": "https://schema.org/MerchantReturnFiniteReturnWindow",
    "merchantReturnDays": 30,
    "returnMethod": "https://schema.org/ReturnByMail",
    "returnFees": "https://schema.org/FreeReturn"
  }
}
```

**Warranty (Schema.org `WarrantyPromise`):**
```json
{
  "@type": "Product",
  "name": "Belkin USB-C 6-i-1 adapter",
  "hasWarrantyPromise": {
    "@type": "WarrantyPromise",
    "durationOfWarranty": {
      "@type": "QuantitativeValue",
      "value": 2,
      "unitCode": "ANN"
    },
    "warrantyScope": "https://schema.org/LaborAndParts"
  }
}
```

**Shipping Details (Schema.org `OfferShippingDetails`):**
```json
{
  "@type": "Product",
  "name": "Belkin USB-C 6-i-1 adapter",
  "offers": {
    "@type": "Offer",
    "price": "859",
    "priceCurrency": "SEK",
    "shippingDetails": {
      "@type": "OfferShippingDetails",
      "shippingRate": {
        "@type": "MonetaryAmount",
        "value": "0",
        "currency": "SEK"
      },
      "deliveryTime": {
        "@type": "ShippingDeliveryTime",
        "handlingTime": {
          "@type": "QuantitativeValue",
          "minValue": 1,
          "maxValue": 2,
          "unitCode": "DAY"
        },
        "transitTime": {
          "@type": "QuantitativeValue",
          "minValue": 2,
          "maxValue": 5,
          "unitCode": "DAY"
        }
      }
    }
  }
}
```

### Why This Matters for AI Shortlist Readiness

**User queries that require policy data:**
- "Show me USB hubs with free returns"
- "Which monitors have a 2-year warranty?"
- "Find laptops with free shipping"
- "Compare return policies for these products"

**Without structured policy data:**
- ❌ AI cannot filter or rank by policy criteria
- ❌ AI cannot provide policy comparisons in answers
- ❌ Products are less likely to appear in policy-aware shortlists

**With structured policy data:**
- ✅ AI can extract and compare policies across retailers
- ✅ Products appear in policy-specific queries
- ✅ AI can generate rich answers: "This product offers free 30-day returns and a 2-year warranty"
- ✅ Competitive advantage in the AI search paradigm

### Competitive Opportunity

Implementing structured policy data is a **low-hanging fruit** for retailers:
- Policies are already defined (legal requirement)
- Implementation is a one-time effort (add to product schema template)
- Immediate impact on X score and LAR
- First-mover advantage in policy-aware AI search

**Estimated LAR impact:**
- Current (no policies): X ≈ 50, contributing 10 points to LAR
- With policies: X ≈ 100, contributing 20 points to LAR
- **Net gain: +10 LAR points** (e.g., from 75 to 85)

---

## Family Score (20% of E)

The family score evaluates contextual structured data that helps AI understand the product's category and hierarchy.

### Breadcrumb Navigation
- `@type: "BreadcrumbList"` with `itemListElement` array
- Each item has `position`, `name`, and `item` (URL)

**Score contribution:** 60 points

### Category/Collection Context
- Product is linked to a category page with structured data
- Category page has `@type: "CollectionPage"` or `@type: "ItemList"`

**Score contribution:** 20 points

### Related Products
- `isRelatedTo` or `isSimilarTo` links to other products
- Structured product recommendations

**Score contribution:** 20 points

**Maximum Family Score:** 100

---

## Example Scoring

### Example 1: Elgiganten USB-C Hub
From `output.json`:

**Product-level data present:**
- ✅ name: "Belkin USB-C 6-i-1 adapter"
- ✅ description: Full product description
- ✅ image: Product image URL
- ✅ url: Canonical URL
- ✅ sku: "286349"
- ✅ gtin: "745883819829"
- ✅ mpn: "AVC008btSGY"
- ✅ brand: "Belkin" with URL
- ✅ offers: Two offer types (standard, business) with price, currency, availability, URL
- ✅ aggregateRating: 4.6 rating, 27 reviews
- ✅ review: Individual review objects
- ✅ itemCondition: NewCondition

**Product Score:** 95/100 (near-perfect)

**Family-level data present:**
- ✅ BreadcrumbList: 3-level hierarchy (Datorer & Kontor → Datortillbehör → Dockningsstation)

**Family Score:** 60/100 (breadcrumbs only, no collection or related products)

**E Score:** 0.8 × 95 + 0.2 × 60 = **88**

---

### Example 2: Hypothetical Poor Implementation

**Product-level data present:**
- ✅ name: "USB Hub"
- ❌ description: Missing
- ✅ image: Product image URL
- ❌ url: Missing canonical URL
- ❌ sku/gtin/mpn: No identifiers
- ❌ brand: Missing
- ⚠️ offers: Price only, no currency or availability
- ❌ aggregateRating: Missing

**Product Score:** 25/100

**Family-level data present:**
- ❌ BreadcrumbList: Missing
- ❌ Category context: Missing

**Family Score:** 0/100

**E Score:** 0.8 × 25 + 0.2 × 0 = **20**

**LAR penalty applied:** Since E < 60, LAR is capped at 40 regardless of other dimensions.

---

## Best Practices for High E Scores

1. **Implement complete Product schema:** Don't skip "optional" fields—AI uses them
2. **Use multiple identifiers:** Include SKU, GTIN, and MPN when available
3. **Structured offers:** Always include price, currency, availability, and URL
4. **Add policy structured data:** Implement `hasMerchantReturnPolicy`, `hasWarrantyPromise`, and `shippingDetails`
5. **Breadcrumbs are essential:** They help AI understand product categories
6. **Ratings signal quality:** Include aggregateRating even with low review counts
7. **Multiple offers:** Business pricing, in-store pickup options boost scores
8. **Technical specs with units:** Use `additionalProperty` with `QuantitativeValue`
9. **Validate with tools:** Use `scripts/extract_jsonld_playwright.py` to test

---

## Common Pitfalls

### 1. **Partial JSON-LD**
Having a Product schema with only name and image is worse than no schema at all—it signals incomplete implementation.

### 2. **Static vs. Dynamic Data**
Ensure price and availability update in real-time in the JSON-LD, not just in the HTML.

### 3. **JavaScript-only Rendering**
JSON-LD injected by JS is fine, but verify with Playwright that it appears in the final DOM.

### 4. **Missing Currency**
Price without `priceCurrency` is ambiguous and may be ignored by AI crawlers.

### 5. **No Identifiers**
Products without SKU/GTIN/MPN are hard to match across retailer sites and AI knowledge bases.

### 6. **Plain Text Policies (The Swedish Retailer Gap)**
**Most critical pitfall identified in testing:**
- Swedish retailers have policies in text (footer, separate pages) but not in structured data
- AI cannot reliably extract or compare policies
- Missing 50 points in X dimension
- Products excluded from policy-aware AI queries

**Solution:** Add `hasMerchantReturnPolicy` and `hasWarrantyPromise` to product schemas.

---

## Scoring Implementation

Product and family scoring logic is in `src/asr/audit.py`:

- `_score_product()`: Analyzes JSON-LD Product schema
- `_score_family()`: Analyzes BreadcrumbList and category context
- `compute_e()`: Combines product and family scores with 80/20 weighting

Scoring weights and thresholds are configurable in `src/asr/config.py`.

---

## X (eXtensibility) Dimension

The X dimension measures how well AI can **extend** the shopping experience beyond basic product information. It consists of two independent components:

### X Calculation

```
X = x_policy + x_specs  (max 100 points)
```

### 1. Policy Information (max 50 points)

Tiered scoring based on policy data richness:

- **50 pts:** Structured policy on product page (`policy_structured=1`)
  - `hasMerchantReturnPolicy` or `hasWarrantyPromise` fields in Product/Offer JSON-LD
  - Enables AI to extract and compare policies programmatically
  
- **40 pts:** Structured policy on separate policy page (`policy_structured_on_policy_page=1`)
  - MerchantReturnPolicy schema on dedicated policy pages
  - Good but requires AI to follow links
  
- **25 pts:** Links to policy pages only (`policy_link=1`)
  - HTML links containing "return", "warranty", "shipping"
  - Basic discoverability, requires text extraction
  
- **0 pts:** No policy information

**Why this matters:**
- "Show me USB hubs with free returns"
- "Which monitors have a 2-year warranty?"
- AI can filter/rank by policy criteria only with structured data

### 2. Technical Specifications (max 50 points)

- **50 pts:** Product has technical specs with units (`specs_units=1`)
  - Examples: "Resolution: 1920x1080", "Power: 65W", "Length: 10cm"
  - Enables AI to answer technical questions precisely
  
- **0 pts:** No specs or specs without units

**Why this matters:**
- "Find HDMI cables longer than 5 meters"
- "Show me monitors with 4K resolution"
- AI needs structured units for comparisons and filtering

### Current Industry Status (Oct 2025)

**Audit findings across 227 Swedish retail product pages:**

| Component | Coverage | Status |
|-----------|----------|--------|
| Policy structured | ~45% | ⚠️ Mixed adoption |
| Policy links | ~95% | ✅ Nearly universal |
| Specs with units | **0%** | ❌ **Industry gap** |

**Key insights:**

1. **Policy data:** Mixed adoption. Leaders (NetOnNet, Elgiganten) have structured policies; others only have links.

2. **Specs with units:** **Zero adoption** across all retailers sampled.
   - This is likely a **detection issue** rather than total absence
   - Retailers may have specs in unstructured formats (tables, paragraphs)
   - Our current parser may not recognize all Schema.org spec patterns
   - **Action item:** Improve specs detection in future versions

3. **Fair comparison:** Since all retailers score 0% on specs, no one is unfairly penalized in current rankings.

4. **Intent balancing:** Products sampled across standardized intents (electronics, tools, etc.) to minimize bias from product mix.

### X Dimension Limitations

**Product category bias potential:**
- Electronics/tools: More meaningful specs (resolution, power, dimensions)
- Consumables/accessories: Fewer meaningful technical specs
- Current mitigation: Intent-based sampling ensures comparable product types across retailers
- Future enhancement: Category-specific spec weights

**Detection accuracy:**
- Specs may exist but not be detected if in non-standard formats
- Future work: Enhanced parsing of PropertyValue, additionalProperty patterns
- Manual validation recommended for critical decisions

---

## Updates (Oct 31, 2025)

### Tiered identifier scoring

To better reflect cross-retailer matchability, identifier scoring is now tiered:

- Full credit when GTIN13/14 is present (`ident_gtin = 1`)
- Discounted credit when only Brand+MPN is present (`ident_brand_mpn = 1`)

Weights in `src/asr/config.py`:

- `has_identifiers_gtin`: 20 pts
- `has_identifiers_brand_mpn`: 12 pts

The legacy `identifiers` column remains (1 if either is present) for backward compatibility.

### JS-rendered JSON-LD fallback (discounted)

Some retailers inject JSON-LD via JavaScript. The audit now performs a single headless render when needed to capture JSON-LD and ratings in one pass. To reflect crawlability/accessibility costs, JS-rendered JSON-LD carries a slightly lower weight than server-rendered JSON-LD:

- `has_jsonld`: 20 pts (server-rendered, initial HTML)
- `has_jsonld_js`: 15 pts (JS-injected)

New transparency fields in `audit_results.csv`:

- `js_jsonld` (1/0), `ident_gtin` (1/0), `ident_brand_mpn` (1/0)

### S (Service) Dimension: Confidence Weighting (v1.2.0)

Ratings are now weighted by their statistical confidence based on review count. A 5.0/5 rating with 1 review is less valuable than a 4.0/5 rating with 50 reviews.

**Formula:**
```python
confidence = min(1.0, rating_count / 25)
S_score = (rating / 5.0) * 100 * confidence
```

**Rationale:**
- Threshold of 25 reviews provides ±10% margin of error at 95% confidence
- Balances statistical rigor with practical achievability
- Penalizes retailers relying on sparse, unreliable ratings
- Rewards consistent quality across well-reviewed products

**Impact:** Retailers with low review counts (e.g., Elgiganten avg 4.4 reviews) see S scores drop 70-80%. Retailers with solid review volumes (e.g., Rusta avg 61 reviews) maintain high scores.

**See:** [docs/confidence_weighting.md](confidence_weighting.md) for full theoretical justification and impact analysis.

---

## Related Documentation

- LAR model overview: `docs/methodology.md`
- Confidence weighting details: `docs/confidence_weighting.md`
- Structured data validation: `scripts/extract_jsonld_playwright.py`
- Schema.org reference: https://schema.org/Product

