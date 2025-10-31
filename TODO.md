# AI Shortlist Screener - TODO Tracker

**Last Updated:** October 31, 2025

---

## 🎯 Current Sprint: LAR Validation & Extension

### Phase 1: Validation & Documentation ✅ Priority
**Goal:** Verify LAR results accuracy and document methodology

- [ ] **Manual E Dimension Validation** (1 hour)
  - [ ] Check 2 high-E retailers (NetOnNet, Hornbach)
    - Inspect Product JSON-LD, Offers, identifiers, specs
    - Confirm product_score reflects structured data quality
  - [ ] Check 2 low-E retailers (Biltema, Byggmax)
    - Understand why E scores are low (8.0, 24.0)
    - Document missing structured data elements
  - [ ] Document findings in `docs/validation.md`

- [ ] **X Dimension Deep Dive** (30 min)
  - [ ] Investigate NetOnNet X=45.6 advantage
    - Find sample URLs with structured policy data
    - Check if JSON-LD contains hasMerchantReturnPolicy, hasWarrantyPromise
    - Compare with baseline X=25.0 retailers
  - [ ] Document what distinguishes high X from baseline

- [ ] **S Dimension Spot Checks** (30 min)
  - [ ] Verify Rusta S=96.7 (highest score)
  - [ ] Verify Clas Ohlson S=72.6
  - [ ] Confirm rating extraction working correctly
  - [ ] Document rating sources (JSON-LD vs Fallback)

- [ ] **Create Validation Report** (30 min)
  - [ ] Template: `docs/validation.md`
  - [ ] Sections: E/X/S accuracy, limitations, confidence level
  - [ ] Include: Sample URLs, screenshots, findings

**Status:** 🔴 Not Started  
**Estimated Time:** 3 hours  
**Blocker:** None

---

### Phase 2: A Dimension Population (SOA Data)
**Goal:** Add empirical Share-of-Answer data to complete LAR framework

- [ ] **Manual SOA Collection** (2-4 hours)
  - [ ] Design query set (20-30 shopping questions)
    - Example: "best dishwasher under 5000 SEK"
    - Example: "where to buy power tools Sweden"
    - Example: "reliable electronics retailer Stockholm"
  - [ ] Run queries across AI assistants:
    - [ ] ChatGPT (10 queries)
    - [ ] Claude (10 queries)
    - [ ] Perplexity (10 queries)
  - [ ] Log retailer mentions in spreadsheet
  - [ ] Calculate SOA percentage per retailer
  - [ ] Populate `data/soa_log.csv`

- [ ] **Re-calculate LAR with A Dimension**
  - [ ] Run: `.venv/bin/asr lar data/audit_results.csv data/soa_log.csv --out data/lar_scores_v2.csv`
  - [ ] Compare rankings: before vs after A dimension
  - [ ] Analyze: Do E/X/S predict A? (correlation analysis)

- [ ] **Optional: Automated SOA Collection** (if time permits)
  - [ ] Set up OpenAI API batch queries
  - [ ] Parse responses for retailer mentions
  - [ ] Aggregate results automatically

**Status:** 🔴 Not Started  
**Estimated Time:** 2-4 hours  
**Blocker:** Phase 1 validation recommended first

---

### Phase 3: S Dimension Enhancement (Optional)
**Goal:** Expand rating coverage beyond product pages

- [ ] **Prisjakt Integration** (Swedish price comparison)
  - [ ] Research Prisjakt scraping/API options
  - [ ] Extract retailer ratings from Prisjakt
  - [ ] Weight: 0.7x (service-level, not product-level)
  - [ ] Add to S dimension calculation

- [ ] **Trustpilot Integration** (Company ratings)
  - [ ] Set up Trustpilot API access
  - [ ] Extract company-level ratings
  - [ ] Weight: 0.5x (service ratings, not product ratings)
  - [ ] Add to S dimension calculation

- [ ] **Re-calculate LAR with Enhanced S**
  - [ ] Run LAR with expanded S dimension
  - [ ] Compare: Product-only S vs Multi-source S
  - [ ] Document: Impact on rankings

**Status:** 🟡 Optional  
**Estimated Time:** 5-8 hours  
**Blocker:** API costs, scraping complexity

---

### Phase 4: Coverage Improvement (If Time Permits)
**Goal:** Increase products per retailer for better reliability

- [ ] **Fix Blocked Retailers**
  - [ ] Dustin (Cloudflare blocking)
  - [ ] Research workarounds: headers, delays, browser automation
  - [ ] Test solutions and document

