# Architecture Overview

## What This Program Does

The AI Shortlist Screener is a **research tool** that measures how "ready" retailers are for AI-powered shopping assistants (ChatGPT, Perplexity, Google AI, etc.). It calculates a **LAR score** (Likelihood of AI Recommendation) by analyzing whether product pages have machine-readable structured data that AI can instantly filter and rank.

### The Core Question

**Will AI shopping assistants recommend your products to users?**

The answer depends on whether AI can:
1. **Find** your products (distribution, service reputation)
2. **Understand** your products (structured data completeness)
3. **Trust** your products (policy machine-readability)
4. **Recommend** your products (historical answer share)

---

## Three-Stage Pipeline

```
┌─────────────┐      ┌─────────────┐      ┌─────────────┐
│  DISCOVER   │  →   │    AUDIT    │  →   │  LAR SCORE  │
│   (URLs)    │      │ (Structure) │      │   (Final)   │
└─────────────┘      └─────────────┘      └─────────────┘
```

---

## Stage 1: Discovery (`discover.py`, `site_search.py`)

**Purpose**: Find product URLs to analyze without introducing bias

### The Problem
If you ask Google "best laptop", results are already biased by Google's ranking algorithm. Testing those top results tells you what *Google* thinks, not what *structured data quality* determines.

### The Solution
Use **site-specific searches** with unbiased criteria:

```python
# Instead of: "best laptop"
# Search: site:elgiganten.se bärbar dator USB-C 16GB

# For each intent × peer combination:
query = f"site:{peer_domain} {intent_terms}"
```

### Key Files & Logic

**`src/asr/discover.py`** - Google API discovery
- Extracts search terms from intent constraints
- Removes brand names to avoid bias
- Uses Google Custom Search API
- Rate limiting with `--limit` flag

**`src/asr/site_search.py`** - On-site search fallback
- Scrapes retailer's own search results
- No API costs
- Slower but more accurate product matches

### Input/Output

**Input**: 
- `intents.csv` - Search intents with constraints (26 intents)
- `peers.csv` - Retailer domains (16 peers)

**Output**: 
- `audit_urls.csv` - Product URLs to audit (intent_id, peer, url)

---

## Stage 2: Audit (`audit.py`, `parse.py`, `fetch.py`)

**Purpose**: Analyze product pages for structured data completeness

**This is the core engine** - where most intelligence lives.

### Architecture

```
┌─────────────┐
│  fetch.py   │  ← HTTP client with retry logic
└──────┬──────┘
       ↓
┌─────────────┐
│  parse.py   │  ← HTML/JSON-LD extraction
└──────┬──────┘
       ↓
┌─────────────┐
│  audit.py   │  ← Scoring orchestrator
└─────────────┘
```

### Key Components

#### **`fetch.py`** - HTTP Client
```python
@retry(stop=stop_after_attempt(3), wait=wait_exponential())
def fetch_html(url: str) -> str:
    # Uses httpx (no JavaScript execution)
    # Realistic browser headers
    # Retry logic for transient failures
```

**Design Decision**: Use httpx (static HTML) instead of Playwright (JS execution)
- **Why**: 10-50× faster, most structured data is in initial HTML (SEO best practice)
- **Validation**: Tested with Playwright - Swedish retailers have JSON-LD in static HTML

#### **`parse.py`** - HTML/JSON-LD Parser
```python
def extract_jsonld(html: str, url: str) -> List[dict]:
    # Uses extruct library
    # Parses <script type="application/ld+json">
    # Returns list of all JSON-LD objects
```

**Advanced Policy Detection**:
```python
def has_policy_links(html: str) -> bool:
    # Primary: Look for <a> tags with policy keywords
    # Fallback: Search raw HTML for embedded JSON/CMS data
    # Handles React/JS-hydrated content without executing JS
```

**Why the fallback?** Sites like NetOnNet store links in JSON that React later renders. By searching raw HTML text, we catch these without needing JavaScript execution.

#### **`audit.py`** - Scoring Orchestrator

