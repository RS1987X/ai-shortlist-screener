
import extruct
from bs4 import BeautifulSoup
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
    return {
        "sku": p.get("sku"),
        "mpn": p.get("mpn"),
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
