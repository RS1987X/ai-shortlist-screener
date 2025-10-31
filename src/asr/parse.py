
import extruct
from bs4 import BeautifulSoup
import json
import re
from w3lib.html import get_base_url

def extract_jsonld(html: str, url: str):
    base_url = get_base_url(html, url)
    data = extruct.extract(html, base_url=base_url, syntaxes=["json-ld"], errors="ignore")
    return data.get("json-ld", []) or []

def has_server_rendered_jsonld(html: str) -> bool:
    soup = BeautifulSoup(html, "lxml")
    return bool(soup.find("script", attrs={"type": "application/ld+json"}))

def classify_schema(items):
    buckets = {"Product": [], "Offer": [], "ProductGroup": [], "Service": [], "AggregateRating": []}
    for it in items:
        t = it.get("@type")
        if isinstance(t, list):
            t = next((x for x in t if isinstance(x, str)), None)
        if not isinstance(t, str):
            continue
        if t in buckets:
            buckets[t].append(it)
    return buckets

def product_identifiers(p):
    brand = p.get("brand")
    if isinstance(brand, dict):
        brand = brand.get("name")
    
    # Schema.org accepts both generic 'gtin' and specific variants
    # Generic 'gtin' can be any length (8/12/13/14 digits)
    gtin_generic = p.get("gtin")
    
    return {
        "sku": p.get("sku"),
        "mpn": p.get("mpn"),
        "gtin": gtin_generic,  # Generic GTIN (any length)
        "gtin8": p.get("gtin8"),
        "gtin12": p.get("gtin12"),
        "gtin13": p.get("gtin13"),
        "gtin14": p.get("gtin14"),
        "brand": brand,
    }

def has_units(additional_props):
    for ap in additional_props or []:
        val = ap.get("value")
        if isinstance(val, str) and any(u in val for u in [" W"," kW"," L"," l"," mm"," cm"," dB"," m³/h"," lm"," kg"]):
            return True
    return False

def has_policy_links(html: str) -> bool:
    """
    Check if the page contains links to policy pages (returns, warranty, köpvillkor).
    Returns True if at least one policy-related link is found.
    Checks both rendered HTML links and embedded JSON/data structures.
    """
    soup = BeautifulSoup(html, "lxml")
    
    # Primary check: Look for links with policy-related keywords in href or text
    policy_keywords = [
        "return", "retur", "ånger", "köpvillkor", "kopvillkor", 
        "warranty", "garanti", "terms", "villkor", "policy", "shipping", "frakt"
    ]
    
    for a in soup.find_all("a", href=True):
        href = a.get("href", "").lower()
        text = a.get_text().lower()
        if any(kw in href or kw in text for kw in policy_keywords):
            return True
    
    # Fallback: Search raw HTML for policy URLs (catches JS-embedded or CMS data)
    # This is useful when footers/links are dynamically rendered
    html_lower = html.lower()
    policy_patterns = [
        "köpvillkor", "kopvillkor", "/terms", "/warranty", "/garanti",
        "returnpolicy", "return-policy", "/retur"
    ]
    if any(pattern in html_lower for pattern in policy_patterns):
        return True
    
    return False

def extract_policy_urls(html: str, base_url: str) -> list:
    """
    Extract policy page URLs from the HTML.
    Returns a list of absolute URLs to policy pages.
    """
    from urllib.parse import urljoin
    import re
    
    soup = BeautifulSoup(html, "lxml")
    policy_urls = set()
    
    # Policy-related keywords for href/text matching
    policy_keywords = [
        "return", "retur", "ånger", "köpvillkor", "kopvillkor", 
        "warranty", "garanti", "terms", "villkor", "policy", "shipping", "frakt"
    ]
    
    # Extract from <a> tags
    for a in soup.find_all("a", href=True):
        href = a.get("href", "")
        text = a.get_text().lower()
        href_lower = href.lower()
        
        if any(kw in href_lower or kw in text for kw in policy_keywords):
            # Convert to absolute URL
            absolute_url = urljoin(base_url, href)
            policy_urls.add(absolute_url)
    
    # Extract from raw HTML (JSON/data structures)
    policy_patterns = [
        r'["\']([^"\']*(?:köpvillkor|kopvillkor|terms|warranty|garanti|return-?policy|retur)[^"\']*)["\']'
    ]
    
    for pattern in policy_patterns:
        matches = re.findall(pattern, html, re.IGNORECASE)
        for match in matches:
            # Filter to likely URLs (starts with / or http)
            if match.startswith('/') or match.startswith('http'):
                absolute_url = urljoin(base_url, match)
                policy_urls.add(absolute_url)
    
    return list(policy_urls)

