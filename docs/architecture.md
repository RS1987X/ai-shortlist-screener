# Architecture Overview

This document provides a high-level overview of the AI Shortlist Screener (ASR/LAR) system, explaining how data flows from discovery to final scoring, key design decisions, and implementation details.

---

## System Purpose

The ASR/LAR system evaluates how ready retailers' product pages are for discovery and recommendation by AI-powered search services (Google AI Overviews, ChatGPT, Perplexity, etc.). It measures structured data quality, policy transparency, actual AI visibility, and service reputation.

**Core output**: A LAR (Likelihood of AI Recommendation) score (0-100) for each retailer, computed from four weighted dimensions.

---

## Three-Stage Pipeline

The system operates in three sequential stages:

```
1. DISCOVER  →  2. AUDIT  →  3. LAR
   (Find URLs)    (Extract Data)  (Compute Scores)
```

### Stage 1: DISCOVER - URL Discovery

**Purpose**: Find relevant product URLs for each intent × peer combination.

**Input**:
- `data/intents/intents_peer_core_sv.csv`: Search intents (product queries like "usb-c adapter", "portable charger 20000mah")
- `data/multibrand_retailer_peers.csv`: Peer retailers with domains (Elgiganten, NetOnNet, Kjell, etc.)

**Output**:
- `data/audit_urls.csv`: CSV with columns: `intent_id, brand, domain, url, relevance_score, title, search_query, found`

**Implementation**: Three discovery methods available:

#### Method 1: Sitemap Search (Primary - **Recommended**)
**File**: `src/asr/sitemap_search.py`

**How it works**:
1. Loads retailer sitemap URLs from `SITEMAP_URLS` dict (hardcoded for 14 retailers)
2. For each intent × peer combination:
   - Extracts search terms from intent using `extract_search_terms()`:
     - **Normalized numeric specs**: "20 000 mAh" → "20000mah" + "20000" (companion tokens)
     - **Unit patterns**: 30+ types (mah, w, hz, gb, l, mm, v, db, lm, etc.)
     - **Text normalization**: wi-fi→wifi, m²→m2, m³→m3
     - **Stopword filtering**: Removes Swedish stopwords, pure numbers, unit-only tokens
   - Fetches sitemap XML and filters to product detail pages (PDPs)
   - Uses **tiered PDP detection**:
     - **Relaxed mode** (3+ path segments): For sitemaps with "product"/"pdp"/"produkt" in filename
     - **Strict mode** (4+ path segments): For generic sitemaps
     - **Always rejects**: /c/, /f/, ?filter, &category patterns
     - **Generic endings filter**: products, produkter, catalog, items, search, list, etc.
   - Scores URLs by search term frequency in path/query
   - Returns best matching URL with relevance score

**Key design choices**:
- **In-memory caching**: Domain URLs cached after first fetch to avoid reloading for subsequent searches
- **Language-specific sitemaps**: Some retailers (Rusta) require explicit language parameters (`?batch=0&language=sv-se`)
- **Tiered filtering**: Product sitemaps can use relaxed rules (3+ segments), generic sitemaps require strict validation (4+ segments)
- **No JavaScript**: Pure XML parsing, no browser automation needed
- **Respects robots.txt**: Sitemap URLs follow standard conventions

**Advantages**:
- ✅ Free (no API costs)
- ✅ Fast (5-10 seconds per retailer, reuses cached URLs)
- ✅ No rate limits
- ✅ High precision (direct product URLs from authoritative source)
- ✅ 62.4% coverage achieved (227/364 intent×peer combinations)

**Limitations**:
- ❌ 3 retailers blocked by Cloudflare (Dustin, Jula) or return 403
- ❌ 1 retailer missing sitemap (Beijerbygg)
- ❌ Some retailers have category URLs mixed in product sitemaps (requires strict filtering)

**Coverage by retailer** (as of Oct 31, 2025):
| Retailer | URLs Found | Total Intents | Coverage |
|----------|------------|---------------|----------|
| Elgiganten | 25 | 26 | 96% |
| Bygghemma | 24 | 26 | 92% |
| Hornbach | 23 | 26 | 88% |
| K-bygg | 23 | 26 | 88% |
| Clas Ohlson | 23 | 26 | 88% |
| Byggmax | 22 | 26 | 85% |
| Biltema | 21 | 26 | 81% |
| Kjell | 20 | 26 | 77% |
| Rusta | 18 | 26 | 69% |
| NetOnNet | 17 | 26 | 65% |
| Mekonomen | 11 | 26 | 42% |
| Dustin | 0 | 26 | 0% (blocked) |
| Jula | 0 | 26 | 0% (blocked) |
| Beijerbygg | 0 | 26 | 0% (no sitemap) |

