
import csv
from urllib.parse import urlparse
import statistics as stats
from pathlib import Path
from collections import defaultdict

# Weight applied to ratings derived from fallback (embedded/inline) sources.
# JSON-LD ratings get full weight (1.0). Fallback ratings are discounted.
FALLBACK_RATING_WEIGHT = 0.7

def _root(url: str) -> str:
    return urlparse(url).netloc

def _load_category_mappings(base_path: str):
    """Load intent-to-category and peer-to-category mappings."""
    data_dir = Path(base_path).parent.parent / "data"
    
    # Load intent categories
    intent_cats = {}
    intent_cat_file = data_dir / "intent_categories.csv"
    if intent_cat_file.exists():
        with open(intent_cat_file, encoding="utf-8") as f:
            r = csv.DictReader(f)
            for row in r:
                intent_cats[row["intent_id"]] = row["category"]
    
    # Load peer categories (which categories each peer competes in)
    peer_cats = {}
    peer_cat_file = data_dir / "peer_categories.csv"
    if peer_cat_file.exists():
        with open(peer_cat_file, encoding="utf-8") as f:
            r = csv.DictReader(f)
            for row in r:
                brand = row["brand"]
                # Get categories where this peer has value 1
                categories = [cat for cat in row.keys() if cat != "brand" and row[cat] == "1"]
                peer_cats[brand] = set(categories)
    
    return intent_cats, peer_cats

