
# ai-shortlist-screener (ASR/LAR)

A lightweight toolkit to screen peers and estimate AI Shortlist Readiness (ASR) and Likelihood of AI Recommendation (LAR).

## Quickstart
```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .

# Audit
asr audit urls.txt --out audit/asr_report.csv --follow-children 2

# LAR
asr lar audit/asr_report.csv data/soa_log.csv data/distribution.csv data/service.csv --out audit/lar_scores.csv
```
