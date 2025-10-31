
# ai-shortlist-screener (ASR/LAR)

A lightweight toolkit to screen peers and estimate AI Shortlist Readiness (ASR) and Likelihood of AI Recommendation (LAR).

> **New to this project?** Read the **[Architecture Overview](docs/architecture.md)** first to understand how the three-stage pipeline (Discover → Audit → LAR) works, key design decisions, and implementation details. This comprehensive guide covers the entire system from discovery to scoring.

## Recent Improvements (Oct 31, 2025)

✨ **100% validation accuracy** on test samples (NetOnNet, Hornbach, Biltema, Byggmax)

- **JS Fallback**: Captures client-side rendered JSON-LD (Playwright-based) - fixed Biltema/Byggmax under-scoring
- **GTIN Detection Fix**: Now recognizes generic `gtin` field (50% adoption in Swedish retail)
- **Tiered Identifiers**: GTIN (20pts) vs Brand+MPN (12pts) reflects real matching capability
- **Transparency**: CSV includes `js_jsonld`, `ident_gtin`, `ident_brand_mpn` flags

**Impact**: More accurate scores, especially for JS-heavy retailers. See [docs/updates.md](docs/updates.md) for details.

## Quickstart

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

### Step 1: Discover Product URLs (Optional but Recommended)

Find product URLs for each intent × peer combination using one of two methods:

**Method 1: Sitemap Search (Recommended - Fast & Free)**
```bash
# No API key required - searches retailer sitemaps
asr discover \
  --intents-csv data/intents/intents_peer_core_sv.csv \
  --peers-csv data/multibrand_retailer_peers.csv \
  --out data/audit_urls.csv
```

**Method 2: Google Custom Search API (Fallback)**
```bash
# Requires API key (free tier: 100/day) - see docs/url_discovery.md
export GOOGLE_API_KEY="your-api-key"
export GOOGLE_SEARCH_ENGINE_ID="your-cx-id"

asr discover --use-api \
  --intents-csv data/intents/intents_peer_core_sv.csv \
  --peers-csv data/multibrand_retailer_peers.csv \
  --out data/audit_urls.csv
```

**Output**: `data/audit_urls.csv` with URLs for manual review before audit.

**Why sitemap search?** 
- ✅ Free (no API costs)
- ✅ Fast (5-10 seconds per retailer)
- ✅ No rate limits
- ✅ 75% retailer coverage (12/16 have sitemaps)
- ✅ Falls back to Google API for retailers without sitemaps

**See:** [Sitemap Discovery Guide](docs/sitemap_discovery.md) for details.

### Step 2: Audit Product Pages

```bash
# From discovered URLs (recommended)
asr audit data/audit_urls.csv --out audit/asr_report.csv

# Or from a simple URL list
asr audit urls.txt --out audit/asr_report.csv --follow-children 2
```

### Step 3: Compute LAR Scores

```bash
# Standard LAR (S auto-computed from product ratings)
asr lar audit/asr_report.csv data/soa_log.csv --out audit/lar_scores.csv

# Override S with manual satisfaction scores (e.g., from Trustpilot)
asr lar audit/asr_report.csv data/soa_log.csv --service-csv data/service.csv --out audit/lar_scores.csv

# Category-weighted LAR (handles peer category imbalance)
asr lar audit/asr_report.csv data/soa_log.csv --weighted --out audit/lar_weighted.csv
```

**Note**: The S (Service Quality) dimension is now **auto-computed** from product ratings found in the audit data. Use `--service-csv` to provide manual overrides when needed (e.g., Trustpilot or Google Reviews scores for retailers without on-site ratings).

---

## Category-Weighted LAR

When analyzing peers with different category coverage (e.g., some peers compete in electronics + DIY, others only in automotive), use `--weighted` to ensure fair comparison:

- Each peer's LAR is computed as the **average of their category-level scores**
- Categories are defined in `data/intent_categories.csv` and `data/peer_categories.csv`
- Prevents category imbalance from skewing results (e.g., 9 DIY peers vs. 6 electronics peers)

**Example**: A specialist electronics retailer (Kjell) won't be penalized for not competing in building materials, while a generalist (Clas Ohlson) is evaluated across all categories where they compete.

---

## Documentation

- **[Architecture Overview](docs/architecture.md)** ⭐ **Start here** - How the system works, where logic lives, design decisions
- **[Sitemap Discovery Guide](docs/sitemap_discovery.md)**: Fast, free URL discovery via sitemaps
- **[URL Discovery Guide](docs/url_discovery.md)**: Google API method and setup
- **[Category Weighting](docs/category_weighting.md)**: Fair peer comparisons across categories
- **[Methodology](docs/methodology.md)**: E·X·A·D·S framework overview
- **[Scoring](docs/scoring.md)**: Product & family scoring details

