# URL Discovery Methods - Quick Reference

## Three Discovery Approaches

### 1. `asr discover-playwright` ⭐ RECOMMENDED
```bash
asr discover-playwright --limit 10
```

**Best for**: Modern JS-heavy sites (Elgiganten, NetOnNet, etc.)

**Pros**:
- ✅ Handles JavaScript-rendered content
- ✅ No API costs or limits
- ✅ Built-in category page extraction
- ✅ Uses retailer's own search (most accurate)
- ✅ Works with SPAs and dynamic content

**Cons**:
- ⚠️ Requires Playwright + Chromium
- ⚠️ Slower than API (browser overhead)

**Setup**:
```bash
pip install playwright
playwright install chromium
```

---

### 2. `asr discover` (Google API + Fallback)
```bash
export GOOGLE_API_KEY="your-key"
export GOOGLE_SEARCH_ENGINE_ID="your-cx-id"
asr discover --limit 100
```

**Best for**: Fast discovery with Google's search index

**Pros**:
- ✅ Fast (uses Google's index)
- ✅ No browser needed
- ✅ Now includes category fallback (NEW!)
- ✅ Good for static sites

**Cons**:
- ⚠️ Costs $$ (free: 100 queries/day)
- ⚠️ Doesn't render JS
- ⚠️ API setup required

**Fallback behavior** (NEW):
- If top result is category page (score=0)
- → Extract products from that page
- → Return best product match

---

### 3. `asr discover-site` (BeautifulSoup)
```bash
asr discover-site --limit 10
```

**Best for**: Simple testing, static sites

**Pros**:
- ✅ No API needed
- ✅ No browser needed
- ✅ Lightweight

**Cons**:
- ⚠️ Static HTML only (no JS)
- ⚠️ No category fallback
- ⚠️ Hardcoded search patterns

---

## When to Use Each

| Scenario | Recommended Method |
|----------|-------------------|
| Modern JS-heavy retailer sites | `discover-playwright` ⭐ |
| SPAs (Single Page Apps) | `discover-playwright` ⭐ |
| Large-scale discovery (cost-sensitive) | `discover-playwright` ⭐ |
| Quick testing with Google API | `discover` |
| Static HTML sites (fast) | `discover` |
| No dependencies available | `discover-site` |

---

## Example Workflow

### Development/Testing
```bash
# Test with 5 intent×peer combinations
asr discover-playwright --limit 5
```

### Production (Full Run)
```bash
# Option 1: Playwright (no API needed)
asr discover-playwright \
  data/intents/intents_peer_core_sv.csv \
  data/peers.csv \
  data/urls_playwright.csv

# Option 2: Google API (if you have credits)
asr discover \
  data/intents/intents_peer_core_sv.csv \
  data/peers.csv \
  data/urls_google.csv \
  --limit 100
```

### Comparison Test
```bash
# Run both methods and compare results
asr discover-playwright --limit 10
mv data/audit_urls.csv data/urls_playwright.csv

asr discover --limit 10
mv data/audit_urls.csv data/urls_google.csv

# Compare
diff data/urls_playwright.csv data/urls_google.csv
```

---

## Performance Expectations

| Method | Speed | Accuracy | Cost |
|--------|-------|----------|------|
| Playwright | ~3-5s per search | Excellent | Free |
| Google API | ~0.5-1s per search | Good | $5/1000 queries |
| Site Search | ~2-3s per search | Good | Free |

**Note**: Actual speed depends on network, site responsiveness, and rate limiting.

---

## Category Page Handling

### Before (All Methods)
```
Search: "USB hub 4 ports" → Category page found
Result: score=0, URL rejected, found=0
❌ Data loss
```

### After (Playwright + Google API)
```
Search: "USB hub 4 ports" → Category page found
Fallback: Extract products from category page
Found: 15 product links
Best: https://retailer.com/product/usb-hub-123456 (score=0.65)
✅ Product recovered
```

---

## Configuration Files

All three methods use the same input/output format:

**Input**: 
- `data/intents/intents_peer_core_sv.csv` (intent specifications)
- `data/peers.csv` (retailer list)

**Output**:
- `data/audit_urls.csv` (discovered URLs with scores)

**Format**:
```csv
intent_id,brand,domain,url,relevance_score,title,search_query,found
usb_hub_001,Elgiganten,elgiganten.se,https://...,0.85,"USB-C Hub 4-port",playwright_site_search:...,1
```

---

## Troubleshooting

### Playwright errors
```bash
# Reinstall browsers
playwright install chromium

# Test installation
python scripts/test_playwright_discovery.py
```

### No products found
1. Check `SEARCH_PATTERNS` in `site_search_playwright.py`
2. Verify search URL manually in browser
3. Try increasing `max_links` parameter
4. Check if site blocks automation (add delays)

### Category pages not extracted
1. Verify score is actually 0.0 (check output)
2. Try non-headless mode: `headless=False`
3. Check product page detection patterns
4. Increase extraction timeout

---

## Key Files

| File | Purpose |
|------|---------|
| `src/asr/site_search_playwright.py` | NEW Playwright discovery |
| `src/asr/discover.py` | Google API + fallback |
| `src/asr/site_search.py` | BeautifulSoup discovery |
| `src/asr/cli.py` | CLI commands |
| `docs/playwright_discovery.md` | Full documentation |
| `scripts/test_playwright_discovery.py` | Quick test |
