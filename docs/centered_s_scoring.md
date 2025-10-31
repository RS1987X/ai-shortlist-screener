# Centered S Scoring: Active Avoidance of Poor Ratings

**Version:** v1.2.1  
**Date:** October 31, 2025  
**Status:** Implemented

---

## Executive Summary

S (Service) scoring has been redesigned to center at **3.5/5 as the neutral point**, creating active avoidance of poorly-rated retailers rather than just ranking them lower. This aligns with how humans naturally evaluate ratings: we don't just "slightly prefer" good ratings over bad ones—we actively **run from** bad ratings and seek out good ones.

**Key Change:**
- **Old approach (v1.2.0):** S ranges 0-100 (linear scale)
  - 2.0/5 rating → S=40 → adds +4 points to LAR
  - No active avoidance, just "less preferred"
  
- **New approach (v1.2.1):** S ranges -100 to +100 (centered scale)
  - 2.0/5 rating → S=-100 → subtracts -10 points from LAR
  - Active avoidance creates red flags for poor retailers

---

## The Problem: No Active Avoidance

### Current Behavior (v1.2.0)

With linear 0-100 scaling, even poor ratings contributed positively to LAR:

| Rating | S Score | Impact on LAR | AI Behavior |
|--------|---------|---------------|-------------|
| 5.0/5  | 100     | +10 points    | Prefer |
| 4.0/5  | 80      | +8 points     | Prefer |
| 3.5/5  | 70      | +7 points     | Prefer |
| 3.0/5  | 60      | +6 points     | Prefer (slightly less) |
| 2.0/5  | 40      | +4 points     | Still prefer! 🚨 |

**The Issue:** A retailer with 2.0/5 ratings still adds +4 points to their LAR score. The AI doesn't actively avoid them—it just ranks them lower than others. If a product is only available at a 2.0/5 retailer, the AI would still recommend it with LAR=44 vs baseline=40.

### Human Behavior vs AI Behavior

**How humans actually think about ratings:**
- 4.5-5.0/5: "Great! I'll definitely buy here." ✓
- 4.0/5: "Good enough, seems reliable." ✓
- 3.5/5: "Meh, average. Whatever." ~
- 3.0/5: "Hmm, kind of sketchy..." 🤔
- 2.0/5: "🚨 RED FLAG! Avoid this place!" ✗

Humans treat poor ratings as **warnings**, not just "slightly less attractive options." A 2-star rating signals potential problems: late delivery, poor customer service, scams, defective products.

---

## The Solution: Centered Scoring

### New Formula (v1.2.1)

```python
S = ((rating - RATING_NEUTRAL_POINT) / RATING_SCALE_RANGE) × 100 × confidence

Where:
  RATING_NEUTRAL_POINT = 3.5  # Middle of 1-5 scale
  RATING_SCALE_RANGE = 1.5    # Distance from neutral to max (5.0 - 3.5)
  confidence = min(1.0, rating_count / 25)  # From v1.2.0
```

### Score Mapping

| Rating | Deviation from 3.5 | S Score (full conf.) | Impact on LAR | AI Behavior |
|--------|-------------------|---------------------|---------------|-------------|
| 5.0/5  | +1.5              | **+100**            | +10 points    | ✓✓ Strongly recommend |
| 4.5/5  | +1.0              | **+66.7**           | +6.7 points   | ✓ Recommend |
| 4.0/5  | +0.5              | **+33.3**           | +3.3 points   | ✓ Recommend |
| 3.5/5  | 0.0               | **0**               | No change     | ~ Neutral (ignore S) |
| 3.0/5  | -0.5              | **-33.3**           | -3.3 points   | ⚠ Caution warning |
| 2.5/5  | -1.0              | **-66.7**           | -6.7 points   | ✗ Avoid |
| 2.0/5  | -1.5              | **-100**            | -10 points    | ✗ Actively avoid |

### Key Properties

1. **Symmetry:** The impact of a 5.0 rating (+10 LAR) equals the penalty of a 2.0 rating (-10 LAR)
2. **Neutrality:** 3.5/5 ratings have ZERO impact on LAR (true neutral point)
3. **Active Avoidance:** Ratings below 3.5 actively **subtract** from LAR scores
4. **Reward Excellence:** Ratings above 4.0 provide meaningful boosts