def compute_lar(asr_report_csv: str, soa_csv: str, service_csv: str = None, out_csv: str = "lar.csv") -> None:
    """
    Compute LAR scores from audit and supplementary data.
    
    LAR = 0.40·E + 0.25·X + 0.25·A + 0.10·S
    
    S dimension can be computed from:
    - Audit data: AggregateRating from product pages (auto-computed)
    - service_csv: Manual override for retailers (optional)
    
    Note: D (Distribution) dimension has been removed as it's not applicable to 
    third-party retailers selling through own channels. See methodology.md for details.
    """
    # Load category mappings
    intent_cats, peer_cats = _load_category_mappings(asr_report_csv)
    
    # E/X from audit - now organized by domain AND intent
    per_intent = defaultdict(lambda: defaultdict(lambda: {"E": [], "X": [], "ratings": []}))
    
    with open(asr_report_csv, encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            url = row["url"]
            k = _root(url)
            e = float(row["product_score"]) * 0.8 + float(row["family_score"]) * 0.2
            
            # X dimension: structured policies get full credit, policy page structured gets good credit, links get partial
            policy_structured = int(row.get("policy_structured", 0))
            policy_structured_on_policy_page = int(row.get("policy_structured_on_policy_page", 0))
            policy_link = int(row.get("policy_link", 0))
            specs_units = int(row.get("specs_units", 0))
            
            # Scoring: structured on product page = 50 points, structured on policy page = 40 points, links only = 25 points, specs = 50 points
            if policy_structured:
                x_policy = 50
            elif policy_structured_on_policy_page:
                x_policy = 40
            elif policy_link:
                x_policy = 25
            else:
                x_policy = 0
            
            x_specs = 50 if specs_units else 0
            x = x_policy + x_specs
            
            # Extract rating if present (normalize to 0-100 scale, assuming 5-star max)
            # Prefer JSON-LD rating; if missing, use fallback with reduced weight
            rating_value = (row.get("rating_value", "") or "").strip()
            rating_source_weight = 1.0
            if not rating_value:
                rating_value = (row.get("rating_value_fallback", "") or "").strip()
                if rating_value:
                    rating_source_weight = FALLBACK_RATING_WEIGHT
            if rating_value:
                try:
                    rating_float = float(rating_value)
                    # Normalize to 0-100 (assuming 5-star scale)
                    rating_normalized = (rating_float / 5.0) * 100 * rating_source_weight
                    per_intent[k]["_all"]["ratings"].append(rating_normalized)
                except ValueError:
                    pass
            
            # Try to extract intent_id from URL or use a default key
            # For now, we'll aggregate all URLs per domain
            per_intent[k]["_all"]["E"].append(e)
            per_intent[k]["_all"]["X"].append(x)
    
    # Compute per-domain E/X (simple average for now)
    E, X = {}, {}
    S_from_audit = {}
    for k, intents in per_intent.items():
        E[k] = stats.mean(intents["_all"]["E"]) if intents["_all"]["E"] else 0.0
        X[k] = stats.mean(intents["_all"]["X"]) if intents["_all"]["X"] else 0.0
        # Compute S from audit ratings (average of all product ratings for this domain)
        if intents["_all"]["ratings"]:
            S_from_audit[k] = stats.mean(intents["_all"]["ratings"])
        else:
            S_from_audit[k] = 0.0

    def _load_simple(path):
        d = {}
        with open(path, encoding="utf-8") as f:
            r = csv.DictReader(f)
            for row in r:
                key = row.get("key") or row.get("domain") or row.get("brand")
                d[key] = float(row.get("value") or row.get("score") or row.get("soa") or 0)
        return d

    A = _load_simple(soa_csv)
    
    # S: Use manual service.csv if provided, otherwise use audit ratings
    if service_csv:
        S_manual = _load_simple(service_csv)
    else:
        S_manual = {}
    
    # Merge S scores: manual overrides auto-computed
    S = {}
    all_domains = set(E.keys()) | set(S_from_audit.keys()) | set(S_manual.keys())
    for domain in all_domains:
        if domain in S_manual:
            S[domain] = S_manual[domain]  # Manual override
        else:
            S[domain] = S_from_audit.get(domain, 0.0)  # Auto-computed from audit

    # Match domain keys to brand names for category lookup
    def _find_brand_for_domain(domain):
        """Map domain to brand name from peer_categories.csv"""
        domain_lower = domain.lower()
        for brand in peer_cats.keys():
            if brand.lower().replace(" ", "") in domain_lower.replace(".", "").replace("-", ""):
                return brand
        return None

    out_rows = []
    keys = set(E) | set(A) | set(S)
    for k in sorted(keys):
        e = E.get(k, 0.0)
        x = X.get(k, 0.0)
        a = A.get(k, 0.0)
        s = S.get(k, 0.0)

        # LAR calculation: E·X·A·S (D dimension removed)
        lar = 0.40*e + 0.25*x + 0.25*a + 0.10*s
        if e < 60:
            lar = min(lar, 40.0)
        
        # Find brand for category info
        brand = _find_brand_for_domain(k)
        categories = ",".join(sorted(peer_cats.get(brand, []))) if brand else ""
        
        out_rows.append({
            "key": k,
            "brand": brand or k,
            "categories": categories,
            "E": round(e,2),
            "X": round(x,2),
            "A": a,
            "S": s,
            "LAR": round(lar,2)
        })

    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["key","brand","categories","E","X","A","S","LAR"])
        w.writeheader()
        for r in out_rows:
            w.writerow(r)