def extract_ratings_fallback(html: str):
    """
    Attempt to extract rating value and count from embedded, non-JSON-LD sources
    available in the initial HTML (no JS execution):
      - script[type="application/json"] blobs (e.g., Hypernova/Next/SPA payloads)
      - Inline JS assignments (limited patterns), e.g., window.CURRENT_PAGE

    Returns a tuple (rating_value, rating_count, source) where values are strings
    (to match CSV writing) or None if not found.
    """
    soup = BeautifulSoup(html, "lxml")

    # Helper: recursively scan for rating signals inside a Python dict/list
    def scan_obj(obj):
        rating = None
        count = None

        rating_keys = {"ratingValue", "averageScore", "averageRating", "rating", "score"}
        count_keys = {"ratingCount", "reviewCount", "numberOfReviews", "numberOfRatings"}

        def _recurse(o):
            nonlocal rating, count
            if isinstance(o, dict):
                # If this dict contains both a rating-like and count-like key, capture and stop
                for rk in rating_keys:
                    if rk in o and isinstance(o[rk], (int, float, str)) and rating is None:
                        try:
                            rating = float(str(o[rk]).replace(",", "."))
                        except Exception:
                            pass
                for ck in count_keys:
                    if ck in o and isinstance(o[ck], (int, float, str)) and count is None:
                        try:
                            # counts should be integers where possible
                            count = int(str(o[ck]).split(".")[0].replace(" ", "").replace(",", ""))
                        except Exception:
                            pass
                # Early exit if both found
                if rating is not None and count is not None:
                    return
                for v in o.values():
                    _recurse(v)
            elif isinstance(o, list):
                for it in o:
                    _recurse(it)
            # Primitives ignored

        _recurse(obj)
        return rating, count

    # 1) Embedded JSON blobs
    for sc in soup.find_all("script", attrs={"type": "application/json"}):
        txt = sc.string or sc.get_text() or ""
        if not txt.strip():
            continue
        try:
            data = json.loads(txt)
        except Exception:
            continue
        r, c = scan_obj(data)
        if r is not None:
            # Prefer integer counts; stringify for CSV
            return str(r), (str(c) if c is not None else ""), "application/json"

    # 2) Limited inline JS patterns (no full JS execution). Try to capture
    # JSON literals from well-known JS variable assignments
    raw = html

    # Try to extract JSON objects from common JS variable patterns
    js_var_patterns = [
        r'window\.__NEXT_DATA__\s*=\s*({.+?});',
        r'window\.__INITIAL_STATE__\s*=\s*({.+?});',
        r'var\s+CURRENT_PAGE\s*=\s*({.+?});',
        r'window\.CURRENT_PAGE\s*=\s*({.+?});',
        r'CURRENT_PAGE\s*=\s*({.+?});',
    ]
    
    for pattern in js_var_patterns:
        match = re.search(pattern, raw, re.DOTALL)
        if match:
            try:
                import json
                data = json.loads(match.group(1))
                r, c = scan_obj(data)
                if r is not None:
                    return str(r), (str(c) if c is not None else ""), "inline_js"
            except Exception:
                # JSON parse failed, continue to next pattern
                pass

    # Fallback: Quick-win regexes for numeric values (less reliable)
    js_rating_patterns = [
        r'\b"averageRating"\s*:\s*([0-9]+(?:\.[0-9]+)?)',
        r'\b"averageScore"\s*:\s*([0-9]+(?:\.[0-9]+)?)',
        r'\b"ratingValue"\s*:\s*([0-9]+(?:\.[0-9]+)?)',
        r'\b"rating"\s*:\s*([0-9]+(?:\.[0-9]+)?)'
    ]
    js_count_patterns = [
        r'\b"numberOfReviews"\s*:\s*([0-9]+)',
        r'\b"numberOfRatings"\s*:\s*([0-9]+)',
        r'\b"reviewCount"\s*:\s*([0-9]+)',
        r'\b"ratingCount"\s*:\s*([0-9]+)'
    ]

    rating_match = None
    for pat in js_rating_patterns:
        m = re.search(pat, raw)
        if m:
            rating_match = m.group(1)
            break
    count_match = None
    for pat in js_count_patterns:
        m = re.search(pat, raw)
        if m:
            count_match = m.group(1)
            break

    if rating_match:
        return rating_match, (count_match or ""), "inline_js"

    return None