#### Method 2: Google Custom Search API (Fallback)
**File**: `src/asr/discover.py` (URLDiscoverer class)

**How it works**:
1. Constructs search queries: `site:domain.com search terms from intent`
2. Calls Google Custom Search JSON API
3. Filters results to product detail pages
4. Returns top result with relevance score

**Advantages**:
- ✅ Works for any retailer with Google indexing
- ✅ Can find products not in sitemaps (JavaScript-rendered pages)

**Limitations**:
- ❌ 100 free queries/day (then $5/1000 queries)
- ❌ Rate limited
- ❌ Requires API key setup
- ❌ Results quality varies (may return category pages, blog posts)

**Use case**: Fallback for retailers blocked or missing from sitemaps.

#### Method 3: Site Search (Experimental)
**Files**: `src/asr/site_search.py`, `src/asr/site_search_playwright.py`

**How it works**:
1. Discovers site search endpoint (looks for `<form>` with `action` containing "search"/"sok")
2. Submits search queries to retailer's own search
3. Extracts product links from search results page
4. Playwright version uses browser automation for JavaScript-heavy sites

**Status**: Experimental, not used in production pipeline. Complex to maintain due to varying site structures.

---

### Stage 2: AUDIT - Structured Data Extraction

**Purpose**: Fetch product pages and extract structured data (JSON-LD/Schema.org), ratings, policies, and specs.

**Input**:
- `data/audit_urls.csv`: URLs from discovery stage

**Output**:
- `data/audit_results.csv`: CSV with 20+ columns including:
  - `url, domain, intent_id, brand`
  - `product_score, family_score` (E dimension components)
  - `policy_structured, policy_structured_on_policy_page, policy_link` (X dimension)
  - `specs_units` (X dimension)
  - `rating_value, rating_count, rating_source` (S dimension)
  - `rating_value_fallback, rating_source_fallback` (S fallback)
  - JSON-LD presence indicators, breadcrumbs, etc.

**Implementation**: `src/asr/audit.py`

**How it works**:

1. **Fetch product pages** (`fetch_html()` from `src/asr/fetch.py`):
   - Uses `httpx.Client` with browser-like headers
   - 3 retry attempts with exponential backoff
   - 15 second timeout per request
   - Follows redirects automatically

2. **Extract structured data** (`parse.py`):
   - **JSON-LD extraction** (`extract_jsonld()`):
     - Uses `extruct` library to parse `<script type="application/ld+json">` tags
     - Handles both server-rendered and client-rendered JSON-LD
     - Classifies by `@type`: Product, Offer, ProductGroup, AggregateRating
   
   - **Product scoring** (`score_product()`):
     - Core attributes (40 pts): name, description, image, url, sku/gtin/mpn
     - Offer data (30 pts): price, priceCurrency, availability, url
     - Brand (10 pts): brand.name
     - Ratings (10 pts): aggregateRating.ratingValue + reviewCount
     - Additional (10 pts): itemCondition, multiple offers, multiple images
     - **Total**: 0-100 scale
   
   - **Family scoring** (`score_family()`):
     - Breadcrumbs (50 pts): BreadcrumbList with ≥3 items
     - Product hierarchy (50 pts): isPartOf, category, inProductGroupWithID
     - **Total**: 0-100 scale
   
   - **Policy detection** (X dimension):
     - **Structured on product page**: `hasMerchantReturnPolicy`, `hasWarrantyPromise`, `shippingDetails` in JSON-LD (50 pts)
     - **Structured on policy page**: Follows policy links, checks for structured data there (40 pts)
     - **Link only**: Finds links to return/warranty/terms pages (25 pts)
     - **Implementation note**: Currently no Swedish retailers have structured policy data (critical gap)
   
   - **Specs with units** (X dimension):
     - Checks `additionalProperty` array for values with units (W, kW, L, mm, cm, dB, etc.)
     - Presence of any spec with units: 50 pts
   
   - **Rating extraction**:
     - **Primary**: JSON-LD `AggregateRating` (full weight: 1.0)
     - **Fallback**: Embedded JSON in `<script type="application/json">` or inline JS (weight: 0.7)
     - Extracts `ratingValue` (e.g., 4.2) and `ratingCount` (e.g., 156)
     - Stores both in separate columns for transparency

3. **Progress tracking**:
   - Prints initial count: `Found N URLs in CSV`
   - Updates every 10 URLs: `[10/227] Auditing URLs... (4.4%)`
   - Shows final 100% completion
   - Logs to stdout (captured via shell redirection when run with `nohup`)