- [ ] **Expand Search Terms**
  - [ ] Add intents to `data/intents/intents_peer_core_sv.csv`
  - [ ] Target: 50+ products per retailer
  - [ ] Re-run discovery with expanded terms

- [ ] **Re-run Full Pipeline**
  - [ ] Discovery → Audit → LAR
  - [ ] Compare: Small sample vs Large sample reliability

**Status:** 🟡 Optional  
**Estimated Time:** 5-10 hours  
**Blocker:** Time-intensive, diminishing returns

---

## 🆕 New Branch: Stock & Revenue Tracking

### Overview
**Goal:** Track product availability (in-stock vs out-of-stock) across retailers to estimate revenue potential and market dynamics.

**Business Value:**
- Revenue gauge: Estimate sales volume by tracking stock levels
- Market dynamics: Which retailers have better supply chain?
- Product lifecycle: Track when products go out of stock
- Competitive intelligence: Who stocks what products?

---

### Phase 1: Design & Architecture 🔴 Not Started
**Goal:** Define data model and collection strategy

- [ ] **Define Data Model** (1 hour)
  ```csv
  # stock_log.csv structure proposal:
  timestamp,url,domain,product_id,in_stock,price,currency,source
  2025-10-31T12:00:00,https://...,elgiganten.se,377217,true,4999,SEK,json-ld
  ```
  - [ ] Decide: What fields to track?
  - [ ] Decide: How to identify same product across retailers?
  - [ ] Decide: Frequency of checks? (daily, weekly, on-demand)

- [ ] **Extraction Strategy** (30 min)
  - [ ] Approach 1: JSON-LD `Offer.availability` field
    - Standard values: "InStock", "OutOfStock", "PreOrder"
  - [ ] Approach 2: HTML selectors (fallback)
    - Button text: "Add to cart" vs "Notify when available"
  - [ ] Approach 3: Inventory APIs (if available)

- [ ] **Architecture Design** (1 hour)
  - [ ] New module: `src/asr/stock.py`
  - [ ] CLI command: `asr stock data/audit_urls.csv --out data/stock_log.csv`
  - [ ] Integration: Should it run after audit? Or separate?
  - [ ] Storage: CSV, SQLite, or time-series database?

**Status:** 🔴 Not Started  
**Estimated Time:** 2-3 hours  
**Deliverable:** Design document in `docs/stock_tracking.md`

---

### Phase 2: Stock Extraction Implementation
**Goal:** Build stock availability extraction logic

- [ ] **Create Stock Extraction Module**
  - [ ] File: `src/asr/stock.py`
  - [ ] Function: `extract_stock_info(html, url) -> dict`
    - Returns: `{in_stock: bool, price: float, availability: str}`
  - [ ] Strategy:
    1. Check JSON-LD Offer.availability
    2. Fallback: Parse HTML for stock indicators
    3. Fallback: Check button text/state

- [ ] **Add CLI Command**
  - [ ] File: `src/asr/cli.py`
  - [ ] Command: `asr stock <input_csv> --out <output_csv>`
  - [ ] Options:
    - `--frequency`: How often to check (daily, weekly)
    - `--monitor`: Continuous monitoring mode
    - `--notify`: Alert on stock changes

- [ ] **Test Extraction**
  - [ ] Test on 10 sample URLs (mix of in-stock and out-of-stock)
  - [ ] Verify accuracy across different retailers
  - [ ] Handle edge cases: Pre-order, discontinued, coming soon

**Status:** 🔴 Not Started  
**Estimated Time:** 4-6 hours  
**Blocker:** Phase 1 design must be complete

---

### Phase 3: Revenue Estimation Logic
**Goal:** Convert stock data to revenue insights

- [ ] **Revenue Estimation Model**
  - [ ] Assumption: Out-of-stock → Product was selling well
  - [ ] Metric 1: **Stock-out rate** = % time product out-of-stock
  - [ ] Metric 2: **Restock velocity** = Days between stock-outs
  - [ ] Metric 3: **Price trends** = Price changes over time
  - [ ] Metric 4: **Availability score** = Uptime percentage

- [ ] **Aggregation by Retailer**
  - [ ] Calculate per-retailer metrics:
    - Average stock-out rate
    - Average price competitiveness
    - Product range coverage (% of market products available)
  - [ ] Output: `data/revenue_gauge.csv`

