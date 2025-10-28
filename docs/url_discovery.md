# URL Discovery Setup Guide

## Overview

The `asr discover` command finds product URLs for each intent × peer combination using **site-specific Google searches** to minimize bias.

---

## Quick Start (No API Key - Limited)

```bash
# Uses web scraping (slow, may be blocked, violates ToS)
asr discover --no-use-api
```

**Limitations**: 
- Slow (3-5 sec per query)
- May be blocked by Google
- Violates Google ToS
- Not recommended for >50 queries

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
# (TODO: Update audit to read from audit_urls.csv format)

# 3. Manually query AI assistants for SoA data
# Use intents from intents_peer_core_sv.csv
```