---

## Real-World Impact

### Example: Swedish Retail Market

**Actual ratings from audit data:**

| Retailer | Avg Rating | Products | Old S (v1.2.0) | New S (v1.2.1) | Change | Interpretation |
|----------|-----------|----------|---------------|---------------|--------|----------------|
| Rusta | 4.99/5 | 18 | 78.38 | **77.81** | -0.57 | ✓✓ Near-perfect stays excellent |
| NetOnNet | 4.01/5 | 14 | 46.88 | **34.27** | -12.61 | ✓ Good rating, positive boost |
| Clas Ohlson | 4.17/5 | 20 | 42.07 | **28.23** | -13.84 | ✓ Above neutral, boosted |
| Elgiganten | 4.43/5 | 6 | 13.95 | **10.87** | -3.08 | ⚠ Low confidence discount |
| Kjell | 4.42/5 | 20 | 4.05 | **3.00** | -1.05 | ⚠ Low confidence, minimal boost |

**Note:** Most retailers with ratings are above 4.0/5, so they maintain positive S scores. The centered approach would show dramatic negative impacts if we had retailers with 2-3 star ratings (which would be red-flagged).

### LAR Rankings Remain Stable

**Top 5 (Old vs New):**

| Rank | Old (v1.2.0) | LAR | New (v1.2.1) | LAR |
|------|--------------|-----|--------------|-----|
| 1 | NetOnNet | 43.29 | NetOnNet | 42.02 |
| 2 | Rusta | 34.27 | Rusta | 34.21 |
| 3 | Hornbach | 33.45 | Hornbach | 33.45 |
| 4 | Elgiganten | 33.12 | Elgiganten | 32.81 |
| 5 | k-bygg.se | 32.41 | k-bygg.se | 32.41 |

**Observation:** Rankings are stable because most Swedish retailers maintain 4.0-5.0 ratings. The real benefit comes when the AI encounters hypothetical poorly-rated retailers (2-3 stars)—it would now actively avoid them instead of just ranking them lower.

---

## AI Decision-Making Behavior

### Scenario: AI Needs to Recommend Where to Buy

**Assume all retailers have identical E/X/A scores (only S differs):**

#### Linear Scaling (v1.2.0)

```
Base LAR = 40.5 (from E=70, X=30, A=20)

Retailer with 5.0/5 → LAR = 40.5 + 10.0 = 50.5  ✓ Top choice
Retailer with 4.0/5 → LAR = 40.5 + 8.0  = 48.5  ✓ Good option
Retailer with 3.0/5 → LAR = 40.5 + 6.0  = 46.5  ○ Acceptable
Retailer with 2.0/5 → LAR = 40.5 + 4.0  = 44.5  ~ Still okay? 🤔
```

**Problem:** AI would still recommend the 2.0/5 retailer if it's the only option (44.5 > 40.5 baseline).

#### Centered Scaling (v1.2.1)

```
Base LAR = 40.5 (from E=70, X=30, A=20)

Retailer with 5.0/5 → LAR = 40.5 + 10.0 = 50.5  ✓✓ Strongly recommend
Retailer with 4.0/5 → LAR = 40.5 + 3.3  = 43.8  ✓ Recommend
Retailer with 3.5/5 → LAR = 40.5 + 0.0  = 40.5  ~ Neutral (ignore)
Retailer with 3.0/5 → LAR = 40.5 - 3.3  = 37.2  ⚠ Warn user
Retailer with 2.0/5 → LAR = 40.5 - 10.0 = 30.5  ✗ AVOID (red flag)
```

**Benefit:** AI now actively avoids the 2.0/5 retailer (LAR drops below baseline). It would only recommend as last resort with explicit warning.

---

## Theoretical Justification

### 1. Aligns with Human Psychology

Humans exhibit **loss aversion**: negative experiences (poor service) weigh more heavily than positive ones. Centered scoring creates symmetric penalties/rewards, matching this psychological pattern.

