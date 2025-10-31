# Confidence Weighting for S (Service) Dimension

**Version:** 1.2.0  
**Date:** October 31, 2025  
**Status:** Implemented

---

## Problem Statement

Product ratings with few reviews are statistically unreliable, yet were treated equally to ratings with hundreds of reviews. This created unfair comparisons where a 5.0/5 rating with 1 review scored higher than a 4.5/5 rating with 100 reviews.

### Real-World Example (Before Confidence Weighting)

| Retailer | Avg Rating | Avg Review Count | Old S Score | Issue |
|----------|------------|------------------|-------------|-------|
| Elgiganten | 4.52/5 | 4.4 reviews | 84.7 | **Overvalued** - small sample size |
| Clas Ohlson | 3.63/5 | 50.8 reviews | 72.6 | **Undervalued** - large sample size |

Elgiganten scored higher despite having 10x fewer reviews per product!

---

## Solution: Confidence-Based Discounting

Ratings are now weighted by their statistical confidence, which scales with review count.

### Formula

```python
confidence = min(1.0, rating_count / RATING_CONFIDENCE_THRESHOLD)
S_score = (rating_value / 5.0) * 100 * confidence * source_weight
```

Where:
- `rating_count`: Number of reviews for the product
- `RATING_CONFIDENCE_THRESHOLD = 25`: Reviews needed for full confidence
- `source_weight`: 1.0 for JSON-LD ratings, 0.9 for JS fallback

### Confidence Scaling Examples

| Review Count | Confidence | Example: 5.0/5 Rating | Final S Score |
|--------------|------------|----------------------|---------------|
| 1 | 0.04 (4%) | 5.0 × 0.04 = 0.20/5 | 4.0 |
| 5 | 0.20 (20%) | 5.0 × 0.20 = 1.00/5 | 20.0 |
| 10 | 0.40 (40%) | 5.0 × 0.40 = 2.00/5 | 40.0 |
| 25 | 1.00 (100%) | 5.0 × 1.00 = 5.00/5 | 100.0 |
| 50+ | 1.00 (100%) | 5.0 × 1.00 = 5.00/5 | 100.0 |

**Key insight:** A 5.0/5 rating with only 1 review contributes the same as a 0.2/5 rating!

---

## Theoretical Justification

### Why 25 Reviews as Threshold?

The threshold of 25 reviews balances:

1. **Statistical Confidence**
   - Margin of error at 95% confidence: ±20% for n=25
   - Standard error: ~0.20 for 5-point scale with n=25
   - Adequate for comparative purposes (not perfect, but reasonable)

2. **Practical Considerations**
   - Too low (e.g., 10): Doesn't sufficiently penalize small samples
   - Too high (e.g., 100): Penalizes legitimate newer products too harshly
   - 25 is achievable for popular products but still filters noise

3. **Empirical Data from Swedish Retail**
   - Average review counts observed: 4.4 to 60.8 per product
   - Median typically 15-30 reviews for established products
   - 25 sits at realistic threshold for "trusted" rating

### Statistical Margin of Error

For a 5-point rating scale (assuming variance ≈ 1.5):

| Sample Size | Standard Error | 95% CI |
|-------------|----------------|--------|
| n=5 | 0.55 | ±1.08 (±22%) |
| n=10 | 0.39 | ±0.76 (±15%) |
| n=25 | 0.24 | ±0.48 (±10%) |
| n=50 | 0.17 | ±0.34 (±7%) |
| n=100 | 0.12 | ±0.24 (±5%) |

At 25 reviews, we achieve ~±10% margin of error, which is acceptable for ranking purposes.

---

## Impact Analysis

### Before vs After (Real Data)

| Retailer | Avg Rating | Avg Reviews | Old S | New S | Change | Reason |
|----------|------------|-------------|-------|-------|--------|--------|
| **Rusta** | 4.74/5 | 60.8 | 96.7 | 78.4 | **-18.3** | Some products below threshold |
| **Elgiganten** | 4.52/5 | 4.4 | 84.7 | 14.0 | **-70.7** | Low review counts penalized |
| **NetOnNet** | 4.01/5 | 20.1 | 80.3 | 46.9 | **-33.4** | Moderate penalty |
| **Clas Ohlson** | 3.63/5 | 50.8 | 72.6 | 42.1 | **-30.5** | High review count, but lower ratings |
| **Kjell** | 3.10/5 (est) | ~15 | 62.0 | 4.1 | **-57.9** | Low count + mediocre rating |

