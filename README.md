
# ai-shortlist-screener (ASR/LAR)

A lightweight toolkit to screen peers and estimate AI Shortlist Readiness (ASR) and Likelihood of AI Recommendation (LAR).

## Quickstart

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

### Step 1: Discover Product URLs (Optional but Recommended)

Find product URLs for each intent × peer combination using unbiased site-specific searches:

```bash
# Requires Google Custom Search API (free tier: 100/day)
# See docs/url_discovery.md for setup
export GOOGLE_API_KEY="your-api-key"
export GOOGLE_SEARCH_ENGINE_ID="your-cx-id"

asr discover \
  --intents-csv data/intents/intents_peer_core_sv.csv \
  --peers-csv data/multibrand_retailer_peers.csv \
  --out data/audit_urls.csv
```

**Output**: `data/audit_urls.csv` with URLs for manual review before audit.

**Why this matters**: Using Google to find URLs can introduce bias. This tool uses **site-specific queries** (`site:domain.com terms`) and **re-ranks by spec match** (not Google rank) to minimize bias.

### Step 2: Audit Product Pages

```bash
# From discovered URLs (recommended)
asr audit data/audit_urls.csv --out audit/asr_report.csv

# Or from a simple URL list
asr audit urls.txt --out audit/asr_report.csv --follow-children 2
```

### Step 3: Compute LAR Scores

```bash
# Standard LAR (simple average across all intents)
asr lar audit/asr_report.csv data/soa_log.csv data/distribution.csv data/service.csv --out audit/lar_scores.csv

# Category-weighted LAR (handles peer category imbalance)
asr lar audit/asr_report.csv data/soa_log.csv data/distribution.csv data/service.csv --out audit/lar_weighted.csv --weighted
```

---

## Category-Weighted LAR

When analyzing peers with different category coverage (e.g., some peers compete in electronics + DIY, others only in automotive), use `--weighted` to ensure fair comparison:

- Each peer's LAR is computed as the **average of their category-level scores**
- Categories are defined in `data/intent_categories.csv` and `data/peer_categories.csv`
- Prevents category imbalance from skewing results (e.g., 9 DIY peers vs. 6 electronics peers)

**Example**: A specialist electronics retailer (Kjell) won't be penalized for not competing in building materials, while a generalist (Clas Ohlson) is evaluated across all categories where they compete.

---

## Documentation

- **[URL Discovery Guide](docs/url_discovery.md)**: How to find product URLs without bias
- **[Category Weighting](docs/category_weighting.md)**: Fair peer comparisons across categories
- **[Methodology](docs/methodology.md)**: E·X·A·D·S framework overview
- **[Scoring](docs/scoring.md)**: Product & family scoring details