def compute_category_weighted_lar(
    asr_report_csv: str,
    soa_csv: str,
    service_csv: str = None,
    out_csv: str = "lar_weighted.csv",
    intent_log_csv: str = None
) -> None:
    """
    Compute LAR with category weighting to handle peer category imbalance.
    
    LAR = 0.40·E + 0.25·X + 0.25·A + 0.10·S
    
    Each peer LAR is computed as the average of their category-level scores,
    giving equal weight to each category they compete in (not each intent).
    
    Args:
        asr_report_csv: Audit report with E/X scores per URL
        soa_csv: Share-of-answer scores by brand/domain
        service_csv: Optional service/satisfaction scores by brand/domain (if not provided, computed from audit)
        out_csv: Output file for weighted LAR scores
        intent_log_csv: Optional intent-level results for per-category A computation
    
    S dimension can be computed from:
    - Audit data: AggregateRating from product pages (auto-computed)
    - service_csv: Manual override for retailers (optional)
    
    Note: D (Distribution) dimension has been removed. See methodology.md for details.
    """
    # Load category mappings
    intent_cats, peer_cats = _load_category_mappings(asr_report_csv)
    
    # E/X from audit - organize by domain and intent
    per_domain_intent = defaultdict(lambda: defaultdict(lambda: {"E": [], "X": [], "ratings": []}))
    
    with open(asr_report_csv, encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            url = row["url"]
            domain = _root(url)
            e = float(row["product_score"]) * 0.8 + float(row["family_score"]) * 0.2
            
            # X dimension: structured policies get full credit, policy page structured gets good credit, links get partial
            policy_structured = int(row.get("policy_structured", 0))
            policy_structured_on_policy_page = int(row.get("policy_structured_on_policy_page", 0))
            policy_link = int(row.get("policy_link", 0))
            specs_units = int(row.get("specs_units", 0))
            
            # Scoring: structured on product page = 50 points, structured on policy page = 40 points, links only = 25 points, specs = 50 points
            if policy_structured:
                x_policy = 50
            elif policy_structured_on_policy_page:
                x_policy = 40
            elif policy_link:
                x_policy = 25
            else:
                x_policy = 0
            
            x_specs = 50 if specs_units else 0
            x = x_policy + x_specs
            
            # Extract rating if present (normalize to 0-100 scale, assuming 5-star max)
            # Prefer JSON-LD rating; if missing, use fallback with reduced weight
            rating_value = (row.get("rating_value", "") or "").strip()
            rating_source_weight = 1.0
            if not rating_value:
                rating_value = (row.get("rating_value_fallback", "") or "").strip()
                if rating_value:
                    rating_source_weight = FALLBACK_RATING_WEIGHT
            if rating_value:
                try:
                    rating_float = float(rating_value)
                    rating_normalized = (rating_float / 5.0) * 100 * rating_source_weight
                    intent_id = row.get("intent_id", "_all")
                    per_domain_intent[domain][intent_id]["ratings"].append(rating_normalized)
                except ValueError:
                    pass
            
            # Extract intent_id if available in the row, otherwise use "_all"
            intent_id = row.get("intent_id", "_all")
            per_domain_intent[domain][intent_id]["E"].append(e)
            per_domain_intent[domain][intent_id]["X"].append(x)
    
    # Compute per-domain, per-category E/X
    domain_category_scores = defaultdict(lambda: defaultdict(lambda: {"E": [], "X": []}))
    
    for domain, intents in per_domain_intent.items():
        for intent_id, scores in intents.items():
            if intent_id == "_all":
                # Fallback: if no intent mapping, use all scores
                category = "General"
            else:
                category = intent_cats.get(intent_id, "General")
            
            if scores["E"]:
                domain_category_scores[domain][category]["E"].extend(scores["E"])
            if scores["X"]:
                domain_category_scores[domain][category]["X"].extend(scores["X"])
    
    # Average E/X per domain per category
    E_by_cat = defaultdict(dict)
    X_by_cat = defaultdict(dict)
    S_from_audit = {}
    
    for domain, categories in domain_category_scores.items():
        for category, scores in categories.items():
            E_by_cat[domain][category] = stats.mean(scores["E"]) if scores["E"] else 0.0
            X_by_cat[domain][category] = stats.mean(scores["X"]) if scores["X"] else 0.0
    
    # Compute S from all audit ratings per domain (not per-category)
    for domain, intents in per_domain_intent.items():
        all_ratings = []
        for intent_id, scores in intents.items():
            all_ratings.extend(scores["ratings"])
        if all_ratings:
            S_from_audit[domain] = stats.mean(all_ratings)
        else:
            S_from_audit[domain] = 0.0
    
    # Load A/S (these are overall, not per-category for now)
    def _load_simple(path):
        d = {}
        with open(path, encoding="utf-8") as f:
            r = csv.DictReader(f)
            for row in r:
                key = row.get("key") or row.get("domain") or row.get("brand")
                d[key] = float(row.get("value") or row.get("score") or row.get("soa") or 0)
        return d
    
    A = _load_simple(soa_csv)
    
    # S: Use manual service.csv if provided, otherwise use audit ratings
    if service_csv:
        S_manual = _load_simple(service_csv)
    else:
        S_manual = {}
    
    # Merge S scores: manual overrides auto-computed
    S = {}
    all_domains = set(E_by_cat.keys()) | set(S_from_audit.keys()) | set(S_manual.keys())
    for domain in all_domains:
        if domain in S_manual:
            S[domain] = S_manual[domain]  # Manual override
        else:
            S[domain] = S_from_audit.get(domain, 0.0)  # Auto-computed from audit
    
    # Match domains to brands
    def _find_brand_for_domain(domain):
        """Map domain to brand name from peer_categories.csv"""
        domain_lower = domain.lower()
        for brand in peer_cats.keys():
            if brand.lower().replace(" ", "") in domain_lower.replace(".", "").replace("-", ""):
                return brand
        return None
    
    # Compute category-weighted LAR for each peer
    out_rows = []
    all_domains = set(E_by_cat.keys()) | set(A.keys()) | set(S.keys())
    
    for domain in sorted(all_domains):
        brand = _find_brand_for_domain(domain)
        eligible_cats = peer_cats.get(brand, set()) if brand else set()
        
        # Compute LAR per category where peer competes
        category_lars = {}
        category_details = {}
        
        for category in eligible_cats:
            e_cat = E_by_cat.get(domain, {}).get(category, 0.0)
            x_cat = X_by_cat.get(domain, {}).get(category, 0.0)
            a_cat = A.get(domain, 0.0)  # TODO: make A per-category if intent log available
            s_cat = S.get(domain, 0.0)
            
            lar_cat = 0.40 * e_cat + 0.25 * x_cat + 0.25 * a_cat + 0.10 * s_cat
            if e_cat < 60:
                lar_cat = min(lar_cat, 40.0)
            
            category_lars[category] = lar_cat
            category_details[category] = {
                "E": round(e_cat, 2),
                "X": round(x_cat, 2),
                "LAR": round(lar_cat, 2)
            }
        
        # Overall weighted LAR = mean of category LARs
        if category_lars:
            weighted_lar = stats.mean(category_lars.values())
            overall_e = stats.mean([category_details[c]["E"] for c in category_lars.keys()])
            overall_x = stats.mean([category_details[c]["X"] for c in category_lars.keys()])
        else:
            # Fallback: no category mapping, use overall scores
            overall_e = stats.mean([v for cat_scores in E_by_cat.get(domain, {}).values() for v in [cat_scores]]) if E_by_cat.get(domain) else 0.0
            overall_x = stats.mean([v for cat_scores in X_by_cat.get(domain, {}).values() for v in [cat_scores]]) if X_by_cat.get(domain) else 0.0
            a_val = A.get(domain, 0.0)
            s_val = S.get(domain, 0.0)
            weighted_lar = 0.40 * overall_e + 0.25 * overall_x + 0.25 * a_val + 0.10 * s_val
            if overall_e < 60:
                weighted_lar = min(weighted_lar, 40.0)
        
        out_rows.append({
            "key": domain,
            "brand": brand or domain,
            "categories": ",".join(sorted(eligible_cats)) if eligible_cats else "none",
            "num_categories": len(eligible_cats),
            "E": round(overall_e, 2),
            "X": round(overall_x, 2),
            "A": A.get(domain, 0.0),
            "S": S.get(domain, 0.0),
            "LAR_weighted": round(weighted_lar, 2),
            "category_details": str(category_details)
        })
    
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=[
            "key", "brand", "categories", "num_categories",
            "E", "X", "A", "S", "LAR_weighted", "category_details"
        ])
        w.writeheader()
        for r in out_rows:
            w.writerow(r)