**E Dimension (Enrichment)** - Product data completeness:
```python
# Product Score (80% of E)
- has_jsonld: 20pts - JSON-LD present
- has_product: 20pts - Product schema exists
- has_offer: 15pts - Pricing info
- has_identifiers: 20pts - SKU/GTIN/MPN
- has_policies: 10pts - Structured policies
- specs_with_units: 15pts - Technical specs with units

# Family Score (20% of E)  
- has_productgroup: 30pts - Product family
- has_hasvariant: 30pts - Variant relationships
- links_to_children: 20pts - Family navigation
- policies: 10pts - Family-level policies
- spec_ranges: 10pts - Variant spec ranges

E = (Product Score × 0.8) + (Family Score × 0.2)
```

**X Dimension (eXtended attributes)** - Policy machine-readability:

Three-tier scoring system:

```python
# Tier 3: Structured on product page (50pts)
if Product.offers.hasMerchantReturnPolicy exists:
    x_policy = 50
    
# Tier 2: Structured on policy page (40pts)
elif policy_page_has_structured_data:
    x_policy = 40
    
# Tier 1: Text-only link (25pts)
elif has_policy_link("köpvillkor"):
    x_policy = 25
    
# Tier 0: Nothing (0pts)
else:
    x_policy = 0

X = x_policy + x_specs
```

**Why three tiers?** 
- **Structured on product (50pts)**: AI can instantly filter "returnDays >= 30" → 100% confidence → high shortlist probability
- **Structured on policy page (40pts)**: AI must follow link, but data is reliable → medium shortlist probability
- **Text-only (25pts)**: AI must parse natural language → uncertain → low shortlist probability
- **None (0pts)**: No policy info → excluded from policy-filtered searches

**Sophisticated Policy Detection**:

1. **Product-level**: Check `Product > offers > hasMerchantReturnPolicy`
2. **Organization-level**: Check `Organization > hasMerchantReturnPolicy` with `@id` reference resolution
3. **Policy page following**: Extract policy URLs (köpvillkor), fetch them, check for `MerchantReturnPolicy` schema

### Input/Output

**Input**: `audit_urls.csv` (URLs from discovery)

**Output**: `asr_report.csv` with columns:
```csv
url,server_jsonld,has_product,has_offer,identifiers,policies,
policy_structured,policy_link,policy_structured_on_policy_page,
specs_units,productgroup,product_score,family_score
```

---

## Stage 3: LAR Computation (`lar.py`)

**Purpose**: Combine audit data with supplementary metrics into final score

### The LAR Formula

```python
LAR = (0.40 × E) + (0.25 × X) + (0.25 × A) + (0.10 × S)
```

**Dimension Breakdown**:

| Dimension | Weight | Source | What It Measures |
|-----------|--------|--------|------------------|
| **E** (Enrichment) | 40% | Audit | Product data completeness |
| **X** (eXtended) | 25% | Audit | Policy machine-readability |
| **A** (Answer-ability) | 25% | `soa_log.csv` | Historical share-of-answer in AI responses |
| **S** (Service Quality) | 10% | Audit (auto) or `service.csv` (override) | Customer satisfaction from product ratings or external sources |

**Note on D dimension**: An earlier version included D (Distribution - cross-channel consistency), but it's been removed as it's not applicable to third-party retailers selling through own channels. See `docs/methodology.md` for details on potential future D implementations for different business contexts.

**Note on S dimension**: Originally designed as "Service/Actionability" measuring booking capabilities (BookAction, LocalBusiness) for service-heavy businesses. For product retailers, customer satisfaction ratings provide better differentiation and are more relevant trust signals. S is now **auto-computed** from product ratings extracted during audit, with optional manual overrides via `service.csv`. See "Key Design Decisions" section below for details.

### Eligibility Gate

```python
if E < 60:
    LAR = min(LAR, 40.0)  # Cap at 40 if basic data is missing
```

**Rationale**: If product data is incomplete (E < 60), AI can't confidently recommend regardless of other factors.

### Category-Weighted Mode

**Problem**: Peers compete in different categories (electronics, DIY, automotive, etc.). Simple averages penalize specialists.

**Solution**: Weight by category presence
```python
# Standard (unfair to specialists):
peer_lar = mean(all_intent_scores)

# Weighted (fair):
for category in peer_categories:
    category_scores = [scores for intent in category]
    category_lar[category] = mean(category_scores)
peer_lar = mean(category_lar.values())
```