### LAR Ranking Changes

**Before Confidence Weighting:**
1. NetOnNet (46.63)
2. Elgiganten (40.19) ← Artificially high
3. Rusta (36.10)

**After Confidence Weighting:**
1. NetOnNet (43.29)
2. Rusta (34.27)
3. Elgiganten (33.12) ← Corrected downward

**Key outcome:** Retailers with consistent, well-reviewed products maintain high scores. Retailers with sparse reviews are appropriately downranked.

---

## Why This Matters for AI Recommendations

### Without Confidence Weighting
- AI might recommend products based on 1-2 positive reviews
- New/unpopular products get undeserved advantage
- Established products with consistent 4.0/5 (100 reviews) lose to 5.0/5 (1 review)

### With Confidence Weighting
- ✅ AI prioritizes products with proven track records
- ✅ New products can still rank if they accumulate reviews
- ✅ Reflects real-world consumer behavior (people trust volume + quality)
- ✅ Aligns with how humans assess credibility

### Real User Queries
- "Show me the best-rated USB cables" → Should favor 4.5/5 (200 reviews) over 5.0/5 (3 reviews)
- "Find highly-rated monitors" → Confidence weighting ensures robustness

---

## Configuration & Tuning

### Current Parameters (v1.2.0)

```python
# src/asr/config.py
RATING_CONFIDENCE_THRESHOLD = 25  # Full confidence at 25+ reviews
FALLBACK_RATING_WEIGHT = 0.9      # JS ratings slightly discounted
```

### Alternative Thresholds (for experimentation)

| Threshold | Philosophy | Use Case |
|-----------|------------|----------|
| 10 | Lenient | High-volume e-commerce, fast turnover |
| 25 | Balanced | **Current default** - General retail |
| 50 | Strict | High-stakes purchases (appliances, tools) |
| 100 | Very strict | Premium/luxury segments |

### How to Adjust

Edit `src/asr/config.py`:
```python
RATING_CONFIDENCE_THRESHOLD = 50  # Require 50 reviews for full confidence
```

Then recompute LAR:
```bash
.venv/bin/asr lar data/audit_results.csv data/soa_log.csv --out data/lar_scores.csv
```

---

## Limitations & Future Work

### Current Limitations

1. **Linear scaling:** Confidence scales linearly (0 to 1.0). Could use logarithmic or sigmoid curves for more nuanced behavior.

2. **No recency weighting:** Old reviews count equally to new ones. Future versions could weight recent reviews higher.

3. **No variance consideration:** Doesn't account for rating distribution (e.g., polarized vs consistent ratings).

4. **Category-agnostic:** Same threshold for all product types. Premium products might need higher thresholds.

### Future Enhancements (Roadmap)

- **Bayesian averaging:** Use global mean to shrink estimates toward baseline
- **Recency decay:** Weight recent reviews more heavily (exponential decay)
- **Variance penalty:** Penalize products with highly divided opinions
- **Category-specific thresholds:** Electronics vs consumables have different review patterns
- **Velocity metric:** Reward products gaining reviews quickly (trending indicator)

---

## References

### Statistical Foundations
- **Standard Error of Mean:** SE = σ / √n
- **Confidence Intervals:** For 95% CI, multiply SE by 1.96
- **Central Limit Theorem:** Applies for n ≥ 25-30

### Industry Practices
- **Amazon:** Uses Bayesian averaging (weighted toward 3.5/5 baseline)
- **Yelp:** Requires minimum review counts for "certified" badges
- **Google Reviews:** Aggregates with confidence intervals shown
- **TripAdvisor:** Popularity + rating combined metric

### Related Reading
- Evan Miller: "How Not To Sort By Average Rating" (Bayesian approach)
- Wilson Score Interval for binomial proportions
- IMDb Top 250 methodology (weighted ratings)

---

## Summary

**Confidence weighting ensures that S (Service) scores reflect both quality AND reliability of ratings. A 5.0/5 rating with 1 review is treated as far less valuable than a 4.0/5 rating with 50 reviews, which aligns with how humans naturally assess credibility.**

**Impact:** More robust LAR rankings that AI systems can confidently use for product recommendations.
