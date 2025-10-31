
import csv
from .fetch import fetch_html
from .parse import extract_jsonld, has_server_rendered_jsonld, classify_schema, product_identifiers, has_units, has_policy_links, extract_policy_urls, extract_ratings_fallback
from .js_fallback import extract_with_js
from .config import DEFAULT_SCORING

def score_url(url: str) -> dict:
    html = fetch_html(url)
    server_jsonld = has_server_rendered_jsonld(html)
    items = extract_jsonld(html, url)
    buckets = classify_schema(items)

    has_product = len(buckets["Product"]) > 0
    has_offer = len(buckets["Offer"]) > 0 or any(p.get("offers") for p in buckets["Product"])
    has_productgroup = len(buckets["ProductGroup"]) > 0
    has_service = len(buckets["Service"]) > 0
    
    # Track if we used JS fallback
    js_jsonld = False
    js_items = []

    # Build @id index to resolve references within the same JSON-LD graph
    id_index = {}
    for it in items:
        _id = it.get("@id")
        if isinstance(_id, str):
            id_index[_id] = it

    def _types(it):
        t = it.get("@type")
        if isinstance(t, list):
            return [x for x in t if isinstance(x, str)]
        return [t] if isinstance(t, str) else []

    def _resolve(value):
        """Resolve @id references inside the same page graph; return list of concrete dicts."""
        if value is None:
            return []
        if isinstance(value, list):
            out = []
            for v in value:
                out.extend(_resolve(v))
            return out
        if isinstance(value, dict):
            # If it's a dict with @id that points to another object, resolve; otherwise keep as-is
            ref = value.get("@id")
            if isinstance(ref, str) and ref in id_index:
                return [id_index[ref]]
            return [value]
        if isinstance(value, str) and value in id_index:
            return [id_index[value]]
        return []

    def _has_shipping_details(obj: dict) -> bool:
        # Check Offer.shippingDetails on offers attached to a Product
        offers = obj.get("offers")
        for off in _resolve(offers):
            if isinstance(off, dict) and ("shippingDetails" in off):
                return True
        return False

    def _has_policies(obj: dict) -> bool:
        # Direct policy fields on object
        if "hasMerchantReturnPolicy" in obj or "hasWarrantyPromise" in obj:
            return True
        # Resolve referenced policies
        for key in ("hasMerchantReturnPolicy", "hasWarrantyPromise"):
            for resolved in _resolve(obj.get(key)):
                if isinstance(resolved, dict):
                    return True
        # Offers can carry shipping details (treated as policy-related for X dimension)
        if _has_shipping_details(obj):
            return True
        return False

    # Policy can be on Product/ProductGroup or on Organization in the same page graph
    has_policy_product = any(_has_policies(p) for p in buckets["Product"] + buckets["ProductGroup"])
    # Scan all items for Organization-level defaults
    has_policy_org = any(_has_policies(it) for it in items if "Organization" in _types(it))
    has_policy_structured = has_policy_product or has_policy_org
    
    # Check for policy page links (discoverability, even if not structured)
    has_policy_link = has_policy_links(html)
    
    # Check if policy pages themselves have structured data
    has_policy_structured_on_policy_page = False
    if has_policy_link and not has_policy_structured:
        # Extract policy URLs and check them (limit to first 1 to avoid excessive requests)
        policy_urls = extract_policy_urls(html, url)
        for policy_url in policy_urls[:1]:  # Changed from [:3] to [:1] - only check first policy page
            try:
                # Use shorter timeout for policy pages (5 seconds instead of 15)
                policy_html = fetch_html(policy_url, timeout=5.0)
                policy_items = extract_jsonld(policy_html, policy_url)
                # Check if policy page has MerchantReturnPolicy or WarrantyPromise
                for item in policy_items:
                    item_types = _types(item)
                    if "MerchantReturnPolicy" in item_types or "WarrantyPromise" in item_types:
                        has_policy_structured_on_policy_page = True
                        break
                    # Check if it's an Organization with policies
                    if "Organization" in item_types and _has_policies(item):
                        has_policy_structured_on_policy_page = True
                        break
                if has_policy_structured_on_policy_page:
                    break
            except Exception:
                # Skip policy pages that fail to fetch
                pass
    
    # Combined policy score: structured is best, links are better than nothing
    has_policy = has_policy_structured or has_policy_link or has_policy_structured_on_policy_page

    ident_ok = False
    has_gtin = False
    has_brand_mpn = False
    specs_units = False
    rating_value = None
    rating_count = None
    has_rating = False  # JSON-LD rating presence
    fb_rating_value = None
    fb_rating_count = None
    fb_source = ""
    
    for p in buckets["Product"]:
        ids = product_identifiers(p)
        # Track identifier quality tiers
        # Check both specific (gtin13/14) and generic (gtin) fields
        gtin_present = bool(ids.get("gtin13") or ids.get("gtin14") or ids.get("gtin"))
        brand_mpn_present = bool(ids.get("brand") and ids.get("mpn"))
        has_gtin |= gtin_present
        has_brand_mpn |= (brand_mpn_present and not gtin_present) or (brand_mpn_present and gtin_present)
        ident_ok |= (gtin_present or brand_mpn_present)
        specs_units |= has_units(p.get("additionalProperty"))
        
        # Extract AggregateRating from Product.aggregateRating
        agg_rating = p.get("aggregateRating")
        if agg_rating:
            if isinstance(agg_rating, dict):
                rating_value = agg_rating.get("ratingValue")
                rating_count = agg_rating.get("ratingCount") or agg_rating.get("reviewCount")
                if rating_value is not None:
                    has_rating = True
            elif isinstance(agg_rating, str) and agg_rating in id_index:
                # Resolve @id reference
                resolved = id_index[agg_rating]
                rating_value = resolved.get("ratingValue")
                rating_count = resolved.get("ratingCount") or resolved.get("reviewCount")
                if rating_value is not None:
                    has_rating = True
    
    # Also check standalone AggregateRating entities
    if not has_rating and buckets["AggregateRating"]:
        for ar in buckets["AggregateRating"]:
            rating_value = ar.get("ratingValue")
            rating_count = ar.get("ratingCount") or ar.get("reviewCount")
            if rating_value is not None:
                has_rating = True
                break

    # Fallback A: embedded JSON or inline JS (no JS execution)
    if not has_rating:
        fb = extract_ratings_fallback(html)
        if fb:
            fb_rating_value, fb_rating_count, fb_source = fb

    # Fallback B: JS-rendered content via Playwright (for both JSON-LD and ratings)
    # Only use if: (1) no server JSON-LD OR no product data, AND (2) no ratings found yet
    needs_js_fallback = (not server_jsonld or not has_product) or (not has_rating and not fb_rating_value)
    
    if needs_js_fallback:
        js_result = extract_with_js(url)
        if js_result:
            js_items = js_result['items']
            js_buckets = classify_schema(js_items)
            
            # Update structure flags if we found data via JS
            if not has_product and len(js_buckets["Product"]) > 0:
                has_product = True
                js_jsonld = True
                # Re-process products from JS
                for p in js_buckets["Product"]:
                    ids = product_identifiers(p)
                    gtin_present = bool(ids.get("gtin13") or ids.get("gtin14") or ids.get("gtin"))
                    brand_mpn_present = bool(ids.get("brand") and ids.get("mpn"))
                    has_gtin |= gtin_present
                    has_brand_mpn |= (brand_mpn_present and not gtin_present) or (brand_mpn_present and gtin_present)
                    ident_ok |= (gtin_present or brand_mpn_present)
                    specs_units |= has_units(p.get("additionalProperty"))
            
            if not has_offer and (len(js_buckets["Offer"]) > 0 or any(p.get("offers") for p in js_buckets["Product"])):
                has_offer = True
                js_jsonld = True
            
            # Update ratings from JS if not found yet
            if not has_rating and not fb_rating_value and js_result['rating_value']:
                fb_rating_value = js_result['rating_value']
                fb_rating_count = js_result['rating_count']
                fb_source = js_result['rating_source']

    w = DEFAULT_SCORING.product_weights
    # Identifier term: full credit for GTIN(13/14), discounted for Brand+MPN only
    ident_term = 0
    if has_gtin:
        ident_term = w.get("has_identifiers_gtin", 0)
    elif has_brand_mpn:
        ident_term = w.get("has_identifiers_brand_mpn", 0)

    product_score = (
        (w["has_jsonld"] if server_jsonld else (w["has_jsonld_js"] if js_jsonld else 0)) +
        (w["has_product"] if has_product or has_service else 0) +
        (w["has_offer"] if has_offer else 0) +
        ident_term +
        (w["has_policies"] if has_policy else 0) +
        (w["has_specs_with_units"] if specs_units else 0)
    )

    wf = DEFAULT_SCORING.family_weights
    family_score = 0
    if has_productgroup:
        group = buckets["ProductGroup"][0]
        hasvariant = bool(group.get("hasVariant"))
        links_to_children = hasvariant
        spec_ranges = False
        for ap in group.get("additionalProperty", []) or []:
            v = ap.get("value")
            if isinstance(v, dict) and any(k in v for k in ("minValue","maxValue")):
                spec_ranges = True
                break
        family_score = (
            (wf["has_productgroup"]) +
            (wf["has_hasvariant"] if hasvariant else 0) +
            (wf["links_to_children"] if links_to_children else 0) +
            (wf["policies"] if has_policy else 0) +
            (wf["spec_ranges"] if spec_ranges else 0)
        )

    return {
        "url": url,
        "server_jsonld": int(server_jsonld),
        "js_jsonld": int(js_jsonld),
        "has_product": int(has_product),
        "has_offer": int(has_offer),
    "identifiers": int(ident_ok),
    "ident_gtin": int(has_gtin),
    "ident_brand_mpn": int(has_brand_mpn),
        "policies": int(has_policy),
        "policy_structured": int(has_policy_structured),
        "policy_link": int(has_policy_link),
        "policy_structured_on_policy_page": int(has_policy_structured_on_policy_page),
        "specs_units": int(specs_units),
        "productgroup": int(has_productgroup),
        "product_score": product_score,
        "family_score": family_score,
        # Ratings (JSON-LD primary)
        "has_rating": int(has_rating),
        "rating_value": rating_value if rating_value is not None else "",
        "rating_count": rating_count if rating_count is not None else "",
        # Fallback ratings (embedded/inline)
        "rating_value_fallback": fb_rating_value if fb_rating_value is not None else "",
        "rating_count_fallback": fb_rating_count if fb_rating_count is not None else "",
        "rating_source_fallback": fb_source,
    }

