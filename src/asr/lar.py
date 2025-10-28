
import csv
from urllib.parse import urlparse
import statistics as stats
from pathlib import Path
from collections import defaultdict

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

def compute_lar(asr_report_csv: str, soa_csv: str, dist_csv: str, service_csv: str, out_csv: str) -> None:
    # Load category mappings
    intent_cats, peer_cats = _load_category_mappings(asr_report_csv)
    
    # E/X from audit - now organized by domain AND intent
    per_intent = defaultdict(lambda: defaultdict(lambda: {"E": [], "X": []}))
    
    with open(asr_report_csv, encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            url = row["url"]
            k = _root(url)
            e = float(row["product_score"]) * 0.8 + float(row["family_score"]) * 0.2
            x = (int(row.get("policies",0)) + int(row.get("specs_units",0))) * 50
            
            # Try to extract intent_id from URL or use a default key
            # For now, we'll aggregate all URLs per domain
            per_intent[k]["_all"]["E"].append(e)
            per_intent[k]["_all"]["X"].append(x)
    
    # Compute per-domain E/X (simple average for now)
    E, X = {}, {}
    for k, intents in per_intent.items():
        E[k] = stats.mean(intents["_all"]["E"]) if intents["_all"]["E"] else 0.0
        X[k] = stats.mean(intents["_all"]["X"]) if intents["_all"]["X"] else 0.0

    def _load_simple(path):
        d = {}
        with open(path, encoding="utf-8") as f:
            r = csv.DictReader(f)
            for row in r:
                key = row.get("key") or row.get("domain") or row.get("brand")
                d[key] = float(row.get("value") or row.get("score") or row.get("soa") or 0)
        return d

    A = _load_simple(soa_csv)
    D = _load_simple(dist_csv)
    S = _load_simple(service_csv)

    # Match domain keys to brand names for category lookup
    def _find_brand_for_domain(domain):
        """Map domain to brand name from peer_categories.csv"""
        domain_lower = domain.lower()
        for brand in peer_cats.keys():
            if brand.lower().replace(" ", "") in domain_lower.replace(".", "").replace("-", ""):
                return brand
        return None

    out_rows = []
    keys = set(E) | set(A) | set(D) | set(S)
    for k in sorted(keys):
        e = E.get(k, 0.0)
        x = X.get(k, 0.0)
        a = A.get(k, 0.0)
        d = D.get(k, 0.0)
        s = S.get(k, 0.0)

        # Standard LAR calculation (can be enhanced with category weighting in future)
        lar = 0.30*e + 0.20*x + 0.25*a + 0.15*d + 0.10*s
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
            "D": d,
            "S": s,
            "LAR": round(lar,2)
        })

    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["key","brand","categories","E","X","A","D","S","LAR"])
        w.writeheader()
        for r in out_rows:
            w.writerow(r)


def compute_category_weighted_lar(
    asr_report_csv: str,
    soa_csv: str,
    dist_csv: str,
    service_csv: str,
    out_csv: str,
    intent_log_csv: str = None
) -> None:
    """
    Compute LAR with category weighting to handle peer category imbalance.
    
    Each peer's LAR is computed as the average of their category-level scores,
    giving equal weight to each category they compete in (not each intent).
    
    Args:
        asr_report_csv: Audit report with E/X scores per URL
        soa_csv: Share-of-answer scores by brand/domain
        dist_csv: Distribution coherence scores by brand/domain
        service_csv: Service/actionability scores by brand/domain
        out_csv: Output file for weighted LAR scores
        intent_log_csv: Optional intent-level results for per-category A computation
    """
    # Load category mappings
    intent_cats, peer_cats = _load_category_mappings(asr_report_csv)
    
    # E/X from audit - organize by domain and intent
    per_domain_intent = defaultdict(lambda: defaultdict(lambda: {"E": [], "X": []}))
    
    with open(asr_report_csv, encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            url = row["url"]
            domain = _root(url)
            e = float(row["product_score"]) * 0.8 + float(row["family_score"]) * 0.2
            x = (int(row.get("policies", 0)) + int(row.get("specs_units", 0))) * 50
            
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
    
    for domain, categories in domain_category_scores.items():
        for category, scores in categories.items():
            E_by_cat[domain][category] = stats.mean(scores["E"]) if scores["E"] else 0.0
            X_by_cat[domain][category] = stats.mean(scores["X"]) if scores["X"] else 0.0
    
    # Load A/D/S (these are overall, not per-category for now)
    def _load_simple(path):
        d = {}
        with open(path, encoding="utf-8") as f:
            r = csv.DictReader(f)
            for row in r:
                key = row.get("key") or row.get("domain") or row.get("brand")
                d[key] = float(row.get("value") or row.get("score") or row.get("soa") or 0)
        return d
    
    A = _load_simple(soa_csv)
    D = _load_simple(dist_csv)
    S = _load_simple(service_csv)
    
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
    all_domains = set(E_by_cat.keys()) | set(A.keys()) | set(D.keys()) | set(S.keys())
    
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
            d_cat = D.get(domain, 0.0)
            s_cat = S.get(domain, 0.0)
            
            lar_cat = 0.30 * e_cat + 0.20 * x_cat + 0.25 * a_cat + 0.15 * d_cat + 0.10 * s_cat
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
            d_val = D.get(domain, 0.0)
            s_val = S.get(domain, 0.0)
            weighted_lar = 0.30 * overall_e + 0.20 * overall_x + 0.25 * a_val + 0.15 * d_val + 0.10 * s_val
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
            "D": D.get(domain, 0.0),
            "S": S.get(domain, 0.0),
            "LAR_weighted": round(weighted_lar, 2),
            "category_details": str(category_details)
        })
    
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=[
            "key", "brand", "categories", "num_categories",
            "E", "X", "A", "D", "S", "LAR_weighted", "category_details"
        ])
        w.writeheader()
        for r in out_rows:
            w.writerow(r)