### 2. Creates Signal Quality

By treating 3.5/5 as "no information" (S=0), the scale focuses on **meaningful deviations**:
- Ratings significantly above 3.5 signal excellence
- Ratings significantly below 3.5 signal problems
- Ratings near 3.5 are neutral (insufficient signal)

### 3. Prevents Recommendation of Risky Options

A 2-star rating isn't just "less good than 5 stars"—it suggests fundamental issues:
- Late/missing deliveries
- Poor customer service
- Defective products
- Potential scams

Linear scaling treats these as "slightly less preferred." Centered scaling treats them as **disqualifying factors**.

### 4. Industry Alignment

Other platforms use similar approaches:
- **Amazon**: Products below 3.5 stars rarely appear in top results
- **Yelp**: 2-star businesses are effectively filtered out
- **TripAdvisor**: Hotels below 3.5 are flagged as "below average"
- **Google Reviews**: 3.0+ is threshold for "acceptable"

### 5. AI Safety

For AI agents making autonomous purchase decisions:
- **Linear scaling**: Agent might buy from sketchy retailers (better than nothing!)
- **Centered scaling**: Agent avoids poor retailers unless explicitly instructed

This reduces risk of bad recommendations that could harm users.

---

## Configuration

### Constants in `src/asr/config.py`

```python
# Centered S scoring - 3.5/5 is the neutral point
RATING_NEUTRAL_POINT = 3.5  # Middle of 1-5 scale
RATING_SCALE_RANGE = 1.5    # Distance from neutral to max (5.0 - 3.5)

# Still using confidence weighting from v1.2.0
RATING_CONFIDENCE_THRESHOLD = 25  # Full confidence at 25+ reviews
FALLBACK_RATING_WEIGHT = 0.9      # JS ratings slightly discounted
```

### Alternative Neutral Points

You could adjust the neutral point based on category or market:

| Neutral Point | When to Use | Effect |
|---------------|-------------|--------|
| 3.0/5 | Lenient markets | Only 1-2 star ratings penalized |
| 3.5/5 | **Balanced (default)** | Middle of scale, symmetric |
| 4.0/5 | Strict markets | Only 4-5 star ratings rewarded |

**Recommendation:** Stick with 3.5 for most use cases. It's the mathematical midpoint and aligns with consumer expectations.

---

## Implementation Details

### Code Changes (v1.2.1)

**Before (v1.2.0):**
```python
# Linear scaling: 0-100
rating_normalized = (rating_float / 5.0) * 100 * confidence * rating_source_weight
```

**After (v1.2.1):**
```python
# Centered scaling: -100 to +100
rating_normalized = ((rating_float - RATING_NEUTRAL_POINT) / RATING_SCALE_RANGE) * 100 * confidence * rating_source_weight
```

**Modified Files:**
- `src/asr/config.py`: Added `RATING_NEUTRAL_POINT` and `RATING_SCALE_RANGE`
- `src/asr/lar.py`: Updated rating normalization in `compute_lar()` and `compute_weighted_lar()`

### Backward Compatibility

**Breaking change:** S scores can now be negative.

**Impact on existing data:**
- LAR scores will shift for retailers with ratings
- Retailers with >3.5 ratings see minimal change
- Retailers with <3.5 ratings would see significant drops (if they existed)
- Retailers without ratings (S=0) are unaffected

**Migration:** Simply recompute LAR scores from existing audit data. No data loss or format changes.

---

## Limitations and Future Work

### Current Limitations

1. **Linear Confidence Discount**
   - Current: confidence scales linearly with review count
   - Issue: 1 review = 4% confidence, but should be near zero
   - Solution: Use logarithmic or square-root scaling

2. **No Recency Weighting**
   - Old reviews might not reflect current service quality
   - Solution: Decay older reviews exponentially

3. **No Variance Consideration**
   - A 4.0 with all 4-star reviews is more reliable than 4.0 with mix of 1-star and 5-star
   - Solution: Penalize high variance (polarized opinions)

4. **Fixed Neutral Point**
   - 3.5/5 may not be appropriate for all product categories
   - Solution: Category-specific neutral points

