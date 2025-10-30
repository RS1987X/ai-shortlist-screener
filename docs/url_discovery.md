# URL Discovery Setup Guide

## Overview

The `asr discover` command finds product URLs for each intent × peer combination using one of three methods:

1. **🎯 Sitemap Search (Recommended)** - Download retailer sitemaps, search locally (fast, free, no API)
2. **🔍 Google Custom Search API** - Site-specific Google searches (reliable, costs money)
3. **⚠️ Web Scraping** - Last resort (slow, blocked often, violates ToS)

---

## Quick Start (Sitemap - No API Key Required)

```bash
# Default: Uses sitemap search (fast, free, reliable)
asr discover

# Sitemap with Google API fallback
asr discover --use-sitemap --use-api
```

**Advantages**: 
- ✅ Fast (5-10 seconds per retailer)
- ✅ Free (no API costs)
- ✅ Reliable (no rate limits)
- ✅ 75% retailer coverage (12/16 have sitemaps)

**See:** [Sitemap Discovery Guide](sitemap_discovery.md) for detailed documentation.

---

## Alternative: Google Custom Search API

For retailers without sitemaps or when higher precision is needed:

```bash
# Google API only
asr discover --no-use-sitemap --use-api
```

**Limitations**: 
- Requires API key (free tier: 100 queries/day)
- Costs $5/1000 queries beyond free tier
- Good for 100% retailer coverage

---

## Recommended: Google Custom Search API (Free Tier)

### Step 1: Get a Free API Key

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project (or select existing)
3. Enable **Custom Search API**:
   - Navigate to "APIs & Services" > "Library"
   - Search for "Custom Search API"
   - Click "Enable"
4. Create credentials:
   - Go to "APIs & Services" > "Credentials"
   - Click "Create Credentials" > "API Key"
   - Copy the key

**Free Tier**: 100 queries/day

---

### Step 2: Create a Custom Search Engine

