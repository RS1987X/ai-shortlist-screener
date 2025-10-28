
# ai-shortlist-screener (ASR/LAR)

A lightweight toolkit to screen peers and estimate AI Shortlist Readiness (ASR) and Likelihood of AI Recommendation (LAR).

## Quickstart
```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .

# Audit
asr audit urls.txt --out audit/asr_report.csv --follow-children 2

# LAR (standard)
asr lar audit/asr_report.csv data/soa_log.csv data/distribution.csv data/service.csv --out audit/lar_scores.csv

# LAR (category-weighted, handles peer category imbalance)
asr lar audit/asr_report.csv data/soa_log.csv data/distribution.csv data/service.csv --out audit/lar_weighted.csv --weighted
```

## Category-Weighted LAR

When analyzing peers with different category coverage (e.g., some peers compete in electronics + DIY, others only in automotive), use `--weighted` to ensure fair comparison:

- Each peer's LAR is computed as the **average of their category-level scores**
- Categories are defined in `data/intent_categories.csv` and `data/peer_categories.csv`
- Prevents category imbalance from skewing results (e.g., 9 DIY peers vs. 6 electronics peers)

**Example**: A specialist electronics retailer (Kjell) won't be penalized for not competing in building materials, while a generalist (Clas Ohlson) is evaluated across all categories where they compete.

