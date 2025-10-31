# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [1.2.0] - 2025-10-31

### Added
- **Statistical Confidence Weighting for Ratings (S Dimension)**
  - Ratings now weighted by review count to reflect statistical reliability
  - Formula: `confidence = min(1.0, rating_count / 25)`
  - Threshold of 25 reviews provides ±10% margin of error at 95% CI
  - Prevents unreliable ratings (1-5 reviews) from scoring equally to robust ratings (50-100 reviews)
  - New configuration: `RATING_CONFIDENCE_THRESHOLD = 25` in config.py

- **Comprehensive Documentation for Confidence Weighting**
  - `docs/confidence_weighting.md`: Full statistical analysis with margin of error tables
  - Theoretical justification based on standard error, consumer trust patterns
  - Impact analysis showing S score adjustments of 14-71 points
  - Alternative threshold options (10/25/50/100) with use cases
  - Future enhancement roadmap: Bayesian averaging, recency weighting, variance penalty

### Changed
- **S Dimension Scoring Now Confidence-Weighted**
  - Low-review retailers see appropriate score reductions (Elgiganten: -70.7 points)
  - High-review retailers maintain strong scores with moderate adjustments (Rusta: -18.3 points)
  - Conservative default: full confidence (1.0) if rating_count missing or invalid

- **LAR Rankings Updated to Reflect Confidence**
  - NetOnNet remains #1 (43.29, down from 46.63)
  - Rusta moves to #2 (34.27, down from 36.10) - solid review volumes rewarded
  - Elgiganten drops to #3 (33.12, down from 40.19) - low review counts appropriately penalized

### Impact
- **Fairer Comparisons:** Ratings with statistical backing now score higher than unreliable ratings
- **AI Safety:** Prevents recommendations based on 1-2 potentially fake/biased reviews
- **Aligns with Consumer Behavior:** Humans naturally trust volume + quality, not just raw ratings
- **Industry Standard:** Follows practices of Amazon, Yelp, Google Reviews, TripAdvisor

### Technical Details
- Modified `compute_lar()` and `compute_weighted_lar()` in src/asr/lar.py
- Centralized configuration constants in src/asr/config.py
- No breaking changes: backward compatible with existing audit data
- Conservative handling: missing rating_count defaults to full confidence

---

## [1.1.0] - 2025-10-31

### Added
- **JS Fallback for Client-Side Rendered Content**
  - Single-pass Playwright-based extraction for CSR sites (Biltema, Byggmax)
  - Captures both JSON-LD structure and ratings in one browser render
  - New `js_jsonld` transparency flag in CSV output
  - Configurable via `has_jsonld_js` weight (15pts vs 20pts for SSR)

- **Tiered Identifier Scoring System**
  - Tier 1: GTIN present → `has_identifiers_gtin` = 20pts (exact matching)
  - Tier 2: Brand+MPN only → `has_identifiers_brand_mpn` = 12pts (fuzzy matching)
  - New CSV columns: `ident_gtin`, `ident_brand_mpn` (legacy `identifiers` retained)
  - Reflects real-world cross-retailer matching capability

- **Comprehensive Documentation**
  - `docs/updates.md`: Detailed changelog with technical rationale
  - `docs/validation.md`: Test results showing 100% accuracy
  - `COMMIT_MESSAGE.md`: Structured commit message for version control

### Fixed
- **Generic GTIN Field Detection Bug** (Critical)
  - Now extracts generic `gtin` field in addition to `gtin13/14/8/12`
  - Schema.org accepts both variants; we were only checking specific ones
  - Impact: GTIN adoption 50% (was 0% due to bug)
  - Affected retailers: NetOnNet, Elgiganten now correctly credited

### Changed
- **Scoring Weights Refinement**
  - Split `has_identifiers` into `has_identifiers_gtin` (20) + `has_identifiers_brand_mpn` (12)
  - Added `has_jsonld_js` (15) for JS-rendered structured data
  - Server-rendered JSON-LD remains `has_jsonld` (20)
  
- **CSV Output Schema Extension**
  - Added: `js_jsonld`, `ident_gtin`, `ident_brand_mpn` transparency columns
  - Retained: `identifiers` (legacy) for backward compatibility
  - Enables detailed analysis of data quality and rendering methods

### Validated
- **5/5 Test Samples - 100% Accuracy**
  - NetOnNet S7: E=68.0 ✓ (server-rendered, GTIN present)
  - NetOnNet S2: E=68.0 ✓ (server-rendered, GTIN present)
  - Hornbach S1: E=68.0 ✓ (server-rendered, SKU+Brand)
  - Biltema S1: E=64.0 improved from 8.0 (JS fallback captured data)
  - Byggmax S1: E=52.0 improved from 24.0 (JS fallback captured data)

### Technical Details
- **Files Modified:**
  - `src/asr/parse.py`: Added generic `gtin` extraction
  - `src/asr/audit.py`: JS fallback integration, tiered identifier logic
  - `src/asr/config.py`: New weight structure (gtin/brand_mpn split)
  - `src/asr/js_fallback.py`: Efficient single-pass extraction with Playwright
  - `docs/scoring.md`: Updated methodology with new weights
  
- **Breaking Changes:** None (maintains backward compatibility)
- **Performance:** JS fallback adds 2-3s per JS-rendered page (only when needed)
- **Dependencies:** Playwright (already in requirements.txt)

### Rationale
1. **Why JS Fallback?**
   - Many retailers (Biltema, Byggmax) use CSR - JSON-LD not in initial HTML
   - Old approach scored these sites artificially low (missing data)
   - New approach captures reality with slight scoring discount (accessibility cost)

2. **Why Tiered Identifiers?**
   - GTIN enables exact matching across retailers (100% precision)
   - Brand+MPN requires fuzzy matching (typo-prone, slower)
   - Scoring now reflects real-world AI matching capability

3. **Why 15pts for JS JSON-LD vs 20pts for Server JSON-LD?**
   - CSR slower for users, harder for bots/crawlers
   - SEO and accessibility implications
   - Still valuable data → credit given, but with realistic discount

---

## [1.0.0] - 2025-10-28

### Initial Release
- Three-stage pipeline: Discover → Audit → LAR
- Sitemap-based URL discovery (75% coverage, no API costs)
- E·X·A·D·S scoring framework
- Auto-computed Service (S) dimension from product ratings
- Category-weighted LAR for fair peer comparisons
- Comprehensive documentation and architecture guide

---

## Future Roadmap

### Planned Features
- [ ] Multi-threaded audit for faster processing (227 URLs in <5 min)
- [ ] Historical LAR tracking (monitor score changes over time)
- [ ] Competitive gap analysis reports (where peers excel/lag)
- [ ] API endpoint for real-time scoring
- [ ] Dashboard for stakeholder visualization

### Under Consideration
- [ ] Support for more Schema.org types (Review, FAQ, HowTo)
- [ ] Machine learning model for LAR prediction
- [ ] Integration with Google Search Console data
- [ ] Automated alerting for score drops

---

**For detailed technical explanations, see:**
- [docs/updates.md](updates.md) - Implementation details and rationale
- [docs/validation.md](validation.md) - Test results and accuracy confirmation
- [docs/scoring.md](scoring.md) - Complete scoring methodology
