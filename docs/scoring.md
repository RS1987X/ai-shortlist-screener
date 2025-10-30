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

## Related Documentation

- LAR model overview: `docs/methodology.md`
- Structured data validation: `scripts/extract_jsonld_playwright.py`
- Schema.org reference: https://schema.org/Product
