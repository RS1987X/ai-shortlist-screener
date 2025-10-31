from typing import Optional, Tuple, Dict, List, Any

from playwright.sync_api import sync_playwright
import extruct
from w3lib.html import get_base_url

from .parse import extract_jsonld, classify_schema
from .parse import extract_ratings_fallback as extract_fallback_from_html

# Efficient JS-rendering fallback that extracts both JSON-LD structure and ratings in one pass.
# Strategy:
# 1) Render page with Playwright (Chromium), wait for network idle
# 2) Extract complete JSON-LD structure (Product, Offer, identifiers, specs)
# 3) Extract ratings from JSON-LD or fallback sources
# 4) Return both structured data AND ratings in single result
# This avoids double JS execution for the same page.

def _extract_from_items(items) -> Optional[Tuple[str, str]]:
    """
    Extract ratings from JSON-LD items.
    Returns (rating_value, rating_count) or None.
    """
    # Buckets for convenience
    buckets = {"Product": [], "AggregateRating": []}
    for it in items:
        t = it.get("@type")
        if isinstance(t, list):
            t = next((x for x in t if isinstance(x, str)), None)
        if not isinstance(t, str):
            continue
        if t == "Product":
            buckets["Product"].append(it)
        elif t == "AggregateRating":
            buckets["AggregateRating"].append(it)

    # Build @id index to resolve references
    id_index = {}
    for it in items:
        _id = it.get("@id")
        if isinstance(_id, str):
            id_index[_id] = it

    def _resolve(value):
        if value is None:
            return []
        if isinstance(value, list):
            out = []
            for v in value:
                out.extend(_resolve(v))
            return out
        if isinstance(value, dict):
            ref = value.get("@id")
            if isinstance(ref, str) and ref in id_index:
                return [id_index[ref]]
            return [value]
        if isinstance(value, str) and value in id_index:
            return [id_index[value]]
        return []

    # Product.aggregateRating
    for p in buckets["Product"]:
        agg = p.get("aggregateRating")
        for ar in _resolve(agg) or []:
            if isinstance(ar, dict):
                rv = ar.get("ratingValue")
                rc = ar.get("ratingCount") or ar.get("reviewCount")
                if rv is not None:
                    return str(rv), str(rc or "")

    # Standalone AggregateRating
    for ar in buckets["AggregateRating"]:
        rv = ar.get("ratingValue")
        rc = ar.get("ratingCount") or ar.get("reviewCount")
        if rv is not None:
            return str(rv), str(rc or "")

    return None


def extract_with_js(url: str, timeout_ms: int = 20000) -> Optional[Dict[str, Any]]:
    """
    Extract both JSON-LD structure and ratings using JS rendering.
    Returns a dict with:
    {
        'html': str,                    # Rendered HTML
        'items': List[dict],            # JSON-LD items (Product, Offer, etc.)
        'rating_value': str or None,    # Rating value (e.g., "4.2")
        'rating_count': str or None,    # Rating count (e.g., "156")
        'rating_source': str            # Source of rating ("jsonld-js", "embedded-js", etc.)
    }
    Returns None if page fails to load.
    """
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                )
            )
            page = context.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
            try:
                page.wait_for_load_state("networkidle", timeout=timeout_ms)
            except Exception:
                # If networkidle never comes, proceed with current DOM
                pass
            html = page.content()
            browser.close()
    except Exception:
        return None

    # Extract JSON-LD from rendered HTML
    items = extract_jsonld(html, url)
    
    # Extract ratings from JSON-LD
    rating_result = _extract_from_items(items)
    if rating_result:
        rating_value, rating_count = rating_result
        return {
            'html': html,
            'items': items,
            'rating_value': rating_value,
            'rating_count': rating_count,
            'rating_source': 'jsonld-js'
        }
    
    # Fallback: embedded JSON in rendered HTML
    fb = extract_fallback_from_html(html)
    if fb:
        fb_rating_value, fb_rating_count, fb_source = fb
        return {
            'html': html,
            'items': items,
            'rating_value': fb_rating_value,
            'rating_count': fb_rating_count,
            'rating_source': f'{fb_source}-js'
        }
    
    # Fallback: Microdata/RDFa
    try:
        base_url = get_base_url(html, url)
        all_data = extruct.extract(html, base_url=base_url, errors="ignore")
        
        for fmt in ["microdata", "rdfa"]:
            for item in all_data.get(fmt, []) or []:
                t = item.get("type", "")
                if "AggregateRating" in t or "Rating" in t:
                    props = item.get("properties", {})
                    rv = props.get("ratingValue", [None])[0] if isinstance(props.get("ratingValue"), list) else props.get("ratingValue")
                    rc = props.get("ratingCount", [None])[0] if isinstance(props.get("ratingCount"), list) else props.get("ratingCount")
                    if rv is not None:
                        return {
                            'html': html,
                            'items': items,
                            'rating_value': str(rv),
                            'rating_count': str(rc or ""),
                            'rating_source': f'{fmt}-js'
                        }
    except Exception:
        pass
    
    # No ratings found, but return JSON-LD structure
    return {
        'html': html,
        'items': items,
        'rating_value': None,
        'rating_count': None,
        'rating_source': ''
    }


def extract_ratings_js(url: str, timeout_ms: int = 20000) -> Optional[Tuple[str, str, str]]:
    """
    Legacy function for backwards compatibility.
    Extracts only ratings using JS rendering.
    Returns (rating_value, rating_count, source) or None.
    
    NOTE: Prefer using extract_with_js() for efficiency (gets both structure and ratings).
    """
    result = extract_with_js(url, timeout_ms)
    if result and result['rating_value']:
        return (result['rating_value'], result['rating_count'], result['rating_source'])
    return None
