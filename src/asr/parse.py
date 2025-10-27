
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
