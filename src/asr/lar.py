
import csv
from urllib.parse import urlparse
import statistics as stats
from pathlib import Path
from collections import defaultdict

from .config import RATING_CONFIDENCE_THRESHOLD, FALLBACK_RATING_WEIGHT, RATING_NEUTRAL_POINT, RATING_SCALE_RANGE


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
    # Attribution accumulators per domain
    attrib = defaultdict(lambda: {
        # E components
        "product_scores": [],
        "family_scores": [],
        # X components (per-URL points and binary flags)
        "x_policy_points": [],
        "x_specs_points": [],
        "policy_structured": 0,
        "policy_structured_on_policy_page": 0,
        "policy_link": 0,
        "specs_units": 0,
        "total_urls": 0,
        # S components (raw and factors)
        "raw_ratings": [],
        "rating_counts": [],
        "confidences": [],
        "source_weights": [],
        "fallback_used": 0,
        "ratings_seen": 0,
    })
    
    with open(asr_report_csv, encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            url = row["url"]
            k = _root(url)
            # Track E components
            product_score = float(row["product_score"]) if row.get("product_score") not in (None, "") else 0.0
            family_score = float(row["family_score"]) if row.get("family_score") not in (None, "") else 0.0
            attrib[k]["product_scores"].append(product_score)
            attrib[k]["family_scores"].append(family_score)
            e = product_score * 0.8 + family_score * 0.2
            
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

            # Track X components and flags
            attrib[k]["x_policy_points"].append(x_policy)
            attrib[k]["x_specs_points"].append(x_specs)
            attrib[k]["policy_structured"] += 1 if policy_structured else 0
            attrib[k]["policy_structured_on_policy_page"] += 1 if policy_structured_on_policy_page else 0
            attrib[k]["policy_link"] += 1 if policy_link else 0
            attrib[k]["specs_units"] += 1 if specs_units else 0
            attrib[k]["total_urls"] += 1
            
            # Extract rating if present (normalize to 0-100 scale, assuming 5-star max)
            # Prefer JSON-LD rating; if missing, use fallback with reduced weight
            rating_value = (row.get("rating_value", "") or "").strip()
            rating_count = (row.get("rating_count", "") or "").strip()
            rating_source_weight = 1.0
            if not rating_value:
                rating_value = (row.get("rating_value_fallback", "") or "").strip()
                rating_count = (row.get("rating_count_fallback", "") or "").strip()
                if rating_value:
                    rating_source_weight = FALLBACK_RATING_WEIGHT
                    attrib[k]["fallback_used"] += 1
            if rating_value:
                try:
                    rating_float = float(rating_value)
                    # Apply confidence weighting based on review count
                    # Ratings with fewer reviews are less reliable (statistical uncertainty)
                    confidence = 1.0  # Default: full confidence
                    if rating_count:
                        try:
                            count = int(rating_count)
                            # Confidence scales linearly from 0 to 1.0 as reviews increase
                            # Full confidence reached at RATING_CONFIDENCE_THRESHOLD reviews
                            confidence = min(1.0, count / RATING_CONFIDENCE_THRESHOLD)
                            attrib[k]["rating_counts"].append(count)
                        except ValueError:
                            pass  # If count invalid, use full confidence (conservative)
                    
                    # CENTERED SCORING: 3.5/5 is the neutral point (S=0)
                    # Formula: S = ((rating - 3.5) / 1.5) * 100
                    # This creates active avoidance of poor ratings (<3.5) and rewards good ratings (>3.5)
                    # Range: -100 (terrible 2.0/5) to +100 (perfect 5.0/5)
                    rating_normalized = ((rating_float - RATING_NEUTRAL_POINT) / RATING_SCALE_RANGE) * 100 * confidence * rating_source_weight
                    per_intent[k]["_all"]["ratings"].append(rating_normalized)
                    # Track S components
                    attrib[k]["raw_ratings"].append(rating_float)
                    attrib[k]["confidences"].append(confidence)
                    attrib[k]["source_weights"].append(rating_source_weight)
                    attrib[k]["ratings_seen"] += 1
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
    attrib_rows = []
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

        # Build attribution row
        at = attrib.get(k, None)
        total_urls = (at or {}).get("total_urls", 0)
        # E components
        e_prod_avg = round(stats.mean(at["product_scores"]) if at and at["product_scores"] else 0.0, 2)
        e_fam_avg = round(stats.mean(at["family_scores"]) if at and at["family_scores"] else 0.0, 2)
        e_contrib = round(0.40 * e, 2)
        # X components
        x_policy_avg = round(stats.mean(at["x_policy_points"]) if at and at["x_policy_points"] else 0.0, 2)
        x_specs_avg = round(stats.mean(at["x_specs_points"]) if at and at["x_specs_points"] else 0.0, 2)
        policy_structured_rate = round(((at["policy_structured"]) / total_urls), 3) if at and total_urls else 0.0
        policy_structured_on_policy_page_rate = round(((at["policy_structured_on_policy_page"]) / total_urls), 3) if at and total_urls else 0.0
        policy_link_rate = round(((at["policy_link"]) / total_urls), 3) if at and total_urls else 0.0
        specs_units_rate = round(((at["specs_units"]) / total_urls), 3) if at and total_urls else 0.0
        x_contrib = round(0.25 * x, 2)
        # S components
        s_source = "manual" if (k in S_manual) else "audit"
        raw_rating_avg = round(stats.mean(at["raw_ratings"]) if at and at["raw_ratings"] else 0.0, 3)
        rating_count_avg = round(stats.mean(at["rating_counts"]) if at and at["rating_counts"] else 0.0, 2)
        confidence_avg = round(stats.mean(at["confidences"]) if at and at["confidences"] else 0.0, 3)
        source_weight_avg = round(stats.mean(at["source_weights"]) if at and at["source_weights"] else 0.0, 3)
        fallback_share = round(((at["fallback_used"]) / at["ratings_seen"]) , 3) if at and at["ratings_seen"] else 0.0
        s_contrib = round(0.10 * s, 2)
        # A contribution
        a_contrib = round(0.25 * a, 2)

        attrib_rows.append({
            "key": k,
            "brand": brand or k,
            "categories": categories,
            # Overall
            "LAR": round(lar, 2),
            # E breakdown
            "E": round(e, 2),
            "E_contrib": e_contrib,
            "E_product_avg": e_prod_avg,
            "E_family_avg": e_fam_avg,
            # X breakdown
            "X": round(x, 2),
            "X_contrib": x_contrib,
            "X_policy_points_avg": x_policy_avg,
            "X_specs_points_avg": x_specs_avg,
            "policy_structured_rate": policy_structured_rate,
            "policy_structured_on_policy_page_rate": policy_structured_on_policy_page_rate,
            "policy_link_rate": policy_link_rate,
            "specs_units_rate": specs_units_rate,
            # A breakdown
            "A": a,
            "A_contrib": a_contrib,
            # S breakdown
            "S": s,
            "S_contrib": s_contrib,
            "S_source": s_source,
            "S_raw_rating_avg": raw_rating_avg,
            "S_rating_count_avg": rating_count_avg,
            "S_confidence_avg": confidence_avg,
            "S_source_weight_avg": source_weight_avg,
            "S_fallback_share": fallback_share,
            # Volume context
            "url_count": total_urls,
            "ratings_seen": (at or {}).get("ratings_seen", 0)
        })

    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["key","brand","categories","E","X","A","S","LAR"])
        w.writeheader()
        for r in out_rows:
            w.writerow(r)

    # Write attribution CSV next to main output with human-friendly column names
    attrib_path = str(Path(out_csv).with_name(Path(out_csv).stem + "_attribution.csv"))
    with open(attrib_path, "w", newline="", encoding="utf-8") as f:
        # Map internal keys -> readable column headers
        readable = [
            ("key", "Domain"),
            ("brand", "Brand"),
            ("categories", "Categories"),
            ("LAR", "LAR"),
            # E (Eligibility)
            ("E", "E (Eligibility)"),
            ("E_contrib", "E contribution to LAR"),
            ("E_product_avg", "E: product score avg"),
            ("E_family_avg", "E: family score avg"),
            # X (eXtensibility / eXtended attributes)
            ("X", "X (eXtensibility)"),
            ("X_contrib", "X contribution to LAR"),
            ("X_policy_points_avg", "X: policy points avg"),
            ("X_specs_points_avg", "X: specs points avg"),
            ("policy_structured_rate", "Policy structured on PDP rate"),
            ("policy_structured_on_policy_page_rate", "Policy structured on policy page rate"),
            ("policy_link_rate", "Policy link only rate"),
            ("specs_units_rate", "Specs with units rate"),
            # A (Availability / Share of Answer)
            ("A", "A (Share of Answer)"),
            ("A_contrib", "A contribution to LAR"),
            # S (Sentiment / Service)
            ("S", "S (Sentiment)"),
            ("S_contrib", "S contribution to LAR"),
            ("S_source", "S: source"),
            ("S_raw_rating_avg", "S: average star rating"),
            ("S_rating_count_avg", "S: average rating count"),
            ("S_confidence_avg", "S: average confidence"),
            ("S_source_weight_avg", "S: average source weight"),
            ("S_fallback_share", "S: fallback share"),
            # Volume context
            ("url_count", "URLs audited"),
            ("ratings_seen", "Ratings found"),
        ]

        fieldnames = [human for _key, human in readable]
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in attrib_rows:
            # Remap row keys to human-friendly headers
            out_row = {human: r.get(key, "") for key, human in readable}
            w.writerow(out_row)


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
            rating_count = (row.get("rating_count", "") or "").strip()
            rating_source_weight = 1.0
            if not rating_value:
                rating_value = (row.get("rating_value_fallback", "") or "").strip()
                rating_count = (row.get("rating_count_fallback", "") or "").strip()
                if rating_value:
                    rating_source_weight = FALLBACK_RATING_WEIGHT
            if rating_value:
                try:
                    rating_float = float(rating_value)
                    # Apply confidence weighting based on review count
                    confidence = 1.0  # Default: full confidence
                    if rating_count:
                        try:
                            count = int(rating_count)
                            confidence = min(1.0, count / RATING_CONFIDENCE_THRESHOLD)
                        except ValueError:
                            pass  # If count invalid, use full confidence (conservative)
                    
                    # CENTERED SCORING: 3.5/5 is the neutral point (S=0)
                    rating_normalized = ((rating_float - RATING_NEUTRAL_POINT) / RATING_SCALE_RANGE) * 100 * confidence * rating_source_weight
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