**Example**: 
- Kjell (electronics only) evaluated on 5 electronics intents
- Clas Ohlson (electronics + DIY + workwear) evaluated on 15 intents across 3 categories
- Both get fair LAR scores within their competitive scope

### Input/Output

### **Input**:
- `asr_report.csv` (from audit)
- `soa_log.csv` (share-of-answer tracking)
- `service.csv` (customer ratings)

**Output**: `lar_scores.csv`
```csv
key,brand,categories,E,X,A,S,LAR
elgiganten.se,Elgiganten,Electronics|Appliances,82.5,30,45.2,80,60.4
```

---

## Supporting Tools

### **Playwright Validator** (`scripts/extract_jsonld_playwright.py`)

**Purpose**: Validation tool to verify httpx approach is sufficient

**When to use**:
- Initial validation of new markets
- Debugging sites that seem to load everything via JS
- Research/documentation proof

**Not used in production pipeline** - only for validation because:
- 30× slower than httpx (3s vs 100ms per URL)
- Most structured data is in initial HTML (SEO best practice)
- Testing confirmed Swedish retailers don't need JS execution

**Example validation**:
```bash
# Validate that httpx catches everything
python scripts/extract_jsonld_playwright.py urls.txt playwright_output.json

# Compare with httpx results from audit
# If identical → httpx is sufficient
```

---

## Data Flow Example

```bash
# 1. DISCOVER: Find URLs for "bärbar dator" across all peers
asr discover --limit 10
# Output: data/audit_urls.csv
# Sample row: INT01,Elgiganten,https://elgiganten.se/product/123

# 2. AUDIT: Analyze product pages
asr audit data/audit_urls.csv --out asr_report.csv
# Output: E scores (80-90 for good retailers), X scores (25 for text-only policies)

# 3. LAR: Compute final scores
asr lar asr_report.csv data/soa_log.csv data/distribution.csv data/service.csv
# Output: LAR scores showing competitive position
```

---

## Key Design Decisions & Lessons

### 1. **httpx vs Playwright**
**Decision**: Use httpx for production, keep Playwright for validation  
**Rationale**: 
- 10-50× speed difference
- Structured data is typically in initial HTML (SEO requirement)
- Validation on Swedish retailers confirmed no JS-injection

**Lesson**: Validate once with Playwright, then optimize with httpx

### 2. **Three-Tier Policy Scoring**
**Decision**: Differentiate between structured (50pts), structured on policy page (40pts), and text-only (25pts)  
**Rationale**: AI shortlisting requires instant filtering
- Structured = instant filtering → high confidence → high shortlist probability
- Text-only = NLP parsing required → uncertain → lower probability

**Lesson**: "AI-accessible" (text) ≠ "AI-ready" (structured)

### 3. **Organization-Level Policy Detection**
**Decision**: Check both Product-level and Organization-level policies with `@id` resolution  
**Rationale**: Companies often declare policies at organization level rather than repeating on every product

**Lesson**: Schema.org allows flexible structures - check all levels

### 4. **Raw HTML Fallback for Policy Links**
**Decision**: Search raw HTML text for "köpvillkor" patterns, not just `<a>` tags  
**Rationale**: Sites like NetOnNet embed links in JSON that React hydrates later

**Lesson**: Raw text search catches pre-rendered data without JS execution

### 5. **Category-Weighted LAR**
**Decision**: Offer both simple and category-weighted LAR modes  
**Rationale**: Fair comparison requires adjusting for different competitive scopes

**Lesson**: Domain-specific weighting is essential for meaningful benchmarking

### 6. **S Dimension: Service Quality vs. Actionability**
**Original design**: S measured "Service/Actionability" - booking capabilities (BookAction), local business presence (LocalBusiness), service offerings  
**Rationale**: Made sense for service-heavy businesses (automotive service booking, installation services)

**Why redesigned for product retailers**:
- Limited booking needs (installation is optional, not core business)
- All have physical stores → no differentiation
- Customer satisfaction provides better variance (2.5-4.5 star range)