def audit_urls(urls, out_csv: str):
    import sys
    rows = []
    total = len(urls)
    print(f"Found {total} URLs in CSV", flush=True)
    
    for idx, u in enumerate(urls, 1):
        u = u.strip()
        if not u:
            continue
        
        # Progress update every 10 URLs with explicit flush
        if idx % 10 == 0 or idx == total:
            print(f"  [{idx}/{total}] Auditing URLs... ({idx/total*100:.1f}%)", flush=True)
            sys.stdout.flush()  # Force flush for nohup
        
        try:
            rows.append(score_url(u))
        except Exception as e:
            rows.append({
                "url": u, "error": str(e),
                "server_jsonld": 0, "js_jsonld": 0, "has_product": 0, "has_offer": 0,
                "identifiers": 0, "policies": 0, "policy_structured": 0, "policy_link": 0,
                "policy_structured_on_policy_page": 0, "specs_units": 0, 
                "productgroup": 0, "product_score": 0, "family_score": 0,
                "has_rating": 0, "rating_value": "", "rating_count": ""
            })
    fieldnames = [
        "url","server_jsonld","js_jsonld","has_product","has_offer","identifiers","ident_gtin","ident_brand_mpn","policies",
        "policy_structured","policy_link","policy_structured_on_policy_page","specs_units",
        "productgroup","product_score","family_score",
        # Ratings
        "has_rating","rating_value","rating_count",
        "rating_value_fallback","rating_count_fallback","rating_source_fallback",
        "error"
    ]
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            if "error" not in r:
                r["error"] = ""
            w.writerow(r)
