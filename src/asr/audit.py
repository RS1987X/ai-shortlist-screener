
import csv
from .fetch import fetch_html
from .parse import extract_jsonld, has_server_rendered_jsonld, classify_schema, product_identifiers, has_units
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
    has_policy = any("hasMerchantReturnPolicy" in p or "hasWarrantyPromise" in p for p in buckets["Product"] + buckets["ProductGroup"])

    ident_ok = False
    specs_units = False
    for p in buckets["Product"]:
        ids = product_identifiers(p)
        ident_ok |= bool(ids.get("gtin13") or ids.get("gtin14") or (ids.get("brand") and ids.get("mpn")))
        specs_units |= has_units(p.get("additionalProperty"))

    w = DEFAULT_SCORING.product_weights
    product_score = (
        (w["has_jsonld"] if server_jsonld else 0) +
        (w["has_product"] if has_product or has_service else 0) +
        (w["has_offer"] if has_offer else 0) +
        (w["has_identifiers"] if ident_ok else 0) +
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
        "has_product": int(has_product),
        "has_offer": int(has_offer),
        "identifiers": int(ident_ok),
        "policies": int(has_policy),
        "specs_units": int(specs_units),
        "productgroup": int(has_productgroup),
        "product_score": product_score,
        "family_score": family_score,
    }

def audit_urls(urls, out_csv: str):
    rows = []
    for u in urls:
        u = u.strip()
        if not u:
            continue
        try:
            rows.append(score_url(u))
        except Exception as e:
            rows.append({
                "url": u, "error": str(e),
                "server_jsonld": 0, "has_product": 0, "has_offer": 0,
                "identifiers": 0, "policies": 0, "specs_units": 0,
                "productgroup": 0, "product_score": 0, "family_score": 0
            })
    fieldnames = ["url","server_jsonld","has_product","has_offer","identifiers","policies","specs_units","productgroup","product_score","family_score","error"]
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            if "error" not in r:
                r["error"] = ""
            w.writerow(r)