**Current implementation**: 
- **Auto-computed (default)**: Extracts `AggregateRating` from product pages during audit, averages per retailer
- **Manual override (optional)**: `service.csv` with external scores (Trustpilot, Google Reviews, Prisjakt)
- CLI: Use `asr lar audit.csv soa.csv` (auto) or `asr lar audit.csv soa.csv --service-csv service.csv` (override)

**Why automated measurement works**:
- Product ratings already captured in audit (schema.org `AggregateRating`)
- Low-hanging fruit - no API costs, no manual research
- Trust signals matter for AI recommendations
- Differentiates retailers (ratings vary 3.5-4.5 stars typically)
- Manual overrides still available when needed

**Lesson**: Dimension definitions should match peer business models. When data is already being collected, use it! Don't force manual work when automation is available.

---

## File Responsibilities Summary

### **Core Logic** (Intelligence)
| File | Purpose | Key Functions |
|------|---------|---------------|
| `audit.py` | Scoring engine | `score_url()`, policy detection, E/X calculation |
| `parse.py` | HTML parser | `extract_jsonld()`, `has_policy_links()`, policy URL extraction |
| `lar.py` | Score compositor | `compute_lar()`, `compute_category_weighted_lar()` |
| `config.py` | Scoring weights | Product/family feature weights, eligibility gate |

### **Infrastructure**
| File | Purpose | Key Functions |
|------|---------|---------------|
| `cli.py` | User interface | Typer CLI commands (discover, audit, lar) |
| `fetch.py` | HTTP client | `fetch_html()` with retry logic |
| `discover.py` | Google API integration | Site-specific search, URL extraction |
| `site_search.py` | On-site search scraping | Fallback when no API key |

### **Utilities**
| File | Purpose |
|------|---------|
| `scripts/extract_jsonld_playwright.py` | Playwright-based JS rendering validator |
| `scripts/csv_to_urls.py` | Extract URL column from discovery CSV |

---

## Performance Characteristics

### **Speed**
- **Discovery**: ~1s per query (Google API), ~3s per query (scraping)
- **Audit**: ~100ms per URL (httpx), ~3s per URL (Playwright if needed)
- **LAR**: <1s for full dataset

### **Scale**
- **Current test**: 8 URLs, ~1 second total audit time
- **Production**: 416 URLs (26 intents × 16 peers), ~42 seconds audit time
- **With rate limiting** (1s delay): ~7 minutes for full audit

### **API Limits**
- Google Custom Search: 100 queries/day (free tier)
- Use `--limit 100` to stay within quota
- On-site search fallback has no quota (but slower)

---

## Research Findings

### **The Structured Data Gap**

Testing on Swedish retailers (Elgiganten, NetOnNet, Kjell) revealed:

✅ **Strong Product Schemas** (E dimension ~80-90):
- All have complete Product, Offer, identifiers
- Good technical specs with units
- High-quality product data

❌ **Zero Structured Policy Data** (X dimension = 25):
- All have köpvillkor/garanti links (text-only)
- **None** have `MerchantReturnPolicy` or `WarrantyPromise` schemas on product pages
- **None** have structured policy data on dedicated policy pages either
- All stuck at Tier 1 (text-only, 25pts) vs optimal Tier 3 (structured, 50pts)

### **Competitive Opportunity**

Implementing structured policies (X: 25 → 50) would:
- Add +5 LAR points directly (20% × 25pts improvement)
- Likely improve A dimension (higher shortlist inclusion → more AI mentions)
- Represent a **first-mover advantage** in Swedish market

**Business Impact**: Retailers with X=50 are predicted to appear in ~15-20% more AI-filtered searches than X=25 competitors (based on shortlist inclusion probability).

---

## Next Steps for Production

See full gap analysis in comments, but key needs:

1. **A dimension data collection** - Track share-of-answer in AI responses
2. **S dimension data** - Customer satisfaction scores
3. **Rate limiting** - Add throttling to audit for scale
4. **Intent tracking** - Link URLs to intent_id for category-level analysis

The core E and X measurement engine is production-ready and validated.

**Note on D dimension**: Originally planned as "distribution coherence" (cross-channel consistency), but removed as not applicable to third-party retailers. See `methodology.md` for context-specific D implementations if expanding to manufacturers or omnichannel retailers.