1. Go to [Google Programmable Search Engine](https://programmablesearchengine.google.com/)
2. Click "Add" to create a new search engine
3. Configure:
   - **Sites to search**: Enter `*.se` (to search all Swedish sites)
   - Or leave blank and enable "Search the entire web"
   - Name it "ASR URL Discovery"
4. Click "Create"
5. Go to "Setup" > Copy the **Search engine ID** (starts with something like `017576662512468239146:omuauf_lfve`)

---

### Step 3: Configure Environment Variables

Add to your `~/.bashrc` or `~/.zshrc`:

```bash
export GOOGLE_API_KEY="AIzaSyC-your-api-key-here"
export GOOGLE_SEARCH_ENGINE_ID="017576662512468239146:omuauf_lfve"
```

Then reload:
```bash
source ~/.bashrc
```

---

### Step 4: Run Discovery

```bash
# With API (fast, reliable)
asr discover

# Or specify files explicitly
asr discover \
  --intents-csv data/intents/intents_peer_core_sv.csv \
  --peers-csv data/multibrand_retailer_peers.csv \
  --out data/audit_urls.csv
```

---

## How It Works (Bias Mitigation)

### Site-Specific Queries
For each intent × peer, the tool constructs:
```
site:clasohlson.com USB-C hub HDMI 4K 100W
```

**Why this reduces bias**:
- ✅ No cross-site ranking (Clas vs Kjell aren't compared by Google)
- ✅ Tests each peer's findability independently
- ✅ Consistent query format for all peers

### Relevance Scoring
Results are re-ranked by **spec match**, not Google rank:
- Category match: +0.3
- Key specs present: +0.4
- Product page indicator: +0.3

**Example**: A result ranked #3 by Google might score 0.9 for spec match while #1 scores 0.5 → we pick #3.

### Query Generation
Extracts technical specs from intent constraints:
- ✅ Includes: `24 tum`, `IPS`, `75 Hz`, `VESA`
- ❌ Excludes: `under 1600 kr`, `enligt PDP`, brand names

This prevents budget/brand bias.

---

## Output Format

`data/audit_urls.csv`:
```csv
intent_id,brand,domain,url,relevance_score,title,search_query,found
INT01,Clas Ohlson,clasohlson.com,https://...,0.85,"Deltaco USB-C Hub",site:clasohlson.com USB-C hub HDMI,1
INT01,Kjell Group,kjell.com,https://...,0.92,"Kjell USB-C Docking",site:kjell.com USB-C hub HDMI,1
INT01,NetOnNet,netonnet.se,,0.0,"",site:netonnet.se USB-C hub HDMI,0
```

**Fields**:
- `found=1`: URL discovered
- `found=0`: No suitable product found (peer gets E=0 for this intent)
- `relevance_score`: How well the URL matches intent specs (0-1)

---

## Manual Review (Critical Step)

**Always review the output before auditing**:

1. Spot-check 10-15 URLs: Do they match the intent?
2. For `found=0` rows: Manually verify no product exists
3. Adjust low-scoring URLs (<0.5): May be false matches
4. Look for patterns: If one peer has all low scores, query format may be off

```bash
# Count found vs not found
grep ",1$" data/audit_urls.csv | wc -l   # Found
grep ",0$" data/audit_urls.csv | wc -l   # Not found

# Check low relevance scores
awk -F',' '$5 < 0.5 && $8 == 1' data/audit_urls.csv
```

---

## Rate Limits & Costs

| Method | Rate Limit | Cost | Reliability |
|---|---|---|---|
| **Google API (free)** | 100/day | Free | High |
| **Google API (paid)** | No limit | $5/1000 queries | High |
| **Web scraping** | ~1/3sec | Free | Low (blocks) |

**For 26 intents × 17 peers = 442 queries**:
- API free tier: Need to run over 5 days (100/day)
- API paid: ~$2.20 one-time
- Scraping: 20-30 minutes, high failure risk

---

## Troubleshooting

### "No API key provided"
```bash
echo $GOOGLE_API_KEY
# Should print your key. If empty:
export GOOGLE_API_KEY="your-key-here"
```

### "Search returned 0 results"
- Check if peer's site is indexed by Google: `site:domain.com`
- Try broadening search terms (may need to tune `extract_search_terms()`)
- Peer may not have products in that category → `found=0` is correct

### "Relevance scores all low"
- Review search query format: May be too specific or too broad
- Manually test query in Google to validate
- Adjust scoring weights in `score_url_relevance()`

### Rate limiting / blocks
- Add longer delays: edit `time.sleep(3)` → `time.sleep(5)`
- Use API instead of scraping
- Spread queries across multiple days

---

## Next Steps

After running discovery:

```bash
# 1. Review URLs
cat data/audit_urls.csv | less

# 2. Run audit on discovered URLs
# (## Filtering Product Pages vs. Category Pages

The discovery system uses **generic pattern matching** to ensure only product detail pages (PDPs) are returned, not category or listing pages. This works across different e-commerce platforms and languages.

### Product Page Detection Logic

**Strong product indicators** (path-based):
- `/product/`, `/produkt/`, `/p/`, `/art/`, `/artikel/`
- `/item/`, `/pd/`, `-p-`

**Product ID patterns** (must have one):
- Numeric ID at end: `/product-name/12345` or `/product-name-12345`
- Alphanumeric SKU: `/product-name-CB1022` or `/adapter-p65980`
- Pattern: 4+ digits or letter-number codes at path end

**Category page signals** (automatic rejection):
- Generic category paths: `/category/`, `/katalog/`, `/browse/`
- Shallow structure: 2-3 segments with no product ID (e.g., `/electronics/laptops`)
- Last segment is category name only (no numbers): `/datorskarmar`, `/powerbank`
- Title patterns: "245 produkter", "visa alla", "browse", "category:"

### Decision Tree

```
1. Has strong product indicator? (e.g., /product/, /art/)
   ├─ YES: Has product ID/code at end?
   │   ├─ YES: ✅ Product page (score based on relevance)
   │   └─ NO: Has category signals?
   │       ├─ YES: ❌ Category page (score = 0)
   │       └─ NO: ❌ Uncertain, reject (score = 0)
   └─ NO: Has product ID/code?
       ├─ YES: ⚠️ Weak product signal (needs review)
       └─ NO: ❌ Not a product page (score = 0)
```

### Examples

✅ **Valid product pages:**
```
https://www.elgiganten.se/product/datorer/laptop/belkin-usb-hub/286349
  → Strong: /product/, ID: 286349 ✓

https://www.kjell.com/se/produkter/dator/usb-c-adapter-cb1022-p65980
  → Strong: /produkter/, SKU: cb1022-p65980 ✓

https://www.netonnet.se/art/dator-surfplatta/usb-hub/1018141.14397/
  → Strong: /art/, ID: 1018141.14397 ✓

https://www.amazon.com/dp/B08XYZ123
  → Strong: /dp/, ID: B08XYZ123 ✓
```

❌ **Rejected category pages:**
```
https://www.netonnet.se/art/dator-surfplatta/datorskarmar/datorskarmar-31-tum-storre
  → No product ID, last segment is category name ✗

https://www.kjell.com/se/produkter/dator/datorskarmar/kontorsskarmar
  → 3 segments, no ID, last = "kontorsskarmar" (office monitors) ✗

https://www.kjell.com/se/produkter/mobilt/powerbank
  → 2 segments, no ID, shallow structure ✗

https://example.com/products
  → Generic "/products" without ID ✗

https://example.com/category/electronics/laptops
  → "/category/" path, shallow structure ✗
```

### Why This Matters

- **Audit accuracy**: Category pages have no product schema → E=0, skews results
- **Intent matching**: Can't verify if category contains the right product
- **Fair comparison**: All peers must be evaluated on equivalent page types
- **Language/platform agnostic**: Works for Swedish, English, German sites; works for various e-commerce platforms

### When Discovery Returns `found=0`

If no product page is found matching the intent:
- **Valuable signal**: Peer may not carry that product category
- **Not a failure**: Helps identify category gaps in peer coverage
- **Action**: Manually verify if peer truly lacks that product category: Update audit to read from audit_urls.csv format)

# 3. Manually query AI assistants for SoA data
# Use intents from intents_peer_core_sv.csv
```