### Future Enhancements

**1. Bayesian Averaging (Cold Start Problem)**
```python
# Shrink toward category average when few reviews
bayesian_rating = (prior_weight * category_avg + count * observed_rating) / (prior_weight + count)
```

**2. Recency Decay**
```python
# Weight recent reviews more heavily
age_weight = exp(-age_in_days / decay_constant)
weighted_rating = sum(rating * age_weight) / sum(age_weight)
```

**3. Variance Penalty**
```python
# Penalize polarized ratings
variance_penalty = 1.0 - min(0.3, stdev / 2.0)  # Max 30% penalty
adjusted_rating = raw_rating * variance_penalty
```

**4. Category-Specific Neutral Points**
```python
NEUTRAL_POINTS = {
    "electronics": 4.0,  # Consumers expect excellence
    "home_goods": 3.5,   # More tolerance for variation
    "groceries": 3.0,    # Basic functionality matters most
}
```

---

## Testing and Validation

### Unit Tests

**Test centered scoring formula:**
```python
def test_centered_scoring():
    assert compute_s_score(5.0, confidence=1.0) == 100
    assert compute_s_score(4.0, confidence=1.0) == 33.3
    assert compute_s_score(3.5, confidence=1.0) == 0
    assert compute_s_score(3.0, confidence=1.0) == -33.3
    assert compute_s_score(2.0, confidence=1.0) == -100
```

**Test symmetry:**
```python
def test_symmetry():
    s_excellent = compute_s_score(5.0, confidence=1.0)  # +100
    s_terrible = compute_s_score(2.0, confidence=1.0)   # -100
    assert abs(s_excellent + s_terrible) < 0.01  # Sum ≈ 0
```

### Integration Tests

**Scenario: Poorly-rated retailer**
```python
# Hypothetical retailer with 2.5/5 rating
assert compute_lar(..., rating=2.5) < compute_lar(..., rating=None)
# Poor rating should REDUCE LAR below baseline
```

---

## References

### Statistical Foundations
- Wilson, E. B. (1927). "Probable Inference, the Law of Succession, and Statistical Inference"
- Standard error of proportion: σ = √(p(1-p)/n)
- Margin of error at 95% CI: MOE = 1.96 × σ

### Industry Practices
- **Amazon**: "Customer Reviews" algorithm (proprietary, but known to filter <3.5)
- **Yelp**: Uses Bayesian averaging with recency weighting
- **Google Reviews**: Default sort by "Most relevant" down-ranks outliers
- **TripAdvisor**: "Popularity Ranking" heavily weights 4-5 star reviews

### Behavioral Economics
- Kahneman & Tversky (1979): "Prospect Theory: An Analysis of Decision under Risk"
- Loss aversion: Losses loom larger than equivalent gains
- Reference points matter for decision-making

### AI Safety
- Russell, S. (2019). *Human Compatible: AI and the Problem of Control*
- Avoiding risky recommendations when uncertainty is high

---

## Changelog

### v1.2.1 (October 31, 2025)
- ✅ Implemented centered S scoring with 3.5/5 as neutral point
- ✅ Added `RATING_NEUTRAL_POINT` and `RATING_SCALE_RANGE` config constants
- ✅ Updated `compute_lar()` and `compute_weighted_lar()` with new formula
- ✅ Documented rationale, impact analysis, and future work
- ✅ Tested on Swedish retail market data (stable rankings, correct behavior)

---

## Summary

Centered S scoring transforms ratings from a **ranking signal** into a **quality signal with active avoidance**. By setting 3.5/5 as the neutral point, we create AI behavior that matches human psychology: excellence is rewarded, mediocrity is ignored, and poor service is actively penalized.

This approach:
- ✅ Aligns with human decision-making patterns
- ✅ Reduces risk of bad AI recommendations
- ✅ Creates symmetric value for ratings above/below neutral
- ✅ Maintains compatibility with existing confidence weighting (v1.2.0)
- ✅ Follows industry best practices (Amazon, Yelp, Google)

**Result:** An AI that behaves like a cautious human shopper, not just a sorting algorithm.
