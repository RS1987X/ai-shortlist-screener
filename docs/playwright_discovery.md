# URL Discovery Improvements - Playwright & Category Extraction

## What's New

Two major improvements to URL discovery to prevent data loss and handle modern JS-rendered websites:

### 1. **Playwright Site Search** (`asr discover-playwright`)
- Uses Playwright for JavaScript rendering (handles dynamic content, SPAs)
- Bypasses Google API entirely (no costs, no rate limits)
- Uses retailer's own search functionality (more accurate)
- Extracts products from both search results AND category pages

### 2. **Category Page Fallback** (all discovery methods)
- When Google/search returns a category page, automatically extracts product links from that page
- Prevents data loss when retailer HAS products but search returns category page
- Applies same product page filtering logic to ensure quality

## Installation

1. **Install Playwright** (if not already installed):
   ```bash
   pip install -e .
   playwright install chromium
   ```

2. **Verify installation**:
   ```bash
   python scripts/test_playwright_discovery.py
   ```

## Usage

### Playwright Discovery (Recommended for JS-heavy sites)

```bash
# Discover URLs using Playwright
asr discover-playwright --limit 10

# Full run (no limit)
asr discover-playwright
```

**Advantages:**
- ✅ Handles JavaScript-rendered search results
- ✅ No API costs or rate limits
- ✅ More accurate (uses retailer's search)
- ✅ Automatic category page extraction

**When to use:**
- Modern JS-heavy retailer websites
- SPAs (Single Page Applications)
- When you don't have Google API access
- When you want to avoid API costs/limits

### Google API Discovery with Fallback

```bash
# Still works, now with category page fallback
asr discover --limit 100

# Without API (scraping + fallback)
asr discover --no-use-api --limit 10
```

**Advantages:**
- ✅ Fast (Google's search index)
- ✅ Now includes category page extraction fallback
- ✅ No browser overhead

**When to use:**
- You have Google API access
- Static HTML sites
- When speed is critical

### Site Search (BeautifulSoup, no JS)

```bash
# Original site search (static HTML only)
asr discover-site --limit 10
```

**When to use:**
- Lightweight testing
- Static HTML retailer sites
- When you don't need JS rendering

## How Category Page Extraction Works

1. **Detection**: If search result has relevance score = 0 (likely category page)
2. **Extraction**: Parse that page's HTML to find product links
3. **Filtering**: Apply same product page detection logic (requires `/product/`, IDs, etc.)
4. **Scoring**: Score each extracted product against intent
5. **Selection**: Return best-scoring product

**Example:**
```
Search: "USB-C hub 4 ports" on elgiganten.se
Result: https://elgiganten.se/usb-hubbar (category page, score=0)
Fallback: Extract 15 product links from category page
Found: https://elgiganten.se/product/usb-c-hub-4-ports-pd/123456 (score=0.65)
```

## Comparison

| Feature | Google API | Playwright | Site Search (BS4) |
|---------|-----------|------------|-------------------|
| JS Rendering | ❌ | ✅ | ❌ |
| Category Fallback | ✅ | ✅ | ❌ |
| API Costs | $$ | Free | Free |
| Rate Limits | 100/day (free) | None | None |
| Speed | Fast | Medium | Medium |
| Accuracy | Good | Excellent | Good |
| Browser Required | No | Yes | No |

## Testing

### Quick Test (3 retailers)
```bash
python scripts/test_playwright_discovery.py
```

### Full Test (with sample intents)
```bash
# Create test subset
head -5 data/intents/intents_peer_core_sv.csv > /tmp/test_intents.csv
head -3 data/peers.csv > /tmp/test_peers.csv

# Test Playwright
asr discover-playwright \
  /tmp/test_intents.csv \
  /tmp/test_peers.csv \
  /tmp/urls_playwright.csv

# Test Google API with fallback
asr discover \
  /tmp/test_intents.csv \
  /tmp/test_peers.csv \
  /tmp/urls_google.csv \
  --limit 15
```

## Configuration

### Playwright Settings

Edit `src/asr/site_search_playwright.py`:

```python
# Browser configuration
self.browser = self.playwright.chromium.launch(
    headless=True,  # Set False to see browser
)

# Timeout settings
page.wait_for_load_state("networkidle", timeout=5000)  # Adjust timeout

# Max links to extract
products = self.extract_product_links_from_page(page, domain, max_links=15)
```

### Search Patterns

Add new retailer search URLs in `SEARCH_PATTERNS` dict:

```python
SEARCH_PATTERNS = {
    "newretailer.se": "https://www.newretailer.se/search?q={query}",
}
```

## Troubleshooting

### Playwright Not Found
```bash
pip install playwright
playwright install chromium
```

### Slow Performance
- Reduce `max_links` in `extract_product_links_from_page()`
- Decrease `timeout` in `page.wait_for_load_state()`
- Use `--limit` flag to test with fewer queries

### No Products Found
- Check if retailer domain is in `SEARCH_PATTERNS`
- Verify search URL pattern with browser
- Increase `max_links` to extract more products
- Check product page detection logic (may need site-specific rules)

### Category Pages Not Being Extracted
- Verify score is actually 0 (check output)
- Check if retailer blocks automated access
- Try non-headless mode: `headless=False`

## Performance Tips

1. **Use limits during development**:
   ```bash
   asr discover-playwright --limit 10  # Test with 10 searches first
   ```

2. **Run in parallel** (for large datasets):
   ```bash
   # Split intents into chunks and run parallel instances
   ```

3. **Adjust delays** in `discover_all()`:
   ```python
   time.sleep(2)  # Reduce if site allows, increase if getting blocked
   ```

## Next Steps

- [ ] Add more retailer search patterns to `SEARCH_PATTERNS`
- [ ] Tune product page detection patterns for specific sites
- [ ] Add retry logic for failed extractions
- [ ] Implement caching to avoid re-searching same queries

## Related Documentation

- `docs/url_discovery.md` - URL discovery methodology
- `docs/methodology.md` - Overall ASR/LAR methodology
- `README.md` - Main project documentation