- [ ] **Visualization**
  - [ ] Create dashboard or report
  - [ ] Charts: Stock-out rate by retailer, price trends
  - [ ] Insights: Who has best availability? Who reprices?

**Status:** 🔴 Not Started  
**Estimated Time:** 3-5 hours  
**Blocker:** Need Phase 2 stock data first

---

### Phase 4: Continuous Monitoring (Optional)
**Goal:** Track stock changes over time

- [ ] **Scheduled Monitoring**
  - [ ] Set up cron job or scheduler
  - [ ] Run: `asr stock` daily/weekly
  - [ ] Append results to time-series database

- [ ] **Change Detection**
  - [ ] Alert when stock status changes
  - [ ] Alert when prices change significantly
  - [ ] Track: Product lifecycle (launch → in-stock → out-of-stock → discontinued)

- [ ] **Historical Analysis**
  - [ ] Trend analysis: Stock patterns over weeks/months
  - [ ] Correlation: Stock-outs vs LAR scores?
  - [ ] Insights: Do high-LAR retailers have better availability?

**Status:** 🟡 Optional  
**Estimated Time:** 5-8 hours (+ ongoing maintenance)  
**Blocker:** Requires sustained monitoring commitment

---

## 📊 Integration: LAR + Stock Tracking

### Potential Combined Metrics
Once both branches are mature, consider:

- [ ] **D Dimension Revival?** (Distribution via stock availability)
  - D = Weighted availability across product categories
  - High D = Products consistently in stock
  
- [ ] **Competitiveness Index**
  - Combine: LAR (AI-readiness) + Stock (availability) + Price (competitiveness)
  - Output: Holistic retailer ranking

- [ ] **Correlation Analysis**
  - Research question: Do high-E retailers have better stock management?
  - Research question: Does SOA (A dimension) correlate with availability?

**Status:** 🔵 Future Work  
**Estimated Time:** TBD

---

## 🎓 Thesis/Research Outputs

### Documentation Deliverables
- [x] `docs/architecture.md` - System architecture (DONE)
- [x] `docs/methodology.md` - LAR methodology (DONE)
- [x] `docs/scoring.md` - Scoring details (DONE)
- [ ] `docs/validation.md` - Validation results (TODO)
- [ ] `docs/stock_tracking.md` - Stock tracking design (TODO)
- [ ] `docs/findings.md` - Key findings and insights (TODO)

### Data Outputs
- [x] `data/audit_results.csv` - Structured data audit (DONE)
- [x] `data/lar_scores.csv` - LAR v1 (E/X/S only) (DONE)
- [ ] `data/soa_log.csv` - Share of answer data (TODO)
- [ ] `data/lar_scores_v2.csv` - LAR v2 (E/X/A/S complete) (TODO)
- [ ] `data/stock_log.csv` - Stock availability tracking (TODO)
- [ ] `data/revenue_gauge.csv` - Revenue estimation (TODO)

---

## 🚀 Quick Start Guide

### Resume LAR Work
```bash
# Start with Phase 1 validation
1. Open data/lar_scores.csv
2. Pick top/bottom retailers to manually verify
3. Document findings in docs/validation.md
```

### Start Stock Tracking Work
```bash
# Start with Phase 1 design
1. Create docs/stock_tracking.md
2. Define data model and extraction strategy
3. Document in the new file
```

---

## 📝 Notes & Decisions

### Design Decisions Log
- **2025-10-31:** Decided to keep X and S separate (different constructs, sources, actionability)
- **2025-10-31:** Fallback rating weight = 0.7x (balance between value and quality)
- **2025-10-31:** PDP filter accuracy = 99.6% (acceptable, one false positive)

### Open Questions
- [ ] Should stock tracking run automatically after audit, or separate?
- [ ] How to identify same product across different retailers? (EAN/GTIN matching?)
- [ ] Should we weight stock data by product price (high-value products matter more)?

---

## 🏆 Success Metrics

### LAR Branch
- ✅ E/X/S validation confidence > 90%
- ⏳ A dimension populated with real SOA data
- ⏳ LAR scores stable and interpretable
- ⏳ Methodology documented for reproducibility

### Stock Tracking Branch
- ⏳ Stock extraction accuracy > 95%
- ⏳ Revenue gauge insights actionable
- ⏳ Monitoring runs reliably (if implemented)
- ⏳ Integration with LAR provides new insights

---

**Legend:**
- 🔴 Not Started
- 🟡 Optional / Low Priority
- 🟢 In Progress
- ✅ Completed
- 🔵 Future Work
