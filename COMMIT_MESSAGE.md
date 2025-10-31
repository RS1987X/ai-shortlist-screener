# Commit Message for Current Changes

```
feat: Add JS fallback, fix GTIN detection, implement tiered identifiers

Major improvements to audit accuracy and scoring sophistication:

1. JS Fallback for Client-Side Rendered Content
   - Implement single-pass Playwright-based fallback for CSR sites
   - Extract JSON-LD + ratings in one browser render (efficient)
   - Add has_jsonld_js scoring (15pts vs 20pts for server-rendered)
   - Increases accuracy: Biltema +56pts, Byggmax +28pts
   - Add js_jsonld transparency flag to CSV output

2. Fix Generic GTIN Field Detection Bug
   - Add extraction of generic 'gtin' field (was only checking gtin13/14)
   - Update scoring to check: gtin OR gtin13 OR gtin14
   - Impact: GTIN adoption 50% (was 0% due to bug)
   - NetOnNet and Elgiganten now correctly credited

3. Implement Tiered Identifier Scoring
   - GTIN (has_identifiers_gtin): 20pts (enables exact matching)
   - Brand+MPN (has_identifiers_brand_mpn): 12pts (requires fuzzy)
   - Add ident_gtin, ident_brand_mpn CSV columns for transparency
   - Reflects real-world cross-retailer matching capability

4. Documentation Updates
   - docs/updates.md: Comprehensive changelog with rationale
   - docs/scoring.md: Updated with new weights and logic
   - docs/validation.md: 5/5 samples validated (100% accuracy)

5. Validation Results
   - NetOnNet: E=68.0 accurate (server-rendered, GTIN present)
   - Hornbach: E=68.0 accurate (server-rendered)
   - Biltema: E=64.0 improved from 8.0 (JS fallback captured data)
   - Byggmax: E=52.0 improved from 24.0 (JS fallback)
   - All score changes reflect improvements, not errors

Files modified:
- src/asr/parse.py: Add generic gtin extraction
- src/asr/audit.py: JS fallback integration, tiered identifiers
- src/asr/config.py: New weight structure (gtin/brand_mpn split)
- src/asr/js_fallback.py: Efficient single-pass extraction
- docs/updates.md: Comprehensive changelog
- docs/scoring.md: Updated methodology
- docs/validation.md: Test results and accuracy confirmation

Breaking changes: None (maintains backward compatibility)
```

## Git Commands to Run

```bash
# Review changes
git status
git diff

# Stage all changes
git add src/asr/parse.py src/asr/audit.py src/asr/config.py src/asr/js_fallback.py
git add docs/updates.md docs/scoring.md docs/validation.md

# Commit with detailed message
git commit -F COMMIT_MESSAGE.md

# (Optional) Tag this version
git tag -a v1.1.0 -m "JS fallback, GTIN fix, tiered identifiers"
```
