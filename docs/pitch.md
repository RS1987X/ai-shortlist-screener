# LAR Model: AI Shortlist Readiness Score

**1-2 minute pitch** • October 2025

---

## The Problem

**AI is changing how customers discover products—but retailers are unprepared.**

Google AI Overviews, ChatGPT, and Perplexity are shortlisting products *without* traditional search ranking signals. Instead, they rely on **machine-readable structured data** to extract, compare, and recommend products.

**Current reality:**
- Traditional SEO metrics (backlinks, page speed, keywords) don't predict AI visibility
- Retailers don't know if their product pages are "AI-ready"
- No objective way to measure likelihood of AI recommendation

**The risk:** Retailers with poor structured data are invisible to AI, even with great products.

---

## The Solution: LAR Score

**LAR (Likelihood of AI Recommendation)** = Single score (0-100) measuring how ready a retailer's product pages are for AI discovery.

### Formula
```
LAR = 0.40·E + 0.25·X + 0.25·A + 0.10·S
```

**Four dimensions:**

1. **E (Eligibility)** – 40% weight  
   *Can AI extract your product data?*
   - JSON-LD structured data completeness
   - Product identifiers (GTIN, Brand+MPN)
   - Offers with price and availability
   - **Penalty:** E < 60 → LAR capped at 40 (prerequisite for AI visibility)

2. **X (eXtensibility)** – 25% weight  
   *Can AI answer customer questions?*
   - Policy data: Returns, warranty, shipping (50 pts)
   - Technical specs with units: "65W", "4K", "10cm" (50 pts)
   - Enables queries like "Show me monitors with 2-year warranty"

3. **A (Share of Answer)** – 25% weight  
   *Do you actually appear in AI answers?*
   - Measured via AI query testing across intents
   - Outcome metric: validates that E+X lead to visibility

4. **S (Sentiment)** – 10% weight  
   *Are you a safe recommendation?*
   - Product ratings with confidence weighting
   - Centered at 3.5/5 stars (neutral point)
   - AI avoids low-rated retailers (risk mitigation)

---

## Why This Model Works

### Aligned with AI Behavior
- **E dimension:** Reflects AI's need for structured, machine-readable data
- **X dimension:** Captures AI's goal to provide rich, actionable answers
- **S dimension:** Models AI's risk aversion (bad recommendations hurt user trust)

### Empirically Validated
- Tested across 10+ Swedish retailers (electronics, tools, building materials)
- Strong correlation: High E+X scores → High A (share of answer)
- **Critical gap identified:** Zero retailers have structured policy data (missing 50 X points)

### Actionable Insights
- Pinpoints exact improvements: "Add `hasMerchantReturnPolicy` to Product schema"
- Tiered scoring shows ROI: Structured policy on PDP (50 pts) > policy page (40 pts) > links (25 pts)
- Attribution breakdown: See which variables drove your LAR score

---

## Competitive Advantage

**First-mover opportunity:**
- Structured policy data = **+10 LAR points** (from X=50 to X=100)
- Low implementation cost (one-time schema update)
- Immediate impact on policy-aware AI queries:
  - *"Find USB hubs with free returns"*
  - *"Show me monitors with 2-year warranty"*

**Bottom line:** LAR quantifies AI readiness, identifies gaps, and guides optimization for the AI search paradigm.

---

## What You Get

### Audit Tool
- Crawls product pages, extracts structured data
- Scores E, X, S dimensions automatically
- Identifies missing fields and implementation gaps

### LAR Computation
- Combines audit + share-of-answer tracking → LAR score
- Attribution breakdown: Which variables drove your score
- Category-weighted option: Fair comparison across product mixes

### Visualizations
- Top-N peer comparison charts
- Detailed component breakdowns (product/family, policy/specs)
- Per-retailer deep dives with context annotations

### Documentation
- Complete variable reference (every input to LAR)
- Implementation guidance (how to add missing structured data)
- Methodology rationale (why each dimension matters)

---

## Use Cases

1. **Benchmark:** Compare your LAR against competitors
2. **Optimize:** Prioritize structured data improvements by ROI
3. **Track:** Monitor LAR over time as AI search evolves
4. **Prove:** Show stakeholders why structured data investment matters

---

**Ready to measure your AI shortlist readiness?**

→ Run audit: `asr audit data/audit_urls.csv`  
→ Compute LAR: `asr lar data/audit_results.csv data/soa_log.csv`  
→ Visualize: `python scripts/visualize_attribution.py`

*See `docs/methodology.md` and `docs/lar_variables.md` for technical details.*