4. **Error handling**:
   - Network timeouts: 3 retries with exponential backoff
   - Malformed JSON-LD: `errors="ignore"` in extruct
   - Missing data: Fields default to 0 or empty string
   - Continues on error (doesn't fail entire audit for one bad URL)

**Performance**:
- ~1-2 seconds per URL (including retries/timeouts)
- 227 URLs: ~5-10 minutes total
- Parallel execution not implemented (risk of rate limiting/blocking)

**Key design choices**:
- **JSON-LD first**: Prioritizes structured data over HTML scraping
- **Fallback extraction**: Searches embedded JSON for ratings when JSON-LD missing
- **Transparent scoring**: Separate columns for each component (product_score, family_score, policy_*, specs_*, rating_*)
- **No JavaScript execution**: Uses initial HTML only (faster, simpler, but may miss client-rendered data)
- **Weighted fallback ratings**: Discounts embedded ratings (0.7x) vs JSON-LD (1.0x) due to lower reliability

---

### Stage 3: LAR - Score Calculation

**Purpose**: Compute final LAR scores from audit data and supplementary inputs.

**Input**:
- `data/audit_results.csv`: Audit data with E/X scores per URL
- `data/soa_log.csv`: Share-of-answer (A dimension) by brand/domain
- `data/service.csv` (optional): Manual service scores (S dimension override)

**Output**:
- `data/lar_scores.csv`: CSV with columns: `key, brand, categories, E, X, A, S, LAR`

**Implementation**: `src/asr/lar.py`

**LAR Formula**:
```
LAR = 0.40·E + 0.25·X + 0.25·A + 0.10·S

With penalty: if E < 60, then LAR = min(LAR, 40)
```

**Dimension computation**:

1. **E (Enrichment) - 40% weight**:
   ```
   E = 0.8 × Product_Score + 0.2 × Family_Score
   ```
   - Computed per-URL during audit
   - Averaged across all URLs for a domain
   - Measures structured data completeness

2. **X (eXtended attributes) - 25% weight**:
   ```
   X = Policy_Score + Specs_Score
   
   Policy_Score = {
     50 pts: Structured on product page (hasMerchantReturnPolicy, hasWarrantyPromise, shippingDetails)
     40 pts: Structured on policy page (follows links, finds structured data)
     25 pts: Policy links only (no structured data)
     0 pts: No policy information
   }
   
   Specs_Score = {
     50 pts: Specs with units present (additionalProperty with W, L, mm, etc.)
     0 pts: No specs or specs without units
   }
   
   Maximum X = 100 pts
   ```
   - Computed per-URL during audit
   - Averaged across all URLs for a domain
   - Measures actionable metadata quality

3. **A (Answer-ability / Share of Answer) - 25% weight**:
   - Loaded from `data/soa_log.csv`
   - Pre-computed metric: % of AI responses where retailer appears
   - Format: `key,value` (key = brand or domain, value = 0-100)
   - Example: `elgiganten.se,45.2` means Elgiganten appeared in 45.2% of AI answers

4. **S (Service Quality) - 10% weight**:
   - **Auto-computed (default)**:
     - Extracts `aggregateRating.ratingValue` from audit data
     - Averages across all products for a domain
     - Normalizes to 0-100 scale (assumes 5-star max)
     - Weighted by source: JSON-LD (1.0x), Fallback (0.7x)
     - Only includes products with ratings (no penalty for missing ratings)
   
   - **Manual override (optional)**:
     - Loaded from `data/service.csv` if provided
     - Format: `key,score` (key = domain, score = 0-100)
     - Use for: Trustpilot scores, Google Reviews, overall brand reputation
     - Overrides auto-computed ratings for matching domains

**Category-Weighted LAR** (`compute_category_weighted_lar()`):

When retailers compete in different categories (electronics, DIY, automotive), use weighted averaging to prevent category imbalance from skewing results.

**How it works**:
1. Load category mappings:
   - `data/intent_categories.csv`: Maps each intent_id to a category
   - `data/peer_categories.csv`: Lists which categories each retailer competes in

2. Compute E/X/S per domain per category:
   - Group audit results by domain and intent
   - Map intents to categories
   - Average scores within each category

3. Compute per-retailer LAR as average of category-level LARs:
   ```
   LAR_retailer = average(LAR_category1, LAR_category2, ...)
   ```
   - Only includes categories where retailer competes
   - Prevents over-weighting categories with more intents

**Example**: 
- Category "Building Materials" has 12 intents, "Electronics" has 9 intents
- Specialist retailer (Kjell - electronics only): LAR based only on electronics category
- Generalist retailer (Clas Ohlson - both): LAR = average(LAR_electronics, LAR_building)
- Result: Fair comparison despite unequal intent distribution

**Key design choices**:
- **E dimension dominates (40%)**: Structured data is most critical for AI discovery
- **A dimension reflects reality (25%)**: Actual AI visibility is key outcome metric
- **X dimension incentivizes richness (25%)**: Policies and specs enable AI to answer user questions
- **S dimension is secondary (10%)**: Trust signals matter but less than technical readiness
- **E penalty**: If E < 60, LAR capped at 40 (can't compensate for poor structured data)
- **Auto-computed S**: Uses product ratings by default (no manual data collection needed)
- **Transparent fallback weighting**: Discounts fallback ratings (0.7x) vs JSON-LD (1.0x)

---

## Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│ STAGE 1: DISCOVER                                               │
├─────────────────────────────────────────────────────────────────┤
│ Input: intents_peer_core_sv.csv + multibrand_retailer_peers.csv│
│                                                                 │
│ For each intent × peer:                                         │
│   1. Extract search terms (normalized specs, units, stopwords) │
│   2. Fetch retailer sitemap (cached per domain)                │
│   3. Filter to PDPs (tiered: relaxed/strict by sitemap type)   │
│   4. Score URLs by term frequency                              │
│   5. Select best match                                          │
│                                                                 │
│ Output: audit_urls.csv (227/364 URLs found, 62.4% coverage)    │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ STAGE 2: AUDIT                                                  │
├─────────────────────────────────────────────────────────────────┤
│ Input: audit_urls.csv                                           │
│                                                                 │
│ For each URL (227 total):                                       │
│   1. Fetch HTML (httpx, 3 retries, 15s timeout)                │
│   2. Extract JSON-LD (extruct library)                          │
│   3. Score Product (0-100): core attrs, offer, brand, ratings  │
│   4. Score Family (0-100): breadcrumbs, hierarchy              │
│   5. Detect Policies: structured/links (0-50 pts)              │
│   6. Detect Specs with units (0-50 pts)                        │
│   7. Extract Ratings: JSON-LD (1.0x) or fallback (0.7x)        │
│   8. Progress: Log every 10 URLs                               │
│                                                                 │
│ Output: audit_results.csv (20+ columns per URL)                │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ STAGE 3: LAR                                                    │
├─────────────────────────────────────────────────────────────────┤
│ Input: audit_results.csv + soa_log.csv + service.csv (opt)     │
│                                                                 │
│ For each domain:                                                │
│   1. E = avg(0.8·Product + 0.2·Family) across URLs             │
│   2. X = avg(Policy + Specs) across URLs                       │
│   3. A = lookup in soa_log.csv (pre-computed SOA)              │
│   4. S = avg(ratings) from audit OR manual override            │
│   5. LAR = 0.40·E + 0.25·X + 0.25·A + 0.10·S                   │
│   6. Penalty: if E < 60, LAR = min(LAR, 40)                    │
│                                                                 │
│ Category-weighted (optional):                                   │
│   - Group by domain + category                                 │
│   - Compute LAR per category                                   │
│   - Average across categories retailer competes in             │
│                                                                 │
│ Output: lar_scores.csv (1 row per domain)                      │
└─────────────────────────────────────────────────────────────────┘
```

---

## Critical Implementation Details

### 1. Search Term Extraction (Discovery)

**Location**: `src/asr/sitemap_search.py`, `extract_search_terms()` function

**Numeric spec normalization**:
```python
# Problem: "20 000 mAh" splits into ["20", "000", "mah"]
# Solution: Normalize spaces in numbers BEFORE pattern extraction
text = re.sub(r'(\d)\s+(\d)', r'\1\2', text)
# Result: "20 000 mAh" → "20000 mAh"

# Extract combined spec: "20000mah"
UNIT_PATTERN = r'\b(\d+(?:\.\d+)?)\s*(mah|ah|wh|w|kw|v|hz|ghz|gb|tb|mbps|l|ml|m2|m3|m|cm|mm|in|ft|tum|...)\b'
specs = re.findall(UNIT_PATTERN, text_normalized, re.IGNORECASE)
tokens.extend([f"{num}{unit}" for num, unit in specs])

# Add numeric-only companion tokens: "20000"
# Why: URLs may have "-20000-" without unit suffix
for num, unit in specs:
    tokens.append(num)
```

**Key insight**: Product URLs often separate number from unit (e.g., `/charger-20000-portable/` vs `/charger-20000mah/`). Generating both tokens increases match rate.

**Text normalization**:
```python
# Wi-Fi variations
text = text.replace("wi-fi", "wifi").replace("Wi-Fi", "wifi")

# Mathematical notation
text = text.replace("m²", "m2").replace("m³", "m3")
```

**Stopword filtering**:
```python
# Swedish stopwords removed: och, för, med, till, etc.
# Pure numeric tokens removed (unless part of spec)
# Unit-only tokens removed (just "mah" without number)
```

### 2. Tiered PDP Detection (Discovery)

**Location**: `src/asr/sitemap_search.py`, `is_product_detail_page()` function

**Context-aware filtering**:
```python
def is_product_detail_page(url: str, sitemap_url: str = None) -> bool:
    # Check if sitemap filename suggests product content
    relaxed_mode = False
    if sitemap_url:
        sitemap_lower = sitemap_url.lower()
        if any(x in sitemap_lower for x in ["product", "pdp", "produkt"]):
            relaxed_mode = True
    
    # Category rejection (always strict)
    if any(p in url_lower for p in ["/c/", "/f/", "?filter", "&category"]):
        return False
    
    # Numeric ID in path/query (strongest signal)
    if re.search(r'/p-\d+', url_lower) or re.search(r'[?&]id=\d+', url_lower):
        return True
    
    # Slug-only URLs: require deeper paths
    path_segments = [s for s in urlparse(url_lower).path.split('/') if s]
    
    if relaxed_mode and len(path_segments) >= 3:
        # Product sitemaps: accept 3+ segments
        last = path_segments[-1]
        if last not in ["products", "produkter", "catalog", "items", "search", "list"]:
            return True
    elif len(path_segments) >= 4:
        # Generic sitemaps: require 4+ segments
        last = path_segments[-1]
        if last not in ["products", "produkter", "catalog", "items", "search", "list"]:
            return True
    
    return False
```

**Why tiered filtering?**
- Retailer sitemaps vary widely in structure and naming
- Product sitemaps (e.g., Byggmax `_product.xml`) are more trustworthy → accept shorter paths
- Generic sitemaps may mix categories and products → require deeper paths for confidence
- Some retailers (Rusta) use pure slug-based URLs with no numeric IDs → path depth is only signal

**Evolution**: Initial simple filter (numeric ID only) → added slug support → added relaxed mode for product sitemaps → achieved 6x coverage improvement (10.4% → 62.4%)

### 3. Rating Extraction Fallback (Audit)

**Location**: `src/asr/parse.py`, `extract_ratings_fallback()` function

**Why needed?**
- Some retailers don't include ratings in JSON-LD
- But ratings exist in embedded JSON (e.g., `<script type="application/json">` with Hypernova/Next.js payloads)
- AI crawlers may extract these too

**How it works**:
1. Find all `<script type="application/json">` tags
2. Parse as JSON (ignore errors)
3. Recursively scan for rating signals:
   - Keys: `ratingValue`, `averageScore`, `averageRating`, `rating`, `score`
   - Count keys: `ratingCount`, `reviewCount`, `numberOfReviews`, `numberOfRatings`
4. Extract first match, return with source label

**Weighting**:
```python
# JSON-LD rating: Full weight (1.0)
rating_normalized = (rating_float / 5.0) * 100 * 1.0

# Fallback rating: Discounted (0.7)
rating_normalized = (rating_float / 5.0) * 100 * 0.7
```

**Rationale**: JSON-LD is standardized and reliable. Embedded JSON varies by CMS/framework and may have inconsistent schemas. Discount reflects higher uncertainty.

### 4. Progress Logging (Audit)

**Location**: `src/asr/audit.py`, `audit_urls()` function

**Implementation**:
```python
def audit_urls(urls, output_csv):
    total = len(urls)
    print(f"Found {total} URLs in CSV")
    
    for idx, url in enumerate(urls, start=1):
        # ... fetch and score URL ...
        
        # Progress update every 10 URLs
        if idx % 10 == 0 or idx == total:
            print(f"  [{idx}/{total}] Auditing URLs... ({idx/total*100:.1f}%)")
    
    print("✓ Audit complete")
```

**Design choice**: Every 10 URLs (not every URL) to balance visibility with log spam. For 227 URLs: 23 progress updates total.

---

## File Structure

```
src/asr/
├── __init__.py                      # Package initialization
├── cli.py                           # Typer CLI commands (discover, audit, lar)
├── audit.py                         # Stage 2: Audit URLs, extract structured data
├── lar.py                           # Stage 3: Compute LAR scores (standard + weighted)
├── fetch.py                         # HTTP fetching with retries
├── parse.py                         # JSON-LD extraction, scoring logic, fallback extraction
├── config.py                        # Configuration (stopwords, etc.)
├── discover.py                      # Google API discovery (fallback method)
├── sitemap_search.py                # Sitemap discovery (primary method)
├── site_search.py                   # Site search discovery (experimental)
├── site_search_playwright.py        # Browser-based site search (experimental)
└── schemas/                         # (Future) JSON schema definitions

data/
├── intents/
│   └── intents_peer_core_sv.csv     # Search intents (26 product queries)
├── multibrand_retailer_peers.csv    # Peer retailers (14 domains)
├── audit_urls.csv                   # Discovery output (227 URLs)
├── audit_results.csv                # Audit output (227 rows × 20+ cols)
├── soa_log.csv                      # Share-of-answer by brand (A dimension)
├── service.csv                      # Optional manual service scores (S override)
├── lar_scores.csv                   # LAR output (14 retailers × 7 cols)
├── intent_categories.csv            # Intent → category mapping
└── peer_categories.csv              # Retailer → categories mapping

docs/
├── architecture.md                  # This file - high-level overview
├── methodology.md                   # LAR framework details (E·X·A·S)
├── scoring.md                       # Scoring formulas and examples
└── sitemap_discovery.md             # Sitemap discovery guide
```

---

## Design Decisions & Rationale

### 1. Why Sitemap Discovery Over Google API?

**Decision**: Use sitemap search as primary method, Google API as fallback.

**Rationale**:
- **Cost**: Sitemap search is free, Google API costs $5/1000 after 100/day
- **Speed**: Sitemap loads once per domain (cached), reused for all searches (~1s per search)
- **Precision**: Sitemaps contain only product URLs (with proper filtering)
- **Coverage**: 62.4% achieved with sitemaps alone (vs ~40% expected with API due to rate limits)
- **Scalability**: Can process 1000s of searches without rate limits or costs

**Trade-off**: Requires manual sitemap URL configuration per retailer (14 retailers = 14 URLs). Blocked retailers (Cloudflare) need API fallback.

### 2. Why No JavaScript Execution in Audit?

**Decision**: Use initial HTML only, no browser automation.

**Rationale**:
- **Speed**: 1-2s per URL vs 5-10s with browser
- **Simplicity**: No Playwright/Selenium dependencies
- **Reliability**: Fewer failure modes (no browser crashes, timeouts)
- **AI crawler behavior**: Most AI crawlers also prefer initial HTML (faster, cheaper)

**Trade-off**: May miss client-rendered JSON-LD. Mitigated by fallback extraction from embedded JSON.

**When to reconsider**: If audit shows major retailers have 0% JSON-LD in initial HTML (not currently the case - Swedish retailers have 80%+ in initial HTML).

### 3. Why Auto-Compute S from Ratings?

**Decision**: Default to product ratings from audit data, allow manual override.

**Rationale**:
- **No extra data collection**: Ratings already extracted during audit
- **Scales automatically**: Works for any retailer with on-site ratings
- **Transparent**: Both JSON-LD and fallback ratings stored in separate columns
- **Flexible**: Manual override option for Trustpilot/Google Reviews when needed

**Trade-off**: Some retailers don't display ratings → S = 0 for them. Solution: Provide manual service.csv for those retailers.

### 4. Why Discount Fallback Ratings (0.7x)?

**Decision**: Apply 0.7x weight to ratings from embedded JSON vs JSON-LD.

**Rationale**:
- **Standardization**: JSON-LD follows Schema.org spec (predictable structure)
- **Variance**: Embedded JSON schemas vary by CMS/framework
- **Confidence**: Lower confidence in extraction accuracy for non-standard formats
- **Incentive**: Encourages retailers to use proper JSON-LD

**Trade-off**: Some accurate fallback ratings get discounted. Alternative: Equal weight (1.0x) if extraction proves highly accurate.

### 5. Why E Dimension Penalty (cap at 40 if E < 60)?

**Decision**: If E < 60, LAR cannot exceed 40, regardless of other dimensions.

**Rationale**:
- **E is foundational**: Without structured data, AI cannot reliably extract product info
- **Prevents gaming**: Can't compensate for poor E with high A/X/S
- **Realistic**: Retailers with poor structured data won't get recommended by AI, even with good service (A/S)

**Impact**: Retailers below 60 E score must fix structured data to improve LAR.

### 6. Why Category-Weighted LAR?

**Decision**: Offer weighted LAR as alternative to standard LAR.

**Rationale**:
- **Fair comparison**: Specialist vs generalist retailers compete in different category sets
- **Intent imbalance**: Some categories have 12 intents, others have 6 → standard LAR over-weights larger categories
- **Peer-to-peer**: Each retailer evaluated only in categories they compete in

**Example**:
- Category A: 12 intents, Category B: 6 intents
- Standard LAR: 12/18 weight to Category A (66%)
- Weighted LAR: 50% to each category (fair for specialists in B)

**When to use**:
- Comparing retailers across different category sets (generalist vs specialist)
- When intent distribution is unbalanced (some categories have more intents)

**When NOT to use**:
- Comparing same-category retailers (e.g., all electronics)
- When all intents equally important (no category grouping needed)

---

## Extension Points & Future Improvements

### 1. JavaScript Execution for Client-Rendered Sites

**Current state**: Audit uses initial HTML only.

**Enhancement**: Add Playwright option for retailers with client-rendered JSON-LD.

**Implementation**:
```python
# In audit.py
def audit_urls_with_js(urls, output_csv):
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for url in urls:
            page = browser.new_page()
            page.goto(url, wait_until="networkidle")
            html = page.content()
            # ... extract and score ...
```

**When to add**: If coverage analysis shows major retailers (>30% of peers) need JS execution for JSON-LD extraction.

### 2. Parallel Audit Execution

**Current state**: Sequential audit (1 URL at a time).

**Enhancement**: Process multiple URLs in parallel with rate limiting.

**Implementation**:
```python
import asyncio
from asyncio import Semaphore

async def audit_url_async(url, semaphore):
    async with semaphore:
        # ... fetch and score ...
        await asyncio.sleep(0.5)  # Rate limit

async def audit_urls_parallel(urls, output_csv, max_concurrent=5):
    semaphore = Semaphore(max_concurrent)
    tasks = [audit_url_async(url, semaphore) for url in urls]
    await asyncio.gather(*tasks)
```

**Benefits**: 5x speedup (5 concurrent = ~2 minutes for 227 URLs vs ~10 minutes sequential).

**Risks**: May trigger rate limiting/blocking from retailers. Start with max_concurrent=3.

### 3. Automated Sitemap Discovery

**Current state**: Manual sitemap URL configuration in `SITEMAP_URLS` dict.

**Enhancement**: Auto-discover sitemaps from robots.txt or common patterns.

**Implementation**:
```python
def discover_sitemap(domain: str) -> Optional[str]:
    # Check robots.txt
    robots_url = f"https://{domain}/robots.txt"
    resp = httpx.get(robots_url)
    match = re.search(r'Sitemap:\s*(https?://[^\s]+)', resp.text, re.IGNORECASE)
    if match:
        return match.group(1)
    
    # Try common patterns
    common = [
        f"https://{domain}/sitemap.xml",
        f"https://{domain}/sitemap_index.xml",
        f"https://{domain}/product-sitemap.xml",
    ]
    for url in common:
        if httpx.head(url).status_code == 200:
            return url
    
    return None
```

**Benefits**: Reduces manual configuration, scales to new retailers automatically.

### 4. Policy Page Crawling

**Current state**: Detects policy links, checks for structured data on policy pages.

**Enhancement**: Extract policy text, use NLP to structure return/warranty info.

**Implementation**:
```python
def extract_policy_structured(policy_url: str) -> dict:
    html = fetch_html(policy_url)
    soup = BeautifulSoup(html, "lxml")
    
    # Find return policy section
    return_section = soup.find(text=re.compile("return|retur|ånger", re.I))
    if return_section:
        # Use regex or NLP to extract:
        # - Return window (30 days, 60 days)
        # - Return fees (free, customer pays)
        # - Return method (mail, in-store)
        ...
    
    return {"returnDays": 30, "returnFees": "free", ...}
```

**Benefits**: Fills X dimension policy gap (currently 0 pts for all Swedish retailers).

**Challenge**: Requires NLP or extensive regex patterns for varied policy text.

### 5. Real-Time Share-of-Answer Tracking

**Current state**: A dimension loaded from pre-computed `soa_log.csv`.

**Enhancement**: Query AI services in real-time, measure SOA dynamically.

**Implementation**:
```python
def measure_soa(intent: str, peers: List[str]) -> Dict[str, float]:
    # Query Google AI Overview
    response = query_google_ai(intent)
    
    # Extract retailer mentions
    mentions = {}
    for peer in peers:
        count = response.text.count(peer.domain)
        mentions[peer.domain] = count
    
    # Compute share
    total = sum(mentions.values())
    soa = {k: (v/total*100) if total > 0 else 0 for k, v in mentions.items()}
    return soa
```

**Benefits**: Real-time LAR updates, no manual SOA data collection.

**Challenges**: API costs, rate limits, requires API access to AI services.

### 6. D Dimension for Manufacturers

**Current state**: D dimension removed (not applicable to third-party retailers).

**Enhancement**: Re-introduce D for manufacturers/brands with multi-channel presence.

**Implementation**:
```python
def compute_distribution_coherence(brand: str, urls: List[str]) -> float:
    # Fetch product data from multiple channels
    own_site = fetch_product(urls['own_site'])
    amazon = fetch_product(urls['amazon'])
    manual_pdf = extract_from_pdf(urls['manual_pdf'])
    
    # Compare fields
    price_match = abs(own_site.price - amazon.price) < 5
    specs_match = own_site.specs == amazon.specs
    availability_match = own_site.in_stock == amazon.in_stock
    
    # Score consistency
    consistency = sum([price_match, specs_match, availability_match]) / 3 * 100
    return consistency
```

**When to add**: If expanding LAR to manufacturers (Samsung, Bosch, etc.) who control data across channels.

---

## Performance Benchmarks

**Discovery (Sitemap)**:
- 14 retailers × 26 intents = 364 searches
- With caching: ~1 second per search = ~6 minutes total
- Coverage: 227/364 (62.4%)

**Audit**:
- 227 URLs × ~2 seconds per URL = ~8-10 minutes
- With retries/timeouts: Up to 15 minutes
- Success rate: ~99% (1-2 network failures per run)

**LAR Calculation**:
- 227 URLs → 14 domains
- Computation: <1 second (pure Python, no I/O)

**Total pipeline**: ~15-20 minutes for full execution (discovery → audit → LAR).

---

## Error Handling & Robustness

**Network errors**:
- Retry 3x with exponential backoff (0.5s, 1s, 2s, 4s)
- Timeout: 15 seconds per request
- Continues on failure (doesn't crash entire pipeline)

**Malformed data**:
- JSON-LD parsing: `errors="ignore"` in extruct
- Missing fields: Default to 0 or empty string
- Invalid URLs: Skipped during PDP filtering

**Blocked domains**:
- Cloudflare 403: Logged, skipped, can use Google API fallback
- robots.txt: Respects sitemap declarations

**Progress tracking**:
- Logs to stdout (captured via redirection)
- Updates every 10 items (not every item, to avoid spam)
- Shows completion percentage for long operations

---

## Testing & Validation

**Unit tests**: `tests/test_smoke.py` (basic smoke tests).

**Manual validation**:
1. **Discovery**: Check `audit_urls.csv` for quality (no category pages, domains match, URLs valid)
2. **Audit**: Inspect `audit_results.csv` for score distribution (E: 60-90, X: 0-50, S: 60-80)
3. **LAR**: Compare `lar_scores.csv` against expected rankings (Elgiganten > NetOnNet > Kjell)

**Common validation checks**:
```python
# In Python shell
import pandas as pd

# Check discovery coverage
df = pd.read_csv("data/audit_urls.csv")
print(df['found'].value_counts())
print(df.groupby('domain')['found'].sum())

# Check audit score distribution
df = pd.read_csv("data/audit_results.csv")
print(df[['product_score', 'family_score', 'policy_link', 'specs_units']].describe())

# Check LAR rankings
df = pd.read_csv("data/lar_scores.csv")
print(df.sort_values('LAR', ascending=False))
```

---

## Troubleshooting

**Issue**: Discovery finds 0 URLs for a retailer.

**Solutions**:
1. Check if sitemap URL is correct (visit in browser)
2. Check if sitemap is blocked (403, Cloudflare challenge)
3. Verify PDP filter isn't too strict (test with `is_product_detail_page()`)
4. Use `--use-api` flag for Google API fallback

**Issue**: Audit shows 0 product_score for all URLs.

**Solutions**:
1. Check if pages have JSON-LD (view page source, search for `application/ld+json`)
2. Check if JSON-LD is client-rendered (may need Playwright)
3. Verify `extruct` library installed correctly

**Issue**: LAR scores all similar (no differentiation).

**Solutions**:
1. Check if A dimension varies (SOA log has different values per retailer)
2. Check if S dimension computed (ratings present in audit data)
3. Verify audit data has variance (not all 100s or all 0s)

---

## Conclusion

The ASR/LAR system provides a comprehensive, automated pipeline for evaluating retailer readiness for AI-powered search. Key strengths:

- ✅ **Fast**: 15-20 minutes for full pipeline
- ✅ **Cost-effective**: Sitemap discovery is free, no API costs for 62% coverage
- ✅ **Transparent**: Separate scoring components, fallback sources labeled
- ✅ **Scalable**: Caching, efficient filtering, extensible architecture
- ✅ **Accurate**: 62.4% discovery coverage, 99% audit success rate

Critical next steps for improvement:
1. Fix policy data gap (add structured policies to product pages)
2. Increase sitemap coverage (solve Cloudflare blocking for Dustin, Jula)
3. Add parallel audit execution (5x speedup)
4. Automate sitemap discovery (reduce manual configuration)

The system is production-ready for Swedish retailer evaluation and can be extended to other markets/verticals with minimal configuration (update sitemap URLs, stopwords, intent lists).
